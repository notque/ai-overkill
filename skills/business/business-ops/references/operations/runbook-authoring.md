---
title: Runbook Authoring — Step Structure, Verification, Rollback, Escalation
domain: operations
level: 3
skill: operations
---

# Runbook Authoring Reference

> **Scope**: Step-by-step runbook construction for operational procedures. Covers step structure with mandatory components, verification checklists, rollback procedures (whole-runbook and per-step), escalation paths, and troubleshooting tables. Use when authoring new runbooks or reviewing existing ones for completeness.
> **Generated**: 2026-05-05 — Validate commands and paths against your actual infrastructure.

---

## Overview

Runbooks fail for one reason: the author knew things the reader does not. The author writes "run the script" because they know which script, where it lives, what user runs it, and what the output looks like. The reader — a new hire at 3am during an incident — knows none of that.

Every runbook authoring decision should pass one test: **Could someone who has never touched this system follow this step right now, with no Slack messages and no phone calls?**

---

## Step Structure — The Five Required Components

Every step in a runbook MUST have all five components. A step missing any component is incomplete.

### 1. Action (What To Do)

The exact command, UI action, or manual procedure. No ambiguity.

| Bad | Good | Why |
|-----|------|-----|
| "Run the migration script" | `cd /opt/deploy && ./migrate.sh --env=prod --dry-run` as user `deploy` | Specifies path, script, flags, and user |
| "Check the logs" | `journalctl -u api-server --since "5 minutes ago" \| grep ERROR` | Specifies which logs, time window, filter |
| "Restart the service" | `sudo systemctl restart api-server.service` then wait 30s | Specifies exact command and timing |
| "Update the config" | Edit `/etc/app/config.yaml`: set `max_connections: 500` (was 200) | Specifies file, key, new value, old value |
| "Notify the team" | Post to #ops-incidents: "DB failover in progress. ETA 15min." | Specifies channel and message content |

Rules:
- Include the full path. `./script.sh` means nothing without the directory.
- Include the user context. `sudo`, `su - deploy`, or "as your own user" — state it.
- Include flags. `--dry-run` vs `--execute` is the difference between a test and production data loss.
- Include wait times. "Wait 30 seconds" is a step component, not implied.

### 2. Expected Result (What Should Happen)

What the operator should see if the step succeeded. Concrete, observable output.

| Bad | Good |
|-----|------|
| "It should work" | Output: `Migration complete. 47 rows updated. 0 errors.` |
| "Service is healthy" | `curl -s localhost:8080/health` returns `{"status":"ok","uptime":">0"}` within 5s |
| "Logs look normal" | `journalctl -u api-server -n 5` shows `INFO` lines, no `ERROR` or `WARN` |
| "Database is accessible" | `psql -h db-primary -U app -c 'SELECT 1'` returns `1` within 2s |

Rules:
- Show exact output when possible. Operators compare what they see against what the runbook says.
- Include timing. "Returns within 5s" catches hangs that "returns ok" misses.
- Include negative checks. "No ERROR lines in the last 60 seconds" catches delayed failures.

### 3. Failure Handling (What To Do When It Goes Wrong)

What the operator does if the expected result does not appear. This is NOT optional.

| Failure | Action |
|---------|--------|
| Command returns non-zero exit code | Check stderr. If "connection refused," verify the service is running: `systemctl status api-server` |
| Output shows unexpected row count | STOP. Do not proceed. This indicates data inconsistency. Jump to Escalation. |
| Timeout (no response in 30s) | Retry once. If second attempt also times out, check network: `ping db-primary` and `telnet db-primary 5432` |
| Permission denied | Verify you are running as the correct user. Check: `whoami` should return `deploy` |
| Partial success | Note which items succeeded in the runbook history. Proceed to the next step only if documented as safe to continue with partial results. |

Rules:
- Differentiate between retryable and non-retryable failures.
- State when to STOP. Not every failure should be worked around.
- State when to escalate. "If you've spent more than 10 minutes on this step, escalate."

### 4. Verification (How To Confirm Success)

A separate check — distinct from the expected result — that confirms the step achieved its purpose.

| Step Purpose | Verification |
|-------------|-------------|
| Deploy new version | `curl -s /version` returns the new build hash |
| Database migration | `psql -c "SELECT COUNT(*) FROM schema_migrations WHERE version='20240515'"` returns 1 |
| Config change | `grep max_connections /etc/app/config.yaml` shows `500` AND `systemctl show api-server --property=ActiveState` shows `active` |
| Cache flush | Request a known cached resource; response header `X-Cache: MISS` confirms fresh fetch |

Rules:
- Verification checks the outcome, not just the action. "The command ran" is not verification. "The system now behaves correctly" is.
- Include both positive and negative verification where applicable. Service is up AND old version is not running.

### 5. Per-Step Rollback (How To Undo This Step)

How to reverse this specific step if later steps fail and the whole runbook needs to be unwound.

| Step | Rollback |
|------|----------|
| Deploy new version | `kubectl rollout undo deployment/api -n production` |
| Database migration | `cd /opt/deploy && ./migrate.sh --env=prod --direction=down --version=20240515` |
| Config change | Restore from backup: `cp /etc/app/config.yaml.bak /etc/app/config.yaml && systemctl restart api-server` |
| DNS change | Revert CNAME in Route 53 to previous value. TTL is 300s; allow 5min for propagation. |

Rules:
- Not all steps are reversible. State "NOT REVERSIBLE — see Rollback section for compensating action" when applicable.
- Include timing. How long does the rollback take to propagate?
- Rollback should be tested. An untested rollback is a hope, not a plan.

---

## Verification Checklists

### Pre-Execution Checklist

Run before starting any runbook. If any item fails, STOP.

```
## Pre-Execution Checklist
- [ ] Correct environment confirmed (production/staging/dev)
- [ ] Required access verified (SSH, console, database, admin panels)
- [ ] Required tools available (kubectl, psql, aws, etc.)
- [ ] Maintenance window active (if required)
- [ ] Stakeholders notified of upcoming work
- [ ] Rollback procedure reviewed and understood
- [ ] Monitoring dashboards open (list specific URLs)
- [ ] Communication channel open (#ops-incidents or equivalent)
- [ ] Previous run's history reviewed for known issues
- [ ] Backup/snapshot taken if applicable
```

### Post-Execution Checklist

Run after completing all steps. Confirms the runbook achieved its purpose.

```
## Post-Execution Checklist
- [ ] All verification steps passed
- [ ] Monitoring shows normal behavior for 15+ minutes post-change
- [ ] No new alerts triggered
- [ ] Stakeholders notified of completion
- [ ] Runbook history updated with date, operator, and observations
- [ ] Any deviations from the runbook documented
- [ ] Maintenance window closed (if applicable)
- [ ] Temporary access/permissions revoked
```

### Review Checklist (For Runbook Authors)

Use when writing or reviewing a runbook for completeness.

```
## Runbook Review Checklist
- [ ] Every step has all 5 components (action, expected, failure, verify, rollback)
- [ ] No step requires knowledge not present in the document
- [ ] Prerequisites list all required access, tools, and prior state
- [ ] Rollback section covers full unwinding, not just last step
- [ ] Escalation paths have names, contact methods, and trigger criteria
- [ ] Troubleshooting table covers failure modes from each step
- [ ] Someone unfamiliar with the system could follow this at 3am
- [ ] Commands use absolute paths, explicit users, and complete flags
- [ ] Expected results include concrete output, not "it should work"
- [ ] Timing constraints stated (wait times, propagation delays, TTLs)
```

---

## Rollback Procedures

### Per-Step vs. Whole-Runbook Rollback

Two levels of rollback. Both are required.

| Level | When Used | Structure |
|-------|-----------|-----------|
| Per-step | Later step fails; need to undo this step as part of unwinding | Component 5 of each step |
| Whole-runbook | Catastrophic failure or post-completion problems; need to return to pre-runbook state | Dedicated section at end of runbook |

### Whole-Runbook Rollback Template

```
## Rollback Procedure

### When to Roll Back
- [Specific trigger: metric exceeds threshold, error rate above X%, user reports Y]
- [Time limit: "If not resolved within 30 minutes of completion, roll back"]

### Pre-Rollback
- [ ] Confirm rollback is the right action (not just a transient issue)
- [ ] Notify stakeholders: "Rolling back [change]. Estimated time: [X minutes]"
- [ ] Open monitoring dashboards

### Rollback Steps (in reverse order)
1. [Undo Step N]: [exact command]
   - Verify: [check]
2. [Undo Step N-1]: [exact command]
   - Verify: [check]
3. [Continue in reverse...]

### Post-Rollback Verification
- [ ] System returned to pre-change state
- [ ] All services healthy
- [ ] No data loss or corruption
- [ ] Monitoring confirms normal behavior for 15+ minutes

### Post-Rollback Actions
- [ ] Notify stakeholders of completed rollback
- [ ] Document what went wrong in the runbook history
- [ ] Create incident ticket if applicable
- [ ] Schedule post-mortem for the failed change
```

### Non-Reversible Steps

Some steps cannot be undone. Identify these before execution.

| Non-Reversible Action | Compensating Action |
|----------------------|---------------------|
| Email sent to customers | Send correction/update email |
| Data deleted from production | Restore from backup (document backup location and restore procedure) |
| Third-party API call (payment, notification) | Manual reversal through vendor portal or support ticket |
| Published DNS change (cached globally) | Revert record; wait for TTL expiry. Document TTL value. |
| Schema migration that drops columns | Restore from pre-migration backup. Document backup timing. |

Rules:
- Non-reversible steps must be called out prominently in the runbook
- Require explicit confirmation before executing non-reversible steps
- Compensating actions must be documented even if they are manual

---

## Escalation Paths

### Escalation Trigger Criteria

Define when to stop working independently and escalate. Time-box troubleshooting.

| Trigger | Action |
|---------|--------|
| Step fails after 2 retry attempts | Escalate to on-call engineer |
| Troubleshooting exceeds 10 minutes with no progress | Escalate to on-call engineer |
| Data inconsistency detected | STOP immediately. Escalate to data owner + on-call |
| Customer-facing impact confirmed | Escalate to incident commander + comms |
| Uncertainty about whether to proceed | Escalate. Asking is always better than guessing. |

### Escalation Contact Template

```
## Escalation Contacts

| Situation | Primary Contact | Method | Backup Contact | Method |
|-----------|----------------|--------|----------------|--------|
| System outage | [Name] | PagerDuty / [phone] | [Name] | Slack DM / [phone] |
| Data issue | [Name] | Slack #data-oncall | [Name] | [phone] |
| Security incident | [Name] | PagerDuty (P1) | Security team | security@company.com |
| Customer impact | [Name] | Slack #incidents | [Name] | [phone] |
| Unknown/general | On-call engineer | PagerDuty | Engineering manager | [phone] |
```

### Escalation Message Template

When escalating, include all of these. Missing context wastes responder time.

```
**What**: [Runbook name] failed at Step [N]
**When**: [Timestamp] [Timezone]
**Where**: [Environment: prod/staging] [Region/cluster]
**Symptom**: [What you observed]
**Expected**: [What should have happened]
**Actions taken**: [What you tried, including retry attempts]
**Current state**: [Is the system degraded? Is the change partially applied?]
**Urgency**: [Customer impact? Data at risk? Time-sensitive?]
```

---

## Troubleshooting Tables

### Structure

Every runbook should include a troubleshooting table mapping symptoms to causes and fixes.

```
## Troubleshooting

| Symptom | Likely Cause | Diagnostic Command | Fix |
|---------|-------------|-------------------|-----|
| Connection refused | Service not running | `systemctl status api-server` | `systemctl start api-server` |
| Permission denied | Wrong user context | `whoami` | `su - deploy` or `sudo -u deploy` |
| Timeout after 30s | Network/firewall issue | `telnet db-primary 5432` | Check security groups / iptables |
| Unexpected row count | Prior failed migration | `SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 5` | Run missing migration or restore from backup |
| Pods in CrashLoopBackOff | Config error or resource limits | `kubectl logs pod/api-xxx -n production --tail=50` | Fix config, then `kubectl rollout restart` |
```

### Common Cross-Runbook Issues

These appear in many runbooks. Include the relevant ones.

| Issue | Diagnostic | Resolution |
|-------|-----------|------------|
| DNS not resolving | `dig +short hostname` | Check DNS records. Allow for TTL propagation. |
| SSL certificate expired | `openssl s_client -connect host:443 2>/dev/null \| openssl x509 -noout -dates` | Renew certificate. Check auto-renewal config. |
| Disk full | `df -h /path` | Identify and remove old logs/artifacts. Expand volume if recurring. |
| OOM killed | `dmesg \| grep -i oom` | Increase memory limits or fix memory leak. |
| Clock skew | `date` vs NTP source | `sudo systemctl restart ntp` or `chronyc makestep` |

---

## Runbook Metadata and Lifecycle

### Required Metadata

Every runbook header must include:

```
## Runbook: [Task Name]
**Owner:** [Team/Person]
**Frequency:** [Daily/Weekly/Monthly/As Needed/Event-Driven]
**Last Updated:** [YYYY-MM-DD]
**Last Run:** [YYYY-MM-DD]
**Last Reviewed:** [YYYY-MM-DD]
**Review Cadence:** [Quarterly]
**Environment:** [Production/Staging/Both]
```

### Run History

Append to the history table after every execution.

```
## Run History
| Date | Operator | Duration | Outcome | Notes |
|------|----------|----------|---------|-------|
| 2026-05-01 | jsmith | 25min | Success | No issues |
| 2026-04-15 | mdoe | 40min | Success | Step 3 slow; network latency |
| 2026-04-01 | jsmith | 55min | Rolled back | Step 5 failed. See INC-1234. |
```

### Review Triggers

Review the runbook when any of these occur:

| Trigger | Action |
|---------|--------|
| Infrastructure change (new cluster, DB migration, cloud region) | Validate all commands and paths |
| Incident involving this procedure | Update with lessons learned |
| 90 days since last review | Full review per the Review Checklist |
| New team member runs it for the first time | Shadow run with review |
| Dependency change (upgraded tool, API version, OS) | Validate commands and expected output |

---

## Runbook Authoring Failure Modes

| Failure Mode | Example | Fix |
|-------------|---------|-----|
| The "just" step | "Just restart the service" | Specify exactly which service, how, and verify it came back. |
| Assumed knowledge | "SSH to the usual box" | Name the host, document the SSH command, specify which key. |
| Missing failure paths | Steps only describe success | Add failure handling and when-to-escalate for every step. |
| Stale commands | Scripts that moved or flags that changed | Date-stamp the runbook. Review quarterly. Run in staging first. |
| Copy-paste from chat | Slack thread pasted as-is | Restructure into the 5-component format. Validate every command. |
| Rollback as afterthought | "If something goes wrong, undo the changes" | Specify exact undo commands in reverse order with verification. |
| Single-author syndrome | Only the author can follow it | Have someone else run it. Fix where they get stuck. |
| No timing information | "Wait for it to finish" | "Wait approximately 60-90 seconds. Timeout after 3 minutes." |
