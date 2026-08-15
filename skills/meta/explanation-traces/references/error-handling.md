# Explanation Traces — Error Handling

Error-fix mappings for every error state the skill encounters when reading
`route-events.jsonl`. Each entry includes: what the error looks like, root cause, and
the exact response to give the user. All commands are read-only.

Path used throughout:

```bash
LOG="${CLAUDE_LEARNING_DIR:-$HOME/.claude/learning}/route-events.jsonl"
```

---

## Error: No Log File Found

**Trigger**: `$LOG` is absent or zero lines.

**Root causes**:
| Cause | How to identify |
|---|---|
| No /do-routed dispatch recorded yet | `~/.claude/learning/` exists but has no `route-events.jsonl` |
| Hooks merged but never synced to `~/.claude` | `ls ~/.claude/hooks/ \| grep routing-decision-recorder` returns nothing |
| `CLAUDE_LEARNING_DIR` points elsewhere | `echo "$CLAUDE_LEARNING_DIR"` is set; check that directory instead |

**Detection** (run to diagnose which cause applies):
```bash
echo "resolved: $LOG"; ls -la "$LOG" 2>/dev/null
echo "env: CLAUDE_LEARNING_DIR=${CLAUDE_LEARNING_DIR:-<unset>}"
ls ~/.claude/hooks/ 2>/dev/null | grep -E "routing-(decision-recorder|outcome-finalizer)"
```

**Response to user**:
```
No route event log found at ~/.claude/learning/route-events.jsonl
(or $CLAUDE_LEARNING_DIR/route-events.jsonl when that variable is set).

The log is created on the first /do-routed dispatch by the
routing-decision-recorder hook (hooks/routing-decision-recorder.py).
An empty or missing log means no /do-routed dispatch has been recorded
yet — or merged hook changes were never synced to ~/.claude; run
hooks/sync-to-user-claude.py or restart the session.
```

Read decisions from the log only. If no file exists, report that there is nothing
to read.

---

## Error: Malformed JSONL Line

**Trigger**: `json.JSONDecodeError` on an individual line.

**Root causes**:
| Cause | Symptom |
|---|---|
| Truncated append (process killed mid-write; rare — per-line appends are atomic) | Last line of the file is a JSON prefix |
| Manual edit | Bad line anywhere in the file |

**Detection**:
```bash
python3 - "$LOG" <<'EOF'
import json, sys
bad = []
for i, line in enumerate(open(sys.argv[1]), 1):
    line = line.strip()
    if not line:
        continue
    try:
        json.loads(line)
    except json.JSONDecodeError as e:
        bad.append((i, e.msg))
print("malformed lines:", bad or "none")
EOF
```

**Response to user**:
```
route-events.jsonl has [N] unparseable line(s): [line numbers].
Skipping them; [M] valid events remain and are shown below.
```

JSONL fails per line, never whole-file: skip each bad line, keep every parseable
event, and report the skip count. Recovery of a truncated final line is
unnecessary — the contract loses at most that one event.

---

## Error: Log Has No Decision Events

**Trigger**: File parses, but zero lines have `"type": "decision"`.

**Detection**:
```bash
python3 - "$LOG" <<'EOF'
import json, sys, collections
c = collections.Counter(json.loads(l)["type"] for l in open(sys.argv[1]) if l.strip())
print("counts by type:", dict(c))
EOF
```

**Root causes**:
| Symptom | Likely cause |
|---|---|
| Only `outcome` events | Recorder hook missing from `~/.claude/hooks/` while the finalizer is present |
| File empty | No /do-routed dispatch since the log was created |
| Dispatches happened but nothing recorded | Recorder skips dispatches without a `[do-route]` marker (deliberate: keeps route-health's denominator honest) — the dispatches were not /do-routed, or the marker is malformed |

**Response to user**:
```
route-events.jsonl exists with [N] outcome event(s) and zero decision events.

Decisions are appended by hooks/routing-decision-recorder.py (PostToolUse on
Agent dispatch) and only for /do-routed dispatches carrying a [do-route]
marker. Check that the recorder is synced to ~/.claude/hooks/ and that the
dispatches you expect were /do-routed.
```

---

## Error: Decision Has No Matched Outcome

**Trigger**: A DECISION event has no OUTCOME with the same `session` and
`key == "{agent}:{skill}"`.

**Root causes**:
| Cause | How to identify |
|---|---|
| Pending — finalizer has not run yet | Decision is recent; the finalizer fires on the next user prompt |
| Session ended before finalization | Decision `ts` is old and its session has no later events |
| Finalizer dropped it (stale, past max pending age) | Old decision, no outcome ever appears |

**Response to user**: Label the entry `pending — not yet finalized` (recent) or
`never finalized` (old). Outcomes arrive on a later user prompt, so a missing
outcome right after a dispatch is normal, never an error. Report the recorded
state; leave the outcome unset rather than inferring one.

---

## Error: Absent Additive Fields

**Trigger**: A decision lacks `n`/`failure`/`action`/`alternates` or
`gate_inputs_present`; an outcome lacks `reason` or `routing_relevant`.

**Cause**: The schema grew append-compatibly — lines written before a field
shipped simply lack it. Also, `n`/`failure`/`action`/`alternates` stay `null`
unless a real numeric `health=` was read (see trace-schema.md, health states).

**Response to user**: Treat absence as "not recorded then". Flag counts:
```
Note: [N] decision(s) predate the health-gate instrumentation — they show
WHAT was routed but carry no health data.
```
Present the fields that exist; leave the rest as unknown rather than inventing
values.

---

## Error: User Asks About a Dispatch Not in the Log

**Trigger**: User asks "why did I get routed to X?" but no DECISION matches X in
`agent`, `skill`, or `alternates`.

**Detection logic**:
```python
query = "golang-general-engineer"
matches = [d for d in decisions
           if query in d.get("agent", "") or query in d.get("skill", "")
           or query in (d.get("alternates") or [])]
```

**Root causes**:
| Cause | Explanation |
|---|---|
| Dispatch was not /do-routed | Manual Agent calls carry no `[do-route]` marker; the recorder skips them |
| Nested fan-out | The recorder records top-level /do-routed dispatches only — recording nested sub-dispatches would inflate route-health's denominator |
| Different session or older than the log | Filter widened to all sessions still finds nothing |

**Response to user**:
```
No decision event found for [X].

The log records /do-routed top-level dispatches only. This session has [N]
recorded decision(s): [list agent+skill pairs]. The dispatch you asked about
was either not /do-routed or was a nested sub-dispatch, which the recorder
deliberately excludes.
```

Show what IS in the log. Leave unrecorded dispatches unexplained rather than
speculating.

---

## Error-Fix Summary Table

| Error | Root cause | User message keyword | Fix |
|---|---|---|---|
| No log file | No dispatch yet, hooks unsynced, or env redirect | "No route event log found" | Name real path + producing hook; suggest sync-to-user-claude.py |
| Malformed line | Truncated append or manual edit | "unparseable line(s)" | Skip per line; report count; keep valid events |
| No decision events | Recorder unsynced or dispatches not /do-routed | "zero decision events" | Check recorder in ~/.claude/hooks/; confirm [do-route] marker |
| Unmatched outcome | Pending or never finalized | "pending — not yet finalized" | Label the state; outcomes arrive on a later prompt |
| Absent additive fields | Pre-instrumentation lines | "predate the health-gate instrumentation" | Treat as unknown; flag counts; keep values as recorded |
| Dispatch not in log | Not /do-routed or nested fan-out | "not /do-routed" | Show recorded decisions; explain the exclusion |
