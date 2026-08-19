# DFlash2 speculative decoding on Strix Halo (gfx1151, Vulkan/RADV)

Measured 2026-08-19 on a Framework Desktop, Ryzen AI Max+ 395, Radeon 8060S (gfx1151), 64 GB unified memory, `amd_iommu=off`, Vulkan/RADV on a mesa-main devenv driver.

## What this is

[DFlash2](https://inco.ai/blog/dflash2/) is a block-diffusion speculative decoder: the drafter proposes a whole block in one forward pass, and v2 adds a 2-tap grouped dynamic depthwise convolution around each attention and FFN sublayer plus a candidate selector that scores adjacent token pairs over the drafter's top-16 candidates.

**Engine support is upstream [ggml-org/llama.cpp#27342](https://github.com/ggml-org/llama.cpp/pull/27342) by Jian Chen, and is not our work.** What is ours: cherry-picking it onto the Strix branch, validating it on gfx1151/Vulkan (688 `test-backend-ops` cases across the ops the new graph adds; the drafter runs fully GPU-resident, `graph splits = 2`, no CPU fallback), and the draft-width tuning below. Drafter weights are inco's own published GGUFs (`incoai/Qwen3.8-27B-DFlash2-GGUF`, Apache-2.0).

## Headline

- **DFlash2 holds about 2x over base at every depth measured** on this corpus: 2.23x at d0, 1.89x at 8k, 2.00x at 32k. Base decode is itself nearly flat (11.81 to 10.54 t/s), so this is about how draftable the text stays.

- **DFlash v1 collapses at depth where v2 does not.** v1 goes 1.79x -> 1.02x (d0 -> 32k), i.e. by 32k it is worth essentially nothing over base, while v2 still returns 2.00x. The conv and selector modules are doing real work exactly where the older drafter gives up.

- **Draft width matters at depth.** At 32k, width 4 gives 21.11 t/s against width 7's 16.32 = +29%. They tie at d0 and 8k. `--spec-draft-n-max 4` is the better default for long context.

## Results

Target: `unsloth/Qwen3.8-27B-GGUF` UD-Q4_K_XL, f16 KV. Tool: [llama-benchy](https://github.com/eugr/llama-benchy) 0.4.0, `--pp 512 --tg 128 --depth 0 8192 32768 --runs 2`, prompts drawn from a Project Gutenberg book so that acceptance reflects real prose rather than random tokens.

### Decode (tg128), tokens/s

*base (no spec decode)* = plain llama.cpp with no draft model and no speculative decoding, one token per forward pass. It is the baseline every speedup below is measured against, and on this box it is bandwidth-bound (11.81 t/s x 17.9 GB of weights is about 211 GB/s, near the memory ceiling), which is why it barely changes with depth.

| context depth | base (no spec decode) | DFlash v1 (n=5) | DFlash2 (n=4) | DFlash2 (n=7) |
|---|---|---|---|---|
| 0 | 11.81 ± 0.03 | 21.09 ± 1.72 | 26.39 ± 0.14 | 25.18 ± 2.49 |
| 8192 | 11.44 ± 0.01 | 12.87 ± 0.23 | 21.58 ± 2.35 | 21.46 ± 1.04 |
| 32768 | 10.54 ± 0.00 | 10.75 ± 0.05 | 21.11 ± 1.45 | 16.32 ± 2.12 |

### Speedup over base

| context depth | DFlash v1 (n=5) | DFlash2 (n=4) | DFlash2 (n=7) |
|---|---|---|---|
| 0 | 1.79x | 2.23x | 2.13x |
| 8192 | 1.12x | 1.89x | 1.88x |
| 32768 | 1.02x | 2.00x | 1.55x |

### Prefill (pp512), tokens/s

| context depth | base (no spec decode) | DFlash v1 (n=5) | DFlash2 (n=4) | DFlash2 (n=7) |
|---|---|---|---|---|
| 0 | 312.6 | 292.9 | 298.1 | 294.3 |
| 8192 | 356.1 | 340.2 | 343.3 | 341.8 |
| 32768 | 310.7 | 299.5 | 301.6 | 301.0 |

## Caveats worth reading before quoting these

- **This is prose.** Content changes the depth curve a lot. On a code-corpus prompt set the same DFlash2 config decayed about 47% from shallow to 32k; on this Gutenberg corpus it decays about 20%. Neither is wrong; they are different workloads. Do not quote one as "the" number.

- **The draft width optimum moves, and not only with depth.** On code continuation via raw completion, width 5-7 wins at ~1.3k. Through the chat template on the same code, where the model emits reasoning first, width 3 wins. At 32k on code, width 3 is worth ~22% over 7. Aggregate acceptance does not predict the optimum on its own: at ~0.33 acceptance the code family peaked at width 3 and the reasoning family at width 5. Tune per workload.

- **Prefill here uses the server default `-ub 512`.** On these weights `-ub 256` is the measured dense optimum (llama-bench pp2048: 314.4 at ub 256 vs 307.9 at 512 and 295.0 at 1024), so the `pp512` column sits a few percent below what the box can do.

- `--spec-draft-p-min` is a **silent no-op** for DFlash drafters (v1 and v2): the confidence-based truncation is gated on `is_dspark`. The flag is accepted and printed in the startup banner as if active.

- A **BF16 drafter is slower than Q8_0** at depth for identical acceptance. Use Q8_0.

- `q8_0` KV is free at shallow depth but costs 6-8% at depth here; these runs use f16 KV.

## Reproducing

```bash
llama-server --model Qwen3.8-27B-UD-Q4_K_XL.gguf --host 127.0.0.1 --port 8080 \
  -ngl 999 -c 40960 -fa on -ctk f16 -ctv f16 -np 1 --jinja \
  -md Qwen3.8-27B-DFlash2-Q8_0.gguf -ngld 999 \
  --spec-type draft-dflash --spec-draft-n-max 4
```

```bash
llama-benchy --base-url http://127.0.0.1:8080/v1 --model qwen38 \
  --tokenizer Qwen/Qwen3.8-27B --pp 512 --tg 128 --depth 0 8192 32768 --runs 2
```

Engine: fork branch `strix-halo-vulkan` at `015f09c8a` (upstream base `9f0d017`). Each arm is a fresh server launch holding an exclusive GPU lock.

## Raw tool output

Unedited `llama-benchy` tables for each arm are vendored under [`benchmarks/results/dflash2-20260819/`](../benchmarks/results/dflash2-20260819/):

| arm | file |
|---|---|
| base (no spec decode) | [`benchy-ar.md`](../benchmarks/results/dflash2-20260819/benchy-ar.md) |
| DFlash v1 (n=5) | [`benchy-v1.md`](../benchmarks/results/dflash2-20260819/benchy-v1.md) |
| DFlash2 (n=4) | [`benchy-n4.md`](../benchmarks/results/dflash2-20260819/benchy-n4.md) |
| DFlash2 (n=7) | [`benchy-n7.md`](../benchmarks/results/dflash2-20260819/benchy-n7.md) |

