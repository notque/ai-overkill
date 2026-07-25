# Motion and Interaction States

<!-- Loaded by ui-design-engineer when task involves animation, motion, Framer Motion, interaction states, hover, focus, disabled, loading, active, or pressed -->

House rules for how much motion to ship and which states must exist. Framer Motion and CSS transition syntax are assumed known; what follows is the budget and the taste.

---

## The 2-to-3 Motion Rule (Three Slots Per Page)

Ship exactly two or three intentional motions per page. Each motion fills one slot:

- **Slot 1: ENTRANCE** — one hero entrance on load
- **Slot 2: SCROLL** — one scroll-linked effect (`useScroll` + `useTransform`)
- **Slot 3: INTERACTION** — one hover/focus/layout transition

**Why**: More than three motions compete for attention. Each additional animation dilutes the signal value of all others. The page feels "jumpy" rather than intentional.

**Why this matters**: When everything animates, nothing communicates. The brain uses motion as a signal for hierarchy and importance. Saturating the page with motion degrades every motion's signal value to zero.

**Preferred action**: Audit existing motion and remove any that isn't filling one of the three slots. Use `variants` with `staggerChildren` to coordinate list animations as a *single* entrance slot rather than N separate motions.

The three most common animation failures: ignoring `prefers-reduced-motion` (triggers vestibular disorders), shipping more than 3 animations per page (destroys hierarchy), and missing `AnimatePresence` for exit animations (element vanishes without transition).

```bash
# Files exceeding the motion budget
rg "motion\." --type tsx -c | awk -F: '$2 > 6'
# Hover animation with no focus counterpart
grep -rn "whileHover" --include="*.tsx" | grep "motion\.div\|motion\.span\|motion\.p"
```

## The 6-State Matrix

Every interactive element (buttons, links, inputs, toggles, cards-as-interactions, tabs, dropdowns) must implement all 6 states. A button with only default and hover is incomplete — users encounter disabled, loading, focused, and pressed states in normal workflows. Missing states create moments where the interface feels broken.

| State | Requirements |
|-------|-------------|
| Default | Clear affordance, correct position in visual hierarchy |
| Hover | Visible change beyond just cursor |
| Active/Pressed | Immediate feedback confirming the press registered |
| Disabled | Visually muted, interaction blocked, `aria-disabled="true"` |
| Focus | `:focus-visible` ring, 3:1 contrast, `outline-offset` |
| Loading | Progress indicator, interaction blocked, `aria-busy="true"` |

## Transition Timing Bounds

| Transition Type | Duration | Rationale |
|----------------|----------|-----------|
| Hover enter/exit | 0.15s - 0.3s | Fast enough to feel responsive, slow enough to see |
| Active/Pressed | 0.1s - 0.15s | Near-instant feedback confirms the press |
| Focus ring | Instant or 0.1s | Keyboard users need immediate visibility |
| Modal/drawer open | 0.3s - 0.5s | Complex layout changes need readable motion |
| Dropdown expand | 0.2s - 0.3s | Fast reveal with slight ease-out |
| Loading transition | 0.2s | Smooth swap between label and spinner |

Timing outside these bounds creates specific problems:
- Below 0.1s: motion is imperceptible, wasted rendering work
- Above 0.5s: interface feels sluggish, user wonders if the action registered

## The 5-Second Test

After implementing all states: can a first-time user identify the primary action within 5 seconds? Load the page, start a timer, and see if the primary CTA is obvious. If not, the visual hierarchy needs work — the primary action should be the most visually prominent interactive element through size, color weight, and position.

## Missing State Indicators

Symptoms that states are missing:

- User clicks a button and nothing visually happens for 200ms+ (missing active/loading)
- Tab key produces no visible indicator of current position (missing focus)
- Greyed-out element still responds to hover (disabled state incomplete)
- Button can be clicked twice during async operation (missing loading state)
- Touch device shows no press feedback (missing active state, relies on hover only)

**Detection:** Tab through the page to verify focus visibility. Toggle `:hover`, `:active`, `:focus-visible`, and `[disabled]` in DevTools to verify each state exists and looks intentional.

**Why this matters**: `whileHover` triggers on CSS `:hover`, not on keyboard focus. A card with hover animation but no `tabIndex` and no focus animation is inaccessible — keyboard users get no feedback and may not know the element is interactive.

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Exit animation doesn't run — element disappears instantly | `AnimatePresence` missing as ancestor | Wrap conditional `motion.*` element with `<AnimatePresence>` and add `key` prop |
| Animation runs in dev but skipped for some users | `prefers-reduced-motion: reduce` active | Add `useReducedMotion()` hook and set `duration: 0` / zero offsets when true |
| `staggerChildren` has no effect | Variants not propagated — child elements lack `variants` prop | Add matching `variants` prop to all child `motion.*` elements |
| Layout animation causes "jump" | `layout` prop on element with `position: absolute` children | Wrap absolute children in `motion.div` with `layout` or use `layoutId` instead |
| Animation works once, breaks on re-render | `key` not stable — component remounts every render | Ensure `key` on `AnimatePresence` children is stable (id, not array index) |
