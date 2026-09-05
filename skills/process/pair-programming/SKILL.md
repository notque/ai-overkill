---
name: pair-programming
description: "Collaborative coding with enforced micro-steps and user-paced control."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "pair program"
    - "collaborative coding"
    - "micro-steps"
    - "step by step coding"
    - "one change at a time"
    - "show each change"
    - "walk me through"
    - "interactive coding"
  category: process
  pairs_with:
    - test-driven-development
    - subagent-driven-development
---

# Pair Programming Skill

Use **Announce-Show-Wait-Apply-Verify** when the user wants to review each change before it is applied. Any domain agent can execute. Stay in the interactive main session; a fork cannot conduct these user gates.

## Instructions

### Session Setup

1. Read the request and relevant code.
2. Show a numbered plan with one logical change per step.
3. Wait for acknowledgment; incorporate requested additions, removals, or reordering.

Track current step, remaining steps, and speed. Announce each change as “Step N of ~M.”

### Micro-Step Protocol (Per Change)

1. **Announce** the change and reason in 1–2 sentences.
2. **Show** the proposed diff or code block, including trivial changes. Default: 15 lines; hard cap: 50. Split larger changes into named sub-steps such as 3a, 3b, and 3c.
3. **Wait** for an explicit control command.
4. **Apply** only after `ok`, `yes`, or `y`.
5. **Verify** with relevant checks and report the result in one sentence. Use `verification-before-completion` for check selection and evidence; keep project-required checks.

| Command | Action |
|---------|--------|
| `ok` / `yes` / `y` | Apply current step, then propose the next |
| `no` / `n` | Skip this step and propose an alternative |
| `faster` | Double step size, up to 50 lines; show any revised proposal and wait |
| `slower` | Halve step size, down to 5 lines; show any revised proposal and wait |
| `skip` | Skip current step and move to the next |
| `plan` | Show remaining steps |
| `done` | End pairing and run final verification |

Speed and navigation commands do not approve a code change. Split changes by logical unit as well as size; announce the split before showing its first part.

### Speed Adjustment

Apply and acknowledge speed changes immediately: “Speed adjusted to ~N lines per step.”

| Setting | Lines per step | Trigger |
|---------|----------------|---------|
| Slowest | 5 | Repeated `slower` |
| Slow | 7 | `slower` from default |
| Default | 15 | Session start |
| Fast | 30 | `faster` from default |
| Fastest | 50 | Repeated `faster` |

### Session End

When the user says `done` or all steps finish, run required final checks and relevant checks not already valid for the final state. Include a full suite when the project requires it or the changes warrant it. Report completed and skipped steps, changed files, check results, and unfinished work. Ending pairing does not complete skipped work.

### Examples

For a Go CSV parser, a plan might cover the record struct, parser, error handling, tests, and integration. Show the plan and wait. Propose an 8-line `CSVRecord` struct, wait for `ok`, apply, and verify. Repeat for the parser.

After `faster` at the default speed, show up to 30 lines per step; `slower` then returns to 15. If the user ends after step 4 of 6, run relevant Go checks such as `go vet` and `go test ./...`, then report the two remaining steps with the results.

## Error Handling

### User Says "Just Do It" / Wants Autonomous Mode

An explicit request to finish autonomously changes the mode. Acknowledge it and continue the remaining authorized work without micro-step approvals. Ask only if the requested mode is unclear.

### Verification Fails After a Step

Propose the fix as the next micro-step: announce, show, wait, apply, and recheck. Keep the interactive approval contract until the user changes mode.

### Step Too Large to Fit Size Limit

Split into logical sub-steps within the current limit. Announce the split and seek approval for each sub-step.

## References

- [Micro-step controls](#micro-step-protocol-per-change)
- [Speed settings](#speed-adjustment)
