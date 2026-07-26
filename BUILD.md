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

Mesa main needs libdrm >= 2.4.133. Build it to a local prefix:
```
# from the libdrm-2.4.133 source (dri.freedesktop.org or the mesa libdrm.wrap)
meson setup _build --prefix=$PWD/install --libdir=lib -Dbuildtype=release -Damdgpu=enabled -Dradeon=enabled
ninja -C _build install
# -> LIBDRM_DIR = $PWD/install/lib
```

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

## 5. Assemble + package

```
VK_BUILD=<...> MESA_ICD_DIR=<...> LIBDRM_DIR=<...> HIP_BUILD=<...> ./build-from-source.sh
./build-images.sh            # docker images strix-halo-llamacpp:vulkan / strix-halo-llamacpp:hip
tar czf strix-halo-llamacpp:vulkan-portable.tar.gz vulkan README.md   # portable dir for a release
```
