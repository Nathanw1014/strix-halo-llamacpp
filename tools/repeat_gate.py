#!/usr/bin/env python3
# Send the SAME request N times into ONE llama-server process and compare the
# responses to EACH OTHER.
#
# Why this exists: on 2026-08-31 the Qwen3.8-Flash-Next (qwen4exp) port was found to
# produce a different greedy continuation on every request after the first, diverging
# at the very first generated token. Three purpose-built gates, a KL-divergence packet
# and a full static-logit comparison all passed. Every one of them compared arm A
# against arm B at the SAME request index, and both arms drifted identically by index,
# so they always agreed. Perplexity and KLD cannot see it at all: they request logits
# for every row, which makes the graph's inp_out_ids gather a no-op.
#
# The check that catches it needs no second arm and no reference: repeat one request
# and diff the answers against each other.
#
# usage:
#   repeat_gate.py --bin BUILD/bin/llama-server --model M.gguf [-- SERVER ARGS...]
#   repeat_gate.py --bin ... --model ... --reps 8 --predict 48 --prompt-file p.txt
#
# exit status: 0 = PASS, 1 = FAIL, 0 with a WARN line = first-request-only difference
# (a hybrid/recurrent warm-up signature that upstream llama.cpp also shows; it is not
# progressive drift, but it still means request 0 is not reproducible).

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Several prompts of DIFFERENT token lengths, deliberately.
#
# This class of bug is extremely sensitive to where the ubatch boundaries land: a single
# trailing newline (one token) on a ~1180-token prompt was measured flipping every arm's
# verdict, including turning a passing build into a failing one and vice versa. One prompt
# is therefore a coin toss, not a gate. These lengths straddle the -ub 512 split so the
# final ubatch has a different row count in each.
_PARA = ("The lightning indexer selects a sparse subset of key blocks for each query token. "
         "Correctness of that selection is what makes the attention output reproducible. ")
_TAIL = "Explain, step by step, why a tie in the selection scores can break greedy reproducibility."

DEFAULT_PROMPTS = {
    "long-nl":   _PARA * 40 + "\n" + _TAIL + "\n",
    "long-nonl": _PARA * 40 + "\n" + _TAIL,
    "mid":       _PARA * 18 + "\n" + _TAIL + "\n",
    "short":     _PARA * 4  + "\n" + _TAIL + "\n",
}


def wait_healthy(port: int, proc: subprocess.Popen, timeout_s: int) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if b'"ok"' in r.read():
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


CACHE_PROMPT = False  # set by --cache-prompt: let the server reuse the cached prefill between identical requests
SUBTOKEN = 0          # set by --subtoken N: request n_probs=N and compare the per-position logprob streams

def generate(port: int, prompt: str, predict: int, seed: int) -> str:
    body = json.dumps({
        "prompt": prompt,
        "n_predict": predict,
        "temperature": 0,
        "top_k": 1,
        "cache_prompt": CACHE_PROMPT,   # default False: force a full re-prefill every time
        "ignore_eos": True,      # fixed length, so EOS variation cannot mask a difference
        "seed": seed,
        **({"n_probs": SUBTOKEN} if SUBTOKEN else {}),
    }).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/completion", body,
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            js = json.loads(r.read())
    except urllib.error.HTTPError as e:
        # a server-side parse failure is itself a difference worth reporting
        LAST_STREAM.append([])
        return f"<<HTTP-{e.code}>>"
    LAST_STREAM.append(probs_stream(js) if SUBTOKEN else [])
    return js["content"]


LAST_STREAM: list = []   # per-request logprob streams, appended by generate() in call order


def probs_stream(js) -> list:
    """[( (id, logprob), (id, logprob), ... ), ...] per generated position, from completion_probabilities.
    Server layout (tools/server/server-task.cpp): each position is {id, token, bytes, logprob,
    top_logprobs:[{id, token, bytes, logprob}, ...]} with post_sampling_probs=false (the default), or
    {.., prob, top_probs:[...]} with it on. Candidate 0 is the position's own token."""
    import math
    def lp_of(c):
        if "logprob" in c:
            return float(c["logprob"])
        pr = float(c.get("prob", 0.0))
        return math.log(pr) if pr > 0 else float("-inf")
    def id_of(c):
        return c.get("id", c.get("token", c.get("tok_str")))
    out = []
    for pos in js.get("completion_probabilities", []) or []:
        row = [(id_of(pos), lp_of(pos))]
        for c in pos.get("top_logprobs") or pos.get("top_probs") or pos.get("probs") or []:
            row.append((id_of(c), lp_of(c)))
        out.append(tuple(row))
    return out


def check_subtoken(name: str, streams: list) -> str:
    """Compare every rep's logprob stream against rep 0. QUIET = all identical (values compared
    exactly, as the server reported them); DETECT otherwise. NB: under graph reuse the server's
    reported logprob for an early position can be aliased by later decodes, so the POSITION is
    indicative only; the verdict is exact."""
    if not streams or not streams[0]:
        print(f"[{name}] SUBTOKEN: no completion_probabilities in the response (server too old?)")
        return "ERROR"
    n_c0 = len(streams[0][0]) if streams[0] else 0
    if n_c0 < 2:
        print(f"[{name}] SUBTOKEN: ERROR - {n_c0} candidate(s) per position; the server returned no top_logprobs list, refusing a vacuous QUIET")
        return "ERROR"
    base = streams[0]
    n_pos = len(base); n_c = len(base[0]) if base else 0
    diffs = []
    for i, st in enumerate(streams[1:], 1):
        first = None; maxd = 0.0; ndiff = 0
        for p in range(min(len(base), len(st))):
            if base[p] != st[p]:
                ndiff += 1
                if first is None:
                    first = p
                for (ta, la), (tb, lb) in zip(base[p], st[p]):
                    if ta == tb and la == la and lb == lb:
                        maxd = max(maxd, abs(la - lb))
                    else:
                        maxd = float("inf")   # candidate identity changed: not a small delta
        if len(base) != len(st):
            ndiff += abs(len(base) - len(st)); first = first if first is not None else min(len(base), len(st))
        if first is not None:
            diffs.append((i, first, ndiff, maxd))
    if not diffs:
        print(f"[{name}] SUBTOKEN: QUIET - {len(streams)} reps, {n_pos} positions x {n_c} candidates, logprob streams identical")
        return "QUIET"
    worst = max(d[3] for d in diffs)
    earliest = min(d[1] for d in diffs)
    print(f"[{name}] SUBTOKEN: DETECT - {len(diffs)}/{len(streams)-1} reps differ from rep 0; "
          f"earliest position {earliest}; max |dlogprob| {'inf (candidate set changed)' if worst == float('inf') else f'{worst:.3e}'}")
    for i, first, ndiff, maxd in diffs[:8]:
        print(f"  rep {i}: first differing position {first}, {ndiff} positions differ, max |dlogprob| "
              f"{'inf' if maxd == float('inf') else f'{maxd:.3e}'}")
    return "DETECT"


def first_diff(a: str, b: str) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def check(name: str, outs: list[str]) -> str:
    uniq = len(set(outs))
    print(f"\n[{name}] {uniq} unique / {len(outs)} requests")
    for i, o in enumerate(outs):
        print(f"  rep {i}  sha {hashlib.sha256(o.encode()).hexdigest()[:16]}  len {len(o)}")
    if uniq == 1:
        return "PASS"
    # classify: first request differing from an otherwise stable tail is the known
    # warm-up signature; anything else is drift and is a hard failure
    if len(set(outs[1:])) == 1:
        j = first_diff(outs[0], outs[1])
        print(f"  rep 0 differs from a stable tail, first at char {j}")
        print(f"    rep0: {outs[0][j:j+60]!r}")
        print(f"    rest: {outs[1][j:j+60]!r}")
        return "WARN"
    for i, o in enumerate(outs[1:], 1):
        if o == outs[0]:
            continue
        j = first_diff(outs[0], o)
        print(f"  rep {i} first differs from rep 0 at char {j}: {outs[0][j:j+40]!r} vs {o[j:j+40]!r}")
    return "FAIL"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True, help="path to llama-server")
    ap.add_argument("--model", required=True)
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--predict", type=int, default=48)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--cache-prompt", action="store_true", help="send cache_prompt:true (server default) instead of forcing a re-prefill")
    ap.add_argument("--allow-warmup", action="store_true", help="old semantics: a rep-0-only difference is WARN (exit 0). Default is strict: any difference FAILS, because the rep-0-only shape is the masked-V leak, not warm-up")
    ap.add_argument("--subtoken", type=int, default=0, metavar="N", help="also request n_probs=N and gate on the per-position logprob streams (sub-token detector); DETECT fails the gate")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--save-dir", default=os.environ.get("REPEAT_GATE_SAVE_DIR"),
                    help="dump every prompt and every raw response into this directory")
    ap.add_argument("--prompt-file", action="append", default=[],
                    help="repeatable; defaults to one built-in ~1200-token prompt")
    ap.add_argument("--load-timeout", type=int, default=2700)
    ap.add_argument("--lock", default=os.environ.get("REPEAT_GATE_LOCK"),
                    help="flock path to serialise against other GPU jobs")
    ap.add_argument("server_args", nargs="*", help="extra llama-server args after --")
    args = ap.parse_args()
    global CACHE_PROMPT
    CACHE_PROMPT = bool(args.cache_prompt)
    global SUBTOKEN
    SUBTOKEN = max(0, int(args.subtoken))

    if args.prompt_file:
        prompts = {p: open(p).read() for p in args.prompt_file}
    else:
        prompts = DEFAULT_PROMPTS

    lock_fd = None
    if args.lock:
        import fcntl
        lock_fd = open(args.lock, "w")
        print(f"waiting for GPU lock {args.lock} ...", flush=True)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

    cmd = [args.bin, "-m", args.model, "--port", str(args.port),
           "--host", "127.0.0.1", "-np", "1"] + args.server_args
    print("+ " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_healthy(args.port, proc, args.load_timeout):
            print("FAIL: server did not become healthy", file=sys.stderr)
            return 1
        verdicts = []
        sub_verdicts = []
        for name, prompt in prompts.items():
            LAST_STREAM.clear()
            outs = [generate(args.port, prompt, args.predict, args.seed)
                    for _ in range(args.reps)]
            streams = list(LAST_STREAM)
            if args.save_dir:
                os.makedirs(args.save_dir, exist_ok=True)
                with open(os.path.join(args.save_dir, f"{os.path.basename(name)}.prompt.txt"), "w") as f:
                    f.write(prompt)
                for i, o in enumerate(outs):
                    with open(os.path.join(args.save_dir, f"{os.path.basename(name)}.rep{i}.txt"), "w") as f:
                        f.write(o)
                if SUBTOKEN:
                    with open(os.path.join(args.save_dir, f"{os.path.basename(name)}.probs.json"), "w") as f:
                        json.dump(streams, f)
            verdicts.append(check(name, outs))
            if SUBTOKEN:
                sub_verdicts.append(check_subtoken(name, streams))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        if lock_fd:
            lock_fd.close()

    print()
    sub_rc = 0
    if SUBTOKEN:
        if "DETECT" in sub_verdicts or "ERROR" in sub_verdicts:
            print("SUBTOKEN GATE: DETECT - logprob streams differ between identical requests (or could not be read)")
            sub_rc = 1
        else:
            print("SUBTOKEN GATE: QUIET - logprob streams identical across all requests")
    if "FAIL" in verdicts:
        print("REPEAT GATE: FAIL - identical requests produced different output")
        return 1
    if "WARN" in verdicts:
        if args.allow_warmup:
            print("REPEAT GATE: WARN - only the first request differs (allowed by --allow-warmup)")
            return sub_rc
        print("REPEAT GATE: FAIL - only the first request differs; that is request-order dependence (masked-V leak class), not warm-up. Use --allow-warmup for the old WARN semantics")
        return 1
    print("REPEAT GATE: PASS - all requests byte-identical")
    return sub_rc


if __name__ == "__main__":
    sys.exit(main())
