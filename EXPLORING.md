# llama.cpp: an explorer's guide, and what we found

A map of the llama.cpp / ggml codebase from the point of view of someone who wants to
make it faster, plus a record of what we actually measured on AMD Strix Halo (gfx1151)
over the last several months: what worked, what shipped where, and the larger pile of
things that turned out to be wrong.

The point of the second half is not the wins. It is the falsifications. Most of the
plausible-sounding optimisations in this space are wrong, and the only cheap way to find
that out is to read someone else's list before you spend a week on one.

Status: 2026-08-23. Written against llama.cpp master around `3af988f`.
Supersedes the 2026-08-10 revision, which was written against `3be50cc`.

Every number below came from a recorded run. Nothing here is estimated, extrapolated,
or reasoned-from-first-principles unless it explicitly says so. 1197 runs are indexed
at the time of writing, against 393 in the previous revision.

There is a companion document, [docs/METHOD.md](docs/METHOD.md), on how this was actually
run: one person, an agent, a lab notebook, and the specific ways that arrangement fails.
If you want the findings, stay here. If you want the process, read that.

**This is long. Where to start, by what you came for:**

- **"My benchmark says something weird."** Part II, *The traps that fabricate results*. It is
  the longest section here on purpose, and every entry produced a number that was published
  or nearly published and was wrong.
- **"I want to make llama.cpp faster on this hardware."** Part I for the layer map and what
  the silicon actually offers, then the falsified entries in Part III before the shipped ones.
  The negatives will save you more time than the positives.
- **"Which knob do I turn today?"** The appendix, plus two settings: `-ub 256` for dense
  models, `-ub 2048` for MoE, and spend precision on the KV cache before the weights.
- **"Is this real?"** Part 0 for what the tags mean, Part IV for the twelve things we
  published and had to take back.
- **"I want to help."** Part V, *Still to explore*, and the ask at the end of it: four
  finished changes are blocked on a benchmark from a card we do not own.
- **"Can I run your tools?"** The availability table at the head of *Instrumentation*, and
  [tools/README.md](tools/README.md).

---

## Part 0: how to read this

Findings are tagged:

- **UPSTREAM** - merged into ggml-org/llama.cpp and available to everyone
- **FORK** - shipped in our fork and toolbox releases, reproducible from a branch, **not
  upstream**
- **MEASURED** - reproduced on our hardware with artifacts, not shipped anywhere
- **FALSIFIED** - we tried it, it did not work, here is why
- **RETRACTED** - we published it, it was wrong, here is the correction
- **OPEN** - known effect, cause not established

If a claim has no tag it is background, not a result.

**The UPSTREAM / FORK distinction is load-bearing and easy to get wrong, so it is worth
being blunt about.** At the time of writing, **exactly one** finding in this document is
merged into llama.cpp itself: the dequant-once plus transpose change for quantised KV
flash attention, merged 2026-08-19 as PR #25494. Everything else tagged FORK ships in
`Nathanw1014/llama.cpp` on the `strix-halo-vulkan` branch and in this repository's
releases. It is real, it is running on other people's machines, and it is reproducible
from a named branch, but **if you build stock llama.cpp you do not have it.**

One clarification, so the "exactly one" above is not misread later: that count is about
**llama.cpp**. Work from this record has also landed in two other places, which are
different upstreams with different queues. A conformance-test fix is merged into
KhronosGroup/VK-GL-CTS, and a Mesa/RADV merge request for 64-bit buffer indexing is open.
See *Where the ceiling is the API, not the code* in Part III for why some problems route
there instead.

Some of the FORK items are staged for upstream and some deliberately are not. A few
examples of the second kind, because "not upstreamed" is not the same as "not good
enough": the iq4_nl routing hardening cannot hit its failure mode upstream at all, since
the type later became natively supported there; three of the dense-prefill changes are
calibrated on one GPU at one depth and would need a second vendor's data before they could
default on anywhere;
and one is a chat-template fix the author chose to keep local. Where an item is queued for
upstream, the entry says so.

Two process facts that shape the pace, and that are not obstacles so much as the
environment: llama.cpp asks new contributors to keep one pull request in flight at a time,
and it prohibits AI-written pull request text, issue text, and reviewer replies outright
(AI-written *code* is allowed, with the contributor fully responsible and required to
disclose). So the queue moves at one item at a time and every word of prose attached to it
is written by hand. See [docs/METHOD.md](docs/METHOD.md) for how that is actually run.

The hardware unless stated: Framework Desktop, Ryzen AI Max+ 395 (Strix Halo),
64 GB unified LPDDR5X, Radeon 8060S / gfx1151, RADV on mesa-main, `iommu=off`.
A second box (128 GB Blackwell DGX Spark) and an RTX 3070 were used for
cross-platform controls.

**A scope rule we apply to ourselves and ask you to apply when quoting this:** every
performance claim here names the part it was measured on. We have one AMD APU and one
NVIDIA card. "AMD does X" is almost never something we are entitled to say, and where
this document says it, it is shorthand for "gfx1151 does X and we have no counterexample".

**Not all of this work is ours, and the DeepSeek-V4 sections especially are not.** Gaetan
Puleo contributed the lightning-indexer kernels and the indexed sparse flash-attention path.
Jaap Buurman ([@Mushoz](https://github.com/Mushoz)) contributed the sparse-prefill
acceleration, a cooperative flash-attention kernel for that path, the indexer prefill
parallelisation, and the diagnosis of the small-batch decode gap that the gather-compact
work then fixed. Per-commit attribution and the preserved original branches are in the
[repository credits](README.md#credits), which is the authoritative record; this document
describes results and does not re-assign authorship.

**What "independently reproduced" means here, where it appears.** Three results have been
confirmed on hardware we do not own: the dequant-once change on a 128 GB machine with an
unrelated model (+40.4% at 32k), the V4 gather-compact decode work on the same class of
machine (+55% at depth 0), and, least comfortably for us, the shared-memory pad regression,
which a downstream user found by bisecting a collapse on a stock driver. That third one is
the most valuable of the three, and it is the reason this document has a Part IV.

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

Two of the larger wins recorded below live in `src/`, not in a shader, which is worth
knowing before you open a `.comp` file: the head-major KV cache layout (2x prefill at
64k on stock upstream, no shader changes) and the KV row padding (up to +65% at 32k).
Layer 1 has real performance leverage and almost nobody looks there.

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

Roughly **half of every ggml graph is never dispatched** (views, no-ops, nodes folded by
fusion). Measured on Qwen3-32B at ub2048: 2245 ggml nodes become 1153 HIP dispatches and
1091 Vulkan ones. Do not reason about cost from node counts.

## Layer 2: the scheduler (`ggml/src/ggml-backend.cpp`)

This is the highest-leverage file in the repo for debugging, and the least read.

The scheduler walks the graph and assigns each node to a backend, then cuts the graph
into **splits** wherever consecutive nodes land on different backends. Every split
boundary is a synchronisation point and often a host round-trip.

Assignment is driven by each backend's `supports_op` callback. This is a pure predicate:
given a node, can you run it. The contract is that `supports_op` returning true is a
promise, and if the dispatch path later disagrees you do not get a fallback, you get
undefined behaviour or a wrong answer.

We have been bitten by both directions of that mismatch, three times now:

- `supports_op` said yes and the dispatch path had no matching pipeline. Produced 84
  `inf` failures that looked like a numerical bug in attention sinks and were not.
  (See *iq4_nl gate* below.)
- `supports_op` said no because tensor metadata was subtly wrong, silently demoting 43
  layers to CPU with no error message at all. (See *issue #2* below.)
- A `supports_op` omission while adding new quant types presented as **a hang**:
  `gpu_busy` at zero, CPU threads at 100%. It was the whole model falling back to a
  CPU path nobody was watching.

The second failure mode is worth dwelling on. **A backend that quietly declines an op
looks exactly like a slow backend.** There is no warning. Your only signal is:

```bash
GGML_SCHED_DEBUG=2 ./llama-bench -v -m model.gguf -p 512 -n 1 2>&1 | head -100
```

which prints the split structure and the backend assignment for every node. Two numbers
to watch: the split count, and how many nodes say `CPU` that you expected to say
`Vulkan0`. In the issue #2 case the split count went from 88 to 174, which was the whole
story, visible in one line.

Note `-v`: `GGML_SCHED_DEBUG` prints through `GGML_LOG_DEBUG`, which needs the verbose
flag to pass the log filter. And use `llama-bench`, not `llama-cli`, for this - see the
`llama-cli` trap below.

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

Concretely, three separate results in Part III are *entirely* explained by which variant
ran: flash attention at N=1 versus N>=2, matmul at n<=8 versus n>=9, and q6_K on HIP
above versus below `ne11=256`. In each case the "regression" was a routing boundary.

### Pipeline creation is where the levers hide

Two of our dense-prefill findings turned out to be facts about *which pipelines get
created*, not about any kernel:

- `pipeline_dequant_mul_mat_mat_q8_1` (the integer-dot MMQ matmuls) is created only
  inside the fp16 **scalar** branch, so a coopmat1 device never gets it. That looks like
  an oversight. It is load-bearing: creating those pipelines would displace coopmat at
  dispatch time and cost ~40% of dense prefill.
- `pipeline_dequant_mul_mat_mat_f16` (f16 B operand for quantised A) is populated only in
  the **coopmat2** branch. There is no recorded rationale. Populating it for coopmat1 too
  is ~40 lines and worth +5 to +7% of dense prefill on wide models.

So when you read a gate, ask whether it encodes a constraint or an accident. Both exist,
they look identical, and the only way to tell is to measure.

### Fusion

The backend fuses adjacent nodes (RMS_NORM+MUL, RMS_NORM_MUL_ROPE, topk_moe patterns,
MUL_MAT_ADD, MUL_MAT_ID_MUL, MULTI_ADD, GLU pairs) and this interacts with everything.
`GGML_VK_DISABLE_FUSION=1` is the first ablation to try when a change has an effect you
cannot explain.

Fusion is also where a lot of intuition goes to die. See *the fusion nulls* in Part III:
we built two correct, bit-exact, verified-engaged fusions that removed real GPU work and
changed wall-clock by zero.

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

**Read the parsing, not just the name.** `ggml_vk_concat_is_transposed` only tests
`env[0] == '0'`, so `GGML_VK_CONCAT_TRANSPOSE=1` is a no-op and the opt-out is `=0`. We
burned a benchmark arm "measuring" a flag against itself before noticing.

## Layer 3b: the other backends, briefly

Worth knowing for cross-checking, because a result that appears on one backend and not
another is much more informative than either alone.

- `ggml-cuda/` is shared by CUDA and HIP (`ggml-hip/` is a thin shim). Far fewer env
  levers: `GGML_CUDA_DISABLE_FUSION`, `GGML_CUDA_DISABLE_GRAPHS`, `GGML_CUDA_DISABLE_MMVQ_Q8_1_CACHE`.
- `ggml-cpu/` is the reference. Slow, but it is the only implementation you should trust
  when validating numerics, and it is the only place logits are batch-shape-invariant
  (which matters enormously for speculative decoding, see Part III).

We have used the CUDA/HIP path repeatedly as a control: if a memory-layout effect shows
up on RADV and not on HIP on the *same silicon*, it is an API or driver effect. If it
shows up on both, it is the memory system. That single distinction has resolved several
questions that were otherwise unresolvable. It is also how we falsified an entire class
of explanation (see *read granularity asymmetry*) and how we localised the entire dense
prefill gap to two matmuls.

**One HIP gate to know about, because it explains a lot of ROCm behaviour:**
`ggml_cuda_should_use_mmq` drops q6_K out of the integer-dot MMQ path above `ne11=256`
into dequantise-then-hipBLAS. That single boundary is why ROCm's dense prefill curve
jumps +15.6% exactly at ub256 to ub512, and it is most of the Vulkan-versus-ROCm dense
gap. A routing rule, not a kernel.

## What gfx1151 actually offers, and which of it llama.cpp reaches

Worth establishing before Part III, because a surprising number of optimisation ideas die on
a hardware fact rather than on a code problem, and because the two backends reach different
subsets of the same silicon.

The device line llama.cpp prints at startup is the cheapest summary, and reading it properly
is most of what you need:

```
0 = AMD Radeon 8060S Graphics (RADV STRIX_HALO) (radv) | uma: 1 | fp16: dot2 | bf16: 0
  | fp4: 0 | warp size: 64 | shared memory: 65536 | int dot: 1 | matrix cores: KHR_coopmat
```

`uma: 1` means there is no discrete memory and no PCIe transfer to optimise away.
`bf16: 0` and `fp4: 0` mean those are emulated, not native. `warp size: 64` is the default,
and the matrix units are wave32-native, which is a whole finding on its own. `int dot: 1`
should always be 1; if it says 0, your build found the wrong shader compiler.

### Compute primitives, measured

| primitive | rate | who uses it |
|---|---|---|
| fp16 cooperative matrix (WMMA, via `KHR_coopmat`) | **53.6 TOPS** microbenchmark, ~37 TFLOPS achievable in-model | Vulkan `mul_mm`, HIP MMQ |
| int8 cooperative matrix | ~1x fp16 rate | **HIP only.** RADV exposes the primitive; llama.cpp has no Vulkan int8 coopmat shader |
| int4 cooperative matrix (`V_WMMA_I32_16X16X16_IU4`) | **108.6 TOPS, 2.03x fp16** | **nobody.** No extension exposes it; we prototyped one |
| bf16 | emulated | Vulkan 8.9 TFLOP/s against HIP's 32.9 |
| fp8, structured sparsity | absent until the next architecture | nobody |
| the NPU | not worth pursuing for this workload | nobody |

**int4 is the only primitive on this part above fp16 rate.** int8 matches fp16 and does not
beat it, which is why an int8 cooperative matmul shader is worth about 4% rather than the
~18% a naive reading of ROCm's MMQ advantage suggests. That one line kills a popular idea.

### Memory, measured

| level | rate |
|---|---|
| DRAM, coalesced sequential | **242 GB/s** ceiling; decode achieves 220 GB/s marginal, 91% |
| DRAM, row-strided onto 2 of 16 channels | **14.7 GB/s** |
| DRAM, row-strided onto 1 of 16 channels | **7.3 GB/s** |
| 32 MB last-level cache, resident | **678-720 GB/s**, about 3x DRAM |
| shared memory per workgroup | 65536 bytes, 32 banks |

Address bits [11:8] select among 16 channels at a 256-byte granule. That single fact
generates the aliasing that runs through half of Part III, and the 33x spread between the
first and third rows is why layout beats almost every kernel optimisation on this part.

### Matmul paths, and the ladder they form

The same logical operation routes to several implementations. What we measured on the
dominant dense shape:

| path | rate | backend |
|---|---|---|
| dequantise then hipBLAS f16 | **~29-32 TFLOP/s** | HIP, above `ne11=256` for q6_K |
| int8 MMQ on the matrix cores | ~21.6 | HIP |
| Vulkan coopmat1 `mul_mm`, best case (q4_0/q4_K) | 21.4 | Vulkan |
| Vulkan coopmat1 `mul_mm`, q6_K | 17.1 | Vulkan |
| Vulkan f16 `mul_mm` | **16.6** | Vulkan |
| Vulkan scalar (coopmat disabled) | ~40% slower than coopmat | fallback only |

Two consequences that are not obvious. **Vulkan's f16 path is its slowest**, so copying
ROCm's dequantise-then-GEMM strategy cannot work. And decode does not use any of these: at
batch 1 it dispatches through `mul_mat_vec` / `mul_mat_vec_q` instead, which is why every
prefill optimisation in this document measured decode-neutral, and why we measure that
rather than assuming it.

Flash attention has its own split: cooperative for batch >= 2 with a fixed 16-row tile, and
scalar at batch 1 which sizes the tile to the batch. Which one you get, and whether GQA head
packing can fill the tile, explains several results that look like regressions.

### What Vulkan reaches that HIP does not, and vice versa

Not a scoreboard, a map of where to look:

- **Vulkan wins flash attention by 1.5-1.9x** on matched dispatch counts, and fuses rope into
  the QK-norm so it emits zero rope dispatches where HIP emits 128.
- **HIP wins dense matmul by up to 1.95x**, entirely through having a fast f16 GEMM to fall
  back on.
- **HIP can express cache bypass** through its non-temporal load builtin. RADV drops half the
  hint and `coopMatLoad` drops it entirely, so the 3x cache-residency number above is not
  reachable from Vulkan today.
- **HIP has no per-op timing knob at all**, which is why we wrote one.
- **Decode is a tie**, at the kernel level and end to end, on every model measured.

This section is the reference table. What follows from it, including why the cache is the
clearest remaining opportunity and why the NPU is not, is in *Architecture-level
observations* at the end of Part III.

---

# Part II: how to actually investigate

## Building

Nothing exotic, but the traps here have cost us more real time than any other category,
because a broken build does not error, it produces *plausible numbers*.

**Trap 1: stale ICD files.** If you build mesa from source to test driver changes, an old
`radeon_devenv_icd.*.json` left on the loader path can silently route you to a software
rasteriser. The symptom is not an error. The symptom is **a correctness A/B that passes
perfectly** and performance numbers that make no sense. Always confirm the device line in
llama.cpp's startup log says what you think it says.

**Trap 2: cmake finds the wrong glslc, and the wrong Vulkan headers.** This one has
recurred three times, and each recurrence taught us that the previous fix was incomplete.

A plain `cmake -DGGML_VULKAN=ON` picked up Ubuntu's shaderc 2023.8 at `/bin/glslc`
instead of our current one, *and* headers from `~/.local/include` (Vulkan 1.4.356)
instead of `/usr/include` (1.3.275). The result: the device init line reports
**`int dot: 0`** instead of `int dot: 1`, on the same device, same ICD, byte-identical
ggml source. That silently disables the integer-dot matmul paths and faked a large deep
context "regression" (35B f16 pp@64k reading 342 against a real ~460, tg 27 against 41).

It was caught only because two device lines were diffed before benchmarking.

```bash
cmake -B build -DGGML_VULKAN=ON \
  -DVulkan_GLSLC_EXECUTABLE=/path/to/current/glslc \
  -DVulkan_INCLUDE_DIR=/usr/include
# then, always:
./build/bin/llama-bench -m any.gguf -p 8 -n 0 2>&1 | grep -E 'Vulkan0|int dot|matrix cores'
```

**Check the device init line every single time.** It is one line and it encodes the four
things most likely to be silently wrong: which device, which driver version, whether
integer dot is on, whether coopmat is on.

**Trap 3: shader defines do not always reach the shader.** Changing a `-D` in CMake does
not always propagate through the shader generator to `glslc`. If a shader change appears
to have zero effect, dump the generated command line before concluding the change is a
no-op. We spent a day on a "dispatch no-op" that was a build plumbing problem.

**Trap 4: build the whole thing, not one target.** A `--target llama-bench` build hid an
additive merge duplication that only broke `llama-server`. If you are about to push, build
all targets first.

**Trap 5: copied build directories.** A build dir copied from another one keeps make rules
that `cd` back into the original. `cmake --build build-latest` then compiles into
`build-vk` and leaves `build-latest`'s binaries stale. You benchmark the old code and
attribute the result to the new.

## If you want to reproduce a number from this document

Scattered through Part II as individual traps, but worth stating once as a checklist,
because getting any one of these wrong silently changes the answer rather than erroring:

- **Driver.** A locally built RADV, not the distribution's. Several results here differ by
  double digits between driver versions, and one shipped change is a 2.4-3.1x regression on
  a stock driver (see the LDS pad). Point the loader at the driver you mean and confirm with
  `vulkaninfo --summary`, because a stale ICD file silently routes you elsewhere.
- **Kernel.** `amd_iommu=off`. Worth about +4% here, and not the default.
- **Build.** Pinned shader compiler and the matching Vulkan headers, then check the device
  line says `int dot: 1`. See *Building*.
- **Exclusivity.** No model server holding weights, no other accelerator workload, and no
  compile running. A throttled build still costs about 7%.
- **Warm-up.** Discard the first run after any rebuild, and never report a shallow-context
  delta from a session's first cell.
- **Repetition.** At least three independent launches per arm, counterbalanced, for anything
  involving a large model at large batch. `-r N` inside one process is not an error bar.

If a number here does not reproduce for you, the first suspects are this list, in this
order. If it still does not reproduce after all six, we would like to know.

## The measurement harness

We record every benchmark run as three artifacts keyed by one run id: a `.meta` (build
hash, branch, full env, exact argv, machine state, whether any other process held GPU
memory while the run went out, GPU lock wait), a `.raw` (verbatim unfiltered
stdout+stderr, including the device init lines), and a `.json` (llama-bench
machine-readable output). One row per run in a TSV index. 1197 runs recorded so far.

The rule that produced this: **no claim that cannot be reconstructed from the raw
artifact alone.** Summaries lie by omission. If a number cannot be traced to a `.raw`
file it does not go in a report.

This sounds like bureaucracy. It is the reason we caught almost everything in the next
section.

## The traps that fabricate results

This is the longest section in the document and it is deliberately longer than the
findings sections. Every one of these produced a number that looked real, was published
or nearly published, and was wrong. None of them announce themselves.

### Trap: GPU contention destroys results, it does not just add noise

Two benchmark processes sharing the GPU do not give you two slightly-slow results. On
2026-08-08 a co-resident `llama-bench` (20.5 GB GTT alongside our 19.1 GB) made a
Qwen3-32B `d16384` cell read **83.7 t/s against a true 190.0 t/s**, and produced a depth
curve that *got faster with depth*, which is physically impossible and was the only
reason we noticed.

Our runner now takes an exclusive `flock` on the GPU and waits up to two hours rather
than run concurrently. Do the equivalent. Also watch for:

- A model server holding weights in the background. If yours keeps a model resident
  after the request that loaded it, then once anything touches the endpoint the server
  stays resident indefinitely and taxes every later run by ~3%.
- Any other accelerator workload on the box pinning tens of GB
- **Page cache thrash.** Large model files being re-read because something else evicted
  them will corrupt decode numbers specifically, and it looks like a real regression.

### Trap: a compile is a benchmark confound, and `nice` does not fix it

A `cmake --build` at `nice -n 19 -j 6` (deliberately throttled) landed inside another
benchmark and cost it ~7%: one cell read 315 t/s against 339 and 340 for its two siblings.

The GPU mutex only serialises benchmarks against benchmarks. **A compile never takes the
lock, so nothing detects it.** And `nice` is the wrong lesson: it lowers CPU scheduling
priority, but what a benchmark loses is memory bandwidth and cache stolen from the feeder
thread. On a UMA box the host feed is the bottleneck, so six `cc1plus` processes at 100%
starve it regardless of priority.

The damage is silent in the worst way: a plausible number, no warning, and a
normal-looking single-GPU-process record in the metadata.

Related, and worse for campaigns: **interleaving two sessions' benchmark arms through the
mutex is still harmful when the models are large.** Two campaigns holding 29 + 17 + 17.9 GB
of weights on a 62 GB box evict each other's page cache on every swap. The mutex protects
the correctness of a single measurement, not the stability of a matrix.

### Trap: the first run after a rebuild is invalid

Mesa's on-disk shader cache keys on the binary, so a freshly built binary pays pipeline
compilation *inside* the measured run. Measured: 35B ub2048 pp2048 read 1043 and 1191 on
the first two uses of a new build against 1292-1295 steady state, up to **-19%**. It looks
exactly like a regression.

**And counterbalancing is not enough**, which we learned the expensive way. A dense A/B
ordered 1,0,0,1 put the session's first cell in the `on` arm: its d0 read 223.4 cold
against 258.2 warm, a 15.6% within-arm spread, while the `off` arm sat at 260.9/271.4.
That manufactured a clean-looking "-9.5% shallow-context regression" that does not exist,
and it was reported as probably-real before the repeat landed.

Depth cells were unaffected, because a long re-prefill amortises pipeline compilation. So
**the cold artifact concentrates at d0**, exactly where deltas are smallest and easiest to
over-read.

Rule: run an explicit throwaway warmup cell before any A/B. Never report a d0 delta from a
run that was first in its session.

### Trap: `-r N` inside one process is not an error bar

`llama-bench -r N` reports the spread of N repetitions **inside a single process**. It
cannot see between-launch variance.

Four independent launches of an *identical* arm (35B MoE, fixed build, `-b 2048 -ub 2048
-p 2048 -r 3`) gave, at d0: 1045.5 / 1316.1 / 1324.2 / 1327.1 t/s. That is a **26.9%
spread against a reported within-run stddev of 0.3%.** At depth: d16384 19.2%, d32768
9.2%, d65536 5.1%.

Partly page-cache warm-up (a 22.4 GB model reloaded per arm on ~59 GiB usable means cache
state differs per launch), but not purely monotonic, so caching is a component and not the
whole story. Scope matters: the same model at `-ub 512` was rock stable, so this is a
model-by-protocol interaction near a memory threshold, not a general property of the box.

Rule: for any headline number involving a >20 GB model at large ubatch, run **at least
three independent launches per arm** and quote the across-launch spread. A single launch
produced a fake 2% regression that four launches refuted.

Cheap validity check that costs no extra runs: within one protocol, two arms that differ
only in a KV type should differ smoothly and monotonically with depth. Alternating-sign
swings (we saw +11.5% / -4.1% / +16.3% / -7.5%) mean the arms are not repeatable and
nothing from that block is publishable.

### Trap: alternating arms is not counterbalancing

A-B-A-B still confounds arm with position-in-round if the order inside each round never
changes. Any systematic within-round effect lands on the same arm every time and reads as
a regression in it.

A cross-model regression sweep showed one arm bimodal (48.40 / 48.65 / 50.67) against a
rock-tight other arm (52.30-52.83, 1.01% spread). It looked like a real -8% slow mode in
the new binary, and the interleaving plus identical per-run machine state seemed to rule
out the environment. It was not real: every round ran base then fix, so the new binary
always occupied the second slot. A counterbalanced block with the order reversed came back
8/8 clean, and pooled over 13 launches per arm the delta was **-0.26%**.

Use A-B-B-A, or randomise. And when one arm's spread is much larger than the other's,
suspect position or a transient before suspecting the code: a genuinely bimodal binary
keeps being bimodal, so check whether the outliers cluster in time.

Corollary found in the same investigation: **the settle time after a model swap is
minutes, not seconds.** All three outliers fell inside a ~7 minute window after a 26 GB to
24 GB swap. Prefer benching one model to completion before loading the next.

### Trap: one llama-server launch, several requests

During a speculative-decoding A/B, a driver that sent three prompts to one `llama-server`
launch produced a cell reading **47.6 t/s at 0.844 acceptance**. The generated text was
`"""` repeated for 400 tokens. Re-run as a single request on a fresh server, the same cell
is **22.6 t/s at 0.316 acceptance**. The contaminated reading was 2.1x too fast and was
the best-looking number in the table.

A degenerate token loop is trivially easy for a drafter to predict, so acceptance and
throughput inflate *together*. Both metrics moving the right way is normally your internal
consistency check, and here it was the symptom.

Probing further: on that model the plain autoregressive arm is *also* non-deterministic
across back-to-back identical requests at temperature 0, and both arms drift on a second
request to the same slot, with speculative arms drifting much harder. So this is server
slot state, not a drafter defect, and it silently destroys any multi-prompt-per-launch A/B.

Rules: fresh server per request. **Always dump the generated text alongside the timings**
and run a repeated-substring check. Treat "acceptance and throughput both jumped a lot on
the easiest content type" as a contamination signal until you have read the text.

### Trap: your benchmark ran a graph that never contained the code you changed

Benchmarking with an empty prompt (`-p 0`) builds a *decode* graph. If your change lives
on the prefill path, or behind a batch-size gate, it is simply not in the executed graph.
The gate can report "enabled" while the code never runs.

**Verify engagement from the executed graph, not from the gate.** In practice: compare
graph pointers or node counts between on and off configurations, or put a one-shot log
line inside the code path itself. A gate that says "on" is a statement about
configuration, not about execution.

The same trap has a benchmark-suite form. The stock `test-backend-ops perf` matmul cases
top out at n=8, which routes through `mul_mat_vec` and never stages tiles into LDS (the
GPU's shared memory) at all. An entire LDS-padding sweep run through it would have measured
nothing, perfectly
repeatably. Use `--test-file` with real shapes.

### Trap: backgrounding a backgrounded job

If your tooling already runs a command in the background, wrapping it again in `{ ... } &`
makes it report completion immediately while it is still running. Everything downstream
then measures a machine with a live benchmark on it. Related: killing a bench script
mid-run can fire its cleanup trap and start whatever it was supposed to restore, which is
how we once OOM-killed the user session.

Long benchmarks want `setsid nohup`. A bench started as a plain background task died
mid-run when its session process exited, losing 1.5 hours.

### Trap: file size x tokens/sec is the wrong denominator for MoE

For a sparse MoE model, dividing model file size by decode time to get "achieved
bandwidth" is meaningless, because you only touch a few experts per token. We measured
the real per-token traffic on a 256-expert model: **the dense (non-expert) block is 78%
of per-token traffic.**

Consequence: achieved bandwidth is roughly flat (162.5-169.8 GB/s, a 4.5% spread) across
Q4 through Q6, and **a larger file can decode faster than a smaller one** (a 26.55 GiB
Q6_K file beat a 19.45 GiB Q4_K_S one, 65.33 against 64.15 t/s, because its `attn_qkv`
was Q6_K instead of Q8_0 and the dense block shrank).

Two further refinements we needed later:

- **Exclude the MTP / nextn block** from bytes-per-token, not just tensors named
  `.nextn.`. Autoregressive decode loads it and never reads it. On one model that block is
  1.75 GB and skipping the exclusion overstated its bytes by 10%.
- Unsloth `_K_XL` quants pin dense tensors to Q8_0/Q6_K regardless of nominal level, and
  use BF16 for `output.weight`. That alone predicts Q8_K_XL is 13.0% slower than Q8_0 at
  decode. Observed: 13%.

If your roofline analysis of a MoE model uses file size, throw it out.

### Trap: the model does not fit, so nothing is measurable

DeepSeek-V4-Flash at ~103 GB against 62 GB of RAM streams weights from disk for the whole
run. Two launches of the *same binary and model*, differing only in page-cache state, read
pp512@d0 = 6.72 against 7.90 t/s (17.6%) and tg32 = 1.46 against 1.67 (14.4%). A first
launch also shows depth *faster* than d0, because the d0 cells run while the model is
still paging in. That looks like a real curve and is not.

A few-percent A/B cannot survive this, and one launch took 76 minutes. The answer is not
more launches, it is a different instrument: `test-backend-ops perf` at the model's real op
shapes, or per-op GPU timestamps, neither of which has a disk term. Reserve end-to-end
throughput for calibration only.

### Trap: `llama-cli` will not exit

`llama-cli` enters its interactive prompt loop even with `-no-cnv -p "..." -n N` and stdin
from `/dev/null`. On EOF it spins re-printing the prompt, writing multi-GB logs (3.5 GB and
6.8 GB in one session) instead of exiting. Combined with `GGML_SCHED_DEBUG` this fills a
disk fast.

Use `llama-bench -v` for scheduler dumps and `llama-server` plus one `curl /completion` at
temperature 0 for deterministic generation A/Bs.

While we are here: `pkill -f <pattern>` matches its own compound command line, and
`until ! pgrep -f foo; do sleep 5; done` never exits for the same reason. That cost 15
minutes of not noticing a finished job, twice.

## Correctness gating

Performance work that changes numerics is not a win, it is a bug with a nice benchmark.
Our ladder, cheapest first:

1. `test-backend-ops -o <OP> -b Vulkan0` - per-op against the CPU reference. Fast.
   Necessary, and **not sufficient**: we have twice had it pass cleanly on a build that
   produced garbage text, because the failure was in dispatch selection or tensor
   metadata rather than in the kernel.
2. Full-model perplexity (PPL) against a `-ngl 0` (CPU) run of the same model and quant.
   This is what catches the class above.
3. KL divergence (KLD) against the CPU reference when you need to distinguish "different"
   from "worse". PPL is too noisy to resolve small numerical changes.

Concrete result from step 3: across our whole Vulkan fix stack, exactly one change
altered outputs at all (a wave32 flash-attention path): KLD 0.0027, 97.6% identical
top-1 token, PPL indistinguishable from noise. Everything else was bit-exact. That is a
much stronger claim than "PPL looked fine", and it took a day to establish once.

Two things worth adding since the last revision.

**Add the awkward type's test case before you generalise, not after.** A row-materialising
helper built on `dequantize4()` passed every q8_0 case and was silently wrong for q4_0
(NMSE 1.17), because `dequantize4` returns elements in *packed* order, not element order.
Its only other consumers are dot products, where any consistent order sums the same, so
nothing ever forced it to be correct. q8_0's layout happens to be contiguous, so it hides
the bug completely. We caught this only because a q4_0 case had been added in the previous
commit.

**A stride change can compute wrong answers while reading a plausible speed.** An 8-byte
KV row pad measured a believable 288.6 t/s and failed 12 q8_0 `MUL_MAT` cases at
error ~1.0, because `mul_mm` loads A in 8-element chunks and the stride must be a multiple
of 8 elements. Any change to a stride, layout, or alignment goes behind
`test-backend-ops -o MUL_MAT` before it goes anywhere near a stopwatch.

**A framework-free replay loop exists and is the right place to iterate.**

```bash
./bin/test-export-graph-ops -m model.gguf -b 2048 -ub 2048 -o ops.txt   # no weights needed
./bin/test-backend-ops perf --test-file ops.txt -b Vulkan0
./bin/test-backend-ops perf --test-file ops.txt -b ROCm0
```

This dumps a real graph's unique op set and replays it standalone on either backend.
Seconds per shape, no 29 GB model load, and it **reproduces in-model per-dispatch rates
within 1-6%**. That equivalence is itself a finding: it proves a gap is inside the kernels
and not in scheduling, fusion, or allocation. It is how the dense prefill gap got
localised in an afternoon after weeks of end-to-end guessing.

## Instrumentation: an honest assessment

This is where llama.cpp is weakest. The previous revision of this document said "no trace
export, no per-dispatch record". That was accurate and it is the section that has changed
most, because we went and built the missing pieces.

### Can you actually run any of this?

Applying this document's own rule to its own tooling, because "we built a tracer" is
worthless to a reader who cannot get it. Availability as of 2026-08-23:

| tool | where it lives | can you run it |
|---|---|---|
| `GGML_SCHED_DEBUG` | upstream | yes |
| `GGML_VK_PERF_LOGGER`, `_FREQUENCY`, `_CONCURRENT` | upstream | yes |
| `GGML_VK_PIPELINE_STATS` | upstream | yes |
| `GGML_VK_DEBUG_MARKERS`, `GGML_VK_SYNC_LOGGER`, `GGML_VK_MEMORY_LOGGER` | upstream | yes |
| `test-export-graph-ops` + `test-backend-ops perf --test-file` | upstream | yes |
| `GGML_VK_PERF_SHAPES` | this fork's `strix-halo-vulkan` | build the fork |
| `vk-membench` (strided-read microbenchmark) | published separately, `Nathanw1014/kv-membench` | yes |
| `tools/vktrace.py`, `tools/tracecmp.py` (analyzers) | **this repository** | yes |
| `GGML_VK_PERF_TRACE` (Vulkan tracer) | branch `vk-perf-trace` on `Nathanw1014/llama.cpp` | yes, build that branch |
| `GGML_CUDA_PERF_TRACE` (HIP tracer) | branch `cuda-perf-trace` on `Nathanw1014/llama.cpp` | yes, build that branch |
| the three-artifact benchmark runner | not published | **no** |

So the honest position: **most of the instrumentation this document leans on is upstream
and you already have it.** The Vulkan per-dispatch tracer is one commit on a named branch,
216 lines in a single file, rebased onto the current fork tip so it applies cleanly:

```bash
git remote add nathan https://github.com/Nathanw1014/llama.cpp.git
git fetch nathan vk-perf-trace && git checkout nathan/vk-perf-trace
```

The HIP one is a sibling branch, `cuda-perf-trace`, 289 insertions across two files, also
one commit on the current fork tip. Same schema, same event names, same thread ids, so one
analyzer reads both and event names line up for cross-backend diffs.

Both are development branches, not releases, and neither is offered upstream: a second
exporter competing with the existing perf logger is a design conversation rather than a
patch.

**Two caveats on the HIP branch, both load-bearing.** It deliberately does not carry the
local integrated-GPU property fix, so on gfx1151 a build of this branch alone compiles and
runs but is **not numerically or performance-trustworthy** (see *recent upstream master
produces garbage on ROCm/gfx1151* below); apply the tracer on top of a
perplexity-validated tree to reproduce any measurement. And per-shape rates are comparable
across backends only where dispatch counts match, which holds for the prefill shapes and
not in decode.

The aggregator that turns those traces into the tables in the dense prefill section,
`tools/tracecmp.py`, ships in this repository alongside `vktrace.py`, with a
[tools/README.md](tools/README.md) covering both and the asymmetry caveats. Read that
before comparing backends: the two instruments are not symmetric and the mistakes are
silent.

So that section is now reproducible end to end by someone else. What remains unpublished is
the benchmark runner that produces the three-artifact records, which is a lab-notebook tool
rather than an instrument, and is described in
[docs/METHOD.md](docs/METHOD.md) in enough detail to rebuild.

### What exists upstream

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
`VK_KHR_pipeline_executable_properties` output (register counts, LDS usage, spills,
subgroups per SIMD, instruction counts) for every pipeline whose name matches the filter.
This is *compile-time* information, not runtime counters: right tool for occupancy
questions, wrong tool for anything dynamic. It is free, needs no GPU time, and it is what
told us occupancy was identical across four dense pipelines whose throughput spread 25%,
which killed the obvious explanation before we spent a day on it.

**External-tool hooks.** `GGML_VK_DEBUG_MARKERS=1` enables `VK_EXT_debug_utils` labels, so
a capture shows ggml op names on the timeline instead of anonymous dispatches. Read the
RGP section below before assuming you can take that capture: on RADV, for a headless
compute workload, you currently cannot.

**Sync and memory tracing.** `GGML_VK_SYNC_LOGGER=1` prints every barrier the backend
inserts and every node as it is queued. `GGML_VK_MEMORY_LOGGER=1` for allocation churn.

**Isolated op benchmarking.** `test-backend-ops perf -o FLASH_ATTN_EXT -b Vulkan0`, plus
the `--test-file` replay described above.

### The perf logger's own failure modes

Every one of these produced a wrong conclusion before it was understood.

- **It under-reports at large ubatch.** In one dense investigation it implied 62.1 TFLOPS
  against a hardware peak of 55.7, and produced a completely convincing false story about
  where time was going. If a per-op number exceeds the roofline, the instrument is wrong,
  not the hardware.
- **Concurrent mode drops the tail sync interval.** The vocabulary matmul was absent from
  its output entirely; the missing 1.09 ms reconciled the concurrent total against the
  serialized one exactly.
- **It costs about 1 ms per token** of wall time on a mid-size MoE, which is around 10% of
  the thing you are measuring.
- **It asserts under split graphs.** `GGML_VK_PERF_LOGGER=1` plus any CPU/GPU split (for
  example `--n-cpu-moe`) aborts on `GGML_ASSERT(ctx->compute_ctx.expired())`: the
  scheduler's async input copies between splits land in the compute context on devices
  with no separate transfer queue, so the context is live when the next split begins.
  Plain runs tolerate this; only the logger path asserts. The fix is six additive lines
  (flush the pending context before the assert).

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

One useful calibration: at large ubatch on a dense model, per-op and concurrent modes
agreed to 0.2% (8.061 against 8.042 s). At those sizes the barriers cost almost nothing
and per-op attribution is trustworthy. At small ubatch they diverge. Measure the
divergence for your workload before trusting either.

### What we built, because it did not exist (and what you cannot yet run)

Two per-dispatch trace exporters, on the same schema, so traces from different backends
diff against each other. The Vulkan one is on a branch you can build (see the table
above); the HIP one is not published. They are described in enough detail to rebuild
either, because the findings in Part III depend on them and you are entitled to know how
those numbers were produced.

**`GGML_VK_PERF_TRACE=<file>`** (Vulkan). One Chrome-trace event per timed interval, with
op name, tensor name, graph sequence number, and per-dispatch GFLOP/s and GB/s, plus CPU
record and wait spans. `GGML_VK_PERF_TRACE_SKIP` / `_COUNT` bound the capture window. It
rides the existing perf-logger query machinery, works in both per-op and concurrent
modes, and suppresses the stderr table when used for trace only. 216 lines in one file.
Trace totals cross-check exactly against the perf logger table on the same run.

**`GGML_CUDA_PERF_TRACE=<file>`** (HIP/CUDA). 289 insertions across `ggml-cuda.cu` and
`vendors/hip.h`. Emits the same event names, the same `args.op` / `tensor` / `graph`
fields, and the same thread ids, so the analyzers read either backend. It also records
node count and executed-node count on the submit span, which gives you the ggml graph op
count against the actual dispatch count.

**`tools/vktrace.py`** ships in this repo and reads either backend's traces. It provides
`summary`, `layers`, `graphs`, `gaps`, `diff`
over the trace JSON. `gaps` classifies host-code bubbles against in-graph bubbles; `diff`
normalises per graph. A companion aggregator splits a multi-ubatch launch into conditions
by modal batch size per graph, drops the first repetition (the first matmul of the first
graph carries ~29 ms of one-time kernel load), and emits a per-shape matmul table with
achieved GFLOP/s.

Three instrument asymmetries to know before you compare backends:

- HIP events bracket nodes on one stream with no serialisation, so node durations sum to
  wall clock (verified 100.0% busy against span). Vulkan per-op mode barriers between ops.
- **Per-shape GFLOP/s is comparable only where dispatch counts match.** True for every
  prefill shape we measured; not true in decode, where Vulkan emits two events per node on
  some shapes and the node's flops estimate is billed to each, inflating its rate about
  2x. Compare time totals there, not rates.
- Overhead: at ub2048 both tracers are within +0.5% of untraced. At ub256 the Vulkan
  tracer costs 2-6%, because there are many more timestamped dispatches per token. Do not
  read ub256 cross-backend wall-clock off traced runs.

**A standalone Vulkan strided-read microbenchmark**, published separately as
`Nathanw1014/kv-membench` and usable on any Vulkan device.
This is the tool that answered the memory-system questions no amount of in-application
instrumentation could reach. Treat it as a **mechanism detector, not a magnitude
predictor**: it correctly identified channel aliasing, and its magnitudes did not transfer
to the real kernel, because `mul_mm` stages through LDS in longer runs than the probe's
64-byte reads.

### What still genuinely does not exist

- **No hardware performance counters.** `VK_KHR_performance_query` is not used anywhere in
  the backend. You cannot get cache hit rate, memory stall cycles, or runtime occupancy out
  of llama.cpp. The usual advice is to fall back to the vendor tool. On this stack that
  fallback does not exist either, for the reasons below.
- **On HIP, `rocprofv3` is a dead end here and we do not recommend retrying it.** Version
  1.1.0 aborts on every output format with `ring_buffer.cpp:106 mmap failed with errno 22`
  at finalize, then spins in its own chained signal handler. Not a bind-mount problem; it
  fails writing the container's own `/tmp`. The `GGML_CUDA_PERF_TRACE` work above exists
  precisely because of this.

### Why there is no RGP step in that list

An earlier revision of this document listed "`GGML_VK_DEBUG_MARKERS=1` plus RGP for a real
timeline and hardware counters" as a step in "what we actually do". That was wrong and it
has been removed. We have never captured an RGP trace of llama.cpp, and on RADV you
currently cannot. (The story of how that sentence got written, and how it got caught, is
in [docs/METHOD.md](docs/METHOD.md). It is the single most useful thing in that document.)

SQTT capture on RADV is gated on the swapchain present path at two independent levels, as
of mesa-main `d18d598e` (2026-07-20):

- `radv_handle_sqtt`, which starts and stops the capture, has exactly one caller:
  `sqtt_QueuePresentKHR` (`src/amd/vulkan/layers/radv_sqtt_layer.c`).
- In the shared mesa runtime, `device->capture_trace` is invoked from one place,
  `src/vulkan/wsi/wsi_common.c`, and the `MESA_VK_TRACE_TRIGGER` trigger-file check sits
  in the same WSI function.

`llama-bench` never presents, so neither path fires. A headless compute workload cannot
be captured without patching RADV to trigger outside WSI. This is a known long-standing
gap, not something specific to llama.cpp.

`GGML_VK_DEBUG_MARKERS=1` still emits real `VK_EXT_debug_utils` labels, and those are
useful on stacks where a capture is possible at all. On RADV headless they currently
label a timeline nobody can record.

The counterargument to the "instrumentation is inadequate" criticism, for fairness: a
transformer graph is the same ~50 op shapes repeated 40-60 times per token, so a
3000-dispatch timeline is 60 redundant copies of a 50-entry table. Aggregate-by-shape is
arguably the *right* default view here, and it is genuinely more readable than a flame
graph of the same thing. That does not excuse the absence of counters, but it does explain
why the aggregate view has survived, and it is why our own tracers are still mostly
consumed through an aggregating analyzer rather than a timeline viewer.

---

# Part III: what we tested

Organised by area. The falsified sections are longer than the shipped ones, which is the
normal and correct ratio. Read the UPSTREAM / FORK tags: one item here is in stock
llama.cpp and the rest are in our fork. Part 0 explains why.

## Flash attention and KV cache

**Read the first four entries as one argument, not four findings.** They are competing
answers to a single problem: on this memory system, reading a KV cache row-strided is
catastrophically slower than reading it densely, and flash attention at depth does almost
nothing else. Four ways to avoid the strided read were built and measured:

| approach | what it does | cost | status |
|---|---|---|---|
| dequant-once + transpose | convert quantised KV into a dense scratch once per pass | one layer of scratch | UPSTREAM |
| per-head-contiguous f16 copy | copy strided f16 KV into a contiguous scratch | same scratch, f16 only | FORK |
| row padding | pad the KV row stride so it stops aliasing | +1.6% KV memory, -2.4% decode | MEASURED, parked |
| head-major layout | store the cache so the read is dense to begin with | none, but incomplete | MEASURED, parked |

The first two ship and compose; they attack the symptom at the point of use. The second two
attack the cause and are mutually exclusive with the first two by construction, which is why
they are parked rather than rejected: **once you are already paying for scratch, a pad that
removes aliasing you no longer touch buys nothing.** If you are building this from scratch
rather than patching an existing backend, the ordering is arguably backwards: head-major
costs nothing at runtime and gives 2x prefill at 64k with no shader changes at all.

The entries below are ordered accordingly: the two shipped scratch approaches first, then
the two layout alternatives, then the aliasing mechanism itself and what else it turned up.

### UPSTREAM: dequant-once + transpose for quantised KV flash attention

**The one item here that is in stock llama.cpp.** Merged 2026-08-19 as PR #25494, after
review rounds that added the cross-vendor exclusions and the buffer-range caps it now
carries. If you are on current master you already have this.

Quantised KV flash attention on RADV was re-dequantising K and V inside the attention
kernel on every access. Dequantising once into scratch and transposing for the access
pattern gave **+42.2% prefill** on our reference configuration.

Reproduced independently on unrelated hardware (128 GB box, MiniMax-230B, +40.4% at 32k
context, r=2), which is the only reason we consider it established rather than
local-hardware folklore.

Caveat worth stating loudly: **the win is a product of three factors**, not a constant.
It scales with how much of runtime is flash attention, how fragmented the KV access is,
and the GQA ratio. On a model where attention is not dominant the same patch is worth
close to nothing. On Coder-30B-A3B it is about 1.6x, not 2x. A single speedup number for
this class of change is misleading, which is why the entries below give a range and name
the factors it scales with rather than a headline.

### FORK: contiguous-KV flash attention for prefill

The RADV-versus-ROCm prefill gap at depth turned out to be **100% attributable to flash
attention at depth**, not to matrix multiply, not to scheduling. The mechanism: the
coopmat1 `coopMatLoad` path collapses on head-interleaved KV strides.

Making KV contiguous for the prefill path (`GGML_VK_FA_KV_CONTIG`, now default-on,
prefill-only) closed the gap to ROCm parity.

**Status: fork, staged for upstream.** It extends the scratch infrastructure the merged
PR added, so it could not be offered until that landed. On current master it collapses to
two commits, because the merged squash already contains most of what its original branch
carried. It is next in the queue.

Non-obvious follow-up that took us a month to get right: **the size of this win tracks KV
channel count**, roughly `2048 / (kv_heads * head_dim)`, and **not** whether the model is
dense or MoE. We initially believed the dense/MoE story, and it fit the first several data
points. It was wrong. When you have a two-variable confound, the cheap model will fit
first.

Thirteen separate shader-level hypotheses for the underlying kernel behaviour were tested
and falsified before we concluded the kernel is issue-bound rather than
bandwidth-or-latency-bound.

**Full model-level matrix, measured 2026-08-22** against the upstream commit immediately
preceding it, counterbalanced, r=3, 36 launches, pp512 head against patch:

| model | d0 | 16k | 32k | 64k |
|---|---|---|---|---|
| Coder-30B UD-Q6_K_XL (MoE, best case) | +0.4% | +34% | +57% | **2.60x** |
| Qwen3.8-27B Q8_0 (dense, strongest aliasing) | flat | +13% | +72% | **2.72x** |
| Qwen3.6-35B hybrid (worst case, ~10/40 attention) | flat | flat | **-1.5%** | -0.5% |

Decode flat everywhere. The -1.5% cell on the hybrid is real, small, and is the disclosed
worst case: the model has only ten attention layers, so there is little to win and the
copy still costs.

Two scoping results that took a purpose-built sweep each, and that we would have got wrong
by inheritance:

- **The batch floor was wrong.** The path inherited a `neq1 >= 64` gate from the quantised
  case. Sweeping it: nb=64 the copy *loses* about 1.3x, nb=128 is -2%, nb=256 is +2%,
  nb=512 wins 1.8-1.9x. Breakeven is about 256, so the f16 clause carries `neq1 >= 256`
  and the quantised clause keeps 64.
- **The win is path-independent.** With coopmat disabled, the scalar flash attention path
  benefits at the same ratio (about 1.8-2.0x, against coopmat1's 1.8x). So this is not a
  cooperative-matrix quirk; it is the strided read. At small KV (cache-resident) the copy
  *costs* on both paths, which is what the batch floor is for.

And a third, which corrects the *quantised* side of the same gate. **`neq1 >= 64` is a
proxy for the wrong quantity.** What actually amortises a one-off conversion is the number
of times the kernel sweeps the KV cache, `R = qk_ratio * ceil(neq1 / block_rows)`. A token
count is only equivalent to that at one GQA ratio and one tile height, so a model with a
different ratio reaches the same pass count at a different token count.

Measured break-even is `R* = 8.7 to 11.7` at 32k with quantised KV, across GQA ratios 4-12,
head dimensions 128-256 and 2-8 KV heads. Gating on `R >= 12` instead is a win at all four
geometries, and the token threshold then falls out of the model rather than being
hardcoded: `neq1 >= 9` at ratio 12, `>= 17` at ratio 8, `>= 33` at ratio 4.

It changes nothing at large ubatch or at decode. It matters for short prompts and short
uncached suffixes, because **`-ub` is a ceiling, not an allocation**: a 40-token turn onto
a cached prefix runs one attention node at `neq1 = 40` however large `-ub` is. It also
matters for long-draft speculative decoding, which verifies at 49-65 tokens.

Left opt-in, because the constant is calibrated on one GPU at one depth. `R*` rises with
depth as the f16 scratch outgrows the 32 MB last-level cache, so 12 is a 32k number. It is
also scoped to quantised KV: the f16 copy shares the gate but has a higher fixed cost (a
pure copy at 4 bytes per element) and a smaller per-pass saving (it never stages through
shared memory), so its break-even is different and unmeasured.

### MEASURED: KV row padding for power-of-two channel aliasing

**MEASURED mechanism:** the gfx1151 stride penalty on KV access is power-of-two channel
aliasing in the memory system. Not cache capacity, not coalescing granularity, though
both of those also exist as separate independent walls.

The predictor is not "power of two", it is **`gcd(stride_bytes / 256, 16)`**. The memory
system uses a 256-byte granule across 16 channels selected by address bits [11:8]. A
stride of 10240 B is 40 granules, `gcd(40,16) = 8`, so rows land on 2 channels of 16. A
stride of 10496 B is 41 granules, gcd 1, and sweeps all 16.

The fix is embarrassingly small: **a 16-byte pad** on the KV row stride recovers
essentially all of it, at a cost of 1.6% additional KV memory. Our first hypothesis was a
128-byte pad, which also works but costs 8x more memory for no additional benefit.

Headline on stock upstream with the pad only: pp512 **+37.4% at 16k, +65.2% at 32k** on
Coder-30B-A3B with f16 KV; decode flat; perplexity bit-identical at short context.

**Falsified on NVIDIA.** The same test on an RTX 3070 shows no such effect. This is a
property of this memory system, not a general GPU property, and anyone generalising it to
other vendors will be wrong.

Not shipped. The padding sits on a branch and stays there. We took the dequant-once
scratch path to production instead, and the two are mutually exclusive by construction, so
the padding stands as a mechanism finding rather than a landed fix. It remains the cheaper
option if you are not already paying for scratch: the pad costs +1.56% of KV memory and
about 2.4% of decode, while the scratch costs one layer's worth of KV.

**And the kernel is provably not the place to fix it.** The channel cycle is
256 bytes x 16 channels = 4096 bytes = exactly one page, so the channel select bits [11:8]
are page-offset bits. No virtual-to-physical mapping policy can touch them. The driver
cannot transparently fix linear storage buffers either, because their address semantics
are contractual (this is why images get a swizzle and buffers do not). The real fix is a
hashed channel interleave in the memory controller, which server parts have. Everything at
the application layer is a workaround, and it is worth knowing that before you go looking
for a cleverer one.

### MEASURED: 2x prefill at 64k from KV cache layout alone

A head-major KV cache layout gives **2x prefill at 64k context on stock upstream master
with zero shader changes.** This is a `src/llama-kv-cache*.cpp` change, not a backend
change, which is a useful reminder that layer 1 has real performance leverage.

Incomplete: the V tensor path is blocked because a transpose flag is inferred from
strides, and state save/load is not implemented.

### MEASURED: the same aliasing in the f16 dequant scratch, and in a delta-net concat

Once we had the `gcd` predictor we audited every f16 and f32 buffer. Closed form: **f16
camps when the row dimension is a multiple of 256** (worst at 2048); **f32 camps when it is
a multiple of 128** (worst at 1024). So nearly every buffer with a model-dimension row
length camps. What matters is whether it is DRAM-resident and read row-strided.

Measured read rates on the strided-read microbenchmark:

| stride | rate | with +64 B | with +256 B |
|---|---|---|---|
| 10240 B (K=5120 f16) | **14.68 GB/s** | 388.36 | **476.63** |
| 34816 B (K=17408) | 57.11 | | 385.51 |
| 51200 B (K=25600) | 61.83 | | 385.51 |
| 20480 B (f32 activations at hidden 5120) | **7.30 GB/s** | 374.5 @ +32 B | 457.2 |

**Quantised weights are safe for free.** A q6_K row is 4160 B and a q8_0 row 5440 B; those
are fractional in granules and de-alias with no pad at all (222.66 and 364.93 GB/s). This
is why the fused matmul path never exposed the defect: it never materialises f16 weights.
It is also a nice illustration that an awkward block size can be an accidental feature.

Two live instances found by the audit:

- **The dequant weight scratch**, where a 256-byte row pad was worth **+49.6% at ub256 and
  +27.9% at ub2048** end to end, moving a ceiling that had been stuck at 224-235 t/s
  across two models, two quants and two prompt lengths.
- **A delta-net conv-state concat** on the qwen35 architecture, reading a transposed source
  at stride 40960 B: `40960/256 = 160`, `160 mod 16 = 0`, so **every read lands on one
  channel of sixteen**. Measured 13.7 GB/s against 138.9 GB/s fixed, a 10.1x that is
  entirely the channel count. 138.9 GB/s is the achievable streaming wall for that access
  pattern, so there is nothing further to win in that kernel. End to end it was worth +7.2%
  at ub2048 and +0.4% at ub256, and it shipped default-on.

### FALSIFIED: channel aliasing on weight operands, and as an explanation for the ubatch decline

Two negatives that matter more than the positives above, because they bound the theory.

**Padding the weight operand makes it worse.** f16 at k=5120 has the textbook 2-of-16
camping stride, and padding it through the test file's explicit strides cost **+18.2% at
+64 B and +9.2% at +256 B**. The pad turns the source into a strided view and costs more
than the aliasing it removes. Do not chase camping on weight operands.

**Camping does not explain why wide dense models get slower with ubatch.** The f32
activation operand at hidden 5120 genuinely reads at 7.30 GB/s, and genuinely leaves the
32 MB last-level cache at ub2048 (5120 x U x 4 = 40 MB). That looked like the answer.
Halving the operand to f16 (20 MB, fits) lifted the whole curve uniformly and left the
slope alone (-9.4% to -8.6%). If spill drove the decline the curve would have flattened.
**The ubatch decline is still unexplained.** What survives is that the 7.30 GB/s reading
is a real property of that stride. The causal link is not.

**Weight streaming during decode is not channel-camped either.** We tested whether
power-of-two weight-row camping explains decode's ~155-161 GB/s against a 242 GB/s
sequential peak. Falsified: real quantised strides (q4_0 2304 B, q8_0 4352 B, q6_K 3360 B)
reach **232-235 GB/s, 97-98% of the same-session sequential anchor**, because odd block
factors already rotate rows across channels. Pure power-of-two f16 dips only ~9% at
64-lane groups and the dip is gone at 256 lanes, and a 16-byte pad does not recover it, so
it is not even the same mechanism.

### FORK: DeepSeek-V4 gather-compact attention and head-compaction fusion

Decode-path gather-compact flash attention plus a head-compaction fusion produced a
**17-23x speedup on the flash attention op at 32k-64k context**, with a depth-flat
profile where the baseline degraded steeply. Community verification on a 128 GB machine
put end-to-end decode at +55% at depth 0. Beats ROCm on every V4 configuration we tested.

**Status: fork.** Vulkan is the last backend without this model family's ops, and the work
is sliced for upstream as a series rather than one change, which is a queue of its own
behind the item above. Parts of the surrounding V4 stack were contributed by other people
and are credited in the repository, not here.

### MEASURED: flash attention tile waste at small batch, and it is KV-type dependent

Upstream routes N=1 to the scalar path (`block_rows = 1`) and N>=2 to coopmat1, where
`block_rows` is a hardcoded 16. So N=2 computes a sixteen-row tile to use two rows. This
produced a 6.3x jump between nb=1 (105 us) and nb=2 (665 us) in one grid, which is what
sent us looking.

It only bites when GQA head batching cannot fill the tile. `max_gqa = min(block_rows, 32)`
evaluates to 16 and the GQA path needs `qk_ratio <= max_gqa`, so a normal ratio-8 model
becomes N=8 through head batching and fills the tile. An MQA-shaped model (64 query heads
over 1 KV head) is refused batching entirely and the tile holds only real query rows.

Routing N<=8 to the scalar tuner, which sizes `block_rows` to N:

| nb | f16 base to scalar | q8_0 base to scalar |
|---|---|---|
| 2 | 664.5 to 192.4 us (3.45x) | 659.8 to 171.8 (3.84x) |
| 4 | 772.7 to 489.0 (1.58x) | 767.8 to 455.9 (1.68x) |
| 8 | 953.4 to 671.2 (1.42x) | 935.1 to 602.1 (1.55x) |

nb=1 and nb=16 unchanged, exactly as the mechanism predicts.

**This is not yet a recommendation, and a follow-up audit is why.** On real models the
outcome flips with KV type. On a 35B with f16 KV, hd256, real head-interleaved strides,
forced scalar wins **17-38% of flash attention time at N=2-8** and never regresses (about
+5-6% end to end at the verify batch shape). On a different model with **q4_0 KV, hd128,
scalar loses 60-90%**: the cooperative path's staged tile loads absorb an interleaved
72-byte-in-576-byte read pattern that the scalar path cannot. Any threshold change has to
gate on KV type, and the blast radius is every model on every cooperative-matrix device.

The audit that produced that reversal also turned up two results with nothing to do with
the routing decision. They stand on their own, so they are recorded here rather than being
parked alongside the fix:

- **GQA head packing is correct and load-bearing** on both models (unpacked is 2.2-3.7x
  worse), and flash attention scaling in N is **sublinear**. Computing achieved bandwidth
  from KV bytes times batch gives 566 GB/s at N=8 against ~200 GB/s of DRAM, which is not
  a real rate: it is the arithmetic failing, because cache absorbs much of the per-token KV
  re-streaming. Naive KV-traffic arithmetic overestimates the value of packing wins.
- **Matmul at n<=8 is already well routed**; forced-tile arms lose 2.4-4.9x on both dense
  and expert-routed paths. That question is closed. But **n=9 to 15 is a 2.2-2.3x
  whole-pass cliff** at the 8-to-9 boundary on both models, because the vector path's
  column limit is 8 and the tile path is weak at roughly one token per expert. That
  matters for any speculative decoder with a draft width of 8 or more, and fixing it needs
  shader work.

Harness calibration from the same grid, worth reusing: across 101 cases measured twice,
the cells this switch *cannot touch* moved by 8 to 26%. **Treat anything under about 1.3x
in a single `test-backend-ops` process as unresolved.**

### FORK: the coopmat1 P-fragment hoist

In the second GEMM of the cooperative flash attention shader, a fragment load that depends
only on the KV block index sat **inside** the head-dimension tile loop. The data it reads is
not written again until the next KV block, so all four fragments were re-read from shared
memory once per tile: twice over at head dim 128, four times at 256. Loading them once into
an array before the loop is the whole change.

8 insertions and 3 deletions in one file, unconditional, with no gate and no environment
variable. Resources unchanged or better: 96 registers before and after, zero spilled, shared
memory unchanged, code size down. Measured at -6.25% of op time, and **+6.9 / +8.1 / +9.2%
end to end at 8k / 16k / 32k** on Coder-30B, with the largest effect (+8.71%) at head dim
256, which is what the tile-count arithmetic predicts. Correctness: 5105/5105 on the
attention suite, 15884/15884 full.

**Status: fork, and it is the strongest standalone upstream candidate of the three flash
attention changes shipped at the same time.** It is unconditional rather than gated, it is
one small hunk in one file, it benefits every cooperative-matrix device rather than only
this one, it costs nothing measurable in resources, and the defect is plainly a bug rather
than a tuning preference. Its sibling commits are a wave32 subgroup rule for the same
shader, which is the one change in the whole stack that moved model outputs at all (KLD
0.0027), and a shared-memory relayout that has no measured benefit and is on hold.

**The one real risk, and why it is not simply submitted:** the array it hoists out of is
function-storage with a specialisation-constant bound and a non-constant access chain, and
**glslang does not unroll it**. RADV folds the bound and promotes the array to registers, so
it is fine here, but the entire benefit depends on the driver unrolling both loops. That
path is shared with pre-Blackwell NVIDIA, Intel, and AMD's Windows driver, so it wants a
second vendor's numbers first. Mitigations if a vendor objects: an unroll hint on the load
loop, or named variables instead of an array.

It is also possible other in-flight work makes it redundant before it lands, which would be
a fine outcome.

## Dense prefill: a worked example of localising a gap

This is the most complete investigation in the record, it ran from 2026-08-16 to
2026-08-22, and it is included at length because the *shape* of it is more transferable
than any individual number.

### Step 0: the claim was folklore

"ROCm is faster than Vulkan on dense prefill" was widely believed, including by us. When we
went to look, **no dense ROCm prefill run existed anywhere**: not in our own 626-run index
at the time, not in the public toolbox corpus, not in two third-party data sets. Every ROCm
prefill row that existed was MoE.

The first real measurement, quiesced box, three launches, spread under 0.3%, each backend at
its own best ubatch (Qwen3.8-27B, pp2048):

- ROCm q6_K at ub1024: **372.4 t/s prefill, 8.56 t/s decode**
- Vulkan q6_K at ub256: **315.1 / 8.51**

So prefill was **+18.2% ROCm** and decode was a tie at +0.6%. The whole dense gap was
prefill. That is a much more useful statement than the folklore, and it took one afternoon.

### Step 1: it is a ubatch-scaling gap, not a kernel-quality gap (this turned out to be half right)

| model | VK ub256/512/1024/2048 | ROCm ub256/512/1024/2048 |
|---|---|---|
| Qwen3.8-27B Q6_K_XL | 314.4 / 307.9 / 295.0 / 286.0 | 299.9 / 346.8 / **369.9** / 364.5 |
| Qwen3-32B Q6_K_XL | 262.2 / 257.8 / 254.9 / 252.8 | 237.4 / 297.6 / 328.9 / **337.7** |

**We win at ub256** (+4.6%, +9.5%) and lose from ub512 up. Vulkan is flat to declining
across 8x of ubatch and pins near 16-17 TFLOPS on both models, 44-45% of the achievable
rate. ROCm climbs to 19-21.6.

Immediate practical consequence, which is still the right advice: **pin `-ub 256` for
dense models on this stack.** It is our peak and the only setting where we win. (MoE is the
opposite and wants 2048; see the model-class section.)

The mechanism of ROCm's climb is the routing rule mentioned in Part I: its q8_0 curve is
flat (346.1 / 347.6 / 345.9 / 335.6) and only q6_K climbs, jumping +15.6% exactly at the
ub256-to-ub512 boundary where `ggml_cuda_should_use_mmq` drops q6_K into
dequantise-then-hipBLAS. So on this hardware, dequantising to f16 and calling a BLAS beats
staying on the int8 matrix cores by up to 23%. Against ROCm's *own* MMQ path we were within
3.5%.

### Step 2: nine eliminations, and a tool that lied

The ubatch decline survived: not activation spill, not occupancy, not GPU idle (traced gaps
1.1% and 0.2%), not attention chunking, not the hybrid architecture, not weight quant, not
any environment flag (ablated with a null control), not build version, not tile selection.

A full warptile sweep came back **negative**: 128x128 is already optimal, forced small,
medium and large tiles lose 12.3 / 15.2 / 7.2%, and a valid BN=256 configuration is 13-19%
slower at every ubatch with a worse slope. Two traps in that sweep alone: an override
placed before the chip-tuning block silently collapsed every configuration into one (a void
sweep, caught only by falsification), and one configuration read **+34.5% while failing
correctness** because it gave a four-warp workgroup to an eight-warp tile.

And this is where `GGML_VK_PERF_LOGGER` implied 62.1 TFLOPS against a 55.7 peak and built a
convincing false story. Which is what motivated the tracers.

### Step 3: two matmuls, 102% of the gap

With per-dispatch traces from both backends on the same schema, Qwen3-32B at ub2048, GPU
busy per 2048-token pass: HIP 6.089 s, Vulkan 8.042 s, gap +1953 ms.

- `MUL_MAT q6_K m=25600 n=2048 k=5120`: **+1491 ms**
- `MUL_MAT q6_K m=5120 n=2048 k=25600`: **+507 ms**
- Everything else nets to zero.

That is **102% of the whole gap in two dispatch shapes.** On the 27B, one shape alone is
84% of its gap.

And Vulkan's rate is flat: 17.1 TFLOP/s at ub256 and **17.1 at ub2048** on the dominant
shape, never above 20.3 anywhere. HIP's q6_K goes 15.8 to 29.4 across the same range. So
the "ubatch decline" was never a matmul-rate decline. Vulkan's matmul time barely moves
(7294 to 7344 ms); the ub256-to-ub2048 GPU-busy increase of +1.4% is roughly half
non-matmul (norms +21%, elementwise +79%) and half matmul.

Two things Vulkan *wins* in the same trace, which is why the end-to-end gap was only 32%
when the matmul deficit was two full seconds:

- **Flash attention by 1.5-1.9x** with dispatch counts matched (32B at ub2048: 285 ms
  against HIP's 542). Worth 257 ms at ub2048, the single largest thing we win.
- **Zero ROPE dispatches**, because the backend fuses rope into the QK-norm; HIP fuses only
  the norm and leaves 128 of them. A wash in time, 128 fewer dispatches.

Decode is parity at the kernel level: 2.065 s against 2.111 s of GPU busy over 16 tokens,
matmul 94-98% of decode on both, at 222.6 GB/s which is ~92% of the memory ceiling.

### Step 4: the decisive table

Replaying one shape (`m=25600 n=2048 k=5120`) across weight types on both backends, in
TFLOP/s:

| src0 | HIP | Vulkan | HIP / VK |
|---|---|---|---|
| f16 | 32.4 | **16.6** | **1.95x** |
| bf16 | 32.9 | 8.9 | 3.72x |
| q6_K | 29.6 | 17.1 | 1.73x |
| q4_0 | 25.9 | **21.4** | 1.21x |
| q4_K | 24.0 | **21.4** | 1.12x |
| q8_0 | 22.4 | 19.2 | 1.16x |
| f32 | 2.5 | 7.3 | 0.34x |

**Vulkan's f16 GEMM, which does zero dequantisation work, is its worst path, slower than
its own q4_0 kernel.** That single row reorganises everything:

- The ladder on this hardware is **hipBLAS f16 ~29 > int8 MMQ on matrix cores ~21.6 >
  Vulkan coopmat1 `mul_mm` ~17-18.**
- **The gap is quant-shaped and q6_K is the worst case.** A dense Q4_K model should show a
  far smaller deficit. (Untested prediction, recorded as such.)
- The target is not "make q6_K faster". Even our best path is 1.5x off HIP's best.

Two controls, both killing the obvious alternatives: cooperative matrix *is* engaged
(disabling it costs 1.47-1.98x, so this is not a scalar fallback), and it is not simple
bandwidth (q8_0 moves 30% more bytes than q6_K and runs faster).

### FALSIFIED: copy ROCm's strategy (dequant-then-f16-GEMM)

`GGML_VK_DEQUANT_SPLIT` forces dequantisation to f16 followed by a plain f16 GEMM, which
is exactly what ROCm does for q6_K above ne11=256. It **loses at every ubatch from 256 to
8192**, on three model/quant combinations: -55.7% at ub256, -21.2% at ub2048. Even after
the channel-camping fix lifted it by +28-50%, it was still 13% behind best-against-best.

The weight-type table above is *why*, and this is the ordering lesson: we had the negative
result a day before we had the mechanism. Its destination on Vulkan (f16, 16.6 TFLOP/s) is
**below where the fused quantised kernels already sit**. Copying a dequant strategy cannot
help when your f16 GEMM is the slow part. Matching HIP needs a faster f16 kernel, not a
prepass in front of the existing one.

Its value was diagnostic anyway: removing the per-N-block weight dequant flipped the ubatch
slope from -9% to +61%, and the split path's ceiling was identical (224-235 t/s) across two
models, two parameter counts, two quants and two prompt lengths. That invariance is what
pointed at the channel-camping defect.

### FALSIFIED: wire up the integer-dot MMQ pipelines on a coopmat1 device

This looks like an oversight in pipeline creation and it is a trap. `ggml_vk_mul_mat_q_f16`
prefers the q8_1 pipeline whenever it exists, so creating those pipelines on a coopmat1
device would **displace cooperative matrix with the scalar shader** and cost about 40% of
dense prefill. Measured with coopmat disabled: 314.8 against 194.9 on the 27B, 261.5
against 152.2 on the 32B.

Integer-dot MMQ itself is worth only 0 to +4% on this chip.

Corollary, which is the part worth carrying: **ROCm's MMQ wins because it is on the matrix
cores** (`wmma_i32_16x16x16_iu8_w32`), not because it is integer. RADV does expose the
primitive, and llama.cpp has no cooperative int8 matmul shader, so writing one is a real
project. On the q8_0 evidence it is worth about 4%, not the ~18% headline. Do not fund it
on this data.

### FORK: run the quantised dense cooperative pipelines at wave32

RDNA3.x matrix instructions are wave32-native, so a wave64 subgroup issues each cooperative
op as two halves. The expert-routed path in this fork already ran wave32, with a comment
saying dense pipelines were untouched. Giving dense the same treatment is the whole change.

**The mechanism was measured, not assumed**, using the free static shader statistics:

- **Occupancy is identical** across the f16/q4_0/q6_K/q8_0 dense pipelines (8 subgroups per
  SIMD, 192 VGPRs, 0 spills). Occupancy does not explain a 17.1-to-21.4 TFLOP/s spread.
- **Instruction count orders the results** (q4_0 3610 to 21.4, q8_0 3661 to 19.2, q6_K 3907
  to 17.1): inline dequantisation competes with matrix-op issue.
- wave32 on q6_K: **3907 to 3433 instructions, -12.1%**, identical registers and occupancy.

Results: end to end, counterbalanced, spread <=0.5%, **Qwen3-32B +7.2% at ub256 and +3.9%
at ub2048; Qwen3.8-27B +5.3% / +4.8%.** KV-independent (repeating with q8_0 KV moved every
cell by under 0.3 points). Decode untouched, and *measured* untouched (8.52 t/s in both
arms, stddev 0.00) because decode dispatches through a different function entirely.

**Perplexity identical, all 20 per-chunk values equal, and there is a reason that does not
generalise:** the retile changes *which warp owns an output sub-tile*, not the order any
single element accumulates over K. It is arithmetically inert. Unlike the one flash
attention change that did move outputs, which changed the reduction itself.

The gate is deterministic, with no runtime measurement: required subgroup size equal to the
tile's own warp width for every dense cooperative pipeline (the shaders derive their warp
grid from the subgroup id and size shared arrays accordingly, so leaving it to the driver
made the agreement incidental), and only tiles that can legally retile are retiled, rather
than asserting. Float tiles are excluded **on measurement**: they are bandwidth-bound, not
issue-bound, and gained nothing (f16 -6.7 to +6.4%, bf16 about zero).

**The MoE arm is a methodology story.** At n=2 per arm it read -0.2% / -1.2%, the wrong
*sign*. One high launch in a two-sample arm. Settled at n=6 per arm across 12
position-balanced launches: +0.2% / +0.8%, both inside the within-arm spread of up to 4.5%,
so "no measurable effect" rather than a gain. Expected, since the expert matmuls already
ran wave32.

**Status: fork, not offered upstream.** The gate is scoped to one driver on one
architecture and no NVIDIA or Intel data exists for it, which is exactly the validation an
upstream reviewer would ask for and we cannot currently supply. There is a probe mode that
also retiles the float tiles, for anyone who can run it on other hardware.

### FORK, THEN CORRECTED: the LDS pad, and why a measured win was still a bug

This is the most instructive item in the document. It is a fork-shipped, measured,
verified +7% that was simultaneously a **2.4-3.1x regression** for everyone on a stock
driver. Note that it never went upstream, and that this is the entry most likely to make
you glad it did not.

The shared-memory stride for the matmul tiles is `BK/2 + pad`, in 4-byte elements, so the
element stride *is* the bank stride on a 32-bank machine. Upstream used one pad constant for
all non-Intel devices, and 4 is not this chip's optimum. Sweeping it:

- **The stride must stay even.** Odd is -53%, because it breaks 8- and 16-byte shared-read
  alignment.
- Among even pads, throughput tracks bank spread: **pad 2 (stride 18, 16 banks) is +13%
  mean over pad 4 (stride 20, 8 banks)**; pad 0 (stride 16, 2 banks) is -31%.
- Per type: q4_0 +32%, q8_0 +22%, q4_K +10%, q6_K +1%. Biggest where dequantisation is
  *cheapest*, which is the complement of the wave32 win, so the two compose.

End to end on top of wave32: **27B +8.3% / +6.6%, 32B +4.1% / +3.6%, Coder-30B MoE +5.8%**
(where wave32 gave nothing). Decode unchanged, perplexity identical. It shipped default-on
for RADV, gated per path on measurement (pad 2 for quantised, pad 4 for float, because the
float paths prefer the opposite).

Then a downstream user on a stock Ubuntu Mesa bisected a prefill collapse to that commit.

It reproduces exactly on system Mesa 25.2.8: **MoE 597 against 1426 t/s, dense 107.5
against 332.8.** Same binary on our development driver: pad 2 is +7.0%.

**The root cause is not driver taste, it is a specification violation.**
`VUID-RuntimeSpirv-OpCooperativeMatrixLoadKHR-08986` requires the pointer and stride to be
aligned to `min(16 bytes, natural row bytes)`, which is 16 bytes for these tiles. Stride
bytes are `(BK/2 + pad) * 4`, so **only `pad % 4 == 0` is legal**, and the 16-bank stride of
18 (72 bytes) can never be. Both drivers share the same lowering and the same alignment
annotation; they differ only in how the compiler backend copes with an out-of-contract
stride. ISA dumps settle it: 25.2 lowers the load as 40 x `ds_read_b128`, entitled by the
16-byte contract, and the 72-byte stride pays runtime misalignment splits on odd rows;
25.3+ lowers as 96 x `ds_read_b64`, for which 72 bytes is always aligned, so only the
bank-spread dial moves. Codegen is pad-invariant per driver.

A version sweep (RADV built per release tag, each A/B'd with the same binary) puts the
change at 25.3.0 and holds it for four consecutive releases: 25.2.8 pad2 -58%; 25.3.0 /
25.3.6 / 26.0.8 / 26.1.8 / 26.2.1 / 26.2-dev / 26.3-dev all pad2 +5.4 to +7.0%.

Fix shipped: pad 2 gated on `driver_id == MesaRadv && driverVersion >= 25.3`, everything
else gets spec-legal pad 4 and is bit-identical to the previous commit. The gate also
narrows an older "AMD and not proprietary" test that would have matched a different driver.

**Status: fork, and this is a good argument for why some things should stay there.** A
tuning constant fitted to one driver version range, which needed a downstream bisect to
find its own regression, is not something to push at every llama.cpp user.

**Three lessons, and they are all about us:**

1. We had the alignment classes in hand from an earlier sweep and still read 16 bytes as a
   *tuning axis* rather than a *contract*. When a validation rule and a measurement
   disagree, the measurement is describing one driver.
2. A tuning constant that is one constant for every device in a class is a signal that
   nobody has measured it, and also that you are about to change behaviour for everyone.
3. The bug was found by a user on a normal driver, which is the configuration we never
   test. Our development driver was the thing making the violation survivable.

For completeness, the pad question turned out to be **three mechanisms, not one**, which is
why the first hypothesis fit and was still wrong. Discriminating with pads 4/6/8, which make
opposite predictions about alignment class and bank spread:

- **Quantised: bank spread, overdetermined.** pad 2 and pad 6 (same bank class, different
  alignment) agree within 0.6% on every quantised cell; ordering is 16 banks > 8 > 4.
- **f32: load width.** pad 8 beats pad 6 by **+47%** with a quarter of the bank spread. The
  float path reads two adjacent elements per k-step and wants 16-byte-aligned rows to keep
  the wide shared-memory read legal.
- **f16: neither.** pad 2 and pad 6 differ by up to 17.7% at identical bank counts, which
  kills bank spread, while pad 6 beats pad 8 despite worse alignment, which kills load
  width. Unexplained. We do not guess about it in public.
- **bf16: pad-indifferent** within 0.4%, consistent with bandwidth-bound.

So "the float path prefers pad 4" is a *compromise between two operand types that want
opposite things*, not a preference. And an earlier belief that the float path ran a
different BK was simply wrong: the shader overrides the host constant, so both run the same
stride.

### FORK: f16 B operand for quantised dense matmul

About 40 lines of C++ and **no shader work at all.** The `matmul_<type>_f16` SPIR-V is
already built for every quantised type, and the pipeline array already exists; upstream only
ever populates it in the coopmat2 branch, with no recorded rationale. Populating it for
coopmat1, relaxing the getter's f32-only check, and folding a flag into the existing
convert-to-scratch plumbing is the whole change.

**Numerically free, not merely safe.** Perplexity is bit-identical (6.0671 both arms, 20
chunks, engagement confirmed from a log line). The reason: the matmul shader already stages
B into shared memory as f16 before the cooperative multiply, so the f32-B kernel *already
rounds B to f16*. Only the storage format and the bytes moved differ.

Measured at pp2048, and the win is size-shaped:

- Qwen3.8-27B Q6_K_XL (hidden 5120): **+5.5 to +7.2%**; the same model at Q8_0 +4.9 to +6.4%
- Qwen3-32B Q6_K_XL (hidden 5120): **+5.6 to +6.8%**
- Qwen2.5-7B Q4_K_M (hidden 3584): **-1.2%**; Coder-30B MoE (hidden 2048): -0.5%
- **Decode untouched**, and measured untouched: the engagement line appears zero times in a
  decode-only run, because at batch 1 the dispatch goes elsewhere. It halves *activation*
  bytes, not weight bytes, so it cannot help a weight-streaming-bound decode. The win shows
  up in time-to-first-token (-3.7%).

Default-off, because MoE regresses about 0.5% and MoE is this fork's main workload. There is
an `auto` mode gated on the hidden size. Two things worth knowing that the commit does not
say: `=1` beats `auto` above ub256 (+8.2% against +6.8% at ub1024), so the gate leaves
headroom, and a quant-type gate measures *worse* end to end than `auto` (+4.7% against
+5.8%) because a mixed quant file has contributing tensors the gate excludes.

**Status: fork, default-off.** Upstreaming it would mean either defending an `auto` gate
fitted to one hidden size on one device, or handing everyone a mode that costs MoE half a
percent. Neither is a good offer yet; a per-shape sweep would make it one.

**We got the attribution wrong once and corrected it.** An earlier version of this entry
said quant type was ruled out and model width was the axis. A matched-shape measurement
(same m/k/n, only the weight type varying) shows q4_K never wins while q6_K and q8_0 win
+4 to +7%. The 7B loses because it is Q4_K_M, not because it is small: one of its shapes is
larger than most of the 27B's and still does not gain. The earlier call came from varying
type inside a dead zone of shapes.

### MEASURED: the amortisation question, answered

"Does HIP do one big thing we do not?" is answerable with a two-parameter fit. Fitting
`time = a + b*n` on the dominant q6_K shape: **HIP has a fixed 1.71 ms per call** (0.49 ms
for q8_0) that it amortises over n; **Vulkan has none** (-1.23 ms, no fixed term). That is
dequantise-once-then-BLAS against dequantise-inline-per-tile, visible in two coefficients.

Consequences: **at n=64 Vulkan wins, 12.0 against 8.8 TFLOP/s**, and the crossover is around
n=256-512, which is exactly the end-to-end ub256 crossover. The two curves are the same
story at two scales.

**B re-streaming is falsified as an explanation.** Growing m from 3200 to 51200 (16x the B
re-reads) moves Vulkan only 18.1 to 17.4 TFLOP/s at n=2048 while HIP climbs 22.1 to 29.8.
Vulkan's ~17.2-17.6 is invariant to both m and n: a **kernel rate ceiling**, not a cache or
traffic effect. There is no scheduling win hiding here.

### MEASURED: int4 cooperative matrix on RADV, as a driver extension

The furthest-out item in the record, included because the *shape* of the result is useful
even if the specific work is not something most people will repeat.

On gfx1151, int4 matrix ops are the only primitive above fp16 rate (int8 is 1x, and there is
no fp8 or structured sparsity until the next architecture). The instruction is
**`V_WMMA_I32_16X16X16_IU4`**, it is in the hardware, and the compiler backend already
defines the opcode (`aco_opcodes.py`, gfx11 opcode `0x45`, with 16x16x32 and sparse variants
defined for the next architecture) and already cost-models IU4 at 2x. Nothing exposes it to
a shader.

Adding a private int4 cooperative-matrix component type to RADV (97 lines across 13 files)
and a W4A4 FFN prefill lane to the Vulkan backend:

- **108.6 int4 TOPS against 53.6 f16 = 2.03x**, bit-exact against a CPU reference on 11
  seeds, and slightly above a HIP harness doing the same thing on the same chip.
- Under realistic inner-loop conditions with shared-memory staging: **105.8 TOPS, 97% of
  ceiling**, ratio 2.01x under load. **No cooperative-load collapse**, because the packed
  carrier needs 2 dword shared reads per fragment per lane against 16 half-word reads for
  f16. That is a direct contrast with the cooperative-load collapse that motivated the
  contiguous-KV work.
- End to end, Qwen3.8-27B pp2048 at ub256, three launches per arm: Vulkan off 362.05,
  Vulkan on **440.30 (+21.6%)**, ROCm 371.14. So the lane turns a 2.4% ROCm lead into an
  18.6% Vulkan lead.

**The catch is quality and it is not small.** Plain round-to-nearest W4A4 costs mean KLD
0.073 on the 27B, against 0.0027 for the only shipped change that moved outputs at all. It
is opt-in and it stays opt-in.

Three things falsified along the way, all of which sounded right:

- **Not bandwidth-bound.** The 64x64 roofline arithmetic matched the measured 30-34 TOPS,
  which was convincing until we built the 128x128 tile: it is *slower* (28-29 against
  30-33). The roofline assumed zero cache reuse. A model that fits your number is not a
  model that is right.
- **Not segmentation.** Matching a reference implementation's coarser quantisation cadence
  buys 2-10% and costs +29.5% error.
- **Not double buffering**, which an earlier probe had already ruled out by hitting 97% of
  ceiling with no global staging.

Coverage turned out to be real but modest, and the naive projection was badly wrong:
profiling found only 35.6% of prefill in the q6_K FFN we take. Opening the q8_0 shapes too
goes 440.6 to 469.1 t/s (+6.5%) for KLD 0.059 to 0.103. The naive projection said 567 t/s,
because it assumed the win transfers: the q6_K win was mostly *avoiding an expensive q6_K
dequantisation* (16.3 TFLOP/s), while q8_0 already runs at 24.9, so a 30 TOPS kernel only
beats it by 1.2x. **A speedup on one path does not project onto a path that was already
fast.**

A file-naming trap fell out of the same work and generalises: a GGUF named `UD-Q6_K_XL`
reports a Q4_K ftype and its traced tensors are q6_K in one big FFN shape plus q8_0 in six
shapes plus q5_K. It is q8_0-dominant by dispatch count. **Always read per-shape type names
from a trace, never from the filename.**

### Where the dense gap stands now, and why the numbers above need rebasing

The 18.2% ROCm lead that opened this section was measured on 2026-08-16. The shipped fix
stack (wave32, LDS pad, f16 B operand) has since moved the Vulkan baseline on the same
model and setting from **315.1 to 362.1 t/s**, against an essentially unchanged ROCm
371.1. **So the ROCm dense prefill lead is now about 2.4%, not 18.2%.**

This is stated explicitly because it is exactly the kind of number that gets quoted for a
year after it stops being true, and because every localisation in this section still holds
at the new baseline: the gap is still those two FFN matmuls, which is why an int4 lane that
touches only those matmuls moves prefill +21.6%.

If you are comparing backends on this hardware, take your own baseline. Ours moved 15% in
six days.

## Matrix multiply and MoE

### FORK: MUL_MAT_ID grouped GEMM

A redesign of the MoE expert-routed matrix multiply, delivered as seven independently
gated pieces so each could be measured alone. Result: **pp512 +24.5%, 128k prefill
+42-46%.**

**Status: fork, and partly overtaken.** An upstream change by someone else implements the
same row-list prepass idea that our first stage did, so that stage is theirs now and the
right move is to rebase the later stages onto their layout rather than propose ours. That
is a normal outcome of working in public on a slow queue, and it is worth saying out loud
because the alternative is quietly re-proposing superseded work.

The important finding is not the speedup, it is the diagnosis. **The MoE "tax" (roughly
2x slower than the equivalent dense computation) is gather cost, row-list construction,
and fragmentation. It is not a DRAM bandwidth ceiling.** We believed the bandwidth story
for a while. An overnight ablation batch killed it.

Three specific sub-optimisations, all of which sounded obviously correct, all **DEAD**:
cheapening the unpack step, increasing occupancy, and double-buffering. None produced a
measurable win. The kernel is not limited by any of the things those address.

### RETRACTED: "MUL_MAT_ID is dequant-bound"

We held and repeated this claim. It is wrong, and the way it was wrong is the useful part.

A clean within-type ablation at fixed shape: baseline 2198 us; no B loads 2068 (-5.9%); no
multiply 2044 (-7.0%); both 1927 (-12.3%, near-additive); **no dequantisation unpack 2191
(-0.3%)**. Two other weight types are untouched by the unpack mode and serve as in-run
canaries. So B loads plus multiply plus dequantisation are about 12% of the op, and **~88%
is the A-load-to-shared-memory path**, sitting 2.5-2.8x above the DRAM floor.

**The methodological point is the part worth telling other people.** A full-model-graph
ablation of the same change gave **2.04x** for it, because the ablated op emits garbage that
propagates downstream and lifts sustained clocks on other ops. Timing each op in isolation
with fresh random inputs removes that. The original claim's own commit message documented
the confound (an uninstrumented op sped up 1.34x purely from zeroed data raising clocks) and
we did not read it as disqualifying at the time.

The control that settles it: sweep across weight types at fixed shape and convert to
achieved bandwidth on A. **f16, which does zero unpack, reaches only 99 GB/s at n=128, 2.1x
off the DRAM floor**, while q4_K is 2.3x off. Same gap with and without dequantisation.
Arithmetic agrees: ~2.5 vector ops per weight needs ~512 G ops/s against a ~7.4 T ops/s
budget, 7% utilisation. Occupancy is not the wall either (8 subgroups per SIMD, and the
ablation was a runtime branch so occupancy was identical).

Real location of the gap: the tiled path gets 60-160 GB/s where the vector path gets 149
GB/s at matched shape *and matched working set*. That is a 1.34x gap, not the 3.2x first
written, which compared unequal working sets against the 32 MB cache. At n=512 it is also
only 7.2 TFLOPS, about 14% of cooperative peak, which points at N-dimension tile-occupancy
waste, and that is the framing of somebody else's open upstream PR rather than a finding of
ours.

### MEASURED: coopmat1 fragment layout on gfx1151

We measured the actual `(lane, element) -> (row, column)` mapping for cooperative matrix
fragments on gfx1151: A is row-contiguous, B is strided, with 4x replication across
wave64.

This is not documented and it unlocks ROCm-style fused dequantisation without the scratch
buffer that the dequant-once approach requires. Probe code exists; the optimisation
itself is not built.

### FALSIFIED: coopmat2 on RADV

Thoroughly dead for the workgroup-scope feature set. It does not even engage without a
workgroup-128 patch, and once it does: 2608 flash attention configurations fail, and it runs
**6.8x slower than coopmat1** because RADV emulates it through shared memory rather than
mapping it to hardware.

**Narrowed since the last revision, and the narrowing matters.** That verdict belongs to
*workgroup-scope* cooperative matrices: a workgroup spans several waves, so lane crossing
cannot reach across it and the driver must emulate through shared memory, which is also what
the workgroup-128 requirement was about. **Subgroup scope needs no emulation.** At ISA level,
RADV lowers the per-element and reduce operations to pure register code with lane-crossing
instructions and zero shared-memory traffic, on exactly the subgroup-scope declaration the
existing flash attention shader already uses. That is the per-element accumulator access the
KHR cooperative-matrix extension lacks and HIP has, which is the mechanism behind a
deep-context gap we have measured elsewhere.

Not upstreamable as it stands: it depends on a vendor extension that RADV gates behind a
default-off driver configuration option. Treat it as a driver research thread, not a
llama.cpp change. Verdict stands for workgroup scope, flexible dimensions, and tensor
addressing.

### FALSIFIED: split q8 scratch buffers

The bet was trading memory traffic for shared memory. Result: **20% slower at 32k depth**
than the f16 scratch it replaced. Clean canary, engagement verified from the executed graph,
so this is a real negative and not a measurement artifact. We kept the prototype as evidence
and did not commit it.

## Decode: where the time actually goes

Decode turned out to be the best-understood part of the system, and the answer is boring in
a way that is worth publishing, because a lot of effort gets spent attacking things that are
not the problem.

### MEASURED: one bandwidth, many fixed costs

A single fit across 17 on-box models spanning a 31x byte range:

```
ms/token = 4.549 x GB_per_token + 2.64      R^2 = 0.9992
```

The marginal term is **220 GB/s, which is 91% of the 242 GB/s ceiling, on every model
class.** Nobody has a bandwidth problem. Percent-of-ceiling, which ranges 50-90% across
models, is almost entirely the *fixed* term divided by bytes per token.

**And the fixed cost sorts by attention architecture, not by sparsity.** The decisive
measurement is a size-matched dense control: a 27.23 GB/token hybrid model has a **4.13 ms**
fixed cost while a 28.13 GB/token plain-attention dense model has **1.03 ms**. Both dense,
same byte scale, 4x the fixed cost. Gated-delta-net hybrids sit at 3.4-4.1 ms whether they
are dense 2B, dense 27B or MoE 35B. Conventional MoE sits at 1.5-1.6 ms. Plain dense sits at
0.9-1.0 ms.

Depth behaves differently by class too: full-attention models get **more** efficient with
depth (77.7% to 86.3% of ceiling from d0 to 64k, as the fixed cost amortises), while hybrids
stay flat at 71-74% because only a quarter of their layers hold KV.

### RESOLVED: the 10-21% of decode wall time that was not GPU op time

This sat in the previous revision's open questions. It is closed, and it is not a defect.

The observation: GPU op time summed to 705.4 ms against 783.5 ms of wall on one model
(10.0%) and 1011.0 against 1273.6 on another (20.6%).

The eliminations, in order:

1. **The GPU is not idle.** Sampling the busy counter at 20 Hz across a steady-state decode
   window: mean 95.9% busy, 567 of 600 samples in the 90-99% band, none below 50%. So it is
   not CPU or submission bound. (First attempt at this was invalid: the sampler had no delay
   and captured model load, reporting a bogus 41.9%.)
2. **Graph reuse removes real CPU work and changes no wall time.** Testing an upstream draft
   PR: user CPU -15%, wall -0.83%, and kernel-side replay cost pushed *total* CPU up. There
   was no CPU-bound stall to remove.
3. **The barrier hypothesis is wrong by construction.** The perf logger computes per-op time
   as consecutive timestamp deltas, which *tile* the whole span from first to last timestamp.
   Barriers between dispatches are already inside the per-op numbers.

Which leaves the answer: `sum(per-op) == last_ts - first_ts`, so the missing time is
everything **outside** each graph's GPU span. That is the per-token serialisation point
inherent to autoregressive decode: fence wait, readback, sampling, next-graph submission.
You cannot start token N+1's graph until N's output is sampled. **Structural, not a defect,
and not reportable as a bug.**

It reconciles all three measurements at once, which is how you know it is the right answer:
GPU ~96% busy, sum-of-ops below wall, and graph reuse changing nothing.

Worth noting: **speculative decoding amortises this serialisation over k+1 tokens**, which
is part of why speculative results beat the naive token-count arithmetic.

### MEASURED: the dispatch floor, and the interval census

Every tiny op costs 2.3-4.1 us regardless of the work it does. That is a **dispatch and
barrier floor of about 2.3 us**, paid roughly 820 times per token on one MoE model, so
around 500 tiny dispatches are about 1.2 ms of pure overhead.

The census across models is the useful artifact:

| model | wall/token | sync intervals/token | GPU busy | idle |
|---|---|---|---|---|
| Coder-30B MoE, d0 | 10.3 ms | ~350 | 92% | ~0.8 ms (7.7%) |
| Coder-30B MoE, d8192 | | ~350 | 95% | same absolute, ~5% |
| Qwen3-32B dense, d0 | 129 ms | | | <1.5%, irrelevant |
| Qwen3.6-35B SSM hybrid, d0 | | **913** | **80%** | **2-3.6 ms, up to 20%** |

**The hybrid is the real victim**, because its SSM layers are long chains of tiny
elementwise ops, each one its own sync interval. That is where a generic elementwise-chain
fuser would be worth something (potentially +10-20% on that model) and where per-pattern
fusion is worth nothing.

Digging into the submission side to check whether the CPU pipeline was the problem: it is
not. Graph build, schedule and record all overlap GPU execution; fence-fire to next compute
entry is ~2 us; whole-graph recording is 1.1-1.5 ms against ~9.5 ms of GPU execution, 6x
headroom. A submit-granularity sweep found the default near-optimal, and **coarser batching
is 3% worse** because it breaks the recording/execution overlap. So the residual 5-8% idle
is distributed intra-graph micro-idle at sync boundaries, not a serial prologue.

### FALSIFIED: fuse dispatches to recover that time (twice, both bit-exact and both null)

We built two fusions to attack the dispatch floor. Both worked, both were bit-exact
(perplexity and greedy output identical), both were verified engaged, and both changed
wall-clock by zero.

**Fusion 1, gated-linear-unit into the up-projection.** Net zero: wall +0.2% +-0.4, and the
concurrent profiler showed the region *worse* by 0.66 us per layer. Mechanism: the unfused
gate and up dispatches run barrier-free in one sync interval and **overlap by ~3.2 us per
layer** (64.4 us for the pair against 67.6 us serialized, about 154 us per token of overlap).
Fusing forces a barrier between them and destroys the overlap, exactly cancelling the saved
dispatch.

> **Any fusion that splits a barrier-free dispatch pair must beat that pair's measured
> overlap first.** That is a cheap thing to check and we did not check it first.

**Fusion 2, merging the pair itself.** The kernel worked, coverage was 26 of 48 layers, and
the concurrent profiler confirmed the win was exactly the eliminated dispatches, about 66 us
per token of GPU-busy time. At n=10 per arm the wall A/B was 98.21 +- 0.25 against 98.48 +-
0.18: **zero to negative.** At depth, dead even.

**GPU-busy savings in that region do not convert to wall time at any depth**, because about
0.9 ms per token of inter-interval submission slack absorbs them.

Only one fusion in the whole audit converted: folding a row-scatter into a matvec epilogue,
**+0.93%**, bit-exact.

The implication we acted on: the remaining audit items were the same dispatch-trimming class
and were predicted nulls, so we did not build them. **The honest ceiling for that programme
is +3.5-4.5% near-term and about +7% for the whole thing at d0**, against an original guess
of +13-18%. The normalisation family is already 3-to-5-op fused and mostly irreducible.

### MEASURED: what the last-level cache is worth

A useful byproduct of a bandwidth sweep: a q4_K weight tensor's footprint (33.03 MB) sits
right at the 32 MB last-level cache, and the isolated-op loop reuses it, so it measures
cache-resident: **678-720 GB/s, about 3x DRAM.**

That is the first direct number we have for what residency is worth on this part, and it is
the strongest argument for the cache-control work described in the driver section: keeping
weights from evicting KV and activations is worth up to 3x on whatever stays resident.

## Speculative decoding

### MEASURED: draft depth has a cliff, and the cliff has a cause

A k-sweep on an MTP self-speculative model, temperature 0, three content genres, acceptance
read from the server's own counters:

| k | speedup | acceptance |
|---|---|---|
| 1 | 1.26x | 96.7% |
| 2 | 1.54x | 96.3% |
| **3** | **1.67x** | 92.8% |
| 4 | 1.42x | **64.3%** |
| 5 | 1.25x | 51.5% |

k=3 is optimal and k>=4 falls off a cliff **because the model has one MTP layer**. A single
layer natively predicts one token, so drafting four or more iterates it past what it was
trained to do. That generalises to any single-layer-MTP model and is exactly what an
adaptive heuristic should key on.

### MEASURED: DFlash2 is roughly 2x over base at all depths, and v1 was not

A newer drafter architecture (dynamic depthwise convolutions around both sublayers plus a
candidate selector over adjacent-token pairs) measured against both plain autoregressive
decode and the previous drafter, one request per server launch, counterbalanced, 18 launches:

| prompt | AR | v1 (n_max 5) | v2 (n_max 7) | v2/AR | v2/v1 |
|---|---|---|---|---|---|
| code | 11.43 | 24.01 | 37.38 | **3.27x** | 1.56x |
| prose | 11.85 | 15.25 | 22.61 | **1.91x** | 1.48x |

The important correction is about *our own earlier reporting*: a 1.39x figure at 32k that we
had attributed to depth decay was **content**, not depth. It was measured on a code corpus.
On prose the ratio holds at roughly 2x at every depth. v1 does die at depth; v2 does not.

### MEASURED: a drafter cannot change what the model says, so stop trying to match it

We expected an abliterated target model to break a stock drafter, because the drafter taps
target hidden states at layers the abliteration rewrote. If acceptance collapsed, speculative
decoding would be *slower* than plain decode and a refusal-matched drafter would be worth
building.

It does not collapse. Paired A/B across five prompts: **mean -1.5 percentage points of
acceptance, sd 4.07, two of five positive.** A null. The refusal-local hypothesis also fails:
the largest drop is on a neutral reasoning prompt, and the two refusal-adjacent prompts sit
mid-range.

The general rule this rests on is worth stating plainly, because it retires a whole category
of idea: **speculative decoding is exact with respect to the target** (up to floating-point
associativity), so a drafter can only ever move *acceptance*. Anything you want to change
about the output belongs on the target model.

A harness sanity check from the same run, also reusable: autoregressive throughput was 7.75
t/s at Q8_0 against 11.75 at Q4_K_XL, a 1.52x ratio against a 1.62x file-size ratio. Decode
is bandwidth-bound, so that is the relationship a correct baseline should show, and the AR
arm was flat across all five prompts (7.69-7.76), which is what a baseline should look like.

### MEASURED: acceptance is prompt-dependent, so most speculative comparisons are invalid

Same binary, same box, same model, varying only the reasoning-effort setting:

| level | prompt tokens | tokens/s |
|---|---|---|
| off | 1187 | 18.6, 18.4 |
| low | 1215 | 19.7, 20.2 |
| medium | 1185 | 19.4, 19.0 |
| xhigh | 1227 | 18.7, 18.7 |

**A 9.8% spread with no code or hardware change.** Speculative throughput is
tokens-accepted-per-forward-pass, and acceptance depends on how predictable the continuation
is. Reasoning directives also change the rendered prompt, so the prompt token count moves
with the setting.

A throughput comparison across prompts, or across reasoning settings, is comparing
acceptance, not speed. Pin the prompt *and* the reasoning setting, and record the prompt
token count next to the number.

### MEASURED: test speculative exactness on CPU, never on the GPU

"Speculative decoding is lossless" gets re-tested every time speculative code changes, and a
mismatch reads exactly like a rollback bug. On this stack it usually is not one.

Matrix on a fixed 105-token prompt, greedy, 192 tokens:

- **CPU:** speculative against non-speculative is **token-exact 192/192**, across ~50
  rollback rounds. Rollback is correct.
- **Vulkan:** not token-exact. q8_0 KV diverged at token 129, f16 KV at token 55, while every
  configuration is bit-identical run to run.

So the divergence is batched-verify against single-token kernel-shape numerics flipping
near-tie argmaxes, not a rollback fault, and KV quantisation is not the cause (f16 diverged
*earlier* here). **No checkpointing change can make Vulkan speculative-against-plain exact**,
because verify batches and single-token decode take different matmul paths.

How to apply it: compare speculative against plain **on CPU**, where logits are
batch-shape-invariant. On the GPU, only compare like for like (same configuration, run
against rerun, must be bit-identical), which catches true nondeterminism.

**And there is a residual we have not explained.** Beyond the 192-token horizon, CPU
speculative and plain do eventually fork: at token 776 on one prompt, 280 on another. It is
prompt-dependent in position, and it is **mechanism-independent**: two different rollback
mechanisms and four different draft trajectories all emit the same output and all fork from
plain decode at the same token. So it is a deterministic property of speculative-mode
evaluation against plain decode, not rollback noise. Prime suspect: recurrent-scan chunking
during batched verify reordering accumulation even on CPU, which would mean "CPU logits are
batch-shape-invariant" holds for attention and not for the state-space scan. Open.

### MEASURED: prefill positions are a biased proxy for draft tokens

Measuring attention-selection overlap between drafted tokens, with the sparse gate's own
counters over 25538 tokens of context:

| source of the "draft" tokens | overlap |
|---|---|
| adjacent prefill tokens (the proxy) | 0.397 |
| real draft tokens | **0.56** |

**Real draft tokens overlap more than adjacent prefill tokens do**, so any quantity derived
from the prefill proxy is biased. The reason is structural rather than model-specific: a
draft explores alternative continuations, while adjacent prefill positions are committed text
that already agrees with itself.

It cost us a 3.14x headline that was really 2.47x. If a proxy is all you can reach, say so in
the artifact **and state which direction the bias runs** before quoting anything derived from
it. When the real source becomes reachable, re-measure rather than assuming it transferred:
the correction here was 40% on the ratio.

### The livelock that three sessions called a deadlock

The best debugging story in the record, and the one with the most transferable lesson.

Symptom: a server stops emitting tokens partway through a long generation. Every thread
parked in a futex wait. Reported as GPU idle. Three separate investigations concluded
deadlock, and one of them built a fence-lifecycle ledger that came back perfectly clean.

It was a **livelock at about 88% GPU busy.** On partial draft acceptance the checkpoint
restore path replays the accepted tokens, and the replay went through the *same verification*
as a fresh draft. On a backend where logits depend on batch shape, the re-verification can
permanently reject its own prefix, restore the same checkpoint, and replay, forever. Captured
verbatim: "accepted 2/3, restore at pos 995" every 27 ms, output 3 bytes in 30 seconds.

Every backtrace landed in the fence wait **because that is where the hot loop's wall time
lives.** A hot loop that emits nothing is indistinguishable from a hang in any single-point
observation, and lock-shaped instrumentation then *confirms* the wrong theory.

The triage procedure that would have got it in minutes, written up as the rule to run
first on the next one. Stated as a rule rather than as a habit, because at the time of
writing it has been derived from one incident and not yet exercised on a second:

> Before diagnosing any serving stall as a deadlock, take a **60-120 second time series**,
> not a snapshot: output file size (frozen or crawling), the GPU busy percentage,
> per-process DRM engine time deltas from `/proc/<pid>/fdinfo/*` (who is consuming the GPU),
> and ring emitted-against-signalled deltas from the debug filesystem.
>
> **Busy + advancing rings + frozen output = livelock.** Switch to application-level round
> tracing, not lock forensics. All idle + a fence never signalling = a real wedge.

Practical aid for attaching a debugger after a stall without perturbing the run: launch the
server with a small preloaded library whose constructor sets the ptrace-attach permission, and
plain `gdb -p` works afterwards with zero runtime cost.

CPU is immune to this class by construction (shape-invariant logits mean the replay always
agrees), which is another instance of the CPU-as-oracle pattern that runs through this whole
document. The fix is that a replay round never re-verifies: force-accept the replayed prefix,
because the authoritative acceptance already happened before the restore, and sample only the
continuation. Proven neutral by a bit-identical 800-token A/B.

Two secondary lessons, both expensive:

- **All prior validation sat under the stall horizon.** Every probe was 192 tokens or fewer;
  the stall arrives 250-500 tokens in. Add a long generation to any speculative validation.
- A release was cut from a branch tip carrying this, so it shipped. Enumerate and smoke-test
  the commits that ride along with a release, per risk surface, before cutting it.

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

RADV maps `ACCESS_NON_TEMPORAL` to the mid-level cache bit only. It never sets the bit that
would mark data as no-allocate in the 32 MB last-level cache. Worse, `coopMatLoad` drops the
access operand entirely.

HIP's non-temporal load builtin sets both. So a cache-bypass strategy that works on HIP has
no expressible equivalent through RADV today. This is a driver gap, and combined with the
3x-for-residency measurement above it is one of the clearest remaining opportunities on this
part.

### MEASURED: HIP flash attention decode collapse with quantised KV

Why q8_0 KV decode is bad on ROCm/gfx1151: the fused vector kernel **is** active, so the
usual explanation (falling off the fast path) is wrong. The actual cause is that it does
not batch GQA, so it performs 8x redundant dequantisation.

A q4_0 control run confirms the kernel is element-bound and ALU-bound, not
bandwidth-bound. Note that a bandwidth model "explains" the observed numbers reasonably
well and is nonetheless wrong. This happens more often than is comfortable.

### MEASURED: recent upstream master produces garbage on ROCm/gfx1151

Bisected to a specific commit changing integrated-GPU property handling, plus a separate 6x
slowdown from HIP math flags.

**`test-backend-ops` passes on both the good and bad builds.** This is the clearest
example we have of why per-op testing is insufficient. Validate HIP builds with
full-model perplexity against `-ngl 0`.

### MEASURED: a unified-memory read path that costs 40% of server prefill

Worth its own entry because it is 100% upstream code, it affects any unified-memory Vulkan
box, and it presented as five unrelated mysteries.

Hybrid and recurrent models make `llama-server` create two context checkpoints per prompt,
which is two CPU reads of a 62.8 MiB recurrent-state buffer. The Vulkan backend's read path
does a **direct CPU memcpy whenever the buffer is host-visible**. If that buffer landed in
write-combined memory the read runs at ~210 MB/s, about 300 ms per checkpoint, which is
exactly a 1221-to-748 t/s server prefill drop on a 1185-token prompt.

Whether the buffer lands in write-combined memory or the cached carve-out is a **packing
knife-edge**: model file size, KV quantisation type, and enabling speculative decoding all
flip it. That is what generated the false correlations, and we chased three of them (an MTP
tensor theory, a quant-mix theory, a prompt-cache theory) before finding the real one.

`llama-bench` never reads state, so it shows nothing at all. The whole class is invisible to
the standard benchmark.

Fix: gate the direct path on the memory being host-*cached*, else use the existing staging
copy. Six lines. Verified on three models.

### The instrument-building bugs, which are also findings

Two bugs found while writing the HIP tracer, both of which are patterns rather than
one-offs:

- **Synchronising on the last recorded event is wrong when the event pool is reused across
  graphs.** The API can return on the event's *previous* completion state. One graph
  reported a 3 us wait while its kernels spanned 6.03 seconds, reaching back into the prior
  graph's window. Synchronise the stream.
- **Disabling CUDA graphs by returning false from the obvious setter does nothing**: the
  caller invokes it for side effects and discards the return value. The real gate is
  elsewhere. Decode captured 2 of 33 token graphs and under-reported by 7x. Prefill was never
  affected, because batch > 1 does not use graph capture at all.

## Where the ceiling is the API, not the code

Several of the walls in this document cannot be moved from inside llama.cpp, and a couple
cannot be moved from inside the driver either. Worth separating out, because time spent
optimising against a wall of this kind is wasted, and because the fix routes somewhere
other than a llama.cpp pull request.

**KHR cooperative matrix has no per-element accumulator access, and that absence is
measurable.** HIP reaches accumulator elements directly. The vendor `cooperative_matrix2`
extension exposes a per-element operation and a reduce, and at ISA level RADV lowers both to
**pure register code with lane-crossing instructions and zero shared-memory traffic**, on the
same subgroup-scope declaration the existing flash attention shader already uses. The KHR
extension has no equivalent, which is the mechanism behind a deep-context gap we have
measured. This is the clearest "the API is the ceiling" item in the record.

Note this **narrows, and does not contradict, our own coopmat2-is-dead verdict** above. That
verdict is about *workgroup* scope, where a workgroup spans several waves so lane crossing
cannot reach across it and the driver must emulate through shared memory: 6.8x slower, 2608
failing configurations. Subgroup scope needs no emulation at all. Two very different
questions wearing one extension's name, and we conflated them for a while.

Not actionable today regardless: the vendor extension is gated behind a default-off driver
option, so it needs a per-user opt-in. It is a driver and standards thread, not a llama.cpp
change.

**Cache control is not expressible.** The non-temporal access operand exists in the API,
RADV maps it to only one of the two cache-level bits, and `coopMatLoad` drops it entirely.
So the cache-bypass strategy that works on HIP has no expressible Vulkan equivalent, on the
part where our own measurement says residency is worth about 3x. Driver-side gap.

**Alignment is a contract, and we learned that the expensive way.** The cooperative-load
validation rule requiring 16-byte pointer and stride alignment is the reason a measured +7%
shared-memory pad was a 2.4-3.1x regression on every driver outside a narrow version range.
The specification was right and our measurement was describing one compiler backend. Full
account in the dense prefill section.

**Buffers above 4 GiB needed a driver extension.** Indexing a storage buffer past 4 GiB is
not expressible in stock Vulkan, and llama.cpp works around it by slicing large tensors into
row-ranges. Implementing 64-bit indexing in RADV (conformance suite 864 pass / 0 fail,
verified on hardware) makes the unsplit dispatch **2.08x the row-split path** on a synthetic
4.64 GiB tensor, and separately fixed a real stall: a long-context multi-slot serving
configuration whose KV cache exceeded 4 GiB as a single buffer wedged on a stock driver. The
Mesa merge request is open; the buffer-level chunking half of it is a standalone correctness
fix for anyone with a buffer that large.

**One thing did land at the standards level, and it is instructive that it is small.** A
conformance-test fix was merged into KhronosGroup/VK-GL-CTS in August 2026: a one-block
support check that failed to require the extension and feature the code path under test
actually depends on, so the cases ran, hit a parse abort, and reported as failures rather
than as unsupported. That is what engaging at that layer usually looks like in practice.
Not a new extension. A gate that was wrong.

**The int4 case is the opposite shape: the hardware is there and nothing exposes it.** On
this part, `V_WMMA_I32_16X16X16_IU4` is the only primitive above fp16 rate, the compiler
backend already defines the opcode and cost-models it at 2x, and no extension surfaces it. A
private component type gets 2.03x fp16 and is bit-exact, so the gap really is exposure. The
route is an extension proposal, not a patch. There is adjacent work in flight from others
(4-bit *storage* with fp16-rate compute), which is complementary rather than competing.

**A llama.cpp-side lesson from the same territory**, since it does not belong to any of the
above: its cooperative-matrix gate passed its shape checks against a driver that advertised
the feature and computed wrong answers. Nothing guards against advertise-but-miscompute. If
you gate on an extension being present, you are trusting the driver's self-report.

**And the counterweight, so this section does not over-claim.** The memory-channel aliasing
that runs through half of Part III is **not** an API problem and no amount of standards work
touches it. The channel cycle is exactly one page, so the channel-select bits are page-offset
bits, and no address-mapping policy can reach them. The driver cannot fix it transparently
either, because linear buffer address semantics are contractual: that is why images get a
swizzle and buffers do not. The real fix is a hashed channel interleave in the memory
controller, which is a hardware and firmware matter. **Application-level workarounds are the
only shippable layer, and knowing that is worth more than another week of looking for a
cleverer one.**

## Numerics and quantisation

### MEASURED: q8_0 KV converts to speed, q4_0 does not

On this hardware, going from f16 to q8_0 KV cache produces a real speedup. Going from
q8_0 to q4_0 does not. The crossover is somewhere between 8 and 4 bits, which means the
usual assumption that smaller KV is monotonically faster is false here.

Since the fix stack landed, KV quantisation is **no longer a prefill-speed decision at
all**: f16 and q8_0 land within 1.2% of each other at every depth on every model measured.
It still buys memory and decode throughput at depth (+41% on one model at 64k). And it costs
about 0.4-1.1% of *shallow* prefill, which is a quantisation overhead with no depth benefit
to pay for it yet.

### MEASURED: fp8 is a weights format here, not a KV format

Simulated on a real KV dump (6144 cells, 60 MB of slot state), mean signal-to-quantisation
noise across 62 blocks:

| encoding | bits/weight | SQNR |
|---|---|---|
| q8_0 | 8.50 | **43.75 dB** |
| e4m3 + per-32 f16 scale | 8.50 | 32.99 dB |
| e4m3 + per-tensor scale | 8.00 | 31.54 dB |
| e5m2 + per-32 f16 scale | 8.50 | 26.99 dB |
| e5m2 + per-tensor scale | 8.00 | 25.56 dB |

**e5m2 for KV is dead**, 16.8 dB behind q8_0. **e4m3 also loses**, by 10.8 dB at an identical
bit budget. The "K has outliers so it wants exponent range" hypothesis is real and far too
small to matter: the correlation with kurtosis is strong (r = -0.858) and the gap only falls
from 12.16 dB to 7.63 dB across the range. It never flips the ranking.

Encoder sanity check worth copying: e4m3 beats e5m2 by exactly 6.00 dB, which is one mantissa
bit at 6.02 dB per bit. That is how you know the simulator is doing the right thing before
you trust any of the other rows.

Caveat stated as we state it internally: SQNR is a proxy, not KLD.

### MEASURED: TurboQuant KV, and where it breaks

We built a numpy-only reference implementation of TurboQuant KV quantisation, validated
19/19 against the paper.

Findings: a per-coordinate residual **sign** beats the paper's construction at 1 bit per
dimension. And tq3_0 is effectively lossless for V while it **collapses** for K, so the
usable configuration is asymmetric.

Important correction to our own earlier conclusion: we initially attributed the K
collapse to an indexing bug in the cooperative flash attention path. It was not a bug. It
was chaotic amplification of a genuine format weakness. **The collapse is a flaw in our
format, not a law about 3-bit K.**

### MEASURED: Q8_0 weights are not measurably more accurate than Q6_K

Tested directly on a model where we expected the opposite. Q8_0 was +22.4% prefill and
-16.4% decode versus Q6_K, with no measurable accuracy advantage. Meanwhile switching the
KV cache to f16 bought the fidelity we were chasing for 0.94 GB, against a 36 GB model
download.

Worth internalising: **spend precision on the KV cache before spending it on weights.**

### The `dequantize4` permutation trap

`dequantize4()` in the shared dequantisation helpers is permutation-agnostic. Its only
consumers are dot-product kernels, where any consistent element order gives the same sum, so
nothing ever forced it to return elements in element order. For q4_0 it returns packed order,
while the real layout has byte j carrying element j in its low nibble and element j+16 in its
high one.

**So it must not be used to materialise a row into memory**, which is the one use where order
matters. Use the per-type materialising shaders, which carry each type's true mapping.

Why it is a trap rather than a bug: q8_0's layout *is* contiguous, so a materialiser built on
it passes every q8_0 test and looks correct. Without a q4_0 case in the suite it ships
silently wrong.

## Bugs found and fixed

### FORK: iq4_nl flash attention gate mismatch

84 flash attention failures that presented as `inf` values in attention sinks. The actual
cause was a `supports_op` / dispatch mismatch: the predicate claimed support for a
configuration with no matching pipeline. Hard-gate fix plus tests. Full suite: 15538/15538.

**Status: fork, deliberately not upstreamed.** The type became natively supported upstream
shortly afterwards, so the failure mode cannot occur there. What survives is the pattern:
a single source of truth for which KV types have a native shader, with `supports_op`
mirroring every hard dispatch condition and an assertion against silent fallback. That
matters again the next time a type is accepted without a shader behind it.

### MEASURED: f16 accumulator overflow in scalar flash attention MMQ

An upstream bug, not hardware-specific: the scalar flash attention MMQ path accumulates
in int32 and then overflows the f16 accumulator type with q8_0 K at default precision.

One-line fix, verified: 5154/5154 with the fix, 5152/5154 with the shader hunk reverted and
the tests kept, so the tests are proven non-vacuous. Held rather than submitted because the
practical impact is close to zero and the fix adds a branch on a hot path. Recorded here so
nobody spends time rediscovering it.

### FORK: quantised reshape stride bug causing silent CPU fallback

The loader's reshape path computes the row stride without accounting for block size, so a
quantised tensor looks non-contiguous to the backend. Vulkan then declines it via
`supports_op` and it silently runs on CPU. In the reported case: 43 layers demoted,
splits going from 88 to 174, presenting purely as a decode performance regression with no
error output.

One-line fix, in the fork. The bug itself is upstream, arriving with a change that made
one model family's weights reshaped at load time; other people have carried a fix for it
too. This is the canonical example of why `GGML_SCHED_DEBUG=2` should be the first thing
you run on any unexplained slowdown: timing never found it, structure did, across seven
timing arms that all failed to reproduce.

### FORK: quantised KV silently disabled every sparse path on DeepSeek-V4

Two community test sets reported no decode benefit from a release. Both had passed
`-ctk q8_0 -ctv q8_0`.

The sparse prefill gate and the small-batch gather gate both tested for f16 and returned
false, while the compressed cache took the requested type straight through. Net effect of
one flag: sparse prefill off (worth about 1.46x end to end at 32k), small-batch gather off,
union off. Only the indexer survived. On a different branch the same flag did not degrade,
it **aborted the process**, because the decline branch asserts that the split form never
declines once shape checks pass, and the author had guarded shape but not type.

The diagnosis is the reusable part. Once admitted, q8_0 was still 1.78x slower than f16, and
it was **not** path selection (both resolve to the same cooperative configuration, verified
by instrumenting the tuning function) and **not** bandwidth (q8_0 reads half the bytes). It
was inline dequantisation in the attention loop, once per query block that reads a row
instead of once per row, and it shows up as a clean constant: **0.148-0.157 us per KV row
attended**, across every batch width and dense alike. A clean constant per unit of work is
usually a redundancy, not a bandwidth wall.

The fix generalises: **put the decode where the data is already being touched once.** The
gather reads each selected row exactly once, so decoding there converts per-use work into
per-row work at no extra pass. q8_0 at batch 8 went 3936 to 1567 (gather alone) to **891 us**
(fused decode), ending 1.5-1.8% *faster* than f16, because after the gather both do identical
f16 attention and q8_0's scattered read moves half the bytes.

**Status: fork**, riding with the sparse attention work it belongs to.

### FORK: a drafter that silently costs 2.4x

A speculative feature enabled itself from a single metadata key. A drafter carrying that key
without the graph structure behind it reads hidden states as something they are not. Measured
on a deliberately key-injected drafter: **0 of 1556 drafts accepted, 4.77 t/s against ~11.4
autoregressive.** A silent 2.4x slowdown, no diagnostic, and the natural assertion never fires
because the pointer it checks is non-null.

Fix: a capability query rather than a metadata sniff, with a warning and fallback, plus a
load-time refusal for the impossible combination. The general form: **when a feature enables
itself from metadata, the failure mode is not a crash, it is a silent performance inversion.**

**Status: fork.** The feature itself is somebody else's open upstream pull request, so the
right move is a review comment offering the mechanism on that PR rather than a competing
change of our own. A public reproduction branch and a deliberately broken checkpoint exist
so the trap can be rebuilt from public files in about two minutes.

### MEASURED: unbounded command-buffer packing versus the kernel watchdog

A long-standing "high context equals Vulkan crash" class of report. The mechanism: the backend
packs up to N graph nodes per command buffer submission, and zero-estimated-flops operations
(transposed copies, which grow with KV size) carry no weight in the packing heuristic. At high
context each is ~100 ms, and a hundred of them crosses the kernel's 10-second compute watchdog.
The ring resets and the application sees a lost device.

Proven with a standalone reproducer, no model and no memory pressure, producing the exact
signature on a stock box with a default watchdog. A bytes-aware submission gate fixes it
(28 lines), validated by the same harness wedging with the gate off and running clean with it
on, at identical prefill performance.

Three things about this one that are worth more than the fix:

- **Prior art existed and disclosing it made the case stronger, not weaker.** The mechanism was
  already known upstream and the manual escape hatch already shipped, added by someone who
  explicitly backed out his own automatic heuristic saying he did not know how to choose a safe
  value. A bytes-aware bound is precisely the missing principled version. And a cited 2-second
  watchdog elsewhere against our 10-second one proves no fixed node count can be right.
- **The cross-vendor answer was a negative, and it changed the pitch.** An RTX 3070 on Windows
  showed no trip at any packing size up to 1500, at 28.2 seconds of wall in one command buffer
  against a 2-second timeout, 11x over. The threshold was genuinely reached. Best explanation:
  the AMD kernel driver's timeout bounds a whole submitted job, while the Windows one bounds
  *preemption latency*, and with every dispatch ~18 ms there is always a preemption point. So
  this is a portability hazard on one kernel driver, not a universal crash, and pitching it as
  the latter would have been wrong.
- **We had to correct our own published description**: the submit condition has four triggers,
  not two, so lifting the node cap splits one command buffer into two rather than creating one
  giant one. The result was unaffected; the explanation was wrong.

Bonus finding for anyone chasing these: a single-value kernel timeout parameter sets the
non-compute rings only on bare metal. The four-value form is needed. Most "I raised the timeout"
reports never touched the compute ring.

## Architecture-level observations

### The NPU is worth approximately nothing

For LLM inference on this part, at this time, in this software stack. Do not plan around
it.

### The 32 MB last-level cache is the underused resource

Now with a number: cache-resident weights read at 678-720 GB/s against ~232 GB/s from DRAM,
about **3x**. And the driver does not currently give you the controls to exploit it, because
it never emits the no-allocate hint (see the non-temporal finding). This is the clearest
remaining opportunity on Strix Halo and it is a driver-side one.

### Decode is bandwidth-solved; prefill is where the model classes differ

From the model-class fit: decode marginal bandwidth is 91% of ceiling on every class, so
class differences there are entirely fixed cost. Prefill is the opposite: dense models reach
37-55% of the achievable rate and MoE only 24-34% at ub2048 (18-26% at ub512).

That asymmetry drives a concrete tuning rule that is easy to get backwards: **MoE gains 5-7
points from ub512 to ub2048 and wants a large ubatch; dense gains 1-3 points and peaks at
ub256.** One number for both is wrong for one of them.

### Speculative decoding is dense-only in practice here

On a MoE-heavy workload the draft model economics do not work out on this hardware. On
dense models it does: we measured 34.30 t/s with speculative decoding against 19.57 t/s
autoregressive, **+75%**, with no expert approximation and no accuracy compromise.

### Watch out for hybrid attention when benchmarking depth

Some recent models are hybrid: one we tested is 10 full-attention layers out of 40, with
30 SSM layers. Its depth curve is nearly flat (2.2x degradation versus 7x for a
conventional model). **That flatness is architecture, not backend quality.** It is a bad
baseline for attention-at-depth work and we nearly drew a wrong conclusion from it.

The same architecture is also the worst case for our KV work (see the contiguous-KV matrix,
where it is the only model with a negative cell) and the best case for dispatch-floor work
(913 sync intervals per token, 20% idle). One architectural fact, three consequences, all
easy to mistake for backend quality.

---

# Part IV: things we published and then had to retract

This section exists because it is the part of a research record that nobody writes down and
everybody needs. Each of these was believed, several were public, all were wrong.

Most of these corrections also live inline, in the entry they belong to, which is why only
one section in Part III carries a RETRACTED tag: this is the consolidated list, not a
separate set of findings. The exception is number 3, where the corrected claim about the
kernel's real bottleneck is itself the result worth keeping.

**1. "We use RGP for a real timeline and hardware counters."**
Written in the previous revision of this document as a step in "what we actually do". It had
never been done: no capture files on the box, no capture environment variable in any of 393
recorded runs, and on RADV it is not even possible for a headless workload. A reader spotted
the section as machine-written and asked how we ran it, which is how it surfaced.
Corrected in `acda56d`. The rule it produced: **before writing "we do X" in anything public,
grep for the artifact X would have left. If it left none, either say so or cut the step.**
This applies to tools and workflows as much as to figures, and it is the reason for the
`docs/METHOD.md` companion.

**2. The LDS pad win was a specification violation.**
Shipped as a measured +7%. It was a 2.4-3.1x regression on every stock driver, because the
stride it uses cannot satisfy the cooperative-load alignment requirement. Our development
driver was the thing making it survivable. Found by a downstream user's bisect. Full account
above. **When a validation rule and a measurement disagree, the measurement is describing
one driver.**

**3. "MUL_MAT_ID is dequant-bound, there is ~2.3x of headroom in the unpack."**
Held and repeated. The unpack is 0.3% of the op. The original 2.3x came from a full-graph
ablation where the ablated op emitted garbage that propagated downstream and raised sustained
clocks on other ops. The confound was documented in the original commit message and we did not
read it as disqualifying.

**4. "The contiguous-KV win is a dense-versus-MoE effect."**
It fit the first several data points. It is KV channel count, roughly
`2048 / (kv_heads * head_dim)`. **When you have a two-variable confound, the cheap model fits
first.**

**5. "Channel camping explains why wide dense models slow down with ubatch."**
The camping is real, the stride reads at 7.30 GB/s, and the buffer genuinely leaves cache at
ub2048. Halving the operand lifted the curve and left the slope alone. Falsified the same day
it was proposed, which is the correct latency for a causal claim.

**6. "The f16 B operand win is about model width, quant type is ruled out."**
Backwards. A matched-shape sweep shows q4_K never wins and q6_K/q8_0 win +4-7%. The earlier
call varied weight type inside a range of shapes where nothing was happening.

**7. "The tq3_0 K collapse is an indexing bug in the hd128 cooperative path."**
It was chaotic amplification of a real weakness in our own format. Blaming the kernel was more
comfortable than blaming the design.

**8. "wave32 costs MoE 0.2-1.2%."**
Two launches per arm, and one high launch in a two-sample arm inverted the *sign*. At six
launches per arm it is +0.2%/+0.8%, inside the spread, so the honest statement is "no
measurable effect".

**9. "The transposed-concat default costs 2.8% of speculative decode."**
Two identical configurations measured against each other, because the flag only tests for
`'0'` and `=1` is a no-op. Pure launch-to-launch drift. Retracted before it reached anyone,
which is the only reason it is a footnote rather than an entry.

**10. "The server is deadlocked."**
Three sessions, one clean fence ledger, hours of lock forensics. It was a livelock at 88% GPU
busy. Every backtrace landed in the fence wait because that is where a hot loop spends its
time.

**11. "DFlash2 gives 1.39x at 32k, so it decays with depth."**
That cell was measured on a code corpus. On prose it holds about 2x at every depth. Content,
not depth.

**12. "The bytes-aware submit gate fixes a cross-vendor crash."**
It does not. The NVIDIA control was a clean negative at 11x over the timeout, because the two
kernel drivers bound different things. A portability hazard on one driver, not a universal
crash.

---

# Part V: open questions and unexplored leads

Two different things, kept apart on purpose. The first list is where a measurement exists
and an explanation does not. The second is where neither exists yet, and where somebody
else could go first.

1. **The DRAM traffic question.** ROCm avoids the strided-access penalty that RADV pays on
   identical silicon, and four source-level explanations have been falsified. The remaining
   hypothesis is that total DRAM traffic differs, which we have not been able to measure
   directly because neither stack exposes the counter.
2. **Vulkan's f16 cooperative matmul ceiling.** 16.6-20.3 TFLOP/s against HIP's 32.4 on the
   same silicon, invariant to both m and n, and slower than our own q4_0 kernel. This is now
   the single largest unexplained number in the record and it bounds all dense prefill work.
   Occupancy, tile size, dequantisation cost, bandwidth, and B re-streaming are all
   eliminated.
3. **The f16 shared-memory pad preference.** Bank spread explains the quantised ordering and
   load width explains f32. f16 obeys neither: 17.7% apart at identical bank counts, and pad 6
   beats pad 8 despite worse alignment.
4. **The dense ubatch decline**, after nine eliminations. Vulkan's matmul rate is flat in
   ubatch, so the decline is elsewhere, and the non-matmul growth (norms +21%, elementwise
   +79%) accounts for only about half of a +1.4% GPU-busy increase.
5. **The residual speculative-against-plain fork on CPU**, at token 776 on one prompt and 280
   on another, mechanism-independent across two rollback designs and four draft trajectories.
   Prime suspect is recurrent-scan chunking during batched verify.
6. **Layer 0 runs about 2x hotter than other layers** at equal op counts, in the first trace
   capture we ever took. Probably a first-graph cold effect. Never followed up.
7. **The coopmat1 fragment layout is measured but unexploited.** The fused-dequantisation
   optimisation it enables is designed and not built.
8. **Depth decay profile for the DSv4 gather-compact path.** We have the depth-0 and 32k/64k
   endpoints. The shape between them is unmeasured.
9. **The int4 kernel's bottleneck.** 34% of ceiling from the streaming kernel, with bandwidth,
   tile size and double-buffering all falsified. Remaining suspects are occupancy from 64
   outputs per thread, shared-memory bank conflicts, and barrier stalls. Needs a real profile.

Closed since the last revision: the 10-21% decode graph overhead (structural per-token
serialisation, not a defect), and the location of the dense prefill gap (two matmuls).

## Still to explore

Leads we think are real and have not followed, with what we believe it would take. None of
these are measured, which is why they are listed separately from everything else in this
document. Where we can estimate a payoff we say so and label it a guess.

1. **A generic elementwise-chain fuser.** The dispatch floor is about 2.3 us and the SSM
   hybrids pay it 913 times per token, sitting at 80% GPU busy against a conventional MoE's
   92-95%. Per-pattern fusion is measured dead: about 0.5% each, days of work apiece, and two
   of ours came back at exactly zero wall-clock. **One mechanism that collapses arbitrary
   MUL / SIGMOID / SCALE / CPY / ADD / SILU chains into single dispatches is the only version
   worth building**, and it is upstream-relevant rather than hardware-specific. Guess, and it
   is a guess: worth close to nothing on conventional models, potentially +10-20% on hybrids.
2. **Fused dequantisation using the cooperative-matrix fragment layout.** We measured the
   `(lane, element)` to `(row, column)` mapping on this part, which is what you need to
   dequantise directly into fragment registers and delete the scratch buffer that both
   shipped KV approaches depend on. The layout is measured, the optimisation is designed,
   nobody has written it.
3. **Make the last-level cache controllable.** Residency is worth about 3x and RADV emits
   only half the hint, so there is currently no way to say "do not evict my KV cache for this
   weight stream" from Vulkan. This is a driver patch, not a llama.cpp one.
4. **Have the driver expose channel and granule geometry.** Every stride rule in this
   document is a constant we reverse-engineered for one part. A property or extension
   reporting granule size and channel count would let an application compute its own safe
   strides instead of hardcoding `gcd(stride/256, 16)` and hoping.
5. **The n=9 to 15 matmul cliff.** A 2.2-2.3x whole-pass step at the 8-to-9 boundary, because
   the vector path stops at 8 columns and the tile path is weak at roughly one token per
   expert. Needs shader work either way. It matters to any speculative decoder drafting 8 or
   more tokens, which is the direction drafters are moving.
6. **A per-shape gate for the f16 B operand.** The shipped `auto` mode keys on one hidden
   size, and forcing it on unconditionally beats `auto` above small batch, so the gate is
   leaving something on the table. A proper m/n/k sweep would settle it. The stock perf suite
   cannot do it, the graph-replay harness can.
7. **A tiled image KV cache.** Images get an address swizzle from the driver that linear
   buffers cannot get, because buffer address semantics are contractual. That would sidestep
   the channel aliasing entirely rather than working around it. Completely unexplored, and it
   may founder on how the attention kernels address memory.
8. **The int4 kernel's bottleneck**, at 34% of ceiling with bandwidth, tile size and
   double-buffering all falsified. Remaining suspects are occupancy at 64 outputs per thread,
   shared-memory bank conflicts, and barrier stalls. This one genuinely needs a profile
   before more kernel work, which is awkward given the capture situation described in Part II.

**And some things that look like leads and are not**, recorded so nobody funds them:

- A Vulkan int8 cooperative matmul shader. On this part int8 matches fp16 rate rather than
  beating it, so the whole project is worth about 4%, not the ~18% that ROCm's MMQ advantage
  suggests.
- Cooperative matrix 2 at workgroup scope on RADV. Emulated through shared memory, 6.8x
  slower, 2608 failing configurations.
- Copying ROCm's dequantise-then-GEMM strategy. Its destination on Vulkan is slower than
  where the fused quantised kernels already sit.
- Cheapening the K-quant unpack in the expert matmul. It is 0.3% of the op.

## The one thing almost anyone reading this could do

**Run the ablations on hardware that is not ours.**

Four changes in this document are measured, verified, perplexity-clean, and stuck: the dense
wave32 retile, the shared-memory pad, the cooperative flash-attention fragment hoist, and the
small-batch attention routing gate. Every one of them is blocked on the same thing, which is
not a technical problem: we have one AMD APU and one NVIDIA card, and these paths are shared
with NVIDIA before Blackwell, with Intel, and with AMD's Windows driver.

The fragment hoist is the clearest case. It is 8 insertions in one file, unconditional, no
gate, costs nothing in registers or shared memory, and is a plain bug rather than a tuning
preference. It should be upstreamable on sight. What stops it is that its benefit depends on
the driver unrolling a loop that the shader compiler does not unroll, and we cannot check
whether that holds anywhere except here.

A before-and-after benchmark on a different vendor's card is an afternoon's work and would
unblock more of this list than any amount of further effort on our side.

---

# Appendix: quick reference

Diagnose an unexplained slowdown, in order:

```bash
# 0. Is the build what you think it is? Check EVERY time.
./bin/llama-bench -m any.gguf -p 8 -n 0 2>&1 | grep -E 'Vulkan0|int dot|matrix cores'

# 1. Is it even running on the GPU you think?
GGML_SCHED_DEBUG=2 ./bin/llama-bench -v -m model.gguf -p 512 -n 1 2>&1 | head -60
#    watch: the split count, and any node saying CPU that should say Vulkan0

# 2. Which op dominates, and at what shape?
GGML_VK_PERF_LOGGER=1 GGML_VK_PERF_SHAPES=1 GGML_VK_PERF_LOGGER_FREQUENCY=20 \
  ./bin/llama-bench -m model.gguf -p 4096 2>&1 | tee perf.log
#    sanity: if a per-op rate exceeds the roofline, the instrument is wrong

# 3. Do the per-op times explain wall-clock, or is there an overlap story?
GGML_VK_PERF_LOGGER=1 GGML_VK_PERF_LOGGER_CONCURRENT=1 \
  ./bin/llama-bench -m model.gguf -p 4096

# 4. Is a specific feature responsible? Bisect by ablation.
GGML_VK_DISABLE_FUSION=1  ./bin/llama-bench -m model.gguf -p 4096
GGML_VK_DISABLE_COOPMAT=1 ./bin/llama-bench -m model.gguf -p 4096
GGML_VK_DISABLE_MMVQ=1    ./bin/llama-bench -m model.gguf -p 4096

# 5. Register and LDS pressure on the hot shader. Free, static, no GPU time.
GGML_VK_PIPELINE_STATS=flash_attn ./bin/llama-bench -m model.gguf -p 4096

# 6. Per-dispatch timeline. Needs the `vk-perf-trace` branch of the fork, not stock.
GGML_VK_PERF_TRACE=trace.json GGML_VK_PERF_TRACE_SKIP=2 GGML_VK_PERF_TRACE_COUNT=3 \
  ./bin/llama-bench -m model.gguf -p 2048
python3 tools/vktrace.py summary trace.json
python3 tools/vktrace.py gaps    trace.json     # host-code vs in-graph bubbles
#    Open trace.json in ui.perfetto.dev for the timeline view.

# 7. Isolate the op, no model in the way
./bin/test-backend-ops perf -o FLASH_ATTN_EXT -b Vulkan0

# 8. Replay a real graph's op set standalone, on either backend
./bin/test-export-graph-ops -m model.gguf -b 2048 -ub 2048 -o ops.txt
./bin/test-backend-ops perf --test-file ops.txt -b Vulkan0
./bin/test-backend-ops perf --test-file ops.txt -b ROCm0

# 9. Correctness, in increasing order of trustworthiness
./bin/test-backend-ops -o FLASH_ATTN_EXT -b Vulkan0
./bin/test-backend-ops -o MUL_MAT        -b Vulkan0   # any stride/layout change
./bin/llama-perplexity -m model.gguf -f wiki.test.raw          # vs the -ngl 0 run
#    then KL divergence vs CPU when you need "different" vs "worse"

# 10. Label dispatches for an external capture. NOTE: on RADV headless there is no
#     capture to take, SQTT is gated on swapchain present. See the RGP section.
GGML_VK_DEBUG_MARKERS=1 ./bin/llama-bench -m model.gguf -p 4096
```

Enumerate every lever your build actually has:

```bash
grep -oE 'getenv\("[A-Z0-9_]+"\)' ggml/src/ggml-vulkan/ggml-vulkan.cpp | sort -u
```

Is a serving stall a deadlock or a livelock? Take a time series, not a snapshot:

```bash
for i in $(seq 60); do
  printf '%s busy=%s out=%s\n' "$(date +%T)" \
    "$(cat /sys/class/drm/card*/device/gpu_busy_percent)" \
    "$(stat -c %s output.txt)"
  grep drm-engine /proc/$PID/fdinfo/* 2>/dev/null | head -3
  sleep 2
done
# busy + advancing engine time + frozen output = LIVELOCK, go to app-level tracing
# all idle + a fence that never signals    = a real wedge, go to lock forensics
```

Channel-aliasing check for any strided buffer on this memory system:

```
granules = row_stride_bytes / 256
channels_used = 16 / gcd(granules, 16)
# channels_used == 16 is fine. 2 or 1 is a 10-30x read penalty.
# f16 camps when the row dimension is a multiple of 256 (worst at 2048)
# f32 camps when the row dimension is a multiple of 128 (worst at 1024)
# quantised rows are fractional in granules and de-alias for free
# minimum effective pad is 16 bytes; 8 bytes computes WRONG ANSWERS in mul_mm
```

## The rules that produced most of the above

1. **Verify engagement from the executed graph, not from the gate.** A configuration flag
   saying "on" is not evidence that code ran. Check the graph, or put a log line in the path.
2. **Serialise your benchmarks, and count compiles as benchmarks.** Contention does not add
   noise, it fabricates results, including physically impossible ones. A throttled build still
   costs 7%, because what it steals is memory bandwidth, not CPU priority.
3. **`-r N` is not an error bar.** Three independent launches per arm, counterbalanced A-B-B-A,
   with a throwaway warmup first. A single launch has produced both a fake regression and a
   fake win in this record.
4. **Keep raw artifacts for every run.** If you cannot reconstruct a number from raw output,
   you do not know it. This is also the only thing that lets you re-audit an old claim when a
   new result contradicts it, which happens constantly.
5. **`test-backend-ops` passing is not correctness.** Gate on full-model perplexity against a
   CPU reference, and on KL divergence when you need to distinguish different from worse. Add
   the awkward type's case *before* you generalise.
6. **When you cannot explain a mechanism, leave llama.cpp.** Build the microbenchmark, or
   replay the op set standalone. Several of these findings were unreachable from inside the
   application and took an afternoon once isolated.
7. **A model that fits your numbers is not a model that is right.** The MoE bandwidth story,
   the int4 roofline, and the HIP decode bandwidth model all fitted well and were all wrong.
   Design the measurement that would *discriminate*, not the one that would confirm.
8. **Name the part every claim was measured on.** We have one APU and one discrete card.
   Unscoped statements are for code structure and arithmetic, not for performance.
9. **Publish the negatives.** They are most of the value here, they are what stops the next
   person building the wrong thing, and they are the only part of a record that ages well.
