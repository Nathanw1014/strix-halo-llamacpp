| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |          pp2048 |       1080.87 ± 3.65 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         90.83 ± 0.46 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 | pp2048 @ d32768 |        287.87 ± 0.53 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         46.84 ± 0.17 |

build: 305a43b (75)
