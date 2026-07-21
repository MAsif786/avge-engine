# AVGE Tool Backlog — Generic And De-Duplicated

Rule: add a new tool only for a genuinely new geometry, query, render, or export operation. A named look, material, brush, object type, or domain-specific variant should be a preset, data-table row, `mode`, or documented workflow on an existing tool.

This backlog is implementation-oriented. Usage recipes belong in `docs/design-guidelines.md` or `docs/environment-guidelines.md`.

## Final Tool Candidates

| Tool / extension | Replaces or absorbs | Why it is a real capability |
|---|---|---|
| `duplicate(pattern="scatter", count, bounds, seed, jitter)` | Cloud/rock/grass/prop scatter needs, ad hoc randomized placement | Implemented in `m0b-v20` as a `duplicate` mode with bounded random center placement and existing jitter support. |
| `add_shading(mode="gradient", stops, light_direction, strength)` | Separate architecture gradient-shading proposal | Continuous per-plane shading cannot be expressed by hard two-tone copies. |
| `generate_background_asset(mode, bounds, count, density, seed, detail)` | `generate_shape(pattern="cornice")`, `generate_shape(pattern="awning")`, `generate_shape(pattern="rooftop_props")`, `create_facade_details`, `create_building_cluster`, tree/water/rock/grass generators | Implemented in `m0b-v21` with generic modes for facade detail, tree clusters, cloud banks, water ripples, rock clusters, and grass patches. |
| `apply_fx(type="lens_flare"|"motion_blur"|"speed_lines"|"impact_lines"|"particles", ...)` | `create_lens_flare`, `create_motion_effect`, weather/particle helper tools | Implemented in `m0b-v23` for editable vector directional/radiant/action FX. Single-stroke weather remains a brush preset. |
| `mix_region_colors(source_region_id, target_region_id, mix_ratio, output)` | True `mixer_brush` behavior | Needs two source regions and generated intermediate color overlays, so it is not just a brush preset. |
| `smudge_region` / `smudge_edge` | Smudge coloring workflow | Directional color drag is different from `blur`, which only softens in place. |
| `warp_region(region_id, mode, handles, falloff, preserve_corners)` | General warp/free deformation gap | Deforms non-rectangular vector outlines beyond affine transform and `project_quad`. |
| `mesh_warp_region` | Higher-order organic deformation | Deferred. Build only if `warp_region` is insufficient. |
| `create_comic_panel_layout(layout, rows, columns, gutters, reading_direction, ...)` | Panel creator and page layout tools | Implemented in `m0b-v22` with grouped panel regions, gutters, common page layouts, reading-order metadata, and clip-target metadata. |
| `create_speech_balloon` | Manual balloon body + tail + text composition | Composite object with body, tail, text, grouping, and z-index defaults. |
| `create_sound_effect_text` | Plain text plus manual outline/shadow accents | Composite lettering treatment for comic/manga SFX. |
| `create_surface_stripes(target_quad, count, orientation, ...)` | Manual crosswalk/lane/floor stripe placement | Repeated projected stripes need shared perspective and spacing falloff. |
| `measure_geometry(mode, points/region_id, units)` | Ruler, angle tool, distance tool | Query operation returning structured measurements in normalized and pixel units. |
| `create_measurement_grid` | Flat ruler/grid/guides | Flat construction grid is distinct from vanishing-point perspective grids. |
| `create_adjustment_layer(type, selector, strength, ...)` | Scene-wide color grading/publishing polish | Non-destructive or overlay-based correction has no existing equivalent. |
| `symmetry_duplicate(mode="mirror"|"radial"|"rotational"|"kaleidoscope", ...)` | Mirror/radial/rotational/kaleidoscope symmetry requests | Existing duplicate/transform covers part of this; kaleidoscope and a unified symmetric workflow are the gap. |
| `resize_document(width, height, scale_content)` | Resize publishing workflow | Post-create canvas resizing with optional content scaling is not currently first-class. |
| `export_raster(format="png"|"jpeg", scale, crop_bounds, background)` | PNG/JPEG export and crop export | Preview PNG exists, but production raster export with crop/format/path settings is a separate publishing operation. |
| `set_print_metadata(dpi, bleed, trim, safe_area, color_mode)` | DPI settings and print setup | Stores print/layout metadata without pretending to implement full CMYK conversion. |
| `create_curve(mode="bezier", handle_in, handle_out)` | Create-then-edit Bézier workflow | Extends existing `create_curve`; exact handles at creation avoid a second edit call. |
| `pattern_brush_along_path` | Repeating decorative brush stamps | Deferred. Build only if `create_line_pattern`, `outline_pattern`, and `fill_pattern` are insufficient. |

## Data Tables, Not Tools

| Data table | Absorbs | Access pattern |
|---|---|---|
| Brush preset table | `paint_brush`, `blend_brush`, `fabric_brush`, `stone_brush`, `wood_grain_brush`, `metal_brush`, `pattern_brush`, `rain_brush`, `snow_brush`, `fire_brush`, `smoke_brush`, `spark_brush`, `water_brush`, plus existing pen/medium aliases | Implemented in `avge_engine.effects.brushes`; discover with `list_brush_presets()`, apply with `apply_brush_style(brush=<key>)`. |
| Background detail table | Cornice, awning, rooftop props, sills, mullions, pipes, facade clutter | Internal to `generate_background_asset(detail=[...])`, not a separate agent-facing tool family. |
| Character scaffold templates | Face/head/body/hand/foot proportions by style/view | Use only if the eval spike proves documented primitive workflows are not enough. |
| FX preset table | Lens flare variants, speed-line styles, impact-line styles, weather particle defaults | Internal to `apply_fx(type=..., preset=...)`. |

## Eval First

These may be useful, but should not be promoted to tools until an eval shows agents cannot produce acceptable results through documented compositions of existing primitives.

| Candidate | Open question |
|---|---|
| `create_character_guide` | Does it materially improve face/body/hand/foot scaffold quality beyond the design guide plus primitives? |
| `create_character_template` | Does it improve turnarounds, expression sheets, or pose references enough to justify a tool? |
| `create_reference_board` | Likely composition-only: regions, text labels, palettes, and layer metadata. Build only if repeated failures show a tool is needed. |
| Layer grouping metadata | Useful for organization, but not a drawing/rendering gap. Consider metadata support only if complex scenes become hard to manage. |

## Removed Or Not Planned

These should not be added as standalone tools.

| Request family | Reason |
|---|---|
| `generate_cloud` | Use brush/cloud presets, scatter duplication, gradient shading, and blur as a documented composition pattern. |
| One-point/two-point rulers | Existing `create_perspective_grid` covers them as modes. |
| Move/scale/rotate/free transform | Existing `transform_objects` covers these. |
| Rectangle/circle/ellipse/polygon/star/line/basic curve | Existing `create_primitive`, `create_region`, `create_curve`, and primitive API endpoints cover these. |
| Lasso/rectangle select/ellipse select/object selection UI tools | Use shared selectors; consider only generic `select_by_shape` or `select_similar` if selector failures persist. |
| Alpha lock | Agents can restyle selected regions without changing geometry. |
| Separate mask/clipping-mask tools | Existing `clip_to` covers the core behavior unless repeated mistakes justify a wrapper. |
| Separate glow/bloom tools | Glow is covered by presets/blend modes/soft overlays; bloom by `apply_texture_effect(effect="bloom")`. |
| PSD/CLIP export | Heavy app-specific publishing formats; out of scope for now. |
| True CMYK conversion | Out of scope until there is a real print pipeline; store color-mode metadata first. |
| Color picker | Agents can inspect `get_region`/style data; not worth a separate human-style tool. |

## Namespace Assignment

- **Eager core:** `add_shading`, `warp_region`, `export_raster`
- **Style:** `mix_region_colors`, `smudge_region`/`smudge_edge`, `pattern_brush_along_path`, brush preset table
- **Geometry:** `measure_geometry`, `create_measurement_grid`, `symmetry_duplicate`, `mesh_warp_region`, Bézier mode for `create_curve`
- **Scene:** `create_adjustment_layer`, `create_surface_stripes`, `resize_document`, `set_print_metadata`
- **Comic:** `create_speech_balloon`, `create_sound_effect_text`
- **Eval-gated scene helpers:** character guide/template/reference board/layer grouping

## Implementation Plan

### Phase 0 — Foundations

- Brush preset table and `list_brush_presets()` implemented in `m0b-v20`.
- Background detail table for facade and urban clutter.
- Shared validation/clamp helpers for counts, jitter, opacity, density, and falloff.
- Namespace/discovery strategy for non-core tools before the flat tool list grows much further.

### Phase 1 — Highest Leverage

Complete:

- `add_shading(mode="gradient")`
- `duplicate(pattern="scatter")`
- `generate_background_asset`
- `create_comic_panel_layout`

Next work starts in Phase 2.

### Phase 2 — Art Quality And Deformation

1. `mix_region_colors`
2. `warp_region`

### Phase 3 — Publishing And Measurement

1. `export_raster`
2. `resize_document`
3. `set_print_metadata`
4. `measure_geometry`
5. `create_measurement_grid`

### Phase 4 — Specialized, Independently Shippable

1. `symmetry_duplicate`
2. `create_speech_balloon`
3. `create_sound_effect_text`
4. `create_surface_stripes`
5. `create_adjustment_layer`
6. Bézier mode on `create_curve`
7. `smudge_region` / `smudge_edge`

### Phase 5 — Eval-Gated Or Deferred

- Run a character/reference scaffold eval before building `create_character_guide`, `create_character_template`, or `create_reference_board`.
- Build `pattern_brush_along_path` only if current pattern tools fail real decorative-border/stamp cases.
- Build `mesh_warp_region` only if `warp_region` fails real deformation cases.
- Add export/critique guardrails for visible guide layers alongside any guide/template feature that ships.
