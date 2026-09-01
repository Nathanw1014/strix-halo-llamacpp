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

## 7. Automated dev builds (CI)

[`.github/workflows/dev-build.yml`](.github/workflows/dev-build.yml) watches the fork's
`strix-halo-vulkan` branch (polled every 2 hours) and, for each new commit, runs steps 1–5
clean-room on a GitHub runner via [`ci/build-payload.sh`](ci/build-payload.sh) — the same
script is runnable locally in a plain `ubuntu:24.04` container after
[`ci/install-deps.sh`](ci/install-deps.sh). Each build produces:

- a **prerelease** tagged `dev-<commit-date>-<sha7>` with the portable tarball + MANIFEST
- container tags `ghcr.io/nathanw1014/strix-halo-llamacpp:vulkan-dev` (rolling) and
  `:vulkan-dev-<date>-<sha7>` (pinned)

The **stable channel is untouched**: `:vulkan`, `:hip` and the v0.x releases remain hand-cut
from validated on-box builds. Dev builds are compile- and packaging-tested only (the runner
has no gfx1151), so promotion to stable stays a manual, benchmark-gated step.

Do that promotion with [`ci/promote.sh`](ci/promote.sh) rather than by hand:

```
ci/promote.sh v0.7.2 <fork-sha> --validation ~/strix-results/<file>       # prints the plan
ci/promote.sh v0.7.2 <fork-sha> --validation ~/strix-results/<file> --yes # uploads
```

It finds the `dev-*` release for that fork commit, refuses to continue unless the manifest's
`source:` really is that commit and the manifest inside the tarball matches the one beside it,
then repacks the tarball with a corrected manifest and attaches both to the v-tag. The payload
bytes are the ones CI built; only `MANIFEST.txt` changes, and the dev tarball's sha256 is
recorded in it so that is checkable after the fact.

`--validation FILE` is what puts the `validation:` block back. The curated line exists *because*
it is benchmark-gated, so a v-tag whose manifest cannot say what was tested has given up the only
thing that distinguishes it from a dev build. v0.7.1 shipped `(automated dev build)` with no
validation field; that is the hole this closes. Promoting without `--validation` writes
`validation: not recorded` and warns, rather than silently omitting the field.

`ci/build-payload.sh` takes the same input directly as `VALIDATION_FILE`, plus `BUILD_KIND` for
the `Built ... (<kind>)` line, if you are building a curated payload locally instead of promoting
a dev one.

Stable releases are cut from a **pinned, individually validated commit**, never from
whatever the branch tip happens to be. Every commit in `<previous payload sha>..<pinned sha>`
ships with the release, so each one in that range needs at least a smoke test on the paths it
touches before the tag is created (hybrid/MTP speculative serving is the easy one to miss:
dense-target testing never reaches the checkpoint paths). If the tip carries commits that are
not yet validated, either validate them first or build from a release branch that
cherry-picks the validated work onto the previous payload base; `dev-build.yml` takes any
ref via `workflow_dispatch`, so the pipeline needs no changes for that.

One gate is **mandatory on every release candidate**, regardless of what changed:

```
tools/repeat_gate.py --bin <build>/bin/llama-server --model <model.gguf> --reps 6 -- <serving flags>
```

It sends the same greedy request N times into one server process and compares the responses
to each other, sweeping four built-in prompt lengths (a single token of prompt length moves
the ubatch boundaries and was measured flipping verdicts, so one prompt is a coin toss, not
a gate). Run it on each model family the release headlines. It exists because every other
gate in this repo's history — KLD packets, byte-identical greedy A/Bs, two-launch
determinism controls — compares arms at the same request index and is structurally blind to
output that drifts *with* request index; v0.7.2 shipped a 0/12 greedy-repeatability defect
(the missing upstream #27812 pick) through all of them. PASS and WARN (rep-0-only, the
warm-up signature upstream also shows) are acceptable; FAIL blocks the tag. Budget about
5 minutes per build; on the shared box pass `--lock` so it respects the GPU bench lock.

CI-specific deltas from the local recipe, all in `ci/build-payload.sh`:

- **mesa/libdrm/shaderc are pinned** (`MESA_REF` / `LIBDRM_REF` / `SHADERC_REF` in the workflow
  env, defaulted in the script) to the exact versions the validated stack was built with. Bump
  them deliberately — the bundled RADV and the shader compiler are part of the validated stack.
  The pinned toolchain build is cached, so routine runs only rebuild llama.cpp.
- **`glslc` is built from source at the pin** — the LunarG noble repo resolves `glslc` to the
  distro shaderc 2023.8, exactly the compiler the toolchain notes above rule out. The SDK repo
  is still used for current Vulkan/SPIRV headers.
- **explicit Zen 5 ISA toggles replace `GGML_NATIVE=ON`** (`GGML_AVX512*`/`GGML_AVX_VNNI`) —
  native on a cloud runner would tune for the runner's CPU, not Strix Halo, and a global
  `-march=znver5` SIGILLs llama.cpp's build-time host tools on the runner. The toggles scope
  the target ISA to the ggml CPU backend only.

Trigger a build immediately (e.g. right after pushing to the fork):

```
gh workflow run dev-build -R Nathanw1014/strix-halo-llamacpp -f force=true
```

Optional instant push-trigger: add a tiny workflow to the fork branch that fires
`repository_dispatch` (event `llama-push`, `client_payload.ref` = the pushed sha) at this
repo, authenticated with a PAT stored in the fork's secrets — the dev-build workflow already
listens for it. Until then, the 2-hour poll picks pushes up on its own.
