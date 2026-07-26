#!/usr/bin/env bash
set -e; cd "$(dirname "$0")"
docker build -t strix-halo-llamacpp:vulkan -f Dockerfile.vulkan .
docker build -t strix-halo-llamacpp:hip    -f Dockerfile.hip .
echo "built: strix-halo-llamacpp:vulkan strix-halo-llamacpp:hip"
