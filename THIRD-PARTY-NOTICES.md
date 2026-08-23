# Third-party notices

The release payload bundles binaries built from the projects below. All three are
MIT-licensed, and MIT requires their copyright and permission notices to travel with
any distribution, which is what this file is for.

Nothing here is modified beyond what the build scripts in this repository do: llama.cpp
is built from the fork branch named in `MANIFEST.txt`, Mesa and libdrm are built from
the pinned upstream refs named there, unmodified.

---

## llama.cpp / ggml

`vulkan/bin/` (`llama-server`, `llama-cli`, `llama-bench`, `libllama*.so`, `libggml*.so`)

Upstream: https://github.com/ggml-org/llama.cpp
Fork used for these builds: https://github.com/Nathanw1014/llama.cpp

    MIT License

    Copyright (c) 2023-2026 The ggml authors

---

## Mesa (RADV Vulkan driver)

`vulkan/driver/libvulkan_radeon.so`

Upstream: https://gitlab.freedesktop.org/mesa/mesa

RADV is `SPDX-License-Identifier: MIT`. Copyright holders include, among others:

    Copyright (c) 2016 Red Hat
    Copyright (c) 2016 Bas Nieuwenhuizen
    Copyright (c) 2015 Intel Corporation

Mesa as a whole covers many components under several licenses; the driver bundled
here is the AMD Vulkan driver, which is MIT. See the upstream tree's
`docs/license.rst` for the full picture.

---

## libdrm

`vulkan/driver/libdrm.so.2*`, `vulkan/driver/libdrm_amdgpu.so.1*`

Upstream: https://gitlab.freedesktop.org/mesa/drm

    Copyright 1999, 2000 Precision Insight, Inc., Cedar Park, Texas.
    Copyright 2000 VA Linux Systems, Inc., Sunnyvale, California.
    All Rights Reserved.

---

## The MIT permission notice

The same text applies to each of the above:

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
