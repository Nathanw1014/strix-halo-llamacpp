#!/usr/bin/env bash
# Assemble the toolbox from a pre-built llama.cpp (Vulkan [+HIP]), a Mesa RADV build, and libdrm.
# This does NOT build llama.cpp/Mesa itself - see BUILD.md for those steps and the exact toolchain.
# It copies the outputs into vulkan/ and hip/ (both git-ignored) and wires up the launcher symlinks.
#
# Required env (paths to your builds):
#   VK_BUILD      llama.cpp Vulkan build dir (contains bin/llama-server, bin/*.so*)
#   MESA_ICD_DIR  Mesa RADV build dir       (contains libvulkan_radeon.so)
#   LIBDRM_DIR    libdrm prefix lib dir     (contains libdrm_amdgpu.so.1*)
# Optional:
#   HIP_BUILD     llama.cpp HIP build dir   (contains bin/llama-server, bin/libggml-hip.so*)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${VK_BUILD:?set VK_BUILD (llama.cpp Vulkan build dir)}"
: "${MESA_ICD_DIR:?set MESA_ICD_DIR (Mesa RADV build dir with libvulkan_radeon.so)}"
: "${LIBDRM_DIR:?set LIBDRM_DIR (libdrm prefix lib dir)}"
HIP_BUILD="${HIP_BUILD:-}"

mkdir -p "$HERE/vulkan/bin" "$HERE/vulkan/driver" "$HERE/hip/bin"

echo "== vulkan: binaries + shared libs =="
cp "$VK_BUILD"/bin/llama-server "$VK_BUILD"/bin/llama-cli "$VK_BUILD"/bin/llama-bench "$HERE/vulkan/bin/"
cp -P "$VK_BUILD"/bin/*.so* "$HERE/vulkan/bin/"

echo "== vulkan: bundle Mesa RADV + libdrm =="
cp -P "$MESA_ICD_DIR"/libvulkan_radeon.so "$HERE/vulkan/driver/"
cp -P "$LIBDRM_DIR"/libdrm.so.2* "$LIBDRM_DIR"/libdrm_amdgpu.so.1* "$HERE/vulkan/driver/"
# ICD json with a RELATIVE library_path (resolved next to the json)
printf '{\n    "file_format_version": "1.0.1",\n    "ICD": {\n        "library_arch": "64",\n        "library_path": "./libvulkan_radeon.so"\n    }\n}\n' \
    > "$HERE/vulkan/driver/radeon_icd.x86_64.json"

echo "== vulkan: launcher symlinks (wrapper _run is tracked) =="
for b in llama-server llama-cli llama-bench; do ln -sf _run "$HERE/vulkan/$b"; done

if [ -n "$HIP_BUILD" ]; then
  echo "== hip: binaries + libs (for the ROCm container) =="
  cp "$HIP_BUILD"/bin/llama-server "$HIP_BUILD"/bin/llama-cli "$HIP_BUILD"/bin/llama-bench "$HERE/hip/bin/" 2>/dev/null || true
  cp -P "$HIP_BUILD"/bin/*.so* "$HERE/hip/bin/" 2>/dev/null || true
fi

echo "done. next: ./build-images.sh   (or run vulkan/llama-server directly)"
