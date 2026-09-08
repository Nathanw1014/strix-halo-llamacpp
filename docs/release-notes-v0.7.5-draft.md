# v0.7.5 (draft, staging branch; not released)

Qwen3.8 Flash-Next long-context decode, Unsloth shared MTP heads, the DSpark prefill fix from upstream, and a hygiene change in the MoE expert GEMM. Base is v0.7.4.1 (5d8c07b44). Numbers are from Strix Halo (gfx1151), same driver, controls run back to back. [PENDING: every number below is filled from take-1 gates and perf; search PENDING before posting.]

## Performance

1. Qwen3.8 Flash-Next decode at depth (PR #9, firelzrd). The QSA indexer recomputed its pooled block keys for the whole context on every decode step, on every QSA layer, together with a per-layer host-side scan of the cell table and two copies that fed it. Five changes, all in how the graph is assembled and what the memory module keeps, no shader touched: one cell scan per compress ratio instead of one per layer (this is upstream's own code from the commit that added the model, which the fork's port had dropped); the block-mean slices are summed without a copy; the pooled keys live in a per-block cache and only the tail the current ubatch can reach is recomputed; and the two dead V allocations next to the indexer are narrowed (1.6 GiB at ctx 262144 with f16 KV). Output is bit-exact against v0.7.4.1 [PENDING: exactness cells at 8k and 32k, logprob streams]. Reporter's numbers on a 64 GB Strix Halo, UD-IQ4_XS, MTP n_max 3: 25.05 to 41.59 t/s at 131k (+66%), +21% at 32k, neutral at 8k and below; 2x RTX 3090 CUDA +13% at 131k. Ours, Q3KEXP f16 PLE, no MTP: [PENDING fn d8k/d32k tg32 base vs cand].

   One correction on top of the series: the pooled-key cache is trusted only while a single sequence is present in the KV stream. With several sequences in one unified cache (llama-server's default when `-np` is auto: four slots, `--kv-unified`), blocks are numbered across sequences, so a second conversation would shift the cache's rows under the first. In that state the cache is rewritten in full every step, which is the previous behaviour; a single slot, or one slot per stream, keeps the whole gain. [PENDING: two-slot control: unfixed tree DIFF, fixed tree SAME.]

   Not included from PR #9: dropping the 1/r scale before the RMS norm (2 ms of a 97 ms step at 131k). It moves the effective epsilon and is the one patch that changes output; this fork gates releases on bit-exactness against the previous build.

2. DSpark and every stateful drafter cost prefill by upstream design (about 190 ms per launch plus 55 to 70 us per prompt token on this box). Upstream #27310 folds the DFlash encoder into the KV injection decode (one `llama_decode` instead of `llama_encode` + `llama_decode`, no device-host-device round trip of the encoder output); ported, with #26756 (DeepSeek V4 rollback with several sequences) and #27711 (synthetic acceptance options for benchmarking, `--spec-draft-*` [PENDING flag names]). Output equivalence with the shipped fork was validated on 2026-09-06 (DSpark on the truncated V4-Flash, same md5, same acceptance). [PENDING: dspark cell BASE vs CAND.]

## Added

3. Unsloth "shared" MTP heads for Qwen3.8 Flash-Next (`mtp-Qwen3.8-Flash-Next-shared-*.gguf`, toolbox issue #17). The draft head borrows the token embedding and LM head from the running target, so the 2.79 GB Q8_0 file loads in place of the 4.14 GB self-contained one. Same weights, same drafts: byte-identical stream at temperature 0 and the same acceptance (154 of 176) as the self-contained head [PENDING: re-confirmed on the release tree]. The memory fitter measures the shared head against a metadata-only target, so `--fit` budgets it. The self-contained files and the fork's older sidecars keep working.

## Changed

4. The mul_mat_id q4_K/q5_K scale-cache toggle (`MMID_QK_SCACHE`) is removed and the cache is keyed off `MUL_MAT_ID` directly. This is the toggle whose half-applied `#if` produced v0.7.4's repeated-token output on MoE q4_K/q5_K models (reverted in v0.7.4.1). No functional change: the preprocessed shader source is byte-identical to v0.7.4.1 for every q4_K/q5_K/q6_K/q8_0/f16 x mul_mat_id/dense configuration. The cache itself is a measured win (+5 to +8% pp512 at ub512, neutral to +2% at ub2048, 12 of 12 cells on Qwen3.6-35B UD-Q5_K_XL/UD-Q4_K_XL and Ornith-1.5-35B Q4_K_M), which corrects the July note that called it a loss.

5. The MTP hidden-state input is zeroed on token-only batches (four lines in llama-graph.cpp); it was uninitialised memory read by the draft graph on the first probe.

## Performance summary (v0.7.5 vs v0.7.4.1, same driver, llama-bench, 3 repetitions per launch, A B B A)

| model | depth | pp512 cand | pp512 base | change | tg32 cand | tg32 base | change |
|---|---|---|---|---|---|---|---|
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d0 | PENDING | | | | | |
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d8k | PENDING | | | | | |
| Qwen3.8 Flash-Next Q3KEXP (MoE, ub512) | d32k | PENDING | | | | | |
| Qwen3.6-35B-A3B UD-Q5_K_XL (MoE, ub512 / ub2048) | d0 | PENDING | | | | | |

## Compatibility

- Slot-save files (`--slot-save-path`) written by v0.7.4 or earlier for Qwen3.8 Flash-Next do not restore into v0.7.5: the indexer cache's V is now one element wide, so the saved state has a different shape. [PENDING: verify the restore fails cleanly rather than crashing.] The in-process prompt cache is unaffected.

## Gates run on this build

- Backend ops: MUL_MAT_ID, MUL_MAT, ADD, TOP_K, SET_ROWS, GET_ROWS, RMS_NORM, ROPE on Vulkan0. [PENDING]
- MoE q4_K coherence (the v0.7.4.1 surface): Ornith-1.5-35B Q4_K_M, Qwen3.6-35B UD-Q4_K_XL. [PENDING]
- Qwen3.8 Flash-Next repeat gates: sweep x6, 1024-token prose x16 at 129 tokens, 32k prose x4, `--subtoken 8`. [PENDING]
- PR #9 exactness vs v0.7.4.1 at 8k and 32k, tokens and logprob streams. [PENDING]
- Two-slot unified-cache control (unfixed tree must differ, release tree must match). [PENDING]
- Shared MTP head parity (self-contained vs shared, sha + acceptance). [PENDING]
- DSpark truncated V4-Flash equivalence vs v0.7.4.1. [PENDING]
- CPU: test-recurrent-state-rollback (3 variants), test-llama-archs: 5/5.

## Credit

firelzrd, for PR #9 (the pooled-key cache and the profiling that ranked it); Daniel Han, for the shared QSA input set (upstream #27742); Bushido76, for asking for the shared MTP heads (#17); upstream authors of #27310 (王金旭), #27711 (Gaurav Garg), #26756 (Aman Gupta).
