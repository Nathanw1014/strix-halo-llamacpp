# HIP / ROCm backend

The HIP build carries the quantized-KV **decode** fix (tile dequant-on-load). It needs the ROCm runtime,
so it is used via the container image, not the portable dir.

Binaries (`bin/`) are git-ignored; populate them with `../build-from-source.sh` (set `HIP_BUILD`) or a
release, then build `../Dockerfile.hip`. Vulkan is the recommended default backend on this hardware; use
HIP specifically for quantized-KV decode-at-depth on ROCm.
