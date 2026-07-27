# Strix Halo llama.cpp flash-attention + MoE fixes - evidence pack

Measured evidence for a set of Flash-Attention and MoE-prefill fixes for llama.cpp on
AMD Strix Halo (gfx1151 / RDNA3.5). Each fix is independent and upstreamable on its own;
this repo is the reproducible measurement behind them, taken on the **latest** GPU driver
and llama.cpp master so the numbers cannot be waved away as a stale toolchain.

Narrative/write-ups are intentionally left out. This is a data pack: every number traces
to a raw `llama-bench` file under `results/`, and the exact toolchain is pinned below.

See **[BRANCHES.md](../BRANCHES.md)** for the per-branch fix inventory (which clean branch carries which
fix, for independent upstreaming) and the mmid config-flag taxonomy (the one real fix vs the marginal
config-tweaks).

## Charts

![Qwen3-Coder-30B-A3B prefill: quantized KV is 2.66x faster than f16 at 64k context](../graphs/01_coder30b_prefill_2.66x.png)

![Qwen3.6-35B-A3B Q4_K_XL, same weights: quant KV matches/beats f16 on prefill and decode at 1/4 the KV memory, versus the best public f16 numbers](../graphs/02_35b_q4kxl_samequant.png)

![Decode throughput vs depth: quantized KV also generates faster than f16 at depth, both models](../graphs/03_decode_both.png)

## The machine

- Framework Desktop, Ryzen AI Max+ 395 (Strix Halo), Radeon 8060S iGPU (gfx1151 / RDNA3.5)
- 64 GB LPDDR5X unified memory, ~256 GB/s. Capacity-rich, bandwidth-poor: it fits large
  models and long KV, but streaming that KV is the bottleneck. That is exactly the regime
  where quantized KV should win, and where these fixes matter.

## Toolchain (pinned)

| Component | Version |
|---|---|
| GPU driver | Mesa **26.3.0-devel** (`git-d18d598e`, 2026-07-25), RADV, built locally |
| libdrm | 2.4.133 (built as a local prefix for the Mesa build) |
| Vulkan headers | 356 |
| Shader compiler | shaderc **v2026.3-dev** (`49a8724d`) - NOT the distro's 2023.8 glslc |
| llama.cpp (PRE) | master `fb92d8f` (2026-07-25) |
| llama.cpp (POST) | `fb92d8f` + the 5 PR #25494 commits + `6e2b7ea` (all-quant transpose) = `d808751` |

The custom Mesa is used only for these runs via `VK_ICD_FILENAMES`; the system Mesa (25.2.8)
is left untouched. The shader-compiler pin matters: building against the 3-year-old distro
`glslc` compiles successfully but emits different SPIR-V, producing numbers that are not
comparable to a current toolchain. All arms here use the same v2026.3-dev glslc.

### Benchmark protocol

```
llama-bench -ngl 99 -fa 1 -b 512 -ub 512 -p 512 -n 32 -d 0,4096,16384,32768,65536 -r 3 -o md
```

- GPU services (llama-swap, ComfyUI) stopped for the whole run; ~60 GiB free.
- q8: `-ctk q8_0 -ctv q8_0`; q4: `-ctk q4_0 -ctv q4_0`; f16: default.
- pre/post arms interleaved adjacently per quant type, 20 s settle between arms, plus a
  start and end f16 canary to bracket window stability.
- `pp512` = prefill throughput at the given context depth; `tg32` = decode throughput at depth.

## The fixes

### 1. Vulkan: dequantize q8_0 KV once in the coopmat1 FA kernel (PR #25494) - prefill

**What it does.** The coopmat1 Flash-Attention path re-dequantized quantized K/V on every
FA invocation. This dequantizes q8_0 K/V **once** into a transposed, contiguous f16 scratch
and reuses it, which also fixes the strided-read penalty on the KV layout. Net effect is on
**prefill at depth**: the deeper the context, the more the one-time dequant amortizes.

- Scope in the PR: **q8_0 only**.
- Branch: `Nathanw1014/llama.cpp` `vulkan-coopmat1-fa-dequant-transpose` (also in `strix-halo-fa-fixes`).
- Status: **in-flight upstream PR #25494**.
- Evidence: the q8 PRE-vs-POST columns in the matrix below (this repo, latest stack).

### 2. HIP/ROCm: dequantize KV on load in the tile FA kernel (decode)

**What it does.** On CUDA/HIP the quantized-decode path uses the `vec` kernel, which
dequantizes each KV element once **per GQA query head** (gqa_ratio× redundant work; 8x on
Qwen3-Coder-30B). This teaches the `tile` kernel to dequantize KV on load into its LDS tile
and routes quantized decode there, so KV is dequantized once and reused across the batched
GQA heads. Same idea as #25494, opposite backend and opposite half of the session (decode,
not prefill). The two are complementary, not overlapping.

- Branch: `Nathanw1014/llama.cpp` `fa-tile-dequant-on-load` (also in `strix-halo-fa-fixes`).
- Status: **public branch, testable now**; upstream PR not yet opened (independent of #25494, different backend).
- Correctness: `test-backend-ops` FLASH_ATTN 6000/6000, after first closing an upstream test
  gap (quantized KV had zero coverage at head-dim 128 / gqa_ratio 8, the common real shape).
- Measured (separate ROCm build, so read the deltas not the absolutes; rocWMMA-OFF, the
  Lemonade llamacpp-rocm config), Qwen3-Coder-30B q8_0 tg32:
  - d32k: 16.72 -> 38.12 (**+128%**), beats f16 (31.99) by 1.19x
  - d64k:  8.94 -> 29.69 (**+232%**), beats f16 (21.37) by 1.39x
  - Cross-vendor: also reproduced on an RTX 3070 (Ampere) under a forced gate: +43.9% @32k,
    +95.7% @64k on Llama-3.2-1B, so it is not a gfx1151 quirk.

### 3. Vulkan: mmid grouped-GEMM row-list prepass (MoE prefill)

**What it does.** `MUL_MAT_ID` (MoE expert routing) ran an O(experts x tokens) expert-ID scan
in every workgroup. A prepass builds row lists (prefix-sum counts -> offsets -> scatter packed
rows) so the scan happens once. That is the real fix (+8.4% end-to-end). Smaller waste-removals
stack on top (scache, bm64, smalln); two knob-tweaks (wave32, f16b) are marginal-to-noise and
kept env-gated. The kernel is DRAM-bandwidth-bound (per-expert weight streaming), so removing
wasted work beats the wall while wave-size/tile knobs cannot.

- Branch: `Nathanw1014/llama.cpp` `mmid-fullstack`. Env-gated; defaults undecided.
- Correctness: 790/790 `MUL_MAT_ID`.
- Measured on this stack (the ceiling matrix below, mmid isolated via env toggle), pp512:
  - Qwen3.6-35B-A3B: +15% at d0, tapering to +7% at 64k (the MoE-heavy model where mmid pays)
  - Qwen3-Coder-30B-A3B: near-zero (its 128-expert/top-8 routing already fits the tiles natively)

### (experimental) all-quant dequant-transpose - extends #25494 to q4/q5

Commit `6e2b7ea` extends the #25494 dequant-once path to q4_0/q4_1/q5_0/q5_1 (and iq4_nl).
It is **not** part of PR #25494 (which is q8-only); it is included here to measure q4 **with**
dequant-once (the `q4 dequant-once` column below) and it feeds the max-performance branch.

- Correctness on the latest stack (this repo's build): FLASH_ATTN passes for
  **f16, q8_0, q4_0, q4_1, q5_0, q5_1**; **iq4_nl is broken** (ERR=inf) and is unused/excluded.

## Correctness gate (this stack)

`test-backend-ops -o FLASH_ATTN_EXT` on the POST build, Mesa 26.3.0-devel, v2026.3-dev glslc:
all f16 / q8_0 / q4_0 / q4_1 / q5_0 / q5_1 cases pass; only the experimental iq4_nl type fails
(known-broken, not used by any arm here).

## The matrix

Both models are A3B MoE. Qwen3-Coder-30B-A3B = Q6_K_XL, head-dim 128, gqa 8.
Qwen3.6-35B-A3B = Q5_K_XL, head-dim 256, gqa 8. All values t/s, r=3.
"post"/"deq-once" = dequant-once ON; "pre"/"base" = OFF (plain master). Start-vs-end f16
canary: deep metrics within 1%, d0 pp within +3.5%.

> **Re-validated on `amd_iommu=off` (0–64k, 2026-07-26).** The full matrix was re-run on a clean iommu-off
> box; start/end canaries agreed within 0.3% (no drift). The headline reproduces: Coder-30B prefill @64k
> stock-f16 71.9 → q4 190 (**2.64x**) / q8 191 (**2.66x**); 35B decode @64k **+18%**. The IOMMU itself
> accounts for only **~+3–5% prefill, ~neutral decode** (measured off-vs-on, same build), so the detailed
> per-depth tables below — from the original iommu-on run — sit a few percent low but are unchanged in shape
> and conclusion. Metric note: the repo graphs are **pp512**; the "vs public" section is **pp2048** to match
> kyuz0, so their prefill percentages differ by construction (pp512 @64k = +9% on the 35B Q4_K_XL).

### Headline

- **q4 gets dequant-once too, and it lands the same win as q8.** Coder-30B prefill at 64k:
  q4 baseline 125.75 -> **182.41 (+45%)**; q8 baseline 125.34 -> 183.75 (+47%). q4-with-dequant-once
  matches q8-with-dequant-once at every depth (both dequantize into the same f16 scratch, so the
  FA cost converges).
- **Dequant-once removes the quantized-KV prefill penalty, and the gain grows with depth.** At
  head-dim 128 (Coder-30B) quantized prefill goes from roughly f16 to **2.6x f16** at 64k. At
  head-dim 256 (35B) it goes from ~17% below f16 up to **f16 parity**.
- **Decode is untouched by the fix** (q8/q4 pre == post within noise): the change is prefill-only.
  Quantized decode already beats f16 at depth on RADV via native GQA batching (Coder-30B 64k:
  q8 +36%, q4 +41%; 35B 64k: q8 +13%, q4 +17%).
- Net: on this box **q4_0 KV is the best long-context choice** - smallest footprint, fastest
  decode, and (with dequant-once) prefill equal to q8.

### Prefill, pp512 (t/s)

**Qwen3-Coder-30B-A3B (head-dim 128)** - the strongly-affected shape:

| depth | f16 | q8 pre | q8 post | Δ q8 | q4 base | q4 deq-once | Δ q4 | q8post / f16 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1128.18 | 1102.36 | 1117.15 | +1% | 1096.29 | 1113.15 | +2% | 0.99x |
| 4096 | 807.28 | 738.36 | 834.38 | +13% | 728.39 | 825.83 | +13% | 1.03x |
| 16384 | 370.73 | 372.81 | 481.31 | +29% | 367.23 | 484.23 | +32% | 1.30x |
| 32768 | 198.98 | 225.79 | 308.33 | +37% | 223.12 | 313.01 | +40% | 1.55x |
| 65536 | 70.64 | 125.34 | 183.75 | +47% | 125.75 | 182.41 | +45% | 2.60x |

**Qwen3.6-35B-A3B (head-dim 256)** - dequant-once brings quant up to f16 parity:

| depth | f16 | q8 pre | q8 post | Δ q8 | q4 base | q4 deq-once | Δ q4 | q8post / f16 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1003.29 | 962.13 | 999.17 | +4% | 996.62 | 1000.51 | +0% | 1.00x |
| 4096 | 902.17 | 873.73 | 914.44 | +5% | 838.86 | 903.93 | +8% | 1.01x |
| 16384 | 768.82 | 691.65 | 765.47 | +11% | 673.01 | 761.27 | +13% | 1.00x |
| 32768 | 631.76 | 546.52 | 623.88 | +14% | 544.24 | 630.80 | +16% | 0.99x |
| 65536 | 469.40 | 388.11 | 464.86 | +20% | 381.73 | 465.09 | +22% | 0.99x |

### Decode, tg32 (t/s)

Decode is prefill-fix-neutral (q8/q4 pre == post within noise), so only the post arms are shown.
Quantized decode beats f16 at depth via RADV's native GQA batching.

**Qwen3-Coder-30B-A3B (head-dim 128)**

| depth | f16 | q8 | q4 | q8 / f16 | q4 / f16 |
|---:|---:|---:|---:|---:|---:|
| 0 | 66.78 | 68.31 | 66.14 | 1.02x | 0.99x |
| 16384 | 45.00 | 49.48 | 52.15 | 1.10x | 1.16x |
| 32768 | 33.71 | 41.28 | 42.92 | 1.22x | 1.27x |
| 65536 | 22.68 | 30.90 | 32.03 | 1.36x | 1.41x |

**Qwen3.6-35B-A3B (head-dim 256)**

| depth | f16 | q8 | q4 | q8 / f16 | q4 / f16 |
|---:|---:|---:|---:|---:|---:|
| 0 | 58.20 | 58.56 | 58.34 | 1.01x | 1.00x |
| 16384 | 51.71 | 55.09 | 54.78 | 1.07x | 1.06x |
| 32768 | 47.85 | 51.57 | 50.18 | 1.08x | 1.05x |
| 65536 | 41.45 | 46.81 | 48.32 | 1.13x | 1.17x |

## The ceiling: all fixes stacked (max prefill + decode)

The matrix above isolates the in-flight PR (dequant-once) on latest master. This section stacks
**everything** for maximum throughput: dequant-once + q4 transpose + the mmid MoE-prefill stack
(`ROWLISTS+SMALLN+BM64+WAVE32`; F16B was left OFF **for these runs** — see note below), built on
the fix base `5c3a586` and compared against stock `5c3a586`, same glslc / same driver. Start-vs-end
f16 canary drifted <1% at every point.

Column key: `stock f16` and `stock q4` = plain 5c3a586. `+FA fixes` = dequant-once + q4 transpose,
mmid off. `CEIL` = + mmid on. `mmid adds` = CEIL vs +FA-fixes (isolates mmid).

> **Note on F16B (updated 2026-07-27).** These runs predate the fix and left `GGML_VK_MMID_F16B`
> off. The abort was root-caused to a missing `Q2_0` f16-B pipeline — an experimental type that only
> `test-backend-ops` reaches and no real GGUF uses — not a Mesa 26.3 driver bug. It is fixed, and the
> shipped `vulkan/_run` wrapper now enables F16B **by default**. So these numbers are a slight
> *under*-statement of the current build on models where F16B helps (small gain on the 35B, neutral
> on Coder-30B).

### Prefill pp512 (t/s) - Qwen3-Coder-30B-A3B (hd128)

| depth | stock f16 | stock q4 | +FA fixes (q4) | CEIL (q4) | CEIL (q8) | mmid adds | total vs stock f16 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1131.64 | 1099.14 | 1114.13 | 1156.07 | 1160.21 | +4% | +2% |
| 4096 | 810.40 | 729.43 | 827.90 | 852.30 | 853.11 | +3% | +5% |
| 16384 | 371.22 | 367.76 | 483.45 | 489.04 | 489.52 | +1% | +32% |
| 32768 | 202.05 | 224.31 | 310.23 | 314.56 | 313.56 | +1% | +56% |
| 65536 | 69.78 | 125.74 | 184.64 | 185.37 | 186.26 | +0% | **+166% (2.66x)** |

### Prefill pp512 (t/s) - Qwen3.6-35B-A3B (hd256)

| depth | stock f16 | stock q4 | +FA fixes (q4) | CEIL (q4) | CEIL (q8) | mmid adds | total vs stock f16 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 992.05 | 997.02 | 1027.92 | 1183.63 | 1183.34 | **+15%** | +19% |
| 4096 | 900.44 | 876.89 | 931.36 | 1070.09 | 1067.39 | +15% | +19% |
| 16384 | 759.99 | 693.90 | 779.54 | 866.66 | 870.85 | +11% | +14% |
| 32768 | 628.41 | 555.04 | 629.06 | 703.52 | 696.77 | +12% | +12% |
| 65536 | 462.91 | 385.36 | 470.41 | 503.68 | 506.51 | +7% | +9% |

### Decode tg32 (t/s), CEIL vs stock f16

| depth | Coder-30B f16 | Coder-30B CEIL q4 | ratio | 35B f16 | 35B CEIL q4 | ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 67.42 | 66.76 | 0.99x | 58.16 | 58.47 | 1.01x |
| 32768 | 33.68 | 42.69 | 1.27x | 47.32 | 52.09 | 1.10x |
| 65536 | 22.69 | 32.56 | 1.43x | 40.71 | 48.47 | 1.19x |

**mmid is model-dependent.** It is a large win on the 35B (+15% shallow, +7-12% at depth) and near-zero
on Coder-30B (+4% shallow, +0% deep): Coder-30B's 128-expert/top-8 routing already fits the tiles
natively (mean per-expert n ~= 32 = the tile width), so there is little redundant expert-scan to remove;
the 35B carries the tile-occupancy waste that mmid's row-list prepass eliminates. On Coder-30B the deep
prefill win is essentially all dequant-once (stock f16 70 -> all-fixes q4 185 = 2.66x at 64k).

## vs public data

The public Strix Halo corpus DOES report depth (correcting an earlier assumption) - but almost all of it
runs **f16 KV**. The cleanest public reference is kyuz0/amd-strix-halo-toolboxes (single box, raw JSON, f16
KV). To compare cleanly we ran the SAME model at kyuz0's exact weight quant (Qwen3.6-35B-A3B UD-Q4_K_XL), so
the only variables are KV type + our fixes, not weights.

**Same box, same weights (UD-Q4_K_XL), stock f16 KV vs fixes + q4 KV (pp2048 / tg32, ub1024):**

| depth | prefill: stock f16 -> fixes q4 | decode: stock f16 -> fixes q4 | KV footprint |
|---:|---|---|---:|
| 32768 | 689 -> 746 (+8%) | 49.7 -> 55.2 (+11%) | 1/4 |
| 65536 | 465 -> 522 (+12%) | 42.6 -> 50.3 (**+18%**) | 1/4 |

**Cross-check vs kyuz0's published f16 (same model, Q4_K_XL):** our stock-f16 decode lands within ~1-2% of
kyuz0's (42.6 vs 43.2 @64k; 49.7 vs 49.2 @32k), so our baseline reproduces theirs and the comparison is
valid. That puts our q4 decode **+16% over kyuz0's f16 at 64k, at 1/4 the KV memory**.

Honest read: **+12% prefill and +18% decode vs stock f16 at matched weights, 1/4 the KV memory.** The decode
win cross-validates against public data. The prefill figure is the same-box A/B: our f16 prefill baseline
sits a bit below kyuz0's (a build/driver gap), so we do not claim a cross-box prefill win. Independent
corroboration that quant-KV beats f16 on decode at depth: the `strix-halo-guide` filled_kv_decode.csv
(35B @64k: f16 41.4 vs q4_0 51.3).

The **2.6x prefill** figure is a *separate* claim: our own f16 -> quant on Qwen3-Coder-30B-A3B (hd128,
where dequant-once is strongest). There is no clean public depth counterpart for that model/config, so it
stands on the same-box pre/post above, not on a public comparison.

kyuz0 numbers: https://github.com/kyuz0/amd-strix-halo-toolboxes/blob/main/docs/results.json (build b9187, f16 KV, -fa).

### 128k deep context — vs strixhalo.wiki (2026-07-26, iommu-off)

`strixhalo.wiki/AI/llamacpp-performance` publishes a Qwen3-30B-A3B (Q4_K_XL, **f16 KV**) run at `d130560`
(~128k) — the deepest public gfx1151 point. We ran our Coder-30B-A3B (same 30B-A3B class, hd128; heavier
Q6_K weights) at the exact same depth:

**Prefill pp512 @ 128k (d130560):**

| build | KV | pp512 | vs our fixed |
|---|---|---:|---:|
| wiki RADV | f16 | 17.2 | **6.0x** slower |
| wiki ROCm | f16 | 40.6 | 2.5x slower |
| wiki ROCm rocWMMA-tuned | f16 | 51.1 | **2.0x** slower |
| ours, stock | f16 | 28.4 | our baseline |
| **ours, + fixes** | **q4 / q8** | **102.8 / 102.5** | — |

**Decode tg @ 128k:** wiki RADV f16 12.5 / ROCm-tuned 13.3 → ours q4 **22.5** (~+70% over their best).

Full 128k curve (this box, iommu-off):

| model | stock f16 pp / tg | q4+fix pp / tg | q8+fix pp / tg |
|---|---|---|---|
| Coder-30B-A3B (Q6_K, hd128) | 28.4 / 13.9 | **102.8 / 22.5** | 102.5 / 20.9 |
| Qwen3.6-35B-A3B (Q5_K, hd256) | 297.7 / 33.1 | 325.3 / 42.0 | 326.2 / 39.9 |

The hd128 prefill gain **grows with depth**: 1.6x @32k → 2.66x @64k → **3.6x @128k** (28.4 → 102.8, same box).
Even our stock f16 (28.4) tops the wiki's RADV f16 (17.2) — that part is the newer Mesa 26.3 + `amd_iommu=off`;
the fix is the 3.6x on top. Caveats: wiki weights are Q4_K_XL (lighter than our Q6_K, if anything favoring
them); deep-context prefill is KV-bound so weight quant matters little here; the 35B (hd256) barely moves (+9%),
as expected. Raw output: `benchmarks/results/` (Phase-3 `d130560` arms).

## Caveats / honesty

- Single measurement window per model. pp512 monotonicity and the start/end f16 canary are the
  in-window sanity checks; a tight r=3 stddev alone is not evidence of a clean window.
- This matrix is **Vulkan/RADV** (the #25494 prefill fix + RADV's native quantized decode).
  The HIP decode fix (section 2) is a different backend and a separate build; its numbers above
  are from their own windows and are labeled as such.
- The `q4 dequant-once` column uses the experimental `6e2b7ea`, not the shipping PR.

## Reproduce

Build Mesa (RADV, compute-only) against a local libdrm 2.4.133, build llama.cpp against the
v2026.3-dev glslc and `~/.local/include` headers, then run the matrix. The exact build/bench
scripts are under `scripts/` (`mesa_build.sh`, `llama_build2.sh`, `kv_matrix3.sh`), the pinned
toolchain and commit hashes are in `PROVENANCE.txt`, and raw `llama-bench` output is under
`results/` (one file per arm, plus start/end `canary*` for window stability).
