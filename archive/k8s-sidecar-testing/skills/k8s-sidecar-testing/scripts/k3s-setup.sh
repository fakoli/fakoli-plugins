#!/usr/bin/env bash
# Install and configure k3s with IPv6-only pod networking inside the VM.
# Run this INSIDE the Multipass VM.
# Usage: ./k3s-setup.sh
set -euo pipefail

echo "==> Detecting VM network addresses..."

# Get the primary IPv4 address (for dual-stack node, like EKS nodes)
NODE_IPV4=$(ip -4 addr show scope global | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
# Generate a ULA IPv6 for the node
NODE_IPV6="fd00:0:0:0:0:0:0:1"
NODE_IPV6_SHORT="fd00::1"

# Add the ULA IPv6 address to the primary interface if not present
PRIMARY_IF=$(ip route | grep default | awk '{print $5}' | head -1)
if ! ip -6 addr show dev "${PRIMARY_IF}" | grep -q "fd00.*::1"; then
    echo "==> Adding IPv6 ULA address ${NODE_IPV6}/64 to ${PRIMARY_IF}..."
    sudo ip -6 addr add "${NODE_IPV6}/64" dev "${PRIMARY_IF}"
fi

echo "    Node IPv4: ${NODE_IPV4}"
echo "    Node IPv6: ${NODE_IPV6_SHORT}"
echo "    Interface: ${PRIMARY_IF}"

echo "==> Installing k3s with IPv6-only pod/service CIDRs..."

# Install k3s with dual-stack CIDRs (IPv4-primary to match advertise addr).
# k3s requires the first service CIDR family to match the advertise address.
# Pods get both IPv4+IPv6; we test the sidecar via the IPv6 address.
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
    --node-ip=${NODE_IPV4},${NODE_IPV6_SHORT} \
    --cluster-cidr=10.42.0.0/16,fd00:42::/56 \
    --service-cidr=10.43.0.0/16,fd00:43::/112 \
    --flannel-ipv6-masq \
    --write-kubeconfig-mode=644" sh -

echo "==> Waiting for k3s to become ready..."
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

for i in $(seq 1 60); do
    if kubectl get nodes 2>/dev/null | grep -q " Ready"; then
        echo "    k3s ready after ${i}s"
        break
    fi
    sleep 1
done

echo "==> Configuring CoreDNS with DNS64 (64:ff9b::/96)..."

# Patch CoreDNS to add DNS64 plugin — synthesizes AAAA records for IPv4-only hosts
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns-custom
  namespace: kube-system
data:
  dns64.override: |
    dns64 64:ff9b::/96 {
      translate_all
    }
EOF

# Wait for CoreDNS deployment to be available, then restart to pick up config
kubectl -n kube-system rollout status deployment coredns --timeout=120s
kubectl -n kube-system rollout restart deployment coredns
kubectl -n kube-system rollout status deployment coredns --timeout=60s

echo ""
echo "==> k3s cluster ready with dual-stack (IPv6-primary) pod networking."
echo "    KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
echo "    Pod CIDR:     fd00:42::/56 + 10.42.0.0/16"
echo "    Service CIDR: fd00:43::/112 + 10.43.0.0/16"
echo "    DNS64 prefix: 64:ff9b::/96"
echo ""
echo "Next: Build the container image and run deploy-test.sh"
