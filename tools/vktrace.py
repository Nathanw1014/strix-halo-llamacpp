#!/usr/bin/env python3
"""Post-process GGML_VK_PERF_TRACE Chrome-trace files.

The trace is produced by the Vulkan backend (branch vk-perf-trace) with:

    GGML_VK_PERF_TRACE=trace.json ./bin/llama-bench -m model.gguf ...

and is viewable directly in ui.perfetto.dev. This script gives terminal
summaries the timeline UI does not:

    vktrace.py summary trace.json [--top 25] [--by-op]
    vktrace.py layers  trace.json
    vktrace.py graphs  trace.json
    vktrace.py gaps    trace.json [--min-us 20] [--top 25]
    vktrace.py diff    a.json b.json [--top 25]

Modes of the underlying capture matter for interpretation:
  - default (per-op): graph is serialized by barriers; durations are isolated
    op times; the sum overstates wall-clock. Use for kernel attribution.
  - GGML_VK_PERF_LOGGER_CONCURRENT=1: timestamps only at natural sync points;
    real overlapped execution. Use for wall-clock and bubble analysis.

Diff caveat: single runs of big models can spread 20-30% between identical
launches. Treat small deltas as noise until reproduced.
"""

import argparse
import json
import re
import sys
from collections import defaultdict


def load_events(path):
    """Load a possibly-unterminated Chrome trace event array."""
    with open(path) as f:
        text = f.read().strip()
    if text.endswith(","):
        text = text[:-1]
    if not text.endswith("]"):
        text += "]"
    events = json.loads(text)
    meta = {}
    complete = []
    for ev in events:
        if ev.get("ph") == "M" and ev.get("name") == "thread_name":
            meta[ev["tid"]] = ev["args"]["name"]
        elif ev.get("ph") == "X":
            complete.append(ev)
    gpu = [e for e in complete if meta.get(e["tid"], "GPU") == "GPU"]
    cpu = [e for e in complete if meta.get(e["tid"]) == "CPU"]
    gpu.sort(key=lambda e: e["ts"])
    cpu.sort(key=lambda e: e["ts"])
    return gpu, cpu


def n_graphs(events):
    return len({e.get("args", {}).get("graph") for e in events if "args" in e}) or 1


def fmt_us(us):
    if us >= 1e6:
        return f"{us / 1e6:9.3f} s"
    if us >= 1e3:
        return f"{us / 1e3:9.3f} ms"
    return f"{us:9.1f} us"


def rollup(gpu, key_fn):
    agg = defaultdict(lambda: {"n": 0, "us": 0.0, "flops": 0.0, "bytes": 0.0})
    for e in gpu:
        k = key_fn(e)
        if k is None:
            continue
        a = agg[k]
        a["n"] += 1
        a["us"] += e["dur"]
        args = e.get("args", {})
        # gflops/gbps are flops-per-ns / bytes-per-ns; dur is us
        if "gflops" in args:
            a["flops"] += args["gflops"] * e["dur"] * 1e3
        if "gbps" in args:
            a["bytes"] += args["gbps"] * e["dur"] * 1e3
    return agg


def print_rollup(agg, total_us, top, header):
    rows = sorted(agg.items(), key=lambda kv: -kv[1]["us"])
    print(f"\n{header}")
    print(f"{'total':>12} {'%':>6} {'count':>7} {'mean us':>9} {'GFLOP/s':>8} {'GB/s':>7}  name")
    for name, a in rows[:top]:
        gflops = a["flops"] / (a["us"] * 1e3) if a["us"] > 0 and a["flops"] > 0 else 0
        gbps = a["bytes"] / (a["us"] * 1e3) if a["us"] > 0 and a["bytes"] > 0 else 0
        print(f"{fmt_us(a['us'])} {100 * a['us'] / total_us:5.1f}% {a['n']:7d} "
              f"{a['us'] / a['n']:9.1f} {gflops:8.0f} {gbps:7.1f}  {name[:110]}")
    if len(rows) > top:
        rest = sum(a["us"] for _, a in rows[top:])
        print(f"{fmt_us(rest)} {100 * rest / total_us:5.1f}% ... {len(rows) - top} more entries")


def cmd_summary(args):
    gpu, cpu = load_events(args.trace)
    if not gpu:
        sys.exit("no GPU events in trace")
    wall = gpu[-1]["ts"] + gpu[-1]["dur"] - gpu[0]["ts"]
    busy = sum(e["dur"] for e in gpu)
    ng = n_graphs(gpu)
    print(f"{args.trace}: {len(gpu)} GPU events over {ng} graphs")
    print(f"window wall {fmt_us(wall).strip()}, GPU busy {fmt_us(busy).strip()} "
          f"({100 * busy / wall:.1f}%), busy/graph {fmt_us(busy / ng).strip()}")
    if cpu:
        rec = sum(e["dur"] for e in cpu if e["name"] == "graph_record_submit")
        wai = sum(e["dur"] for e in cpu if e["name"] == "graph_wait")
        print(f"CPU record+submit {fmt_us(rec).strip()}, fence wait {fmt_us(wai).strip()}")
    key = (lambda e: e.get("args", {}).get("op", e["name"])) if args.by_op else (lambda e: e["name"])
    print_rollup(rollup(gpu, key), busy, args.top,
                 "by op" if args.by_op else "by op+shape (perf-logger bucket names)")


LAYER_RE = re.compile(r"blk\.(\d+)|-(\d+)$")


def layer_of(e):
    t = e.get("args", {}).get("tensor", "")
    m = LAYER_RE.search(t)
    if m:
        return int(m.group(1) or m.group(2))
    return None


def cmd_layers(args):
    gpu, _ = load_events(args.trace)
    agg = rollup(gpu, layer_of)
    if not agg:
        sys.exit("no layer-attributable events (concurrent-mode traces group ops; use per-op mode)")
    attributed = sum(a["us"] for a in agg.values())
    total = sum(e["dur"] for e in gpu)
    med = sorted(a["us"] for a in agg.values())[len(agg) // 2]
    print(f"{args.trace}: {100 * attributed / total:.1f}% of GPU time attributable to layers")
    print(f"{'layer':>5} {'total':>12} {'count':>7}  (* = >1.25x median)")
    for layer in sorted(agg):
        a = agg[layer]
        bar = "#" * int(40 * a["us"] / max(v["us"] for v in agg.values()))
        flag = " *" if a["us"] > 1.25 * med else ""
        print(f"{layer:5d} {fmt_us(a['us'])} {a['n']:7d}  {bar}{flag}")


def cmd_graphs(args):
    gpu, cpu = load_events(args.trace)
    per = defaultdict(lambda: {"busy": 0.0, "n": 0, "t0": None, "t1": None})
    for e in gpu:
        g = e.get("args", {}).get("graph")
        p = per[g]
        p["busy"] += e["dur"]
        p["n"] += 1
        p["t0"] = e["ts"] if p["t0"] is None else min(p["t0"], e["ts"])
        p["t1"] = max(p["t1"] or 0, e["ts"] + e["dur"])
    cpu_per = defaultdict(dict)
    for e in cpu:
        cpu_per[e.get("args", {}).get("graph")][e["name"]] = e["dur"]
    print(f"{'graph':>6} {'nodes':>6} {'gpu busy':>12} {'gpu span':>12} {'cpu rec+sub':>12} {'cpu wait':>12}")
    for g in sorted(per, key=lambda x: (x is None, x)):
        p = per[g]
        c = cpu_per.get(g, {})
        print(f"{str(g):>6} {p['n']:6d} {fmt_us(p['busy'])} {fmt_us(p['t1'] - p['t0'])} "
              f"{fmt_us(c.get('graph_record_submit', 0))} {fmt_us(c.get('graph_wait', 0))}")


def cmd_gaps(args):
    gpu, cpu = load_events(args.trace)
    gaps = []
    for a, b in zip(gpu, gpu[1:]):
        end = a["ts"] + a["dur"]
        gap = b["ts"] - end
        if gap >= args.min_us:
            gaps.append((gap, end, a, b))
    gaps.sort(key=lambda g: -g[0])
    total_gap = sum(g[0] for g in gaps)
    wall = gpu[-1]["ts"] + gpu[-1]["dur"] - gpu[0]["ts"] if gpu else 0
    print(f"{len(gaps)} gaps >= {args.min_us} us, total {fmt_us(total_gap).strip()} "
          f"({100 * total_gap / wall:.1f}% of window)")
    for gap, at, a, b in gaps[: args.top]:
        ga = a.get("args", {}).get("graph")
        gb = b.get("args", {}).get("graph")
        kind = "between graphs (host code)" if ga != gb else "in-graph bubble"
        print(f"{fmt_us(gap)} at t={at / 1e3:.3f}ms  {kind}")
        print(f"{'':>12}   after: {a['name'][:90]}")
        print(f"{'':>12}  before: {b['name'][:90]}")


def cmd_diff(args):
    ga, _ = load_events(args.a)
    gb, _ = load_events(args.b)
    na, nb = n_graphs(ga), n_graphs(gb)
    ra = rollup(ga, lambda e: e["name"])
    rb = rollup(gb, lambda e: e["name"])
    print(f"A: {args.a} ({na} graphs)  B: {args.b} ({nb} graphs), per-graph normalized")
    rows = []
    for name in set(ra) | set(rb):
        ua = ra[name]["us"] / na if name in ra else 0.0
        ub = rb[name]["us"] / nb if name in rb else 0.0
        rows.append((ub - ua, ua, ub, name))
    rows.sort(key=lambda r: -abs(r[0]))
    ta = sum(r[1] for r in rows)
    tb = sum(r[2] for r in rows)
    print(f"{'A us/graph':>12} {'B us/graph':>12} {'delta':>10} {'%':>7}  name")
    print(f"{ta:12.1f} {tb:12.1f} {tb - ta:+10.1f} {100 * (tb - ta) / ta if ta else 0:+6.1f}%  TOTAL")
    for d, ua, ub, name in rows[: args.top]:
        pct = f"{100 * d / ua:+6.1f}%" if ua > 0 else "   new"
        print(f"{ua:12.1f} {ub:12.1f} {d:+10.1f} {pct}  {name[:100]}")
    print("\nnote: single-launch runs can spread; reproduce before trusting small deltas")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("summary", help="top ops by GPU time, busy %%")
    s.add_argument("trace")
    s.add_argument("--top", type=int, default=25)
    s.add_argument("--by-op", action="store_true", help="collapse shapes into one row per op")
    s.set_defaults(fn=cmd_summary)

    s = sub.add_parser("layers", help="per-layer rollup from tensor names")
    s.add_argument("trace")
    s.set_defaults(fn=cmd_layers)

    s = sub.add_parser("graphs", help="per-graph busy/span/CPU table")
    s.add_argument("trace")
    s.set_defaults(fn=cmd_graphs)

    s = sub.add_parser("gaps", help="GPU idle gaps: bubbles and host time")
    s.add_argument("trace")
    s.add_argument("--min-us", type=float, default=20.0)
    s.add_argument("--top", type=int, default=25)
    s.set_defaults(fn=cmd_gaps)

    s = sub.add_parser("diff", help="A/B compare two traces by bucket name")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--top", type=int, default=25)
    s.set_defaults(fn=cmd_diff)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
