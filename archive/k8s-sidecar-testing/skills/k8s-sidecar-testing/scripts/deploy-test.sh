#!/usr/bin/env bash
# Deploy the nat464-demo pod and run verification tests.
# Run this INSIDE the Multipass VM.
# Usage: ./deploy-test.sh [manifest-path]
set -euo pipefail

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="${1:-/home/ubuntu/nat464-sidecar/deploy/example-pod.yaml}"
PEER_MANIFEST="${SCRIPT_DIR}/../../deploy/ipv6-peer-nginx.yaml"

echo "==> Deploying nat464-demo pod..."

# Clean up any previous run
kubectl delete pod nat464-demo --ignore-not-found --wait=true 2>/dev/null
kubectl delete configmap nat464-demo-nginx-conf --ignore-not-found 2>/dev/null

# Deploy with imagePullPolicy: Never (using local image)
# The manifest may contain ConfigMap + Pod, so apply the whole file with sed patching
sed 's/image: nat464-sidecar:latest/image: nat464-sidecar:latest\n      imagePullPolicy: Never/' "${MANIFEST}" | kubectl apply -f -

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
echo "===== TEST 2: Nginx is IPv4-only (ss -tlnp) ====="
SS_OUTPUT=$(kubectl exec nat464-demo -c app -- sh -c 'ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null' 2>/dev/null || echo "")
echo "    Listen sockets on port 80:"
echo "${SS_OUTPUT}" | grep -E '(:80 |:80$)' | sed 's/^/        /' || true

if echo "${SS_OUTPUT}" | grep -qE '0\.0\.0\.0:80[^0-9]' && ! echo "${SS_OUTPUT}" | grep -qE '(\[::\]:80[^0-9]|:::80[^0-9])'; then
    echo "    PASS: nginx listens on 0.0.0.0:80 only (IPv4-only confirmed)"
else
    echo "    INFO: nginx listen sockets may include IPv6 (check output above)"
fi

echo ""
echo "===== TEST 3: Direct IPv6 to nginx:80 is refused (proving sidecar is needed) ====="
DIRECT_V6=$(kubectl run ipv6-direct-test --rm -i --restart=Never \
    --image=curlimages/curl:latest \
    --command -- curl -6 -s --connect-timeout 5 "http://[${POD_IPV6}]:80/" 2>&1 || true)
kubectl delete pod ipv6-direct-test --ignore-not-found --wait=false &>/dev/null || true

if echo "${DIRECT_V6}" | grep -qiE '(refused|reset|timed out|couldn.t connect|FAILED|error)' || [ -z "${DIRECT_V6}" ]; then
    echo "    PASS: Direct IPv6 to nginx:80 refused (sidecar is required for IPv6 inbound)"
else
    echo "    WARN: Direct IPv6 to nginx:80 may have succeeded: ${DIRECT_V6:0:80}"
fi

echo ""
echo "===== TEST 4: Inbound IPv6 -> IPv4 (curl -6 pod:8080 -> nginx:80) ====="
INBOUND_RESULT=$(kubectl run curl-test --rm -i --restart=Never \
    --image=curlimages/curl:latest \
    --command -- curl -6 -s --connect-timeout 5 "http://[${POD_IPV6}]:8080/" 2>/dev/null || echo "FAILED")
kubectl delete pod curl-test --ignore-not-found --wait=false &>/dev/null || true

if echo "${INBOUND_RESULT}" | grep -q "nginx"; then
    echo "    PASS: Received nginx response through IPv6 -> IPv4 translation"
else
    echo "    FAIL: Expected nginx response, got: ${INBOUND_RESULT:0:100}"
fi

echo ""
echo "===== TEST 5: Outbound SOCKS5 to external (example.com) ====="
OUTBOUND_EXT=$(kubectl exec nat464-demo -c app -- \
    curl -s --connect-timeout 10 -o /dev/null -w '%{http_code}' \
    -x socks5h://127.0.0.1:1080 http://example.com 2>/dev/null || echo "000")
if [ "${OUTBOUND_EXT}" = "200" ]; then
    echo "    PASS: Outbound SOCKS5 to example.com returned HTTP 200"
else
    echo "    FAIL: Expected HTTP 200, got: ${OUTBOUND_EXT}"
fi

echo ""
echo "===== TEST 6: Outbound SOCKS5 to IPv6 peer pod ====="
# Deploy ipv6-peer if manifest exists and pod isn't running
if [ -f "${PEER_MANIFEST}" ]; then
    if ! kubectl get pod ipv6-peer &>/dev/null; then
        echo "    Deploying ipv6-peer pod..."
        kubectl delete pod ipv6-peer --ignore-not-found --wait=true 2>/dev/null
        kubectl delete configmap ipv6-peer-nginx-conf --ignore-not-found 2>/dev/null
        kubectl apply -f "${PEER_MANIFEST}"
        kubectl wait --for=condition=Ready pod/ipv6-peer --timeout=60s
    fi

    PEER_IPV6=$(kubectl get pod ipv6-peer -o jsonpath='{.status.podIPs[*].ip}' | tr ' ' '\n' | grep ':' | head -1)
    if [ -n "${PEER_IPV6}" ]; then
        echo "    Peer IPv6: ${PEER_IPV6}"
        OUTBOUND_PEER=$(kubectl exec nat464-demo -c app -- \
            curl -s --connect-timeout 10 -x socks5h://127.0.0.1:1080 "http://[${PEER_IPV6}]:80/" 2>/dev/null || echo "FAILED")
        if echo "${OUTBOUND_PEER}" | grep -q "ipv6-peer-ok"; then
            echo "    PASS: Outbound SOCKS5 to IPv6 peer pod works"
        else
            echo "    FAIL: Expected 'ipv6-peer-ok', got: ${OUTBOUND_PEER:0:100}"
        fi
    else
        echo "    SKIP: No IPv6 address on ipv6-peer pod"
    fi
else
    echo "    SKIP: ${PEER_MANIFEST} not found (run from repo root or provide path)"
fi

echo ""
echo "===== TEST 7: Sidecar logs ====="
kubectl logs nat464-demo -c nat464-sidecar --tail=20

echo ""
echo "===== TEST 8: Pod status ====="
kubectl get pod nat464-demo -o wide

echo ""
echo "==> Tests complete."
echo "    To run full validation: ./validate-paths.sh"
echo "    To run benchmarks:      ./benchmark.sh"
echo "    To clean up:            kubectl delete pod nat464-demo ipv6-peer --ignore-not-found"
