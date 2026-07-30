| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |           pp512 |       1353.38 ± 4.92 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |            tg32 |         46.78 ± 0.16 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d32768 |        522.63 ± 4.17 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d32768 |         38.04 ± 0.24 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |  pp512 @ d65536 |        328.84 ± 3.57 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q8_0 |   q8_0 |   1 |   tg32 @ d65536 |         32.12 ± 0.11 |

build: 63f88cc (243)
