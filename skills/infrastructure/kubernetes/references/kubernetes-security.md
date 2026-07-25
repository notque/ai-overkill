# Kubernetes Security Process

Harden Kubernetes clusters and workloads through RBAC, pod security, network isolation, secret management, and supply chain controls.

## Domain Routing

| Domain | Reference |
|--------|-----------|
| Access control, permissions, roles | `rbac-patterns.md` |
| Pod hardening, container security | `pod-security.md` |
| Network isolation, traffic rules | `network-policies.md` |
| Image signing, secrets, admission control | `supply-chain.md` |

If the question spans multiple domains, load all relevant references. Most production hardening touches at least RBAC + pod security.

## Process

1. **RESPOND** — answer with concrete YAML manifests and specific configurations from the loaded references; they contain complete, copy-paste-ready examples for each security domain. Reference-backed manifests, not generic advice.
2. **VERIFY** — validate the security posture against the misconfiguration table in `supply-chain.md`. Flag any of the 8 common misconfigurations present in the user's manifests.

For general Kubernetes debugging, see `kubernetes-debugging.md`.

## External References

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [External Secrets Operator](https://external-secrets.io/)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [Cosign](https://docs.sigstore.dev/cosign/overview/)
- [Kyverno](https://kyverno.io/)
