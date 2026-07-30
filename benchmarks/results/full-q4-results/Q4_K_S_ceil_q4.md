| model                          |       size |     params | backend    | ngl | n_ubatch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |          pp2048 |       1311.01 ± 1.29 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |            tg32 |         63.80 ± 0.45 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |  pp2048 @ d4096 |      1197.99 ± 11.94 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         61.97 ± 0.21 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 | pp2048 @ d16384 |        980.45 ± 5.59 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         60.11 ± 0.46 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 | pp2048 @ d32768 |        767.01 ± 3.50 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         57.32 ± 0.77 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 | pp2048 @ d65536 |        532.93 ± 1.22 |
| qwen35moe 35B.A3B Q4_K - Small |  19.45 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         52.76 ± 0.73 |

build: 63f88cc (243)
