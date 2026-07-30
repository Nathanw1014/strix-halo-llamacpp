| model                          |       size |     params | backend    | ngl | n_ubatch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |          pp2048 |       1136.56 ± 4.47 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |            tg32 |         63.52 ± 0.58 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |  pp2048 @ d4096 |      1072.88 ± 10.30 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |    tg32 @ d4096 |         60.71 ± 0.35 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 | pp2048 @ d16384 |        890.19 ± 3.58 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |   tg32 @ d16384 |         56.43 ± 0.04 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 | pp2048 @ d32768 |        710.31 ± 1.27 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |   tg32 @ d32768 |         51.56 ± 0.06 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 | pp2048 @ d65536 |        463.97 ± 6.85 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   1 |   tg32 @ d65536 |         44.10 ± 0.42 |

build: 5c3a586 (72)
