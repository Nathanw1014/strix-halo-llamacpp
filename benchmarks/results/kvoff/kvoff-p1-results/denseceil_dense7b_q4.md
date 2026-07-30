| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |       1359.61 ± 5.05 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         46.41 ± 0.09 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   pp512 @ d4096 |       1096.45 ± 9.69 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         45.36 ± 0.06 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d16384 |       747.50 ± 14.97 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         42.46 ± 0.12 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d32768 |        523.34 ± 9.51 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         38.54 ± 0.05 |

build: 63f88cc (243)
