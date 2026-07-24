# Kubernetes & Helm Quick Reference

> **Scope**: The diagnosis table and deploy-safety pipeline worth having verbatim at the keyboard. General Kubernetes/Helm knowledge is assumed; judgment lives in the agent body.

## Pod State Diagnosis Table

| Pod State | Common Cause | First Command |
|-----------|-------------|---------------|
| `ImagePullBackOff` | Wrong image name, missing pull secret | `kubectl describe pod <pod> \| grep -A5 Events` |
| `CrashLoopBackOff` | App crash, missing env var, OOM, bad probe | `kubectl logs <pod> --previous` |
| `OOMKilled` | Memory limit too low or leak | `kubectl describe pod <pod> \| grep -A2 'OOM\|Limits'` |
| `Pending` | No schedulable node, PVC unbound, quota exceeded | `kubectl describe pod <pod> \| grep -A10 Events` |
| `Terminating` (stuck) | Finalizer not cleared, PVC in use | `kubectl describe pod <pod> \| grep Finalizers` |
| `CreateContainerConfigError` | Missing ConfigMap/Secret in pod spec | `kubectl get events --sort-by='.lastTimestamp' -n <ns>` |
| `ErrImageNeverPull` | `imagePullPolicy: Never`, image not on node | `crictl images \| grep <name>` |

## Helm Chart Validation Pipeline

Run in this order before every deploy:

```bash
helm lint ./charts/myapp --values values-prod.yaml
helm template myapp ./charts/myapp --values values-prod.yaml | less
helm upgrade --install myapp ./charts/myapp \
  --values values-prod.yaml --dry-run=server --namespace production
helm diff upgrade myapp ./charts/myapp \
  --values values-prod.yaml --namespace production
```

`--dry-run=server` validates against the live API server — it catches `apiVersion` deprecations that `--dry-run=client` misses.
