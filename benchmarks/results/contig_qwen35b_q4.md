| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1264.91 ± 7.00 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         57.91 ± 0.21 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   pp512 @ d4096 |      1143.54 ± 15.84 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         57.53 ± 0.17 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d16384 |       921.93 ± 10.94 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         55.17 ± 0.17 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d32768 |       736.71 ± 14.32 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         52.39 ± 0.33 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d65536 |       520.66 ± 13.00 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         48.85 ± 0.30 |

build: f69e4ea (276)
