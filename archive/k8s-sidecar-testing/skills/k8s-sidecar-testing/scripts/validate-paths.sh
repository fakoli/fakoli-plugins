#!/usr/bin/env bash
# Validate all nat464-sidecar translation paths.
# Run this INSIDE the Multipass VM after deploy-test.sh has deployed nat464-demo
# and ipv6-peer-nginx.yaml has been applied.
# Usage: ./validate-paths.sh
set -euo pipefail

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

PASS_COUNT=0
FAIL_COUNT=0

pass() { echo "    PASS: $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "    FAIL: $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

# Resolve pod IPv6 address
POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[*].ip}' | tr ' ' '\n' | grep ':' | head -1)
if [ -z "${POD_IPV6}" ]; then
    echo "ERROR: No IPv6 address found on nat464-demo pod"
    exit 1
fi
echo "nat464-demo IPv6: ${POD_IPV6}"

# Deploy ipv6-peer if not already running
if ! kubectl get pod ipv6-peer &>/dev/null; then
    echo "==> Deploying ipv6-peer pod..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    MANIFEST="${SCRIPT_DIR}/../../deploy/ipv6-peer-nginx.yaml"
    kubectl apply -f "${MANIFEST}"
    kubectl wait --for=condition=Ready pod/ipv6-peer --timeout=60s
fi

PEER_IPV6=$(kubectl get pod ipv6-peer -o jsonpath='{.status.podIPs[*].ip}' | tr ' ' '\n' | grep ':' | head -1)
if [ -z "${PEER_IPV6}" ]; then
    echo "ERROR: No IPv6 address found on ipv6-peer pod"
    exit 1
fi
echo "ipv6-peer IPv6:   ${PEER_IPV6}"
echo ""

# ────────────────────────────────────────────────────────────────
echo "===== TEST 1: Nginx is IPv4-only (ss -tlnp) ====="
SS_OUTPUT=$(kubectl exec nat464-demo -c app -- sh -c 'ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null' 2>/dev/null || echo "")
echo "    Listen sockets:"
echo "${SS_OUTPUT}" | grep -E '(:80 |:80$)' | sed 's/^/        /' || true

# Check: should see 0.0.0.0:80, should NOT see [::]:80 or :::80
if echo "${SS_OUTPUT}" | grep -qE '0\.0\.0\.0:80[^0-9]'; then
    HAS_IPV4=true
else
    HAS_IPV4=false
fi
if echo "${SS_OUTPUT}" | grep -qE '(\[::\]:80[^0-9]|:::80[^0-9])'; then
    HAS_IPV6=true
else
    HAS_IPV6=false
fi

if $HAS_IPV4 && ! $HAS_IPV6; then
    pass "nginx listens on 0.0.0.0:80 only (IPv4)"
else
    fail "nginx listen sockets unexpected (IPv4=${HAS_IPV4}, IPv6=${HAS_IPV6})"
fi

# Verify direct IPv6 to port 80 fails (bypassing sidecar)
echo ""
echo "    Verifying direct IPv6 to nginx:80 is refused..."
DIRECT_V6=$(kubectl run ipv6-direct-test --rm -i --restart=Never \
    --image=curlimages/curl:latest \
    --command -- curl -6 -s --connect-timeout 5 "http://[${POD_IPV6}]:80/" 2>&1 || true)
# Clean up pod if it's stuck
kubectl delete pod ipv6-direct-test --ignore-not-found --wait=false &>/dev/null || true

if echo "${DIRECT_V6}" | grep -qiE '(refused|reset|timed out|couldn.t connect|FAILED|error)'; then
    pass "Direct IPv6 to nginx:80 refused (sidecar is required)"
elif [ -z "${DIRECT_V6}" ]; then
    pass "Direct IPv6 to nginx:80 returned nothing (connection refused)"
else
    fail "Direct IPv6 to nginx:80 unexpectedly succeeded: ${DIRECT_V6:0:80}"
fi

# ────────────────────────────────────────────────────────────────
echo ""
echo "===== TEST 2: Inbound IPv6 -> IPv4 via sidecar (port 8080) ====="
INBOUND=$(kubectl run inbound-test --rm -i --restart=Never \
    --image=curlimages/curl:latest \
    --command -- curl -6 -s --connect-timeout 10 "http://[${POD_IPV6}]:8080/" 2>/dev/null || echo "FAILED")
kubectl delete pod inbound-test --ignore-not-found --wait=false &>/dev/null || true

if echo "${INBOUND}" | grep -qi "nginx"; then
    pass "Inbound IPv6->IPv4 translation works (got nginx response)"
else
    fail "Inbound test: expected nginx, got: ${INBOUND:0:100}"
fi

# ────────────────────────────────────────────────────────────────
echo ""
echo "===== TEST 3: Outbound SOCKS5 to IPv6 peer pod ====="
OUTBOUND_PEER=$(kubectl exec nat464-demo -c app -- \
    curl -s --connect-timeout 10 -x socks5h://127.0.0.1:1080 "http://[${PEER_IPV6}]:80/" 2>/dev/null || echo "FAILED")

if echo "${OUTBOUND_PEER}" | grep -q "ipv6-peer-ok"; then
    pass "Outbound SOCKS5 to IPv6 peer pod works"
else
    fail "Outbound peer test: expected 'ipv6-peer-ok', got: ${OUTBOUND_PEER:0:100}"
fi

# ────────────────────────────────────────────────────────────────
echo ""
echo "===== TEST 4: Outbound SOCKS5 to external (example.com) ====="
OUTBOUND_EXT=$(kubectl exec nat464-demo -c app -- \
    curl -s --connect-timeout 10 -o /dev/null -w '%{http_code}' \
    -x socks5h://127.0.0.1:1080 "http://example.com" 2>/dev/null || echo "000")

if [ "${OUTBOUND_EXT}" = "200" ]; then
    pass "Outbound SOCKS5 to example.com returned HTTP 200"
else
    fail "Outbound external test: expected HTTP 200, got: ${OUTBOUND_EXT}"
fi

# ────────────────────────────────────────────────────────────────
echo ""
echo "====================================================="
echo "Results: ${PASS_COUNT} passed, ${FAIL_COUNT} failed (of $((PASS_COUNT + FAIL_COUNT)) tests)"
echo "====================================================="

if [ "${FAIL_COUNT}" -gt 0 ]; then
    exit 1
fi
