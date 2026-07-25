# PHP Quality Review Process

## Core Rules (Always Apply)

### Strict Types Declaration

Every PHP file must begin with `declare(strict_types=1)`. This enforces scalar type coercion rules, catching type errors at call time instead of silently converting values.

```php
<?php

declare(strict_types=1);

// Without strict_types: strlen(123) silently returns 3
// With strict_types: strlen(123) throws TypeError
```

This is non-negotiable. Omitting it is a code quality defect.

### PSR-12 Coding Standard

PSR-12 extends PSR-1 and PSR-2 as the accepted PHP coding style. Key rules:

- 4-space indentation, no trailing whitespace
- One class per file
- `use` statements after namespace with a blank line before and after
- Visibility required on all properties, methods, and constants
- Opening braces on same line for control structures
- Opening braces on next line for classes and methods

## Phase 1: ASSESS

Determine what kind of PHP quality review is needed:

| Request type | Load references | Action |
|-------------|----------------|--------|
| Code review | All quality refs | Full quality pass |
| Type system question | `modern-php-features.md` | Feature-specific guidance |
| Framework patterns | `framework-idioms.md` | Idiomatic pattern review |
| Tooling setup | `quality-tools.md` | Config and CI guidance |

**Gate**: Request classified and relevant references loaded.

## Phase 2: REVIEW

Apply loaded reference knowledge to the user's code or question. Every review checks:
1. `declare(strict_types=1)` present
2. PSR-12 compliance
3. Modern PHP features used where appropriate (from references)
4. Framework idioms followed (if applicable)
5. Quality tooling configured (if applicable)

**Gate**: Specific, reference-backed feedback provided.
