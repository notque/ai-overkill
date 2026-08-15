# fal.ai Image Generation

fal.ai provides queue-based image generation via 8 model endpoints. Requires `FAL_KEY` in `~/.env`. Auth header format is `Key $FAL_KEY` — not Bearer.

---

## Authentication

```bash
# Correct format
curl -H "Authorization: Key $FAL_KEY" https://queue.fal.run/...

# Wrong — this returns 401
# -H "Authorization: Bearer $FAL_KEY"
```

Get `FAL_KEY` at fal.ai. Add to `~/.env`.

---

## Model Endpoints

| Model | Endpoint | Best for | Speed |
|-------|----------|----------|-------|
| GPT Image 1.5 | `fal-ai/gpt-image-1` | Transparency, complex prompts, instruction-following | Slow (~30s) |
| Nano Banana 2 | `fal-ai/nano-banana-2` | Speed, game sprites, icons | Fast (~5s) |
| Nano Banana Pro | `fal-ai/nano-banana-pro` | Better quality than Nano 2, still fast | Medium (~12s) |
| Grok Imagine (XAI) | `fal-ai/grok-imagine` | Photorealism, characters | Medium (~15s) |
| Flux Schnell | `fal-ai/flux/schnell` | General purpose, fast | Fast (~4s) |
| Flux Dev | `fal-ai/flux/dev` | Higher quality Flux | Medium (~20s) |
| Stable Diffusion XL | `fal-ai/stable-diffusion-xl` | SDXL default | Medium (~15s) |
| Ideogram v2 | `fal-ai/ideogram/v2` | Text in images, logos, typography | Slow (~25s) |

**Selection guide**:
- Transparency needed (sprite, icon, UI element): **GPT Image 1.5** — only model that reliably outputs PNG with alpha
- Maximum speed (prototype iteration): **Nano Banana 2**
- Chroma-key workflow: **Nano Banana 2** with `#00FF00` background prompt
- Text in image: **Ideogram v2**
- Photorealistic character: **Grok Imagine**

---

## Queue-Based API

All fal.ai endpoints use a queue. Submit a job, poll for result.

### Step 1: Submit to Queue

```bash
curl -X POST https://queue.fal.run/fal-ai/nano-banana-2 \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "pixel art warrior character, game sprite, transparent background, 64x64",
    "image_size": "square",
    "num_images": 1
  }'

# Response:
# {
#   "request_id": "req-abc123",
#   "status": "IN_QUEUE",
#   "queue_position": 0,
#   "response_url": "https://queue.fal.run/fal-ai/nano-banana-2/requests/req-abc123"
# }
```

### Step 2: Poll for Result

```bash
curl -H "Authorization: Key $FAL_KEY" \
  https://queue.fal.run/fal-ai/nano-banana-2/requests/REQ_ID

# When complete:
# {
#   "status": "COMPLETED",
#   "output": {
#     "images": [{"url": "https://fal.media/...", "width": 1024, "height": 1024}]
#   },
#   "metrics": {"inference_time": 4.2}
# }
```

### Step 3: Download

```bash
curl -o output.png "$(RESULT_URL_FROM_ABOVE)"
```

### Full Script (use `scripts/fal_queue_image_run.py`)

```bash
python3 scripts/fal_queue_image_run.py \
  --model fal-ai/nano-banana-2 \
  --prompt "pixel art warrior, game sprite, green background #00FF00" \
  --output public/assets/warrior-sprite.png \
  --size square
```

---

## Chroma-Key Workflow (Sprite Transparency)

When the model doesn't support native transparency, use a chroma-key green background then remove it in post.

### Step 1: Generate with Green Background

```bash
python3 scripts/fal_queue_image_run.py \
  --model fal-ai/nano-banana-2 \
  --prompt "pixel art warrior, game sprite, #00FF00 green background, no shadow, flat lighting" \
  --output /tmp/warrior-chroma.png \
  --size square
```

**Key prompt additions for clean chroma-key**:
- `"#00FF00 green background"` or `"solid lime green background"`
- `"no shadow"` (shadows bleed into the background, making removal imprecise)
- `"flat lighting"` (prevents green light spill on the character)

### Step 2: Remove Green Background

```python
from PIL import Image
import numpy as np

def remove_chroma_key(input_path: str, output_path: str, tolerance: int = 50) -> None:
    """Remove #00FF00 chroma-key background, output PNG with alpha."""
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)

    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    # Target: R < 100, G > 200, B < 100 (pure green range)
    mask = (r < tolerance) & (g > (255 - tolerance)) & (b < tolerance)
    data[mask] = [0, 0, 0, 0]  # Set to transparent

    Image.fromarray(data).save(output_path, "PNG")

remove_chroma_key("/tmp/warrior-chroma.png", "public/assets/warrior-sprite.png")
```

Requires: `pip install Pillow numpy`

---

## GPT Image 1.5 — Best for Transparency

GPT Image 1.5 supports native transparency via prompt instruction. No chroma-key removal needed.

```bash
curl -X POST https://queue.fal.run/fal-ai/gpt-image-1 \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "pixel art warrior character, game sprite, transparent background, isolated subject, PNG format",
    "image_size": "1024x1024",
    "quality": "standard",
    "style": "vivid"
  }'
```

**GPT Image 1.5-specific parameters**:
- `quality`: `"standard"` or `"hd"` (hd costs more, slower)
- `style`: `"vivid"` (saturated, dramatic) or `"natural"` (realistic)
- `background`: `"transparent"` — explicit parameter to request PNG alpha (check current API docs)

---

## Common Parameters

Different models support different parameters. These are widely supported:

| Parameter | Values | Notes |
|-----------|--------|-------|
| `image_size` | `"square"`, `"landscape_4_3"`, `"portrait_16_9"`, `"1024x1024"` | Use `"square"` for sprites/icons |
| `num_images` | 1-4 | Most models: 1-4, some support up to 8 |
| `num_inference_steps` | 1-50 | Higher = better quality + slower. Default varies by model |
| `seed` | integer | Set for reproducibility |
| `negative_prompt` | string | What to avoid in the image |

---

## Cost Tracking

fal.ai includes billing info in response headers:

```bash
curl -v -H "Authorization: Key $FAL_KEY" \
  https://queue.fal.run/fal-ai/nano-banana-2/requests/REQ_ID 2>&1 \
  | grep -i "x-fal-"
# x-fal-billing-units: 1
# x-fal-credits-used: 0.003
```

`scripts/fal_queue_image_run.py` logs these automatically. Nano Banana 2 is cheapest (~$0.002/image). GPT Image 1.5 is most expensive (~$0.08/image hd).

---

## .meta.json Sidecar

```json
{
  "prompt": "pixel art warrior character, game sprite, transparent background",
  "model": "fal-ai/gpt-image-1",
  "request_id": "req-abc123",
  "image_size": "1024x1024",
  "generated_at": "2026-04-04T12:00:00Z",
  "source": "fal-ai",
  "output_path": "public/assets/warrior-sprite.png",
  "credits_used": 0.08,
  "seed": 42
}
```

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Wrong auth format | Use `Key $FAL_KEY` not `Bearer $FAL_KEY` |
| 403 Forbidden | Invalid key | Regenerate at fal.ai |
| status: "FAILED", error: "content policy" | Prompt violates content policy | Rephrase prompt, remove violence/NSFW |
| status: "FAILED", error: "unsupported parameter" | Parameter not supported by this model | Check model docs, remove unsupported param |
| Green fringe after chroma removal | Tolerance too low | Increase `tolerance` from 50 to 80 in chroma removal |
| Transparent areas inside character | Tolerance too high | Decrease `tolerance` to 30 |
| Long wait (>60s for Nano Banana 2) | Queue congestion | Normal — fal.ai queues; poll every 3s |
