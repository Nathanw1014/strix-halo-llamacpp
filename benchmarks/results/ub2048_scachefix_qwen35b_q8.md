| model                          |       size |     params | backend    | ngl | n_ubatch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |          pp2048 |       1288.86 ± 0.50 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |            tg32 |         58.09 ± 0.27 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |  pp2048 @ d8192 |       1095.84 ± 4.49 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |    tg32 @ d8192 |         56.57 ± 0.14 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 | pp2048 @ d16384 |        958.54 ± 6.44 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |   tg32 @ d16384 |         54.75 ± 0.12 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 | pp2048 @ d32768 |        764.44 ± 6.24 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         51.67 ± 0.41 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 | pp2048 @ d65536 |        539.34 ± 1.14 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |   tg32 @ d65536 |         47.17 ± 0.17 |

build: 0b97626 (281)
