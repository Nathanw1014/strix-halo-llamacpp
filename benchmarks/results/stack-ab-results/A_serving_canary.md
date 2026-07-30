| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |          pp2048 |       1086.18 ± 3.89 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         91.66 ± 0.33 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 | pp2048 @ d32768 |        287.62 ± 0.33 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         47.33 ± 0.09 |

build: 305a43b (75)
