| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |           pp512 |       1214.73 ± 5.92 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         68.09 ± 0.05 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   pp512 @ d4096 |       898.68 ± 17.73 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |    tg32 @ d4096 |         60.88 ± 0.20 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d16384 |        505.66 ± 5.82 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d16384 |         51.07 ± 0.29 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d32768 |        322.63 ± 1.19 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         42.61 ± 0.44 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d65536 |        191.28 ± 1.21 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d65536 |         31.50 ± 0.14 |

build: f69e4ea (276)
