#!/usr/bin/env bash
# Benchmark nat464-sidecar translation overhead using iperf3.
# Run this INSIDE the Multipass VM after deploy-test.sh.
# Usage: ./benchmark.sh
set -euo pipefail

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[*].ip}' | tr ' ' '\n' | grep ':' | head -1)
if [ -z "${POD_IPV6}" ]; then
    POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[0].ip}')
fi
echo "Pod IPv6: ${POD_IPV6}"

echo ""
echo "===== BASELINE: Direct localhost (no sidecar) ====="
# Run iperf3 server in the app container, connect directly via localhost
kubectl exec nat464-demo -c app -- sh -c 'iperf3 -s -D -p 5201 --one-off' 2>/dev/null
sleep 1
kubectl exec nat464-demo -c app -- iperf3 -c 127.0.0.1 -p 5201 -t 5 --json 2>/dev/null | \
    jq '{
        "test": "baseline_localhost",
        "bits_per_second": .end.sum_sent.bits_per_second,
        "mbps": (.end.sum_sent.bits_per_second / 1000000 | floor),
        "retransmits": .end.sum_sent.retransmits
    }' 2>/dev/null || echo "Baseline test skipped (iperf3 not in nginx image)"

echo ""
echo "===== SIDECAR: IPv6 → IPv4 translation ====="
echo "To measure sidecar overhead, run iperf3 inside the app container on port 80"
echo "and connect through the sidecar on port 8080 from an external pod."
echo ""
echo "Manual steps:"
echo "  1. kubectl exec nat464-demo -c app -- sh -c 'apt-get update && apt-get install -y iperf3 && iperf3 -s -p 5201 -D'"
echo "  2. kubectl run iperf-test --rm -i --restart=Never --image=networkstatic/iperf3 -- -c ${POD_IPV6} -p 8080 -t 10"
echo ""
echo "(Full iperf3-through-sidecar requires the sidecar to forward to port 5201)"
