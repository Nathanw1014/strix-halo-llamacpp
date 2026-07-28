| model                          |       size |     params | backend    | ngl | n_batch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | --: | --------------: | -------------------: |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |           pp512 |      1224.67 ± 10.97 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |            tg32 |         57.25 ± 0.31 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   pp512 @ d4096 |       1122.18 ± 8.56 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |    tg32 @ d4096 |         55.87 ± 0.63 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d16384 |       920.90 ± 17.83 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d16384 |         52.19 ± 0.22 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d32768 |       731.61 ± 14.46 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d32768 |         47.80 ± 0.09 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d65536 |        523.79 ± 5.77 |
| qwen35moe 35B.A3B Q5_K - Medium |  24.76 GiB |    34.66 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d65536 |         41.53 ± 0.19 |

build: f69e4ea (276)
