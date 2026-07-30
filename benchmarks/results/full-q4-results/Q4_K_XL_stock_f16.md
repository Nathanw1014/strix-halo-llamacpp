| model                          |       size |     params | backend    | ngl | n_ubatch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |          pp2048 |       1137.21 ± 2.09 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |            tg32 |         59.41 ± 2.23 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |  pp2048 @ d4096 |       1064.25 ± 5.06 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |    tg32 @ d4096 |         57.86 ± 2.06 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 | pp2048 @ d16384 |        864.23 ± 3.43 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |   tg32 @ d16384 |         53.50 ± 0.65 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 | pp2048 @ d32768 |        689.33 ± 1.24 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |   tg32 @ d32768 |         49.73 ± 0.07 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 | pp2048 @ d65536 |        464.77 ± 5.98 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |   tg32 @ d65536 |         42.56 ± 0.10 |

build: 5c3a586 (72)
