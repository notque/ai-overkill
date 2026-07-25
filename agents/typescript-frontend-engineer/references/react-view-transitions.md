# React View Transitions Reference
<!-- Loaded by typescript-frontend-engineer when task involves ViewTransition, page animations, shared element transitions, or navigation animations -->

## Overview

`<ViewTransition>` is a React component (canary/React 19+) that wraps content to animate its enter, exit, and update. Animations activate when state updates are wrapped in `startTransition`, driven by `useDeferredValue`, or triggered by `<Suspense>` resolving.

**Browser support:** Chromium 111+, Firefox 144+, Safari 18.2+. Always include reduced-motion CSS.

- Next.js: enable `experimental.viewTransition: true` in `next.config.js` to also animate `<Link>` navigations.
- `instance` object in event handlers: `instance.old`, `instance.new`, `instance.group`, `instance.imagePair`.
- `onShare` takes precedence over `onEnter`/`onExit`. Always return a cleanup function from event handlers.

This API is thinly documented and its failure modes are non-obvious. That is what this file is for.

---

## Rules That Are Not Guessable

- **`flushSync` skips animations.** Use `startTransition` instead.
- **Place directional `<ViewTransition>` in page components, not layouts.** Layouts persist across navigations and never unmount — `enter`/`exit` won't fire on route changes.
- **Omit `key` to trigger an update (cross-fade)** rather than exit + enter. This avoids Suspense remount/refetch when switching between views that share identity. Use `key` when content identity changes and state should reset; omit it for tabs, panels, carousels.
- **Isolate persistent layout elements.** Headers, navbars, and sidebars are captured in the page's transition snapshot and slide along with page content unless given a unique `viewTransitionName`.
- **Match skeleton to content.** Give matching controls in the `<Suspense>` fallback and the real content the same `viewTransitionName` so they morph in place rather than cross-fading.
- **Do not put manual `viewTransitionName` on the root DOM node directly inside a `<ViewTransition>`** — React's auto-generated name overrides it.
- `useDeferredValue` makes filter updates a transition, activating `<ViewTransition>` on the results container. Use `default="none"` on per-item transitions to prevent cross-fading every item on every keystroke.

## Two CSS Workarounds

Text elements, to avoid raster scaling artifacts on size changes:

```css
::view-transition-group(.text-morph) { animation-duration: var(--duration-move); }
::view-transition-old(.text-morph) { display: none; }
::view-transition-new(.text-morph) { animation: none; object-fit: none; object-position: left top; }
```

Elements with `backdrop-filter`, to hide the old snapshot and avoid a flash:

```css
::view-transition-old(persistent-nav) { display: none; }
::view-transition-new(persistent-nav) { animation: none; }
```

## Duration Budget

| Transition | Duration |
|---|---|
| Direct toggle (expand/collapse) | 100–200ms |
| Route transition (slide) | 150–250ms |
| Suspense reveal (skeleton → content) | 200–400ms |
| Shared element morph | 300–500ms |

## Implementation Checklist

When adding view transitions to an existing app:

1. **Audit** — find every `<Link>`/`router.push`, every `<Suspense>`, every persistent element, every shared visual element (thumbnails that expand, etc.)
2. **Add CSS** — timing variables, fade/slide keyframes, and a `prefers-reduced-motion` block
3. **Isolate persistent elements** — add `viewTransitionName` to headers, navbars, sidebars
4. **Add directional page transitions** — wrap each page component (not layout) with type-keyed `<ViewTransition>`
5. **Add Suspense reveals** — wrap fallback and content in matching `<ViewTransition enter/exit>`
6. **Add shared element transitions** — add matching named `<ViewTransition name={...}>` on source and target
7. **Verify** — walk every navigation path and confirm animations fire correctly

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| VT not activating | State update not inside `startTransition` | Wrap with `startTransition` |
| VT not activating | `<ViewTransition>` is not the first thing before DOM | Ensure `<ViewTransition>` comes before any DOM node |
| "Two ViewTransition components with the same name" | Non-unique name | Use IDs: `name={\`hero-${item.id}\`}` |
| `flushSync` skips animations | Incompatible with view transitions | Use `startTransition` instead |
| Only updates animate, no enter/exit | Missing `<Suspense>` — React treats swaps as updates | Wrap in `<Suspense>` or conditionally render the VT itself |
| Layout VT prevents page VTs | Nested VTs never fire enter/exit inside a parent | Remove the layout-level `<ViewTransition>` |
| List reorder not animating with `useOptimistic` | Optimistic values resolve before snapshot | Use committed state for list order |
| TS error "Property 'default' is missing" | Type-keyed objects require a `default` key | Add `default: 'none'` to every type map object |
| Backdrop-blur flickers | Old snapshot has backdrop-blur | Use the backdrop-blur workaround CSS above |
| `border-radius` lost during transitions | Not applied to captured element | Apply `border-radius` directly to the captured element |
| Skeleton controls slide away | Controls not matched between skeleton and content | Give both the same `viewTransitionName` |
| `router.back()` skips animation | `popstate` is synchronous, incompatible with VT | Use `router.push()` with explicit URL instead |
