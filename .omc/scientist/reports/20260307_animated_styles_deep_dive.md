# Technical Deep Dive: 4 Animated Styles in MediaCoverGenerator v0.9.1

Generated: 2026-03-07 23:38:24
Source: upstream/main (justzerock/MoviePilot-Plugins)

---

## Executive Summary

All 4 animated styles share a common architecture:
1. **Pre-render phase**: Load images, extract colors, build background/text layers
2. **Frame generation phase**: Loop over `total_frames = fps * duration`, compose each frame as BMP
3. **Encoding phase**: Use ffmpeg subprocess to encode BMP sequence into APNG/GIF
4. **Output**: Base64-encoded binary string

All styles depend on: PIL/Pillow, numpy, ffmpeg (external binary), and ColorHelper utility.

---

## Style 1: animated_1 - Card Stack Rotation + Fly-out

### Core Concept
A **3-layer card stack** (main/mid/heavy blur) rotates in a fan arrangement on the right side of the canvas. 
The top card departs (fly/fade/crossfade), the stack shifts up, and a new card appears at the bottom.

### Algorithm Detail

**Card Preparation (per image):**
```
1. crop_to_square(img) -> resize to card_size (odd number = target_h * 0.7)
2. Main card:  rounded_corners + soft_rim + shadow
3. Mid card:   blur(8) + 50% color blend + rounded_corners + soft_rim + shadow
4. Heavy card: blur(16) + 40/60% color blend + rounded_corners + soft_rim + shadow
```

**Card colors** extracted via `ColorHelper.extract_dominant_colors(style="macaron")` - 3 colors per image.

**Rotation Math:**
- 3 angle slots: s1=-5deg, s2=10deg, s3=25deg (CSS-style, negated for PIL)
- `rotate_on_stable_canvas()`: Forces ODD canvas size to eliminate 0.5px jitter
  - Canvas = ceil(hypot(card_w, card_h)) + 9, forced odd
  - Center pixel = canvas_size // 2 (exact integer for odd sizes)
  - PIL `rotate(angle, expand=False, center=(c,c))`
- Per-frame interpolation: `ease_in_out_sine(local)` drives angle/position transitions

**Departure Types (3 modes):**
1. `fly`: Card slides to (0.75*W, -0.2*H) with ease_in_out_sine, alpha fades after 40%
2. `fade`: Card stays in place, alpha = 1 - ease_in_out_sine(t)
3. `crossfade`: Card stays, Image.blend between current and next card content

**Background Animation:**
- Breathing zoom: `zoom = 1 + amp * (0.5 - 0.5*cos(2*pi*phase))`
- Micro-pan: `sin(theta)` horizontal, `sin(theta + pi/3)` vertical
- Per-card background pre-rendered (blur + color_ratio blend + film_grain)
- Background crossfades in sync with top card transition

**Frame Timing:**
```
phase = frame_idx / total_frames          # 0.0 -> 1.0
cycle_pos = phase * n_cards               # maps to card index
local = cycle_pos - int(cycle_pos)        # 0.0 -> 1.0 within each card's segment
```

### Key Parameters
| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| image_count | 5 | 3-9 | More cards = shorter per-card display time |
| animation_fps | 15 | 1+ | Quality vs file size |
| animation_duration | 4s | 1+ | Total loop duration |
| departure_type | "fly" | fly/fade/crossfade | Visual transition style |
| animation_resolution | 400x300 | any WxH | Higher = better quality, larger file |

### Memory Profile
- 3 PIL Image lists (main/mid/heavy) x n_cards = **15 RGBA images** (at 400x300)
- Background list: n_cards RGBA images
- Stable canvas: ~hypot(card_w, card_h) + 9 pixels square
- Per-frame: 1 frame + 1 rotated card composite
- **Estimated peak**: ~50-80 MB for 5 cards at 400x300

---

## Style 2: animated_2 - Diagonal Split + Curtain Transition

### Core Concept
A **diagonal split layout** divides the canvas: left side shows blurred background + title text, 
right side shows the poster image. Images crossfade with ease_in_out_sine between transitions.

### Algorithm Detail

**Layout Geometry:**
```
split_top = 0.55 * target_w      # diagonal top boundary
split_bottom = 0.40 * target_w   # diagonal bottom boundary
-> Creates a slanted dividing line from (55%W, 0) to (40%W, H)
```

**Static Masks (pre-computed once):**
1. `_create_dynamic_diagonal_mask`: Binary polygon mask for left/right compositing
2. `_create_dynamic_shadow_mask`: Feathered edge shadow along the diagonal

**Image De-duplication:**
- `_image_signature()`: Resize to 24x24 grayscale, MD5 hash -> detect duplicate posters

**Per-image preparation:**
```
Right side: align_image_right(src, canvas_size) -> RGBA
Left side:  fit(src, canvas) -> GaussianBlur -> blend with bg_color -> film_grain
Text layer: _build_text_layer() with scaled fonts, shadow blur
```

**Frame Generation:**
```python
phase = f / total_frames
cycle_pos = phase * n_imgs
idx, nxt = int(cycle_pos) % n, (int(cycle_pos)+1) % n
local = cycle_pos - int(cycle_pos)
mix_t = ease_in_out_sine(local)

right = blend(right[idx], right[nxt], mix_t)
left_bg = blend(left[idx], left[nxt], mix_t)
frame = Image.composite(left_bg, right, diagonal_mask)
frame += edge_shadow
frame += blend(text[idx], text[nxt], mix_t)
```

**Key Difference from multi_1/static_3:**
- NOT a grid layout. Single poster displayed on right half
- Diagonal split with feathered shadow edge
- Text positioned at left 25% center
- Background changes per-poster (not fixed)

### Key Parameters
| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| image_count | 9 | 2-12 | Number of posters in rotation |
| animation_fps | 15 | 1+ | Smoothness |
| animation_duration | 10s | 1+ | How long each poster shows |
| animation_resolution | 320x180 | any WxH | Output size |

### Memory Profile
- 3 lists x n_imgs: right images, left backgrounds, text layers
- 2 masks (static, computed once)
- Per-frame: 3 blend operations + composite
- **Estimated peak**: ~30-50 MB for 9 images at 320x180

---

## Style 3: animated_3 - Multi-poster Scrolling Grid

### Core Concept
A **3x3 grid of posters** arranged in columns, rotated -15.8 degrees, scrolling vertically.
This is the **animated version of static_3** (multi_1). The most complex style with the highest
resource requirements.

### Algorithm Detail

**Grid Configuration (from POSTER_GEN_CONFIG):**
```
ROWS=3, COLS=3, MARGIN=22px, CORNER_RADIUS=46.1px
ROTATION_ANGLE=-15.8deg
CELL_WIDTH=410, CELL_HEIGHT=610 (at 1080p, scaled down)
START_X=835, START_Y=-362
COLUMN_SPACING=100
```

**Image Loading:**
- Custom order: "315426987" -> maps file names to positions
- Expects files named 1.jpg through 9.jpg
- Extended to fill 3x3 grid if fewer images

**Column Strip Construction:**
```
For each column (3 columns):
  - Take column's 3 posters
  - Duplicate: [A,B,C,A,B,C,A] = 7 images for seamless looping
  - Stack vertically with margins into a tall strip
  - Add shadow to each poster
```

**Scroll Animation:**
4 scroll modes:
1. `down`: All columns scroll down in sync
2. `up`: All columns scroll up in sync  
3. `alternate`: Columns 0,2 scroll down, column 1 scrolls up (with phase offsets)
4. `alternate_reverse`: Opposite of alternate

```
scroll_dist = rows * (cell_height + margin)  # one full cycle
col_phases = [0, scroll_dist//4, scroll_dist//2]

For each frame:
  progress = frame_idx / n_frames
  For each column:
    dy = (progress * scroll_dist + phase) % scroll_dist  # modular wrap
    sub_strip = strip.crop(0, dy, view_w, dy + view_h)
    rotated = sub_strip.rotate(-15.8deg, expand=True)
    paste onto frame at column position
```

**View Height Calculation:**
```
cos_val = cos(radians(15.8))
view_h = int(target_h / cos_val * 1.6)  # ~1.66x canvas height to cover rotation gaps
```

**Frame Cap:** Hard limit of 500 frames max (safety against infinite loops).

### Key Parameters
| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| animation_scroll | "alternate" | down/up/alternate/alternate_reverse | Scroll direction |
| animation_fps | 15 | 1+ | Smoothness |
| animation_duration | 12s | 1+ | Loop duration |
| animation_resolution | 300x200 | any WxH | CRITICAL for performance |

### Memory Profile
- 9 poster images (with shadows) at scaled resolution
- 3 column strips: each ~7 posters tall
- Base frame (bg + text, pre-composited once)
- Per-frame: 3 crop + rotate + paste operations
- **Estimated peak**: ~40-70 MB at 300x200
- **At 1080p this would be catastrophic**: strips would be enormous

### Critical Differences from static_3
- Static_3 renders once at full resolution (1920x1080)
- Animated_3 renders at reduced resolution per frame
- Animated_3 uses subprocess.run() (blocking) for ffmpeg vs Popen in others
- Background + text pre-composited into `base_frame` (optimization)
- First image path hardcoded as `poster_folder / "1.jpg"` for color extraction

---

## Style 4: animated_4 - Full-screen Background Crossfade

### Core Concept
The **simplest animated style**. Full-screen blurred background images crossfade between posters
with centered title text overlay. No cards, no grids, no geometric transforms.

### Algorithm Detail

**Per-image preparation:**
```python
bg, tint = _prepare_bg(path, canvas_size, blur_size, color_ratio)
# _prepare_bg:
#   1. Open image, fit to canvas
#   2. GaussianBlur(scaled_blur)
#   3. Extract dominant color or use bg_color_config
#   4. Darken tint by 0.82
#   5. numpy blend: bg * (1-ratio) + tint * ratio
#   6. Return RGBA image + tint color

text_layer = _build_text_layer(canvas_size, title, font_path, ...)
# Centered text (unlike animated_2 which is left-25%)
```

**Frame Generation (minimal):**
```python
phase = f / total_frames
cycle_pos = phase * n_imgs
idx, nxt = int(cycle_pos) % n, (int(cycle_pos)+1) % n
mix_t = ease_in_out_sine(local)

frame = blend(bg[idx], bg[nxt], mix_t)          # background crossfade
text  = blend(text[idx], text[nxt], mix_t)       # text crossfade
frame = alpha_composite(frame, text)              # overlay text
```

### Key Parameters
| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| image_count | 5 | 2-12 | Poster count |
| animation_fps | 15 | 1+ | Smoothness |
| animation_duration | 10s | 1+ | Loop time |
| animation_resolution | 320x180 | any WxH | Output size |

### Memory Profile
- 2 lists x n_imgs: backgrounds + text layers
- Per-frame: 2 blend + 1 composite (cheapest of all styles)
- **Estimated peak**: ~20-30 MB for 5 images at 320x180

---

## Cross-cutting Analysis

### Common Architecture Pattern
```
┌─────────────────────────────────────────┐
│ 1. Parse resolution, load images        │
│ 2. De-duplicate via _image_signature()  │  (all except animated_3)
│ 3. Pre-render per-image assets          │
│ 4. Frame loop: compose BMP files        │
│ 5. ffmpeg encode BMP -> APNG/GIF        │
│ 6. Return base64 string                 │
└─────────────────────────────────────────┘
```

### reduce_colors Parameter Mapping
| Mode | Palette Colors | Dither | Use Case |
|------|---------------|--------|----------|
| strong | 64 | none | Smallest file, banding visible |
| medium | 128 | bayer:bayer_scale=3 | Good balance |
| off | 256 (full) | floyd_steinberg (GIF) / none (APNG) | Best quality, largest file |

### ffmpeg Encoding Differences
- **animated_3**: Uses `subprocess.run()` (blocking, no stop_event check during encode)
- **animated_1/2/4**: Use `subprocess.Popen()` with poll loop + stop_event check

### Font Handling
| Style | Font Scaling | Text Position | Wrapping |
|-------|-------------|---------------|----------|
| animated_1 | `scale = target_h / 1080.0` | Left 25% center | Yes (by zh width) |
| animated_2 | `scale = height / 1080.0` | Left 25% center | Yes (by zh width) |
| animated_3 | `scale = target_h / 1080.0` | Fixed coords (73, 427) | Yes (multiline) |
| animated_4 | Manual `anim_scale` | Center (50%, 50%) | Yes (_wrap_english) |

### Image Requirements
| Style | Input | Expected Files | De-dup |
|-------|-------|---------------|--------|
| animated_1 | library_dir | Any poster images | MD5 signature |
| animated_2 | library_dir | Any poster images | MD5 signature |
| animated_3 | library_dir | Files named 1-9.jpg | No (custom order) |
| animated_4 | library_dir | Any poster images | MD5 signature |

---

## Performance Estimates

### Frame Generation Time (per frame, estimated)
| Style | Operations/Frame | Relative Cost |
|-------|-----------------|---------------|
| animated_1 | 4 rotations + 4 composites + bg_animate | HIGH (~50ms) |
| animated_2 | 3 blends + 1 composite + shadow | MEDIUM (~20ms) |
| animated_3 | 3 crops + 3 rotates + 3 pastes | MEDIUM-HIGH (~35ms) |
| animated_4 | 2 blends + 1 composite | LOW (~10ms) |

### Total Frame Counts (defaults)
| Style | FPS | Duration | Frames | Est. Total Time |
|-------|-----|----------|--------|----------------|
| animated_1 | 15 | 4s | 60 | ~3s + ffmpeg |
| animated_2 | 15 | 10s | 150 | ~3s + ffmpeg |
| animated_3 | 15 | 12s | 180 (cap 500) | ~6s + ffmpeg |
| animated_4 | 15 | 10s | 150 | ~1.5s + ffmpeg |

### File Size Estimates (320x180, reduce=strong)
| Format | animated_1 (60f) | animated_2 (150f) | animated_3 (180f) | animated_4 (150f) |
|--------|-----------------|-------------------|-------------------|-------------------|
| APNG | ~200-400 KB | ~300-600 KB | ~400-800 KB | ~200-400 KB |
| GIF | ~150-300 KB | ~200-500 KB | ~300-600 KB | ~150-300 KB |

---

## Potential Issues & Mitigations

### 1. animated_3 Hardcoded File Naming
**Issue**: `first_image_path = poster_folder / "1.jpg"` and custom_order="315426987" expect 
specific file naming. Current __init__.py `__filter_valid_items` may not produce files named 1-9.jpg.
**Mitigation**: Verify file preparation logic in __init__.py matches expected naming.

### 2. ffmpeg Dependency
**Issue**: All 4 styles require ffmpeg binary in PATH. No fallback.
**Mitigation**: Add ffmpeg check in init_plugin, log clear error if missing.

### 3. Memory Leak in animated_3
**Issue**: Uses `subprocess.run()` which blocks and doesn't check stop_event during encoding.
If encoding hangs, no way to cancel.
**Mitigation**: Switch to Popen pattern like animated_1/2/4.

### 4. animated_1 ODD Size Constraint
**Issue**: Card sizes and canvas sizes are forced to odd numbers to prevent rotation jitter.
If resolution produces even intermediate values, the `+1` adjustment could cause 1px visual artifacts.
**Mitigation**: Already handled in code with explicit odd-forcing.

### 5. numpy Version Compatibility
**Issue**: All styles use `np.array`, `np.clip`, `np.random.normal`. These are stable numpy APIs.
**Minimum**: numpy >= 1.20 (for type annotation support in some helpers).

### 6. PIL Version Requirements
**Issue**: Uses `Image.Resampling.BICUBIC` (Pillow 9.0+), `rounded_rectangle` (Pillow 8.2+).
**Minimum**: Pillow >= 9.0.0

### 7. Browser Compatibility
| Format | Chrome | Firefox | Safari | Edge |
|--------|--------|---------|--------|------|
| APNG | Yes | Yes | Yes | Yes |
| GIF | Yes | Yes | Yes | Yes |
| WebP | Yes | Yes | 14+ | Yes |
Note: WebP is disabled in __init__.py (`if format == "webp": format = "gif"`)

### 8. ImageResourceManager Not Used
**Issue**: `ImageResourceManager` is imported in __init__.py but the animated styles 
don't use it internally. PIL images are not explicitly closed after frame generation.
**Mitigation**: Not critical due to tempfile cleanup and GC, but could cause memory pressure 
during generation of styles with many pre-rendered assets.

### 9. Thread Safety
**Issue**: `stop_event` is checked in frame loop and ffmpeg poll loop, providing graceful cancellation.
**Risk**: animated_3's `subprocess.run()` is not interruptible by stop_event.

---

## Integration Checklist

1. [ ] All 4 styles import from `style/` subdirectory (not root level)
2. [ ] Font handling: All need (zh_font_path, en_font_path) tuple
3. [ ] All need `bg_color_config` dict with keys: mode, custom_color, config_color
4. [ ] animated_3 needs `__filter_valid_items` to produce files named 1-9.jpg
5. [ ] animated_1/2/4 need generic poster images (any naming)
6. [ ] ffmpeg must be available in PATH
7. [ ] `stop_event` threading.Event() passed to all styles
8. [ ] `animation_resolution` forced to "320x180" in __init__.py dispatch
9. [ ] Return value: base64 string on success, False on failure
10.[ ] WebP format disabled, only APNG and GIF supported
