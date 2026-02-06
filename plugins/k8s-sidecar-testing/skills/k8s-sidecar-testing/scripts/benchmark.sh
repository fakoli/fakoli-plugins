#!/usr/bin/env bash
# Benchmark nat464-sidecar translation overhead.
# Measures HTTP latency and throughput: baseline (localhost) vs through-sidecar (IPv6).
# Run this INSIDE the Multipass VM after deploy-test.sh.
# Usage: ./benchmark.sh [iterations]
set -euo pipefail

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

ITERATIONS="${1:-50}"
echo "nat464-sidecar benchmark (${ITERATIONS} iterations per test)"
echo "============================================================"

# ── Resolve addresses ──────────────────────────────────────────
POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[*].ip}' | tr ' ' '\n' | grep ':' | head -1)
if [ -z "${POD_IPV6}" ]; then
    POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[0].ip}')
fi
echo "Pod IPv6: ${POD_IPV6}"
echo ""

# ── Helper: run curl N times, collect timing ───────────────────
# Writes time_connect and time_total (in ms) to a temp file, then computes stats.
run_latency_test() {
    local label="$1"
    local curl_args="$2"
    local tmpfile
    tmpfile=$(mktemp)

    echo "  Running ${ITERATIONS} requests..."
    for i in $(seq 1 "${ITERATIONS}"); do
        kubectl exec nat464-demo -c app -- \
            curl -s -o /dev/null -w '%{time_connect} %{time_total}\n' \
            ${curl_args} 2>/dev/null || echo "0 0"
    done > "${tmpfile}"

    # Compute stats with awk
    awk -v label="${label}" '
    BEGIN { n=0 }
    $2 > 0 {
        connect[n] = $1 * 1000
        total[n] = $2 * 1000
        n++
    }
    END {
        if (n == 0) { print "    No successful requests"; exit }
        # Sort for percentiles
        asort(connect, sc)
        asort(total, st)
        p50 = int(n * 0.50); if (p50 < 1) p50 = 1
        p95 = int(n * 0.95); if (p95 < 1) p95 = 1
        p99 = int(n * 0.99); if (p99 < 1) p99 = 1

        printf "    Samples:      %d\n", n
        printf "    Connect (ms): p50=%.2f  p95=%.2f  p99=%.2f\n", sc[p50], sc[p95], sc[p99]
        printf "    Total   (ms): p50=%.2f  p95=%.2f  p99=%.2f\n", st[p50], st[p95], st[p99]
    }' "${tmpfile}"

    rm -f "${tmpfile}"
}

run_throughput_test() {
    local label="$1"
    local curl_args="$2"
    local tmpfile
    tmpfile=$(mktemp)

    echo "  Running ${ITERATIONS} requests..."
    for i in $(seq 1 "${ITERATIONS}"); do
        kubectl exec nat464-demo -c app -- \
            curl -s -o /dev/null -w '%{speed_download} %{size_download} %{time_total}\n' \
            ${curl_args} 2>/dev/null || echo "0 0 0"
    done > "${tmpfile}"

    awk -v label="${label}" '
    BEGIN { n=0; total_bytes=0; total_time=0 }
    $3 > 0 {
        total_bytes += $2
        total_time += $3
        speeds[n] = $1
        n++
    }
    END {
        if (n == 0) { print "    No successful requests"; exit }
        asort(speeds, ss)
        p50 = int(n * 0.50); if (p50 < 1) p50 = 1
        avg_speed = total_bytes / total_time

        printf "    Samples:            %d\n", n
        printf "    Avg throughput:     %.0f bytes/sec (%.2f KB/s)\n", avg_speed, avg_speed/1024
        printf "    Median speed:       %.0f bytes/sec (%.2f KB/s)\n", ss[p50], ss[p50]/1024
        printf "    Total transferred:  %.0f bytes in %.3f sec\n", total_bytes, total_time
    }' "${tmpfile}"

    rm -f "${tmpfile}"
}

# ── Test 1: Baseline latency (localhost, no sidecar) ───────────
echo "===== BASELINE: Latency (curl 127.0.0.1:80, no sidecar) ====="
run_latency_test "baseline" "http://127.0.0.1:80/"
echo ""

# ── Test 2: Sidecar latency (through inbound path) ────────────
echo "===== SIDECAR: Latency (curl [::1]:8080, through sidecar) ====="
run_latency_test "sidecar" "http://[::1]:8080/"
echo ""

# ── Test 3: Baseline throughput ────────────────────────────────
echo "===== BASELINE: Throughput (curl 127.0.0.1:80) ====="
run_throughput_test "baseline" "http://127.0.0.1:80/"
echo ""

# ── Test 4: Sidecar throughput ─────────────────────────────────
echo "===== SIDECAR: Throughput (curl [::1]:8080) ====="
run_throughput_test "sidecar" "http://[::1]:8080/"
echo ""

# ── Test 5: Outbound SOCKS5 latency ───────────────────────────
echo "===== OUTBOUND: SOCKS5 latency (curl -x socks5h://127.0.0.1:1080 example.com) ====="
echo "  Running ${ITERATIONS} requests (external, may be slower)..."
OUTBOUND_TMP=$(mktemp)
for i in $(seq 1 "${ITERATIONS}"); do
    kubectl exec nat464-demo -c app -- \
        curl -s -o /dev/null -w '%{time_connect} %{time_total}\n' \
        -x socks5h://127.0.0.1:1080 http://example.com 2>/dev/null || echo "0 0"
done > "${OUTBOUND_TMP}"

awk '
BEGIN { n=0 }
$2 > 0 {
    connect[n] = $1 * 1000
    total[n] = $2 * 1000
    n++
}
END {
    if (n == 0) { print "    No successful requests"; exit }
    asort(connect, sc)
    asort(total, st)
    p50 = int(n * 0.50); if (p50 < 1) p50 = 1
    p95 = int(n * 0.95); if (p95 < 1) p95 = 1
    p99 = int(n * 0.99); if (p99 < 1) p99 = 1

    printf "    Samples:      %d\n", n
    printf "    Connect (ms): p50=%.2f  p95=%.2f  p99=%.2f\n", sc[p50], sc[p95], sc[p99]
    printf "    Total   (ms): p50=%.2f  p95=%.2f  p99=%.2f\n", st[p50], st[p95], st[p99]
}' "${OUTBOUND_TMP}"
rm -f "${OUTBOUND_TMP}"
echo ""

# ── Summary ────────────────────────────────────────────────────
echo "============================================================"
echo "Benchmark complete."
echo ""
echo "Notes:"
echo "  - Baseline uses 127.0.0.1:80 (direct to nginx, no sidecar)"
echo "  - Sidecar uses [::1]:8080 (IPv6 -> sidecar -> 127.0.0.1:80)"
echo "  - Outbound uses SOCKS5 proxy to example.com (includes DNS + internet RTT)"
echo "  - For raw TCP throughput with iperf3, see deploy/benchmark-pod.yaml"
echo ""
echo "Manual iperf3 test (optional):"
echo "  1. kubectl apply -f deploy/benchmark-pod.yaml"
echo "  2. kubectl exec nat464-demo -c app -- sh -c 'apt-get update && apt-get install -y iperf3 && iperf3 -s -D'"
echo "  3. kubectl exec nat464-bench -- iperf3 -c <pod-ipv4> -p 5201 -t 10  # baseline"
echo "  4. (iperf3 through sidecar requires forwarding port 5201)"
