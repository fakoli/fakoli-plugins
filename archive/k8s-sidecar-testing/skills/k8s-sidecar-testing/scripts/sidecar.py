#!/usr/bin/env python3
"""Bounded nat464 test helpers; no third-party Python dependencies."""
import argparse
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile

OWNER_KEY = "app.kubernetes.io/managed-by"
OWNER = "k8s-sidecar-testing"
RESOURCES = {"Pod": {"nat464-demo", "ipv6-peer"},
             "ConfigMap": {"nat464-demo-nginx-conf", "ipv6-peer-nginx-conf"}}


class Failure(RuntimeError):
    pass


def run(argv, *, timeout=120, input=None, check=True, env=None):
    """Bound the entire process group, including hung exec/build descendants."""
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True, env=env)
    except OSError as exc:
        raise Failure(f"Cannot run {argv[0]}: {exc}") from exc
    try:
        stdout, stderr = proc.communicate(input, timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise Failure(f"{argv[0]} exceeded {timeout}s") from exc
    result = subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
    if check and result.returncode:
        raise Failure(f"{argv[0]} exited {result.returncode}: {stderr.strip() or stdout.strip()}")
    return result


def require(*names):
    for name in names:
        if not shutil.which(name):
            raise Failure(f"Missing prerequisite: {name}")


def integer(value):
    if not re.fullmatch(r"[1-9][0-9]*", str(value)) or int(value) > 10000:
        raise argparse.ArgumentTypeError("expected an integer from 1 to 10000")
    return int(value)


class Cluster:
    def __init__(self, args):
        if not args.context or not args.namespace:
            raise Failure("Specify --context and --namespace (or KUBE_CONTEXT and KUBE_NAMESPACE)")
        if args.namespace in {"default", "kube-system", "kube-public", "kube-node-lease"}:
            raise Failure("Use a dedicated test namespace, not a default/system namespace")
        require("kubectl")
        self.args = args
        self.prefix = ["kubectl", f"--context={args.context}", f"--namespace={args.namespace}",
                       "--request-timeout=30s"]

    def k(self, *args, **kwargs):
        return run(self.prefix + list(args), **kwargs)

    def preflight(self):
        self.k("get", "namespace", self.args.namespace)
        print(f"Target: context={self.args.context} namespace={self.args.namespace}", flush=True)

    def ipv6(self, pod):
        obj = json.loads(self.k("get", "pod", pod, "-o", "json").stdout)
        for entry in obj.get("status", {}).get("podIPs", []):
            addr = ipaddress.ip_address(entry["ip"])
            if addr.version == 6:
                return str(addr)
        raise Failure(f"No IPv6 address on pod {pod}; IPv4 is not a substitute for this test")

    def curl(self, pod, container, *args):
        return self.k("exec", pod, "-c", container, "--", "curl", "--globoff", "--silent",
                      "--show-error", "--fail", "--connect-timeout", "5", "--max-time", "15",
                      *args, timeout=45, check=False)

    def prepare(self, paths):
        """Validate every document and existing ownership before any apply."""
        items = []
        seen = set()
        for path in paths:
            if not path.is_file():
                raise Failure(f"Missing project manifest: {path}")
            obj = json.loads(self.k("apply", "--dry-run=client", "-f", str(path), "-o", "json").stdout)
            for item in obj.get("items", []) if obj.get("kind") == "List" else [obj]:
                kind = item.get("kind")
                meta = item.get("metadata", {})
                name = meta.get("name")
                if item.get("apiVersion") != "v1" or name not in RESOURCES.get(kind, set()):
                    raise Failure(f"Unsupported manifest resource: {kind}/{name}; only the demo/peer Pods and ConfigMaps are allowed")
                if meta.get("namespace", self.args.namespace) != self.args.namespace:
                    raise Failure(f"Manifest namespace differs from {self.args.namespace}")
                if (kind, name) in seen:
                    raise Failure(f"Duplicate manifest resource: {kind}/{name}")
                seen.add((kind, name))
                existing = self.k("get", kind, name, "--ignore-not-found", "-o", "json").stdout.strip()
                if existing and json.loads(existing).get("metadata", {}).get("labels", {}).get(OWNER_KEY) != OWNER:
                    raise Failure(f"Refusing to overwrite unowned {kind}/{name}; use a fresh test namespace")
                meta["namespace"] = self.args.namespace
                meta.setdefault("labels", {})[OWNER_KEY] = OWNER
                if kind == "Pod":
                    spec = item.get("spec", {})
                    if spec.get("hostNetwork") or spec.get("hostPID") or spec.get("hostIPC"):
                        raise Failure("Test pods must not share host namespaces")
                    if name == "nat464-demo":
                        sidecars = [c for c in spec.get("containers", []) if c.get("name") == "nat464-sidecar"]
                        if len(sidecars) != 1:
                            raise Failure("nat464-demo must contain a nat464-sidecar container")
                        # Structural update: never insert YAML with sed or duplicate a field.
                        if self.args.local_image:
                            sidecars[0]["image"] = self.args.local_image
                            sidecars[0]["imagePullPolicy"] = "Never"
                items.append(item)
        if not {("Pod", "nat464-demo"), ("Pod", "ipv6-peer")} <= seen:
            raise Failure("Deployment requires both nat464-demo and ipv6-peer Pod manifests")
        return {"apiVersion": "v1", "kind": "List", "items": items}


def validate(cluster):
    pod_v6 = cluster.ipv6("nat464-demo")
    peer_v6 = cluster.ipv6("ipv6-peer")
    passed = failed = 0

    def report(ok, label, detail=""):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"{'PASS' if ok else 'FAIL'}: {label}" + (f" ({detail.strip()[:300]})" if detail else ""))

    health = cluster.curl("nat464-demo", "app", "--noproxy", "*", "http://127.0.0.1:9464/healthz")
    report(health.returncode == 0, "health endpoint", health.stderr)
    sockets = cluster.k("exec", "nat464-demo", "-c", "app", "--", "sh", "-c",
                        "ss -tln || netstat -tln", timeout=45, check=False)
    # Treat absent diagnostics as failure, not proof. Match local socket fields, including wildcard IPv6.
    listeners = []
    for line in sockets.stdout.splitlines():
        cols = line.split()
        if cols and cols[0] == "LISTEN" and len(cols) >= 4:  # ss
            listeners.append(cols[3])
        elif cols and cols[0] in {"tcp", "tcp6"} and len(cols) >= 6 and cols[-1] == "LISTEN":
            listeners.append(cols[3])
    port80 = [s for s in listeners if s.endswith(":80")]
    ipv4_only = "0.0.0.0:80" in port80 and all(s.count(":") == 1 and not s.startswith("*:") for s in port80)
    report(sockets.returncode == 0 and ipv4_only, "application listens on IPv4 port 80 only", sockets.stderr)

    # A successful peer -> sidecar control establishes client tooling and IPv6 connectivity first.
    inbound = cluster.curl("ipv6-peer", "app", "--noproxy", "*", "-6", f"http://[{pod_v6}]:8080/")
    inbound_ok = inbound.returncode == 0 and cluster.args.inbound_marker in inbound.stdout
    report(inbound_ok, "peer IPv6 -> sidecar -> IPv4 application", inbound.stderr)
    # Print the curl status *inside* the exec session. A kubectl failure can never be refusal proof.
    direct = cluster.k("exec", "ipv6-peer", "-c", "app", "--", "sh", "-c",
                       'curl --globoff --silent --show-error --noproxy "*" -6 --connect-timeout 5 --max-time 15 "$1" >/dev/null; rc=$?; printf "CURL_EXIT=%s\\n" "$rc"',
                       "sh", f"http://[{pod_v6}]:80/", timeout=45, check=False)
    report(inbound_ok and direct.returncode == 0 and direct.stdout.strip() == "CURL_EXIT=7",
           "direct IPv6 port 80 cannot connect (curl 7, with working IPv6 control)", direct.stderr)
    peer = cluster.curl("nat464-demo", "app", "--noproxy", "", "--proxy", "socks5h://127.0.0.1:1080", f"http://[{peer_v6}]:80/")
    report(peer.returncode == 0 and cluster.args.peer_marker in peer.stdout,
           "SOCKS5 -> IPv6 peer", peer.stderr)
    if cluster.args.external_url:
        external = cluster.curl("nat464-demo", "app", "--noproxy", "", "--proxy", "socks5h://127.0.0.1:1080", cluster.args.external_url)
        report(external.returncode == 0, "SOCKS5 -> requested external URL", external.stderr)
    else:
        print("SKIP: external network check (provide --external-url to include it)")
    print(f"Results: {passed} passed, {failed} failed")
    return int(failed > 0)


def benchmark(cluster):
    failures = 0
    tests = [("baseline", ["--noproxy", "*", "http://127.0.0.1:80/"]),
             ("sidecar", ["--noproxy", "*", "http://[::1]:8080/"])]
    if cluster.args.external_url:
        tests.append(("external SOCKS5 (includes network RTT)", ["--noproxy", "", "--proxy", "socks5h://127.0.0.1:1080", cluster.args.external_url]))
    for label, args in tests:
        samples = []
        for _ in range(cluster.args.iterations):
            result = cluster.curl("nat464-demo", "app", "-o", "/dev/null", "-w", "%{time_connect} %{time_total} %{size_download}", *args)
            try:
                values = [float(x) for x in result.stdout.split()]
                valid = (result.returncode == 0 and len(values) == 3 and
                         all(math.isfinite(x) and x >= 0 for x in values) and values[1] > 0)
            except ValueError:
                valid = False
            if valid:
                samples.append(values)
            else:
                failures += 1
                print(f"FAIL: {label} sample: {result.stderr.strip() or 'invalid/unsuccessful curl sample'}", file=sys.stderr)
        print(f"{label}: {len(samples)} successful, {cluster.args.iterations - len(samples)} failed")
        if samples:
            for idx, metric in enumerate(("connect", "total")):
                data = sorted(s[idx] * 1000 for s in samples)
                quantiles = [data[math.ceil(len(data) * p) - 1] for p in (.50, .95, .99)]
                print(f"  {metric} ms: p50={quantiles[0]:.3f} p95={quantiles[1]:.3f} p99={quantiles[2]:.3f}")
            rate = sum(s[2] for s in samples) / sum(s[1] for s in samples)
            print(f"  HTTP payload rate: {rate:.1f} bytes/s (sequential requests; not link capacity)")
    return int(failures > 0)


def cluster_command(args):
    cluster = Cluster(args)
    cluster.preflight()
    if args.command == "deploy-test":
        project = Path(args.project_dir).expanduser().resolve()
        def resolve(value):
            p = Path(value).expanduser()
            return p if p.is_absolute() else project / p
        manifest = cluster.prepare([resolve(args.manifest), resolve(args.peer_manifest)])
        result = cluster.k("apply", "-f", "-", input=json.dumps(manifest))
        print(result.stdout, end="")
        cluster.k("wait", "--for=condition=Ready", "pod/nat464-demo", "pod/ipv6-peer", "--timeout=120s", timeout=150)
        return validate(cluster)
    if args.command == "validate-paths":
        return validate(cluster)
    if args.command == "benchmark":
        return benchmark(cluster)
    # Delete only known resources that still carry this helper's ownership label.
    # Never remove a namespace, images, arbitrary Pods, or global VM state.
    for kind, names in RESOURCES.items():
        for name in sorted(names):
            existing = cluster.k("get", kind, name, "--ignore-not-found", "-o", "json").stdout.strip()
            if not existing:
                continue
            if json.loads(existing).get("metadata", {}).get("labels", {}).get(OWNER_KEY) != OWNER:
                print(f"SKIP: unowned {kind}/{name}")
                continue
            # Keep selector in the delete request to protect against an ownership change after get.
            print(cluster.k("delete", kind, "--field-selector", f"metadata.name={name}", "--selector", f"{OWNER_KEY}={OWNER}",
                            "--ignore-not-found", "--wait=true", "--timeout=60s", timeout=90).stdout, end="")
    return 0


def vm_setup(args):
    require("multipass")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", args.name):
        raise Failure("VM name must start with a letter and contain letters, digits, or hyphens")
    listing = json.loads(run(["multipass", "list", "--format=json"], timeout=30).stdout)
    if any(vm.get("name") == args.name for vm in listing.get("list", [])):
        raise Failure(f"VM {args.name} already exists; it was not changed")
    run(["multipass", "launch", args.release, "--name", args.name, "--cpus", str(args.cpus),
         "--memory", args.memory, "--disk", args.disk, "--timeout", "600"], timeout=630)
    run(["multipass", "exec", args.name, "--", "sudo", "-n", "env", "DEBIAN_FRONTEND=noninteractive",
         "sh", "-ec", "apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update && apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 install -y curl iproute2 python3 docker.io"], timeout=600)
    print(f"VM {args.name} ready. Transfer both the project and this installed skill directory before running VM helpers.")
    return 0


def k3s_setup(args):
    require("sudo", "curl", "ip", "systemctl")
    if Path("/etc/rancher/k3s/config.yaml").exists() or Path("/etc/rancher/k3s/k3s.yaml").exists() or shutil.which("k3s"):
        raise Failure("An existing k3s installation/configuration was found; use a fresh disposable VM")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+\+k3s[0-9]+", args.version):
        raise Failure("--version must be an explicit k3s release, e.g. vX.Y.Z+k3sN")
    ipv4, ipv6 = ipaddress.IPv4Address(args.node_ipv4), ipaddress.IPv6Address(args.node_ipv6)
    addresses = json.loads(run(["ip", "-j", "addr", "show"], timeout=30).stdout)
    assigned = {a["local"] for interface in addresses for a in interface.get("addr_info", [])}
    if str(ipv4) not in assigned or str(ipv6) not in assigned:
        raise Failure("Both --node-ipv4 and --node-ipv6 must already be assigned to this VM")
    run(["sudo", "-n", "true"], timeout=10)
    with tempfile.TemporaryDirectory(prefix="sidecar-k3s-") as folder:
        installer = Path(folder) / "install.sh"
        run(["curl", "--fail", "--location", "--connect-timeout", "10", "--max-time", "60", "https://get.k3s.io", "-o", str(installer)], timeout=70)
        env = os.environ.copy()
        env["INSTALL_K3S_VERSION"] = args.version
        # Installer accepts INSTALL_K3S_* variables; executes sudo internally when not root.
        run(["sh", str(installer), "server", f"--node-ip={ipv4},{ipv6}",
             "--cluster-cidr=10.42.0.0/16,fd00:42::/56", "--service-cidr=10.43.0.0/16,fd00:43::/112",
             "--flannel-ipv6-masq", "--write-kubeconfig-mode=600"], timeout=600, env=env)
    run(["sudo", "-n", "k3s", "kubectl", "--kubeconfig=/etc/rancher/k3s/k3s.yaml", "--context=default",
         "--request-timeout=150s", "wait", "--for=condition=Ready", "node", "--all", "--timeout=120s"], timeout=160)
    print("k3s ready: IPv4-primary dual-stack pods/services. DNS64 and EKS parity are not configured.")
    return 0


def build_image(args):
    require("sudo", "docker", "k3s")
    project = Path(args.project_dir).expanduser().resolve()
    if not (project / "Dockerfile").is_file():
        raise Failure(f"Missing Dockerfile in {project}")
    if not args.image or args.image.startswith("-") or any(c.isspace() for c in args.image):
        raise Failure("--image must be one explicit container image reference")
    run(["sudo", "-n", "docker", "build", "--tag", args.image, str(project)], timeout=1800)
    with tempfile.TemporaryDirectory(prefix="sidecar-image-") as folder:
        archive = str(Path(folder) / "image.tar")
        run(["sudo", "-n", "docker", "save", "--output", archive, args.image], timeout=180)
        run(["sudo", "-n", "k3s", "ctr", "--namespace", "k8s.io", "images", "import", archive], timeout=180)
    print(f"Imported {args.image} into this machine's k3s containerd (namespace k8s.io)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("deploy-test", "validate-paths", "benchmark", "teardown"):
        p = commands.add_parser(name)
        p.add_argument("--context", default=os.getenv("KUBE_CONTEXT"))
        p.add_argument("--namespace", default=os.getenv("KUBE_NAMESPACE"))
        p.set_defaults(handler=cluster_command)
        if name != "teardown":
            p.add_argument("--external-url", help="Optional authorized external HTTP(S) endpoint")
        if name in {"deploy-test", "validate-paths"}:
            p.add_argument("--inbound-marker", default="nginx")
            p.add_argument("--peer-marker", default="ipv6-peer-ok")
        if name == "deploy-test":
            p.add_argument("--project-dir", default=os.getcwd())
            p.add_argument("--manifest", default="deploy/example-pod.yaml")
            p.add_argument("--peer-manifest", default="deploy/ipv6-peer-nginx.yaml")
            p.add_argument("--local-image", help="Set the sidecar image and imagePullPolicy=Never")
        if name == "benchmark":
            p.add_argument("--iterations", type=integer, default=50)
    p = commands.add_parser("vm-setup")
    p.add_argument("--name", required=True)
    p.add_argument("--release", default="24.04")
    p.add_argument("--cpus", type=integer, default=2)
    p.add_argument("--memory", default="4G")
    p.add_argument("--disk", default="20G")
    p.set_defaults(handler=vm_setup)
    p = commands.add_parser("k3s-setup")
    p.add_argument("--version", required=True)
    p.add_argument("--node-ipv4", required=True)
    p.add_argument("--node-ipv6", required=True)
    p.set_defaults(handler=k3s_setup)
    p = commands.add_parser("build-image")
    p.add_argument("--project-dir", required=True)
    p.add_argument("--image", required=True)
    p.set_defaults(handler=build_image)
    args = parser.parse_args(argv)
    try:
        if getattr(args, "external_url", None) and not re.match(r"^https?://", args.external_url):
            raise Failure("--external-url must use http:// or https://")
        return args.handler(args)
    except (Failure, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
