# Kubernetes Debugging Process

Systematic diagnosis of pod failures, networking issues, and resource problems using a structured triage flow: describe, logs, events, exec.

## Triage Flow

Follow this sequence for every pod or workload issue. Do not skip steps — many failures (scheduling, image pull, volume mount) are only visible in events and describe output, not in logs, so jumping straight to logs misses them.

Always specify `-n <namespace>` explicitly in every command; never rely on the default context namespace, because the wrong namespace silently returns empty or misleading results.

```bash
# 1. Overview
kubectl get pods -n <namespace> -o wide
# 2. Describe for events/conditions
kubectl describe pod <pod-name> -n <namespace>
# 3. Current logs
kubectl logs <pod-name> -n <namespace> -c <container-name>
# 4. Previous logs (critical for CrashLoopBackOff)
# Always check --previous before current logs for crashed containers,
# because deleting or restarting the pod destroys these logs permanently.
kubectl logs <pod-name> -n <namespace> -c <container-name> --previous
# 5. Namespace events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
# 6. Live inspection
kubectl exec -it <pod-name> -n <namespace> -c <container-name> -- /bin/sh
```

Use read-only commands (describe, logs, get) to gather evidence before proposing any modifications. Never suggest changes based on assumptions — gather diagnostic output first.

## Diagnosis Routing

| Symptom | Reference |
|---------|-----------|
| CrashLoopBackOff, ImagePullBackOff, Pending | `crash-diagnosis.md` |
| Service unreachable, DNS failure | `network-debugging.md` |
| CPU throttling, OOMKill, disk pressure | `resource-debugging.md` |

## Common Error: "no endpoints available for service"
Cause: Service selector does not match any running pod labels.
Fix: Compare `kubectl get svc <name> -o yaml` selector with `kubectl get pods --show-labels`.
