---
name: dev-branch-deploy
description: Drive the Hermes/Maia Concourse dev-branch deploy workflow — test stack changes in a live lab before merging to master. Use for "dev branch", "deploy to dev", "hermes-dev-branch", "maia-dev-branch", "test in labs", "dev lane". Covers both the hermes and maia stacks.
version: 1.0.0
routing:
  triggers:
    - dev branch
    - dev-branch
    - deploy to dev
    - dev lane
    - hermes-dev-branch
    - maia-dev-branch
    - test in labs
    - sync master to dev
  pairs_with:
    - pr-workflow
  complexity: Medium
  category: infrastructure
---

# Dev-Branch Deploy — Hermes & Maia

Test a Hermes or Maia stack change in a **live lab region before merging to master**, using the
pipeline's parallel `dev` lane. One workflow, two stacks — parametrized by stack.

## The problem this solves

Concourse pins a git `branch:` per resource at pipeline-definition time; you can't override it at
trigger time. So normally you must merge to `master` to see a chart/secrets change run in a lab.
The `dev` lane adds a second set of jobs pointed at `<stack>-dev-branch`, so you deploy and validate
in a real lab region with **no risk to master or production**.

## Stack parameters

Everything below is identical between stacks except these values.

| Param | hermes | maia |
|-------|--------|------|
| Dev branch | `hermes-dev-branch` | `maia-dev-branch` |
| fly target | `ci-monitoring` | `monitoring` |
| Concourse | `https://ci1.eu-de-2.cloud.sap` | `https://ci.eu-de-2.cloud.sap` |
| Pipeline dir | `ci/hermes/` in `cc/secrets` | `ci/maia/` in `cc/secrets` |
| `set-pipeline` vars | — | `--load-vars-from vars.yaml` |
| Chart | `openstack/hermes` | `openstack/maia` |

**Constants (both stacks):**
- Team: `monitoring`
- Lab regions the dev lane deploys to: `qa-de-1`, `qa-de-2`, `qa-de-3`, `eu-de-3`
- Repos the dev branch must exist on: `cc/secrets` (GHE `github.wdf.sap.corp`) **and** `sapcc/helm-charts` (github.com)
- Local `cc/secrets` clone: `~/gh/secrets`

## The two lanes

| Lane | Branch | Role |
|------|--------|------|
| `labs` | `master` | Guards production-branch health. **Never break it.** |
| `dev` | `<stack>-dev-branch` | Sandbox: validate a feature in a real lab before master. |

Both deploy to the same lab regions, independently. Production lanes (`bronze`/`silver`/`gold`/`global`)
are untouched by this workflow.

## Pipeline wiring (reference)

Dev lane = paired git resources + a `dev` job group.

- `secrets-dev.git` → `<stack>-dev-branch` (twin of `secrets.git` on master)
- `helm-charts-dev.git` → `<stack>-dev-branch` (twin of `helm-charts.git` on master)
- Shared by both lanes: built image, `kube-secrets`, credentials.

Dev jobs run the same helm upgrade as prod but input-map the dev resources over prod:
```yaml
input_mapping:
  helm-charts.git:  helm-charts-dev.git
  secrets.git:      secrets-dev.git
```

Dev group jobs:
| Job | Purpose |
|-----|---------|
| `deploy-all-dev` | Manual fan-out trigger for the whole dev lane |
| `deploy-to-dev-<region>` | `helm upgrade` per lab region, from the dev branch |
| `sync-master-to-dev` | Keep the dev branch caught up with master |

## Preflight — ALWAYS run before using a stack's dev lane

Confirm the dev branch exists on **both** repos and the pipeline is actually wired. Substitute
`<stack>` = `hermes` or `maia`.

```bash
STACK=hermes            # or: maia
DEVBRANCH=${STACK}-dev-branch

# 1. Dev branch on internal secrets repo
git -C ~/gh/secrets ls-remote --heads origin "$DEVBRANCH"

# 2. Dev branch on public helm-charts repo
git ls-remote --heads https://github.com/sapcc/helm-charts.git "$DEVBRANCH"

# 3. Is the dev lane present in the generated pipeline? (erb must define the dev group)
grep -n "helm-charts-dev.git\|deploy-all-dev\|${DEVBRANCH}" ~/gh/secrets/ci/${STACK}/pipeline.yaml.erb
```

**Decision logic:**
1. Both `ls-remote` return a SHA **and** grep shows the dev group → dev lane is ready, proceed.
2. Branch missing on one/both repos → **stop**. It must be created on both before the lane works.
   Report exactly which repo is missing it.
3. erb has no dev group → the pipeline change isn't merged/generated yet. Report that; do not proceed.

> Hermes is fully wired (branch on both repos, dev group live on master).
> Maia's dev lane may still be on the unmerged branch `add-maia-dev-group`, and `maia-dev-branch`
> may not exist yet — the preflight catches this.

## Developer workflow

1. **Cut a feature branch from `master`** in `helm-charts` and/or `secrets` as needed.
2. **Merge the feature branch into `<stack>-dev-branch`** (merge, never force-push).
   ```bash
   git -C ~/gh/secrets fetch origin
   git -C ~/gh/secrets checkout "$DEVBRANCH"
   git -C ~/gh/secrets merge --no-ff origin/<feature-branch>
   git -C ~/gh/secrets push origin "$DEVBRANCH"
   ```
3. **Concourse auto-picks-up** the change on the dev branch and triggers the dev lane.
4. **Validate** `deploy-to-dev-<region>` goes green across all lab regions — this is the proof.
   ```bash
   fly -t <target> watch -j ${STACK}/deploy-to-dev-qa-de-1
   ```
   Or trigger the whole lane manually:
   ```bash
   fly -t <target> trigger-job -j ${STACK}/deploy-all-dev -w
   ```
5. **Merge the feature branch to `master`** as normal (via PR).
6. **Confirm the `labs` lane stays healthy** on master.

## Keeping the dev branch fresh

Before starting new dev work, sync the dev branch to master so you're testing against current state:
```bash
fly -t <target> trigger-job -j ${STACK}/sync-master-to-dev -w
```
(Or merge `origin/master` into the dev branch locally and push — never force-push.)

## Regenerate & ship the pipeline

The pipeline is ERB-generated, then pushed with `fly`. Log in first: `fly -t <target> login`.

**Hermes:**
```bash
cd ~/gh/secrets/ci/hermes
erb pipeline.yaml.erb > pipeline.yaml
fly -t ci-monitoring set-pipeline -p hermes -c pipeline.yaml
```

**Maia:**
```bash
cd ~/gh/secrets/ci/maia
erb pipeline.yaml.erb > pipeline.yaml
fly -t monitoring set-pipeline -p maia -c pipeline.yaml --load-vars-from vars.yaml
```

## Rules (hard constraints)

- **Never break `labs`** — it tracks `master` only and gates production.
- **No force-pushes** to any `<stack>-dev-branch`. It's a shared integration branch.
- Merge features **into** the dev branch; don't rewrite its history.
- This workflow touches **lab regions only**. Production lanes are out of scope.

## Error handling

| Symptom | Cause / fix |
|---------|-------------|
| `ls-remote` returns nothing for the dev branch | Branch not created on that repo. Create `<stack>-dev-branch` on both `cc/secrets` and `sapcc/helm-charts` before deploying. |
| grep finds no `deploy-all-dev` in erb | Dev-lane pipeline change not merged/generated. Merge it, `erb > pipeline.yaml`, `fly set-pipeline`. |
| `deploy-to-dev-*` never triggers | Confirm the change landed on `<stack>-dev-branch` (not just a feature branch); check the `*-dev.git` resource in Concourse is finding the commit. |
| `fly: unknown target` | `fly -t <target> login` first. Hermes=`ci-monitoring`, Maia=`monitoring`. |
| Dev deploy passes but master breaks after merge | The feature diverged from what was tested on dev — re-sync dev to master and re-validate before re-merging. |
