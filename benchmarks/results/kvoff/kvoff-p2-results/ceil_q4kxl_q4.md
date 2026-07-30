| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1369.63 ± 4.31 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         60.49 ± 0.17 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d65536 |       535.76 ± 11.85 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         50.44 ± 0.32 |

build: 63f88cc (243)
