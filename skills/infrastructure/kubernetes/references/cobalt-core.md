# Cobalt Core

Domain knowledge for the cobaltcore-dev project family — SAP Converged Cloud infrastructure components for KVM hypervisor management, metrics collection, and compute-node tooling.

## Component Table

| Component | Repository | Reference |
|-----------|-----------|-----------|
| KVM Exporter | `cobaltcore-dev/kvm-exporter` | `cobalt-kvm-exporter.md` |

If the component is not listed, tell the user no reference exists yet and offer to analyze the repo (see Extension Process).

The references contain: architecture and data flow diagrams; complete metric catalogs with types, labels, and descriptions; configuration options and environment variables; deployment models (Helm, DaemonSet, container specs); code patterns (concurrency, caching, error handling); testing strategies (unit mocks, E2E with Kind clusters); alerting rules and operational concerns.

## Implementation Pairing

- Go code patterns: pair with `go-patterns` skill
- Prometheus/Grafana: pair with `prometheus-grafana-engineer`
- Kubernetes deployment: this skill covers it

## Extension Process

To add a new cobaltcore repo:
1. Analyze repo systematically (README, go.mod, source, Dockerfile, Helm)
2. Create reference file at `references/cobalt-{repo-name}.md`
3. Update the Reference Loading Table in SKILL.md
4. Update the Component Table above

Follow the structure established in `cobalt-kvm-exporter.md` for consistency.
