| model                          |       size |     params | backend    | ngl | n_ubatch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |          pp2048 |       1034.89 ± 1.11 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |            tg32 |         58.34 ± 0.20 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |  pp2048 @ d8192 |        895.71 ± 3.60 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |    tg32 @ d8192 |         55.02 ± 0.19 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d16384 |        793.31 ± 9.01 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d16384 |         50.71 ± 2.76 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d32768 |        655.49 ± 6.46 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d32768 |         47.80 ± 0.32 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d65536 |        537.48 ± 0.40 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d65536 |         41.55 ± 0.29 |

build: f69e4ea (276)
