# Agent Capability Map Reference

> **Scope**: Task-to-agent routing table; capabilities and boundaries per agent.

---

## Primary Routing Table

| Task Type | Primary Agent | Fallback | Avoid |
|-----------|--------------|----------|-------|
| Go source code | `golang-general-engineer` | — | general-purpose |
| TypeScript backend API | `nodejs-api-engineer` | `typescript-frontend-engineer` | general-purpose |
| TypeScript frontend/React | `typescript-frontend-engineer` | — | nodejs-api-engineer |
| Python scripts/data | `python-general-engineer` | `python-openstack-engineer` | general-purpose |
| Database schema/migrations | `database-engineer` | — | application agents |
| Kubernetes/Helm | `kubernetes-helm-engineer` | — | ansible-automation-engineer |
| Ansible playbooks | `ansible-automation-engineer` | — | kubernetes-helm-engineer |
| OpenSearch/Elasticsearch | `opensearch-elasticsearch-engineer` | — | database-engineer |
| Prometheus/Grafana | `prometheus-grafana-engineer` | — | — |
| Swift iOS/macOS | `swift-general-engineer` | — | — |
| Kotlin Android/JVM | `kotlin-general-engineer` | — | — |
| PHP backend | `php-general-engineer` | — | — |
| React Native / Expo | `react-native-engineer` | — | typescript-frontend-engineer |
| Code review | `reviewer-code-playbook` | `reviewer-system-playbook` | — |
| Security audit | `security-threat-model` | — | — |
| Performance | `performance-optimization-engineer` | — | — |
| Documentation | `technical-documentation-engineer-playbook` | — | — |

Verify agent exists: `ls ~/.claude/agents/ | grep {agent-name}`

---

## Agent Scope Boundaries

**golang-general-engineer**: CAN modify `.go` files, run `go build/test/vet`, add packages, fix linting. CANNOT modify non-Go files, make architectural decisions, run migrations.

**nodejs-api-engineer**: CAN do REST endpoints, middleware, auth, webhooks, DB integration. CANNOT do frontend components, native code, infrastructure.

**database-engineer**: CAN do schema design, migrations, indexes, query optimization. CANNOT do application code. **Mandatory sequencing**: database agent ALWAYS before application agents on schema changes.

**performance-optimization-engineer**: CAN do Core Web Vitals, bundle analysis, rendering optimization, profiling. CANNOT fix unrelated logic bugs.

---

## Compound Task Routing

### API + Frontend Feature
```
1. database-engineer → schema migration
2. nodejs-api-engineer → endpoint (parallel with 3 if no shared types)
3. typescript-frontend-engineer → UI
4. reviewer-code-playbook → full-stack review
```

### Go Service Performance
```
1. performance-optimization-engineer → profile, identify hotspot (read-only)
2. golang-general-engineer → fix
3. golang-general-engineer → benchmark validation
```

### Infrastructure + Application
```
1. kubernetes-helm-engineer → Helm chart (parallel with 2 if isolated)
2. ansible-automation-engineer → provisioning
3. Application agent → smoke test
```

---

## Preferred Patterns

### Route to Specialist Agent
**Signal**: Dispatching undefined subagent_type for Go errors.
**Fix**: Look up task type in routing table, specify exact `subagent_type`.

### Match Agent to Language Domain
**Signal**: TypeScript backend work sent to frontend engineer.
**Fix**: Check imports — `express`/`@nestjs`/`fastify` → nodejs-api-engineer. `react`/`next` → typescript-frontend-engineer.

```bash
rg "import.*express|import.*@nestjs" --files-with-matches src/  # → backend
rg "import.*react|import.*next" --files-with-matches src/       # → frontend
```

### Route Schema Changes to Database Agent
**Signal**: Asking nodejs-api-engineer to add a column.
**Fix**: database-engineer first for migration, then application agent for ORM models.

---

## Agent Selection Decision Tree

```
.go files? → golang-general-engineer
TypeScript backend/API? → nodejs-api-engineer
TypeScript frontend/React? → typescript-frontend-engineer
Database schema? → database-engineer (first, before app agents)
K8s/containers? → kubernetes-helm-engineer
VM provisioning? → ansible-automation-engineer
Performance? → performance-optimization-engineer
Code review? → reviewer-code-playbook
Otherwise? → Check agents/ for domain match → general-purpose as last resort
```
