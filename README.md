# Strix Halo llama.cpp toolbox (FA + MoE-prefill fixes)

A ready-to-run llama.cpp for AMD Strix Halo (Ryzen AI Max+ 395 / Radeon 8060S / gfx1151),
tuned for **long-context, quantized-KV** workloads. It bundles a set of Flash-Attention and
MoE-prefill fixes plus a current GPU driver, so quantized KV cache is fast instead of a penalty.

The measurements behind these fixes (matrices, methodology, raw data) live in the companion
[evidence pack](benchmarks/BENCHMARKS.md).

## Speedups at a glance

**v0.6.4 payload vs stock master, same box, same session** (`amd_iommu=off`, pp512 / tg32 t/s, `-b 512 -ub 512`,
`-r 3`, captured 2026-08-18 between 05:28 and 06:04 UTC). Baseline is stock upstream `9f0d017` at f16 KV, the
commit this release merged; fixed is the released v0.6.4 payload (`baf6360b` on `strix-halo-vulkan`). Both arms
were built with the same pinned glslc and run against the same pinned Mesa, so only llama.cpp differs. Every cell
traces to a raw run under [`benchmarks/results/glance-20260818/`](benchmarks/results/glance-20260818/).

| Model (arch) | KV | Prefill d0 | Prefill deep | Decode d0 | Decode deep |
|---|---|---:|---:|---:|---:|
| Qwen3-Coder-30B-A3B-Instruct (Q6_K_XL, hd128 MoE) | f16 *stock* | 1161 | 72 | 69 | 23 |
| | f16 | 1242 = +7% | **235 = 3.26x** | 69 = +1% | 23 = +0% |
| | q8_0 | 1230 = +6% | **233 = 3.24x** | 69 = +0% | **32 = +41%** |
| Qwen3.6-35B-A3B (Q4_K_XL, hd256 MoE) | f16 *stock* | 1125 | 492 | 62 | 43 |
| | f16 | 1507 = **+34%** | 618 = **+26%** | 62 = -0% | 43 = -0% |
| | q8_0 | 1524 = **+35%** | 616 = **+25%** | 62 = -1% | 50 = +14% |
| Qwen2.5-7B-Instruct (Q4_K_M, hd128 dense) | f16 *stock* | 1350 | 358 | 48 | 34 |
| | f16 | 1512 = **+12%** | **663 = 1.85x** | 48 = +0% | 34 = -0% |
| | q8_0 | 1505 = **+11%** | **660 = 1.84x** | 47 = -1% | 38 = +14% |

"deep" is **d65536** for the two MoE models and **d32768** for Qwen2.5-7B, whose trained context is 32768
(`qwen2.context_length`, no rope scaling). The 7B does keep scaling past that, 2.31x at d65536 on the
2026-08-10 capture, but that is outside the context the model was trained for, so it is not quoted beside two
models measured inside theirs. This capture takes d0 and the deep point only; full curves for all five depths
are in [benchmarks/BENCHMARKS.md](benchmarks/BENCHMARKS.md), from the 2026-08-10 capture.

All three stock arms reproduce their 2026-08-10 values within 0.5% on every cell, a week of upstream apart, so
the movement in the fixed rows is this stack changing and not the baseline or the box drifting.

**Depth scaling is a head-dim effect, not a dense-vs-MoE one.** Both hd128 models climb hard with depth (Coder
1.07x at d0 rising to 3.26x at 64k; the dense 7B 1.12x rising to 1.85x at 32k) while the hd256 model is flat to
slightly declining (1.34x at d0, 1.26x at 64k). One of those hd128 models is MoE and one is dense, so what tracks
the depth win is KV channel count, not sparsity. The hd256 model never collapsed in the first place, so there is
no collapse to recover.

**What moved since the 2026-08-10 capture is the shallow end.** The 35B went +22% to +34% at d0 and the dense 7B
+1% to +12%, while Coder-30B barely moved at d0 (+6% to +7%). That is the v0.6.4 matmul work: the wave32 retile
and LDS pad tune apply to the quantised *dense* coopmat pipelines, which is most of the 7B's prefill and much of
the 35B's, whereas Coder-30B-A3B pushes its GEMM through `mul_mat_id`, which already ran wave32. The 35B also
collects the transposed-concat default, a fix derived on exactly its delta-net conv-state path. Those
attributions come from the per-commit isolations in the release notes, not from this table, which measures the
whole stack at once.

**Decode is untouched by the Vulkan fixes, by construction.** Across all three models, fixed-f16 decode matches
stock-f16 decode within 1% at every depth. So the decode column's q8 win is the KV *type*, not the patches:
+41% on Coder, +14% on the 35B, +14% on the dense 7B at their deep points.

**Read the prefill rows as a build comparison, not a KV-type one.** f16 and q8 land within 1.2% of each
other at every depth on every model, so on this stack **KV quantization is no longer a prefill-speed
decision**. Keep `-ctk q8_0 -ctv q8_0` anyway: it still buys KV memory and the decode throughput at depth
shown above. One caveat the earlier numbers missed: q8 costs a few percent of *shallow* prefill (-1.0% at
d0 on Coder, and up to -3.1% at the larger production ubatch), and that cost falls to zero by 64k. See
[f16 catches up](benchmarks/BENCHMARKS.md#f16-catches-up-the-kv-contig-fix-2026-07-28-build-74434c3).

**What each fix contributes:**

| Fix / knob | Backend | Contribution |
|---|---|---|
| FA dequant-once (#25494) | Vulkan | **the bulk of the 3.26x**: dequantize q8 KV once in the FA kernel (prefill). Was measured at 2.66x on the 2026-07-25 build; the headline rose to 3.26x as the FA prefill stack landed on top, against an unchanged stock baseline (72 t/s @64k then and now) |
| all-quant transpose | Vulkan | extends it to q4/q5 KV (q4 lands the same 2.64x) |
| f16 KV contiguize | Vulkan | **2.63x** f16 prefill at depth (Coder-30B pp512 @64k: 70.6 to 190.0 vs master `8161641`). f16 KV only, prefill only, on by default (`GGML_VK_FA_KV_CONTIG=0` opts out). It contributes nothing to the q8 headline above; it is what makes the f16 line match it. |
| FA prefill stack (P-hoist / `Psh` relayout / wave32) | Vulkan | +2.8 to +3.1% at d0 rising to **+21.6 to +22.0%** at d32768 on Coder-30B, consistent across f16/q8/q4 KV, decode unchanged. P-hoist alone +6.9/+8.1/+9.2% at d8k/16k/32k; the wave32 pin adds a further +2.7 to +11.9% on top, rising with depth; the `Psh` relayout measures ~0 on its own and rides along as the enabler for the vectorized GEMM2 A load. |
| dense wave32 retile (v0.6.4) | Vulkan | quantised *dense* coopmat pipelines run at wave32 on RDNA3.x, where WMMA is wave32-native. Standalone MUL_MAT at the dense FFN shapes: q6_K +5.2 to +10.8%, q8_0 +5.4 to +8.4%, q4_K +0.7 to +9.1%; the float paths are bandwidth-bound and left alone. PPL bit-identical. |
| coopmat LDS pad tune (v0.6.4) | Vulkan | per-path shared-memory pad on RADV: pad 2 reaches 16 of 32 banks against 8 for the old constant, +13% mean on the quantised path in a standalone sweep (q4_0 +32%, q8_0 +22%, q4_K +10%, q6_K +1%). Largest where the dequant is cheapest, the complement of what wave32 helps. Together with the retile: **+11.0% / +7.7%** pp2048 at ub256 / ub2048 on Qwen3-32B, payload A/B against v0.6.2. |
| transposed concat (v0.6.4) | Vulkan | default-on tiled transpose for the delta-net conv-state concat, which otherwise walks src1 at a stride that lands every read on one of 16 memory channels (13.7 GB/s against 138.9). +7.2% pp2048 at ub2048 on Qwen3.8-27B, +0.4% at ub256. Delta-net models only. |
| mmid row-list prepass | Vulkan | **+8.4%** MoE prefill on the 2026-07-14 window (q8 KV, base `b805834`); the current in-repo isolation on f16 measures +11.2% at d0 / +8.2% at d16384 (`results/finalize/rowlists_{off,on}.md`). Model-dependent; ~1–2% on Coder at depth. |
| mmid BM64 | Vulkan | +1.3% (13.5 t/s against ±3.5 — near noise). The scale-cache that used to sit here is disabled: it was obsoleted by later tile changes and regressed. |
| mmid WAVE32 / F16B | Vulkan | marginal. WAVE32 +2.8%, but its mechanism caps out ~1.7%, so treat it as noise-adjacent. F16B is quoted at +2.4% from an unvendored model; the only in-repo isolation (Coder-30B) measures +1.2% at d0. On by default. |
| mmid TILE16 / INT | Vulkan | −3.8% / −8% (documented negatives, never enabled). The −8% arm is INT+SMALLN and its control carried BM64 while neither INT arm did, so part of that loss is the missing BM64; INT alone is −7.9%. |
| HIP tile-dequant KV | HIP/ROCm | **+128% / +232%** decode @32k / 64k (beats f16) |
| `amd_iommu=off` | host | +1.0–7.3% prefill, decode within noise (optional host tuning) |

Honest read: on Coder the **q8 prefill headline is almost entirely FA dequant-once**, with the 2026-07-30 FA
stack adding roughly a fifth more at depth. The f16 contiguize is a win of comparable size on the f16 line,
which is why KV type is no longer a prefill-speed decision here. `rowlists` is the
real MoE-prefill fix (larger on other shapes); the rest are small waste-removals and the knob-tweaks are
marginal-to-negative — as expected on a bandwidth-bound kernel. The v0.6.4 matmul rows are the exception to
that last clause: they are the first knob-level changes here worth double digits, and they act at *every*
depth rather than only where FA collapses, which is why the shallow end of the table moved. Full per-depth
matrices + charts are below and in [benchmarks/BENCHMARKS.md](benchmarks/BENCHMARKS.md).

## What's inside

- **`vulkan/`** self-contained Vulkan/RADV build (recommended default backend on this hardware).
  Bundles **Mesa 26.3.0-devel RADV** + **libdrm 2.4.134**, so it does not use or need the host
  Mesa. Runs directly on the host with just the Vulkan loader and `/dev/dri`.
- **`hip/`** ROCm/HIP build carrying the quantized-KV decode fix. Needs the ROCm runtime, so it
  is built as a container image (`Dockerfile.hip`). **Not published**: no `:hip` tag exists on
  ghcr and `hip/bin` is git-ignored, so this one is build-it-yourself today — see below.

## Getting the binaries

Three ways — the first two need **no build and no Docker**:

**1. Portable tarball (recommended for a quick start).** Self-contained — bundles the RADV driver, so it
doesn't use the host's Mesa; only needs `libvulkan1` + read access to `/dev/dri`:
```
curl -L https://github.com/Nathanw1014/strix-halo-llamacpp/releases/download/v0.2/strix-halo-llamacpp-vulkan-portable.tar.gz | tar xz
./vulkan/llama-server -m /path/to/MODEL.gguf -ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 --host 0.0.0.0
```

**2. Container.** `docker pull ghcr.io/nathanw1014/strix-halo-llamacpp:vulkan` (see [Quickstart](#quickstart)).

**3. Build from source.** Build the **`strix-halo-vulkan`** branch of the
[fork](https://github.com/Nathanw1014/llama.cpp) (the complete Vulkan stack) — see **[BUILD.md](BUILD.md)**
for the exact toolchain; `build-from-source.sh` then assembles the built binaries + driver into this layout.

The tarball (31 MB) ships via GitHub Releases and the Vulkan container image via ghcr; neither is
tracked in git. The HIP image is not published — build it locally if you need the ROCm decode fix.

To check a tarball is really using the bundled GPU driver rather than falling back to CPU, run
`./vulkan/llama-bench -m MODEL.gguf -ngl 99 -p 128 -n 8 -r 1` and confirm the `backend` column
says `Vulkan` (not `CPU`) and that it prints a `ggml_vulkan: 0 = ...RADV STRIX_HALO` line.
**The v0.1 tarball fails this check** — its ICD manifest was missing a required field, so the
bundled driver was skipped and it ran on CPU. Use v0.2 or later.

**Which route gets which fixes.** All three routes are cut from the same `strix-halo-vulkan` tip,
so they carry the same fixes. The benchmark tables further down were measured on an earlier build
(`63f88cc`, 2026-07-23) and therefore predate the f16 KV contiguize pass and the 2026-07-30 FA
stack: they understate the current artifacts rather than overstate them.

## The fixes

- **Vulkan: dequantize KV once in the FA kernel (prefill).** Quantized KV was re-dequantized on
  every FA pass; now it is dequantized once into a transposed scratch and reused. This is what
  makes quantized-KV **prefill** fast at depth (up to 2.66x f16 on head-dim-128 models). The same
  path covers q4_0/q4_1/q5_0/q5_1 and iq4_nl, so q4 KV lands the same win at 1/4 the memory.
- **Vulkan: contiguize strided f16 KV before FA (prefill).** The f16 counterpart of the
  dequant-once transpose. The KV cache stores heads interleaved per token, so f16 K/V reached the
  coopmat1 kernel strided and a 16x16 tile touched 16 cache lines instead of 4; quantized KV never
  paid this, because the dequant scratch already writes per-head-contiguous rows. Routing strided
  f16 K/V through the same scratch with a pure copy shader takes Coder-30B f16 pp512 @64k from
  70.6 to 190.0 t/s (2.69x vs the published post baseline, 2.63x vs current master `8161641`).
  Prefill only, decode untouched. On by default; `GGML_VK_FA_KV_CONTIG=0` opts out.
- **Vulkan: coopmat1 FA prefill stack (2026-07-30).** Three changes: hoist the GEMM2 P
  `coopMatLoad` out of the `hsv_tile` loop, store `Psh` query-major so the GEMM2 A load vectorizes,
  and pin a 32-wide subgroup where narrowing is free. Combined, +2.8 to +3.1% at d0 rising to
  +21.6 to +22.0% at d32768 on Coder-30B (pp2048/ub2048), consistent across f16/q8_0/q4_0 KV, with
  decode unchanged. The subgroup pin is the `GGML_VK_FA_WAVE32` knob (see Recommended flags). From v0.7.4 it is off by default: it reorders the FA reduction and moves about 2% of greedy tokens on dense models relative to upstream for about 1% prefill; set `GGML_VK_FA_WAVE32=1` to opt back in.
- **Vulkan: route non-native FA K/V types through the dequant-once path.** `iq4_nl` has no native
  FA shader on the scalar/coopmat1 paths, and outside the dequant-once path the shader read
  garbage. `ggml_vk_fa_kv_native()` is now the single source of truth for native K/V types and
  `supports_op` mirrors every hard gate, so admission and dispatch always agree. Correctness only,
  no perf claim: FLASH_ATTN_EXT passes 5105/5105, including all 340 iq4_nl cases.
- **Vulkan: mmid row-list prepass (MoE prefill).** Removes the redundant per-workgroup expert-ID
  scan in `MUL_MAT_ID`. Model-dependent: large on some MoEs, small on others. The q5_K/q4_K scale
  cache that used to sit alongside it is now disabled: later tile changes obsoleted it and it had
  regressed to -4% at pp512/ub512 and -20% at pp2048/ub2048 on Q5_K-weight MoE.
- **HIP: dequantize KV on load in the tile FA kernel (decode).** Routes quantized decode through
  the tile kernel (dequant once, batched across GQA heads) instead of the vec kernel that repeats
  the dequant per query head. Fixes quantized-KV **decode** at depth on ROCm.

Two robustness changes ride along on the same branch: FA now falls back instead of aborting when
the dequant scratch would exceed `maxStorageBufferRange` (`e21d01e`), and on discrete GPUs the
scratch is gated on device-local capacity, with `GGML_VK_FA_DEQUANT_RESERVE_MB` to override the
1 GiB reserve (`8a2c6b2`; a no-op on UMA parts, which includes gfx1151).

## Branches (upstreaming)

Five of the fixes — plus one community-contributed feature — are genuine llama.cpp upstream
candidates: each is kept on its own clean, minimal branch so it can be reviewed and merged on
its own, independent of this toolbox.

| Branch | Fix | Upstream status |
|---|---|---|
| [`vulkan-coopmat1-fa-dequant-transpose`](https://github.com/Nathanw1014/llama.cpp/tree/vulkan-coopmat1-fa-dequant-transpose) | Vulkan FA dequant-once, q8 KV (prefill) | **in-flight, PR #25494** |
| [`vulkan-fa-f16-kv-contig`](https://github.com/Nathanw1014/llama.cpp/tree/vulkan-fa-f16-kv-contig) | Vulkan f16 KV contiguize before FA (prefill) | ready; stacked on the #25494 branch since it extends that scratch infra, so queued behind it |
| [`vulkan-mmid-rowlists`](https://github.com/Nathanw1014/llama.cpp/tree/vulkan-mmid-rowlists) | mmid row-list prepass (MoE prefill) | ready; clean cherry-pick onto master |
| [`feat/fa-p-hoist`](https://github.com/Nathanw1014/llama.cpp/tree/feat/fa-p-hoist) | FA GEMM2 P-load hoist (prefill) | ready, wants a second vendor first — it is unconditional and benefits every KHR-coopmat device, but the win depends on the driver unrolling the loop, and cm1 is shared with NVIDIA pre-Blackwell, Intel and AMD-Windows |
| [`fa-tile-dequant-on-load`](https://github.com/Nathanw1014/llama.cpp/tree/fa-tile-dequant-on-load) | HIP tile-dequant (quantized-KV decode) | ready; PR not yet opened |
| [`vulkan-dsv4-lightning-indexer`](https://github.com/Nathanw1014/llama.cpp/tree/vulkan-dsv4-lightning-indexer) | DeepSeek V4: Vulkan lightning-indexer kernels (scalar + coopmat prefill + decode) and indexed sparse FA — **contributed by Gaetan Puleo**, hardened + parity tests added here | ready; PR not yet opened |

**Not offered upstream, though they ship here.** The combined branch
[`strix-halo-vulkan`](https://github.com/Nathanw1014/llama.cpp/tree/strix-halo-vulkan) merges the
six above onto upstream master `8161641` (2026-07-28) plus four changes that are deliberately
local:

- `feat/fa-wave32-rule` (`dfb619c`) — the FA subgroup pin. There is real precedent for it (the
  sibling scalar path already does AMD-specific wave selection) and it would help every wave64
  AMD part, but it needs its env gate removed, an assert relocated that can fire from device
  properties alone on a subgroup-128/256 device, and confirmation on a second AMD part.
- `feat/fa-psh-relayout` (`40f85eb`) — **on hold.** No measured standalone benefit; it exists to
  enable the hoist, and it steers into RADV's only alignment-asserting coopmat path.
- the non-native K/V routing fix (`8929240`) — correct for this stack, but upstream master
  `8161641` reworked the same area (#24585) and the two need reconciling first.
- the mmid scale-cache disable (`bfc1eb4`) — a revert of a local change; nothing to upstream.

`test/fa-perf-probes` is a benchmark-only branch (`test-backend-ops perf` cases used to measure
the FA work). It is not a fix and is not an upstream candidate.

Full inventory (combined + experimental branches) and the honest **mmid fixes vs config-tweaks**
taxonomy (one real mmid fix, the rest marginal knobs): **[BRANCHES.md](BRANCHES.md)**.

## Quickstart

### Portable (Vulkan, no container)
```
./vulkan/llama-server -m /path/to/MODEL.gguf -ngl 99 -fa 1 --host 0.0.0.0 --port 8080
./vulkan/llama-bench  -m /path/to/MODEL.gguf -ngl 99 -fa 1 -p 512 -n 32 -d 0,32768
```
Requires the Vulkan loader (`libvulkan1`) and read access to `/dev/dri`. Everything else
(driver, libdrm, ggml libs) is bundled.

### Container (Vulkan)
```
docker build -t strix-halo-llamacpp:vulkan -f Dockerfile.vulkan .
docker run --rm --device /dev/dri -v /path/to/models:/models -p 8080:8080 \
  strix-halo-llamacpp:vulkan llama-server -m /models/MODEL.gguf -ngl 99 -fa 1 --host 0.0.0.0
```
No baked entrypoint: `docker run -it` (no command) gives an interactive shell with the
binaries on PATH — the toolbox workflow.

### Container (HIP / ROCm, decode fix)

⚠️ **There is no published HIP image.** ghcr carries only the `vulkan` tag, and `hip/bin` is
git-ignored, so `docker build -f Dockerfile.hip` on a fresh clone fails with
`"/hip/bin": not found`. To use the HIP decode fix you have to build it: check out
`fa-tile-dequant-on-load`, build it in a ROCm image targeting gfx1151, populate the payload with
`HIP_BUILD=<build-dir> ./build-from-source.sh` (see [BUILD.md](BUILD.md) §4), and only then:

```
docker build -t strix-halo-llamacpp:hip -f Dockerfile.hip .
docker run --rm --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render --security-opt seccomp=unconfined \
  -v /path/to/models:/models -p 8080:8080 \
  strix-halo-llamacpp:hip llama-server -m /models/MODEL.gguf -ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 --host 0.0.0.0
```

### distrobox / toolbox (interactive)

The images carry the `com.github.containers.toolbox=true` label and a toolbox-friendly base, so they
drop into the same workflow as the other Strix Halo toolboxes. GPU (`/dev/dri`) and your home dir are
passed through automatically; the binaries are on `PATH` and the wrapper sets the driver + mmid env, so
they "just work" from the shell.

**distrobox** (podman or docker backend):
```
distrobox create --name strix-fa --image ghcr.io/nathanw1014/strix-halo-llamacpp:vulkan
distrobox enter strix-fa
# then, inside:
llama-server -m ~/models/MODEL.gguf -ngl 99 -fa 1 -ctk q4_0 -ctv q4_0 --host 0.0.0.0
llama-bench  -m ~/models/MODEL.gguf -ngl 99 -fa 1 -p 512 -n 32 -d 0,32768
```

**toolbox** (Fedora / immutable distros):
```
toolbox create strix-fa --image ghcr.io/nathanw1014/strix-halo-llamacpp:vulkan
toolbox enter strix-fa
llama-server -m ~/models/MODEL.gguf -ngl 99 -fa 1 --host 0.0.0.0
```

The HIP image works the same way once you have built it locally (it additionally needs `/dev/kfd`,
which distrobox/toolbox pass through along with `/dev/dri`) — but there is no `:hip` tag on ghcr to
pull, so `distrobox create --image ghcr.io/nathanw1014/strix-halo-llamacpp:hip` will fail. Only the
Vulkan image is published.

## Recommended flags

- `-fa 1` always (Flash-Attention on).
- **Prefill-heavy work: raise the ubatch. Which value is model-specific.**
  The default (512) leaves prefill on the table on MoE models: a MoE touches essentially every
  expert once the ubatch exceeds ~16 tokens, so the whole expert tensor streams regardless of
  batch size, and arithmetic intensity keeps rising with ubatch until it reaches this machine's
  compute/bandwidth balance point (~230 FLOP/byte).
  - **Coder-30B-class MoE (hd128, small-expert A3B): `-b 2048 -ub 2048`.** This is what the
    maintainer's own server runs. Isolated at the same prompt length, ub2048 is worth **+39%**
    over ub512 at d0 (`pp2048` 1170 -> 1631). Going ub512 -> ub1024 alone is +9.9% at d0
    (1482 -> 1629 on UD-Q4_K_XL) and +4.1% at d32768, so most of the win is in the last step.
  - **Qwen3.6-35B-class (hd256 hybrid): `-b 1024 -ub 1024`.** ub2048 measures **-12% at d0** on
    that model (1180 -> 1035), so it is not a blanket win. ub2048 only pays there for
    deep-context work.
  - **DeepSeek-V4-Flash (284B-A13B, 128GB boxes): `-ub 1024`.** Community-measured: pp4096
    146.6 -> 184.3 (**+26%**) over the 512 default at d0. Decode is unaffected (single-token
    graphs), so this is pure prefill upside.
  ⚠️ Caveat: larger ubatch raises per-batch memory (+1.1 GiB on Coder-30B going ub1024 -> ub2048).
  On a 64 GB box with other GPU work resident (e.g. ComfyUI) that pressure is real, though this
  repo has no measurement of it — every benchmark here stops the co-tenants first. Keep `ub512`
  if the box is shared. Decode is unaffected either way (it is bandwidth-bound, not batch-bound).
- **Long context: use q4_0 KV** (`-ctk q4_0 -ctv q4_0`). It is the smallest footprint (about 1/4
  of f16) and the fastest at depth for **decode** (33.3 vs 22.5 t/s f16 @64k on Coder-30B). It is
  not a prefill win any more: with these fixes all three KV types land within ~2.7% at every depth,
  so pick KV type on memory and decode, not prefill. Use `q8_0` if
  you want a little more KV quality; use `f16` only for short prompts where it does not matter.
- **mmid** MoE-prefill flags are ON by default in the Vulkan wrapper
  (`GGML_VK_MMID_ROWLISTS/SMALLN/BM64/WAVE32`). To turn them off, set any to `0` before running.
  `GGML_VK_MMID_F16B` is **on by default** (this is a squeeze-everything build; it is safe and gives
  a small gain on some MoEs like the 35B, neutral elsewhere). Disable it with `GGML_VK_MMID_F16B=0`.
  An earlier abort on the experimental `Q2_0` type has been fixed (it now falls back to the standard path).

## Benchmarks

Measured on this box (Radeon 8060S / gfx1151), Mesa 26.3.0-devel + this build, `-fa 1`, r=3, services
stopped, **`amd_iommu=off`** (see host tuning). "fixes" = dequant-once + q4 transpose + the mmid stack
(the toolbox default). Start/end f16 canaries agreed to within 0.93% on prefill and 3.86% on decode, so no
meaningful thermal drift.

![Qwen3-Coder-30B-A3B prefill: the FA fixes are 2.66x faster than stock master at 64k](graphs/01_coder30b_prefill_2.66x.png)

> The 2.66x is the **build** (stock master `5c3a586` vs the FA fixes `63f88cc`), not the KV
> type. Separately, on the 2026-07-28 contiguize build all three KV types land within 2.7% of
> each other at every depth (worst case d4096; 0.7% at 64k), so KV quantization is no longer a
> prefill-speed decision on this stack. Those are two different builds: `63f88cc` predates the
> f16 contiguize pass and has no f16 arm.

**Qwen3-Coder-30B-A3B (head-dim 128), prefill pp512, stock f16 vs fixes + q8 KV:**

| context | stock f16 | fixes + q8 KV | gain |
|---:|---:|---:|---:|
| 0 | 1163 | 1218 | +5% |
| 16k | 377 | 505 | +34% |
| 32k | 205 | 323 | +57% |
| 64k | 71.9 | 191 | **2.66x** |

(q4 KV lands the same win at **1/4** the KV memory — 190 t/s / 2.64x at 64k — so use q4 for maximum context,
q8 for maximum KV quality. We reference q8 here: it's the shipping PR's scope and the higher-quality cache.)

![Qwen3.6-35B-A3B Q4_K_XL, same weights: quant KV vs f16 on prefill and decode, against the best public f16](graphs/02_35b_q4kxl_samequant.png)

**Qwen3.6-35B-A3B (head-dim 256, UD-Q4_K_XL, same weights), at 64k:** q8 KV gives **+9% prefill and +15%
decode** vs stock f16 at **1/2 the KV memory** (q4 gives +18% decode at 1/4). Our stock-f16 decode (42.7 t/s
@64k) matches the best public f16 numbers (kyuz0, 43.2) on the same model, so the quant-KV win is real, not a
baseline artifact.

![Decode throughput vs depth: quantized KV also generates faster than f16 at depth, both models](graphs/03_decode_both.png)

**How to read it:** the Flash-Attention dequant-once fix removes the quantized-KV prefill penalty and grows
with depth (dramatic at head-dim 128, parity-restoring at head-dim 256). The mmid row-list fix adds
MoE-prefill speedup on top (model-dependent). Decode: quantized KV is both smaller and faster at depth.
Net guidance: use `-ctk q4_0 -ctv q4_0` for long context.

![Dense model Qwen2.5-7B: q8 KV + fixes vs stock f16, prefill and decode at depth](graphs/04_dense7b_f16_vs_q8.png)

**Dense models too:** the FA dequant-once fix isn't MoE-specific. On dense Qwen2.5-7B (head-dim 128), q8 KV +
fixes gives **+91% prefill and +22% decode at 64k** vs stock f16 — same mechanism, same win.

Full matrices, raw `llama-bench` output, methodology, and correctness gates are in
[benchmarks/BENCHMARKS.md](benchmarks/BENCHMARKS.md); the per-fix branch inventory and the honest
fixes-vs-tweaks taxonomy are in [BRANCHES.md](BRANCHES.md).

## Toolchain

- GPU driver: Mesa 26.3.0-devel (RADV, `git-d18d598e`), libdrm 2.4.134, shaderc v2026.3-dev
  (`49a8724d`).
- llama.cpp: fork branch `strix-halo-vulkan`, rebased on upstream master `8161641` (2026-07-28);
  the tarball and images are cut from its tip. The benchmark figures on this page were taken on
  the earlier `63f88cc` (2026-07-23), so they predate the f16 contiguize pass and the 2026-07-30
  FA stack and understate the current artifacts rather than overstate them. HIP build on ROCm 7.2.4.

## Host tuning (optional)

- **`amd_iommu=off`** (kernel boot parameter): removes IOMMU address-translation overhead on GPU memory
  access, which can help on this bandwidth-bound hardware. This is host kernel config, not part of the
  toolbox. To try it: reboot, at the GRUB menu press `e`, append `amd_iommu=off` to the `linux` line,
  `Ctrl-X` (one-shot); or add it to `GRUB_CMDLINE_LINUX_DEFAULT` and `sudo update-grub` to persist. It is
  a security tradeoff (the IOMMU provides DMA isolation), so verify the effect on your box first. **Measured
  here (off vs on, same build, 10 arms): +1.0% to +7.3% prefill (larger on the 35B MoE than on
  Coder-30B), decode within noise at -2.4% to +3.9%** — a modest tuning gain, not the larger figures sometimes cited. The benchmark numbers above are
  taken with it **off**, so leaving the IOMMU on costs you roughly that few percent, nothing more.

## Running Qwen3.8-Flash-Next

The engram / PLE table (`per_layer_token_embd`) is ~95 GiB at f16. It **cannot** be offloaded and
is not meant to be: it is memory-mapped and read a few KB per token. Everything below assumes it
stays mapped on the host.

### Mandatory flags

```
--load-mode mmap --no-host --no-repack --fit off
```

`--load-mode auto` silently disables mmap when a Vulkan device is present and then tries to
allocate the whole table, which is a real second copy rather than a mapping. If you see ~95 GiB of
anonymous RSS, that is what happened. Check with:

```
grep -E "RssFile|RssAnon" /proc/$(pgrep -f llama-server)/status
```

The table should show in the load log as `CPU_Mapped model buffer size`, never under `Vulkan0`.

### `--tensor-read-lazy` (on by default since v0.7.2)

```
--tensor-read-lazy on|auto|off     (default: auto)
```

The engram table is gathered 16 random rows per token and never read densely, but the loader used
to advise the whole mapping sequential, so the kernel read ahead 128 KiB for every ~130 bytes
actually wanted. On a 64 GB box that cost 249.7 GiB of disk reads for a single 512 token prompt
against a 152 GiB model, and the run was disk bound end to end.

`auto` advises arch-marked gather tables over 4 GiB for random access and batches a prefetch of
the rows the next ubatch will touch. Both halves matter: suppressing the kernel's readahead
without replacing it is slower than leaving the mapping alone.

Worth knowing before you rely on it:

- the win **depends on the table not fitting in page cache**. On 64 GB it is 3.5x prefill; three
  community 128 GB runs measured about 1.4x
- it **shrinks with context depth**, 3.5x at depth 0 down to 2.5x at 32k
- output is unchanged, gated byte-identical at temperature 0
- `off` restores the pre-v0.7.2 behaviour exactly

### Best decode: fit the experts in GTT

On a 64 GB box a Q3-class cut fits fully offloaded, which is the fastest decode configuration:

```
llama-server -m Qwen3.8-Flash-Next-Q3-*.gguf \
  -ngl 99 --n-cpu-moe 0 -fa on \
  --load-mode mmap --no-host --no-repack --fit off
```

Measured on gfx1151 / 64 GB, Q3 cut, v0.7.2: **pp512 352, tg128 33.4 t/s**.

Those figures need `--tensor-read-lazy`, which is on by default since v0.7.2. Earlier releases
measured **pp512 101.7, tg128 25.4** on the same box and the same weights; that difference is the
engram table's mapping, not the model. See the
[v0.7.2 notes](https://github.com/Nathanw1014/strix-halo-llamacpp/releases/tag/v0.7.2). The win
shrinks with context depth (3.5x at depth 0, 2.5x at 32k) and depends on the table not fitting in
page cache, so expect much less of it on a 128 GB box.

`--n-cpu-moe 0` is what makes decode fast. Raise it only if the model does not fit: each step
spills more experts to the host and costs decode. If a larger quant will not load, raise
`--n-cpu-moe` until it does rather than dropping `-ngl`.

At `-ub 2048` on a 64 GB box, `-ncmoe 0` and `1` do not fit and die with `vk::DeviceLostError`;
**2 is the floor**, not the 4 previously suggested here. Every step above the floor costs about
7.4% of pp512 (333.9 at 2, 310.8 at 3, 286.4 at 4), so 4 gives away roughly 17% prefill for
nothing. `-ub 256` with `-ncmoe 0` is faster than any `-ub 2048` configuration this box can run.

### 128 GB boxes

More of the model fits, so start at `--n-cpu-moe 0` with a larger quant. The table still stays
mapped on the host regardless of how much VRAM you have, since it is larger than either.

`--tensor-read-lazy` helps much less here, because the table largely fits in page cache already.
Three community runs on 128 GB machines measured prefill at 1.35x, 1.53x and 1.43x, with decode
at 0.90x, 1.04x and 1.00x. The decode figures are a wash and we cannot yet explain the 0.90; if
you serve interactively and want the older behaviour exactly, pass `--tensor-read-lazy off`.
These are reported by their owners rather than measured here.

### MTP (speculative decoding)

The draft head ships as a separate sidecar. It needs GTT headroom **alongside** the target, so on
a 64 GB box you must leave room for it (`--n-cpu-moe 4` or higher). At `--n-cpu-moe 0` the target
alone fills GTT and the first queue submit dies with `vk::DeviceLostError`.

### Vision

Works. Pass the mmproj alongside the model:

```
llama-mtmd-cli \
  -m Qwen3.8-Flash-Next-Q3-*.gguf --mmproj mmproj-F16.gguf \
  --image photo.png -p "Describe this image." \
  -ngl 99 --n-cpu-moe 8 -fa on \
  --load-mode mmap --no-host --no-repack --fit off < /dev/null
```

Two things to know:

- **Give it GTT headroom.** The vision tower needs room beside the target, so `--n-cpu-moe 0`
  gets OOM-killed on a 64 GB box. `8` works.
- **`--image` and `-p` together force single-shot.** Without an image the CLI drops into an
  interactive chat REPL, and if stdin is not a terminal it spins on its own prompt and writes
  gigabytes of log. Redirect stdin from `/dev/null`.

For grounding tasks the loader will suggest `--image-min-tokens 1024`; the default is fine for
description.

## Support

If you want to support my work on making local inference better, you are welcome to do so here:

**[buymeacoffee.com/nathanw1014](https://buymeacoffee.com/nathanw1014)**

It goes towards hardware, which means faster iteration on finding, testing and validating fixes,
and that feeds back into more and better releases.

## Credits

- **Gaetan Puleo** — the DeepSeek V4 Vulkan work: lightning-indexer kernels (scalar + coopmat
  prefill + decode variants) and the indexed sparse flash-attention path, contributed as a draft
  against this toolbox's branch and integrated 2026-08-01 with hardening and parity tests added
  during review. Their original branch is preserved verbatim at
  [`dsv4-flash-vulkan-poc`](https://github.com/Nathanw1014/llama.cpp/tree/dsv4-flash-vulkan-poc);
  the clean upstream-candidate cut is
  [`vulkan-dsv4-lightning-indexer`](https://github.com/Nathanw1014/llama.cpp/tree/vulkan-dsv4-lightning-indexer).

- **Jaap Buurman ([@Mushoz](https://github.com/Mushoz))**: the DeepSeek V4 sparse-prefill
  acceleration, a coopmat flash-attention kernel for the indexed sparse path plus a raw/selected
  split, tiled scratch, probability-fragment reuse and per-key-block mask caching (prefill 119 to
  210 tok/s at 32k depth, sparse FA 8.16 s to 1.10 s), contributed as
  [PR #2](https://github.com/Nathanw1014/llama.cpp/pull/2) and merged with authorship intact; the
  Lightning Indexer prefill parallelization, 25 to 51% off the indexer depending on shape
  ([PR #3](https://github.com/Nathanw1014/llama.cpp/pull/3)); and the diagnosis of the batch 2 to
  63 decode gap that the small-batch gather-to-compact commits fix. Those commits carry a
  `Suggested-by` trailer.

## Notes and caveats

- Vulkan is the recommended default on this hardware; the HIP image is for quantized-KV
  decode-at-depth on ROCm specifically.
- mmid is model-dependent (large on some MoEs, near-zero on others).
- Numbers are single-box measurements; reproduce with the bundled `llama-bench`.
