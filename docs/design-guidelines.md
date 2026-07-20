# AVGE Design Skill
### Aesthetic conventions for the AVGE tool-calling agent

**Purpose:** the AVGE engine gives you geometric and stylistic capability (fills, strokes, gradients, opacity, layering, effects) — this skill tells you *when and how* to reach for that capability so results look intentional rather than like a generic clip-art placeholder. Geometry correctness (proportion, symmetry, recognizability) is necessary but not sufficient — this skill is about the remaining 30% that separates "technically a coffee cup" from "a coffee cup someone designed."

Apply this skill on every `create_region`/`style_objects` call, not as a final pass — retrofitting flat shapes with depth after the fact costs more tool calls than building it in from the start.

---

## 1. Every filled region gets depth, not a flat fill

A single flat `fill` color reads as a placeholder. Before finalizing a region's style, choose one:

- **Two-tone shading**: split a curved/rounded surface into a "lit" region and a "shadow" region using two adjacent Regions of the same hue family (e.g. base `#E8D4B0` + a darker `#C9AD82` sliver along one edge to imply where light doesn't reach). This is what worked well in the coffee cup's liquid surface (two nested browns) — extend that same trick to every major surface, not just the ones that happened to need it structurally.
- **Gradient fill** where the tool supports it: light-to-dark along the axis facing away from an assumed light source (default: upper-left).
- **A thin highlight stroke or region** (very light tone, low opacity, positioned along one edge) reads as reflected light and is cheap — 1 extra region, disproportionate visual payoff.

Reserve pure flat fill for genuinely flat-by-design objects (icon-style silhouettes, background shapes) — make that a deliberate choice, not the default.

## 2. Line weight is a hierarchy, not a constant

Don't give every stroke the same width. Establish 2–3 tiers per composition:
- **Outer/primary silhouette**: heaviest stroke (defines the object against the background).
- **Internal structural lines** (e.g. cup rim, window panes): medium.
- **Fine detail** (highlights, texture lines): thinnest, or no stroke at all (fill-only).
Uniform stroke width everywhere (as seen in the MVP results so far — most objects used `width=0.005` across nearly every region) is the single fastest visual tell of an unstyled result. Vary it deliberately.

## 3. Palette: pick 3–5 colors with a relationship, not independent choices per region

Before creating any region, decide the palette as a set, not one color at a time:
- **Analogous** (adjacent hues — warm browns/tans for the cup, greens for a tree) for a calm, cohesive object.
- **Complementary accent**: one small element in a contrasting hue draws the eye (e.g. a warm cup with a single cool-toned accent).
- Avoid pure saturated primaries (`#FF0000`, `#00FF00`, `#FFFF00`-family flat colors) unless the brief calls for a literal flat/icon style — they read as unconsidered defaults. Slightly desaturated, warmed, or cooled variants read as chosen.
- Reuse the same 3–5 hex values across all regions in a scene rather than picking a new arbitrary color per region — visual coherence comes from a shared, small palette, not variety.

## 4. Ground objects with shadow or context, don't float them

A subject centered on pure white with no grounding cue reads as a sticker, not a scene. Cheap, high-payoff additions:
- A soft ground shadow region (low-opacity dark ellipse/shape beneath the subject) — as the coffee cup benchmark already did with its saucer, extend the same instinct even when the prompt doesn't explicitly ask for a supporting surface (e.g. a subtle shadow under a smiley face's chin, a ground-line under a star if it's meant to sit in a scene rather than float as a pure icon).
- Whether to ground an object is itself a style decision — flat icon-style compositions (app icons, logos) *should* float; representational/scene-style compositions should not. Decide which register the prompt calls for before defaulting to either.

## 5. Composition: use the canvas deliberately

- Default centering (bounding box centered in the 0–1 canvas) is a safe fallback, not a design choice — deliberately shift the subject off-center (e.g. lower-third, or offset toward negative space) when the composition benefits, especially for scene-style (not icon-style) prompts.
- Leave breathing room: a subject that fills 90%+ of the canvas edge-to-edge reads as cramped. 70–80% of the canvas's shorter dimension is a reasonable default fill ratio for a single-subject composition.
- For multi-element scenes (house, tree), vary element scale intentionally rather than making every sub-part roughly equal size — visual hierarchy needs one dominant element and supporting smaller ones.
- **Proportion relative to scene context**: an object's canvas footprint must match how it fits in a real scene. A desk is ~90–100% of the canvas width; headphones resting on it are ~15–25%; a water bottle is ~6–8%. Before creating any region, estimate what fraction of the canvas it should occupy by comparing it to the real-world object it represents alongside the other objects in the scene. The most common proportion mistake is making standalone objects too large (filling 40–50%+ of canvas width when they should be 15–25%). A good heuristic: if the item sits on a surface, its width should be ≤¼ of the surface's width unless it's the sole subject.

## 6. Match the style register to the prompt, and hold it consistently

Before the first `create_region` call, decide (even implicitly) which register this composition is in, and keep every subsequent choice consistent with it:
- **Flat/icon style**: bold flat fills, minimal-to-no shading, thick uniform-ish outlines, geometric simplicity. (Rules 1–2 relax here — flat fill is *correct* for this register.)
- **Soft/organic style**: gradients or two-tone shading throughout, rounded corners (`smoothness` biased high), softer/muted palette.
- **Line-art style**: little to no fill, all definition carried by stroke weight hierarchy (Rule 2 becomes the primary tool).
Mixing registers within one composition (e.g. one region flat-shaded, the next gradient-shaded, for no compositional reason) is what makes a result look inconsistent even when each individual region is fine in isolation.

## 7. Self-check before finishing (use `render_preview`, not just `describe_scene`)

Structural correctness doesn't surface aesthetic problems — visual review does. Before returning a final result, look at the preview and ask:
- Does anything look flat/pasted-on rather than dimensional? → apply Rule 1.
- Is every stroke the same weight? → apply Rule 2.
- Are the colors an arbitrary grab-bag, or a considered set? → apply Rule 3.
- Does the subject look grounded or like a floating sticker — and is that the right choice for this prompt's register? → apply Rule 4.
- Is the composition centered-by-default, or centered-on-purpose? → apply Rule 5.
- Do the objects obey real-world proportions — is each the right size relative to its container/surface? → see proportion guidance in Rule 5.
- Did you edit the existing document incrementally rather than rebuilding from scratch? → use \ to recolor, \ to remove, \/\ for undo.

This maps directly onto why visual feedback outperformed text-only in the MVP comparison (§4 of the MVP TDD) — \ cannot catch any of the above, since none of it is expressible as bounds/tags. This is a second, independent reason \ earns its cost, beyond the completeness finding already documented.

---

## 8. Character design: ask first, plan the register, build layer by layer

Before creating any region of a human/character, establish the following — either from the prompt's explicit description or by asking clarifying questions first:

### 8a. Decide the style register before anything else

The same character drawn in different registers uses *different proportions, different features, and different construction rules*. Decide upfront, then stay consistent:

| Register | Head-to-body ratio | Eyes | Nose | Mouth | Skin/shading |
|---|---|---|---|---|---|
| **Anime / manga** | 1:4–1:6 (large head) | Large, detailed iris + shine, often simplified lids | Small or omitted (just a shadow line) | Small curved line or simple shape | Flat cel-shading, minimal shadows |
| **Realistic** | 1:7–1:8 | Anatomical: whites + colored iris + round pupil + upper/lower lids + brows | Bridge + tip + nostrils clearly defined | Upper lip + lower lip + philtrum | Layered shading (two-tone per Rule 1), skin hue variation |
| **Cartoon / stylized** | 1:3–1:5 (head can be very large) | Simple circles or ovals, minimal detail, big pupils | Cute button or triangle, or omitted | Wide expressive shape | Flat fills, bold outlines, limited palette |
| **Chibi / super-deformed** | 1:2–1:3 (head is ~half the body) | Huge eyes, very large iris, big shines | Tiny dot or omitted | Small dot or curve | Flat fills, simple |

Asking the user "What style? Anime, realistic, cartoon, or chibi?" before starting saves time and avoids rebuilding.

### 8b. Establish character specs before drawing

Ask or determine:
- **Age range** (child, teen, young adult, adult) — affects face proportions (eyes lower on face for younger, higher for older) and body height
- **Gender** — affects jaw shape (softer/rounder vs sharper/angular), shoulder width, hip width
- **Clothing / outfit** — school uniform, casual, formal — determines what parts of the body are visible
- **Pose** — standing, sitting, with props — affects limb placement from the start
- **Viewing angle** — front, 3/4, profile — determines symmetry and visible features

### 8c. Human face proportions (realistic register)

- **Eyes**: positioned at the **vertical center** of the head (not the upper half). Distance between eyes = width of one eye.
- **Nose bottom**: halfway between eyes and chin bottom.
- **Mouth**: halfway between nose bottom and chin bottom.
- **Ears**: top aligns with eyebrows, bottom aligns with nose bottom.
- **Hairline**: roughly ⅓ of the way from crown to eyebrows.
- **Face width**: about ⅔ of head height.

For **anime**: eyes are lower on the face (below center), larger, and the nose is minimal. For **chibi**: the face is mostly eyes and forehead.

### 8d. Human body proportions

| Body part | Realistic (adult) | Anime | Cartoon | Chibi |
|---|---|---|---|---|
| **Head** | 1 unit | 1 unit | 1 unit | 1 unit |
| **Torso + neck** | ~2.5 units | ~2 units | ~2 units | ~1 unit |
| **Legs** | ~4 units (half the height) | ~3-3.5 units | ~2.5 units | ~1-1.5 units |
| **Arms** | reach mid-thigh | reach below hip | reach hip | reach waist |
| **Shoulder width** | ~2 head widths | ~1.5-1.8 head widths | ~1.5 head widths | ~1.2 head widths |

### 8e. Build order (smart layering)

Build the character in this order so each layer guides the next:

1. **Face shape** (oval/round) — establishes position and scale.
2. **Hair base** — covers the top of the face, defines silhouette.
3. **Eyes** — most expressive feature; position determines the rest of the face layout.
4. **Eyebrows** — just above eyes; set expression.
5. **Nose** — subtle; placed by the halfway rule.
6. **Mouth** — below nose; small changes here change expression dramatically.
7. **Ears** — align with eyes/nose.
8. **Neck + torso** — connects head to body; width relative to head.
9. **Arms + hands** — extend from shoulders; hands are ~face-sized.
10. **Legs + feet** — longer than expected (half the total height in realistic).

### 8f. Smart iteration workflow

- Start with a **checkpoint** before adding the face features so you can restore if the proportions are off.
- Use **describe_scene to verify positions** — check that eye y-coordinates match (both eyes at same height), that the nose is centered (x=0.5 for frontal view).
- **Render_preview frequently** — human faces are the most perceptually sensitive subject; bounding-box text feedback is not enough to judge if a face looks right.
- Fix asymmetry with  or  + recreate — never rebuild the full document.
- For complex characters, build the **face and body in separate checkpoint layers**: checkpoint("face_done") before adding the body, so you can adjust body proportions without losing face work.
 (§4 of the MVP TDD) — `describe_scene` cannot catch any of the above, since none of it is expressible as bounds/tags. This is a second, independent reason `render_preview` earns its cost, beyond the completeness finding already documented.

## 9. Segments, Not Curves — Posing Through Rotation

In 2D vector illustration, **bent limbs and fanned fingers are built from straight segments at angles, not from curved outlines.** The illusion of curvature comes from how segments connect — the eye reads the angle change as a bend.

### 9a. The principle

Do NOT draw a bent arm as a single curved arm outline. Do NOT draw fanning fingers as five custom-shaped finger outlines.

Instead:
- **A bent arm** = two straight rects: upper arm (rotated from shoulder) + forearm (rotated from elbow), overlapping at the joint
- **Fanning fingers** = one pill rect, duplicated and rotated at different angles
- **A bent knee** = upper leg + lower leg rects, each rotated independently

### 9b. Arm construction

```
Start with a vertical rect for the upper arm (e.g. 0.06 wide × 0.22 tall):
  → transform_objects(rotate=-30)  → angles out from shoulder
  → transform_objects(rotate=20)   → angles forward from shoulder

Then a second rect for the forearm:
  → positioned at the elbow (end of upper arm)
  → transform_objects(rotate=10)   → angles down from elbow

Optionally bridge_shapes the overlapping elbow joint for a smooth transition.
```

The z-order matters: forearm on top of upper arm hides the overlap edge.

### 9c. Finger construction

```
Create one pill rect: rect(width=0.045, height=0.22, rx=0.022)
Clone and rotate each:
  → finger 1: rotate=-15° (pinky)
  → finger 2: rotate=-8°  (ring)
  → finger 3: rotate=0°   (middle)
  → finger 4: rotate=8°   (index)
  → finger 5: rotate=15°  (thumb)
```

All sit at a higher z-index than the palm. The palm has no top-edge stroke — only the hand outline (z=0) provides the outer silhouette.

### 9d. Stroke discipline for segmented bodies

- **Each segment has no stroke** — the fill alone defines it
- **A single silhouette outline** behind everything (z=0, `fill="none"`) traces the outer boundary
- **Only the final outer stroke** — no internal segment strokes to create crossing patterns
- Exception: crease lines, joint lines, and detail marks keep their own thin strokes

### 9e. Why this works

A rotated rect reads as a foreshortened limb because the viewer's brain fills in the missing curvature. The Catmull-Rom smoothness on the silhouette outline rounds the sharp corners at joints naturally. Two segments at 30° read as a bent elbow more convincingly than a hand-traced curved outline ever does.

### 9f. Position tracking after rotation

After `transform_objects(rotate=...)`, the shape's center shifts. To find the new position for attaching the next segment (e.g. forearm to elbow):

1. Call `describe_scene` to get the region's bounding box
2. The rotation pivot is the original center — the post-rotation position is offset
3. For the next segment, use `offset_x`/`offset_y` on `duplicate_region` to position it at the joint
4. Or read the SVG output to verify actual segment endpoints

A future enhancement will provide `get_feature_points(region_id, edge)` that returns actual post-transform coordinates, eliminating the guesswork.

## 10. Geometric Patterns and Batch Workflows

The engine supports two powerful patterns for reducing tool calls: **batch operations** (multiple ops in one call) and **geometric pattern generators** (deriving geometry from geometry).

### 10a. Inline shapes in batch

Instead of creating each shape individually, define them inline inside a batch call:

```python
batch([
  {"tool": "create_primitive", "shape": {"type": "rect", "x": 0.1, "y": 0.66, "width": 0.09, "height": 0.1},
   "fill": "#CCC", "stroke": "#333", "stroke_width": 3},
  {"tool": "create_primitive", "shape": {"type": "rect", "x": 0.21, "y": 0.66, "width": 0.09, "height": 0.1},
   "fill": "#CCC", "stroke": "#333", "stroke_width": 3},
])
```

Supported tools in batch include every registered tool, especially `create_region`, `create_ellipse_band`, `create_primitive`, `create_curve`, `edit_region`, `duplicate_region`, `delete_region`, `style_objects`, `transform_objects`, `project_quad`, and `generate_shape`.

### 10b. distribute_linear — point sequence generator

Given a start point and end point, generates evenly-spaced coordinates between them.

```
generate_shape(pattern="distribute_linear", params={
  "start": [0.1, 0.66],
  "end": [0.86, 0.66],
  "count": 8
})
→ returns coordinate list like [(0.1,0.66), (0.208,0.66), (0.317,0.66), ...]
```

**Use case — row of buildings:** Feed the returned coordinates into a loop that creates wall rects at each position. One `distribute_linear` call + N batch ops = entire building row.

The `duplicate_grid` tool is an alternative when you already have a source region and just want evenly-spaced copies. `distribute_linear` is better when you need the raw coordinates for custom positioning.

### 10c. apex_from_edge — outline arithmetic

Given a closed outline (typically a building wall rect), projects a triangle from one edge — creating a roof in a single operation.

```python
# Step 1: create a wall rect
create_primitive(shape={"type": "rect", "x": 0.1, "y": 0.66, "width": 0.09, "height": 0.1},
                 fill="#CCC", stroke="#333")

# Step 2: derive roof from wall outline
generate_shape(pattern="apex_from_edge", params={
  "region_id": "rect_abc123",
  "edge": "top",               # project from top edge
  "apex_offset": 0.05,         # roof height (optional; defaults to 0.4×edge width)
  "fill": "#E8D4B0",           # roof fill color
  "stroke": "#333",
})
→ creates triangle outline automatically
```

**How it works:** The function finds the two points defining the chosen edge (top = minimum y), calculates the edge midpoint, and projects a third point perpendicularly. The result is a 3-point triangle outline registered as a new region.

**Why this matters:** Every architectural scene with multiple buildings needs wall + roof pairs. Without `apex_from_edge`, each roof requires manual coordinate computation for every apex point. With it, one call generates the roof from the wall's existing geometry.

### 10d. Wall + roof construction workflow

The efficient pattern for multi-building scenes:

```python
# 1. Distribute positions along a line
seq = generate_shape(pattern="distribute_linear",
  params={"start": [0.05, 0.7], "end": [0.95, 0.7], "count": 6})
# Returns 6 evenly-spaced base positions

# 2. Batch-create walls at each position
batch([
  {"tool": "create_primitive", "shape": {"type": "rect", "x": seq[0][0], "y": seq[0][1], "width": 0.08, "height": 0.12},
   "fill": "#D4A574", ...},
  # ... repeat for seq[1] through seq[5]
])

# 3. Generate roofs from each wall
for wall_id in wall_ids:
  generate_shape(pattern="apex_from_edge",
    params={"region_id": wall_id, "edge": "top", "fill": "#C94C4C"})
```

Total calls: 1 (distribute) + 1 (batch) + 1 (apex loop) — instead of 6 walls + 6 roofs individually.

## 11. Batch Tool Reference — All Supported Tools

Every tool below is supported in `batch(ops=[...])`. Each op dict requires a `"tool"` key; all other params match the standalone tool's arguments.

| Tool | Required params | Common optional params |
|---|---|---|
| `create_region` | `outline` (list of [x,y]) | `fill`, `stroke`, `stroke_width`, `smoothness`, `closed`, `z_index`, `layer`, `clip_to`, `fill_gradient`, `blend_mode` |
| `create_ellipse_band` | `cx`, `cy`, `rx` | `ry`, `thickness`, `inner_rx`, `inner_ry`, `start_angle`, `end_angle`, `rotation`, `perspective`, `skew_x`, `fill`, `stroke`, `stroke_width`, `z_index` |
| `create_primitive` | `shape` (rect/ellipse/line/polyline/compound_path/etc.) | `fill`, `stroke`, `stroke_width`, `stroke_dasharray`, `smoothness`, `closed`, `z_index`, `layer`, `blend_mode`, `opacity` |
| `create_curve` | `points` (list of [x,y]) | `stroke`, `stroke_width`, `smoothness`, `z_index`, `layer`, `stroke_linecap`, `blend_mode` |
| `create_text` | `x`, `y`, `text` | `fill`, `font_size`, `font_family`, `text_anchor`, `font_weight`, `z_index`, `rotate` |
| `import_svg_path` | `path_data` (SVG path string) | `fill`, `stroke`, `smoothness`, `closed`, `z_index`, `layer`, `samples_per_curve` |
| `create_line_pattern` | `pattern` | `points`, `bounds`, `center`, `radius`, `count`, `density`, `amplitude`, `frequency`, `stroke`, `stroke_width`, `width_profile`, `role` |
| `edit_region` | `region_id` or `ids` | `outline`, `point_index`, `point_coords`, `point_dx`, `point_dy`, `fill`, `stroke`, `smoothness`, `z_index`, `shape`, `layer`, `clip_to`, `blend_mode` |
| `edit_regions` | `updates` | Per-item `outline`, `point_index`, `point_coords`, `point_dx`, `point_dy`, `fill`, `stroke`, `opacity`, `z_index`, `layer`, `clip_to`, `blend_mode` |
| `duplicate_region` | `region_id` | `offset_x`, `offset_y`, `scale`, `rotate`, `fill`, `z_index`, `mirror_x`, `mirror_y`, `shadow_mode` |
| `create_shadow` | `region_id` | `onto_region_id`, `direction`, `distance`, `softness`, `opacity`, `scale`, `sx`, `sy`, `z_offset` |
| `delete_region` | `region_id` | — |
| `style_objects` / `restyle` | `ids` or `selector` | `fill`, `stroke`, `stroke_width`, `opacity`, `blend_mode`, `clip_to`, `fill_gradient`, `material` (`glass`, `brushed_metal`, `concrete`, `wood`, `tile`, `foliage`) |
| `apply_brush_style` | `selector` | `brush`, `color`, `size`, `opacity`, `apply_to`, `blend_mode`, `pressure`, `texture_strength` |
| `set_layer_role` | `layer`, `role` | `z_base`, `opacity`, `blend_mode` |
| `apply_texture_effect` | `effect` | `selector`, `bounds`, `clip_to`, `color`, `secondary_color`, `density`, `size`, `opacity`, `angle`, `blend_mode` |
| `transform_objects` | `selector` | `dx`, `dy`, `scale`, `rotate`, `group_mode`, `mirror_x`, `mirror_y`, `z_index`, `mode`, `alignment` |
| `project_quad` | `target_quad` | `source_region_id`, `replace_source`, `columns`, `rows`, `fill`, `stroke`, `stroke_width`, `z_index`, `inherit_style` |
| `generate_shape` | `pattern`, `params` | Pattern-specific — see `generate_shape` docs |
| `critique` | — | `mode` (`rules`, `visual`, `both`), `min_confidence`, `as_json` |

Use `create_line_pattern` for linework families that should be generated consistently rather than hand-placed: wavy, zigzag, spiral, hatch, cross-hatch, contour hatch, scribble, stipple, construction, center, gesture, decorative, and implied lines. Use `width_profile="tapered"` or `"pressure"` when the line should visibly change thickness; this creates filled ribbon geometry because SVG strokes are otherwise uniform width along a path.

For object-bound linework, use `outline_pattern` / `fill_pattern` on the creation tool itself. `create_region(shape=...)`, freeform `create_region(outline=...)`, `create_primitive`, `create_curve`, and `create_ellipse_band` can create editable pattern overlay regions tied to the base object. Examples: dotted circle outline, wavy square border, rough/sketch polygon contour, hatched freeform fill, stippled ellipse fill, or pressure-style curve overlay.

For generic digital art workflows, use `set_layer_role` to keep layer purpose and z-order explicit: background, sketch, base_color, shadow, highlight, texture, line_art, glow, and fx should not share one undifferentiated layer. Use `apply_brush_style` on existing strokes/regions when the same geometry should read as pencil, ink, g-pen, airbrush, watercolor, chalk, hair, foliage, cloud, or particle marks. Use `apply_texture_effect` for clipped vector overlays such as halftone, screen tone, fabric grain, paper/noise, bloom, particles, gradient light, and rim light. These tools complement `restyle` and `create_line_pattern`; they do not replace base fills, palette planning, or object-bound `outline_pattern`/`fill_pattern`.

For whole-region transforms, use `transform_objects` exclusively. Do not use `edit_region` or `edit_regions` to move, scale, rotate, mirror, align, or distribute regions. The edit tools own content/style changes and single-point edits only; `point_dx` / `point_dy` are vertex nudges, not object translation.

For any tool that targets existing regions, prefer the shared `selector` object over one-off targeting fields. The standard selector keys are: `ids`, `group_name`, `layer`, `fill`, `tags`, `bounds` (`min_x`, `max_x`, `min_y`, `max_y`, `min_w`, `max_w`, `min_h`, `max_h`), `z_min`, `z_max`, and `has_stroke`. Multiple selector filters are AND-ed; `ids` or `group_name` establish the candidate set first.

**Inline shapes in batch:** Use `create_primitive` or `create_region` with shape data directly:
```python
batch([{"tool": "create_primitive", "shape": {"type": "rect", "x": 0.1, "y": 0.66, "width": 0.09, "height": 0.1},
        "fill": "#CCC", "stroke": "#333"}])
```

**Batch text labels:** Create multiple text labels in one call:
```python
batch([
  {"tool": "create_text", "x": 0.25, "y": 0.05, "text": "SMALL BRAIN", "font_size": 0.04, "fill": "#000"},
  {"tool": "create_text", "x": 0.75, "y": 0.05, "text": "BIG BRAIN", "font_size": 0.04, "fill": "#000"},
])
```

**Adding a new tool to batch:** When creating a new scene graph method, add a matching `elif tool == "new_tool":` branch in `SceneGraph.batch()` in `scene/graph.py`. Extract params via `op.pop()` for required args (consumes them) and `op.get()` for optional args (leaves them in the dict for other branches).
