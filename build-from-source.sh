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

# Clean the payload dirs first. Without this, a rebuild against a different library version
# leaves the previous .so alongside the new one (e.g. libdrm 1.133.0 next to 1.134.0), which
# bloats the tarball and makes it ambiguous which one shipped.
rm -rf "$HERE/vulkan/bin" "$HERE/vulkan/driver"
mkdir -p "$HERE/vulkan/bin" "$HERE/vulkan/driver" "$HERE/hip/bin"

echo "== vulkan: binaries + shared libs =="
cp "$VK_BUILD"/bin/llama-server "$VK_BUILD"/bin/llama-cli "$VK_BUILD"/bin/llama-bench "$HERE/vulkan/bin/"
# Copy only the LIVE libraries, by walking each unversioned .so symlink to its target.
# A long-lived build dir accumulates every soversion it has ever produced (libllama-common
# .so.0.0.243 ... .0.0.319), and a blanket `cp *.so*` shipped all of them - 46 MB of dead
# weight in the tarball. Anything no unversioned symlink points at is stale by definition.
copied=0
for l in "$VK_BUILD"/bin/*.so; do
    [ -e "$l" ] || continue
    if [ -L "$l" ]; then
        cur="$l"
        while [ -L "$cur" ]; do                      # lib.so -> lib.so.0 -> lib.so.0.0.N
            cp -P "$cur" "$HERE/vulkan/bin/"
            cur="$(dirname "$cur")/$(readlink "$cur")"
        done
        cp "$cur" "$HERE/vulkan/bin/"
    else
        cp "$l" "$HERE/vulkan/bin/"                  # plain lib*-impl.so
    fi
    copied=$((copied + 1))
done
echo "   $copied library chains copied (stale soversions in $VK_BUILD/bin skipped)"

echo "== vulkan: bundle Mesa RADV + libdrm =="
cp -P "$MESA_ICD_DIR"/libvulkan_radeon.so "$HERE/vulkan/driver/"
cp -P "$LIBDRM_DIR"/libdrm.so.2* "$LIBDRM_DIR"/libdrm_amdgpu.so.1* "$HERE/vulkan/driver/"
# ICD json with a RELATIVE library_path (resolved next to the json).
# api_version is MANDATORY: without it the Vulkan loader logs
#   "does not have an 'api_version' field. Skipping ICD JSON"
# and then "Found no drivers!", and llama.cpp silently falls back to the CPU backend.
# Take it from Mesa's own generated manifest so it tracks the bundled driver.
SRC_ICD="$(ls "$MESA_ICD_DIR"/radeon_devenv_icd.*.json "$MESA_ICD_DIR"/radeon_icd.*.json 2>/dev/null | head -1 || true)"   # ls exits 2 when one glob is unmatched; under pipefail that killed the script whenever only radeon_icd.*.json exists
API_VERSION="$(sed -n 's/.*"api_version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SRC_ICD" 2>/dev/null | head -1)"
if [ -z "$API_VERSION" ]; then
    echo "ERROR: could not read api_version from Mesa's ICD manifest ($MESA_ICD_DIR)." >&2
    echo "       Refusing to emit a manifest the Vulkan loader will skip." >&2
    exit 1
fi
printf '{\n    "file_format_version": "1.0.1",\n    "ICD": {\n        "api_version": "%s",\n        "library_arch": "64",\n        "library_path": "./libvulkan_radeon.so"\n    }\n}\n' \
    "$API_VERSION" > "$HERE/vulkan/driver/radeon_icd.x86_64.json"
echo "   ICD api_version=$API_VERSION (from $(basename "$SRC_ICD"))"

# ---- release gate: no build-machine paths in the payload --------------------------------
# BUILD.md documented all of this and it still shipped wrong in v0.1/v0.3/v0.4, so it is
# enforced here - the one place both the manual and the CI build go through.
echo "== gate: build-machine paths =="

# 1. amdgpu.ids. The lookup path is COMPILED INTO libdrm_amdgpu (BUILD.md #1), so a libdrm
# built with a local prefix bakes in a path that does not exist on a user's box and every
# run reports it. Hard failure: a payload like that is not shippable.
IDS_WANT="/usr/share/libdrm/amdgpu.ids"
for so in "$HERE"/vulkan/driver/libdrm_amdgpu.so.1.*; do
    [ -f "$so" ] || continue
    ids="$(strings -a "$so" | grep -m1 '/amdgpu\.ids$' || true)"
    if [ "$ids" != "$IDS_WANT" ]; then
        echo "ERROR: $(basename "$so") looks up amdgpu.ids at '${ids:-<none found>}'," >&2
        echo "       not $IDS_WANT. LIBDRM_DIR points at a libdrm built with a local prefix." >&2
        echo "       Rebuild libdrm with --prefix=/usr and DESTDIR-stage it (BUILD.md #1)." >&2
        exit 1
    fi
done
echo "   amdgpu.ids -> $IDS_WANT"

# 2. RPATH/RUNPATH. Binaries copied out of a build tree carry that tree's absolute path.
# Harmless at runtime (_run sets LD_LIBRARY_PATH, which is searched before DT_RUNPATH) but it
# publishes the build machine's directory layout. Rewrite to $ORIGIN so the payload still
# resolves its own libraries when a binary under bin/ is run without the wrapper.
if ! command -v patchelf >/dev/null; then
    echo "ERROR: patchelf not found; cannot scrub build-tree RPATHs (apt install patchelf)." >&2
    exit 1
fi
scrubbed=0
while IFS= read -r f; do
    head -c4 "$f" | grep -q ELF || continue
    rp="$(patchelf --print-rpath "$f" 2>/dev/null || true)"
    case "$rp" in
        ""|'$ORIGIN') continue ;;
    esac
    patchelf --set-rpath '$ORIGIN' "$f"
    scrubbed=$((scrubbed + 1))
done < <(find "$HERE/vulkan/bin" "$HERE/vulkan/driver" -type f ! -type l)
echo "   $scrubbed ELF RPATHs rewritten to \$ORIGIN"

# 3. Source paths compiled into assert/log strings (__FILE__). Not fixable here - it needs
# -ffile-prefix-map at llama.cpp compile time - so this warns rather than fails.
leaky="$(grep -rlI --binary-files=text -e "$HOME/" "$HERE/vulkan/bin" "$HERE/vulkan/driver" 2>/dev/null | wc -l)"
[ "$leaky" = 0 ] || echo "   WARNING: $leaky file(s) still embed \$HOME source paths (__FILE__ strings; rebuild with -ffile-prefix-map to clear)"

echo "== vulkan: launcher symlinks (wrapper _run is tracked) =="
for b in llama-server llama-cli llama-bench; do ln -sf _run "$HERE/vulkan/$b"; done

if [ -n "$HIP_BUILD" ]; then
  echo "== hip: binaries + libs (for the ROCm container) =="
  cp "$HIP_BUILD"/bin/llama-server "$HIP_BUILD"/bin/llama-cli "$HIP_BUILD"/bin/llama-bench "$HERE/hip/bin/" 2>/dev/null || true
  cp -P "$HIP_BUILD"/bin/*.so* "$HERE/hip/bin/" 2>/dev/null || true
fi

echo "done. next: ./build-images.sh   (or run vulkan/llama-server directly)"
