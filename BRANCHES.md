# Branches and config flags

This work is deliberately split into **clean, per-concern branches** (one fix each, for independent
upstreaming) plus a few **combined branches** for users who just want everything. The mmid tuning is
further split into **fixes** (remove wasted work) and **config-tweaks** (change a knob), because they
behave very differently on this bandwidth-bound hardware.

## Upstream-candidate branches (clean, per-concern)

Each carries exactly one fix, kept minimal so it can be reviewed and merged on its own.

| Branch | Fix | Backend | Status |
|---|---|---|---|
| `vulkan-coopmat1-fa-dequant-transpose` | dequantize q8_0 KV once in the coopmat1 FA kernel (prefill) | Vulkan | in-flight PR #25494 |
| `vulkan-mmid-rowlists` | mmid row-list prepass: removes the redundant per-workgroup expert-ID scan in `MUL_MAT_ID` | Vulkan | upstream candidate (clean cherry-pick onto master, MUL_MAT_ID 2/2) |
| `fa-tile-dequant-on-load` | dequantize KV on load in the tile FA kernel, route quantized decode there (decode) | HIP / CUDA | public branch, testable now; upstream PR not yet opened |
| `vulkan-fa-f16-kv-contig` | contiguize strided f16 KV before FA (the f16 counterpart of the dequant-once transpose; 2.63x pp @ 64k vs stock master) | Vulkan | stacked on the #25494 branch (extends its scratch infra); PR queued behind #25494 |
| `feat/fa-p-hoist` | hoist the GEMM2 P `coopMatLoad` out of the `hsv_tile` loop (prefill) | Vulkan | ready; unconditional and 8 insertions in one file, but wants a second vendor first (the win depends on the driver unrolling the loop, and cm1 is shared with NVIDIA pre-Blackwell / Intel / AMD-Windows) |

Those five are the whole upstream set. Everything below ships in the combined branch but is
**not** offered upstream — see the per-item reasons in the 2026-07-30 section and the README.

## Combined / max-performance branches

| Branch | Contents | Use |
|---|---|---|
| [`strix-halo-vulkan`](https://github.com/Nathanw1014/llama.cpp/tree/strix-halo-vulkan) | #25494 + all-quant transpose + mmid + F16B fix + f16 KV contiguize (on by default, `b1a10f9`/`9019eb4`) + non-native K/V type routing (`8929240`) + scale-cache disable (the scache had regressed) + the 2026-07-30 FA stack (`e11cafa` P-load hoist, `40f85eb` Psh relayout, `dfb619c` wave32 pin) + `0b29b30` all perf env gates **default-on** (opt-out `=0`), rebased on upstream **`8161641`** (2026-07-28 master; pre-rebase tip archived as `strix-halo-vulkan-ff067f7`, where the older `442d7df`/`3957182`/`1abdd92`/`146fb73` hashes still resolve) | **the complete Vulkan stack behind the toolbox — build from source here.** Verified: FLASH_ATTN_EXT gate green for f16/q8/q4/q4_1/q5_0/q5_1; iq4_nl routing fix landed, full validation pending; Coder-30B f16 @64k 2.63x vs stock master |
| `strix-halo-fa-fixes` | #25494 + HIP tile-dequant | both-backends branch (points Strix Halo users at both fixes) |
| `mmid-fullstack` | earlier cut of the Vulkan stack, older upstream base | superseded by `strix-halo-vulkan` |

## Experimental

| Change | What | Note |
|---|---|---|
| all-quant dequant-transpose (`6e2b7ea`) | extends #25494's dequant-once to q4_0/q4_1/q5_0/q5_1 | this is what makes q4 KV prefill fast; shipped as `569987e`; `iq4_nl` was broken when this was written but the routing fix (`8929240`) closed that and FLASH_ATTN_EXT is now 5105/5105 including all 340 iq4_nl cases |

## mmid config flags: fixes vs tweaks

> **Since `0b29b30` (2026-07-30) every flag below is ON by default on `strix-halo-vulkan`** —
> the ceiling branch ships max-perf with no flags; `=0` opts out. A/B runs must now set the
> off-arm explicitly (unset no longer means off). Per-flag numbers below are unchanged.

A **fix** removes wasted work (an algorithmic inefficiency). A **tweak** just changes a hardware/format
knob hoping the same work runs faster. On this kernel the fixes won and the tweaks did not, because the
bottleneck is **DRAM bandwidth** (per-expert weight streaming): removing wasted work beats the wall,
wave-size/tile knobs cannot.

### 2026-07-30 flash-attention stack (pushed, stacked branches)

Each isolates one change; they are stacked because the relayout edits the line the hoist adds.
All are merged into `strix-halo-vulkan` (tip `54d76da`).

| Branch | Commit | What it does | Measured (Coder-30B, pp2048, ub2048) |
|---|---|---|---|
| [`feat/fa-p-hoist`](https://github.com/Nathanw1014/llama.cpp/tree/feat/fa-p-hoist) | `e11cafa` | hoists the GEMM2 P coopMatLoad out of the hsv_tile loop | +6.9 / +8.1 / +9.2% at d8k / 16k / 32k |
| [`feat/fa-psh-relayout`](https://github.com/Nathanw1014/llama.cpp/tree/feat/fa-psh-relayout) | `40f85eb` | stores Psh query-major so the GEMM2 A load vectorizes; also fixes the host shmem estimator | perf-neutral by design (LDS 16384 -> 15360 B) |
| [`feat/fa-wave32-rule`](https://github.com/Nathanw1014/llama.cpp/tree/feat/fa-wave32-rule) | `dfb619c` | pins a 32-wide subgroup where narrowing is free (reduces to hsv <= 128 on a 64-wide device); `GGML_VK_FA_WAVE32=1` | +2.7 / +9.1 / +11.5 / +11.9% on top of the hoist |
| [`test/fa-perf-probes`](https://github.com/Nathanw1014/llama.cpp/tree/test/fa-perf-probes) | `54d76da` | perf-only probe cases (head sizes, KV-head counts, quant KV, delta-net, MoE tiles) | n/a |

Combined: +2.8 to +3.1% at d0 rising to +21.6 to +22.0% at d32768, consistent across f16/q8_0/q4_0
KV, with decode unchanged. Full matrix and caveats: the 2026-07-30 RADV-vs-ROCm data pack.

**Upstream status of these four.** Only `feat/fa-p-hoist` is an upstream candidate (it is listed
in the table at the top). `feat/fa-wave32-rule` is strong but not ready: it needs its env gate
removed, an assert relocated that can fire from device properties alone on a subgroup-128/256
device, and confirmation on a second AMD part. `feat/fa-psh-relayout` is **on hold** — no measured
standalone benefit, it exists to enable the hoist, and it steers into RADV's only
alignment-asserting coopmat path with an unasserted 16-byte precondition; its host shmem estimator
fix is not standalone either, since upstream's estimator is correct without the relayout.
`test/fa-perf-probes` is benchmark scaffolding, not a fix, and is not a candidate at all.

### Fixes (remove wasted work)

| Flag | Gain | What it removes |
|---|---|---|
| `GGML_VK_MMID_ROWLISTS` | **+8 to +11%** (depth-dependent) | THE fix. Prefix-sum over per-expert counts -> offsets -> scatter packed rows, so the O(experts x tokens) expert-ID scan runs once instead of per workgroup |
| `GGML_VK_MMID_BM64` | +1.3% | 64x32 tile halves redundant B L2 re-reads |
| `GGML_VK_MMID_SMALLN` | ~0% alone | fixes tile-occupancy waste at small per-expert n; only visible once ROWLISTS unmasks it (stacks) |

### Reverted / obsoleted

| Flag | Status | Why |
|---|---|---|
| scache (compile-time) | **disabled in the shipped build** | Once measured at +1.67%, but later tile changes obsoleted it and it regressed to -4% at the standard protocol and -20% on Q5_K-weight MoE at ub2048. Disabled; its +1.67% is not part of any current number. |

### Config-tweaks (change a knob; marginal or negative here)

| Flag | Effect | Note |
|---|---|---|
| `GGML_VK_MMID_WAVE32` | +2.8% | required subgroup size 32. Marginal / within canary noise: shaderstats show no register spill either way; the only mechanism is VOPD dual-issue, ~1.7% of VALU slots |
| `GGML_VK_MMID_F16B` | +2.4% | f16 B operand (halves B bytes). Model-dependent: small gain on some MoEs, positive but within noise on Coder-30B (+1.2% d0, +0.5% d4096, +0.3% d16384). An abort on the experimental `Q2_0` type has been fixed (falls back to the standard path) |
| `GGML_VK_MMID_TILE16` | -3.8% | NEGATIVE: shrinking BN below mean per-expert n grows A traffic |
| `GGML_VK_MMID_INT` | -8.5% | NEGATIVE: on RDNA3.5, coopmat f16 beats scalar packed-int for these MoE shapes |

### Toolbox defaults

`ROWLISTS + SMALLN + BM64 + WAVE32 + F16B` on. F16B is default-on in the max-perf toolbox (safe now,
small gain on some MoEs like the 35B, neutral elsewhere; disable with `GGML_VK_MMID_F16B=0`).
`TILE16` and `INT` are documented negatives, never enabled.

Honest one-liner: **one real fix (rowlists) plus small waste-removals (bm64/smalln); the
knob-tweaks are marginal-to-negative, as expected on a bandwidth-bound kernel.**
