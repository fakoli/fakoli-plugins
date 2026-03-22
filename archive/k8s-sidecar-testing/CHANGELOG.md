# Changelog

## 1.1.0 (2026-02-06)

### Added
- `validate-paths.sh` - Focused 5-test path validation with PASS/FAIL output
  - nginx IPv4-only proof (ss + direct IPv6 refusal)
  - Inbound IPv6->IPv4 via sidecar
  - Outbound SOCKS5 to IPv6 peer pod
  - Outbound SOCKS5 to external host
- IPv6 peer pod manifest (`ipv6-peer-nginx.yaml`) for outbound testing
- Benchmark pod manifest (`benchmark-pod.yaml`) for iperf3

### Changed
- `deploy-test.sh` expanded from 4 to 8 automated tests:
  - Added nginx IPv4-only confirmation (ss -tlnp)
  - Added direct IPv6 to nginx:80 refusal test
  - Added outbound SOCKS5 to external (example.com)
  - Added outbound SOCKS5 to IPv6 peer pod
  - Auto-deploys ipv6-peer pod if manifest exists
- `benchmark.sh` rewritten from iperf3 stub to real HTTP benchmarks:
  - Baseline vs sidecar latency (p50/p95/p99)
  - Baseline vs sidecar throughput
  - Outbound SOCKS5 latency measurement

### Fixed
- Port-matching regex now anchors to avoid false positives (:::8080 matching :::80)
- Awk scripts use `exit` instead of `next` in END blocks (gawk compatibility)
- Arithmetic uses `$((x + 1))` instead of `((x++))` to avoid set -e failures

## 1.0.0 (2026-02-06)

- Initial release
- VM provisioning with Multipass (vm-setup.sh)
- k3s cluster setup with dual-stack networking and CoreDNS DNS64 (k3s-setup.sh)
- Container image build and k3s import (build-image.sh)
- Automated deploy and verification tests (deploy-test.sh)
- iperf3 benchmark scaffolding (benchmark.sh)
- Teardown script for pods, images, and VM (teardown.sh)
- Troubleshooting reference guide
