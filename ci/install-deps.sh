#!/usr/bin/env bash
# Toolchain for the CI payload build (Ubuntu 24.04 / noble). Run as root.
#
# The LunarG SDK is not optional: BUILD.md's toolchain notes apply verbatim in CI —
# noble's distro glslc (shaderc 2023.8) compiles but emits non-comparable SPIR-V, and
# recent llama.cpp needs Vulkan headers that ship alongside spirv/ headers. The SDK's
# /usr install satisfies both (-DVulkan_INCLUDE_DIR=/usr/include, glslc on PATH).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends wget ca-certificates gnupg

wget -qO /etc/apt/trusted.gpg.d/lunarg.asc https://packages.lunarg.com/lunarg-signing-key-pub.asc
wget -qO /etc/apt/sources.list.d/lunarg-vulkan-noble.list https://packages.lunarg.com/vulkan/lunarg-vulkan-noble.list
apt-get update

apt-get install -y --no-install-recommends \
    vulkan-sdk \
    build-essential gcc-14 g++-14 cmake ninja-build ccache git curl patchelf \
    pkg-config bison flex \
    python3 python3-pip python3-setuptools python3-mako python3-yaml \
    zlib1g-dev libzstd-dev libexpat1-dev

# mesa main needs a newer meson than noble's 1.3.2
pip3 install --break-system-packages 'meson>=1.4'

echo "== toolchain =="
glslc --version | head -2
gcc-14 --version | head -1
meson --version
cmake --version | head -1
