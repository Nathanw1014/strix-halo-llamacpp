#!/usr/bin/env bash
# Clean-room build of the Vulkan payload: libdrm + Mesa RADV (both pinned) + llama.cpp from
# the fork branch, assembled with ../build-from-source.sh into vulkan/ and packaged as the
# portable tarball. This is the script CI runs; it also runs as-is in a plain noble
# container after ci/install-deps.sh (that is how it was validated).
#
# Inputs (env):
#   LLAMA_REPO      llama.cpp fork          (default Nathanw1014/llama.cpp)
#   LLAMA_REF       branch or commit         (default strix-halo-vulkan)
#   MESA_REF        pinned mesa commit       (default = the commit the v0.4 driver shipped from)
#   LIBDRM_REF      pinned libdrm tag        (default libdrm-2.4.133, what v0.4 shipped)
#   SHADERC_REF     pinned shaderc commit    (default = the box's from-source glslc; the distro
#                   glslc "works" but emits non-comparable SPIR-V — see BUILD.md toolchain notes)
#   TOOLCHAIN_CACHE_DIR  optional dir for the mesa+libdrm+glslc outputs; reused across runs
#                   while the pins hold (these are the slow, rarely-changing half of the build)
#   WORK            scratch dir              (default <repo>/_work)
#   JOBS            parallelism              (default nproc)
#
# Output: <repo>/vulkan payload, <repo>/MANIFEST.txt, <repo>/strix-halo-llamacpp-vulkan-portable.tar.gz
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"

LLAMA_REPO="${LLAMA_REPO:-Nathanw1014/llama.cpp}"
LLAMA_REF="${LLAMA_REF:-strix-halo-vulkan}"
MESA_REF="${MESA_REF:-d18d598e275d1ab4634381c5414affe1319af6b1}"
LIBDRM_REF="${LIBDRM_REF:-libdrm-2.4.133}"
SHADERC_REF="${SHADERC_REF:-49a8724d561c13db22b52f99f2a0e2707a9a9e3c}"
WORK="${WORK:-$HERE/_work}"
JOBS="${JOBS:-$(nproc)}"
mkdir -p "$WORK"

# ---- toolchain: glslc + mesa RADV + libdrm (pinned; cacheable) ---------------------------
TC="${TOOLCHAIN_CACHE_DIR:-$WORK/toolchain}"
STAMP="mesa=$MESA_REF libdrm=$LIBDRM_REF shaderc=$SHADERC_REF"
if [ -f "$TC/stamp" ] && [ "$(cat "$TC/stamp")" = "$STAMP" ]; then
    echo "== toolchain: cache hit ($STAMP) =="
else
    rm -rf "$TC"; mkdir -p "$TC"

    echo "== shaderc/glslc @ $SHADERC_REF =="
    rm -rf "$WORK/shaderc"
    git init -q "$WORK/shaderc"
    git -C "$WORK/shaderc" remote add origin https://github.com/google/shaderc.git
    git -C "$WORK/shaderc" fetch --depth 1 origin "$SHADERC_REF"
    git -C "$WORK/shaderc" checkout -q FETCH_HEAD
    (cd "$WORK/shaderc" && ./utils/git-sync-deps)
    cmake -S "$WORK/shaderc" -B "$WORK/shaderc/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DSHADERC_SKIP_TESTS=ON -DSHADERC_SKIP_EXAMPLES=ON -DSHADERC_SKIP_COPYRIGHT_CHECK=ON
    cmake --build "$WORK/shaderc/build" --target glslc_exe -j "$JOBS"
    cp "$WORK/shaderc/build/glslc/glslc" "$TC/glslc"

    echo "== libdrm $LIBDRM_REF =="
    rm -rf "$WORK/drm"
    git clone --depth 1 --branch "$LIBDRM_REF" https://gitlab.freedesktop.org/mesa/drm.git "$WORK/drm"
    # --prefix=/usr is load-bearing: the amdgpu.ids path is compiled in (see BUILD.md #1)
    meson setup "$WORK/drm/_build" "$WORK/drm" --prefix=/usr --libdir=lib \
        -Dbuildtype=release -Damdgpu=enabled -Dradeon=enabled
    ninja -C "$WORK/drm/_build" -j "$JOBS"
    DESTDIR="$TC/libdrm-stage" ninja -C "$WORK/drm/_build" install >/dev/null
    # The staged .pc reports prefix=/usr (deliberate, see above), so mesa's compile expects
    # xf86drm.h at /usr/include/libdrm. Make that true in this disposable build env — the
    # stage alone only works on machines where a system libdrm-dev happens to be new enough.
    SUDO=""; [ "$(id -u)" != 0 ] && SUDO=sudo
    $SUDO cp -a "$TC/libdrm-stage/usr/." /usr/

    echo "== mesa RADV @ $MESA_REF =="
    rm -rf "$WORK/mesa"
    git init -q "$WORK/mesa"
    git -C "$WORK/mesa" remote add origin https://gitlab.freedesktop.org/mesa/mesa.git
    git -C "$WORK/mesa" fetch --depth 1 origin "$MESA_REF"
    git -C "$WORK/mesa" checkout -q FETCH_HEAD
    PKG_CONFIG_PATH="$TC/libdrm-stage/usr/lib/pkgconfig" meson setup "$WORK/mesa/build-rel" "$WORK/mesa" \
        -Dvulkan-drivers=amd -Dgallium-drivers= -Dllvm=disabled \
        -Dplatforms= -Dvideo-codecs= -Dbuildtype=release -Dwerror=false
    ninja -C "$WORK/mesa/build-rel" -j "$JOBS"

    mkdir -p "$TC/mesa-icd"
    cp "$WORK/mesa/build-rel/src/amd/vulkan/libvulkan_radeon.so" "$TC/mesa-icd/"
    cp "$WORK/mesa/build-rel/src/amd/vulkan/"radeon_*icd.*.json "$TC/mesa-icd/" 2>/dev/null || true
    ls "$TC/mesa-icd/"radeon_*icd.*.json >/dev/null   # build-from-source.sh needs one for api_version
    echo "$STAMP" > "$TC/stamp"
fi

# ---- llama.cpp Vulkan from the fork branch ----------------------------------------------
echo "== llama.cpp $LLAMA_REPO @ $LLAMA_REF =="
rm -rf "$WORK/llama.cpp"
# blob-less clone: full history so the embedded build number (git rev-list --count) is real,
# without the full checkout cost
git clone --filter=blob:none "https://github.com/$LLAMA_REPO" "$WORK/llama.cpp"
git -C "$WORK/llama.cpp" checkout -q "$LLAMA_REF"
LLAMA_SHA="$(git -C "$WORK/llama.cpp" rev-parse HEAD)"
LLAMA_SUBJECT="$(git -C "$WORK/llama.cpp" log -1 --format=%s)"

# BUILD.md #3, with one CI adaptation: GGML_NATIVE=ON on a cloud runner would tune for the
# runner's CPU, so target Strix Halo (Zen 5) explicitly via ggml's per-backend ISA toggles.
# NOT a global -march=znver5: that also compiles build-time HOST tools (llama-ui-embed,
# vulkan-shaders-gen), which execute on the runner and SIGILL on non-Zen5 CPUs. The toggles
# scope the target ISA to the ggml CPU-backend objects; host tools stay runner-generic.
CCACHE_ARGS=()
command -v ccache >/dev/null && CCACHE_ARGS=(-DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache)
cmake -S "$WORK/llama.cpp" -B "$WORK/llama.cpp/build-vk" -G Ninja \
    -DCMAKE_C_COMPILER=gcc-14 -DCMAKE_CXX_COMPILER=g++-14 \
    -DGGML_AVX512=ON -DGGML_AVX512_VBMI=ON -DGGML_AVX512_VNNI=ON -DGGML_AVX512_BF16=ON \
    -DGGML_AVX_VNNI=ON \
    -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF \
    -DVulkan_INCLUDE_DIR=/usr/include \
    -DVulkan_GLSLC_EXECUTABLE="$TC/glslc" \
    "${CCACHE_ARGS[@]}"
cmake --build "$WORK/llama.cpp/build-vk" --target llama-server llama-cli llama-bench -j "$JOBS"

# ---- assemble + package ------------------------------------------------------------------
VK_BUILD="$WORK/llama.cpp/build-vk" \
MESA_ICD_DIR="$TC/mesa-icd" \
LIBDRM_DIR="$TC/libdrm-stage/usr/lib" \
    "$HERE/build-from-source.sh"

cat > "$HERE/MANIFEST.txt" <<EOF
Built $(date -u +%Y-%m-%dT%H:%M:%SZ) (automated dev build)
source: $LLAMA_REF ${LLAMA_SHA:0:7} ($LLAMA_SUBJECT)
mesa: ${MESA_REF:0:9}  libdrm: ${LIBDRM_REF#libdrm-}  glslc: $("$TC/glslc" --version | head -1)
vulkan bins: $(cd "$HERE/vulkan/bin" && ls llama-* | tr '\n' ' ')
vulkan driver: $(cd "$HERE/vulkan/driver" && ls | tr '\n' ' ')
vulkan dir size: $(du -sh "$HERE/vulkan" | cut -f1)
EOF
cat "$HERE/MANIFEST.txt"

tar -C "$HERE" -czf "$HERE/strix-halo-llamacpp-vulkan-portable.tar.gz" vulkan README.md MANIFEST.txt
echo "== payload + tarball ready (llama.cpp $LLAMA_SHA) =="
