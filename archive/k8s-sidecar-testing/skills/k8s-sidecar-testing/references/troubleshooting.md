# Troubleshooting

Read the failed command's stderr and the named context/namespace first. All diagnostic kubectl commands should retain `--context "$KUBE_CONTEXT" --namespace "$KUBE_NAMESPACE"`; changing the current context is unnecessary.

## Cluster and VM setup

- **VM daemon/launch failure:** inspect `multipass list` and `multipass info VM_NAME`. Do not recreate an existing VM automatically or change the global driver as a generic repair. Supported drivers depend on host architecture and installed Multipass version.
- **Missing IPv6:** inspect the node's `ip -j addr show` and the Pod's `.status.podIPs`. The setup helper requires node addresses already assigned; it does not invent addresses or persist host networking. A missing IPv6 Pod address fails validation instead of falling back to IPv4.
- **k3s network family mismatch:** dual-stack must be configured at initial cluster creation. IPv6-primary requires matching node address ordering. The bundled helper intentionally chooses IPv4-primary dual-stack. ULA masquerading does not itself provide upstream IPv6 connectivity.
- **kubeconfig permission denied:** use the intended administrative user or a separate owner-readable kubeconfig with appropriate credentials. Do not use `chmod 644` on administrative credentials.
- **CoreDNS/DNS64:** the plugin no longer injects a DNS64 stanza into CoreDNS. Verify installed CoreDNS plugin support, configuration loading, and actual NAT64 translation/routing before making a separate DNS64 change. AAAA synthesis alone does not implement NAT64.

## Deployment and validation

- **Missing manifest:** `--project-dir` identifies the nat464 source tree. Installing this skill does not provide that project's `deploy/` files. Inspect/adapt the actual project manifests and ensure the peer `app` image has curl and sh.
- **Unowned resource:** use a fresh dedicated test namespace or inspect ownership manually. The helper deliberately does not label/adopt arbitrary pre-existing Pods and ConfigMaps.
- **Immutable Pod update:** inspect the diff; if replacement is requested, run the targeted teardown and redeploy. Deployment never deletes resources preemptively.
- **ImagePullBackOff/ErrImageNeverPull:** the built image must be imported into containerd on the node that will run the Pod. The helper imports only into the local VM. Use `--local-image` only when that image exists there; multi-node clusters need an appropriate registry or import on every eligible node.
- **ss/netstat unavailable:** this is a prerequisite failure, not evidence that the app is IPv4-only. Prepare a diagnostic-capable test image instead of installing packages into running containers.
- **Direct IPv6 failure:** require the successful peer-to-sidecar IPv6 control first. Curl 7 proves inability to connect at the target port in that setup; the additional socket check supports the IPv4-only explanation. Network policy rejection can also produce connection failure, so this is not a universal proof about application binding. Curl 28 means timeout and is a failed/inconclusive check.
- **SOCKS5 failure:** inspect sidecar logs, the loopback proxy listener, peer IPv6 reachability, and DNS separately. `socks5h` resolves the hostname through the proxy. An external outage does not isolate a sidecar defect.
- **Benchmark errors:** report sample counts and failures. Zero/invalid/non-finite timing values and HTTP errors do not become valid samples. Kubectl startup overhead is outside curl's reported timing, but the shared node and tiny payload still affect the experiment.

## Upstream sources reviewed 2026-09-05

- [K3s networking](https://docs.k3s.io/networking/basic-network-options): distinct dual-stack and IPv6-only configurations, initial-creation requirement, family ordering, ULA masquerading.
- [K3s installer configuration](https://docs.k3s.io/installation/configuration): explicit version selection and installer/server arguments.
- [kubectl exec](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_exec/): explicit container/command separation and client options.
- [curl manual](https://curl.se/docs/manpage.html): failure exit codes, total/connect deadlines, proxy resolution, and write-out metrics.
- [Multipass delete](https://canonical.com/multipass/docs/latest/reference/command-line-interface/delete/): targeted permanent deletion versus global deletion/purge behavior.

These facts changed the helpers' design: explicit topology instead of EKS claims, no automatic DNS64, selected targets on every command, successful control requests before negative-test conclusions, and narrowly scoped cleanup.
