| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |           pp512 |       1274.12 ± 6.20 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         58.14 ± 0.10 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   pp512 @ d4096 |      1147.80 ± 12.98 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |    tg32 @ d4096 |         57.23 ± 0.21 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d16384 |       927.52 ± 14.36 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d16384 |         54.71 ± 0.24 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d32768 |        730.28 ± 9.35 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         52.26 ± 0.65 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d65536 |        524.44 ± 9.23 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d65536 |         47.12 ± 0.05 |

build: 0b97626 (281)
