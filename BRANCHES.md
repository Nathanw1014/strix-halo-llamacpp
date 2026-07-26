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
| `fa-tile-dequant-on-load` | dequantize KV on load in the tile FA kernel, route quantized decode there (decode) | HIP / CUDA | queued behind #25494 (one upstream PR at a time) |

## Combined / max-performance branches

| Branch | Contents | Use |
|---|---|---|
| `strix-halo-fa-fixes` | #25494 + HIP tile-dequant | community "point Strix Halo users here" branch (both backends) |
| `mmid-fullstack` | #25494 + the full mmid stack (env-gated) | Vulkan MoE-prefill stack |
| ceiling stack (this repo's toolbox binary) | #25494 + all-quant transpose + mmid + scache + F16B fix | the max-performance build behind the toolbox |

## Experimental

| Change | What | Note |
|---|---|---|
| all-quant dequant-transpose (`6e2b7ea`) | extends #25494's dequant-once to q4_0/q4_1/q5_0/q5_1 | this is what makes q4 KV prefill fast; `iq4_nl` is broken (excluded), used for the q4 matrix arm |

## mmid config flags: fixes vs tweaks

A **fix** removes wasted work (an algorithmic inefficiency). A **tweak** just changes a hardware/format
knob hoping the same work runs faster. On this kernel the fixes won and the tweaks did not, because the
bottleneck is **DRAM bandwidth** (per-expert weight streaming): removing wasted work beats the wall,
wave-size/tile knobs cannot.

### Fixes (remove wasted work)

| Flag | Gain | What it removes |
|---|---|---|
| `GGML_VK_MMID_ROWLISTS` | **+8.4%** | THE fix. Prefix-sum over per-expert counts -> offsets -> scatter packed rows, so the O(experts x tokens) expert-ID scan runs once instead of per workgroup |
| scache (compile-time) | +1.67% | drops redundant per-iteration scale re-extraction via a shared-memory cache (q4_K/q5_K) |
| `GGML_VK_MMID_BM64` | +1.3% | 64x32 tile halves redundant B L2 re-reads |
| `GGML_VK_MMID_SMALLN` | ~0% alone | fixes tile-occupancy waste at small per-expert n; only visible once ROWLISTS unmasks it (stacks) |

### Config-tweaks (change a knob; marginal or negative here)

| Flag | Effect | Note |
|---|---|---|
| `GGML_VK_MMID_WAVE32` | +2.8% | required subgroup size 32. Marginal / within canary noise: shaderstats show no register spill either way; the only mechanism is VOPD dual-issue, ~1.7% of VALU slots |
| `GGML_VK_MMID_F16B` | +2.4% | f16 B operand (halves B bytes). Model-dependent: small gain on some MoEs, neutral-to-negative on Coder-30B. An abort on the experimental `Q2_0` type has been fixed (falls back to the standard path) |
| `GGML_VK_MMID_TILE16` | -3.8% | NEGATIVE: shrinking BN below mean per-expert n grows A traffic |
| `GGML_VK_MMID_INT` | -8.5% | NEGATIVE: on RDNA3.5, coopmat f16 beats scalar packed-int for these MoE shapes |

### Toolbox defaults

`ROWLISTS + SMALLN + BM64 + WAVE32 + F16B` on. F16B is default-on in the max-perf toolbox (safe now,
small gain on some MoEs like the 35B, neutral elsewhere; disable with `GGML_VK_MMID_F16B=0`).
`TILE16` and `INT` are documented negatives, never enabled.

Honest one-liner: **one real fix (rowlists) plus small waste-removals (scache/bm64/smalln); the
knob-tweaks are marginal-to-negative, as expected on a bandwidth-bound kernel.**
