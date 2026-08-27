# Context-boundary policy

Choose context transitions inside `/do`; do not make the user manage sessions or commands.

| State | Action |
|---|---|
| The live conversation is primary evidence or decisions remain unresolved | Continue in the current context. |
| The next task is fully described by durable artifacts | Start a fresh worker with a complete Task Spec, or start a fresh session from the plan artifacts. |
| Plan or session lifecycle must survive a user-visible pause | Use `pause.md`; planning owns durable pause and resume artifacts. |
| Inline worker or agent transfer within active execution | Use `session-handoff` and the Task Spec; do not create planning pause artifacts. |
| Context pressure is high but the task remains coupled | Compact only the evidence needed for the next judgment. |

Before a transition, verify that the receiver has the goal, scope, decisions, relevant paths, constraints, acceptance criteria, and next action. Never assume conversation memory crosses a worker or session boundary.
