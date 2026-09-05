# Quick Skill Output Templates

Banner and STATE.md templates used across phases.

---

## --trivial Summary Banner

```
===================================================================
 QUICK --trivial: <description>
===================================================================

 Files edited: <N>
 Commit: <hash> on <branch>

===================================================================
```

---

## DISCUSS Banner

```
===================================================================
 QUICK DISCUSS: <task summary>
===================================================================

 Before planning, I need to resolve:

 1. <question>
 2. <question>

===================================================================
```

---

## Inline Plan Banner

```
===================================================================
 QUICK [task-id]: <description>
===================================================================

 Plan:
   1. <what to change in file X>
   2. <what to change in file Y>
   3. <why: brief rationale>

 Files: <file1>, <file2>
 Estimated edits: <N>

===================================================================
```

Upgrade prompt when estimated edits exceed 15:
```
This task estimates more than 15 edits. Consider /do if the work
needs multiple components, architecture changes, or parallel execution.
```

---

## Commit Format

```bash
git commit -m "$(cat <<'EOF'
<type>: <description>

Quick task <task-id>
EOF
)"
```

Type is usually `fix:`, `chore:`, or `refactor:`.

---

## STATE.md Schema

Initial creation:

```markdown
# Task State

## Quick Tasks

| Date | ID | Description | Commit | Branch | Tier | Status |
|------|----|-------------|--------|--------|------|--------|
```

Row to append per task:

```markdown
| YYYY-MM-DD | <task-id> | <description> | <short-hash> | <branch> | quick | done |
```

If escalated from `--trivial`, use tier `trivial->quick`.

---

## Completion Banner

```
===================================================================
 QUICK [task-id]: COMPLETE
===================================================================

 Description: <description>
 Files edited: <N>
 Commit: <hash> on <branch>
 Flags: <--discuss, --research, --full, or "base">
 Logged: STATE.md

 Next steps:
   - Push: /pr-workflow
   - More work: /quick <next task>
   - Merge to parent: git merge quick/<task-id>-...

===================================================================
```

For `--no-commit`, replace commit hashes with `skipped (--no-commit)` in summaries and STATE.md. Continue already-authorized delivery steps instead of presenting them as new permission requests.
