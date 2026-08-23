#!/usr/bin/env python3
"""Compare GGML_VK_PERF_TRACE and GGML_CUDA_PERF_TRACE captures op by op.

The traces come from two branches of Nathanw1014/llama.cpp, neither of which is upstream:

    vk-perf-trace      GGML_VK_PERF_TRACE=<file>     Vulkan backend
    cuda-perf-trace    GGML_CUDA_PERF_TRACE=<file>   HIP / CUDA backend

Both emit the same Chrome-trace schema (see tools/vktrace.py), so one aggregator handles
either. This adds what a cross-backend comparison needs and vktrace.py lacks:

  - condition splitting: a single llama-bench launch with -ub 256,2048 puts both conditions in
    one trace. Graphs are classified by the modal MUL_MAT n= in their event names.
  - repetition selection: only the LAST repetition of a condition is kept, so first-call kernel
    load (a 29 ms outlier on the first matmul of the first graph) is excluded.
  - op categories, and a per-shape MUL_MAT table with achieved GFLOP/s.

    tracecmp.py conditions <trace.json>
    tracecmp.py report <trace.json> [--cond N] [--categories]
    tracecmp.py compare <label=trace.json> ... [--cond N] [--json out.json]

--prompt must match the prompt length the trace was captured at (default 2048). Getting it
wrong does not error, it silently mis-selects which repetition is kept. Run `conditions`
first: it prints the condition split it found, which is the cheap check that the trace and
the flags agree.

Interpretation, and it is not symmetric:
  - HIP: events bracket nodes on one stream, no serialization, so durations sum to wall clock.
  - Vulkan per-op: barriers between ops, so durations are ISOLATED op times and their sum
    overstates wall clock wherever the real schedule overlaps.
  - Vulkan concurrent: timestamps only at natural sync points. Totals are wall-clock true,
    per-op names are not meaningful.
"""

import argparse
import json
import re
import sys
from collections import defaultdict

# ordered: first match wins
CATEGORIES = [
    ("matmul (dense)",  {"MUL_MAT"}),
    ("matmul (MoE)",    {"MUL_MAT_ID"}),
    ("flash attn",      {"FLASH_ATTN_EXT"}),
    ("attn (no FA)",    {"SOFT_MAX", "DIAG_MASK_INF"}),
    ("norm",            {"RMS_NORM", "NORM", "GROUP_NORM", "L2_NORM"}),
    ("rope",            {"ROPE", "ROPE_BACK"}),
    ("glu / unary",     {"GLU", "UNARY", "SILU_BACK"}),
    ("elementwise",     {"ADD", "MUL", "SUB", "DIV", "SCALE", "SQR", "SQRT", "CLAMP",
                         "ADD_ID", "SUM_ROWS", "MEAN"}),
    ("copy / cache",    {"CPY", "CONT", "DUP", "SET_ROWS", "GET_ROWS", "CONCAT", "SET", "PAD",
                         "VIEW", "RESHAPE", "PERMUTE", "TRANSPOSE"}),
]


def load(path):
    with open(path) as f:
        text = f.read().strip()
    if text.endswith(","):
        text = text[:-1]
    if not text.endswith("]"):
        text += "]"
    events = json.loads(text)
    meta, gpu, cpu = {}, [], []
    for ev in events:
        if ev.get("ph") == "M" and ev.get("name") == "thread_name":
            meta[ev["tid"]] = ev["args"]["name"]
    for ev in events:
        if ev.get("ph") != "X":
            continue
        (cpu if meta.get(ev["tid"]) == "CPU" else gpu).append(ev)
    gpu.sort(key=lambda e: e["ts"])
    cpu.sort(key=lambda e: e["ts"])
    return gpu, cpu


N_RE = re.compile(r" n=(\d+)")


def graph_cond(events):
    """Condition label for one graph: the modal n= over its matmul events."""
    counts = defaultdict(int)
    for e in events:
        m = N_RE.search(e["name"])
        if m:
            counts[int(m.group(1))] += 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def by_graph(gpu):
    out = defaultdict(list)
    for e in gpu:
        out[e.get("args", {}).get("graph")].append(e)
    return out


def conditions(gpu):
    """[(cond_n, [graph ids in trace order]), ...] with graphs grouped into runs of one cond."""
    graphs = by_graph(gpu)
    seq = [(g, graph_cond(graphs[g])) for g in sorted(graphs, key=lambda x: (x is None, x))]
    runs = []
    for g, c in seq:
        if runs and runs[-1][0] == c:
            runs[-1][1].append(g)
        else:
            runs.append((c, [g]))
    return runs


def last_repetition(gpu, cond=None, per_rep=None, prompt=2048):
    """Graph ids of the final repetition of the requested condition.

    llama-bench runs a warmup pass then -r repetitions, each covering prompt/ubatch graphs, and
    a condition's graphs arrive as one contiguous run. Taking the LAST prompt/ubatch graphs
    drops the warmup, and with it the one-time kernel load that costs 29 ms on the first matmul
    of the first graph. The condition label IS the ubatch for prefill traces, so per_rep is
    derived; pass --per-rep for decode traces, where every graph is one token.
    """
    runs = conditions(gpu)
    if cond is not None:
        runs = [r for r in runs if r[0] == cond]
        if not runs:
            sys.exit(f"no graphs for condition n={cond}")
    ids = [g for _, gs in runs for g in gs]
    if per_rep is None:
        per_rep = max(1, prompt // cond) if cond else len(ids)
    per_rep = min(per_rep, len(ids))
    return ids[-per_rep:]


def category_of(op):
    for name, ops in CATEGORIES:
        if op in ops:
            return name
    return "other"


def rollup(gpu, key_fn):
    agg = defaultdict(lambda: {"n": 0, "us": 0.0, "flops": 0.0, "bytes": 0.0})
    for e in gpu:
        k = key_fn(e)
        if k is None:
            continue
        a = agg[k]
        args = e.get("args", {})
        a["n"] += 1
        a["us"] += e["dur"]
        if "gflops" in args:
            a["flops"] += args["gflops"] * e["dur"] * 1e3
        if "gbps" in args:
            a["bytes"] += args["gbps"] * e["dur"] * 1e3
    return agg


def window(gpu, cpu, ids):
    idset = set(ids)
    g = [e for e in gpu if e.get("args", {}).get("graph") in idset]
    c = [e for e in cpu if e.get("args", {}).get("graph") in idset]
    return g, c


def stats(g, c, n_graphs):
    busy = sum(e["dur"] for e in g)
    span = max(e["ts"] + e["dur"] for e in g) - min(e["ts"] for e in g) if g else 0.0
    rec = sum(e["dur"] for e in c if e["name"] == "graph_record_submit")
    wait = sum(e["dur"] for e in c if e["name"] == "graph_wait")
    n_nodes = 0
    for e in c:
        if e["name"] == "graph_record_submit":
            n_nodes += e.get("args", {}).get("n_nodes", 0)
    return {"busy_us": busy, "span_us": span, "dispatches": len(g), "graphs": n_graphs,
            "cpu_record_us": rec, "cpu_wait_us": wait, "graph_nodes": n_nodes}


def fmt(us):
    if us >= 1e6:
        return f"{us / 1e6:8.3f} s"
    if us >= 1e3:
        return f"{us / 1e3:8.3f} ms"
    return f"{us:8.1f} us"


def cmd_conditions(a):
    gpu, _ = load(a.trace)
    graphs = by_graph(gpu)
    print(f"{a.trace}: {len(gpu)} GPU events, {len(graphs)} graphs")
    for cond, ids in conditions(gpu):
        sizes = [len(graphs[g]) for g in ids]
        print(f"  cond n={cond}: {len(ids)} graphs {ids[:3]}{'...' if len(ids) > 3 else ''} "
              f"nodes/graph {min(sizes)}-{max(sizes)}")
    for cond, _ in conditions(gpu):
        sel = last_repetition(gpu, cond, a.per_rep, a.prompt)
        print(f"  cond n={cond}: final repetition = {len(sel)} graphs {sel}")


def cmd_report(a):
    gpu, cpu = load(a.trace)
    ids = last_repetition(gpu, a.cond, a.per_rep, a.prompt)
    g, c = window(gpu, cpu, ids)
    s = stats(g, c, len(ids))
    print(f"{a.trace}  cond={a.cond}  graphs={s['graphs']}  dispatches={s['dispatches']}"
          f"  graph_nodes={s['graph_nodes'] or 'n/a'}")
    print(f"  GPU busy {fmt(s['busy_us']).strip()}   span {fmt(s['span_us']).strip()}"
          f"   busy/span {100 * s['busy_us'] / s['span_us']:.1f}%")
    print(f"  CPU record+submit {fmt(s['cpu_record_us']).strip()}   wait {fmt(s['cpu_wait_us']).strip()}")
    key = (lambda e: category_of(e.get("args", {}).get("op", "?"))) if a.categories else (lambda e: e["name"])
    agg = rollup(g, key)
    print(f"\n{'total':>11} {'%':>6} {'count':>7} {'mean us':>9} {'GFLOP/s':>8} {'GB/s':>7}  name")
    for name, v in sorted(agg.items(), key=lambda kv: -kv[1]["us"])[:a.top]:
        gf = v["flops"] / (v["us"] * 1e3) if v["us"] and v["flops"] else 0
        gb = v["bytes"] / (v["us"] * 1e3) if v["us"] and v["bytes"] else 0
        print(f"{fmt(v['us'])} {100 * v['us'] / s['busy_us']:5.1f}% {v['n']:7d} "
              f"{v['us'] / v['n']:9.1f} {gf:8.0f} {gb:7.1f}  {name[:100]}")


def collect(path, cond, per_rep=None, prompt=2048):
    gpu, cpu = load(path)
    ids = last_repetition(gpu, cond, per_rep, prompt)
    g, c = window(gpu, cpu, ids)
    s = stats(g, c, len(ids))
    cats = {k: dict(v) for k, v in rollup(g, lambda e: category_of(e.get("args", {}).get("op", "?"))).items()}
    shapes = {k: dict(v) for k, v in rollup(g, lambda e: e["name"]).items()}
    ops = {k: dict(v) for k, v in rollup(g, lambda e: e.get("args", {}).get("op", "?")).items()}
    return {"trace": path, "cond": cond, "stats": s, "categories": cats, "shapes": shapes, "ops": ops}


def cmd_compare(a):
    arms = {}
    for spec in a.arms:
        label, _, path = spec.partition("=")
        arms[label] = collect(path, a.cond, a.per_rep, a.prompt)

    print(f"condition: matmul n={a.cond}\n")
    print(f"{'arm':<22} {'dispatch':>9} {'GPU busy':>11} {'span':>11} {'busy/span':>10} "
          f"{'cpu launch':>11} {'cpu wait':>11}")
    for label, d in arms.items():
        s = d["stats"]
        print(f"{label:<22} {s['dispatches']:9d} {fmt(s['busy_us'])} {fmt(s['span_us'])} "
              f"{100 * s['busy_us'] / s['span_us']:9.1f}% {fmt(s['cpu_record_us'])} {fmt(s['cpu_wait_us'])}")

    cats = sorted({c for d in arms.values() for c in d["categories"]},
                  key=lambda c: -max(d["categories"].get(c, {}).get("us", 0) for d in arms.values()))
    print(f"\n{'category':<16}" + "".join(f"{l:>26}" for l in arms))
    print(f"{'':<16}" + "".join(f"{'time':>11}{'%':>6}{'count':>9}" for _ in arms))
    for cat in cats:
        row = f"{cat:<16}"
        for label, d in arms.items():
            v = d["categories"].get(cat, {"us": 0.0, "n": 0})
            busy = d["stats"]["busy_us"]
            row += f"{fmt(v['us'])}{100 * v['us'] / busy:6.1f}%{v['n']:9d}"
        print(row)

    print(f"\nMUL_MAT by shape (time, achieved GFLOP/s)")
    shapes = sorted({s for d in arms.values() for s in d["shapes"] if s.startswith("MUL_MAT")},
                    key=lambda s: -max(d["shapes"].get(s, {}).get("us", 0) for d in arms.values()))
    print(f"{'shape':<44}" + "".join(f"{l:>26}" for l in arms))
    for sh in shapes[:a.top]:
        row = f"{sh:<44}"
        for label, d in arms.items():
            v = d["shapes"].get(sh)
            if not v:
                row += f"{'-':>26}"
                continue
            gf = v["flops"] / (v["us"] * 1e3) if v["us"] and v["flops"] else 0
            row += f"{fmt(v['us'])}{gf:9.0f}{v['n']:8d}"
        print(row)

    if a.json:
        with open(a.json, "w") as f:
            json.dump(arms, f, indent=1)
        print(f"\nwrote {a.json}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    for sp in ():
        pass
    c = sub.add_parser("conditions"); c.add_argument("trace"); c.set_defaults(fn=cmd_conditions)

    r = sub.add_parser("report")
    r.add_argument("trace"); r.add_argument("--cond", type=int); r.add_argument("--top", type=int, default=25)
    r.add_argument("--categories", action="store_true"); r.set_defaults(fn=cmd_report)

    m = sub.add_parser("compare")
    m.add_argument("arms", nargs="+", help="label=trace.json")
    m.add_argument("--cond", type=int, required=True); m.add_argument("--top", type=int, default=14)
    m.add_argument("--json"); m.set_defaults(fn=cmd_compare)

    for sp in (c, r, m):
        sp.add_argument("--per-rep", type=int, default=None,
                        help="graphs per repetition; derived as prompt/ubatch when omitted")
        sp.add_argument("--prompt", type=int, default=2048, help="prompt length of the capture")
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
