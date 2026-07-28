| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1203.19 ± 6.54 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         66.89 ± 0.86 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   pp512 @ d4096 |       895.91 ± 19.46 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         61.55 ± 0.39 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d16384 |        503.39 ± 6.45 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         52.74 ± 0.47 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d32768 |        322.32 ± 2.47 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         43.76 ± 0.21 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d65536 |        189.87 ± 1.93 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         33.31 ± 0.05 |

build: f69e4ea (276)
