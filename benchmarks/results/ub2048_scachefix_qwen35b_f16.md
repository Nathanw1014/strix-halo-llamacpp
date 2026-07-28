| model                          |       size |     params | backend    | ngl | n_ubatch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |          pp2048 |       1296.47 ± 1.26 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |            tg32 |         57.99 ± 0.43 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |  pp2048 @ d8192 |        993.87 ± 5.32 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |    tg32 @ d8192 |         55.31 ± 0.15 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d16384 |        945.31 ± 6.76 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d16384 |         52.89 ± 0.11 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d32768 |        766.54 ± 3.53 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d32768 |         47.91 ± 0.15 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d65536 |        541.14 ± 2.68 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d65536 |         41.58 ± 0.08 |

build: 0b97626 (281)
