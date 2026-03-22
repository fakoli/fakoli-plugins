---
name: k8s-sidecar-testing
description: "End-to-end testing workflow for nat464-sidecar in IPv6-only Kubernetes clusters. Use when setting up test environments, deploying the sidecar to k3s, verifying IPv6-to-IPv4 translation (inbound and outbound), benchmarking performance, running path validation, or troubleshooting pod networking issues. Triggers: 'test the sidecar', 'set up test cluster', 'verify IPv6 translation', 'deploy to k3s', 'benchmark sidecar', 'validate paths', 'test inbound/outbound', 'IPv6-only cluster setup'."
---

# K8s Sidecar Testing

Test nat464-sidecar in an IPv6-only Kubernetes cluster using Multipass VMs and k3s.

## Workflow

Execute phases in order. Each phase has a corresponding script in `scripts/`.

### Phase 1: VM Provisioning (run on Mac)

```bash
scripts/vm-setup.sh [vm-name] [cpus] [memory] [disk]
# Defaults: nat464-dev, 2 CPUs, 4G RAM, 20G disk
```

Then transfer the project into the VM:
```bash
tar czf /tmp/nat464.tar.gz --exclude=target --exclude=.git -C /path/to nat464-sidecar
multipass transfer /tmp/nat464.tar.gz nat464-dev:/home/ubuntu/
multipass shell nat464-dev
# Inside VM:
tar xzf nat464.tar.gz
```

### Phase 2: k3s Cluster Setup (run inside VM)

```bash
scripts/k3s-setup.sh
```

Creates an IPv6-only pod network emulating AWS EKS:
- Pod CIDR: `fd00:42::/56` (IPv6-only, like EKS)
- Service CIDR: `fd00:43::/112` (IPv6-only)
- Node: dual-stack (like EKS ENI nodes)
- CoreDNS DNS64 with `64:ff9b::/96` prefix

### Phase 3: Build Container Image (run inside VM)

```bash
scripts/build-image.sh [project-dir]
# Default: /home/ubuntu/nat464-sidecar
```

Builds with Docker, imports into k3s containerd.

### Phase 4: Deploy and Verify (run inside VM)

```bash
scripts/deploy-test.sh [manifest-path]
# Default: /home/ubuntu/nat464-sidecar/deploy/example-pod.yaml
```

Runs eight automated tests:
1. Health check (`/healthz` endpoint)
2. Nginx IPv4-only confirmation (`ss -tlnp` shows `0.0.0.0:80` only)
3. Direct IPv6 to nginx:80 refused (proving sidecar is required)
4. Inbound translation (curl -6 pod:8080 through sidecar to nginx:80)
5. Outbound SOCKS5 to external host (example.com)
6. Outbound SOCKS5 to IPv6 peer pod (deploys `ipv6-peer-nginx.yaml` automatically)
7. Sidecar logs inspection
8. Pod status verification

### Phase 5: Path Validation (run inside VM)

```bash
scripts/validate-paths.sh
```

Focused validation with PASS/FAIL for all translation paths:
- nginx IPv4-only (ss + direct IPv6 refusal)
- Inbound IPv6->IPv4 via sidecar
- Outbound SOCKS5 to IPv6 peer pod
- Outbound SOCKS5 to external host

### Phase 6: Benchmark (run inside VM)

```bash
scripts/benchmark.sh [iterations]
# Default: 50 iterations per test
```

Measures HTTP latency (p50/p95/p99) and throughput:
- Baseline: direct `127.0.0.1:80` (no sidecar)
- Sidecar: `[::1]:8080` (through inbound path)
- Outbound: SOCKS5 to example.com

### Phase 7: Teardown

```bash
scripts/teardown.sh          # Clean pods/images, keep VM
scripts/teardown.sh --vm     # Also delete the Multipass VM
```

## Quick Verification Commands

From inside the VM after deployment:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[*].ip}' | tr ' ' '\n' | grep ':' | head -1)

# Health
kubectl exec nat464-demo -c app -- wget -qO- http://localhost:9464/healthz

# Inbound: IPv6 -> IPv4
kubectl run curl-test --rm -i --restart=Never --image=curlimages/curl -- curl -6 -s http://[${POD_IPV6}]:8080/

# Outbound: IPv4 -> IPv6 via SOCKS5
kubectl exec nat464-demo -c app -- curl -x socks5h://127.0.0.1:1080 http://example.com

# Logs
kubectl logs nat464-demo -c nat464-sidecar
```

## Deploy Manifests

| Manifest | Purpose |
|----------|---------|
| `deploy/example-pod.yaml` | Main demo pod: IPv4-only nginx + sidecar (ConfigMap forces `listen 80;` only) |
| `deploy/ipv6-peer-nginx.yaml` | IPv6-only nginx peer (ConfigMap forces `listen [::]:80;` only) |
| `deploy/benchmark-pod.yaml` | iperf3 pod for manual TCP throughput testing |

## Troubleshooting

See [references/troubleshooting.md](references/troubleshooting.md) for common issues with VMs, k3s, pod networking, and IPv6 connectivity.
