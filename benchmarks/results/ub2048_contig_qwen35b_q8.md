| model                          |       size |     params | backend    | ngl | n_ubatch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |          pp2048 |       1009.70 ± 2.20 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |            tg32 |         58.13 ± 0.16 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |  pp2048 @ d8192 |        908.23 ± 3.49 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |    tg32 @ d8192 |         56.41 ± 0.18 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 | pp2048 @ d16384 |        794.76 ± 5.01 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |   tg32 @ d16384 |         54.30 ± 0.78 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 | pp2048 @ d32768 |        728.22 ± 4.42 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         51.20 ± 0.13 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 | pp2048 @ d65536 |        482.22 ± 5.03 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     2048 |   q8_0 |   q8_0 |   1 |   tg32 @ d65536 |         45.88 ± 0.35 |

build: f69e4ea (276)
