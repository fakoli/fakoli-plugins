#!/usr/bin/env bash
# Clean up test resources. Run with --vm to also delete the Multipass VM.
# Usage: ./teardown.sh [--vm] [vm-name]
set -euo pipefail

DELETE_VM=false
VM_NAME="nat464-dev"

for arg in "$@"; do
    case "$arg" in
        --vm) DELETE_VM=true ;;
        *) VM_NAME="$arg" ;;
    esac
done

if [ -f /etc/rancher/k3s/k3s.yaml ]; then
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    echo "==> Deleting test pods..."
    kubectl delete pod nat464-demo --ignore-not-found 2>/dev/null
    kubectl delete pod curl-test --ignore-not-found 2>/dev/null
    echo "==> Removing container images..."
    sudo k3s ctr images rm docker.io/library/nat464-sidecar:latest 2>/dev/null || true
fi

if [ "${DELETE_VM}" = true ]; then
    echo "==> Deleting Multipass VM: ${VM_NAME}..."
    multipass delete "${VM_NAME}" --purge
    echo "    VM deleted."
else
    echo "==> Cluster resources cleaned. VM '${VM_NAME}' preserved."
    echo "    To delete VM: multipass delete ${VM_NAME} --purge"
fi

echo "==> Teardown complete."
