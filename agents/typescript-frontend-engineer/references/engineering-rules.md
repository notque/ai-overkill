# TypeScript Frontend Engineer: Engineering Rules

House rules, hard gates, and stop conditions. Generic TypeScript and React idioms are assumed known and are not restated here.

---

## Hard Boundary Patterns (HARD GATE)

Before writing TypeScript code, check for these patterns. If found:
1. STOP - Pause execution
2. REPORT - Flag to user
3. FIX - Remove before continuing

| Pattern | Why It Violates Standards | Correct Alternative |
|---------|---------------|---------------------|
| `const data: any = ...` (without justification) | Defeats type safety | Define proper interface or use `unknown` |
| Type assertion without validation: `response.json() as User` | Runtime mismatch crashes app | Validate with Zod: `UserSchema.parse(data)` |
| `// @ts-ignore` or `@ts-nocheck` | Hides real bugs | Fix root cause or properly extend types |
| `forwardRef` in React 19 | Deprecated, removed in future | Use `ref` as prop: `function Component({ ref }: { ref?: Ref })` |
| `useFormState` from react-dom | Renamed in React 19 | Use `useActionState` from react |
| Implicit ref callback return: `<div ref={el => (x = el)} />` | React 19 TypeScript error | Explicit: `<div ref={el => { x = el }} />` |

### Detection
```bash
grep -r ": any" src/ --include="*.ts" --include="*.tsx"
grep -r "as User\|as.*Response" src/ --include="*.ts" --include="*.tsx"
grep -r "@ts-ignore\|@ts-nocheck" src/
grep -r "forwardRef" src/ --include="*.tsx"
grep -r "useFormState" src/ --include="*.tsx"
```

### Exceptions
- `any` is acceptable ONLY with detailed comment explaining why (e.g., third-party library with no types)
- Type assertions acceptable for DOM elements: `event.target as HTMLFormElement`
- `forwardRef` acceptable only in React 18 projects not yet migrated
- Replace `@ts-ignore` with `@ts-expect-error` (it fails when the suppression stops being needed); link the GitHub issue if it is a TypeScript bug

## House Preferences

- Create custom type utilities only after the pattern repeats 3+ times. Two occurrences is a coincidence.
- **interface** for object shapes, component props, class implementations. **type** for unions, intersections, tuples, mapped types, primitive aliases. Be consistent within a file.
- `safeParse` for user-facing validation (returns errors), `parse` for internal validation (throws).
- Always validate data crossing a trust boundary: APIs, user input, localStorage, URL params.

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../../../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Type assertion is fine here, I know the shape" | Shape changes break at runtime, not compile time | Add Zod schema and validate |
| "`any` is just temporary for prototyping" | Technical debt spreads, types become unreliable | Use `unknown` or proper types immediately |
| "This API response is stable" | APIs change without notice | Always validate with Zod schema |
| "React 18 pattern still works" | Deprecated patterns removed in future versions | Migrate to React 19 patterns now |
| "Type checking is slow, I'll relax strict mode" | Loosening types defeats TypeScript's purpose | Optimize config, not type safety |

## Verification STOP Blocks

These checkpoints are mandatory. Do not skip them even when confident.

- **After writing code**: STOP. Run `npx tsc --noEmit` and show the output. Code that does not compile is not done.
- **After claiming a fix**: STOP. Verify the fix addresses the root cause, not just the symptom. Re-read the original error and confirm it cannot recur.
- **After completing the task**: STOP. Run the type checker and any relevant tests before reporting completion. Show the actual output.
- **Before editing a file**: Read the file first. Blind edits cause regressions.
- **Before committing**: Do not commit to main. Create a feature branch. Main branch commits affect everyone.

## Blocker Criteria

STOP and ask the user (always get explicit approval) before proceeding when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Multiple state management approaches possible | User preference (Zustand vs Redux vs Context) | "Use Zustand (lightweight), Redux Toolkit (complex apps), or Context (simple)?" |
| Unclear validation requirements | Over-validation hurts UX | "Validate on blur, on change, or on submit?" |
| API contract ambiguous | Wrong types cause runtime errors | "What's the exact API response structure? Can you share an example?" |
| React version unclear | React 18 vs 19 patterns differ | "Are you using React 18 or React 19?" |
| Breaking type changes | User coordination for migration | "This changes types used by 5 other components - proceed?" |
| Form library choice | Project consistency matters | "Use React Hook Form (recommended) or Formik?" |

## Death Loop Prevention

### Retry Limits
- Maximum 3 attempts for type error resolution
- If types still fail to compile after 3 attempts, simplify approach

### Compilation-First Rule
1. Verify TypeScript compilation before linting
2. Fix type errors before addressing ESLint warnings
3. Fix compilation before running tests

### Recovery Protocol
1. **Detection**: More than 3 type errors after attempting fix
2. **Intervention**: Simplify types - remove complex mapped types, use simpler interfaces
3. **Prevention**: Start with simple types, add complexity only when needed

## Non-Obvious Failure Modes

Symptoms that do not point at their cause.

| Symptom | Cause | Fix |
|---|---|---|
| Input loses focus every keystroke; animations restart; effect cleanup+setup run every parent render; scroll resets | Component defined inline inside another component's body — new type identity each render | Hoist the component definition out |
| One user's data appears in another user's response | Module-level mutable variable in a server module is process-wide shared memory across concurrent renders | Keep request data local to the render tree |
| `React.cache()` never hits | Argument equality is `Object.is`; inline object args are new references each call | Pass primitives, not object literals |
| Both arrays serialize across the RSC boundary | `.toSorted()`/`.filter()`/`.map()`/`.slice()`/spread/`Object.assign()`/`structuredClone()` break reference-identity dedup | Move the transform to the client component |
| Effect re-runs after remount despite `[]` deps | Effects re-run on remount, including Strict Mode double-invocation in dev | Module-level guard for once-per-app-load work |
| `useEffectEvent` function in a dep array causes churn | Its identity is intentionally unstable by design | Never list it as a dependency |
| `localStorage` throws in production | `getItem`/`setItem` throw in private browsing (Safari, Firefox), over quota, or disabled by policy | Always wrap in try-catch |
| Custom swipe/zoom gesture cannot cancel scroll | `passive: true` forbids `preventDefault()` | Omit `passive` for listeners that must cancel default behavior |
| A single slow fetch blocks every sibling fetch from starting | Awaited sequentially instead of composed as parallel children | Compose parallel Suspense children |

Ordering rule for Server Actions: validate input first (avoids auth overhead on malformed data), then authenticate, then authorize, then mutate.

Do not hoist I/O to module level when assets vary per request or user, files may change at runtime, or large files would consume excessive memory.

Safe at module level: immutable static config loaded once at startup, caches intentionally shared across requests and keyed correctly, process-wide singletons holding no user-specific mutable state.
