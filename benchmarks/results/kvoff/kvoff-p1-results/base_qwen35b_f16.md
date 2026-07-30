| model                          |       size |     params | backend    | ngl | n_batch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |           pp512 |       1060.14 ± 9.59 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |            tg32 |         57.43 ± 0.51 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   pp512 @ d4096 |       960.85 ± 10.40 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |    tg32 @ d4096 |         56.10 ± 0.97 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d16384 |       804.53 ± 11.96 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d16384 |         51.65 ± 0.17 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d32768 |       658.43 ± 13.18 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d32768 |         48.12 ± 0.19 |

build: 5c3a586 (72)
