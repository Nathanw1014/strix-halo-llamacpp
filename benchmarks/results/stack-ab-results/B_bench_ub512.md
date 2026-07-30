| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |          pp2048 |       1482.07 ± 6.91 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         92.97 ± 0.07 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 | pp2048 @ d32768 |        337.48 ± 0.88 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         50.61 ± 0.25 |

build: 63f88cc (243)
