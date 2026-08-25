---
summary: "30-second start: install, /do, mental model."
read_when:
  - "first-time setup"
---

# Quick Start

**Read time: 30 seconds**

---

## Installation

Before using VexJoy Agent, run the installer:

```bash
cd ~/vexjoy-agent
./install.sh
```

Claude Code is the primary runtime. If you also use Codex CLI, Factory, or Reasonix, the same install mirrors toolkit skills (and agents where the harness supports them) into `~/.codex/`, `~/.factory/`, and `~/.reasonix/` so all the CLIs share the same skill library. Reasonix has no agent surface, so it gets skills + scripts + hooks only. Gemini CLI support was removed (deprecated upstream, transitioned to Antigravity CLI); Antigravity support pending CLI maturity — see README § "Gemini CLI / Antigravity CLI Support (removed)".

Codex hook support requires v0.144.1+. The six hooks shipped for v0.114 were correct for that Bash-only hook surface; current support covers 25 native and 35 adapter-backed registrations (60 supported), with 13 unsupported. The adapter covers `apply_patch`, not writes through `unified_exec` or other unmatched tools, and PreCompact/Stop hooks receive less telemetry than on Claude Code. After install or a hook update, run `/hooks` in Codex to review and trust changed definitions.

Command entry points:
- Claude Code: `/do`
- Codex: `$do`
- Factory: `/do`
- Reasonix: `/do`

**Alternative (bootstrap via Claude):** Start Claude Code in the vexjoy-agent directory. The sync hook will automatically copy agents, skills, hooks, commands, and scripts to `~/.claude/`.

```bash
cd ~/vexjoy-agent
claude
```

> **Note:** The initial sync must run from the vexjoy-agent directory. After that, hooks work globally from any directory.

Verify the install:

```bash
python3 ~/.claude/scripts/install-doctor.py check
python3 ~/.claude/scripts/install-doctor.py inventory
```

If Codex should pick up newly added skills or agents after a `git pull`, rerun `./install.sh`.

---

## The Simple Version

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   Just tell Claude what you want.                              ║
║                                                                ║
║   "I want to debug this failing test"                          ║
║   "Review my Go code for quality"                              ║
║   "Add this feature using TDD"                                 ║
║                                                                ║
║   Claude routes to the right tools automatically.              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

That's it. You can stop reading here.

---

## Want More Control?

### Option A: Use the Smart Router

```
/do [what you want in plain language]
$do [what you want in plain language]
```

Examples:
- `/do Debug why authentication is broken`
- `/do Extract coding patterns from this repo`
- `/do Make this status update professional`
- `$do Debug why authentication is broken`

Use `/do` in Claude Code and `$do` in Codex.

The system figures out which tools to use and tells you what it selected.

---

### Option B: Use the Router for Specific Workflows

The router command routes your request to the right agent and skill automatically. Use `/do` in Claude Code and Factory, and `$do` in Codex:

| Want This? | Try This |
|------------|----------|
| Test-driven development | `/do write tests for this function using TDD` |
| Systematic debugging | `/do debug this test failure` |
| Code linting/formatting | `/do lint this project` |
| Verification before shipping | `/do verify this change is correct` |
| Go quality checks | `/do run Go quality checks on this package` |

Full list of available agents and skills: [REFERENCE.md](./REFERENCE.md)

---

### Option C: Request Specific Expertise

For complex domain work, ask for a specialized agent:

```
"Use the golang-general-engineer agent to review this code"
"Use the kubernetes-helm-engineer agent to help with deployment"
```

Specialized agents available across: Go, Python, Kubernetes, React, TypeScript, databases, monitoring, and more.

---

## Natural Language Triggers

These phrases automatically activate the right tools:

| Say This | Gets You |
|----------|----------|
| "TDD" or "test first" | Test-driven development workflow |
| "debug" or "investigate" | Systematic debugging methodology |
| "lint" or "format" | Code linting and formatting |
| "read only" | Exploration without modifications |
| "verify" or "make sure" | Multi-layer verification |

---

## The Mental Model (Optional)

```
┌─────────────────────────────────────────────────────────┐
│                    Your Request                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│   /do in Claude | $do in Codex | /do in Factory         │
│         (or natural-language routing)                   │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Agents  │    │  Skills  │    │ Commands │
    │          │    │          │    │          │
    │ Deep     │    │ Workflow │    │ Explicit │
    │ expertise│    │ patterns │    │ actions  │
    └──────────┘    └──────────┘    └──────────┘
```

**You don't need to understand this.** Just describe what you want.

---

## Next Steps

- **Ready to work?** Just start. Describe your task.
- **Want the full command list?** See [REFERENCE.md](./REFERENCE.md)
- **Building your own tools?** See [CLAUDE.md](../CLAUDE.md)
