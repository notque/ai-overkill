---
description: "Learning system interface: stats, search, graduate learnings. Backed by learning.db (SQLite + FTS5)."
argument-hint: "[status|list|search <term>|graduate]"
allowed-tools: ["Bash", "Read", "Edit", "Grep", "Glob", "Skill"]
---

# Retro Knowledge System

Interact with the learning database: view stats, search entries, and graduate mature learnings into agents/skills.

## Usage

```
/retro              # Status overview (default)
/retro list         # Display all accumulated knowledge
/retro search TERM  # Full-text search across learnings
/retro graduate     # Graduate mature knowledge into agents/skills
```

## Subcommands

### status (default)
Shows learning system health: entry counts, categories, graduation status, injection method.

### list
Displays all accumulated knowledge grouped by category from the learning database.

### search
Full-text search (FTS5) across all learnings. Returns results ranked by relevance.

### graduate
AI-driven evaluation of mature learning entries for embedding into specific agents/skills. Queries design/gotcha entries, evaluates each for prescriptive readiness, drafts modifications to the target agent/skill, and applies after user approval.

## Instructions for Claude

Call the Skill tool with `retro`. Pass the command argument through to select the subcommand.

Parse the argument to select the subcommand:
- No argument or "status" → run status subcommand
- "list" → run list subcommand
- "search TERM" → run search subcommand
- "graduate" → run graduate subcommand

All retro operations go through `python3 ~/.claude/scripts/learning-db.py` — never parse learning files manually.

## Related

- `scripts/learning-db.py` — Python CLI for all database operations
- `hooks/session-context.py` — Injects pre-built dream payload and high-confidence patterns at session start
- `scripts/learning.db` — SQLite database with FTS5 search index
