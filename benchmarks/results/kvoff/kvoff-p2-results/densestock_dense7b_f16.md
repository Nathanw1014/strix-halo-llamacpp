| model                          |       size |     params | backend    | ngl | n_batch |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | --: | --------------: | -------------------: |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |           pp512 |       1357.19 ± 1.25 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |            tg32 |         47.54 ± 0.07 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |  pp512 @ d65536 |        171.93 ± 1.18 |
| qwen2 7B Q4_K - Medium         |   4.36 GiB |     7.62 B | Vulkan     |  99 |     512 |   1 |   tg32 @ d65536 |         26.27 ± 0.03 |

build: 5c3a586 (72)
