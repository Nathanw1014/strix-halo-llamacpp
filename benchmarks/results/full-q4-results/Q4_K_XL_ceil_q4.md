| model                          |       size |     params | backend    | ngl | n_ubatch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |          pp2048 |       1281.57 ± 1.22 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |            tg32 |         60.42 ± 0.36 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |  pp2048 @ d4096 |       1163.58 ± 9.52 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         59.60 ± 0.17 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 | pp2048 @ d16384 |        946.77 ± 7.18 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         57.41 ± 0.30 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 | pp2048 @ d32768 |        745.80 ± 2.82 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         55.15 ± 0.09 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 | pp2048 @ d65536 |        521.86 ± 2.11 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     1024 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         50.25 ± 0.72 |

build: 63f88cc (243)
