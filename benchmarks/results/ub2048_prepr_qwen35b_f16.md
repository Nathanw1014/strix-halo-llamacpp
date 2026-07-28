| model                          |       size |     params | backend    | ngl | n_ubatch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |          pp2048 |       1140.74 ± 1.72 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |            tg32 |         58.39 ± 0.34 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |  pp2048 @ d8192 |        979.34 ± 2.67 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |    tg32 @ d8192 |         53.73 ± 3.04 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d16384 |        857.04 ± 2.16 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d16384 |         52.64 ± 0.36 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d32768 |        595.78 ± 4.27 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d32768 |         47.84 ± 0.03 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 | pp2048 @ d65536 |        297.04 ± 1.58 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   1 |   tg32 @ d65536 |         41.73 ± 0.03 |

build: 8161641 (98)
