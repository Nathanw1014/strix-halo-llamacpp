#!/usr/bin/env bash
set -e; cd "$(dirname "$0")"
docker build -t strix-fa-vulkan -f Dockerfile.vulkan .
docker build -t strix-fa-hip    -f Dockerfile.hip .
echo "built: strix-fa-vulkan strix-fa-hip"
