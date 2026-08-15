# Local Background Removal

No paid APIs. No `remove.bg`, no cloud bg-removal services. Three local strategies, all run on the user's machine:

1. **Chroma key** (default; `--bg-mode chroma`) — pure Pillow + numpy. Two-pass despill-aware key against the magenta `#FF00FF` matte plus 1-pixel alpha dilation.
2. **Gray-tolerance** (`--bg-mode gray-tolerance`) — adapted from road-to-aew's production algorithm. Best when the backend paints a gray (#3a3a3a) background instead of honoring the magenta-bg prompt.
3. **rembg** (`--bg-mode rembg`, opt-in) — ONNX U^2-Net model (~200MB). Use only when neither chroma assumption holds.

The chroma key handles the spritesheet workflow because the skill controls the input (prompts for magenta bg, the canvas template paints magenta). The gray-tolerance algorithm is for backends like Gemini Nano Banana that ignore explicit color instructions and paint their own #3a3a3a default. rembg is the fallback for general bg removal when no chroma assumption is reliable.

## Mode selection at a glance

| Backend / scenario | Mode | Why |
|---|---|---|
| Codex CLI image_gen, magenta bg honored | `chroma` (default) | Generator paints true #FF00FF; despill chroma is fastest and cleanest. |
| Codex CLI but the "magenta bg" instruction was ignored | `gray-tolerance` (or `auto`) | Generator picked its own neutral gray; chroma key won't match. |
| Gemini Nano Banana / similar | `gray-tolerance` | road-to-aew has 87 production-clean PNGs with this approach. |
| User-supplied photo / non-game asset | `rembg` | No chroma assumption; ML segmentation handles arbitrary bg. |
| Batch with mixed outputs | `auto` | Tries chroma first; falls through to rembg when alpha coverage <30%. |

CLI selection lives at `sprite_process.py remove-bg` and `sprite_pipeline.py`:

```bash
# default — magenta chroma key with despill + alpha dilation
python3 sprite_process.py remove-bg input.png --output out.png

# gray-tolerance for Gemini-style output
python3 sprite_process.py remove-bg input.png --output out.png --bg-mode gray-tolerance

# tune
python3 sprite_process.py remove-bg input.png --output out.png \
    --bg-mode chroma \
    --chroma-threshold 30 \
    --pass2-threshold 90 \
    --despill-strength 0.5 \
    --alpha-dilate 1
```

## Chroma mode (default)

The skill prompts the backend to produce magenta (`#FF00FF`) backgrounds, then removes magenta in post in three steps: pass 1 tight, pass 2 despill-aware, dilation cleanup.

### Step 1: tight chroma match (pass 1)

```python
def chroma_pass1(
    img: Image.Image,
    chroma: tuple[int, int, int] = (255, 0, 255),
    threshold: int = 30,
) -> Image.Image:
    """Mask pixels within sum-of-abs-diff threshold of chroma."""
    arr = np.array(img.convert("RGBA"))
    rgb = arr[..., :3].astype(int)
    diff = np.abs(rgb - np.array(chroma)).sum(axis=-1)
    mask = diff <= threshold  # True = chroma pixel
    arr[mask, 3] = 0  # set alpha to 0
    return Image.fromarray(arr, "RGBA")
```

This catches solid-magenta backgrounds. It does NOT catch:

- Pixels that are not exactly magenta but are close (faint pink fringing, anti-aliased edges).
- Magenta that has been compressed by JPEG or downsampled.

### Step 2: despill-aware edge flood (pass 2)

```python
def chroma_pass2_edge_flood_despill(
    img: Image.Image,
    chroma: tuple[int, int, int] = (255, 0, 255),
    threshold: int = 90,                  # looser than pass 1
    despill_strength: float = 0.5,
) -> Image.Image:
    """Flood-fill from canvas edges; preserve off-color pixels (despill)."""
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    chroma_arr = np.array(chroma)
    despill_cutoff = 20 * despill_strength

    queue = deque()  # all 4 edges seeded
    while queue:
        y, x = queue.popleft()
        if visited[y, x] or not (0 <= y < h and 0 <= x < w):
            continue
        if arr[y, x, 3] == 0:
            visited[y, x] = True
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                queue.append((y + dy, x + dx))
            continue
        rgb = arr[y, x, :3].astype(int)
        diff = int(np.abs(rgb - chroma_arr).sum())
        if diff > threshold:
            continue
        # DESPILL: preserve a near-bg pixel if its RGB is "off-color".
        if despill_strength > 0 and arr[y, x, 3] > 128:
            r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
            color_balance = max(r, g, b) - min(r, g, b)
            if color_balance > despill_cutoff:
                visited[y, x] = True
                continue
        visited[y, x] = True
        arr[y, x, 3] = 0
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            queue.append((y + dy, x + dx))

    return Image.fromarray(arr, "RGBA")
```

#### Why despill?

Anti-aliased edges between magenta and the character produce semi-transparent pixels whose RGB has spilled toward magenta. Naively zeroing those pixels eats the character silhouette; preserving them lets the visible halo persist. Despill checks `max(r,g,b) - min(r,g,b)` — if the channel spread is large, the pixel is a saturated character color that happens to be near the bg threshold (saturated yellows, cyans, greens at the silhouette). Those get preserved. Truly desaturated near-magenta pixels (the fringe) get zeroed.

This lets us safely loosen pass-2 threshold from 60 to 90: the threshold is wider, so we catch more fringe, but despill prevents false positives on character art.

#### Tuning despill

| `despill_strength` | Behavior |
|---|---|
| 0.0 | Despill off. Pure threshold-based pass 2 (legacy behavior). |
| 0.3 | Conservative. Only saturated colors (`color_balance > 6`) protected. |
| **0.5 (default)** | Balanced. Protects most character art (`color_balance > 10`). |
| 1.0 | Aggressive preservation. Protects almost any colored pixel (`color_balance > 20`). |

Increase if pass 2 is biting into character; decrease if halo persists.

### Step 2.5: fire-pixel preservation through LANCZOS resample (`_preserve_fire_pixels`)

Sub-unity LANCZOS resample (typical 0.82x for fractional-pitch slicers) smears
anti-aliased fire boundary pixels into "warm but not fire" colors. Asset 27
(dragon flame breath on green torso) loses 25-35% of per-cell fire pixels even
when the slicer captured 100% of source content: `(R=255, G=80, B=20)` fire
averaged with `(R=80, G=180, B=60)` body becomes `(R=240, G=40, B=20)` — fails
the `G > 60` fire criterion and reads as "dark red".

`_preserve_fire_pixels` runs after LANCZOS, before despill. It is a **no-op
for non-fire assets**: zero source `_is_fire` matches exits the block.

**Algorithm:**

1. Build the source fire mask on the kept-content crop (`_is_fire(crop_arr)
   AND keep_mask`).
2. Resample mask via PIL **BOX filter**; threshold > 0 marks any target pixel
   whose source neighborhood had fire.
3. Sample source fire RGB via **MaxFilter(5) + NEAREST** so painted color
   carries the dominant local fire hue (median fallback for non-fire spread).
4. If painted count is below `fire_target_ratio × source_fire_count`
   (default 0.88), iteratively dilate the fire mask 4-connected into adjacent
   hot-looking target pixels (`R > 200`, `B < 80`, `alpha > 16`). Rescues
   deep-red shading LANCZOS pushed below `G > 60`.
5. Cap each ring's painted pixels at `target_count` for reproducibility.

**Why 0.88 not 1.0?** Downstream despill (`alpha_fade_magenta_fringe`,
`dilate_alpha_zero`, `kill_pink_fringe`) and the mass-centroid anchor trim a
few percent more. 0.88 overshoots the 95% `verify_pixel_preservation` gate.

**Result on asset 27.** Before: 73% per-cell fire ratio. After: 100%,
`verify_pixel_preservation` passes. Implementation: `sprite_slicing.py:216`
(`_preserve_fire_pixels`), triggered inside `slice_with_content_awareness`
when `preserve_fire=True` (default). Module per ADR-205 split.

### Step 3: interior-spill neutralization (`neutralize_interior_magenta_spill`)

The chroma + edge-flood + despill chain handles BACKGROUND magenta and
SILHOUETTE-EDGE fringe. It does NOT handle a third class of bleed:
**full-opacity pink-cast pixels INSIDE the silhouette**. The Codex
generator sometimes paints pink streaks into dark hair or shadow regions
(R high, G low, B moderate-to-high, alpha 255 because they're "real
character pixels"). Despill protects them because their per-pixel color
spread `max(R,G,B) - min(R,G,B)` is high.

Two-tier neutralization, with hue discrimination to protect costume
purple:

```python
def neutralize_interior_magenta_spill(arr):
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    alpha = arr[..., 3]
    # Tier A: near-pure magenta cast (R>=200, B>=200, G<=80)
    tier_a = (r >= 200) & (b >= 200) & (g <= 80) & ((r - g) > 120) & ((b - g) > 120) & (alpha == 255)
    # Tier B: moderate pink cast (catches diluted hair-spill the GIF
    # quantizer would dither into pink). B <= R*1.05 distinguishes pink
    # (B≈R) from purple (B>R*1.1) so manager-suit costume is preserved.
    tier_b = (
        (r >= 150) & (g <= 80) & (b >= 90)
        & ((r - g) > 90) & ((b - g) > 50)
        & (b * 100 <= r * 105)  # pink hue, NOT purple
        & (alpha == 255)
    )
    pink_inside = tier_a | tier_b
    # Pull R and B down to G (neutral hue, preserve brightness)
    arr[..., 0] = np.where(pink_inside, g, arr[..., 0])
    arr[..., 2] = np.where(pink_inside, g, arr[..., 2])
    return arr
```

#### Why two tiers?

Tier A catches `(250, 30, 200)`-class pixels — pure magenta streaks.
Tier B catches `(233, 56, 165)`-class pixels — diluted spill that survived
chroma despill because the model painted them as "almost-but-not-quite
pure magenta". Without Tier B, the diluted spill renders as visible pink
wisps inside dark hair on hand-painted styles (asset 16 in the live demo:
the luchadora's flowing black hair had pink streaks).

#### Why `B <= R*1.05`?

This is the costume-protection invariant. Pink/magenta pixels have
B ≈ R: pure (255, 0, 255) has B/R = 1.0; spill pixels typically have
B/R between 0.7 and 1.0. Purple pixels have B > R: a purple suit
highlight at (180, 80, 200) has B/R = 1.11. Without this clause, the
neutralizer would erase the manager-heel character's purple suit. The
1.05 ratio is the tightest threshold that catches all observed pink
spill while preserving all observed purple costume art.

### GIF format bleed at silhouette edges — root cause + matte-composite fix

Even when the RGBA source is squeaky clean (zero pink pixels per the
strict R>200&B>200&G<100 criterion), animated GIF output can still show
a pink halo at silhouette edges. Why:

1. GIF has **1-bit alpha** (transparent or opaque, no smooth edges).
2. GIF has **256-color indexed palette** built ADAPTIVELY from the input.

Anti-aliased silhouette pixels in the RGBA source are
mostly-transparent (alpha 50-180) and mostly-character-color, but with
subtle channel mixing from the original chroma key. When PIL builds an
adaptive palette across frames, those edge pixels — even after they're
flattened over a transparent matte — get rounded to a NEARBY palette
color. If the flattened pixel happens to be `(50, 30, 50)` (a dark plum,
because the matte was dark blue and the alpha was low), the palette
allocates a "dark plum" entry, and nearby pixels round to it, growing a
plum-tinted halo.

Two complementary fixes:

#### Fix 1 — matte-composite over neutral middle-gray BEFORE quantizing

```python
def matte_composite(img, matte=(40, 40, 40)):
    img = img.convert("RGBA")
    bg = Image.new("RGB", img.size, matte)
    bg.paste(img, (0, 0), img)
    return bg
```

A neutral middle-gray matte gives the quantizer no pink reference to
lock onto. Anti-aliased pixels blend to gray, the palette stays neutral,
and surviving GIF edges look like dark gray (visually neutral) instead
of pink.

Color choice matters:
- `(0, 0, 0)` pure black — too dark; shows hard edge against any non-
  pure-black page bg.
- `(40, 40, 40)` middle-dark gray — matches typical dark-theme page bgs
  closely while desaturating fringe. **Default.**
- `(64, 64, 64)` to `(80, 80, 80)` — fine if page bg matches.
- `(128, 128, 128)` mid-gray — desaturates aggressively but washes out
  silhouette against dark-theme pages.
- `(24, 26, 33)` blue-tinged gray — DON'T USE for fringe-prone art:
  blue mixes with magenta to dark plum, which the quantizer still sees
  as a pink-family color.

#### Fix 2 — emit animated WebP alongside GIF; prefer WebP in HTML

WebP has **8-bit alpha** (full smooth transparency) and lossless or
lossy compression that doesn't quantize colors to a 256-palette. The
silhouette stays clean. Modern browsers (Chrome 32+, Firefox 65+, Safari
14+, Edge 18+) autoplay animated WebP just like GIF.

```python
# After Phase H assembly, emit BOTH:
frames[0].save(
    output_dir / f"{name}.webp",
    save_all=True, append_images=frames[1:],
    duration=duration_ms, loop=0, format="WebP",
)
# (Then write the matte-composited GIF as a compatibility fallback.)
```

In HTML/Phaser/etc., prefer WebP via `<picture>` or by checking
`final.webp` existence and substituting the `<img src>`. GIF stays as
the long-tail-compatibility fallback for ancient browsers.

#### Combined effect, measured

On the live demo's portrait-loop assets (16-luchadora, 18-manager-heel),
the strict-criterion magenta-pixel count per cell dropped:

| Asset | Before fix (RGBA / GIF) | After fix (RGBA / GIF) | After WebP |
|---|---|---|---|
| 16-luchadora-loop | 224 / 309 | 9 / 0 | 0 |
| 18-manager-heel-loop | 169 / 131 | 559* / 1721* | 58 |

*Asset 18's "after" count includes intentional purple-suit costume
pixels that cross the strict criterion — the visual is clean. Assets 15
(veteran-indie) and 17 (giant-heel) were clean both before and after
(no hair-spill class to neutralize).

### Step 4: alpha-zero dilation

After pass 2, expand the alpha=0 region by 1 pixel (4-connected). This kills the residual halo that survives even pass-2 flood-fill on anti-aliased generator output.

```python
def dilate_alpha_zero(arr: np.ndarray, radius: int = 1) -> np.ndarray:
    alpha = arr[..., 3]
    mask = alpha == 0
    for _ in range(radius):
        shifted = np.zeros_like(mask)
        shifted[1:, :] |= mask[:-1, :]
        shifted[:-1, :] |= mask[1:, :]
        shifted[:, 1:] |= mask[:, :-1]
        shifted[:, :-1] |= mask[:, 1:]
        mask = mask | shifted
    arr[..., 3] = np.where(mask, 0, alpha)
    return arr
```

Pure numpy. No scipy. Radius=1 is enough for almost every case; radius=2 if the halo spans 2+ pixels (unusual; usually means upstream is wrong).

#### Tuning the dilation

| Radius | Use when |
|---|---|
| 0 | Disable. Use when the chroma key is already clean and you want pixel-perfect silhouettes. |
| **1 (default)** | Most generator output. Removes 1-pixel anti-aliased halo. |
| 2+ | Only if you can see a 2+ pixel halo after pass 2. Investigate the generator first. |

### Combined defaults

```bash
python3 sprite_process.py remove-bg input.png --output out.png \
    --chroma-threshold 30 \
    --pass2-threshold 90 \
    --despill-strength 0.5 \
    --alpha-dilate 1
```

These defaults are calibrated against the live demo (8 spritesheets, 200+ frames). Tune `pass2-threshold` first if you see halo or biting; tune `despill-strength` second; tune `alpha-dilate` last.

## Gray-tolerance mode

Adapted from `~/road-to-aew/scripts/generate_enemy_sprite.py` lines 1048-1128 (`remove_watermark` + `make_background_transparent`). The road-to-aew project has produced 87 clean transparent PNGs in production with this algorithm — it's earned its place as our secondary mode.

### The two-step algorithm

```python
BG_COLOR = (58, 58, 58)        # #3a3a3a — Gemini Nano Banana default bg
BG_TOLERANCE = 30              # per-channel abs-diff
WATERMARK_MARGIN = 40          # corner box size in pixels
WATERMARK_BRIGHTNESS = 180     # mean(R,G,B) > this = "bright" pixel

def remove_watermark_corners(img, bg_color, margin, brightness=180):
    """Step 1: paint bright corner pixels back to bg_color."""
    # The four corner boxes (margin x margin each) get scanned.
    # Any pixel with mean(R,G,B) > brightness gets repainted to bg_color.
    # This kills Gemini's "made by..." watermark BEFORE step 2 sees it.

def gray_tolerance_to_alpha(img, bg_color, tolerance):
    """Step 2: any pixel within ±tolerance of bg_color (per-channel) gets alpha=0."""
    arr = np.array(img.convert("RGBA"))
    rgb = arr[..., :3].astype(int)
    bg = np.array(bg_color, dtype=int)
    within = np.all(np.abs(rgb - bg) <= tolerance, axis=-1)
    arr[within, 3] = 0
    return Image.fromarray(arr, "RGBA")
```

Step 1 (watermark cleanup) only matters when the backend paints a watermark in a corner. For backends that don't, it's a cheap no-op.

Step 2 is a per-channel tolerance check. It's looser than chroma sum-of-abs-diff because Gemini's gray bg has more channel variance (compression / dithering). Per-channel `±30` is the sweet spot road-to-aew settled on after iteration.

The same alpha dilation step (radius=1) runs after step 2.

### Tuning gray-tolerance

| Parameter | Default | Adjust if |
|---|---|---|
| `--gray-bg R G B` | `58 58 58` | Backend paints a different gray (e.g. `64 64 64`). |
| `--gray-tolerance` | 30 | Halo persists → 40; biting into character → 20. |
| `--watermark-margin` | 40 | Watermark in larger corner area → 60. Set to 0 to skip step 1. |
| `--alpha-dilate` | 1 | Same tuning as chroma mode. |

### When to use which mode

```
Did the backend paint magenta as instructed?
├── YES → --bg-mode chroma (default)
├── NO, painted gray → --bg-mode gray-tolerance
└── NO, painted white/photo → --bg-mode rembg
```

The skill's `auto` mode handles the first uncertainty: chroma first, fall through to rembg if alpha coverage <30%. But auto does NOT try gray-tolerance — that's a deliberate user choice based on the backend.

## rembg (opt-in)

`rembg` is a Python package wrapping a pre-trained ONNX model that segments foreground from background without chroma assumptions. Useful when:

- The backend produced a non-magenta, non-gray background.
- The character has magenta in their actual design (showman archetype with magenta gear) AND the bg isn't gray either.
- General-purpose cleanup of arbitrary user-supplied images.

Install:

```bash
pip install rembg onnxruntime
```

The first call downloads the U^2-Net or BiRefNet model (~200MB) to `~/.u2net/`. After that, it runs locally.

Usage is gated by import — the skill never installs rembg silently.

## Performance

| Mode | 256x256 | 1024x1024 |
|------|---------|-----------|
| Magenta pass-1 only | ~30ms | ~500ms |
| Magenta pass-1+2 (despill) | ~80ms | ~1500ms |
| Magenta full (+ dilate) | ~85ms | ~1550ms |
| Gray-tolerance (numpy) | ~25ms | ~450ms |
| Gray-tolerance + dilate | ~30ms | ~500ms |
| rembg (CPU) | ~1500ms | ~12000ms |
| rembg (GPU via onnxruntime-gpu) | ~200ms | ~1200ms |

For a 16-frame walk cycle (256×256 each), magenta full takes ~1.4s; gray-tolerance ~0.5s; rembg ~24s on CPU. Default to chroma; opt into rembg only when chroma fails.

## Validation

After bg removal, the dominant corner color should be transparent:

```python
def validate_alpha(img: Image.Image) -> None:
    arr = np.array(img.convert("RGBA"))
    h, w = arr.shape[:2]
    corners = [arr[0, 0], arr[0, w-1], arr[h-1, 0], arr[h-1, w-1]]
    for color in corners:
        if color[3] != 0:
            warn(f"corner not transparent: alpha={color[3]}")
```

A non-transparent corner usually means the chroma threshold is too tight or the bg color was something other than magenta. With gray-tolerance mode, a non-transparent corner means the bg color guess (`#3a3a3a`) was wrong — try `--gray-bg 64 64 64` or measure the corner pixel directly.

## Supported local paths

The skill uses only these local paths:

- `remove.bg` API (`api.remove.bg/v1.0/removebg`)
- `removebg` Python package that wraps the above
- `clipdrop.co` API
- Any cloud service that takes an image URL and returns a no-bg image

The grep gate (`grep -rE 'remove\.bg|REMOVEBG|clipdrop' skills/game/game-sprite-pipeline/`) must return no matches.

## Acknowledgement

The gray-tolerance algorithm and watermark-corner cleanup are adapted from `~/road-to-aew/scripts/generate_enemy_sprite.py` (upstream road-to-aew project, 2025). That project produces 87 clean transparent enemy PNGs in production. The despill addition to pass 2 is original to this skill, calibrated against the live demo's anti-aliased Codex output.

<!-- no-pair-required: section header; pair lives in subsection -->
## Patterns to Detect and Fix

### Signal: Calling a cloud bg-removal service

**Detection**: `requests.post('https://api.remove.bg/v1.0/removebg', files={'image_file': open(path, 'rb')}, headers={'X-Api-Key': KEY})`.

**Why it matters**: A paid API call requires a key the user did not authorize. That breaks the local-first expectation and makes results depend on a third-party billing path.

**Preferred action**: Use chroma key (free, fast, deterministic) by default. Use rembg (free, local, slower) as an opt-in fallback. Keep cloud services out of a problem that is fundamentally pixel classification.

### Signal: Single-pass chroma with no edge flood

**Detection**: Just `arr[matches_chroma] = transparent` and shipping the output.

**Why it matters**: Anti-aliased edges between magenta and the character produce intermediate pink shades that miss the threshold. Those pixels survive and form a visible halo around the character.

**Preferred action**: Use a two-pass workflow with despill. Pass 1 catches solid magenta; pass 2 flood-fills from edges with a looser threshold and despill, then 1-pixel alpha dilation removes the residual halo. Pillow plus numpy is enough.

### Signal: Skipping despill on pass 2

**Detection**: Bumping pass-2 threshold above 60 without despill; output looks "eaten" and the silhouette has chunks missing where saturated colors lived.

**Why it matters**: A loose pass 2 catches everything in the wider band, including fully opaque saturated character pixels that happen to have a magenta-ish hue.

**Preferred action**: Keep despill at 0.5 minimum when pass-2 threshold is above 60. Despill checks `max(rgb) - min(rgb)` so saturated character pixels stay visible and fringe pixels can fall away.

### Signal: Skipping alpha dilation on a "clean" output

**Detection**: A clean-looking pass 2 result ships, and downstream consumers report a faint 1-pixel halo at the silhouette.

**Why it matters**: Chroma thresholds are calibrated against direct color, but anti-aliased pixels with low alpha can still show up against light backgrounds.

**Preferred action**: Ship `--alpha-dilate 1` by default. Set it to 0 only when pixel-perfect silhouettes are required by tooling that performs its own anti-aliasing.

## Reference loading hint

Load when:
- Phase B or Phase E (bg removal) is active
- Output has visible magenta halos
- Choosing between `--bg-mode chroma` and `--bg-mode gray-tolerance`
- Considering rembg for difficult subjects
- Investigating a paid-API leakage finding (the grep gate flagged something)
