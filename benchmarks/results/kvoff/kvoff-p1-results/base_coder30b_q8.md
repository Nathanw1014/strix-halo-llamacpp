| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |           pp512 |       1133.56 ± 5.82 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         67.98 ± 0.05 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   pp512 @ d4096 |       771.56 ± 17.68 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |    tg32 @ d4096 |         60.90 ± 0.52 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d16384 |        384.10 ± 7.81 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d16384 |         50.55 ± 0.21 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d32768 |        230.21 ± 1.47 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         42.12 ± 0.49 |

build: 5c3a586 (72)
