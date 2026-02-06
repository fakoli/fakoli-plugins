#!/usr/bin/env bash
# Provision a Multipass VM for nat464-sidecar testing.
# Usage: ./vm-setup.sh [vm-name] [cpus] [memory] [disk]
set -euo pipefail

VM_NAME="${1:-nat464-dev}"
CPUS="${2:-2}"
MEMORY="${3:-4G}"
DISK="${4:-20G}"

echo "==> Creating Multipass VM: ${VM_NAME} (${CPUS} CPUs, ${MEMORY} RAM, ${DISK} disk)"

# Check if VM already exists
if multipass info "${VM_NAME}" &>/dev/null; then
    echo "VM '${VM_NAME}' already exists. Use 'multipass delete ${VM_NAME} --purge' to recreate."
    exit 1
fi

multipass launch --name "${VM_NAME}" --cpus "${CPUS}" --memory "${MEMORY}" --disk "${DISK}" 24.04

echo "==> VM created. Installing prerequisites..."

# Install Docker for building container images
multipass exec "${VM_NAME}" -- bash -c '
    sudo apt-get update -qq
    sudo apt-get install -y -qq curl socat iperf3 jq docker.io >/dev/null 2>&1
    sudo usermod -aG docker ubuntu
'

echo "==> Getting VM IP addresses..."
VM_IPV4=$(multipass info "${VM_NAME}" --format json | jq -r '.info["'"${VM_NAME}"'"].ipv4[0]')
echo "    IPv4: ${VM_IPV4}"

echo ""
echo "==> VM '${VM_NAME}' ready."
echo "    Shell: multipass shell ${VM_NAME}"
echo "    Transfer files: multipass transfer <local-path> ${VM_NAME}:<remote-path>"
echo ""
echo "Next: Transfer project and run k3s-setup.sh inside the VM."
