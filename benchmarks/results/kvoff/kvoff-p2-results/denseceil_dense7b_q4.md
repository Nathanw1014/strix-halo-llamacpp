| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1356.27 ± 3.11 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         46.47 ± 0.25 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d65536 |        327.54 ± 3.99 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d65536 |         33.21 ± 0.02 |

build: 63f88cc (243)
