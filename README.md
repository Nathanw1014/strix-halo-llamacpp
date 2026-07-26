# Strix Halo llama.cpp toolbox (FA + MoE-prefill fixes)

A ready-to-run llama.cpp for AMD Strix Halo (Ryzen AI Max+ 395 / Radeon 8060S / gfx1151),
tuned for **long-context, quantized-KV** workloads. It bundles a set of Flash-Attention and
MoE-prefill fixes plus a current GPU driver, so quantized KV cache is fast instead of a penalty.

The measurements behind these fixes (matrices, methodology, raw data) live in the companion
evidence pack.

## What's inside

- **`vulkan/`** self-contained Vulkan/RADV build (recommended default backend on this hardware).
  Bundles **Mesa 26.3.0-devel RADV** + **libdrm 2.4.133**, so it does not use or need the host
  Mesa. Runs directly on the host with just the Vulkan loader and `/dev/dri`.
- **`hip/`** ROCm/HIP build carrying the quantized-KV decode fix. Needs the ROCm runtime, so it
  ships as a container image (`Dockerfile.hip`).

## Getting the binaries

The binaries and bundled driver (~200 MB) are shipped via GitHub Releases (the portable Vulkan tarball)
and a container registry, not tracked in git. To build from source instead, see **[BUILD.md](BUILD.md)**
and run `build-from-source.sh`. The commands below assume the `vulkan/` dir is populated.

## The fixes

- **Vulkan: dequantize KV once in the FA kernel (prefill).** Quantized KV was re-dequantized on
  every FA pass; now it is dequantized once into a transposed scratch and reused. This is what
  makes quantized-KV **prefill** fast at depth (up to 2.66x f16 on head-dim-128 models).
- **Vulkan: mmid row-list prepass (MoE prefill).** Removes the redundant per-workgroup expert-ID
  scan in `MUL_MAT_ID`. Model-dependent: large on some MoEs, small on others.
- **HIP: dequantize KV on load in the tile FA kernel (decode).** Routes quantized decode through
  the tile kernel (dequant once, batched across GQA heads) instead of the vec kernel that repeats
  the dequant per query head. Fixes quantized-KV **decode** at depth on ROCm.

## Quickstart

### Portable (Vulkan, no container)
```
./vulkan/llama-server -m /path/to/MODEL.gguf -ngl 99 -fa 1 --host 0.0.0.0 --port 8080
./vulkan/llama-bench  -m /path/to/MODEL.gguf -ngl 99 -fa 1 -p 512 -n 32 -d 0,32768
```
Requires the Vulkan loader (`libvulkan1`) and read access to `/dev/dri`. Everything else
(driver, libdrm, ggml libs) is bundled.

### Container (Vulkan)
```
docker build -t strix-fa-vulkan -f Dockerfile.vulkan .
docker run --rm --device /dev/dri -v /path/to/models:/models -p 8080:8080 \
  strix-fa-vulkan -m /models/MODEL.gguf -ngl 99 -fa 1 --host 0.0.0.0
```

### Container (HIP / ROCm, decode fix)
```
docker build -t strix-fa-hip -f Dockerfile.hip .
docker run --rm --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render --security-opt seccomp=unconfined \
  -v /path/to/models:/models -p 8080:8080 \
  strix-fa-hip -m /models/MODEL.gguf -ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 --host 0.0.0.0
```

### distrobox / toolbox (interactive)

The images carry the `com.github.containers.toolbox=true` label and a toolbox-friendly base, so they
drop into the same workflow as the other Strix Halo toolboxes. GPU (`/dev/dri`) and your home dir are
passed through automatically; the binaries are on `PATH` and the wrapper sets the driver + mmid env, so
they "just work" from the shell.

**distrobox** (podman or docker backend):
```
distrobox create --name strix-fa --image <registry>/strix-fa-vulkan
distrobox enter strix-fa
# then, inside:
llama-server -m ~/models/MODEL.gguf -ngl 99 -fa 1 -ctk q4_0 -ctv q4_0 --host 0.0.0.0
llama-bench  -m ~/models/MODEL.gguf -ngl 99 -fa 1 -p 512 -n 32 -d 0,32768
```

**toolbox** (Fedora / immutable distros):
```
toolbox create strix-fa --image <registry>/strix-fa-vulkan
toolbox enter strix-fa
llama-server -m ~/models/MODEL.gguf -ngl 99 -fa 1 --host 0.0.0.0
```

For the HIP image use `strix-fa-hip` the same way (it still needs `/dev/kfd`, which distrobox/toolbox
pass through along with `/dev/dri`).

## Recommended flags

- `-fa 1` always (Flash-Attention on).
- **Long context: use q4_0 KV** (`-ctk q4_0 -ctv q4_0`). It is the smallest footprint (about 1/4
  of f16) and, with these fixes, the fastest at depth for both prefill and decode. Use `q8_0` if
  you want a little more KV quality; use `f16` only for short prompts where it does not matter.
- **mmid** MoE-prefill flags are ON by default in the Vulkan wrapper
  (`GGML_VK_MMID_ROWLISTS/SMALLN/BM64/WAVE32`). To turn them off, set any to `0` before running.
  `GGML_VK_MMID_F16B` is **on by default** (this is a squeeze-everything build; it is safe and gives
  a small gain on some MoEs like the 35B, neutral elsewhere). Disable it with `GGML_VK_MMID_F16B=0`.
  An earlier abort on the experimental `Q2_0` type has been fixed (it now falls back to the standard path).

## Numbers (measured on this box, r=3, services stopped)

- **Qwen3-Coder-30B-A3B** (head-dim 128), prefill at 64k: **2.66x** f16 with q4 KV + fixes.
- **Qwen3.6-35B-A3B** (head-dim 256), 64k: **+12% prefill, +18% decode** vs stock f16, at 1/4 the
  KV memory. Decode independently matches the best public f16 numbers on the same model.
- The prefill win scales with context depth and is largest on head-dim-128 GQA MoE models.

## Toolchain

- GPU driver: Mesa 26.3.0-devel (RADV), built with libdrm 2.4.133, shader compiler shaderc v2026.3-dev.
- llama.cpp: recent master with the fixes applied. HIP build on ROCm 7.2.4.

## Notes and caveats

- Vulkan is the recommended default on this hardware; the HIP image is for quantized-KV
  decode-at-depth on ROCm specifically.
- mmid is model-dependent (large on some MoEs, near-zero on others).
- Numbers are single-box measurements; reproduce with the bundled `llama-bench`.
