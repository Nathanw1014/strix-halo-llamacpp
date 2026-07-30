| model                          |       size |     params | backend    | ngl | n_batch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | --: | --------------: | -------------------: |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |           pp512 |       1361.48 ± 5.21 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |            tg32 |         47.66 ± 0.19 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |   pp512 @ d4096 |       1095.95 ± 1.98 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |    tg32 @ d4096 |         44.89 ± 0.21 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d16384 |        613.71 ± 1.58 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d16384 |         39.12 ± 0.08 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d32768 |        358.09 ± 3.05 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d32768 |         33.65 ± 0.03 |

build: 5c3a586 (72)
