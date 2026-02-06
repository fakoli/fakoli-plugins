---
name: k8s-sidecar-testing
description: "End-to-end testing workflow for nat464-sidecar in IPv6-only Kubernetes clusters. Use when setting up test environments, deploying the sidecar to k3s, verifying IPv6-to-IPv4 translation (inbound and outbound), benchmarking with iperf3, or troubleshooting pod networking issues. Triggers: 'test the sidecar', 'set up test cluster', 'verify IPv6 translation', 'deploy to k3s', 'benchmark sidecar', 'test inbound/outbound', 'IPv6-only cluster setup'."
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
tar czf /tmp/nat464.tar.gz -C /path/to nat464-sidecar
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

Runs four automated tests:
1. Health check (`/healthz` endpoint)
2. Inbound translation (curl -6 pod:8080 through sidecar to nginx:80)
3. Sidecar logs inspection
4. Pod status verification

Manual outbound test:
```bash
kubectl exec nat464-demo -c app -- curl -x socks5h://127.0.0.1:1080 http://example.com
```

### Phase 5: Benchmark (optional, run inside VM)

```bash
scripts/benchmark.sh
```

Measures baseline vs sidecar-translated throughput using iperf3.

### Phase 6: Teardown

```bash
scripts/teardown.sh          # Clean pods/images, keep VM
scripts/teardown.sh --vm     # Also delete the Multipass VM
```

## Quick Verification Commands

From inside the VM after deployment:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
POD_IPV6=$(kubectl get pod nat464-demo -o jsonpath='{.status.podIPs[0].ip}')

# Health
kubectl exec nat464-demo -c app -- wget -qO- http://localhost:9464/healthz

# Inbound: IPv6 → IPv4
kubectl run curl-test --rm -i --restart=Never --image=curlimages/curl -- curl -6 -s http://[${POD_IPV6}]:8080/

# Outbound: IPv4 → IPv6 via SOCKS5
kubectl exec nat464-demo -c app -- curl -x socks5h://127.0.0.1:1080 http://example.com

# Logs
kubectl logs nat464-demo -c nat464-sidecar
```

## Troubleshooting

See [references/troubleshooting.md](references/troubleshooting.md) for common issues with VMs, k3s, pod networking, and IPv6 connectivity.
