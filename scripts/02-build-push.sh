#!/usr/bin/env bash
# Builds the Docker image and pushes it to DigitalOcean Container Registry.
# --platform linux/amd64 matters on Apple Silicon Macs: DOKS nodes run amd64.
set -euo pipefail
source "$(dirname "$0")/config.env"

IMAGE="registry.digitalocean.com/$REGISTRY_NAME/$IMAGE_NAME:$IMAGE_TAG"

echo "==> Logging Docker in to DOCR"
doctl registry login

echo "==> Building $IMAGE"
docker buildx build --platform linux/amd64 -t "$IMAGE" "$(dirname "$0")/../app" --push

echo "==> Pushed. Images in registry:"
doctl registry repository list-tags "$IMAGE_NAME"
