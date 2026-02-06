#!/usr/bin/env bash
# Deploy the nat464-demo pod and run verification tests.
# Run this INSIDE the Multipass VM.
# Usage: ./deploy-test.sh [manifest-path]
set -euo pipefail

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
MANIFEST="${1:-/home/ubuntu/nat464-sidecar/deploy/example-pod.yaml}"

echo "==> Deploying nat464-demo pod..."

# Clean up any previous run
kubectl delete pod nat464-demo --ignore-not-found --wait=true 2>/dev/null

# Deploy with imagePullPolicy: Never (using local image)
kubectl apply -f - <<EOF
$(sed 's/image: nat464-sidecar:latest/image: nat464-sidecar:latest\n      imagePullPolicy: Never/' "${MANIFEST}")
EOF

echo "==> Waiting for pod to be ready..."
kubectl wait --for=condition=Ready pod/nat464-demo --timeout=120s

# Get pod IPv6 address (may be index 0 or 1 in dual-stack)
POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[*].ip}' | tr ' ' '\n' | grep ':' | head -1)
if [ -z "${POD_IPV6}" ]; then
    echo "    ERROR: No IPv6 address found on pod"
    POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[0].ip}')
fi
echo "    Pod IPv6: ${POD_IPV6}"

echo ""
echo "===== TEST 1: Health check ====="
HEALTH=$(kubectl exec nat464-demo -c nat464-sidecar -- wget -qO- http://localhost:9464/healthz 2>/dev/null || \
         kubectl exec nat464-demo -c app -- wget -qO- http://localhost:9464/healthz 2>/dev/null || \
         echo "FAILED")
echo "    /healthz: ${HEALTH}"

echo ""
echo "===== TEST 2: Inbound IPv6 → IPv4 (curl -6 pod:8080 → nginx:80) ====="
# From a test pod, curl the sidecar's IPv6 listen port
INBOUND_RESULT=$(kubectl run curl-test --rm -i --restart=Never \
    --image=curlimages/curl:latest \
    --command -- curl -6 -s --connect-timeout 5 "http://[${POD_IPV6}]:8080/" 2>/dev/null || echo "FAILED")
if echo "${INBOUND_RESULT}" | grep -q "nginx"; then
    echo "    PASS: Received nginx response through IPv6 → IPv4 translation"
else
    echo "    FAIL: Expected nginx response, got: ${INBOUND_RESULT:0:100}"
fi

echo ""
echo "===== TEST 3: Sidecar logs ====="
kubectl logs nat464-demo -c nat464-sidecar --tail=20

echo ""
echo "===== TEST 4: Pod status ====="
kubectl get pod nat464-demo -o wide

echo ""
echo "==> Tests complete."
echo "    To run outbound test: kubectl exec nat464-demo -c app -- curl -x socks5h://127.0.0.1:1080 http://example.com"
echo "    To clean up: kubectl delete pod nat464-demo"
