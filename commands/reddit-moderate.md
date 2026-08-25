---
description: "Reddit moderation: fetch modqueue, classify content, take mod actions"
argument-hint: "[--auto] [--dry-run]"
allowed-tools: ["Read", "Bash", "Skill"]
---

# /reddit-moderate

Moderate your Reddit community. Fetches the modqueue, classifies each item against
subreddit rules, and recommends actions for your approval.

## Usage

```
/reddit-moderate           # Interactive: fetch, classify, present, confirm, act
/reddit-moderate --auto    # Auto mode: remove clear spam, skip uncertain
/reddit-moderate --dry-run # Dry-run: show recommendations without acting
```

## Loop Mode

```
/loop 10m /reddit-moderate --auto
```

Call the Skill tool with `reddit-moderate`.

Parse the argument:
- No argument → run interactive mode (Phase 1-5)
- "--auto" → run auto mode
- "--dry-run" → run dry-run mode
