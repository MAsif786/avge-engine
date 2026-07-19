# AVGE Engine — Tool Reference (51 tools)

_Generated from `__main__` — tool set: m0b-v8_

## `add_bumps`

Add small protrusions (bumps/knuckles/jagged edges) at specified segments of a region's outline. Good for knuckle bumps on fingers, serrated leaf edges, or spiky hair details. Extrudes outward from each segment midpoint. Process segments from last to first so indices remain valid.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `angle_offset` | `number` |  |  |
| `direction` | `string` |  |  |
| `document_id` | `any` |  |  |
| `extrusion_length` | `number` |  |  |
| `extrusion_width` | `number` |  |  |
| `region_id` | `string` | ✓ |  |
| `segment_indices` | `any` |  |  |
| `shape` | `string` |  |  |

---

## `add_depth_shadow`

Create a soft offset shadow from a region outline. Use to ground objects quickly without manually drawing shadow blobs. direction is degrees (0=right, 90=down); distance is normalized canvas units; softness is blur radius in pixels.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `color` | `string` |  |  |
| `direction` | `number` |  |  |
| `distance` | `number` |  |  |
| `document_id` | `any` |  |  |
| `new_region_id` | `any` |  |  |
| `opacity` | `number` |  |  |
| `region_id` | `string` | ✓ |  |
| `scale` | `number` |  |  |
| `softness` | `number` |  |  |
| `sx` | `any` |  |  |
| `sy` | `any` |  |  |
| `z_offset` | `integer` |  |  |

---

## `add_shading`

Add directional shading to a region. Creates highlight + shadow copies offset perpendicular to light direction, auto-colored via HSL. IDs use timestamp suffix — safe to call in parallel.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `intensity` | `number` |  |  |
| `light_direction` | `number` |  |  |
| `region_id` | `string` | ✓ |  |

---

## `apply_depth_haze`

Apply atmospheric perspective to existing regions by blending fills/strokes toward a haze color based on distance. Use for far buildings, skyline, canals, and background layers so scenes gain depth without manually restyling every region.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `affect_fill` | `boolean` |  |  |
| `affect_stroke` | `boolean` |  |  |
| `document_id` | `any` |  |  |
| `far_y` | `number` |  |  |
| `haze_color` | `string` |  |  |
| `max_strength` | `number` |  |  |
| `near_y` | `number` |  |  |
| `opacity_falloff` | `number` |  |  |
| `selector` | `any` |  |  |

---

## `apply_line_hierarchy`

Automate stroke-weight by depth: outer silhouette regions get thicker strokes, internal detail gets thinner. 💡 Apply after building a scene to enforce consistent line hierarchy.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `basis` | `string` |  |  |
| `document_id` | `any` |  |  |
| `inner_width` | `number` |  |  |
| `outer_width` | `number` |  |  |

---

## `batch`

Execute multiple operations in a single call. **ALL** registered tools work in batch — not just the ones listed.
  Stroke rule: stroke_width_px overrides normalized stroke_width when both are provided.
  create_region: outline, fill, stroke, smoothness, closed, z_index, stroke_width_px
  create_ellipse_band: cx, cy, rx, ry, thickness, start_angle, end_angle, perspective
  create_primitive: shape (rect/ellipse/line/polyline/compound_path), fill, stroke, stroke_width_px
  create_curve: points, stroke, stroke_width_px, smoothness
  create_text: x, y, text, fill, font_size, font_family, text_anchor
  insert_image: x, y, width, height, href
  import_svg_path: path_data, fill, smoothness
  edit_region: region_id, outline, fill, stroke, z_index, shape
  duplicate: region_id, pattern, count, dx, dy, columns, rows, spacing_falloff, scale_falloff
  add_depth_shadow: region_id, direction, distance, softness, sy
  cast_shadow: from_region_id, onto_region_id, direction, distance, softness
  apply_depth_haze: selector, haze_color, near_y, far_y, max_strength
  restyle: selector, mode, fill, stroke, stroke_width_px, material
  delete_region: region_id
  transform_objects: ids, mode, dx, dy, scale, rotate, alignment
  project_quad: target_quad, source_region_id, fill, stroke, columns, rows
  create_perspective_grid: vanishing_points, horizon_y, bounds
  create_facade_grid: target_quad, rows, columns, lit_ratio
  copy_element: region_id OR group, target_document_id, source_document_id, offset_x/y
  generate_shape: pattern, params
💡 Inline shapes: create primitives directly — {"tool":"create_primitive","shape":{"type":"rect","x":0.1,"y":0.66,"width":0.09,"height":0.1},"fill":"#CCC"}
💡 Batch text: multiple labels in one call — {"tool":"create_text","x":0.5,"y":0.5,"text":"Hello","font_size":0.06}

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `ops` | `array` | ✓ |  |

---

## `boolean_operation`

Perform boolean geometry on regions using shapely/GEOS. Operations: union, intersect, subtract, xor. Use for cutouts (windows, mug handle hole) and compound shapes without hand-tracing the result.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `keep_originals` | `boolean` |  |  |
| `new_region_id` | `any` |  |  |
| `opacity` | `any` |  |  |
| `operation` | `string` | ✓ |  |
| `region_ids` | `array` | ✓ |  |
| `simplify_tolerance` | `any` |  |  |
| `stroke` | `any` |  |  |
| `stroke_width` | `any` |  |  |

---

## `cast_shadow`

Create a soft shadow from one region clipped onto another region. Use for objects casting onto floors, walls, tables, platforms, or panels.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `color` | `string` |  |  |
| `direction` | `number` |  |  |
| `distance` | `number` |  |  |
| `document_id` | `any` |  |  |
| `from_region_id` | `string` | ✓ |  |
| `new_region_id` | `any` |  |  |
| `onto_region_id` | `string` | ✓ |  |
| `opacity` | `number` |  |  |
| `scale` | `number` |  |  |
| `softness` | `number` |  |  |
| `sx` | `any` |  |  |
| `sy` | `any` |  |  |
| `z_offset` | `integer` |  |  |

---

## `checkpoint`

Save a snapshot of the current document state. Use restore() to revert back to this point.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `name` | `string` |  |  |

---

## `checkpoint_diff`

Compare the current scene against a named checkpoint. Shows which regions were added, removed, or changed since the checkpoint. 💡 Use checkpoint before a risky edit, then checkpoint_diff to review what actually changed.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `name` | `string` |  |  |

---

## `compare_style_consistency`

Compare palette and stroke-width across multiple documents. Flags mismatches (e.g. a character's skin tone differing between pages). 💡 Use before finishing a multi-panel or multi-page work.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_ids` | `array` | ✓ |  |

---

## `copy_element`

Copy any element (region, rect, text, image, ellipse, line) or group from one document to another. 💡 Reuse characters, props, or backgrounds across pages instead of rebuilding from scratch. Copies all properties: outline, style, primitive, transform, metadata. 💡 Pass group_name='cat' to copy all group members at once. 💡 Use offset_x/y to reposition in the target doc. Example: copy_element(region_id='head', target_document_id='doc_p2') Example: copy_element(group_name='building', target_document_id='doc_p2', source_document_id='doc_p1', offset_x=0.2)

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `group_name` | `any` |  |  |
| `new_region_id` | `any` |  |  |
| `offset_x` | `number` |  |  |
| `offset_y` | `number` |  |  |
| `region_id` | `any` |  |  |
| `source_document_id` | `any` |  |  |
| `target_document_id` | `any` |  |  |

---

## `create_curve`

Create a smooth curved line through 3+ control points. Unlike create_region (filled shapes) or create_shape (primitives), create_curve produces a thin stroked path that curves through your points with Catmull-Rom interpolation. 💡 Hair strands: 4-6 points with smoothness=0.5, stroke='#3D2B1F', stroke_width=0.003, stroke_linecap='round' 💡 Wrinkles/creases: 3-4 points with smoothness=0.4, stroke_width=0.0015, stroke_linecap='round' 💡 Eyebrows, smile lines: 3 points, smoothness=0.6, stroke_linecap='round'

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `blend_mode` | `any` |  |  |
| `document_id` | `any` |  |  |
| `layer` | `string` |  |  |
| `opacity` | `number` |  |  |
| `points` | `array` | ✓ |  |
| `region_id` | `any` |  |  |
| `relative_to` | `any` |  |  |
| `smoothness` | `number` |  |  |
| `stroke` | `any` |  |  |
| `stroke_dasharray` | `any` |  |  |
| `stroke_linecap` | `any` |  |  |
| `stroke_width` | `number` |  |  |
| `stroke_width_px` | `any` |  |  |
| `z_index` | `integer` |  |  |

---

## `create_document`

Create a new canvas. Must be called first — call once per scene, then use create_region/restyle to edit the same document incrementally. Never rebuild from scratch.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `background` | `string` |  |  |
| `fill_gradient` | `any` |  |  |
| `height` | `integer` |  |  |
| `name` | `string` |  |  |
| `unit` | `string` |  |  |
| `width` | `integer` |  |  |

---

## `create_ellipse_band`

Create a filled elliptical ring or arc band in one call. Use for realistic circular balconies, overhead rings, rail strips, counters, curved floors, rims, and glass bands. Set start_angle/end_angle for partial arcs; use perspective>0 to widen the lower/near side and narrow the upper/far side; use skew_x for oblique architectural views.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `blend_mode` | `any` |  |  |
| `clip_to` | `any` |  |  |
| `cx` | `number` | ✓ |  |
| `cy` | `number` | ✓ |  |
| `document_id` | `any` |  |  |
| `end_angle` | `number` |  |  |
| `fill` | `any` |  |  |
| `fill_gradient` | `any` |  |  |
| `groups` | `any` |  |  |
| `inner_rx` | `any` |  |  |
| `inner_ry` | `any` |  |  |
| `layer` | `string` |  |  |
| `opacity` | `number` |  |  |
| `perspective` | `number` |  |  |
| `region_id` | `any` |  |  |
| `rotation` | `number` |  |  |
| `rx` | `number` | ✓ |  |
| `ry` | `any` |  |  |
| `samples` | `integer` |  |  |
| `skew_x` | `number` |  |  |
| `smoothness` | `number` |  |  |
| `start_angle` | `number` |  |  |
| `stroke` | `any` |  |  |
| `stroke_width` | `number` |  |  |
| `stroke_width_px` | `any` |  |  |
| `tags` | `any` |  |  |
| `thickness` | `any` |  |  |
| `z_after` | `any` |  |  |
| `z_before` | `any` |  |  |
| `z_index` | `integer` |  |  |

---

## `create_facade_grid`

Create a perspective-aware building facade with repeated window quads. Supports lit_ratio, deterministic seed, and subtle per-window inset variation so night-city facades read as buildings instead of flat sign slabs.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `columns` | `integer` | ✓ |  |
| `create_base` | `boolean` |  |  |
| `document_id` | `any` |  |  |
| `facade_fill` | `string` |  |  |
| `facade_stroke` | `string` |  |  |
| `layer` | `string` |  |  |
| `lit_fill` | `string` |  |  |
| `lit_ratio` | `number` |  |  |
| `margin_u` | `number` |  |  |
| `margin_v` | `number` |  |  |
| `opacity` | `number` |  |  |
| `region_id` | `any` |  |  |
| `rows` | `integer` | ✓ |  |
| `seed` | `integer` |  |  |
| `stroke_width` | `number` |  |  |
| `stroke_width_px` | `any` |  |  |
| `target_quad` | `array` | ✓ |  |
| `variation` | `number` |  |  |
| `window_fill` | `string` |  |  |
| `window_stroke` | `any` |  |  |
| `z_index` | `integer` |  |  |

---

## `create_perspective_grid`

Create two-point perspective construction guides from shared vanishing points. Use before project_quad/create_facade_grid so building edges, signs, rails, and street objects converge to the same off-canvas vanishing points. Emits editable compound-path guide regions.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `bounds` | `any` |  |  |
| `document_id` | `any` |  |  |
| `horizon_y` | `number` |  |  |
| `horizontals` | `integer` |  |  |
| `include_horizon` | `boolean` |  |  |
| `layer` | `string` |  |  |
| `opacity` | `number` |  |  |
| `region_id` | `any` |  |  |
| `stroke` | `string` |  |  |
| `stroke_width` | `number` |  |  |
| `stroke_width_px` | `any` |  |  |
| `vanishing_points` | `array` | ✓ |  |
| `verticals` | `integer` |  |  |
| `z_index` | `integer` |  |  |

---

## `create_primitive`

Create an SVG primitive shape (rect, ellipse, line, polygon, star, arc), open polyline, or stroked compound path. Use for geometric objects where polygon outlines would be imprecise. 💡 Stars: star shape = 4-point star in one call, not 16 tiny circles. 💡 Pentagon: polygon with sides=5. 💡 Fingers: rect with rx=half the width gives perfect pill shapes. 💡 Palm creases: line for stroke-only wrinkles. 💡 Curved lines: use type='polyline' with points and smoothness. 💡 Compound strokes: use type='compound_path' with subpaths to keep many seams/cables as one region. Shape object keys per type:
  rect:     x, y, width, height, rx? (corner radius), taper? (trapezoid)
  ellipse:  cx, cy, rx, ry? (ry=rx if omitted)
  line:     x1, y1, x2, y2 (or points for backward-compatible polyline)
  polyline: points ([[x,y],...]), closed?, smoothness?
  compound_path: subpaths ([[[x,y],...], ...]), closed?, smoothness?
  polygon:  cx, cy, r, sides? (default 6), rotate?
  star:     cx, cy, r, r_inner?, points? (default 5), rotate?
  arc:      cx, cy, r, start_angle?, end_angle?

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `blend_mode` | `any` |  |  |
| `closed` | `any` |  |  |
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `groups` | `any` |  |  |
| `layer` | `string` |  |  |
| `opacity` | `number` |  |  |
| `region_id` | `any` |  |  |
| `relative_to` | `any` |  |  |
| `rotate` | `number` |  |  |
| `shape` | `object` | ✓ |  |
| `smoothness` | `any` |  |  |
| `stroke` | `any` |  |  |
| `stroke_dasharray` | `any` |  |  |
| `stroke_linecap` | `any` |  |  |
| `stroke_width` | `number` |  |  |
| `stroke_width_px` | `any` |  |  |
| `z_after` | `any` |  |  |
| `z_before` | `any` |  |  |
| `z_index` | `integer` |  |  |

---

## `create_region`

Create a vector region from an outline defined by points. The engine fits smooth Bézier curves to your points. ⚠️ Coordinates MUST be normalized 0.0–1.0 ((0,0)=top-left, (1,1)=bottom-right). 💡 Refine incrementally: add regions here, use ``restyle`` to recolor, ``edit_region`` to nudge points — never rebuild from scratch. 💡 blur=N adds Gaussian blur for soft glows, shadows, and fog.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `blend_mode` | `any` |  |  |
| `blur` | `number` |  |  |
| `clip_to` | `any` |  |  |
| `closed` | `boolean` |  |  |
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `fill_gradient` | `any` |  |  |
| `groups` | `any` |  |  |
| `handle_in` | `any` |  |  |
| `handle_out` | `any` |  |  |
| `layer` | `string` |  |  |
| `opacity` | `number` |  |  |
| `outline` | `any` |  |  |
| `region_id` | `any` |  |  |
| `relative_to` | `any` |  |  |
| `rotate` | `number` |  |  |
| `shape` | `any` |  |  |
| `smoothness` | `number` |  |  |
| `smoothness_per_point` | `any` |  |  |
| `stroke` | `any` |  |  |
| `stroke_dasharray` | `any` |  |  |
| `stroke_linecap` | `any` |  |  |
| `stroke_width` | `number` |  |  |
| `stroke_width_px` | `any` |  |  |
| `tags` | `any` |  |  |
| `z_after` | `any` |  |  |
| `z_before` | `any` |  |  |
| `z_index` | `integer` |  |  |

---

## `create_text`

Create a text label. ``y`` is the text **baseline** (bottom of text, not center). Font size is relative to canvas height (0.04 = 4%). 💡 Isometric text: ``skew_y=-30`` for right face, ``30`` for left. Available fonts for manga/manhwa/comic styling:
  Bradley Hand Bold — hand-lettered, closest to English manga
  Marker Felt — marker pen style, good for effects
  Comic Sans MS — casual comic book style
  Hiragino Kaku Gothic ProN — Japanese manga gothic font
  Apple SD Gothic Neo — Korean manhwa gothic font
  Chalkduster — rough chalkboard style
  Brush Script MT — brush stroke, elegant hand-lettering
  Arial/Helvetica bold — clean all-caps comic style

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `background_box` | `any` |  |  |
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `font_family` | `string` |  |  |
| `font_size` | `number` |  |  |
| `font_style` | `string` |  |  |
| `font_weight` | `string` |  |  |
| `groups` | `any` |  |  |
| `layer` | `string` |  |  |
| `letter_spacing` | `number` |  |  |
| `opacity` | `number` |  |  |
| `region_id` | `any` |  |  |
| `rotate` | `number` |  |  |
| `skew_x` | `number` |  |  |
| `skew_y` | `number` |  |  |
| `text` | `string` | ✓ |  |
| `text_anchor` | `string` |  |  |
| `x` | `number` | ✓ |  |
| `y` | `number` | ✓ |  |
| `z_index` | `integer` |  |  |

---

## `critique_composition`

Auto-check the scene against design skill rules. Returns structured findings about stroke-width uniformity, palette size, depth shading, and off-canvas objects. The mechanical version of the Design Skill checklist. 💡 Call after completing each major object, not only once before finishing — catches perspective/grounding mismatches while they're still cheap to fix.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |

---

## `critique_preview`

Preview-quality visual critique. Flags likely visual issues such as too_flat, over_rounded, missing_contact_shadows, bad_perspective, and dominant_blob_shape. Returns actionable suggestions with affected region IDs.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `as_json` | `boolean` |  |  |
| `document_id` | `any` |  |  |
| `min_confidence` | `number` |  |  |

---

## `define_gradient`

Store a named gradient definition. The returned gradient dict can be referenced in restyle(fill_gradient=...) or create_region(fill_gradient=...). 💡 Define once, reuse across many regions.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `angle` | `number` |  |  |
| `document_id` | `any` |  |  |
| `name` | `string` | ✓ |  |
| `stops` | `any` |  |  |
| `type` | `string` |  |  |

---

## `delete_document`

Delete one or more saved documents from disk. Call with confirm=False first to preview what will be deleted, then call with confirm=True to execute. Use list_documents to see available documents. ⚠️ This permanently removes the document and all its regions.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `confirm` | `boolean` |  |  |
| `ids` | `array` | ✓ |  |

---

## `delete_region`

Delete one or more regions by ID. Returns list of actually removed IDs. Use this to clean up stray geometry, botched outlines, or elements you want to replace.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `ids` | `array` | ✓ |  |

---

## `describe_scene`

Get a text description of the current canvas — object list, bounds, styles, and warnings. Use this for structural feedback.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `detail` | `string` |  |  |
| `document_id` | `any` |  |  |
| `filter_layer` | `any` |  |  |

---

## `duplicate`

Make copies of a region or group according to a placement pattern. Consolidates duplicate_region, duplicate_grid, duplicate_radial, and duplicate_group into one configurable tool.
Patterns:
  single — one copy with offset/mirror/scale. Params: region_id, dx, dy, mirror_x, mirror_axis_x, scale
  linear — N copies in a row. Params: region_id, count, dx, dy, spacing_falloff, scale_falloff
  grid — N×M grid. Params: region_id, columns, rows, spacing_x, spacing_y
  radial — circular array. Params: region_id, count, center_x, center_y, radius
  group — duplicate group with transforms. Params: group_name, dx, dy, scale, rotate

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `center_x` | `number` |  |  |
| `center_y` | `number` |  |  |
| `columns` | `integer` |  |  |
| `count` | `integer` |  |  |
| `document_id` | `any` |  |  |
| `dx` | `number` |  |  |
| `dy` | `number` |  |  |
| `group_name` | `any` |  |  |
| `jitter` | `any` |  |  |
| `mirror_axis_x` | `any` |  |  |
| `mirror_axis_y` | `any` |  |  |
| `mirror_x` | `boolean` |  |  |
| `mirror_y` | `boolean` |  |  |
| `new_prefix` | `any` |  |  |
| `pattern` | `string` | ✓ |  |
| `radius` | `number` |  |  |
| `region_id` | `any` |  |  |
| `rotate` | `number` |  |  |
| `rotate_copies` | `boolean` |  |  |
| `rows` | `integer` |  |  |
| `scale` | `number` |  |  |
| `scale_falloff` | `number` |  |  |
| `shadow_mode` | `boolean` |  |  |
| `spacing_falloff` | `number` |  |  |
| `spacing_x` | `number` |  |  |
| `spacing_y` | `number` |  |  |
| `start_angle` | `number` |  |  |
| `variations` | `any` |  |  |
| `z_index` | `any` |  |  |

---

## `edit_group`

Unified group operation tool. Use one action per call: 'create' — create or replace a group with the given region IDs. 'add' — add regions to an existing group (creates if missing). 'remove' — remove specific regions from a group (doesn't delete regions). 'delete' — delete an entire named group (regions are not deleted). 💡 Use 'create' once to set up a group, then 'add' incrementally as you add more regions to the object.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `action` | `string` | ✓ |  |
| `document_id` | `any` |  |  |
| `group_name` | `string` | ✓ |  |
| `region_ids` | `any` |  |  |

---

## `edit_region`

Modify an existing region's outline, style, z_index, or shape. Only provided fields are changed; omitted fields keep their values. 💡 Single-point editing: use ``point_index`` + ``point_coords`` to nudge one vertex without resending the whole outline. 💡 Batch z-index: pass ids=[...] with z_index=N to reorder multiple regions at once.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `blend_mode` | `any` |  |  |
| `clip_to` | `any` |  |  |
| `document_id` | `any` |  |  |
| `dx` | `any` |  |  |
| `dy` | `any` |  |  |
| `fill` | `any` |  |  |
| `handle_in` | `any` |  |  |
| `handle_out` | `any` |  |  |
| `ids` | `any` |  |  |
| `layer` | `any` |  |  |
| `opacity` | `any` |  |  |
| `outline` | `any` |  |  |
| `point_coords` | `any` |  |  |
| `point_index` | `any` |  |  |
| `region_id` | `any` |  |  |
| `shape` | `any` |  |  |
| `smoothness` | `any` |  |  |
| `smoothness_per_point` | `any` |  |  |
| `stroke` | `any` |  |  |
| `stroke_dasharray` | `any` |  |  |
| `stroke_linecap` | `any` |  |  |
| `stroke_width` | `any` |  |  |
| `stroke_width_px` | `any` |  |  |
| `tags` | `any` |  |  |
| `z_index` | `any` |  |  |

---

## `edit_regions`

Edit multiple regions in a single call, each with its own relative transform (dx, dy, scale, rotate) or property override. 💡 Move a belt + buckle + gadgets together without extra union steps.
Example: [{"id":"belt","dx":-0.03},{"id":"belt_buckle","dx":-0.03}]

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `updates` | `array` | ✓ |  |

---

## `export_svg`

Export the current canvas to an SVG file on disk. Returns the file path and SVG character count.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `filepath` | `string` |  |  |

---

## `find_objects`

Query regions by visual properties and bounds. Lets you target e.g. 'all regions with fill #E8D4B0' for a palette-wide recolor without tracking every ID manually. Filters are AND-ed together; omit a filter to skip it. 💡 Use tags filter to find regions by semantic label (e.g. tags={'part':'handle'} after creating with tags).

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `has_stroke` | `any` |  |  |
| `layer` | `any` |  |  |
| `max_h` | `any` |  |  |
| `max_w` | `any` |  |  |
| `max_x` | `any` |  |  |
| `max_y` | `any` |  |  |
| `min_h` | `any` |  |  |
| `min_w` | `any` |  |  |
| `min_x` | `any` |  |  |
| `min_y` | `any` |  |  |
| `tags` | `any` |  |  |
| `z_max` | `any` |  |  |
| `z_min` | `any` |  |  |

---

## `generate_palette`

Generate a color harmony palette. Returns hex values the agent can use for fills/strokes. 💡 Use instead of inventing arbitrary hex values per region. Feed the output into restyle(selector={...}, fill=

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `base_hue` | `any` |  |  |
| `count` | `any` |  |  |
| `harmony` | `string` |  |  |
| `include_shades` | `boolean` |  |  |
| `mood` | `any` |  |  |

---

## `generate_shape`

Generate geometry from a generic pattern function. Each pattern is a pure geometric operation — no domain knowledge. Patterns:
  radial_spread — Fan N protrusions from one edge of a base shape.
    Params: region_id, count, anchor, length_range, width, angle_spread, taper, length_variance
  offset_outline — Expand (positive) or contract (negative) an outline uniformly.
    Params: region_id, distance
  guide_lines — Generate proportional division markers within a bounding box.
    Params: bbox_x, bbox_y, bbox_w, bbox_h, ratios, horizontal
  distribute_points — Place N evenly-spaced points along one edge.
    Params: region_id, count, edge
  bridge_shapes — Connect two overlapping outlines into one.
    Params: region_id_a, region_id_b
  interpolate_outlines — Create N morph steps between two outlines.
    Params: region_id_a, region_id_b, steps
  distribute_linear — Generate evenly-spaced points along a line.
    Params: start (x,y), end (x,y), count
    Returns coordinate list — feed into batch or create primitives.
    💡 Place building walls, fence posts, window columns in one call.
  apex_from_edge — Project a triangle (roof) from an outline edge.
    Params: region_id (source outline), edge (top/bottom/left/right), apex_offset, inset
    Creates a new region — roof triangle from a wall rect.
    💡 Wall rect + apex_from_edge = complete building in 2 calls.
    💡 inset=0.015 for roof overhang (wider than wall).
  segmented_chain — Create a bent limb or curled finger chain.
    Params: region_id (anchor), anchor (edge name), segments (list of dicts),
    joint_radius, count (fan multiple chains), angle_spread
    💡 One bent arm (2 segments + joint) or 5 curled fingers in 1 call.
  create_burst — Radiating lines from center (impact/speed lines).
    Params: cx, cy, count, radius_inner, radius_outer, start_angle, angle_span, taper, fill, stroke
    💡 Sunbursts, impact effects, speed lines, auras in one call.
  speech_bubble — Generate a speech bubble outline (rounded rect + tail).
    Params: cx, cy, width, height, tail_direction (top/bottom/left/right),
    tail_length, tail_width, rx (corner radius), fill, stroke
    💡 Creates a region — add text inside with create_text.
  isometric_box — Generate 3 visible faces of an isometric 3D box.
    Params: x, y, width, depth, height, angle, fill, top_fill, left_fill, right_fill,
      skip_faces (e.g. ["top"] for hidden leg faces), shadow (bool),
      shadow_opacity (default 0.12), z_index, opacity, layer,
      top_slant (vertical offset at front edge for slanted surfaces)
    💡 relative_to positions legs at visual 0-1 of face bbox.
      leg at (0.12,0.85) = front-left, (0.85,0.76) = front-right,
      (0.12,0.15) = back-left, (0.85,0.24) = back-right.
    💡 One gold bar = 1 call. Table leg: skip_faces=["top"], shadow=true
  attach — Snap one isometric box to another using named anchors.
    Params: parent (region_id), parent_anchor, child_anchor, flush (bool),
      child isometric_box params (width, depth, height, fill, etc.)
    Anchors: top_back_vertex, top_left/right/front_corner,
      bottom_back, bottom_left/right/front
    💡 attach(parent='frame_top', parent_anchor='bottom_left',
             child_anchor='top_left_corner', flush=true, width=0.06)

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `params` | `object` | ✓ |  |
| `pattern` | `string` | ✓ |  |
| `relative_to` | `any` |  |  |

---

## `get_document`

Get metadata for a document. Returns document ID, name, canvas size, region count, version, and a preview URL (open in browser to view). Omit document_id to use the active document.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |

---

## `get_history`

Show mutation history for a document. Requires document_id (get from create_document or list_documents). Returns auto-saved checkpoints with timestamps and actions. Use restore() to revert to any point.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `limit` | `integer` |  |  |

---

## `get_region`

Get a region's full outline coordinates, style, and primitive data. Use this when you need exact point positions for editing — e.g. adding a border to an isometric box face requires knowing its actual parallelogram vertices, not just bounding boxes.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `decimals` | `integer` |  |  |
| `document_id` | `any` |  |  |
| `region_id` | `string` | ✓ |  |

---

## `import_svg_path`

Import an SVG path data string as a vector region. Parses M, L, C, Q, Z commands into outline points. 💡 Use for complex silhouettes, logos, or any shape where typing coordinates manually would be impractical. Combine with smoothness=0.0 to preserve straight edges.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `closed` | `boolean` |  |  |
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `layer` | `string` |  |  |
| `mirror_x` | `boolean` |  |  |
| `mirror_y` | `boolean` |  |  |
| `path_data` | `string` | ✓ |  |
| `region_id` | `any` |  |  |
| `samples_per_curve` | `integer` |  |  |
| `smoothness` | `number` |  |  |
| `stroke` | `any` |  |  |
| `stroke_width` | `number` |  |  |
| `z_index` | `integer` |  |  |

---

## `insert_image`

Add an image (PNG, JPG, SVG, data URI) to the canvas. Renders as SVG <image> at the given position and size. 💡 Use for textures, photos, logos — paste a URL or data URI. The image must be accessible when the SVG is rendered.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `height` | `number` | ✓ |  |
| `href` | `string` | ✓ |  |
| `layer` | `string` |  |  |
| `preserve_aspect_ratio` | `string` |  |  |
| `region_id` | `any` |  |  |
| `rotate` | `number` |  |  |
| `width` | `number` | ✓ |  |
| `x` | `number` | ✓ |  |
| `y` | `number` | ✓ |  |
| `z_index` | `integer` |  |  |

---

## `list_documents`

List all saved documents on disk. Returns ID, name, version, and region count for each. Use load_document to restore one.


---

## `list_groups`

List all named groups and their member counts.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |

---

## `list_layers`

List all unique layers and their region counts. Use shift_layer_z to shift all regions in a layer up or down in the z-order.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |

---

## `load_document`

Load a previously saved document from disk into the editor. Use list_documents to see available documents.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `string` | ✓ |  |

---

## `project_quad`

Create or perspective-warp a rectangular/panel region into a target quadrilateral. Use for realistic tables, windows, floor tiles, wall panels, screens, and signs. target_quad order is top-left, top-right, bottom-right, bottom-left. Pass source_region_id to warp an existing region; omit it to create a projected panel.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `blend_mode` | `any` |  |  |
| `columns` | `integer` |  |  |
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `group_name` | `any` |  |  |
| `inherit_style` | `boolean` |  |  |
| `layer` | `string` |  |  |
| `opacity` | `any` |  |  |
| `region_id` | `any` |  |  |
| `replace_source` | `boolean` |  |  |
| `rows` | `integer` |  |  |
| `smoothness` | `number` |  |  |
| `source_region_id` | `any` |  |  |
| `stroke` | `any` |  |  |
| `stroke_width` | `any` |  |  |
| `stroke_width_px` | `any` |  |  |
| `target_quad` | `array` | ✓ |  |
| `z_index` | `integer` |  |  |

---

## `render_diff`

Render a visual diff PNG comparing current state against a named checkpoint. Shows added (green), removed (red), and modified (yellow) regions. 💡 Use after checkpoint/restore to verify changes visually. Returns a data URI that can be opened in a browser.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `name` | `string` |  |  |
| `scale` | `number` |  |  |

---

## `render_preview`

Get a visual PNG preview URL for the current canvas. 💡 Pass region_id to render just one region for inspection.
Also: /preview/{doc_id}.png (PNG) and /preview/{doc_id}.svg (SVG).

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `bbox` | `any` |  |  |
| `document_id` | `any` |  |  |
| `region_id` | `any` |  |  |
| `scale` | `number` |  |  |

---

## `restore`

Restore document state from a named checkpoint. All changes made after the checkpoint are discarded.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `name` | `string` |  |  |

---

## `restyle`

Change the appearance of a selection of regions. Consolidates recolor_conditional and recolor_palette into one tool. Select regions via ``selector``, then apply changes via ``mode``.
Modes:
  exact — set fill/stroke/opacity directly (directly)
  hsl_offset — shift each region's current color by HSL delta
  palette_swap — replace one exact fill color with another
Materials: glass, brushed_metal, concrete, wood, tile, foliage
Selector (choose one): ids=[...], group_name='...', fill='#...', layer='...'
💡 restyle(selector={'ids':['window']}, material='glass') — apply a material preset

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `blend_mode` | `any` |  |  |
| `document_id` | `any` |  |  |
| `fill` | `any` |  |  |
| `fill_gradient` | `any` |  |  |
| `fill_hsl_offset` | `any` |  |  |
| `from_color` | `any` |  |  |
| `material` | `any` |  |  |
| `material_detail` | `boolean` |  |  |
| `material_intensity` | `number` |  |  |
| `mode` | `string` |  |  |
| `opacity` | `any` |  |  |
| `preset` | `any` |  |  |
| `selector` | `any` |  |  |
| `stroke` | `any` |  |  |
| `stroke_hsl_offset` | `any` |  |  |
| `stroke_width` | `any` |  |  |
| `stroke_width_px` | `any` |  |  |
| `to_color` | `any` |  |  |
| `z_index` | `any` |  |  |

---

## `set_background`

Change the canvas background color of an existing document. 💡 Use instead of recreating the document when you need a different background.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `background` | `any` |  |  |
| `document_id` | `any` |  |  |
| `fill_gradient` | `any` |  |  |

---

## `shift_layer_z`

Shift all regions in a layer by a z-offset. Positive offset moves them higher (top), negative moves lower (back). Use after list_layers to find which layer to adjust.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | `any` |  |  |
| `layer` | `string` | ✓ |  |
| `z_offset` | `integer` | ✓ |  |

---

## `transform_objects`

Move, scale, rotate, mirror, or align existing regions. Use to reposition/resize objects after creation, or set mode='align' to align/distribute regions. 💡 For multi-part objects, use group_name to transform all members. Or layer='sky' to transform everything in a layer without listing IDs.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `alignment` | `any` |  |  |
| `document_id` | `any` |  |  |
| `dx` | `number` |  |  |
| `dy` | `number` |  |  |
| `group_mode` | `boolean` |  |  |
| `group_name` | `any` |  |  |
| `ids` | `any` |  |  |
| `layer` | `any` |  |  |
| `mirror_x` | `boolean` |  |  |
| `mirror_y` | `boolean` |  |  |
| `mode` | `string` |  |  |
| `pivot_mode` | `any` |  |  |
| `pivot_x` | `any` |  |  |
| `pivot_y` | `any` |  |  |
| `rotate` | `number` |  |  |
| `scale` | `number` |  |  |
| `sx` | `any` |  |  |
| `sy` | `any` |  |  |
| `z_index` | `any` |  |  |

---

