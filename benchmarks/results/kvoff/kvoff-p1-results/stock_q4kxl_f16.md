| model                          |       size |     params | backend    | ngl | n_batch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |           pp512 |        950.42 ± 9.06 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |            tg32 |         59.53 ± 0.67 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   pp512 @ d4096 |        869.48 ± 5.11 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |    tg32 @ d4096 |         57.10 ± 0.33 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d16384 |       760.66 ± 10.06 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d16384 |         53.54 ± 0.92 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d32768 |       643.66 ± 11.82 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d32768 |         48.90 ± 0.44 |

build: 5c3a586 (72)
