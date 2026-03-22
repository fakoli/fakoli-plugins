#!/usr/bin/env bash
# Build the nat464-sidecar container image inside the VM.
# Run this INSIDE the Multipass VM from the project root.
# Usage: ./build-image.sh [project-dir]
set -euo pipefail

PROJECT_DIR="${1:-/home/ubuntu/nat464-sidecar}"

echo "==> Building nat464-sidecar container image..."

cd "${PROJECT_DIR}"
sudo docker build -t nat464-sidecar:latest .

# Import into k3s containerd so pods can use it
echo "==> Importing image into k3s..."
sudo docker save nat464-sidecar:latest | sudo k3s ctr images import -

echo "==> Image ready."
sudo k3s ctr images ls | grep nat464-sidecar
