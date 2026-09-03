# Trace tooling

Two analyzers for per-dispatch GPU traces from llama.cpp, plus the branches that produce
those traces. Neither the tracers nor these scripts are upstream.

## Getting a trace

The exporters live on two branches of `Nathanw1014/llama.cpp`, one commit each on top of
`strix-halo-vulkan`:

| branch | env var | backend | size |
|---|---|---|---|
| `vk-perf-trace` | `GGML_VK_PERF_TRACE=<file>` | Vulkan | 216 lines, 1 file |
| `cuda-perf-trace` | `GGML_CUDA_PERF_TRACE=<file>` | HIP / CUDA | 289 lines, 2 files |

```bash
git remote add nathan https://github.com/Nathanw1014/llama.cpp.git
git fetch nathan vk-perf-trace && git checkout nathan/vk-perf-trace
# build as usual, then:
GGML_VK_PERF_TRACE=trace.json GGML_VK_PERF_TRACE_SKIP=2 GGML_VK_PERF_TRACE_COUNT=3 \
  ./bin/llama-bench -m model.gguf -p 2048
```

`_SKIP` and `_COUNT` bound the capture window in graph evaluations. Skip at least one:
the first matmul of the first graph carries one-time kernel load, around 29 ms in one
measurement.

Both exporters emit the same Chrome-trace schema (same event names, same `args.op` /
`tensor` / `graph` fields, same thread ids), which is the point: event names line up, so
the same script reads either and the two can be diffed against each other. The JSON opens
directly in `ui.perfetto.dev` for a timeline view.

**The HIP branch deliberately excludes a local integrated-GPU property fix.** On gfx1151 it
compiles and runs but is not numerically or performance-trustworthy on its own. Apply the
tracer on top of a perplexity-validated tree before believing any measurement from it.

## Which script

**`vktrace.py`** - one trace, one backend. Where did the time go?

```bash
python3 tools/vktrace.py summary trace.json [--top 25] [--by-op]
python3 tools/vktrace.py layers  trace.json
python3 tools/vktrace.py graphs  trace.json
python3 tools/vktrace.py gaps    trace.json [--min-us 20]   # host-code vs in-graph bubbles
python3 tools/vktrace.py diff    a.json b.json
```

**`tracecmp.py`** - several traces, possibly different backends. Why is one slower?

```bash
python3 tools/tracecmp.py conditions trace.json          # run this first
python3 tools/tracecmp.py report     trace.json [--categories] [--prompt 2048]
python3 tools/tracecmp.py compare    vk=a.json hip=b.json --cond 2048 [--json out.json]
```

`compare` requires `--cond`, naming the condition to compare across arms. `conditions`
tells you which ones the trace contains.

`tracecmp.py` adds condition splitting (one `llama-bench` launch with `-ub 256,2048` puts
both conditions in one trace, separated by the modal matmul `n=`), repetition selection,
op categories, and a per-shape matmul table with achieved rates.

`--prompt` must match the capture length. Getting it wrong does not error, it silently
mis-selects the repetition. `conditions` prints the split it found and is the cheap check
that the trace and the flags agree.

Both are stdlib-only Python 3, no dependencies.

## Reading cross-backend output without fooling yourself

The two instruments are not symmetric, and this matters more than any flag:

- **HIP** brackets nodes on one stream with no serialization, so node durations sum to wall
  clock (verified at 100.0% busy against span).
- **Vulkan per-op mode** inserts a barrier after every node, so durations are *isolated* op
  times and their sum overstates wall clock wherever the real schedule overlaps. At large
  ubatch on a dense model this agreed with concurrent mode to 0.2%; at small ubatch it does
  not. Measure the divergence for your workload before trusting either.
- **Vulkan concurrent mode** (`GGML_VK_PERF_LOGGER_CONCURRENT=1`) writes timestamps only
  where the backend was already synchronising. Totals are wall-clock true; per-op
  attribution is not meaningful when ops overlapped.

**Per-shape rates are comparable across backends only where dispatch counts match.** That
holds for the prefill shapes we measured. It does not hold in decode, where Vulkan emits two
events per node on some shapes and bills the node's flop estimate to each, inflating its
apparent rate around 2x. Compare time totals there, not rates.

Tracer overhead: at ub2048 both are within +0.5% of untraced. At ub256 the Vulkan tracer
costs 2-6%, because there are many more timestamped dispatches per token. Do not read ub256
cross-backend wall-clock off traced runs.

Background, and the findings these produced: [EXPLORING.md](../EXPLORING.md), particularly
*Instrumentation* and *Dense prefill: a worked example of localising a gap*.

`repeat_gate.py --subtoken N` (2026-09-03): sub-token detector. Requests `n_probs=N` on every
identical greedy request and compares the per-position logprob streams exactly; `SUBTOKEN GATE:
QUIET` or `DETECT` (exit 1). Catches ULP-scale non-repeatability before it flips a token. Also
`--cache-prompt` (server-default prompt reuse instead of a forced re-prefill) and `--prompt-file`
for the 1024-token and 32k shapes. Per-request streams are saved as `<prompt>.probs.json` with
`--save-dir`.
