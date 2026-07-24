---
summary: "Five-minute path from install to first /do."
read_when:
  - "onboarding a new user"
---

# Start Here

Install once, then say what you want in plain English. The router connects your request to the right agent, skill, and quality gates automatically. You never browse the catalog; the value is wired in. This page gets you from zero to your first `/do` in about five minutes.

## What You Need

One thing: [Claude Code](https://docs.claude.com/en/docs/claude-code) installed.

```bash
claude --version
```

If that prints a version number, you're good. If not, install Claude Code first and come back.

Optional: Codex CLI, Factory, or Reasonix. The toolkit mirrors skills (and agents where the harness supports them) into their directories (`~/.codex/`, `~/.factory/`, `~/.reasonix/`), so all the CLIs dispatch the same domain expertise. Reasonix has no agent surface, so it gets skills + scripts + hooks only. Claude Code remains the only runtime with the full hook surface. Gemini CLI support was removed (deprecated upstream, transitioned to Antigravity CLI); Antigravity support pending CLI maturity — see README § "Gemini CLI / Antigravity CLI Support (removed)".

Verify optional tools: `codex --version` / `factory --version` / `reasonix --version`.

Command entry points:

| CLI | Command |
|-----|---------|
| Claude Code | `/do` |
| Codex | `$do` |
| Factory | `/do` |
| Reasonix | `/do` |

## Install

```bash
git clone https://github.com/notque/vexjoy-agent.git
cd vexjoy-agent
./install.sh
```

The installer asks one question: symlink or copy. Symlink means updates via `git pull`. Copy means a stable snapshot. Either works.

What it does: installs agents, skills, hooks, commands, and scripts into `~/.claude/` (symlinked or copied per your choice). Mirrors skills and agents into `~/.codex/`, agents into `~/.factory/droids/` (Factory calls agents "droids"), and skills + scripts + hooks into `~/.reasonix/` (no agent surface there). It configures each harness's supported hooks.

### Codex hook coverage

Codex integration requires v0.144.1+. The original six-hook allowlist was correct for v0.114, when Codex tool hooks intercepted only Bash. Current Codex support classifies the 74 Claude hook registrations as 26 native, 35 adapter-backed, and 13 unsupported (61 supported); the counts are registrations, not unique files.

The adapter translates Codex `apply_patch` operations into Write/Edit events for existing VexJoy guards. It cannot cover writes through `unified_exec`, unmatched MCP tools, WebSearch, or other unsupported paths. Codex also omits Claude's `conversation_history` at PreCompact and `session_data` at Stop, so those adapted hooks run with degraded telemetry. This is not full Claude parity.

After installation or a hook update, run `/hooks` in Codex and review changed definitions. Codex hash-trusts hook commands and skips changed definitions until you approve them.

## Verify

```bash
python3 ~/.claude/scripts/install-doctor.py check
python3 ~/.claude/scripts/install-doctor.py inventory
```

`check` verifies the install layout, settings, hook paths, learning DB access, and CLI mirrors. `inventory` lists what each CLI can currently see. If you pull new toolkit changes later and want the mirrors updated, rerun `./install.sh`.

## First Commands

Open any project folder. Start Claude Code.

```bash
claude
```

Then:

```
/do what can you do?
```

The router reads your request, picks the right agent and skill, runs it. This one shows you the full routing system.

```
/do give me an overview of this codebase
```

Works in any repo. Reads structure, identifies patterns, explains what the project does.

```
/do write a blog post about [topic]
```

Multi-phase pipeline: research, outline, draft, voice validation. Output lands in a file.

```
/html report on [anything you just worked on]
```

One self-contained HTML file: report, slide deck, prototype, data viz. Opens in any browser, shares as a single file. The output non-engineers love most.

```
/do debug why [problem]
```

Systematic debugging. Gathers evidence before guessing.

## What Got Installed

Five kinds of things in `~/.claude/`. You never invoke them by name; the router does.

- **Agents**: domain experts. Go, Python, Kubernetes, data engineering, content, more.
- **Skills**: reusable workflows. TDD, debugging, code review, article writing, research pipelines.
- **Hooks**: automation that fires on session start, after errors, before context compression.
- **Commands**: slash command definitions that wire up entry points like `/do`.
- **Scripts**: Python utilities agents call for deterministic operations.

These load automatically when you start Claude Code in any directory.

## Where Next

Depends on what you're here for.

**[For Knowledge Workers](for-knowledge-workers.md)** : Writing, research, data analysis, moderation, HTML artifacts. No code required.

**[For Developers](for-developers.md)** : Architecture, extension points, how to build your own agents and skills.

**[For AI Power Users](for-ai-wizards.md)** : Routing internals, hook lifecycle, pipeline architecture.

**[For AI Agents](for-claude-code.md)** : Machine-dense component inventory. If you're an LLM operating in this repo, start there.
