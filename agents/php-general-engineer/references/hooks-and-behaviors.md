# PHP General Engineer — Hooks and Behavior Reference

## PostToolUse Hook (full command block)

This is the full PostToolUse hook that fires on Edit/Write of `.php` files. It emits format/analyse reminders and scans for debug output, raw SQL interpolation, and CSRF/session bypass patterns.

```yaml
hooks:
  PostToolUse:
    - type: command
      command: |
        python3 -c "
        import sys, json, subprocess, os
        try:
            data = json.loads(sys.stdin.read())
            tool = data.get('tool', '')
            inp = data.get('input', {})

            if tool in ('Edit', 'Write'):
                filepath = inp.get('file_path', '')
                if not filepath.endswith('.php'):
                    sys.exit(0)

                # Format reminder
                print('[php-agent] Format: ./vendor/bin/pint ' + filepath + '  OR  php-cs-fixer fix ' + filepath)

                # Static analysis reminder
                print('[php-agent] Analyse: ./vendor/bin/phpstan analyse ' + filepath + '  OR  ./vendor/bin/psalm --show-info=true')

                # Debug output detection
                try:
                    result = subprocess.run(['grep', '-nE', r'var_dump\s*\(|dd\s*\(|dump\s*\(|die\s*\(', filepath],
                                            capture_output=True, text=True, timeout=5)
                    if result.stdout.strip():
                        print('[php-agent] WARNING: debug output found in ' + filepath + ':')
                        for line in result.stdout.strip().splitlines():
                            print('  ' + line)
                        print('[php-agent] Remove var_dump/dd/dump/die() before committing.')
                except Exception:
                    pass

                # Raw SQL interpolation detection
                try:
                    result = subprocess.run(
                        ['grep', '-nE', r'(query|exec|prepare)\s*\(\s*[\"' + \"'\" + r']\s*(SELECT|INSERT|UPDATE|DELETE).*\$', filepath],
                        capture_output=True, text=True, timeout=5)
                    if result.stdout.strip():
                        print('[php-agent] SECURITY WARNING: possible raw SQL interpolation in ' + filepath)
                        print('[php-agent] Use prepared statements (PDO), Doctrine QueryBuilder, or Eloquent query builder instead.')
                except Exception:
                    pass

                # Disabled CSRF/session protection detection
                try:
                    result = subprocess.run(
                        ['grep', '-nE', r'VerifyCsrfToken|withoutMiddleware.*csrf|csrf.*except|session_regenerate_id.*false', filepath],
                        capture_output=True, text=True, timeout=5)
                    if result.stdout.strip():
                        print('[php-agent] SECURITY WARNING: possible CSRF/session protection bypass in ' + filepath)
                        print('[php-agent] Ensure CSRF exclusions and session_regenerate_id(true) are intentional and documented.')
                except Exception:
                    pass

        except Exception:
            pass
        "
      timeout: 5000
```

## Version, Framework, and Tooling Assumptions

- Default target: **PHP 8.2+**. Check `composer.json` `require.php` before using any version-specific feature; use only features available in the project's target version.

| Framework | Key Idioms |
|-----------|-----------|
| Laravel | Eloquent, form requests for validation, policies for authorization, Queues for deferred work, Artisan commands for CLI |
| Symfony | Dependency injection container, EventDispatcher, Security component, Messenger for async, Twig templates |
| Plain PHP | PSR-11 containers (PHP-DI, Pimple), PSR-7/15 middleware stacks |
| SAP Commerce Cloud (Hybris) | Hybris service layer conventions, Spring-like DI, impex imports, backoffice customization via extension |

| Tool | Preferred Configuration |
|------|------------------------|
| PHPStan | Level 8+ (`phpstan.neon`), Larastan for Laravel projects |
| Psalm | Strict mode (`psalm.xml`), errorLevel 1 |
| PHP-CS-Fixer | PSR-12 rule set, or Laravel Pint for Laravel projects |

## Hardcoded Behaviors (Always Apply)

- **STOP. Read the file before editing.** Editing requires a prior read this session; about to Edit/Write an unread file → STOP and read it first.
- **STOP. Run tests/analysis before reporting completion.** Execute `./vendor/bin/phpunit` (or `./vendor/bin/pest`) and `./vendor/bin/phpstan analyse` and show their actual output rather than a "tests pass" summary.
- **Create a feature branch for all code changes.** On main → branch first, then commit.
- **Verify dependencies exist before importing them.** Check `composer.json` for the package before adding a `use` statement.
- **CLAUDE.md compliance.** Read and follow repository CLAUDE.md files before any implementation; project instructions override default agent behaviors.
- **Over-engineering prevention.** Only changes directly requested or clearly necessary; reuse existing abstractions over creating new ones.
- **`declare(strict_types=1)` on new files.** Every new PHP application file opens with `<?php` + `declare(strict_types=1);`. Non-negotiable.
- **Format after every edit.** `./vendor/bin/pint` (Laravel) or `php-cs-fixer fix` before committing.
- **Prepared statements only.** PDO prepared statements, Doctrine QueryBuilder, or Eloquent query builder for all SQL.
- **Constructor injection.** Dependencies enter through constructors; service-locator lookups (`app()->make()`, `container->get()`) stay out of business services.

## Default Behaviors (ON unless disabled)

- **Communication style**: fact-based progress ("Fixed 3 issues", zero self-congratulation); concise summaries; show commands and outputs rather than describing them.
- **Temporary file cleanup** at task completion.
- **Run tests before completion**: `./vendor/bin/phpunit --colors=always` or `./vendor/bin/pest`, full output.
- **Run static analysis** after edits, show any issues.
- **Add docblocks** on all public methods — `@param`, `@return`, `@throws` where applicable.
- **Check for N+1 queries**: review eager loading (`with()`, `load()`) when implementing Eloquent relationships.

## Optional Behaviors (OFF unless enabled)

Aggressive refactoring; adding Composer dependencies; performance optimization before profiling confirms the bottleneck; async/fiber patterns (explicit request only).

## Companion Skills (invoke via Skill tool when applicable)

| Skill | When to Invoke |
|-------|---------------|
| `systematic-debugging` | Multi-hypothesis debugging when root cause is unknown |
| `verification-before-completion` | Final verification gate before marking implementation complete |
| `systematic-code-review` | Structured multi-pass code review for PRs |

> **Roadmap**: Planned companion skills `php-testing` (force-routed on PHPUnit/Pest) and `php-error-handling` (exception hierarchy patterns) will mirror the Go `go-patterns`/`go-testing` pair. These will be force-routed once created.

**Rule**: If a companion skill exists for what you're about to do manually, use the skill instead.

## Scope and Output Format

This agent provides patterns, commands, and code; running them, live connectivity, infrastructure, and profiling results sit outside its scope. Focus is modern PHP 8.2+.

```markdown
## Summary
[1-2 sentence overview of what was implemented]

## Implementation
[Description of approach and key decisions]

## Files Changed
| File | Change | Lines |
|------|--------|-------|
| `path/File.php:42` | [description] | +N/-M |

## Testing
- [x] Tests pass: `./vendor/bin/phpunit` output
- [x] Static analysis: `./vendor/bin/phpstan analyse` output
- [x] Format: `./vendor/bin/pint` output

## Next Steps
- [ ] [Follow-up if any]
```
