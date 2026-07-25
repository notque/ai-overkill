# Zsh Configuration Patterns

> **Scope**: Zsh-native patterns for PATH management, variable scoping, completions, and tool integration. Covers correct configuration for Zsh 5.8+ with detection commands for common violations.
> **Version range**: Zsh 5.8+
> **Generated**: 2026-05-26

---

## Overview

Zsh configuration errors rarely produce loud failures — they produce silent wrong behavior: PATH entries that vanish after restart, completions that work once then break, hooks that overwrite each other, or variables invisible to scripts. The patterns below show the Zsh-native approach for each common task, with detection commands to find violations in existing configs.

---

## Pattern Catalog

### Use `typeset -U path` for PATH Deduplication

Declare `path` as a unique array at the top of `~/.zshenv`. Every subsequent assignment deduplicates automatically.

```zsh
# ~/.zshenv — top of file
typeset -U path
path=(~/bin ~/.local/bin $path)
export PATH
```

**Why this matters**: Without `typeset -U`, repeated shell starts (tmux panes, subshells) cause PATH to grow with duplicate entries. Commands may unexpectedly resolve to earlier (possibly stale) versions of the same binary.

**Detection**:
```bash
grep -n 'export PATH' ~/.zshenv ~/.zshrc 2>/dev/null | grep -v 'typeset -U'
grep -n 'PATH.*:.*PATH' ~/.zshenv ~/.zshrc 2>/dev/null
```

**Preferred action**: Add `typeset -U path` as the first line in `~/.zshenv`. Replace string-concatenation PATH assignments (`export PATH="$PATH:/new"`) with array-style: `path+=(/new/path)`.

---

### Use `.zshenv` for Environment Variables (Not `.zshrc`)

Place `PATH`, `EDITOR`, `LANG`, `GOPATH`, and other exported variables in `~/.zshenv`.

```zsh
# ~/.zshenv — correct
export EDITOR=nvim
export LANG=en_US.UTF-8
export GOPATH=~/go
typeset -U path
path=(~/go/bin $path)
export PATH
```

**Why this matters**: `~/.zshrc` is sourced only for interactive shells. Scripts, cron jobs, and processes spawned by editors (e.g., neovim terminal) source `~/.zshenv` only. Variables in `~/.zshrc` are invisible to those processes.

**Detection**:
```bash
grep -n '^export\s\+\(EDITOR\|LANG\|GOPATH\|CARGO_HOME\|PATH\)' ~/.zshrc 2>/dev/null
```

**Preferred action**: Move exported environment variables from `~/.zshrc` to `~/.zshenv`. Keep aliases, functions, completions, and prompt in `~/.zshrc`.

---

### Use `compinit` Guards to Avoid Slow Startup

Guard `compinit` with a `~/.zcompdump` age check so it only rescans fpath once per day.

```zsh
# ~/.zshrc — fast compinit
autoload -Uz compinit
if [[ -n ~/.zcompdump(#qN.mh+24) ]]; then
  compinit
else
  compinit -C    # -C: use cached dump, skip security check
fi
```

**Why this matters**: Without the guard, `compinit` scans every file in every fpath directory on every shell start. With 20+ fpath directories (common with oh-my-zsh or homebrew), this adds 200–500ms per shell open.

**Detection**:
```bash
# Measure startup time
time zsh -i -c exit

# Profile compinit
zsh -i -c 'zmodload zsh/zprof; compinit; zprof' 2>&1 | head -20
```

**Preferred action**: Add the age guard around `compinit`. Regenerate `~/.zcompdump` manually when adding new completion scripts: `rm ~/.zcompdump && compinit`.

---

### Use `add-zsh-hook` Instead of Overwriting `precmd`/`preexec`

Attach hooks with `add-zsh-hook` — this preserves existing handlers.

```zsh
autoload -Uz add-zsh-hook

_my_precmd() { print -Pn "\e]0;%~\a"; }
add-zsh-hook precmd _my_precmd

_my_preexec() { print -Pn "\e]0;$1\a"; }
add-zsh-hook preexec _my_preexec
```

**Why this matters**: Writing `precmd() { ... }` directly replaces the entire `precmd` function. If a prompt theme or another plugin already defined `precmd`, that definition is lost — causing silent breakage of the overwritten handler (typically the prompt's vcs_info update).

**Detection**:
```bash
grep -n '^precmd()\|^preexec()\|^chpwd()' ~/.zshrc ~/.zsh/*.zsh 2>/dev/null
```

**Preferred action**: Replace bare `precmd() { ... }` function definitions with `add-zsh-hook precmd my_function_name`. Verify `autoload -Uz add-zsh-hook` is called first.

---

### Use Glob Qualifier `(N)` to Prevent "No Matches" Errors

Append `(N)` to globs that may match nothing when `NULL_GLOB` is not set, or when passing to commands that error on empty args.

```zsh
# Without (N): error if no .log files exist
rm -- *.log           # zsh: no matches found: *.log

# With (N): silently expands to nothing
rm -- *.log(N)        # no error if no matches

# Practical uses
for f in /var/log/*.log(N); do
  gzip "$f"
done

# Check existence before glob
local files=(~/.zsh/completions/*(N))
(( ${#files} > 0 )) && echo "Found ${#files} completions"
```

**Why this matters**: With `EXTENDED_GLOB` set (common default), unmatched globs throw an error and abort the current script or function. `(N)` is per-glob; `NULL_GLOB` is global (changes behavior for all globs in the session).

**Detection**:
```bash
grep -n '\*\.' ~/.zshrc ~/.zshenv 2>/dev/null | grep -v '(N)'
```

**Preferred action**: Add `(N)` to any glob used in conditional or cleanup contexts (`rm`, `for`, test). Use `setopt NULL_GLOB` only when you want this behavior session-wide.

---

### Guard Tool Integrations With `(( $+commands[tool] ))`

Check tool availability before running init hooks. Use `(( $+commands[tool] ))` (hash lookup) or `command -v tool &>/dev/null`.

```zsh
# ~/.zshrc — guarded tool inits
if (( $+commands[starship] )); then
  eval "$(starship init zsh)"
fi

if (( $+commands[direnv] )); then
  eval "$(direnv hook zsh)"
fi

if (( $+commands[zoxide] )); then
  eval "$(zoxide init zsh)"
fi

# Alternative: command -v (POSIX-compatible)
if command -v fnm &>/dev/null; then
  eval "$(fnm env --use-on-cd)"
fi
```

**Why this matters**: If a tool is not installed, the bare init command fails with "command not found" — producing an error on every new shell. This is especially visible in CI environments, Docker containers, or machines with minimal tool installations.

**Detection**:
```bash
grep -n 'eval.*init zsh\|eval.*hook zsh\|eval.*activate zsh' ~/.zshrc 2>/dev/null | grep -v 'command\|+commands'
```

**Preferred action**: Wrap every `eval "$(tool init zsh)"` in `(( $+commands[tool] )) &&` or an `if` block. The `$+commands` hash is faster than `command -v` (no subprocess).

---

### Place `fpath` Extensions Before `compinit`

Always extend `fpath` before calling `compinit`. Completions added after `compinit` are not registered until the next shell start.

```zsh
# Correct order in ~/.zshrc
typeset -U fpath
fpath=(~/.zsh/completions /opt/homebrew/share/zsh/site-functions $fpath)
autoload -Uz compinit
compinit
```

**Why this matters**: `compinit` builds the completion index from the current `fpath` snapshot. Extensions added after `compinit` are in `fpath` but not in the index — `_mycommand` completion is never found even though the file is present.

**Detection**:
```bash
awk '/fpath=|fpath\+=/,/compinit/' ~/.zshrc 2>/dev/null | grep -c 'compinit'
# If fpath lines appear after compinit, output will be > 0
```

**Preferred action**: Move all `fpath` assignments above the `autoload -Uz compinit && compinit` block. When adding Homebrew completions, use the setup block at the top of `.zshrc` before any plugin loading.

---

### Use `autoload -Uz` Consistently

Always pass `-Uz` flags to `autoload`: `-U` disables alias expansion (prevents accidental override), `-z` forces Zsh-style autoload.

```zsh
autoload -Uz compinit
autoload -Uz add-zsh-hook
autoload -Uz vcs_info
autoload -Uz my_custom_function
```

**Why this matters**: `autoload` without `-U` expands aliases during function definition, which can silently change behavior if you have an alias that shadows a builtin. `-z` forces Zsh-native loading semantics (as opposed to ksh-compatibility mode).

**Detection**:
```bash
grep -n '^autoload ' ~/.zshrc 2>/dev/null | grep -v '\-U'
```

**Preferred action**: Replace all bare `autoload func` with `autoload -Uz func`.

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| PATH grows on each new shell/tmux pane | No `typeset -U path` | Add `typeset -U path` at top of `~/.zshenv` |
| Env var not visible in scripts | Set in `~/.zshrc` | Move to `~/.zshenv` |
| Shell startup > 300ms | `compinit` running without cache guard | Add `~/.zcompdump` age check around `compinit -C` |
| Prompt stops updating after adding `precmd` | Overwrote existing `precmd` | Use `add-zsh-hook precmd my_func` |
| `no matches found: *.ext` error | Glob with no matches, no `(N)` qualifier | Append `(N)`: `*.ext(N)` |
| Tool init error on every shell open | `eval "$(tool init zsh)"` without availability guard | Wrap in `(( $+commands[tool] ))` check |
| Completions not found after adding `_mycommand` | `fpath` extended after `compinit` | Move `fpath` extension above `compinit` |
| `autoload` function uses wrong alias | Missing `-U` flag | Use `autoload -Uz func` |
| `compinit: insecure directories` | World/group-writable fpath entries | `compaudit`; `chmod go-w /path`; or `compinit -u` |
| `add-zsh-hook: command not found` | `autoload -Uz add-zsh-hook` not called | Add `autoload -Uz add-zsh-hook` before hook calls |
| `~/.zcompdump` outdated | Stale cache after adding new completions | `rm ~/.zcompdump && compinit` |
| `zsh -n` reports syntax error in valid-looking code | `EXTENDED_GLOB` patterns like `^` or `#` in unquoted strings parsed as glob operators | Quote strings containing these characters; `setopt NO_EXTENDED_GLOB` temporarily to isolate |

---

## Detection Commands Reference

```bash
# PATH growing (no typeset -U)
grep -n 'export PATH\|PATH.*:.*PATH' ~/.zshenv ~/.zshrc 2>/dev/null

# Env vars in wrong file (should be in .zshenv)
grep -n '^export\s\+\(EDITOR\|LANG\|GOPATH\|PATH\)' ~/.zshrc 2>/dev/null

# Missing compinit cache guard
grep -n 'compinit' ~/.zshrc 2>/dev/null | grep -v '\-C\|zcompdump'

# Direct precmd/preexec overwrite (should use add-zsh-hook)
grep -n '^precmd()\|^preexec()\|^chpwd()' ~/.zshrc 2>/dev/null

# Globs without (N) qualifier in loops/cleanup
grep -n 'rm.*\*\.' ~/.zshrc 2>/dev/null | grep -v '(N)'

# Tool inits without availability guard
grep -n 'eval.*init zsh\|eval.*hook zsh' ~/.zshrc 2>/dev/null | grep -v 'commands\|command -v'

# fpath after compinit
grep -n 'fpath\|compinit' ~/.zshrc 2>/dev/null

# autoload without -U flag
grep -n '^autoload ' ~/.zshrc 2>/dev/null | grep -v '\-U'

# Syntax check all rc files
for f in ~/.zshenv ~/.zprofile ~/.zshrc; do
  [[ -f "$f" ]] && zsh -n "$f" || echo "SYNTAX ERROR: $f"
done
```

---

## See Also

- `bash-migration.md` — Bash→Zsh syntax translation table
- `zsh-quick-reference.md` — Variable scoping, parameter expansion flags, special variables
- `tool-integrations.md` — Complete tool integration patterns (Go, Rust, Docker, Node.js, pyenv)
