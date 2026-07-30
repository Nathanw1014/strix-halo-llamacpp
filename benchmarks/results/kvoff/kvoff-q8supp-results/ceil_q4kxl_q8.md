| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |           pp512 |       1368.45 ± 3.31 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         60.22 ± 0.09 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d32768 |       776.18 ± 16.54 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         53.51 ± 0.70 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d65536 |        537.41 ± 9.49 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d65536 |         49.25 ± 0.07 |

build: 63f88cc (243)
