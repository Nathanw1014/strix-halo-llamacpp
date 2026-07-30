# Building the toolbox from source

The released binaries/images are built from the pieces below. `build-from-source.sh` assembles the
toolbox once you have these three (four with HIP) build outputs. This file documents how to produce them.

## Toolchain that matters

- **Shader compiler: a current `glslc`** (shaderc ~v2026.x). The distro `glslc` (shaderc 2023.8) compiles
  successfully but emits different SPIR-V and produces non-comparable, sometimes slower shaders. Build shaderc
  from source or use a current SDK, and pass it as `-DVulkan_GLSLC_EXECUTABLE=`.
- **Vulkan headers with SPIRV headers** on the include path (recent llama.cpp uses the `spv::` namespace).
  Point CMake at a headers dir that has both `vulkan/` and `spirv/`, via `-DVulkan_INCLUDE_DIR=`.

## 1. libdrm (recent)

Mesa main needs libdrm >= 2.4.133. Build it with `--prefix=/usr` and stage the install elsewhere
with `DESTDIR`:
```
# from the libdrm source (dri.freedesktop.org or the mesa libdrm.wrap)
meson setup _build --prefix=/usr --libdir=lib -Dbuildtype=release -Damdgpu=enabled -Dradeon=enabled
ninja -C _build
DESTDIR=$PWD/stage ninja -C _build install
# -> LIBDRM_DIR = $PWD/stage/usr/lib
```
**Use `--prefix=/usr`, not a local prefix.** libdrm compiles the path to `amdgpu.ids` (the GPU
marketing-name table) in at build time and looks it up at exactly that absolute path. A local
prefix bakes in a build-machine path that will not exist on a user's box, so every run prints
`.../amdgpu.ids: No such file or directory` and the device name comes back unqualified.
`/usr/share/libdrm/amdgpu.ids` is where distro `libdrm-common` puts it, so it resolves on the
host; the Vulkan container installs `libdrm-common` for the same reason.

## 2. Mesa RADV (compute-only)

```
git clone https://gitlab.freedesktop.org/mesa/mesa.git && cd mesa
PKG_CONFIG_PATH=<LIBDRM_DIR>/pkgconfig meson setup build-rel \
  -Dvulkan-drivers=amd -Dgallium-drivers= -Dllvm=disabled \
  -Dplatforms= -Dvideo-codecs= -Dbuildtype=release -Dwerror=false
ninja -C build-rel
# -> MESA_ICD_DIR = mesa/build-rel/src/amd/vulkan   (has libvulkan_radeon.so)
```

## 3. llama.cpp Vulkan (the fixes)

Check out the combined Strix Halo branch **`strix-halo-vulkan`** of the fork (dequant-once + all-quant
transpose + the full mmid stack — this is the complete Vulkan stack the toolbox ships), then build:
```
git clone https://github.com/Nathanw1014/llama.cpp && cd llama.cpp && git checkout strix-halo-vulkan
cmake -B build-vk -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF \
  -DVulkan_INCLUDE_DIR=<headers-with-vulkan-and-spirv> \
  -DVulkan_GLSLC_EXECUTABLE=<current-glslc>
cmake --build build-vk --target llama-server llama-cli llama-bench -j
# -> VK_BUILD = build-vk
```

The per-fix branches live in the llama.cpp fork (each is an independent upstream candidate):
`vulkan-coopmat1-fa-dequant-transpose` (PR #25494), `vulkan-mmid-rowlists`, `fa-tile-dequant-on-load` (HIP).

## 4. llama.cpp HIP (optional, decode fix)

Build the `fa-tile-dequant-on-load` branch inside a ROCm dev image (e.g. `rocm/dev-ubuntu-24.04:7.2.4`)
targeting gfx1151:
```
cmake --build build-hip --target llama-server llama-cli llama-bench -j
# -> HIP_BUILD = build-hip
```

> **The ICD manifest needs `api_version`.** `build-from-source.sh` writes
> `vulkan/driver/radeon_icd.x86_64.json` with a relative `library_path` and copies `api_version`
> out of Mesa's own generated manifest. Omitting that field makes the Vulkan loader log
> `does not have an 'api_version' field. Skipping ICD JSON` followed by `Found no drivers!`, at
> which point llama.cpp silently falls back to the **CPU** backend — it still runs, just ~7x
> slower, with `backend` reading `CPU` in `llama-bench` output. The script now fails loudly
> rather than emit a manifest the loader will skip.

## 5. Assemble + package

```
VK_BUILD=<...> MESA_ICD_DIR=<...> LIBDRM_DIR=<...> HIP_BUILD=<...> ./build-from-source.sh
./build-images.sh            # docker images strix-halo-llamacpp:vulkan / strix-halo-llamacpp:hip
tar czf strix-halo-llamacpp-vulkan-portable.tar.gz vulkan README.md   # the release tarball
```

## 6. Publish

```
./push-images.sh             # images to ghcr.io (auth + usage in the script header)
gh release create v0.1 strix-halo-llamacpp-vulkan-portable.tar.gz
```
