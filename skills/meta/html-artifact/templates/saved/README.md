# Saved templates — named, frozen HTML layouts

A named starting layout the builder clones and fills, instead of regenerating
structure from scratch. One skill, many template files: add a layout here to
grow the gallery — never add a skill per template.

## How a saved template works

Each entry is two files sharing a base name:

| File | Role |
|---|---|
| `<name>.html` | Frozen layout. Content slots are `{{SLOT_NAME}}` markers. |
| `<name>.slots.json` | Slot manifest: each slot's name, whether it is required, and a one-line description. |

The layout (CSS, structure, chrome) is fixed. Only slot text changes.

## Fill a template (deterministic)

```
python3 skills/meta/html-artifact/scripts/fill-template.py \
  --template business-review \
  --slots slots.json \
  --out artifact.html
```

`slots.json` maps slot names to HTML/text values. The script:

- Refuses if a required slot is missing (exit 1).
- Refuses if a provided slot name is not declared in the manifest (exit 1) — no silent typos.
- Substitutes every declared slot, then verifies no `{{...}}` markers remain (exit 1).
- Never edits layout, CSS, or chrome. Content-vs-layout authority is enforced by the script, not by prompt discipline.

## Gallery

| Template | Shape | Use |
|---|---|---|
| `business-review` | report | Performance/KPI review with segments, decisions, outlook |
| `system-design` | report | Architecture doc: requirements, components, data flow, tradeoffs |
| `github-issues` | data-viz | Rendered GitHub issue set (pre-existing) |

## Add a template

1. Author `<name>.html` in the Birchline design system, marking content spots with `{{SLOT}}`.
2. Author `<name>.slots.json` declaring every slot.
3. Run `fill-template.py --template <name> --slots <sample>.json --out /tmp/check.html` and confirm no markers remain.
4. Add a row to the gallery table above.
