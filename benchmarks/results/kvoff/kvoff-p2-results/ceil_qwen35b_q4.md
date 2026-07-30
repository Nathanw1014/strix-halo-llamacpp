| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1267.68 ± 6.79 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         58.03 ± 0.07 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d65536 |        520.47 ± 6.27 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         48.42 ± 0.27 |

build: 63f88cc (243)
