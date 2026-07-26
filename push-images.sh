#!/usr/bin/env bash
# Publish the toolbox images to a container registry.
# Run `docker login <registry>` first (your credentials; not stored here).
# Usage: REGISTRY=docker.io/nathanw1014 ./push-images.sh    (or ghcr.io/nathanw1014)
set -euo pipefail
: "${REGISTRY:?set REGISTRY, e.g. docker.io/nathanw1014 or ghcr.io/nathanw1014}"
for tag in vulkan hip; do
  docker tag  "strix-halo-llamacpp:$tag" "$REGISTRY/strix-halo-llamacpp:$tag"
  docker push "$REGISTRY/strix-halo-llamacpp:$tag"
done
echo "pushed $REGISTRY/strix-halo-llamacpp:{vulkan,hip}"
