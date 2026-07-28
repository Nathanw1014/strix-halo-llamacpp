| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |           pp512 |       1265.19 ± 6.07 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         57.87 ± 0.10 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   pp512 @ d4096 |      1140.45 ± 15.63 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |    tg32 @ d4096 |         57.31 ± 0.11 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d16384 |       916.18 ± 12.51 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d16384 |         54.83 ± 0.21 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d32768 |       737.19 ± 19.09 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         51.82 ± 0.42 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d65536 |        521.39 ± 8.00 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d65536 |         47.47 ± 0.12 |

build: f69e4ea (276)
