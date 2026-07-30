| model                          |       size |     params | backend    | ngl | n_batch | n_ubatch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |    1024 |     1024 |   q8_0 |   q8_0 |   1 |          pp2048 |       1629.15 ± 4.89 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |    1024 |     1024 |   q8_0 |   q8_0 |   1 |            tg32 |         92.90 ± 0.01 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |    1024 |     1024 |   q8_0 |   q8_0 |   1 | pp2048 @ d32768 |        351.24 ± 2.09 |
| qwen3moe 30B.A3B Q4_K - Medium |  16.45 GiB |    30.53 B | Vulkan     |  99 |    1024 |     1024 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         51.34 ± 0.51 |

build: 63f88cc (243)
