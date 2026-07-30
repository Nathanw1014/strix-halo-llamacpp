| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1369.66 ± 3.08 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         60.61 ± 0.52 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   pp512 @ d4096 |      1235.50 ± 16.32 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         60.00 ± 0.28 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d16384 |       987.60 ± 23.21 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         57.63 ± 0.22 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d32768 |       766.67 ± 12.92 |
| qwen35moe 35B.A3B Q4_K - Medium |  20.81 GiB |    34.66 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         54.95 ± 0.45 |

build: 63f88cc (243)
