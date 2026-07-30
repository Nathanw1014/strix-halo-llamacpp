| model                          |       size |     params | backend    | ngl | n_batch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | -----: | -----: | --: | --------------: | -------------------: |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |           pp512 |      1151.47 ± 11.05 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |            tg32 |         67.08 ± 0.94 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   pp512 @ d4096 |       873.79 ± 20.65 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |    tg32 @ d4096 |         60.99 ± 0.29 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d16384 |        496.58 ± 6.02 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d16384 |         52.81 ± 0.65 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |  pp512 @ d32768 |        317.58 ± 2.66 |
| qwen3moe 30B.A3B Q6_K          |  24.53 GiB |    30.53 B | Vulkan     |  99 |     512 |   q4_0 |   q4_0 |   1 |   tg32 @ d32768 |         43.57 ± 0.03 |

build: 63f88cc (243)
