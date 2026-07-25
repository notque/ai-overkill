
# Fish Shell Configuration Skill

Fish is not POSIX. Every pattern here targets Fish 3.0+ (supports `$()`, `&&`, `||`). Fish 4.0 (Rust rewrite) has no syntax changes. All generated code must use Fish-native syntax exclusively — never emit Bash constructs (`VAR=value`, `[[ ]]`, `export`, heredocs) in Fish contexts.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| migrating from Bash: converting `.bashrc`/`.bash_aliases`, `source`, `export`, `[[` in Fish file | `fish-bash-migration.md` | Full Bash-to-Fish syntax translation table. |
| editing fish config: variable assignment, PATH management, conditionals; error audit: "unknown command", PATH not persisting, abbreviation not working, broken conf.d | `fish-preferred-patterns.md` | Failure mode catalog with detection commands and error-fix mappings. |
| syntax lookup: variable scope, PATH, functions, abbreviations, conditionals, debugging | `fish-quick-reference.md` | Loads detailed guidance from `fish-quick-reference.md`. |
| wiring dev tools into fish: Go, Rust, Node, Python, Docker, PATH and init hooks | `fish-tool-integrations.md` | Loads detailed guidance from `fish-tool-integrations.md`. |

## Instructions

### Step 1: Confirm Fish Context

Before writing any shell code, confirm the target is Fish:

- `$SHELL` contains `fish`, or
- Target file has `.fish` extension, or
- Target directory is `~/.config/fish/`

If none of these hold, stop — this skill does not apply to Bash, Zsh, or POSIX shells.

### Step 2: Choose the Correct File Location

Place configuration in `conf.d/` modules with numeric prefixes for ordering — keep `config.fish` minimal. A monolithic `config.fish` with hundreds of lines is slow to load, hard to maintain, and impossible to selectively disable.

**Directory layout**:
```
~/.config/fish/
├── config.fish              # Minimal — interactive-only init
├── fish_variables           # Auto-managed by Fish (never edit)
├── conf.d/                  # Auto-sourced in alphabetical order
│   ├── 00-path.fish
│   ├── 10-env.fish
│   └── 20-abbreviations.fish
├── functions/               # Autoloaded functions (one per file)
│   ├── fish_prompt.fish
│   └── mkcd.fish
└── completions/             # Custom completions
    └── mycommand.fish
```

**Decision tree**:
| What you're writing | Where it goes |
|---------------------|---------------|
| PATH additions | `conf.d/00-path.fish` |
| Environment variables | `conf.d/10-env.fish` |
| Abbreviations | `conf.d/20-abbreviations.fish` |
| Tool integrations | `conf.d/30-tools.fish` |
| Named function | `functions/<name>.fish` |
| Custom prompt | `functions/fish_prompt.fish` |
| Completions | `completions/<command>.fish` |
| One-time interactive init | `config.fish` (inside `status is-interactive`) |

### Step 3: Write Variables

Variable assignment is always `set VAR value` — never `VAR=value` (syntax error in Fish) or `export VAR=value`.

```fish
set -l VAR value    # Local — current block only
set -f VAR value    # Function — entire function scope
set -g VAR value    # Global — current session
set -U VAR value    # Universal — persists across sessions (use sparingly)
set -x VAR value    # Export — visible to child processes
set -gx VAR value   # Global + Export (typical for env vars)
set -e VAR          # Erase variable
set -q VAR          # Test if set (silent, for conditionals)
```

Every Fish variable is a list. Never use colon-separated strings for PATH or similar variables — `set PATH "$PATH:/new/path"` creates a single malformed element because Fish PATH is a list, not a colon-delimited string.

### Step 4: Manage PATH

Use `fish_add_path` for PATH manipulation — it handles deduplication and persistence automatically. Manual `set PATH` only for session-scoped overrides.

```fish
# CORRECT: fish_add_path handles deduplication and persistence
fish_add_path ~/.local/bin
fish_add_path ~/.cargo/bin
fish_add_path -P ~/go/bin     # -P = session only, no persist

# CORRECT: Direct manipulation when needed (session only)
set -gx PATH ~/custom/bin $PATH

# WRONG: Colon-separated string — Fish PATH is a list
# set PATH "$PATH:/new/path"
```

### Step 5: Write Functions

The autoloaded function filename must match the function name exactly — `functions/foo.fish` must contain `function foo`. A mismatch causes "Unknown command" errors.

```fish
# ~/.config/fish/functions/mkcd.fish
function mkcd --description "Create directory and cd into it"
    mkdir -p $argv[1]
    and cd $argv[1]
end
```

Functions with argument parsing:
```fish
function backup --description "Create timestamped backup"
    argparse 'd/dest=' 'h/help' -- $argv
    or return

    if set -q _flag_help
        echo "Usage: backup [-d destination] file..."
        return 0
    end

    set -l dest (set -q _flag_dest; and echo $_flag_dest; or echo ".")
    for file in $argv
        set -l ts (date +%Y%m%d_%H%M%S)
        cp $file $dest/(basename $file).$ts.bak
    end
end
```

### Step 6: Choose Between Abbreviations, Functions, and Aliases

| Use Case | Mechanism | Why |
|----------|-----------|-----|
| Simple shortcut | `abbr -a g git` | Expands in-place, visible in history |
| Needs arguments/logic | `function` in `functions/` | Full programming, works in scripts |
| Wrapping a command | `alias ll "ls -la"` | Convenience; creates function internally |

Abbreviations are interactive-only — they do not work in scripts. Always wrap them in an interactive guard because they have no effect during non-interactive sourcing:

```fish
# Always guard abbreviations
if status is-interactive
    abbr -a g git
    abbr -a ga "git add"
    abbr -a gc "git commit"
    abbr -a gst "git status"
    abbr -a dc "docker compose"
end
```

### Step 7: Write Conditionals and Control Flow

Use the `test` builtin for conditionals — never `[[ ]]` (syntax error in Fish) or `[ ]` (calls external `/bin/[`, slower than the builtin). Fish has no word splitting, so `$var` and `"$var"` behave identically — quote only when you need to prevent list expansion or preserve empty strings.

```fish
# Conditionals — use 'test', not [[ ]]
if test -f config.json
    echo "exists"
else if test -d config
    echo "is directory"
end

# Command chaining (both styles work in Fish 3.0+)
mkdir build && cd build && cmake ..
mkdir build; and cd build; and cmake ..

# Loops
for file in *.fish
    echo "Processing $file"
end

# Switch
switch $argv[1]
    case start
        echo "Starting..."
    case stop
        echo "Stopping..."
    case "*"
        echo "Unknown: $argv[1]"
        return 1
end
```

### Step 8: Integrate External Tools

Guard every tool integration with `type -q` so the config works on machines where the tool is not installed:

```fish
# ~/.config/fish/conf.d/30-tools.fish
if type -q starship
    starship init fish | source
end

if type -q direnv
    direnv hook fish | source
end

if type -q fzf
    fzf --fish | source
end

# Homebrew (macOS)
if test -x /opt/homebrew/bin/brew
    eval (/opt/homebrew/bin/brew shellenv)
end

# Nix
if test -e /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
    source /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
end
```

### Step 9: Verify

1. **Syntax check** — run `fish -n <file>` (parse without executing)
2. **Function name match** — verify filename matches function name for every file in `functions/`
3. **Interactive guards** — verify `status is-interactive` guards on abbreviations and key bindings in `conf.d/`
4. **Clean environment test** — run `fish --no-config` then `source <file>` to confirm isolated correctness


## Error Handling

### Error: "Unknown command" for new function
Cause: Filename does not match function name
Solution: Ensure `functions/foo.fish` contains exactly `function foo`. Check for typos in both the filename and the function declaration.

### Error: PATH changes not persisting across sessions
Cause: Used `set -gx PATH` (session-only) instead of `fish_add_path` (writes to universal `fish_user_paths`)
Solution: Use `fish_add_path /new/path` which persists by default, or use `set -U fish_user_paths /path $fish_user_paths` explicitly.

### Error: Abbreviations not expanding in scripts
Cause: Abbreviations are interactive-only by design
Solution: Use a function instead. Move the logic from `abbr` to a file in `functions/`.

### Error: Variable not visible to child process
Cause: Missing `-x` (export) flag on `set`
Solution: Use `set -gx VAR value` to make variable visible to subprocesses. Check with `set --show VAR` to inspect current scope and export status.

## Worked Examples

### Setting Up a New Fish Config
User says: "Set up my Fish shell config"
1. Confirm Fish context
2. Create modular structure in `~/.config/fish/`
3. Write `conf.d/00-path.fish`, `conf.d/10-env.fish`, `conf.d/20-abbreviations.fish`
4. Syntax-check all files

### Migrating a Bash Alias File
User says: "Convert my .bash_aliases to Fish"
1. Read `.bash_aliases`, confirm Fish target
2. Determine which become abbreviations vs functions
3. Write abbreviations to `conf.d/`, functions to `functions/`
4. Syntax-check, test in clean shell
