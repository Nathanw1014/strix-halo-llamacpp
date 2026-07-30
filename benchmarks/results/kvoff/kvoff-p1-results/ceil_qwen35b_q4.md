| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1265.42 ± 4.10 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         58.05 ± 0.17 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   pp512 @ d4096 |      1135.75 ± 13.92 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         57.66 ± 0.06 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d16384 |       926.04 ± 13.33 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         55.17 ± 0.42 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d32768 |       738.58 ± 10.32 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         52.43 ± 0.78 |

build: 63f88cc (243)
