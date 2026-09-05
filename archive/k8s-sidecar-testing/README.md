# K8s Sidecar Testing

Project-specific helpers for the nat464-sidecar demo. This package was archived from the general marketplace in March 2026; these maintenance changes preserve it for deliberate use without restoring its catalog entry. It has native Codex and Claude Code manifests and one discoverable skill.

The helpers verify health, IPv4-only application listening, inbound IPv6 translation, direct IPv6 port 80 failure, and outbound SOCKS5 translation to a peer. Deployment failures and failed checks exit nonzero. Benchmarks report successful and failed samples separately.

## Requirements and topology

Host tools: Bash, Python 3.9+, and `kubectl` for cluster operations. Optional provisioning needs Multipass; VM setup installs Docker, curl, iproute2, and Python. k3s setup and image import require noninteractive sudo on the chosen disposable Linux VM. No API keys are used.

Select a readable kubeconfig, explicit context, and an existing dedicated test namespace. The scripts reject `default` and Kubernetes system namespaces. They never change the current context or overwrite `KUBECONFIG`.

The project's manifests must provide:

- Pod `nat464-demo`: container `app` serves an IPv4-only HTTP application at port 80; container `nat464-sidecar` exposes IPv6 port 8080, SOCKS5 at 127.0.0.1:1080, and health at 127.0.0.1:9464/healthz.
- Pod `ipv6-peer`: container `app` serves IPv6 HTTP port 80, with response marker `ipv6-peer-ok`.
- Both `app` containers need `curl` and `sh`; the demo app also needs `ss` or `netstat`. Build these into the test images. The scripts do not install packages into running pods.
- Both Pods must have IPv6 addresses and permit peer-to-demo IPv6 traffic. Application content defaults to marker `nginx`; override `--inbound-marker`/`--peer-marker` when appropriate.

`deploy/example-pod.yaml` and `deploy/ipv6-peer-nginx.yaml` are inputs from the **user's nat464 project**, not files shipped by this plugin. Deployment allows only the two named Pods plus `nat464-demo-nginx-conf` and `ipv6-peer-nginx-conf` ConfigMaps; it rejects other kinds, names, namespaces, and host-namespace Pods. Review the source manifests as part of the deployment request. The helper labels resources it manages and refuses to overwrite unowned existing resources. It does not delete/recreate immutable Pods automatically: use requested targeted teardown before redeployment when needed.

## Select paths and run

`SKILL_DIR` means the installed skill directory, independent of the current project. Run helpers through Bash or directly:

```bash
SKILL_DIR=/absolute/path/to/k8s-sidecar-testing/skills/k8s-sidecar-testing
export KUBE_CONTEXT=your-test-context
export KUBE_NAMESPACE=sidecar-tests
bash "$SKILL_DIR/scripts/validate-paths.sh"
bash "$SKILL_DIR/scripts/deploy-test.sh" --project-dir /path/to/nat464-sidecar
bash "$SKILL_DIR/scripts/benchmark.sh" --iterations 50
bash "$SKILL_DIR/scripts/teardown.sh"
```

Select only the operation the user requested. Context and namespace can instead be supplied on each command with `--context` and `--namespace`. `--manifest` and `--peer-manifest` resolve relative to `--project-dir` (default: current directory), or accept absolute paths. A structural `--local-image nat464-sidecar:test` override sets the sidecar's image and `imagePullPolicy: Never` without editing project files.

Validation runs from the existing peer container, so no transient probe Pods are created. Direct IPv6 refusal requires curl exit 7 inside a successful `kubectl exec` plus a successful inbound control request. A timeout, API failure, missing tool, HTTP error, or empty output is not proof of refusal. Optional external checks use an explicit endpoint:

```bash
bash "$SKILL_DIR/scripts/validate-paths.sh" --external-url https://example.com/
```

A successful HTTP response means curl succeeded with `--fail`; it does not specifically assert status 200. Curl calls disable environment proxy bypass for SOCKS5 and disable proxies for direct tests. They bound connection time to 5 seconds and total request time to 15 seconds. Process deadlines also cover a hung kubectl exec. An external check omitted by the caller is reported as skipped.

The benchmark measures sequential HTTP request latency and payload rate, not raw link capacity. It uses nearest-rank percentiles and excludes failed samples from timings while counting failures and returning nonzero. External measurements include DNS/proxy/internet latency and are not isolated sidecar overhead. Python statistics work on macOS and Ubuntu without GNU awk.

## Optional disposable VM setup

Provisioning is a separate operation. Existing VMs are not replaced:

```bash
bash "$SKILL_DIR/scripts/vm-setup.sh" --name nat464-dev --cpus 2 --memory 4G --disk 20G
```

Transfer both the skill directory and your project into the VM. On that VM, choose an explicit released k3s version and addresses already assigned to the node:

```bash
bash "$SKILL_DIR/scripts/k3s-setup.sh" --version "$K3S_VERSION" --node-ipv4 "$NODE_IPV4" --node-ipv6 "$NODE_IPV6"
bash "$SKILL_DIR/scripts/build-image.sh" --project-dir /home/ubuntu/nat464-sidecar --image nat464-sidecar:test
```

Setup refuses existing k3s state. It downloads the upstream installer, installs the selected version, waits for Ready with a deadline, and keeps kubeconfig permissions at `0600`. Obtain a readable kubeconfig with owner-only permissions; never make the administrative kubeconfig world-readable. Create/select your intended test namespace before deployment.

This creates **IPv4-primary dual-stack** Pod CIDRs `10.42.0.0/16,fd00:42::/56` and Service CIDRs `10.43.0.0/16,fd00:43::/112`. It does not configure DNS64, NAT64 routing, public IPv6 reachability, or EKS parity. A separate IPv6-only cluster requires its own reviewed configuration. Image build uses this VM's Docker daemon and imports into this VM's k3s containerd `k8s.io` namespace; it is not a remote-context operation.

Provisioning/build/install processes have 10–30 minute deadlines; Kubernetes readiness/deletion and API/exec calls have shorter explicit bounds. On timeout or partial provisioning failure the command fails and leaves resources for inspection; it does not destroy a VM automatically.

## Cleanup and migration from 1.x

Version 2 replaces positional/default machine targets with named arguments and explicit Kubernetes targeting. `teardown.sh --vm` is removed. Teardown deletes only the known owned Pods/ConfigMaps; it preserves other resources, the namespace, images, and VMs. For a separately requested permanent VM deletion, identify the exact VM and use `multipass delete --purge VM_NAME`; never run global `multipass purge` or `delete --all` as test cleanup.

See [troubleshooting](skills/k8s-sidecar-testing/references/troubleshooting.md) for failures and upstream sources.

## Maintainer verification

```bash
python3 -m unittest discover -s plugins/k8s-sidecar-testing/tests -v
```

Tests run shell entrypoints against command fakes in temporary directories, checking success/failure semantics, ownership, project paths, time bounds, and statistics. They do not launch VMs, install k3s, alter a cluster, or prove real network translation works. Run the selected workflow on an authorized test cluster for that evidence.

MIT license.
