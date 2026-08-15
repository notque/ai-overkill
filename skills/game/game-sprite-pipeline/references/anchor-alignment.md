# Anchor Alignment

Phase F of the spritesheet pipeline. Per-frame normalization: shared-scale rescale + anchor alignment. Without this, walk-cycle frames have wildly different character heights and the character's feet bounce vertically as the animation plays.

## Anchor modes

The skill exposes anchor strategies via `--anchor-mode`. v8 introduced
`mass-centroid` as the default for spritesheets and portrait-loops; the
older `ground-line` mode is kept for backward compatibility.

| Mode | Default? | Behavior | Use when |
|---|---|---|---|
| `mass-centroid` | Yes (sheets, loops) | Translate each frame so its alpha-mass centroid lands at a globally-stable Y. The centroid integrates over ALL opaque pixels, so limb extensions don't dominate. Eliminates the "trunk hops up when bbox-bottom is a fist" failure. | Mixed grounded/aerial poses, idle loops, action cycles. The default since v8. |
| `ground-line` | Legacy | Detect a globally-stable ground-Y across all frames; translate each frame so its alpha-bbox-bottom lands AT that Y. | Backward compat. The bbox-bottom-Y is dominated by extended limbs (mic, raised arm), causing the "hop" failure on action cycles. |
| `per-frame-bottom` (alias: `bottom`) | Legacy | Translate so each frame's OWN alpha-bbox-bottom lands at `cell_h - bottom_margin`. Drift increases with bbox-height variance. | Pure same-pose loops where every frame's bottom truly is the feet (idle breathing where the silhouette barely changes). |
| `center` | Opt-in | Vertically center the frame on the canvas. | Genuinely off-ground sequences (jump-loop, fly, falling-loop). |
| `auto` | Legacy fallback | `bottom` when `height/width > 1.2` else `center`. Per-frame heuristic. | Compatibility only; superseded by `mass-centroid`. |

## v8 mass-centroid anchor (the new default)

The bbox-bottom-anchor approach (ground-line) had a residual failure mode:
when every frame's bbox-bottom is artificially identical (because the
ground-line translator forced it there), the **trunk** position varied by
the difference between the bbox-bottom and the body's actual mass center.
For action frames where the bbox-bottom is a fist or extended leg, the
trunk floats up by 30-50 pixels relative to the rest pose — the user's
"hop" complaint on assets 05 (powerhouse) and 23 (manager megaphone).

Mass centroid fixes this by anchoring on the quantity people actually
notice. The mass centroid Y is the alpha-weighted mean of all opaque pixel
Y coordinates: it represents "where the body is on average". A single
extended limb adds at most a few percent to the centroid — never the 30-50
pixel shift bbox-bottom suffers.

Concrete metrics from the live demo (author's local validation harness,
replace before use: `<your-output-dir>/assets/05-nes-powerhouse-attack`),
16 frames at 256x256 cells, after the ground-line fix landed:

| Metric | bbox-bottom anchor | mass-centroid anchor |
|---|---|---|
| bbox-bottom-Y stddev | 0px (anchor pinned) | 0-2px |
| centroid-Y stddev | **15.84px** (the visible hop) | **<2px** (drift-free) |
| Visible trunk drift across 16 frames | 30+ pixels on 3 lunge frames | None |

The new gate `verify_anchor_consistency` enforces a centroid-Y stddev
below 8px (4px for portrait-loops). It catches the hop class of failure
that the bbox-bottom verifier missed.

## The drift bug (what `ground-line` fixes)

Per-frame bottom-anchor produces visible vertical drift on extreme-pose animations. The lunge frame of an attack cycle has its character's bbox-bottom at the extended fist or trailing leg — NOT the feet. Pinning that bottom to the cell bottom puts the FIST at the ground-line and the feet float somewhere above.

Concrete example from the live demo (author's local validation harness, replace before use: `<your-output-dir>/assets/05-nes-powerhouse-attack`):

| Stat | Per-frame bottom-anchor | Global ground-line |
|---|---|---|
| bbox-bottom-Y stddev across 64 frames | 22.5 px | 0.0 px |
| bbox-bottom-Y range | 74 px | 0 px |
| Visual symptom | Character bounces vertically by ~half the cell | Feet planted; only the silhouette above changes |

A 74-pixel bounce on a 128-pixel cell is more than half the cell height. The feet were never the bbox-bottom for some lunge frames; per-frame anchor put the wrong body part on the ground.

## The two operations

### 1. Shared-scale rescale

After Phase D, each frame is cropped to its own bounding box. Bounding-box heights vary because the character's silhouette differs per pose (arms up = taller, crouched = shorter). Walk cycles need consistent character height across frames.

```python
import statistics

def shared_scale(frames: list[Image.Image], target_percentile: float = 95) -> int:
    heights = [f.height for f in frames]
    target_height = int(statistics.quantiles(heights, n=100)[int(target_percentile) - 1])
    return target_height

def rescale_to_height(frame: Image.Image, target_height: int) -> Image.Image:
    aspect = frame.width / frame.height
    new_width = int(target_height * aspect)
    return frame.resize((new_width, target_height), Image.LANCZOS)
```

Why the 95th percentile (not the median or max):

- Median: a single tall frame (jumping pose) skews short; arms-up frames get scaled down and look small.
- Max: a single accidental tall component (artifact glow) inflates everything else.
- 95th: robust to a single outlier, captures "near-tallest legitimate frame" as the canonical height.

`--scale-percentile` flag exposes this; default is 95.

### 2. Ground-line anchor (default; the new path)

After rescale, run a single batch-scope detection step BEFORE pasting any frame to the cell canvas:

```python
def detect_ground_line(
    frames: list[Image.Image],
    cell_h: int,
    bottom_zone_pct: float = 0.30,
    fallback_percentile: float = 75.0,
) -> int:
    """Return the cell-Y where 'feet' typically sit across the animation.

    Algorithm:
      1. For each frame, find the alpha-bbox bottom-Y (pre-cell-staging).
      2. Take the median of bottom-Ys whose value falls in the lower
         `bottom_zone_pct` of the cell (default lower 30%) — these are
         the feet-on-ground reference frames.
      3. If NO frame's bottom is in the lower zone (every frame aerial),
         fall back to the 75th percentile of all bottoms.

    The median (not max, not mean) is robust to one-pixel jitter from AA
    or chroma fringing on individual frames.
    """
```

Then for each frame:

```python
def apply_ground_line_anchor(
    frame: Image.Image,
    ground_line_y: int,
    cell_w: int,
    cell_h: int,
    horizontal_mode: str = "centroid",
) -> Image.Image:
    """Translate so the frame's alpha-bbox-bottom lands at ground_line_y."""
```

Per-frame translation moves the CHARACTER (not the FRAME) so its lowest pixel matches the global ground line. Frames where the lowest pixel is the feet get correctly grounded; frames where the lowest pixel is an extended fist still align that fist with the ground line — but because the FEET frames are the median, every grounded frame is consistent and the aerial frames LOOK aerial relative to that ground.

#### Bottom-zone heuristic

Why "lower 30% of the cell"? Because grounded frames almost always have their bbox-bottom in the lower portion of the cell (the model places the feet near the bottom). Frames whose bbox-bottom is HIGH in the cell are aerial (jumping, leaping) and shouldn't influence the ground line. The 30% threshold is empirical: it captures grounded frames reliably without folding in mid-leap frames.

#### Horizontal centering

`apply_ground_line_anchor(horizontal_mode="centroid")` centers the alpha-mass centroid horizontally rather than the bbox center. For a lunge frame where the bbox extends right but the body's center of mass is still vertical-axis-aligned, centroid-mode keeps the silhouette grounded; bbox-mode would shift the whole frame left.

### 3. Per-frame bottom-anchor (legacy)

Kept for backward compat and same-pose loops:

```python
def find_bottom_anchor(frame: Image.Image) -> int:
    """Y-coordinate of lowest non-transparent pixel within `frame`."""
    arr = np.array(frame)
    alpha = arr[..., 3]
    has_pixel = alpha.max(axis=1) > 0
    nonzero_rows = np.where(has_pixel)[0]
    if len(nonzero_rows) == 0:
        return frame.height
    return int(nonzero_rows.max())

def anchor_to_canvas(frame, canvas_w, canvas_h, bottom_margin=8):
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    bottom = find_bottom_anchor(frame)
    paste_y = (canvas_h - bottom_margin) - bottom
    paste_x = (canvas_w - frame.width) // 2
    canvas.paste(frame, (paste_x, paste_y), frame)
    return canvas
```

This is fine when every frame's bbox-bottom is the feet. It is NOT fine when one frame's bbox-bottom is a fist or a foot extended beyond the standing-foot Y (lunge, kick).

## Frame-relative anchor data

The metadata JSON written by Phase F includes per-frame anchor coordinates and the global ground-line Y:

```json
{
  "scale_percentile": 95,
  "target_height": 244,
  "cell_size": [256, 256],
  "anchor_mode": "ground-line",
  "ground_line_y": 248,
  "frames": [
    {"name": "knight_frame_00.png", "anchor_y": 248, "scaled_to": [228, 244]},
    {"name": "knight_frame_01.png", "anchor_y": 248, "scaled_to": [242, 236]}
  ]
}
```

Phaser texture-atlas JSON consumes the `anchor_y` for `setOrigin(0.5, anchor_y/cell_h)` calls in game code.

## Failure modes

### Per-frame bottom on extreme-pose sheets — VISIBLE DRIFT

Symptom: the character's feet bounce vertically as the animation plays. Stddev of `bbox-bottom-Y` across frames > 5 px on output.

Cause: `--anchor-mode bottom` (or `per-frame-bottom`) treats whatever pixel is lowest in each frame as "the foot" — but on attack/lunge/aerial frames, that pixel is a fist or extended limb.

Fix: switch to `--anchor-mode ground-line` (the default since Apr 2026). Reprocess. Verify `bbox-bottom-Y` stddev → ~0.

### Ground-line on pure-aerial sequences

Symptom: the entire animation looks too low in the cell — the character is flying, but the renderer planted them at a low ground line.

Cause: `detect_ground_line` couldn't find any feet-on-ground frames (every frame is aerial), so it fell back to the 75th percentile of all bottoms. This produces a ground line near the bbox-bottom of the LOWEST aerial pose, which may be visually too low.

Fix: pass `--anchor-mode center` for genuinely-airborne sequences (jump-loop, falling-loop). Ground-line is the default for mixed sequences only.

### All-transparent frame

A frame with no non-transparent pixels (rare; usually a Phase D failure). `detect_ground_line` skips frames whose alpha-bbox is None. If ALL frames are empty, the function returns `cell_h - bottom_margin` as a sane default. Surfaced as a warning:

```
WARNING: frame_03 has no non-transparent pixels; check frame extraction
```

The pipeline does not abort — the output sheet has an empty cell, but downstream consumers handle it.

### Wide character (boss / giant)

`giant` archetype has a 1.2x scale modifier. After Phase F, its bbox is wider than other frames. Horizontal centering (centroid mode) still works; downstream renderers should not assume uniform width. The atlas JSON records per-frame width.

## Tuning parameters

| Parameter | Default | Adjust if |
|-----------|---------|-----------|
| `--anchor-mode` | `ground-line` | Pure same-pose loop where bbox-bottom IS the feet → `per-frame-bottom`. Pure aerial → `center`. |
| `--scale-percentile` | 95 | Median (50) for groups of similar-pose frames; Max (100) for single-pose sheets |
| `--bottom-margin` | 8 px | Larger if feet should sit higher in the cell; 0 for feet-at-edge |

## Output

Per-frame normalized PNGs at `<output-dir>/<name>_frame_NN.png`. Each is exactly `cell_w × cell_h` pixels. Plus a metadata JSON with per-frame bbox, anchor, and scale info.

## Validation

After Phase F:

```python
def validate_normalization(frames: list[Image.Image], cell_w: int, cell_h: int):
    bottoms = []
    for i, f in enumerate(frames):
        if (f.width, f.height) != (cell_w, cell_h):
            raise NormalizationError(f"frame {i} is {f.size}, expected ({cell_w}, {cell_h})")
        anchor = find_bottom_anchor(f)
        bottoms.append(anchor)
        if anchor < cell_h * 0.5:
            warn(f"frame {i} anchor at y={anchor} (canvas height {cell_h}) — sprite floats high")
    # Drift check (only meaningful for ground-line mode):
    spread = max(bottoms) - min(bottoms)
    if spread > 5:
        warn(f"bbox-bottom-Y spread = {spread}px — anchor drift detected; check --anchor-mode")
```

The skill emits warnings for frames whose anchor is in the upper half (sprite "floating") because this often indicates a Phase D extraction error rather than a legitimate aerial pose. It also warns on bottom-Y spread > 5px under ground-line mode (post-fix the spread should be 0).

## Why ground-line as the default

Walk-cycle and idle animations have the character's feet planted on the ground. If frames are center-anchored, the head bobs up and down as the bbox height varies. If frames are per-frame-bottom-anchored, attack/lunge frames pin the wrong body part.

Ground-line anchor pins the GLOBAL FEET POSITION (the median across grounded frames), so:
- Walk-cycle: feet always at ground-line Y. Head bobs only when the actual silhouette changes height.
- Attack-cycle: standing frames have feet at ground-line; lunge/kick frames have the lowest body point at ground-line, but the body's CENTER OF MASS still hangs naturally.
- Idle: ~zero motion; ground-line and per-frame-bottom converge.

For animations where the character is genuinely off-ground for the entire sequence (jumping, flying, falling), `--anchor-mode center` produces the right look. The default is `ground-line` because most game animations are mixed-state and the legacy per-frame-bottom drift was the most-reported regression.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anchor Patterns to Detect and Fix

### Anchor Patterns to Detect and Fix: Per-frame bottom-anchor on extreme-pose animations

**Signal:** Default `--anchor-mode bottom` on an attack/jump/aerial cycle. Each frame's lowest pixel pinned to the cell bottom.

**Why it matters:** The lowest pixel of a lunge frame is the extended fist or trailing leg — not the feet. Pinning that to the ground-Y puts the wrong body part on the floor. Across the cycle the character bounces vertically by tens of pixels (live demo evidence: 74-px range on a 128-px cell, see `<your-output-dir>/screenshots/05-drift-evidence/`).

**Preferred action**: Use `--anchor-mode ground-line` (default since Apr 2026). The detector picks a single global ground-Y from the grounded frames and pins each frame's lowest pixel to THAT Y. Result: standing-frame feet are correct AND lunge frames look correct because their lowest reach (fist) is consistent with where standing-frame feet sit.

### Anchor Patterns to Detect and Fix: Center-anchoring all frames regardless of action

**Signal:** Always centering frames vertically, regardless of whether the character is grounded or aerial.

**Why it matters:** Walk-cycle feet bounce because center-anchored frames with different bbox heights produce different ground-Y. Animation looks broken even if individual frames are well-rendered.

**Preferred action**: `ground-line` for mixed sequences (default). `center` only when the entire sequence is genuinely off-ground.

### Anchor Patterns to Detect and Fix: Skipping shared-scale and trusting per-frame bbox sizes

**Signal:** Outputting frames at their natural bbox dimensions without rescaling to a shared height.

**Why it matters:** Walk-cycle frames have arms in different positions; their bboxes have different heights. Without shared-scale, the character's apparent height changes frame-to-frame even though the actual character is the same size.

**Preferred action**: Compute the 95th-percentile height across all frames and rescale every frame's height to that target, preserving per-frame aspect. Width varies (arms out vs arms in), but height stays constant.

## Reference loading hint

Load when:
- Spritesheet Phase F (normalization) is active
- Output frames have inconsistent character size or bouncing feet
- Phaser atlas integration needs anchor data
- Adding a new anchor mode or tuning the ground-line detector
