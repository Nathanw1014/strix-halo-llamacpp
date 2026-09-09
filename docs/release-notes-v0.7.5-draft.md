# v0.7.5 (draft, staging branch; not released)

Qwen3.8 Flash-Next long-context decode, Unsloth shared MTP heads, the DSpark prefill fix from upstream, and a hygiene change in the MoE expert GEMM. Base is v0.7.4.1 (5d8c07b44); release tree dff600487. Numbers are from Strix Halo (gfx1151), same driver, controls run back to back. 

## Performance

1. Qwen3.8 Flash-Next decode at depth (PR #9, firelzrd). The QSA indexer recomputed its pooled block keys for the whole context on every decode step, on every QSA layer, together with a per-layer host-side scan of the cell table and two copies that fed it. Five changes, all in how the graph is assembled and what the memory module keeps, no shader touched: one cell scan per compress ratio instead of one per layer (this is upstream's own code from the commit that added the model, which the fork's port had dropped); the block-mean slices are summed without a copy; the pooled keys live in a per-block cache and only the tail the current ubatch can reach is recomputed; and the two dead V allocations next to the indexer are narrowed (1.6 GiB at ctx 262144 with f16 KV). Output is not byte-identical to v0.7.4.1 on Vulkan: sharing one input set across the QSA layers changes the graph order the backend fuses over, and this backend's rounding is not invariant to that (v0.7.4's perplexity already moves about 0.2% with `-ub`). The change is rounding-sized (same candidate tokens, logprobs shifted by a few tenths at near-ties) and the quality gate is KL divergence against v0.7.4.1's logits on wikitext-2 with the previous build at `-ub 256` as the floor for what a harmless rounding change does to this model: at 4096 context, mean KLD 0.015 against a floor of 0.026 (96.3% vs 94.9% same top token); at 8192, 0.097 against a floor of 0.084 (91.5% vs 92.0%); perplexity unchanged at 4k and 2.2% lower at 8k. With the cache switched off the statistics are identical to the last digit, and a 64-token greedy continuation after an 8k prompt is byte-identical with the cache on and off, so the cache itself is bit-exact in prefill and in decode; under speculative decoding the verify batches take a different rounding path with the cache present, of the same size as changing the ubatch (the pre-PR build at `-ub 256` moves the same MTP run from 154 to 133 accepted drafts). Within-server repeatability is unchanged (all three Flash-Next repeat gates identical with identical logprob streams). Reporter's numbers on a 64 GB Strix Halo, UD-IQ4_XS, MTP n_max 3: 25.05 to 41.59 t/s at 131k (+66%), +21% at 32k, neutral at 8k and below; 2x RTX 3090 CUDA +13% at 131k. Ours, Q3KEXP f16 PLE, no MTP, llama-bench ub512, two launches per arm: tg32 32.3 to 32.5 t/s at d0 (parity), 28.3 to 30.5 at 8k (+8%), 21.5 to 28.9 at 32k (+35%); pp512 at 32k depth 173 to 274 t/s (+59%, the base's own runs scattered 133/212 where the candidate's did not).

   One correction on top of the series: the pooled-key cache is trusted only while a single sequence is present in the KV stream. With several sequences in one unified cache (llama-server's default when `-np` is auto: four slots, `--kv-unified`), blocks are numbered across sequences, so a second request in flight at the same time would shift the cache's rows under the first (sequential requests are not exposed: the default idle-slot clearing invalidates the cache). In that state the cache is rewritten in full every step, which is the previous behaviour; a single slot, or one slot per stream, keeps the whole gain. Measured with two slots on a unified cache and a 12k-token first conversation continued after a second one grew: the unfixed tree's continuation differs from its single-slot run, the fixed tree's is byte-identical.

   `LLAMA_QSA_POOL_CACHE=0` turns the pooled-key cache off (every block recomputed inline, the previous behaviour) for A/B or support.

   Not included from PR #9: dropping the 1/r scale before the RMS norm (2 ms of a 97 ms step at 131k). It moves the effective epsilon and is the one patch that changes output; this fork gates output changes on a KL-divergence measurement, and this one has not had it.

2. DSpark and every stateful drafter cost prefill by upstream design (about 190 ms per launch plus 55 to 70 us per prompt token on this box). Upstream #27310 folds the DFlash encoder into the KV injection decode (one `llama_decode` instead of `llama_encode` + `llama_decode`, no device-host-device round trip of the encoder output); ported, with #26756 (DeepSeek V4 rollback with several sequences) and #27711 (synthetic acceptance options for benchmarking, synthetic acceptance options for benchmarking). Output equivalence with the shipped fork was validated on 2026-09-06 (DSpark on the truncated V4-Flash, same md5, same acceptance). Re-checked on this release: token streams identical to v0.7.4.1 on four launches; with the DSpark drafter attached, prefill 598 to 698 t/s (+17%) at equal decode.

2b. Dense prefill on the f16-B path, on by default (`GGML_VK_DENSE_F16B` auto). The f32 activation operand of a quantized dense matmul is converted to f16 before the mul_mm dispatch when two measured conditions hold: the row width is an odd multiple of 1024 (the case where halving the row stride moves it off a memory-channel camp) and the weight rows carry at least 6144 bytes (the conversion's break-even). Fitted on 276 op-level cells: 42 engage, none regress (worst -0.04%, mean +4.1%). End to end, Qwen3.8-27B UD-Q4_K_XL prefill +4.9% at ub2048 and +1.7% at ub256, decode unchanged, perplexity identical chunk for chunk; Qwen2.5-7B and Qwen3.6-35B do not engage and measure parity (re-measured on the release tree: 27B +1.9% at ub256, +5.0% at ub2048, Qwen3.6 1630 vs 1635 t/s). `GGML_VK_DENSE_F16B=0` turns it off, `=1` forces it on for a model you have measured yourself.

## Added

3. Unsloth "shared" MTP heads for Qwen3.8 Flash-Next (`mtp-Qwen3.8-Flash-Next-shared-*.gguf`, toolbox issue #17). The draft head borrows the token embedding and LM head from the running target, so the 2.79 GB Q8_0 file loads in place of the 4.14 GB self-contained one. The shared head borrows the target's `output.weight`, which in UD-Q3_K_XL is Q6_K where the self-contained head carries Q8_0, so the two heads' drafts are close but not bit-identical; on the v0.7.4 tree they happened to produce the same stream and acceptance (154 of 176), on this tree they diverge at near-ties (133 of 182 vs 128 of 184 on the same prompt), which is within this model's run-to-run sensitivity to any rounding change. The memory fitter measures the shared head against a metadata-only target, so `--fit` budgets it. The self-contained files and the fork's older sidecars keep working.

## Changed

4. The mul_mat_id q4_K/q5_K scale-cache toggle (`MMID_QK_SCACHE`) is removed and the cache is keyed off `MUL_MAT_ID` directly. This is the toggle whose half-applied `#if` produced v0.7.4's repeated-token output on MoE q4_K/q5_K models (reverted in v0.7.4.1). No functional change: the preprocessed shader source is byte-identical to v0.7.4.1 for every q4_K/q5_K/q6_K/q8_0/f16 x mul_mat_id/dense configuration. The cache itself is a measured win (+5 to +8% pp512 at ub512, neutral to +2% at ub2048, 12 of 12 cells on Qwen3.6-35B UD-Q5_K_XL/UD-Q4_K_XL and Ornith-1.5-35B Q4_K_M), which corrects the July note that called it a loss.

5. The MTP hidden-state input is zeroed on token-only batches (four lines in llama-graph.cpp); it was uninitialised memory read by the draft graph on the first probe.

## Performance summary (v0.7.5 vs v0.7.4.1, same driver, llama-bench, 3 repetitions per launch, A B B A)

| model | depth | pp512 cand | pp512 base | change | tg32 cand | tg32 base | change |
|---|---|---|---|---|---|---|---|
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d0 | 388.4 | 393.4 | -1.3% | 32.5 | 32.3 | +0.5% |
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d8k | 378.7 | 379.3 | -0.1% | 30.5 | 28.3 | +7.8% |
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d32k | 274.2 | 172.8 | +59% | 28.9 | 21.5 | +35% |
| Qwen3.6-35B-A3B UD-Q5_K_XL (MoE, ub512) | d0 | 1386.5 | 1388.2 | -0.1% | 58.4 | 58.5 | -0.2% |
| Qwen3.6-35B-A3B UD-Q5_K_XL (MoE, pp2048 @ ub2048) | d0 | 1628.3 | 1631.6 | -0.2% | | | |
| DeepSeek V4-Flash trunc10 IQ3_XXS (ub2048) | d0 / 8k / 32k | 894 / 831 / 798 | 895 / 841 / 807 | -0.1 / -1.2 / -1.1% | 74.2 / 71.0 / 68.9 | 75.1 / 72.3 / 68.8 | -1.1 / -1.8 / +0.2% |

## Known and not in this release

- MTP speculative decoding on Qwen3.8 Flash-Next still runs through context checkpoints on this fork (`n_rs_seq = 0`; each checkpoint is the 48-layer recurrent state, 112 MiB), so every rejected round pays a restore. On a short code prompt with `--spec-draft-n-max 3` that makes MTP slower than plain decode here (10.5 vs 18.5 t/s at 76% acceptance); on prose it is a wash (19 vs 18.5). Upstream #28123 (recurrent-state rollback for qwen4exp) was tried on top of this release and changes nothing until the server requests rollback slots for the MTP draft; that wiring is the next item.

## Compatibility

- Slot-save files (`--slot-save-path`) written by v0.7.4 or earlier for Qwen3.8 Flash-Next do not restore into v0.7.5: the indexer cache's V is now one element wide, so the saved state has a different shape. The restore fails with a logged "mismatched value type" error and the load returns 0 (`llama_kv_cache::state_read_data` checks type, row size and GQA width per layer before touching the cache), so the server reports the slot as not restored and the request re-prefills. The in-process prompt cache is unaffected.

## Gates run on this build

- Backend ops on Vulkan0: MUL_MAT_ID 4833/4833, MUL_MAT 4962/4962, ADD 99/99, TOP_K 453/453, SET_ROWS 319/319, GET_ROWS 119/119, RMS_NORM 51/51, ROPE 448/448.
- MoE q4_K coherence (the v0.7.4.1 surface): Ornith-1.5-35B Q4_K_M 49 distinct words in 96 tokens, Qwen3.6-35B UD-Q4_K_XL 62; PASS.
- Qwen3.8 Flash-Next repeat gates: sweep x6, 1024-token prose x16 at 129 tokens (1 unique), 32k prose x4 (1 unique), `--subtoken 8`: PASS and QUIET on all three.
- PR #9 quality vs v0.7.4.1: KLD at 4k and 8k within the ubatch floor (item 1); pooled cache bit-exact in prefill and in a 64-token continuation after 8k, cache on vs off.
- Two-slot unified-cache control: unfixed tree differs on the continuation, release tree byte-identical to its single-slot run.
- Shared MTP head: loads, drafts and fits; acceptance within a few percent of the self-contained head (the borrowed output matrix is the target's quant, see item 3).
- DSpark on the truncated V4-Flash: token streams identical to v0.7.4.1, four launches.
- CPU: test-recurrent-state-rollback (3 variants), test-llama-archs: 5/5.

## Where this work goes next

The Vulkan work is moving to the halo-box community fork, halo-box/strix-llama.cpp, where it is maintained with the other Strix Halo contributors. The v0.7.4 correctness set is in their master (halo-box/strix-llama.cpp#20), the Vulkan performance stack is up as halo-box/strix-llama.cpp#17 with its original authorship, and the runtime changes behind this fork's Flash-Next numbers, this release's included, follow once #17 lands. Until that port is complete, this repository and the fork remain the place for issues and pull requests, and releases here continue; the toolbox and its portable bundle will track whichever tree carries the work once it has moved.

## Credit

firelzrd, for PR #9 (the pooled-key cache and the profiling that ranked it); Daniel Han, for the shared QSA input set (upstream #27742); Bushido76, for asking for the shared MTP heads (#17); upstream authors of #27310 (王金旭), #27711 (Gaurav Garg), #26756 (Aman Gupta).
