# v0.7.4 (draft, staging branch; not released)

Three correctness fixes on top of v0.7.3 (one in the KV cache, two in the Vulkan backend; two of the three defects also exist in upstream llama.cpp), plus one performance fix that restores a win the fork had measured but never shipped. Numbers are N identical greedy requests into one llama-server on Strix Halo (gfx1151), Qwen 3.8 Flash-Next Q3 with f16 PLE.

## Fixed

1. Output depended on stale KV cache cells (masked-V leak). A fully masked flash attention column has P = +0.0, but P times V takes V's sign, stale cache cells feed -0.0 into the accumulator, and gfx11 WMMA does not add -0.0 exactly, so output depended on what the previous request left in the cache. 1024 token prompt, 16 identical greedy requests, 129 token continuations: v0.7.3 gives 3 to 6 distinct across runs on Qwen3.8 Flash-Next and alternates between two continuations on Qwen2.5-7B with plain f16 KV; v0.7.4 gives 16 identical on both, byte identical to a fresh server's first request on both. Fix: the KV cache keeps every free cell at zero. Cells are zeroed in every layer at the moment they are freed, so a masked-out cell never holds anything to leak. No shader change, no per-token work, no graph nodes. Not covered: masked-out cells that belong to another sequence in a unified multi-sequence cache (--kv-unified with more than one slot); that case needs the shader-side fix, which is not shipped. Also present in upstream (master: 3 to 6 of 16 on the same prompt); reported.

2. Top-k slot order race in the radix select (upstream #28032, in the fork since Aug 31). Output slots were assigned with atomicAdd, so the sparse selection came out in a scheduling-dependent order and the noise cascaded into late token flips above 2051 prompt tokens. Fix: deterministic per-chunk scan, ascending index order. 32k prompt, 4 tries: 2 to 3 distinct before, 4 identical after; prefill and decode at 16k depth within noise. Also present in upstream master; reported.

3. Flash-attention dequant-once fast path read some K/V layouts in the wrong order. The guard that routes K/V into the dequant scratch only checked element stride and contiguous allocation, while the shader assumes heads packed inside the KV stride; heads-outer q8_0/q4_0/iq4_nl caches and the MiniMax-M3 MSA batch view produced wrong attention output at default f16 KV. The guard now pins the layout, ten test-backend-ops cases cover it (the old guard fails 5 of them with errors of 1.5 to 1.9 against a 0.0005 tolerance; the fix passes all), and the repeat gates are unchanged. Standard layouts keep the fast path.

## Performance

4. The mul_mat_id q5_K/q4_K scale cache that bfc1eb47b (Jul 28) meant to disable was still compiled in on every build (an `#ifdef` guarding a macro defined as 0). Fixed with `#if`. Measured on Qwen3.6-35B-A3B UD-Q5_K_XL, same driver, 3 repetitions: pp512 at ub512 1400 to 1749 t/s (+25%), pp2048 at ub2048 1633 to 1789 t/s (+10%), decode unchanged. Models without q5_K/q4_K expert weights are unaffected.

## Performance summary (v0.7.4 vs v0.7.3, same driver, llama-bench, 3 repetitions, controls run back to back)

| model | depth | pp2048 v0.7.4 | pp2048 v0.7.3 | change | tg32 v0.7.4 | tg32 v0.7.3 | change |
|---|---|---|---|---|---|---|---|
| Qwen2.5-7B Q4_K_M (dense, ub256) | d0 | 1458.9 ± 0.8 | 1448.4 ± 14.9 | +0.7% | 47.9 ± 0.0 | 47.7 ± 0.2 | +0.4% |
| Qwen2.5-7B Q4_K_M (dense, ub256) | d16k | 866.5 ± 3.3 | 864.9 ± 4.9 | +0.2% | 39.6 ± 0.2 | 39.2 ± 0.1 | +1.1% |
| Qwen3.8-27B UD-Q4_K_XL (dense, ub256) | d16k | 304.7 ± 1.0 | 304.3 ± 0.8 | +0.2% | 11.6 ± 0.0 | 11.6 ± 0.0 | -0.1% |
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d0 | 440.1 ± 5.1 | 438.8 ± 4.8 | +0.3% | 32.5 ± 0.2 | 32.4 ± 0.2 | +0.4% |
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d16k | 352.4 ± 3.1 | 343.0 ± 0.9 | +2.8% | 26.1 ± 0.1 | 26.2 ± 0.2 | -0.4% |

Every cell is at parity within noise. The Flash-Next d16k control is the v0.7.3 cell measured earlier the same day (343.0 ± 0.9 pp, 26.2 tg), not back to back. The earlier candidate carried the fix inside the cm1 flash attention shader and lost 8 to 18% dense prefill at depth by the shader's mere presence (measured by isolation: not its executed work, not the guard, not the scale cache, not the build). That form is dropped; the shipped fix touches only the KV cache.

## Corrections to the v0.7.3 notes

- v0.7.3 did not fix the repeatability report; it fixed the progressive drift (missing upstream #27812) and reached upstream's own repeatability level at the reporter's shape.
- The remaining alternation was attributed to the bundled Mesa driver. That was wrong: it reproduces on stock Mesa 25.2.8 and on the bundled Mesa 26.3 inside the published container with an empty environment; the driver only changes which stale bytes are read.

## Gate changes (tools/repeat_gate.py, tools/prompts/, BUILD.md)

The previous repeatability prompt was one sentence repeated, whose continuation has almost no near-tie tokens; it read clean on a build that was not. The mandatory gate now runs real prose (a 1024 token WikiText article and a 31.7k token slice), 129 token continuations, a 32k prompt, `--subtoken 8` (compares the full per-position logprob streams and fails on any difference), and a pure-upstream control on the same box. Results for this build are in the validation section below; upstream master's are in the reproduction section.

## Reproducing the repeatability defects (upstream master included)

Both defects are visible with stock llama-server on gfx1151 with `-fa on`, one slot, greedy sampling, real text. The shape matters:

- Prompt length not a multiple of 256 tokens. The KV window is padded to 256, and the rows between the prompt's end and the pad hold the previous request's generation; a 1024-token article that tokenizes to 1045 leaves 235 such rows. A prompt that lands exactly on a multiple of 256 hides the defect during the prompt and only exposes it during decode.
- Continuation of 129 tokens or more, and at least 8 identical requests; 16 is what we run. On Qwen3.8 Flash-Next upstream master gives 3 to 6 distinct continuations of 16 at this shape (v0.7.3: 5 to 6).
- Dense f16 KV models rarely flip a token within 129 tokens. Request `n_probs` (we use 8) and compare the per-position logprob streams instead: on Qwen2.5-7B, upstream master returns identical tokens over 8 requests while every request after the first differs in logprobs from the first generated token on (top-token logprob -0.2150, -0.2044, -0.2060 across three full re-prefills of the same prompt, `cache_prompt` false and `--cache-ram 0`). A distinct-output count cannot see this form.
- The top-k order race needs Qwen3.8 Flash-Next and more than 2051 prompt tokens: with a 31.7k-token prompt and 4 identical requests of 48 tokens, upstream master gives 2 to 3 distinct continuations.

`tools/repeat_gate.py` does all of this (launches the server, sends N identical requests, compares tokens and logprob streams, exits non-zero on any difference); the prompts are in `tools/prompts/`:

```
python3 tools/repeat_gate.py --bin ./vulkan/llama-server --model <model.gguf> --reps 16 --predict 129 --subtoken 8 --prompt-file tools/prompts/prose-1024-wikitext.txt -- -ngl 99 -fa on -b 2048 -ub 512 -c 4096
python3 tools/repeat_gate.py --bin ./vulkan/llama-server --model <Qwen3.8-Flash-Next.gguf> --reps 4 --predict 48 --subtoken 8 --prompt-file tools/prompts/prose-32k-wikitext.txt -- -ngl 99 --n-cpu-moe 0 -fa on -b 2048 -ub 512 -c 33280
```

Expected on v0.7.4: `REPEAT GATE: PASS` and `SUBTOKEN GATE: QUIET` for both.

## Not changed

Numerics switches (`GGML_VK_FA_WAVE32`, the delta-net l2norm identity) are unchanged; they move bits relative to upstream, not correctness. The ragged-block QSA policy (the reference implementation's extra r - 1 slots) remains a recorded candidate for a later release.

## Where this work goes next

This is the last release cut from Nathanw1014/llama.cpp as the primary home of the Vulkan work. The stack (the Strix Halo Vulkan fixes, the Flash-Next and DeepSeek V4 paths, the repeatability gates) is moving to the halo-box community fork, halo-box/strix-llama.cpp, where it will be maintained with the other Strix Halo contributors; the commits are being staged there now with their original authorship. The toolbox and its portable bundle will track that fork. Issues and pull requests for the Vulkan stack should go to halo-box from here on.

## Credit

lhl (shisa.ai), for the repeatability report that set the shape we test at.

## Staging build validation (2026-09-03, take 6, local assemble)

Build: release/v0.7.4-staging ea35c5066, CI flags, assembled locally with the shipped v0.7.3 Mesa 26.3 driver. The CI artifact (dev build of the same commit) gets the same gates before promotion; those results replace this section in the release body.

Gates on the assembled launcher (16 identical greedy requests unless stated, per-position top-8 logprob streams compared):

- Qwen2.5-7B, 1024-token prompt, 129 tokens: 16/16 identical, logprob streams identical.
- Qwen3.8 Flash-Next, sweep (2 prompts x 6): identical.
- Qwen3.8 Flash-Next, 1024-token prompt, 129 tokens: 16/16 identical.
- Qwen3.8 Flash-Next, 32k prose prompt, 48 tokens x 4: identical.
- Clean room (the take-6 image, docker's empty environment, bundled driver only), Flash-Next 1024 x 16: identical.

Sanity bench on the assembled launcher, Qwen2.5-7B d0 ub256: pp2048 1441.9 ± 2.8, tg32 47.9 ± 0.2 (v0.7.3 bundle, same driver: 1453.1, 47.7).
