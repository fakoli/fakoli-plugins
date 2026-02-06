# K8s Sidecar Testing

End-to-end testing workflow for [nat464-sidecar](https://github.com/fakoli/nat464-sidecar) in IPv6-only Kubernetes clusters.

## What It Does

Provides a phased testing workflow using Multipass VMs and k3s to validate NAT464 translation in a real Kubernetes environment that emulates AWS EKS IPv6 networking.

## Phases

1. **VM Provisioning** - Create an Ubuntu VM with Multipass
2. **k3s Setup** - Install k3s with dual-stack networking and CoreDNS DNS64
3. **Image Build** - Build the sidecar container and import into k3s
4. **Deploy & Verify** - Deploy the sidecar pod and run automated tests (health check, inbound IPv6-to-IPv4, logs, status)
5. **Benchmark** - Measure translation overhead with iperf3
6. **Teardown** - Clean up pods, images, and optionally the VM

## Scripts

| Script | Phase | Runs On |
|--------|-------|---------|
| `vm-setup.sh` | 1 | Mac host |
| `k3s-setup.sh` | 2 | Inside VM |
| `build-image.sh` | 3 | Inside VM |
| `deploy-test.sh` | 4 | Inside VM |
| `benchmark.sh` | 5 | Inside VM |
| `teardown.sh` | 6 | Inside VM or Mac |

## Requirements

- macOS with [Multipass](https://multipass.run/) installed
- Docker (inside VM, installed by k3s)
- nat464-sidecar source code

## Usage

Invoke the skill when working on nat464-sidecar:

```
/k8s-sidecar-testing
```

Or trigger naturally: "test the sidecar", "set up test cluster", "deploy to k3s".

## License

MIT
