# Voice Infrastructure Reference

Voice file structure, config/profile schemas, modes, and fix strategies.

---

## Voice File Structure

Each voice lives at `skills/voice-{name}/` and contains:

| File | Required | Purpose |
|------|----------|---------|
| `SKILL.md` | Yes | AI instructions, patterns, anti-patterns |
| `profile.json` | Yes | Quantitative metrics targets |
| `config.json` | Yes | Validation settings, modes, thresholds |
| `references/samples/` | No | Few-shot examples (load 1-2 if available) |

---

## profile.json Schema

The profile captures quantitative voice metrics:

```json
{
  "voice": "name",
  "metrics": {
    "avg_sentence_len": 15.3,
    "contraction_rate": 0.72,
    "short_sentence_ratio": 0.35
  },
  "preferred_transitions": ["so", "but", "and", "because"],
  "banned_phrases": ["delve into", "it's worth noting", "in conclusion"]
}
```

---

## config.json Schema

The config drives validation thresholds and available modes:

```json
{
  "thresholds": {
    "pass_score": 75,
    "error_max": 0,
    "warning_max": 3
  },
  "modes": ["default", "technical", "awards"],
  "direct_write": false
}
```

### Threshold Parsing (Phase 1)

Extract from `config.json`:
- `thresholds.pass_score` — minimum score to pass validation
- `thresholds.error_max` — maximum allowed errors (usually 0)
- `thresholds.warning_max` — maximum allowed warnings
- `modes` — list of available content modes

---

## Available Modes Per Voice

Modes are voice-specific and defined in each voice's `config.json`. Common examples:
- `default` — general-purpose content
- `technical` — systems explanations, how-it-works pieces
- `awards` — celebratory recognition pieces

Load the voice's `config.json` to see which modes are available.

---

## Fix Strategies for Phase 5 (REFINE)

Apply targeted fixes in this order (errors before warnings):

| Violation Type | Fix Strategy |
|----------------|-------------|
| Banned phrase | Remove or replace with the direct version of the phrase |
| Em-dash | Replace with comma, period, or restructure the sentence |
| Sentence rhythm | Break long sentences; vary short/medium/long distribution |
| Contraction rate too low | Replace "do not" → "don't", "it is" → "it's", etc. |
| Contraction rate too high | Expand contractions in more formal passages |
| Transition word mismatch | Replace with a transition from the profile's preferred list |

Key rule: fix one violation at a time. Do not rewrite entire sections — fix the specific issue only.

---

## Creating Missing Files

### If profile.json is missing

```bash
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples [writing-sample-files] \
  --output skills/voice-{name}/profile.json
```

When an indexed voice-calibration skill is installed, route to it through `/do`; otherwise, use the script above.

### If config.json is missing

Create a minimal config using the schema above. Use `pass_score: 75` as a starting default and add modes based on the voice's intended use cases.
