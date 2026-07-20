# AVGE Engine — AI-Native Vector Graphics Engine

**Version:** 0.5.7 | **Tool set:** m0b-v18

Vector illustration tools for AI agents — create editable vector art with shapes, armatures, materials, and rendering. Output is clean SVG you can open in Illustrator, Figma, or any vector editor. Runs as an MCP server.

> [**View examples**](docs/examples.md) — fridge scene, bedroom, landscape, iPhone mockup, cat manga, and more with previews.

## Quick Start

```bash
python -m avge_engine api       # FastAPI HTTP server (:8000)
python -m avge_engine mcp-sse   # MCP SSE server (:8001)
python -m avge_engine mcp       # MCP stdio server
```

Preview renders at `http://localhost:8000/preview/<document_id>.png`

## Features

- **Normalized coordinates** — 0.0–1.0 canvas, no pixel math
- **Isometric box** — 3-face box with z-ordering, shadows, per-face styling, `top_slant` for slanted surfaces, and `attach` pattern for anchor-to-anchor placement
- **Procedural geometry** — radial spread, offset outlines, guide lines, segmented chains, speech bubbles, bursts, armature skeletons, foreshortening, surface detail
- **Armature skeletons** — node-edge graphs with tapered segments, junction separation, filleted V-gaps, curved Catmull-Rom chains, and unary union merging
- **Boolean operations** — union, intersect, subtract, xor with Ramer-Douglas-Peucker simplification
- **Perspective projection** — `project_quad` maps panels, tables, windows, signs, and floor tiles into real quadrilateral perspective
- **HSL shading** — auto highlight + shadow from light direction, plus gradient mode for architectural planes
- **Depth shadows** — `create_shadow` creates soft blurred grounding shadows or clipped cast shadows from existing outlines
- **Scene critique** — `critique(mode="rules"|"visual"|"both")` flags rule-based composition issues and visual-read problems
- **Primitives** — rects (including tapered/trapezoid), ellipses, ellipse/arc bands, lines, open polylines, compound paths, arcs, polygons, stars, and isometric boxes
- **Text + images** — SVG text with font family/style/anchor/letter-spacing/opacity/skew for isometric perspective, embedded images via `<image>`
- **Gradient backgrounds** — linear and radial gradient definitions, inline in `create_document` or via `set_background`
- **Style system** — fill, stroke, stroke-width, opacity, blend modes, dash patterns, rgba/hsla color support
- **Material presets** — `restyle(material=...)` for glass, brushed metal, concrete, wood, tile, and foliage with editable highlights, shadows, seams, and grain overlays
- **Pixel stroke widths** — `stroke_width` accepts canvas pixels for predictable rails, seams, branches, and cables
- **Environment helpers** — perspective grids, facade/window density, surface stripes, soft clouds, haze, and densify patterns for cornices, awnings, and rooftop props
- **Line pattern helpers** — wavy, zigzag, spiral, hatch, cross-hatch, contour hatch, scribble, stipple, and true tapered/pressure-width strokes
- **Region pattern styling** — apply dashed, dotted, wavy, zigzag, rough, sketch, tapered, pressure outlines, plus hatch/scribble/stipple fills, directly on primitives, freeform regions, curves, and ellipse bands
- **Generic art workflow tools** — brush presets, layer roles, clipped texture/effect overlays, halftones, bloom, particles, and gradient/rim lighting
- **Shared selectors** — targeting tools use one selector shape: `ids`, `group_name`, `layer`, `fill`, `tags`, `bounds`, `z_min`, `z_max`, `has_stroke`
- **Batch operations** — execute multiple tools in one call, edit multiple regions with per-region transforms
- **Palette generation** — HSL harmony presets (complementary, triadic, analogous, etc.)
- **Named gradients** — define once with `define_gradient`, reference by name in `restyle`
- **Cross-document copy** — copy elements between documents with offset
- **SVG arc support** — A/a commands in `import_svg_path` (elliptical arcs with sweep/large-arc flags)
- **Relative positioning** — place elements relative to a parent region's bounding box
- **PNG rasterization** — via rsvg-convert (librsvg) with Unicode/emoji font support
- **Per-document tracking** — checkpoint/restore history, tool usage stats

## 56 MCP Tools

| Category | Tools |
|----------|-------|
| **Document** | `create_document`, `clone_document`, `list_documents`, `set_background`, `get_document_stats` |
| **Create** | `create_region`, `create_ellipse_band`, `generate_cloud`, `create_primitive`, `create_curve`, `create_text`, `insert_image`, `import_svg_path` |
| **Edit** | `edit_region` (point-level nudge), `edit_regions` (batch content/style edits), `delete_region`, `copy_element`, `get_region` (inspect outline) |
| **Transform** | `transform_objects`, `project_quad`, `create_perspective_grid`, `create_facade_grid`, `create_surface_stripes`, `duplicate`, `boolean_operation` |
| **Depth** | `create_shadow`, `add_shading` |
| **Style** | `restyle` (including material presets), `apply_brush_style`, `set_layer_role`, `apply_texture_effect`, `apply_depth_haze`, `generate_palette`, `define_gradient`, `apply_line_hierarchy`, `compare_style_consistency` |
| **Groups** | `group_regions`, `ungroup_regions` |
| **Procedural** | `create_line_pattern`, `generate_shape` (19 patterns: armature, segmented_chain, radial_spread, speech_bubble, create_burst, cornice, awning, rooftop_props, isometric_box, attach, ...) |
| **View** | `render_preview`, `describe_scene`, `critique`, `checkpoint_diff`, `render_diff` |
| **History** | `checkpoint`, `restore`, `get_history`, `batch` |

### Coordinates

All coordinates are normalized 0.0–1.0 where `(0, 0)` = top-left and `(1, 1)` = bottom-right.

### Isometric Box — 5 calls for a table with 4 legs

```json
// Frame — one call
{"pattern": "isometric_box", "params": {"new_prefix": "frame",
  "x": 0.35, "y": 0.35, "width": 0.35, "depth": 0.22, "height": 0.05,
  "fill": "#A0522D", "z_index": 5, "shadow": true}}

// Legs — attach by named anchor, zero coordinate math
{"pattern": "attach", "params": {"parent": "frame_top",
  "parent_anchor": "bottom_left", "child_anchor": "top_left_corner",
  "width": 0.06, "depth": 0.06, "height": 0.15, "fill": "#666",
  "flush": true, "z_index": 0}}

{"pattern": "attach", "params": {"parent": "frame_top",
  "parent_anchor": "bottom_right", "child_anchor": "top_right_corner",
  "width": 0.06, "depth": 0.06, "height": 0.15, "fill": "#555",
  "flush": true, "z_index": 0}}

{"pattern": "attach", "params": {"parent": "frame_top",
  "parent_anchor": "bottom_back_left", "child_anchor": "top_left_corner",
  "width": 0.06, "depth": 0.06, "height": 0.15, "fill": "#777",
  "flush": true, "z_index": 0}}

{"pattern": "attach", "params": {"parent": "frame_top",
  "parent_anchor": "bottom_back_right", "child_anchor": "top_right_corner",
  "width": 0.06, "depth": 0.06, "height": 0.15, "fill": "#888",
  "flush": true, "z_index": 0}}
```

### Text with Isometric Perspective

```json
// Text skewed to match a right face (slope = -30°)
{"tool": "create_text", "x": 0.25, "y": 0.55, "text": "THE BOOK",
 "font_size": 0.025, "skew_y": -30, "fill": "#FFF", "font_weight": "bold"}
```

### Gradient by Name

```json
{"tool": "define_gradient", "name": "gold_top", "stops": [
  {"offset": 0, "color": "#FFD700"}, {"offset": 1, "color": "#DAA520"}], "angle": 160}

{"tool": "restyle", "fill_gradient": "gold_top", "selector": {"ids": ["panel_1"]}}
```

### Material Presets

```json
{"tool": "restyle", "selector": {"ids": ["window"]}, "material": "glass"}
{"tool": "restyle", "selector": {"ids": ["floor"]}, "material": "tile", "material_intensity": 0.8}
```

## Architecture

```
avge_engine/
├── controllers/      # MCP tool definitions (region, scene_ops, style, procedural, ...)
├── scene/            # Scene graph (graph.py, models.py)
├── geometry/         # Curve fitting, procedural patterns, types
├── effects/          # Style dataclass, HSL color transforms
├── renderer/         # SVG serializer + PNG rasterization
├── services/         # Engine service, document persistence
├── api.py            # FastAPI HTTP server
└── server.py         # MCP server setup (FastMCP)
```

- **Python 3.12** with FastMCP (MCP SDK)
- **Normalized coordinates**, resolved at render time
- **Catmull-Rom → cubic Bézier** curve fitting (deterministic, closed-form)
- **SVG output** with text, images, gradient defs, skew transforms
- **PNG preview** via rsvg-convert with fontconfig/Unicode support
- **JSON file persistence** per document
