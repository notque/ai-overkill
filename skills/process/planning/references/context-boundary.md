# Context-boundary policy

Choose context transitions inside `/do`; do not make the user manage sessions or commands.

| State | Action |
|---|---|
| The live conversation is primary evidence or decisions remain unresolved | Continue in the current context. |
| The next task is fully described by durable artifacts | A fresh worker or session can use those artifacts; transfer only when parallel work, separate expertise, or context limits warrant it. |
| Plan or session lifecycle must survive a user-visible pause | Use `pause.md`; planning owns durable pause and resume artifacts. |
| Inline worker or agent transfer within active execution | Use `session-handoff` and the Task Spec; do not create planning pause artifacts. |
| Context pressure is high but the task remains coupled | Compact only the evidence needed for the next judgment. |

Before a transition, use the Task Spec contract owned by `scripts/build-dispatch.py` and `/do`. Carry the request, intent, constraints and authority, relevant files, acceptance checks, and next action. Include decisions, prior results, and gaps when they affect the receiver's work. Keep required fields; do not invent a second schema here.

Use `session-handoff` for working-tree, PR, and live-process state. Link durable evidence and quote the parts needed for the next decision. Never assume conversation memory crosses a worker or session boundary. In the same live context, reuse unchanged instructions instead of reloading them at every phase. For checks, apply the evidence-reuse rules in `verification-before-completion`; a transition alone does not invalidate a result.
