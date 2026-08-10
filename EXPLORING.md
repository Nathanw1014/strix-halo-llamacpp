# llama.cpp: an explorer's guide, and what we found

A map of the llama.cpp / ggml codebase from the point of view of someone who wants to
make it faster, plus a record of what we actually measured on AMD Strix Halo (gfx1151)
over the last several months: what worked, what shipped, and the larger pile of things
that turned out to be wrong.

The point of the second half is not the wins. It is the falsifications. Most of the
plausible-sounding optimisations in this space are wrong, and the only cheap way to find
that out is to read someone else's list before you spend a week on one.

Status: 2026-08-10. Written against llama.cpp master around `3be50cc`.

Every number below came from a recorded run. Nothing here is estimated, extrapolated,
or reasoned-from-first-principles unless it explicitly says so.

---

## Part 0: how to read this

Findings are tagged:

- **SHIPPED** - merged somewhere public, reproducible from a branch
- **MEASURED** - reproduced on our hardware with artifacts, not yet upstream
- **FALSIFIED** - we tried it, it did not work, here is why
- **OPEN** - known effect, cause not established

If a claim has no tag it is background, not a result.

The hardware unless stated: Framework Desktop, Ryzen AI Max+ 395 (Strix Halo),
64 GB unified LPDDR5X, Radeon 8060S / gfx1151, RADV on mesa-main, `iommu=off`.
A second box (128 GB Blackwell DGX Spark) and an RTX 3070 were used for
cross-platform controls.

---

# Part I: the codebase

## The three layers

llama.cpp is not one project, it is three stacked ones, and almost every performance
question lives at a specific layer. Getting the layer wrong is the most common way to
waste a week.

```
  src/                  llama.cpp proper: tokeniser, sampling, KV cache
                        policy, and per-architecture graph construction
        |
        |  emits a ggml_cgraph (a flat list of tensor nodes)
        v
  ggml/src/ggml.c       ggml core: tensor metadata, op definitions,
  ggml-backend.cpp      the scheduler that assigns nodes to backends
        |
        |  dispatches each node to a backend
        v
  ggml/src/ggml-vulkan/ backend: turns nodes into dispatches
  ggml/src/ggml-cuda/   (Vulkan, CUDA, HIP, Metal, CPU, SYCL, ...)
  ggml/src/ggml-cpu/
```

A useful mental model: **llama.cpp decides what to compute, ggml decides where, the
backend decides how.** If your idea changes the shape of the computation it belongs in
`src/`. If it changes which device runs a node it belongs in the scheduler. If it
changes instruction selection or memory access it belongs in the backend.

## Layer 1: graph construction (`src/`)

Per-architecture graph builders live in `src/models/`, one file per model family, 142 of
them at time of writing. Each builds the forward graph for one architecture using the
shared helpers in `src/llama-graph.cpp`.

Read `src/llama-graph.cpp` first. It contains `build_attn`, `build_ffn`, `build_moe_ffn`
and friends. Nearly every model file is a thin arrangement of these. If you want to know
what tensors flow through attention at depth, this is the only file you need.

`src/llama-kv-cache*.cpp` is where KV layout policy lives. There are several
implementations now (unified, iSWA, hybrid, MSA, DSA, DSv4), which matters because a lot
of "why is attention slow at depth" questions are really "what does the KV cache hand to
the attention op".

Key thing to understand: **the graph is rebuilt every eval, and it is the same graph
every time.** For a 40-layer model you get the same ~50 op shapes repeated 40 times, then
again next token. This is why aggregate per-op statistics are more useful here than they
would be in, say, a game engine, and it is worth keeping in mind when you read the
tooling section below.

## Layer 2: the scheduler (`ggml/src/ggml-backend.cpp`)

This is the highest-leverage file in the repo for debugging, and the least read.

The scheduler walks the graph and assigns each node to a backend, then cuts the graph
into **splits** wherever consecutive nodes land on different backends. Every split
boundary is a synchronisation point and often a host round-trip.

Assignment is driven by each backend's `supports_op` callback. This is a pure predicate:
given a node, can you run it. The contract is that `supports_op` returning true is a
promise, and if the dispatch path later disagrees you do not get a fallback, you get
undefined behaviour or a wrong answer.

We have been bitten by both directions of that mismatch:

- `supports_op` said yes and the dispatch path had no matching pipeline. Produced 84
  `inf` failures that looked like a numerical bug in attention sinks and were not.
  (See *iq4_nl gate* below.)
- `supports_op` said no because tensor metadata was subtly wrong, silently demoting 43
  layers to CPU with no error message at all. (See *issue #2* below.)

The second failure mode is worth dwelling on. **A backend that quietly declines an op
looks exactly like a slow backend.** There is no warning. Your only signal is:

```bash
GGML_SCHED_DEBUG=2 ./llama-cli -m model.gguf -p "test" -n 1 2>&1 | head -100
```

which prints the split structure and the backend assignment for every node. Two numbers
to watch: the split count, and how many nodes say `CPU` that you expected to say
`Vulkan0`. In the issue #2 case the split count went from 88 to 174, which was the whole
story, visible in one line.

Get in the habit of running this before you benchmark anything. We have thrown away
results because we did not.

## Layer 3: the Vulkan backend

`ggml/src/ggml-vulkan/ggml-vulkan.cpp` is a single 20,000-line file. It is intimidating
but it has clear regions:

| Region | What lives there |
|---|---|
| ~1-2500 | Types, pipeline struct definitions, the perf logger class |
| ~2500-7500 | Device init, feature detection, pipeline creation |
| ~7500-8000 | `ggml_vk_instance_init`, env var parsing (read this to find every lever) |
| ~8000-16000 | Per-op dispatch functions (`ggml_vk_mul_mat`, `ggml_vk_flash_attn`, ...) |
| ~16000-18500 | `ggml_vk_build_graph`, `ggml_backend_vk_graph_compute` (the main loop) |
| ~18500-20645 | Backend interface, `supports_op`, buffer types |

Shaders are separate: `ggml/src/ggml-vulkan/vulkan-shaders/`, 147 `.comp` GLSL files,
compiled at build time by a generator (`vulkan-shaders-gen`) that stamps out many
variants per file via preprocessor defines (dtype, subgroup size, tile shape, coopmat
level). One `.comp` file becomes dozens of pipelines.

**The single most important structural fact about this backend:** the same logical op has
several completely different implementations selected at dispatch time by shape, dtype,
and hardware feature. `MUL_MAT` alone routes to matrix-core (coopmat1/coopmat2), integer
dot product (MMQ), vector (MMV/MMVQ), or scalar paths. Flash attention has cooperative
and scalar variants. **Measuring "attention" without knowing which variant ran tells you
nothing**, and the variant can change when you change batch size, context depth, or quant
type. More than one of our early results was invalidated by this.

### Fusion

The backend fuses adjacent nodes (RMS_NORM+MUL, topk_moe patterns, GLU pairs) and this
interacts with everything. `GGML_VK_DISABLE_FUSION=1` is the first ablation to try when a
change has an effect you cannot explain.

### The env var surface

The Vulkan backend exposes about 55 environment variables. They are not documented
anywhere. To enumerate them for whatever version you have:

```bash
grep -oE 'getenv\("[A-Z0-9_]+"\)' ggml/src/ggml-vulkan/ggml-vulkan.cpp | sort -u
```

Roughly grouped:

- **Feature ablation:** `GGML_VK_DISABLE_COOPMAT`, `_COOPMAT2`, `_F16`, `_BFLOAT16`,
  `_INTEGER_DOT_PRODUCT`, `_MMVQ`, `_FUSION`, `_GRAPH_OPTIMIZE`, `_MULTI_ADD`
- **Forcing:** `GGML_VK_FORCE_MMVQ`, `GGML_VK_FORCE_MAX_ALLOCATION_SIZE`
- **Batching:** `GGML_VK_MAX_NODES_PER_SUBMIT`, `GGML_VK_MAX_MB_PER_SUBMIT`
- **Memory:** `GGML_VK_PREFER_HOST_MEMORY`, `GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM`,
  `GGML_VK_SUBALLOCATION_BLOCK_SIZE`
- **Instrumentation:** covered in its own section below

The disable flags are the best debugging tool in the codebase. **Bisecting a performance
change by turning features off is faster than reading the code**, and it works on a
release build.

## Layer 3b: the other backends, briefly

Worth knowing for cross-checking, because a result that appears on one backend and not
another is much more informative than either alone.

- `ggml-cuda/` is shared by CUDA and HIP (`ggml-hip/` is a thin shim). Far fewer env
  levers: `GGML_CUDA_DISABLE_FUSION`, `GGML_CUDA_DISABLE_GRAPHS`, `GGML_CUDA_DISABLE_MMVQ_Q8_1_CACHE`.
- `ggml-cpu/` is the reference. Slow, but it is the only implementation you should trust
  when validating numerics.

We have used the CUDA/HIP path repeatedly as a control: if a memory-layout effect shows
up on RADV and not on HIP on the *same silicon*, it is an API or driver effect. If it
shows up on both, it is the memory system. That single distinction has resolved several
questions that were otherwise unresolvable. It is also how we falsified an entire class
of explanation (see *read granularity asymmetry*).

---

# Part II: how to actually investigate

## Building

Nothing exotic, but two traps that cost us real time.

**Trap 1: stale ICD files.** If you build mesa from source to test driver changes, an old
`radeon_devenv_icd.*.json` left on the loader path can silently route you to a software
rasteriser. The symptom is not an error. The symptom is **a correctness A/B that passes
perfectly** and performance numbers that make no sense. Always confirm the device line in
llama.cpp's startup log says what you think it says.

**Trap 2: shader defines do not always reach the shader.** Changing a `-D` in CMake does
not always propagate through the shader generator to `glslc`. If a shader change appears
to have zero effect, dump the generated command line before concluding the change is a
no-op. We spent a day on a "dispatch no-op" that was a build plumbing problem.

## The measurement harness

We record every benchmark run as three artifacts keyed by one run id: a `.meta` (build
hash, branch, full env, exact argv, machine state), a `.raw` (verbatim unfiltered
stdout+stderr), and a `.json` (llama-bench machine-readable output). One row per run in a
TSV index. 393 runs recorded so far.

The rule that produced this: **no claim that cannot be reconstructed from the raw
artifact alone.** Summaries lie by omission. If a number cannot be traced to a `.raw`
file it does not go in a report.

This sounds like bureaucracy. It is the reason we caught the next item.

### Trap: GPU contention destroys results, it does not just add noise

Two benchmark processes sharing the GPU do not give you two slightly-slow results. On
2026-08-08 a co-resident `llama-bench` (20.5 GB GTT alongside our 19.1 GB) made a
Qwen3-32B `d16384` cell read **83.7 t/s against a true 190.0 t/s**, and produced a depth
curve that *got faster with depth*, which is physically impossible and was the only
reason we noticed.

Our runner now takes an exclusive `flock` on the GPU and waits up to two hours rather
than run concurrently. Do the equivalent. Also watch for:

- A model server (llama-swap, Ollama) holding memory in the background
- An image/video generation stack (ComfyUI and similar) pinning tens of GB
- **Page cache thrash.** Large model files being re-read because something else evicted
  them will corrupt decode numbers specifically, and it looks like a real regression.

### Trap: your benchmark ran a graph that never contained the code you changed

This one is subtle and we got it wrong before we got it right. Benchmarking with an empty
prompt (`-p 0`) builds a *decode* graph. If your change lives on the prefill path, or
behind a batch-size gate, it is simply not in the executed graph. The gate can report
"enabled" while the code never runs.

**Verify engagement from the executed graph, not from the gate.** In practice: compare
the graph pointers or node counts between the on and off configurations, or put a
one-shot log line inside the code path itself. A gate that says "on" is a statement about
configuration, not about execution.

### Trap: backgrounding a backgrounded job

If your tooling already runs a command in the background, wrapping it again in `{ ... } &`
makes it report completion immediately while it is still running. Everything downstream
then measures a machine with a live benchmark on it. Related: killing a bench script
mid-run can fire its cleanup trap and start whatever it was supposed to restore, which is
how we once OOM-killed the user systemd session.

### Trap: file size x tokens/sec is the wrong denominator for MoE

For a sparse MoE model, dividing model file size by decode time to get "achieved
bandwidth" is meaningless, because you only touch a few experts per token. We measured
the real per-token traffic on a 256-expert model: **the dense (non-expert) block is 78%
of per-token traffic.** Consequence: achieved bandwidth is roughly flat (154-161 GB/s)
across Q4 through Q6, and **a larger file can decode faster than a smaller one.** If your
roofline analysis of a MoE model uses file size, throw it out.

## Correctness gating

Performance work that changes numerics is not a win, it is a bug with a nice benchmark.
Our ladder, cheapest first:

1. `test-backend-ops -o <OP> -b Vulkan0` - per-op vs CPU reference. Fast. Necessary, and
   **not sufficient**: we have twice had test-backend-ops pass cleanly on a build that
   produced garbage text, because the failure was in dispatch selection or in tensor
   metadata rather than in the kernel.
2. Full-model perplexity against a `-ngl 0` (CPU) run of the same model and quant. This
   is what catches the class above.
3. KL divergence against the CPU reference when you need to distinguish "different" from
   "worse". PPL is too noisy to resolve small numerical changes.

Concrete result from step 3: across our whole Vulkan fix stack, exactly one change
altered outputs at all (a wave32 flash-attention path): KLD 0.0027, 97.6% identical
top-1 token, PPL indistinguishable from noise. Everything else was bit-exact. That is a
much stronger claim than "PPL looked fine", and it took a day to establish once.

## Instrumentation: an honest assessment

This is where llama.cpp is weakest, and it is worth being precise about *how* weak,
because the tooling is better than the docs suggest and worse than you would want.

### What exists

**Per-op GPU timing.** `GGML_VK_PERF_LOGGER=1` wraps nodes in Vulkan timestamp queries
and prints, per graph eval, one line per op kind: call count, mean microseconds, total
microseconds, and achieved GFLOPS/s where it can compute the flops.

```bash
GGML_VK_PERF_LOGGER=1 GGML_VK_PERF_LOGGER_FREQUENCY=20 \
  ./bin/llama-bench -m model.gguf -p 4096 2>&1 | tee perf.log
```

- `GGML_VK_PERF_LOGGER_FREQUENCY=N` prints every Nth eval. Essential at depth.
- `GGML_VK_PERF_SHAPES=1` disaggregates `MUL`, `MUL_MAT` and `MUL_MAT_ID` by tensor shape
  instead of collapsing them by op name. This is what turns "MUL_MAT is 60% of runtime"
  into an actionable statement.
- The accumulator is cleared on each print, so counts are per-window, not cumulative.

**Static shader statistics.** `GGML_VK_PIPELINE_STATS=<substring>` prints
`VK_KHR_pipeline_executable_properties` output (register counts, LDS usage, spills) for
every pipeline whose name matches the filter. Note this is *compile-time* information,
not runtime counters. It is the right tool for occupancy questions and the wrong tool for
anything dynamic.

**External-tool hooks.** `GGML_VK_DEBUG_MARKERS=1` enables `VK_EXT_debug_utils` labels, so
a capture in RGP, RenderDoc, or Nsight shows ggml op names on the timeline instead of
anonymous dispatches.

**Sync and memory tracing.** `GGML_VK_SYNC_LOGGER=1` prints every barrier the backend
inserts and every node as it is queued. `GGML_VK_MEMORY_LOGGER=1` for allocation churn.

**Isolated op benchmarking.** `test-backend-ops perf -o FLASH_ATTN_EXT -b Vulkan0`.

### What genuinely does not exist

Being direct, because this has come up as a criticism and the criticism is largely fair:

- **No trace export.** No Tracy, no Perfetto, no Chrome trace, no Firefox profiler
  format. `grep -i "tracy\|perfetto" ggml/ src/` returns nothing. There is no built-in
  wall-clock timeline of dispatches.
- **No hardware performance counters.** `VK_KHR_performance_query` is not used anywhere
  in the backend. You cannot get cache hit rate, memory stall cycles, or runtime
  occupancy out of llama.cpp. You get those from RGP or rocprofv3 or the vendor
  equivalent, treating llama.cpp as an opaque application.
- **Output is aggregate.** `print_timings` buckets by op name (plus shape, if you ask)
  and prints text to stderr. There is no per-dispatch record you can post-process.

### The barrier question, precisely

The specific criticism that the perf logger "wraps compute dispatches in extra barriers"
is **true in the default mode and false in the other mode**, and this distinction is not
documented anywhere, so it is very easy to miss.

In default per-op mode, the main graph loop does this after every enqueued node:

```
writeTimestamp(...)
ggml_vk_sync_buffers(ctx, compute_ctx)   // full pipelineBarrier
```

`ggml_vk_sync_buffers` is a real `vkCmdPipelineBarrier` over shader and transfer
read/write. So yes: turning on the perf logger serialises the graph. The per-op numbers
you get are *isolated* op times, and their sum systematically overstates real wall-clock
because all overlap has been removed.

`GGML_VK_PERF_LOGGER_CONCURRENT=1` exists precisely for this. In that mode the backend
writes timestamps **only at points where it was already going to synchronise** (the
`need_sync` path that exists regardless of instrumentation). It inserts no extra
barriers, so you measure the real overlapped execution. The cost is attribution: you get
timing per sync interval rather than per op, and when several ops genuinely overlapped
you cannot split their time apart.

That is a real engineering tradeoff, not an oversight, but it is undiscoverable. The two
modes answer different questions:

- **per-op (default):** "which kernel is slow" - correct for kernel optimisation
- **concurrent:** "where does wall-clock actually go" - correct for scheduling and
  occupancy work

Use per-op when tuning a shader. Use concurrent when the sum of your per-op times does
not match your end-to-end number, which is the moment you have an overlap problem.

### What we actually do, given that

The honest workflow, which is a workaround and not a solution:

1. `GGML_VK_PERF_LOGGER=1` + `GGML_VK_PERF_SHAPES=1` to find which op and shape dominates.
2. `GGML_VK_PERF_LOGGER_CONCURRENT=1` to check whether that op's isolated cost actually
   translates to wall-clock, or whether it was overlapping with something.
3. `GGML_VK_PIPELINE_STATS` for register and LDS pressure on that specific shader.
4. `GGML_VK_DEBUG_MARKERS=1` plus RGP when we need a real timeline or hardware counters.
5. When even that is not enough: **write a standalone microbenchmark**. We ended up
   building a separate cross-GPU Vulkan strided-read benchmark because no amount of
   in-app instrumentation could isolate the memory behaviour we were chasing. That tool
   answered the question in an afternoon after weeks of inference-level guessing.

Point 5 is the real lesson. A large fraction of our results came from **stepping outside
llama.cpp entirely** to isolate one variable, then coming back. The in-app tooling is
adequate for attribution and inadequate for mechanism. If you are asking "why", build the
microbenchmark.

The counterargument to the criticism, for fairness: a transformer graph is the same ~50
op shapes repeated 40-60 times per token, so a 3000-dispatch timeline is 60 redundant
copies of a 50-entry table. Aggregate-by-shape is arguably the *right* default view here,
and it is genuinely more readable than a flame graph of the same thing. That does not
excuse the absence of counters or trace export, but it does explain why the aggregate
view has survived.

---

# Part III: what we tested

Organised by area. The falsified section is longer than the shipped section, which is the
normal and correct ratio.

## Flash attention and KV cache

### SHIPPED: dequant-once + transpose for quantised KV flash attention

Quantised KV flash attention on RADV was re-dequantising K and V inside the attention
kernel on every access. Dequantising once into scratch and transposing for the access
pattern gave **+42.2% prefill** on our reference configuration.

Reproduced independently on unrelated hardware (128 GB box, MiniMax-230B, +40.4% at 32k
context, r=2), which is the only reason we consider it established rather than
local-hardware folklore.

Caveat worth stating loudly: **the win is a product of three factors**, not a constant.
It scales with how much of runtime is flash attention, how fragmented the KV access is,
and the GQA ratio. On a model where attention is not dominant the same patch is worth
close to nothing. On Coder-30B-A3B it is about 1.6x, not 2x. Quoting a single speedup
number for this class of change is misleading and we have stopped doing it.

### SHIPPED: contiguous-KV flash attention for prefill

The RADV-versus-ROCm prefill gap at depth turned out to be **100% attributable to flash
attention at depth**, not to matrix multiply, not to scheduling. The mechanism: the
coopmat1 `coopMatLoad` path collapses on head-interleaved KV strides.

Making KV contiguous for the prefill path (`GGML_VK_FA_KV_CONTIG`, now default-on,
prefill-only) closed the gap to ROCm parity.

Non-obvious follow-up that took us a month to get right: **the size of this win tracks KV
channel count**, roughly `2048 / (kv_heads * head_dim)`, and **not** whether the model is
dense or MoE. We initially believed the dense/MoE story, and it fit the first several data
points. It was wrong. When you have a two-variable confound, the cheap model will fit
first.

Thirteen separate shader-level hypotheses for the underlying kernel behaviour were tested
and falsified before we concluded the kernel is issue-bound rather than
bandwidth-or-latency-bound.

### MEASURED: KV row padding for power-of-two channel aliasing

**MEASURED mechanism:** the gfx1151 stride penalty on KV access is power-of-two channel
aliasing in the memory system. Not cache capacity, not coalescing granularity, though
both of those also exist as separate independent walls.

The fix is embarrassingly small: **a 16-byte pad** on the KV row stride recovers
essentially all of it, at a cost of 1.6% additional KV memory. Our first hypothesis was a
128-byte pad, which also works but costs 8x more memory for no additional benefit.

**Falsified on NVIDIA.** The same test on an RTX 3070 shows no such effect. This is an
AMD memory-system property, not a general GPU property, and anyone generalising it to
other vendors will be wrong.

Not shipped. The padding sits on an upstream branch and stays there. We took the
dequant-once scratch path to production instead, so the padding stands as a mechanism
finding rather than a landed fix. It remains the cheaper option if you are not already
paying for scratch.

### SHIPPED: DeepSeek-V4 gather-compact attention and head-compaction fusion

Decode-path gather-compact flash attention plus a head-compaction fusion produced a
**17-23x speedup on the flash attention op at 32k-64k context**, with a depth-flat
profile where the baseline degraded steeply. Community verification on a 128 GB machine
put end-to-end decode at +55% at depth 0.

Beats ROCm on every V4 configuration we tested.

### MEASURED: 2x prefill at 64k from KV cache layout alone

A head-major KV cache layout gives **2x prefill at 64k context on stock upstream master
with zero shader changes.** This is a `src/llama-kv-cache*.cpp` change, not a backend
change, which is a useful reminder that layer 1 has real performance leverage.

Incomplete: the V tensor path is blocked because a transpose flag is inferred from
strides, and state save/load is not implemented.

## Matrix multiply and MoE

### SHIPPED: MUL_MAT_ID grouped GEMM

A redesign of the MoE expert-routed matrix multiply, delivered as seven independently
gated pieces so each could be measured alone. Result: **pp512 +24.5%, 128k prefill
+42-46%.**

The important finding is not the speedup, it is the diagnosis. **The MoE "tax" (roughly
2x slower than the equivalent dense computation) is gather cost, row-list construction,
and fragmentation. It is not a DRAM bandwidth ceiling.** We believed the bandwidth story
for a while. An overnight ablation batch killed it.

Three specific sub-optimisations, all of which sounded obviously correct, all **DEAD**:
cheapening the unpack step, increasing occupancy, and double-buffering. None produced a
measurable win. The kernel is not limited by any of the things those address.

### MEASURED: coopmat1 fragment layout on gfx1151

We measured the actual `(lane, element) -> (row, column)` mapping for cooperative matrix
fragments on gfx1151: A is row-contiguous, B is strided, with 4x replication across
wave64.

This is not documented and it unlocks ROCm-style fused dequantisation without the scratch
buffer that the dequant-once approach requires. Probe code exists; the optimisation
itself is not built.

### FALSIFIED: coopmat2 on RADV

Thoroughly dead. It does not even engage without a workgroup-128 patch, and once it does:
2608 flash attention configurations fail, and it runs **6.8x slower than coopmat1**
because RADV emulates it through LDS rather than mapping it to hardware.

We wrote this up as driver feedback rather than pursuing it. If you are considering
coopmat2 on RADV, do not.

### FALSIFIED: split q8 scratch buffers

The bet was trading memory traffic for LDS. Result: **20% slower at 32k depth** than the
f16 scratch it replaced. Clean canary, engagement verified from the executed graph, so
this is a real negative and not a measurement artifact. We kept the prototype as evidence
and did not commit it.

## Cross-backend and driver findings

### MEASURED: ROCm does not pay the channel-camping tax

Validated on a perplexity-gated build so we know both sides were computing the same
thing: HIP genuinely does not suffer the strided-access penalty that RADV does, on
identical silicon.

The critical inference: **the tax is API-independent in origin but the APIs differ in how
they expose it**, which means the real question is total DRAM traffic, not layout. Four
separate source-level mechanisms that would have explained it were tested and falsified.
This one is still not fully closed.

### MEASURED: RADV drops non-temporal hints

RADV maps `ACCESS_NON_TEMPORAL` to SLC only (GL1 and GL2). It never sets DLC, which is
what would mark data as no-allocate in the MALL. Worse, `coopMatLoad` drops the access
operand entirely.

HIP's `__builtin_nontemporal_load` does set both slc and dlc. So a cache-bypass strategy
that works on HIP has no expressible equivalent through RADV today. This is a driver gap,
and it is one of the reasons the 32 MB MALL on this part is underused.

### MEASURED: HIP flash attention decode collapse with quantised KV

Why q8_0 KV decode is bad on ROCm/gfx1151: the fused vector kernel **is** active, so the
usual explanation (falling off the fast path) is wrong. The actual cause is that it does
not batch GQA, so it performs 8x redundant dequantisation.

A q4_0 control run confirms the kernel is element-bound and ALU-bound, not
bandwidth-bound. Note that a bandwidth model "explains" the observed numbers reasonably
well and is nonetheless wrong. This happens more often than is comfortable.

### MEASURED: recent upstream master produces garbage on ROCm/gfx1151

Bisected to a specific commit changing `prop.integrated` handling, plus a separate 6x
slowdown from HIP math flags.

**`test-backend-ops` passes on both the good and bad builds.** This is the clearest
example we have of why per-op testing is insufficient. Validate HIP builds with
full-model perplexity against `-ngl 0`.

## Numerics and quantisation

### MEASURED: q8_0 KV converts to speed, q4_0 does not

On this hardware, going from f16 to q8_0 KV cache produces a real speedup. Going from
q8_0 to q4_0 does not. The crossover is somewhere between 8 and 4 bits, which means the
usual assumption that smaller KV is monotonically faster is false here.

### MEASURED: TurboQuant KV, and where it breaks

We built a numpy-only reference implementation of TurboQuant KV quantisation, validated
19/19 against the paper.

Findings: a per-coordinate residual **sign** beats the paper's QJL construction at 1 bit
per dimension. And tq3_0 is effectively lossless for V while it **collapses** for K, so
the usable configuration is asymmetric: `-ctk tq4_0 -ctv tq3_0`.

Important correction to our own earlier conclusion: we initially attributed the K
collapse to an indexing bug in the cooperative flash attention hd128 path. It was not a
bug. It was chaotic amplification of a genuine format weakness. **The collapse is a flaw
in our format, not a law about 3-bit K.**

### MEASURED: Q8_0 weights are not measurably more accurate than Q6_K

Tested directly on a model where we expected the opposite. Q8_0 was +22.4% prefill and
-16.4% decode versus Q6_K, with no measurable accuracy advantage. Meanwhile switching the
KV cache to f16 bought the fidelity we were chasing for 0.94 GB, against a 36 GB model
download.

Worth internalising: **spend precision on the KV cache before spending it on weights.**

## Bugs found and fixed

### SHIPPED: iq4_nl flash attention gate mismatch

84 flash attention failures that presented as `inf` values in attention sinks. The actual
cause was a `supports_op` / dispatch mismatch: the predicate claimed support for a
configuration with no matching pipeline.

Hard-gate fix plus tests pushed. Full suite: 15538/15538.

### MEASURED: f16 accumulator overflow in scalar flash attention MMQ

An upstream bug, not hardware-specific: the scalar flash attention MMQ path accumulates
in int32 and then overflows the f16 `ACC_TYPE` with q8_0 K at default precision.

One-line fix, verified. Held rather than submitted because the practical impact is close
to zero and the fix adds a branch on a hot path. Recording it here so nobody spends time
rediscovering it.

### SHIPPED: quantised reshape stride bug causing silent CPU fallback

The loader's reshape path computes `nb[1]` without accounting for block size, so a
quantised tensor looks non-contiguous to the backend. Vulkan then declines it via
`supports_op` and it silently runs on CPU. In the reported case: 43 layers demoted,
splits going from 88 to 174, presenting purely as a decode performance regression with no
error output.

One-line fix. This is the canonical example of why `GGML_SCHED_DEBUG=2` should be the
first thing you run on any unexplained slowdown.

## Architecture-level observations

### The NPU is worth approximately nothing

For LLM inference on this part, at this time, in this software stack. Do not plan around
it.

### The 32 MB MALL is the underused resource

This is the clearest remaining opportunity on Strix Halo and the driver does not currently
give you the controls to exploit it (see the non-temporal finding above).

### Speculative decoding is dense-only in practice here

On a MoE-heavy workload the draft model economics do not work out on this hardware. On
dense models it does: we measured 34.30 t/s with speculative decoding against 19.57 t/s
autoregressive, **+75%**, with no expert approximation and no accuracy compromise.

### Watch out for hybrid attention when benchmarking depth

Some recent models are hybrid: one we tested is 10 full-attention layers out of 40, with
30 SSM layers. Its depth curve is nearly flat (2.2x degradation versus 7x for a
conventional model). **That flatness is architecture, not backend quality.** It is a bad
baseline for attention-at-depth work and we nearly drew a wrong conclusion from it.

---

# Part IV: open questions

Things we know are real and cannot yet explain. Contributions welcome.

1. **The DRAM traffic question.** ROCm avoids the strided-access penalty that RADV pays on
   identical silicon, and four source-level explanations have been falsified. The
   remaining hypothesis is that total DRAM traffic differs, which we have not been able
   to measure directly because neither stack exposes the counter.
2. **Depth decay profile for DSv4 gather-compact.** We have the depth-0 and
   depth-32k/64k endpoints. The shape between them is unmeasured.
3. **A 10-21% graph overhead** observed in the graph-reuse path. The effect reproduces.
   The cause is unknown, and we have deliberately not submitted a claim about it.
4. **The coopmat1 fragment layout is measured but unexploited.** The fused-dequant
   optimisation it enables is designed and not built.

---

# Appendix: quick reference

Diagnose an unexplained slowdown, in order:

```bash
# 1. Is it even running on the GPU you think?
GGML_SCHED_DEBUG=2 ./bin/llama-cli -m model.gguf -p test -n 1 2>&1 | head -60

# 2. Which op dominates, and at what shape?
GGML_VK_PERF_LOGGER=1 GGML_VK_PERF_SHAPES=1 GGML_VK_PERF_LOGGER_FREQUENCY=20 \
  ./bin/llama-bench -m model.gguf -p 4096 2>&1 | tee perf.log

# 3. Do the per-op times explain wall-clock, or is there an overlap story?
GGML_VK_PERF_LOGGER=1 GGML_VK_PERF_LOGGER_CONCURRENT=1 \
  ./bin/llama-bench -m model.gguf -p 4096

# 4. Is a specific feature responsible? Bisect by ablation.
GGML_VK_DISABLE_FUSION=1 ./bin/llama-bench -m model.gguf -p 4096
GGML_VK_DISABLE_COOPMAT=1 ./bin/llama-bench -m model.gguf -p 4096
GGML_VK_DISABLE_MMVQ=1 ./bin/llama-bench -m model.gguf -p 4096

# 5. Register and LDS pressure on the hot shader
GGML_VK_PIPELINE_STATS=flash_attn ./bin/llama-bench -m model.gguf -p 4096

# 6. Real timeline and hardware counters: label, then capture in RGP
GGML_VK_DEBUG_MARKERS=1 ./bin/llama-bench -m model.gguf -p 4096

# 7. Isolate the op, no model in the way
./bin/test-backend-ops perf -o FLASH_ATTN_EXT -b Vulkan0

# 8. Correctness, in increasing order of trustworthiness
./bin/test-backend-ops -o FLASH_ATTN_EXT -b Vulkan0
./bin/llama-perplexity -m model.gguf -f wiki.test.raw          # vs the -ngl 0 run
```

Enumerate every lever your build actually has:

```bash
grep -oE 'getenv\("[A-Z0-9_]+"\)' ggml/src/ggml-vulkan/ggml-vulkan.cpp | sort -u
```

## The five rules that produced most of the above

1. **Verify engagement from the executed graph, not from the gate.** A configuration flag
   saying "on" is not evidence that code ran.
2. **Serialise your benchmarks.** Contention does not add noise, it fabricates results,
   including physically impossible ones.
3. **Keep raw artifacts for every run.** If you cannot reconstruct a number from raw
   output, you do not know it.
4. **test-backend-ops passing is not correctness.** Gate on full-model perplexity against
   a CPU reference, and on KLD when you need to distinguish different from worse.
5. **When you cannot explain a mechanism, leave llama.cpp.** Build the microbenchmark.
   Several of these findings were unreachable from inside the application and took an
   afternoon once isolated.
