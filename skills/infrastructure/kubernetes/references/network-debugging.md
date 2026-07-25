# Network Debugging Reference

> **Scope**: Service resolution, DNS debugging, port-forwarding for local testing, and NetworkPolicy verification. Does NOT cover pod crash diagnosis or resource limits.
> **Version range**: Kubernetes 1.25+ (ephemeral containers assumed available)
> **Generated**: 2026-04-16

---

## Service Resolution -- pod cannot reach another service

```bash
# Verify the service exists and has endpoints
kubectl get svc <service-name> -n <namespace>
kubectl get endpoints <service-name> -n <namespace>

# Check if endpoints are populated (empty = no matching pods)
kubectl describe endpoints <service-name> -n <namespace>
```

---

## DNS Debugging

```bash
# Run a DNS lookup from inside the cluster
kubectl run dns-debug --rm -it --restart=Never --image=busybox:1.36 -n <namespace> -- \
  nslookup <service-name>.<namespace>.svc.cluster.local

# Check CoreDNS pods are running
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check CoreDNS logs for errors
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50
```

---

## Port-Forward for Local Testing

```bash
# Forward a pod port to localhost
kubectl port-forward pod/<pod-name> -n <namespace> 8080:8080

# Forward a service port to localhost
kubectl port-forward svc/<service-name> -n <namespace> 8080:80

# Test the endpoint locally
curl -v http://localhost:8080/healthz
```

---

## NetworkPolicy Blocking Traffic

See kubernetes-security.md for full policy patterns.

```bash
# List network policies in the namespace
kubectl get networkpolicy -n <namespace>

# Describe a specific policy to see ingress/egress rules
kubectl describe networkpolicy <policy-name> -n <namespace>
```
