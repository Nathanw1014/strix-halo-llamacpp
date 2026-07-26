| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1099.14 ± 4.98 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         68.09 ± 0.20 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   pp512 @ d4096 |       729.43 ± 15.59 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         60.28 ± 0.48 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d16384 |        367.76 ± 3.94 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         51.83 ± 0.72 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d32768 |        224.31 ± 2.67 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         43.38 ± 0.19 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d65536 |        125.74 ± 1.19 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         32.66 ± 0.12 |

build: 5c3a586 (72)
