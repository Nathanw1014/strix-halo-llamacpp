# v0.7.4 (draft, staging branch; not released)

Two Vulkan shader fixes on top of v0.7.3, both for defects that also exist in upstream llama.cpp, plus one performance fix that restores a win the fork had measured but never shipped. Numbers are N identical greedy requests into one llama-server on Strix Halo (gfx1151), Qwen 3.8 Flash-Next Q3 with f16 PLE.

## Fixed

1. Masked-V leak in the cm1 flash attention shader. A fully masked column has P = +0.0, but P times V takes V's sign, stale cache cells feed -0.0 into the accumulator, and gfx11 WMMA does not add -0.0 exactly, so output depended on what the previous request left in the cache. Fix: per-column visibility mask built during the mask load, V zeroed for fully masked columns, staged path only for partially masked blocks. 1024 token prompt, 16 tries, 129 token continuations: v0.7.3 gave 5 to 6 distinct, v0.7.4 gives 16 identical. Also present in upstream (master: 3 to 6 of 16 on the same prompt); reported.

2. Top-k slot order race in the radix select (upstream #28032, in the fork since Aug 31). Output slots were assigned with atomicAdd, so the sparse selection came out in a scheduling-dependent order and the noise cascaded into late token flips above 2051 prompt tokens. Fix: deterministic per-chunk scan, ascending index order. 32k prompt, 4 tries: 2 to 3 distinct before, 4 identical after; prefill and decode at 16k depth within noise. Also present in upstream master; reported.

## Performance

3. The mul_mat_id q5_K/q4_K scale cache that bfc1eb47b (Jul 28) meant to disable was still compiled in on every build (an `#ifdef` guarding a macro defined as 0). Fixed with `#if`. Measured on Qwen3.6-35B-A3B UD-Q5_K_XL, same driver, 3 repetitions: pp512 at ub512 1400 to 1749 t/s (+25%), pp2048 at ub2048 1633 to 1789 t/s (+10%), decode unchanged. Models without q5_K/q4_K expert weights are unaffected.

## Corrections to the v0.7.3 notes

- v0.7.3 did not fix the repeatability report; it fixed the progressive drift (missing upstream #27812) and reached upstream's own repeatability level at the reporter's shape.
- The remaining alternation was attributed to the bundled Mesa driver. That was wrong: it reproduces on stock Mesa 25.2.8 and on the bundled Mesa 26.3 inside the published container with an empty environment; the driver only changes which stale bytes are read.

## Gate changes (tools/repeat_gate.py, tools/prompts/, BUILD.md)

The previous repeatability prompt was one sentence repeated, whose continuation has almost no near-tie tokens; it read clean on a build that was not. The mandatory gate now runs real prose (a 1024 token WikiText article and a 31.7k token slice), 129 token continuations, a 32k prompt, `--subtoken 8` (compares the full per-position logprob streams and fails on any difference), and a pure-upstream control on the same box. Results for this build and for upstream master are in the release checklist output.

## Not changed

Numerics switches (`GGML_VK_FA_WAVE32`, the delta-net l2norm identity) are unchanged; they move bits relative to upstream, not correctness. The MMID_QK_SCACHE `#ifdef` and the ragged-block QSA policy remain as recorded candidates for a later release.

## Credit

lhl (llm-tracker), for the repeatability report and the retest.

## Staging build validation (2026-09-03)

Bundle built from `release/v0.7.4-staging` (8f8df23) with the CI cmake block and the same Mesa 26.3 driver as v0.7.3, so only llama.cpp changed. All gates run with `--subtoken 8` and the strict token gate:

| gate | result |
|---|---|
| four-prompt sweep, 6 requests each | 1 unique on every prompt; logprob streams identical |
| WikiText 1024 token prompt, 16 requests, 129 token continuations | 1 unique; logprob streams identical (129 positions x 9 candidates) |
| WikiText 31.7k token prompt, 4 requests, 48 token continuations | 1 unique; logprob streams identical |
| the same 1024 x16 shape inside the container image, empty environment | 1 unique; logprob streams identical |

Same shapes on the builds this release replaces: v0.7.3 gives 5 to 6 unique at the 1024 x16 shape, upstream master gives 6 (129 tokens) and 2 of 4 at 32k.
