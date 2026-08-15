# PPTX Conversion Reference

> **Scope**: python-pptx extraction patterns for the PPTX-to-HTML conversion path — text, notes, images, shapes, and failure modes.
> **Version range**: python-pptx 0.6.21+ (pip install python-pptx). Python 3.8+.
> **Generated**: 2026-04-17

---

## Overview

PPTX conversion uses `python-pptx` to extract slide content before building the HTML deck. The most common failure modes are (1) silently skipping slides that use grouped or embedded OLE shapes, and (2) losing slide notes because `text_frame` is checked on the wrong object. Always extract text, notes, and image references in a single pass and validate the slide count before proceeding.

---

## Pattern Table

| Task | API | Notes |
|------|-----|-------|
| Open presentation | `prs = Presentation(path)` | Raises `PackageNotFoundError` on corrupt/missing file |
| Iterate slides | `for slide in prs.slides` | `prs.slides` is 0-indexed |
| Slide dimensions | `prs.slide_width`, `prs.slide_height` | In EMUs; divide by 914400 for inches |
| Slide notes | `slide.notes_slide.notes_text_frame.text` | Raises `AttributeError` if no notes — always guard |
| Shape text | `shape.text_frame.text` | Only on shapes where `shape.has_text_frame` is True |
| Placeholder text | `shape.placeholder_format` | Check `ph_idx` for title (0), body (1) |
| Images | `shape.image.blob`, `shape.image.ext` | Only when `shape.shape_type == MSO_SHAPE_TYPE.PICTURE` |
| Tables | `shape.table.rows[i].cells[j].text_frame.text` | Only when `shape.has_table` |

---

## Correct Patterns

### Safe slide extraction loop

```python
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
import base64

def extract_slides(pptx_path: str) -> list[dict]:
    prs = Presentation(pptx_path)
    results = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        slide_data = {
            'number': slide_num,
            'title': '',
            'body': [],
            'notes': '',
            'images': [],
        }

        for shape in slide.shapes:
            # Title placeholder (ph_idx == 0)
            if shape.has_text_frame:
                ph = shape.placeholder_format
                if ph is not None and ph.idx == 0:
                    slide_data['title'] = shape.text_frame.text.strip()
                elif ph is not None and ph.idx == 1:
                    # Body placeholder — collect non-empty paragraphs
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            slide_data['body'].append(text)
                elif ph is None:
                    # Freestanding text box
                    text = shape.text_frame.text.strip()
                    if text:
                        slide_data['body'].append(text)

            # Images
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                img_blob = shape.image.blob
                img_ext = shape.image.ext
                img_b64 = base64.b64encode(img_blob).decode('utf-8')
                slide_data['images'].append({
                    'ext': img_ext,
                    'data_uri': f'data:image/{img_ext};base64,{img_b64}',
                })

        # Speaker notes — guard AttributeError for slides with no notes
        try:
            notes_tf = slide.notes_slide.notes_text_frame
            slide_data['notes'] = notes_tf.text.strip()
        except AttributeError:
            pass

        results.append(slide_data)

    return results
```

**Why**: `shape.has_text_frame` must be checked before accessing `.text_frame` — not all shapes have one. Notes access via `notes_slide` raises `AttributeError` on slides where no notes placeholder exists; the try/except is mandatory, not defensive.

---

### Dependency check with clear error

```python
def check_python_pptx() -> None:
    try:
        import pptx  # noqa: F401
    except ImportError:
        print("Error: python-pptx is not installed.")
        print("Install it with: pip install python-pptx")
        print("Or provide slide content manually.")
        raise SystemExit(1)
```

**Why**: Silent import failure causes an `AttributeError` or `NameError` later in the extraction, not a clear message. Always check the import upfront with actionable instructions.

---

### Slide count validation

```python
def validate_extraction(slides: list[dict], pptx_path: str) -> None:
    from pptx import Presentation
    expected = len(Presentation(pptx_path).slides)
    if len(slides) != expected:
        print(f"Warning: extracted {len(slides)} slides but PPTX has {expected}.")
        print("Grouped shapes or embedded OLE objects may have been skipped.")
```

**Why**: Grouped shapes (MSO_SHAPE_TYPE.GROUP) and OLE objects (MSO_SHAPE_TYPE.OLE_OBJECT) are common in slides built from templates. The loop silently skips them — a count mismatch is the only signal that content was lost.

---

## Pattern Catalog

### Guard text_frame Access with has_text_frame

**Detection**:
```bash
grep -n '\.text_frame' convert.py | grep -v 'has_text_frame'
rg 'shape\.text_frame' --type py | grep -v 'has_text_frame'
```

**Signal**:
```python
for shape in slide.shapes:
    text = shape.text_frame.text  # AttributeError on Picture, Table, GroupShape
```

**Why this matters**: `AttributeError: 'Picture' object has no attribute 'text_frame'` on the first slide with an image. Extraction aborts with no output.

**Do instead:** Guard every `text_frame` access with `shape.has_text_frame`:

```python
for shape in slide.shapes:
    if shape.has_text_frame:
        text = shape.text_frame.text
```

---

### Wrap Notes Access in try/except AttributeError

**Detection**:
```bash
grep -n 'notes_slide' convert.py | grep -v 'try\|except\|AttributeError'
rg 'notes_text_frame' --type py | grep -v 'try\|except'
```

**Signal**:
```python
notes = slide.notes_slide.notes_text_frame.text
```

**Why this matters**: Raises `AttributeError: 'NoneType' object has no attribute 'notes_text_frame'` on slides with no notes. PPTX files created from blank templates frequently have no notes placeholder on every slide.

**Do instead:** Wrap notes access in a `try/except AttributeError` block:

```python
try:
    notes = slide.notes_slide.notes_text_frame.text.strip()
except AttributeError:
    notes = ''
```

---

### Embed Images as Base64 Data URIs

**Detection**:
```bash
grep -n 'open.*wb\|\.write(img' convert.py
rg 'image\.blob.*open|with open.*image' --type py
```

**Signal**:
```python
with open(f'slide_{i}_img.png', 'wb') as f:
    f.write(shape.image.blob)
# Then references <img src="slide_1_img.png"> in HTML
```

**Why this matters**: The output must be a single self-contained `.html` file with no external dependencies. External image files break when the HTML is shared or opened from a different directory.

**Do instead:** Embed images as base64 data URIs so the HTML file is self-contained:

```python
import base64
b64 = base64.b64encode(shape.image.blob).decode('utf-8')
data_uri = f'data:image/{shape.image.ext};base64,{b64}'
# Use data_uri in <img src="...">
```

---

### Recurse into Grouped Shapes

**Detection**:
```bash
grep -n 'MSO_SHAPE_TYPE\|shape_type' convert.py | grep -v 'GROUP'
rg 'for shape in slide\.shapes' --type py -A 5 | grep -v 'GROUP\|group'
```

**Signal**:
```python
for shape in slide.shapes:
    if shape.has_text_frame:
        ...  # GroupShape has no text_frame — silently skipped
```

**Why this matters**: `GROUP` shapes contain child shapes with text. Skipping them silently drops bullet points and labels that appear in the original slide.

**Do instead:** Use a recursive generator to walk into grouped shapes before processing:

```python
def iter_shapes(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(shape.shapes)
        else:
            yield shape

for shape in iter_shapes(slide.shapes):
    if shape.has_text_frame:
        ...
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `AttributeError: 'Picture' object has no attribute 'text_frame'` | Accessing `.text_frame` without `has_text_frame` check | Add `if shape.has_text_frame:` guard |
| `AttributeError: 'NoneType' object has no attribute 'notes_text_frame'` | Notes access on slide with no notes | Wrap in `try/except AttributeError` |
| `ModuleNotFoundError: No module named 'pptx'` | python-pptx not installed | `pip install python-pptx`; check upfront with import guard |
| `PackageNotFoundError` | PPTX file corrupt, wrong path, or not a real PPTX | Check file exists and has `.pptx` extension before `Presentation()` call |
| Fewer extracted slides than expected | Grouped shapes or OLE objects skipped silently | Validate count; recurse into GROUP shapes |
| Images not visible in output HTML | Images saved as external files, not embedded | Use base64 data URI in `<img src>` |
| Table content missing | `shape.has_table` not checked; table shapes skipped | Add `elif shape.has_table:` branch; iterate `shape.table.rows` |
| Slide order wrong | `enumerate(prs.slides)` is correct; check if slides list is being sorted | Do not sort; PPTX slide order is authoring order |

---

## Detection Commands Reference

```bash
# text_frame access without guard
grep -n '\.text_frame' convert.py | grep -v 'has_text_frame'

# notes without AttributeError guard
grep -n 'notes_slide\|notes_text_frame' convert.py | grep -v 'try\|except'

# external image files (should use data URI instead)
grep -n "open.*'wb'" convert.py

# missing GROUP shape recursion
grep -n 'for shape in slide.shapes' convert.py
```

---

## See Also

- `STYLE_PRESETS.md` — CSS base block and presets applied after extraction
- `slide-controller.md` — SlideController JS patterns for the output HTML
