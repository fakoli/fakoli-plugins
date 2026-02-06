# Troubleshooting

## Table of Contents
- VM Issues
- k3s / Cluster Issues
- Pod / Sidecar Issues
- Network / IPv6 Issues

## VM Issues

**Multipass launch fails on Apple Silicon**
```bash
# Ensure virtualization framework is selected
multipass set local.driver=qemu  # or virtualbox
```

**Cannot SSH into VM**
```bash
multipass shell nat464-dev  # preferred over SSH
```

**Transfer files to VM**
```bash
multipass transfer ./file.txt nat464-dev:/home/ubuntu/
# For directories, tar first:
tar czf project.tar.gz -C /path/to nat464-sidecar && multipass transfer project.tar.gz nat464-dev:/home/ubuntu/
```

## k3s / Cluster Issues

**k3s fails to start with IPv6 CIDRs**
Ensure the node has a real IPv6 address. Check with:
```bash
ip -6 addr show scope global
# If empty, add a ULA:
sudo ip -6 addr add fd00:node::1/64 dev enp0s1
```

**CoreDNS not resolving DNS64**
```bash
# Check CoreDNS logs
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=50
# Verify custom config was loaded
kubectl -n kube-system get cm coredns-custom -o yaml
# Force restart
kubectl -n kube-system rollout restart deployment coredns
```

**kubectl not working**
```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
# Or for non-root:
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
```

## Pod / Sidecar Issues

**Pod stuck in ImagePullBackOff**
The image must be imported into k3s containerd, not just in Docker:
```bash
sudo docker save nat464-sidecar:latest | sudo k3s ctr images import -
# Verify
sudo k3s ctr images ls | grep nat464
```
Ensure the pod spec has `imagePullPolicy: Never`.

**Sidecar CrashLoopBackOff**
```bash
kubectl logs nat464-demo -c nat464-sidecar
# Common causes:
# - Port conflict (another process on 8080/1080/9464)
# - App container not ready on forward port (race condition at startup)
```

**Health check failing**
```bash
kubectl exec nat464-demo -c nat464-sidecar -- wget -qO- http://localhost:9464/healthz
# If wget not available (distroless):
kubectl exec nat464-demo -c app -- wget -qO- http://localhost:9464/healthz
```

## Network / IPv6 Issues

**Inbound test fails (curl -6 to pod IPv6)**
```bash
# Check pod has IPv6 address
kubectl get pod nat464-demo -o jsonpath='{.status.podIPs}'
# Should show fd00:42::... address

# Check sidecar is listening
kubectl exec nat464-demo -c app -- ss -tlnp | grep 8080

# Check app is listening on IPv4 localhost
kubectl exec nat464-demo -c app -- ss -tlnp | grep 80
```

**Outbound SOCKS5 test fails**
```bash
# Verify socks5 proxy is listening
kubectl exec nat464-demo -c app -- ss -tlnp | grep 1080

# Test with curl through SOCKS5
kubectl exec nat464-demo -c app -- curl -v -x socks5h://127.0.0.1:1080 http://example.com

# Check DNS resolution inside pod
kubectl exec nat464-demo -c app -- nslookup example.com
```

**No IPv6 connectivity between pods**
```bash
# Verify flannel is running
kubectl -n kube-system get pods -l app=flannel
# Check node IPv6 routes
ip -6 route show | grep fd00:42
```
