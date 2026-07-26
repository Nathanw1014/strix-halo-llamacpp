#!/usr/bin/env bash
# Publish the toolbox images to GitHub Container Registry (ghcr.io).
# Auth (your credentials; nothing stored here). After `gh auth login`:
#   gh auth token | docker login ghcr.io -u nathanw1014 --password-stdin
# Usage:
#   ./push-images.sh                 # push both (vulkan 273MB + hip ~29GB)
#   ./push-images.sh vulkan          # push only the small Vulkan image
#   REGISTRY=ghcr.io/you ./push-images.sh
set -euo pipefail
REGISTRY="${REGISTRY:-ghcr.io/nathanw1014}"
if [ $# -gt 0 ]; then TAGS=("$@"); else TAGS=(vulkan hip); fi
for tag in "${TAGS[@]}"; do
  docker tag  "strix-halo-llamacpp:$tag" "$REGISTRY/strix-halo-llamacpp:$tag"
  docker push "$REGISTRY/strix-halo-llamacpp:$tag"
done
echo "pushed $REGISTRY/strix-halo-llamacpp: ${TAGS[*]}"
