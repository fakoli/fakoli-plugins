---
name: k8s-sidecar-testing
description: Test the nat464-sidecar demo topology in a selected Kubernetes test namespace, verify IPv6 translation paths, and compare HTTP latency. Includes optional disposable Multipass/k3s setup.
---

# K8s Sidecar Testing

Use the helpers for the nat464 demo topology. Inspect the actual project manifests and container names first; adapt the checks if its contract differs. The supplied cluster setup is IPv4-primary **dual-stack**, not IPv6-only or an AWS EKS emulator.

Resolve `SKILL_DIR` to the directory containing this installed `SKILL.md`. Helpers live at `$SKILL_DIR/scripts/`; manifests and Dockerfile belong to the **user's project**, selected with `--project-dir`. These are separate paths. When working inside a VM, transfer the whole skill directory as well as the project.

1. Read [the plugin README](../../README.md) for prerequisites, topology, arguments, and mutation boundaries. Reuse an authorized existing test environment when available; VM provisioning is optional.
2. Select an explicit kubeconfig context and a dedicated namespace using `--context`/`--namespace` or `KUBE_CONTEXT`/`KUBE_NAMESPACE`. Helpers preserve the caller's `KUBECONFIG`. Never infer a target from whichever context is current.
3. For existing pods, run `validate-paths.sh`; it does not deploy resources. For a requested deployment, run `deploy-test.sh --project-dir ...` with both project manifests. It validates supported resources and ownership before applying, then returns the checks' actual exit status. Existing unowned resources are not adopted.
4. Run `benchmark.sh --iterations 50` only when performance measurement is requested. Report failed samples as well as p50/p95/p99. External HTTP checks require `--external-url`; a skipped check is not a pass.
5. On requested cleanup, `teardown.sh` removes only known, owned Pods/ConfigMaps in the selected namespace. VM deletion is a separate explicitly targeted operation documented in the README.

All helpers accept `--help`. Provisioning, image import, deploy, cleanup, and benchmarks are independent operations; a request to inspect or validate does not imply permission to run all phases. Treat nonzero exits, missing prerequisites, absent IPv6, timeout, and infrastructure errors as incomplete/failed evidence. Do not rerun or broaden scope silently.

See [troubleshooting](references/troubleshooting.md) for diagnosing failed checks and the authoritative upstream sources behind networking assumptions.
