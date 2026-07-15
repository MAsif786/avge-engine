# AVGE Engine — AI-Native Vector Graphics Engine

**Version:** 0.5.0 | **Tool set:** m0b-v1

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
- **Procedural geometry** — radial spread, offset outlines, guide lines, building chains, speech bubbles, bursts, armature skeletons, foreshortening
- **Armature skeletons** — node-edge graphs with tapered segments, junction separation, filleted V-gaps, curved Catmull-Rom chains, and unary union merging
- **Boolean operations** — union, intersect, subtract, xor with Ramer-Douglas-Peucker simplification
- **HSL shading** — auto highlight + shadow from light direction
- **Primitives** — rects (including tapered/trapezoid), ellipses, lines, polylines, arcs, polygons, stars
- **Text + images** — SVG text with font family/style/anchor, embedded images via `<image>`
- **Gradient backgrounds** — linear and radial gradient definitions
- **Style system** — fill, stroke, stroke-width, opacity, blend modes, dash patterns
- **Batch operations** — execute multiple tools in one call, edit multiple regions with per-region transforms
- **Palette generation** — HSL harmony presets (complementary, triadic, analogous, etc.)
- **Cross-document copy** — copy elements between documents with offset
- **SVG arc support** — A/a commands in `import_svg_path` (elliptical arcs with sweep/large-arc flags)
- **Relative positioning** — place elements relative to a parent region's bounding box
- **PNG rasterization** — via rsvg-convert (librsvg) with Unicode/emoji font support
- **Per-document tracking** — checkpoint/restore history, tool usage stats

## 42+ MCP Tools

| Category | Tools |
|----------|-------|
| **Document** | `create_document`, `list_documents`, `set_background`, `get_document_stats` |
| **Create** | `create_region`, `create_primitive`, `create_curve`, `create_text`, `insert_image`, `import_svg_path` |
| **Edit** | `edit_region` (point-level nudge), `edit_regions` (batch transforms), `delete_region`, `copy_element` |
| **Transform** | `transform_objects`, `duplicate`, `boolean_operation`, `mirror_region` |
| **Style** | `restyle`, `add_shading`, `generate_palette`, `define_gradient`, `apply_line_hierarchy`, `compare_style_consistency` |
| **Groups** | `group_regions`, `ungroup_regions` |
| **Procedural** | `generate_shape` (14+ patterns: armature, segmented_chain, radial_spread, speech_bubble, create_burst, foreshorten, etc.) |
| **View** | `render_preview`, `describe_scene`, `checkpoint_diff`, `render_diff` |
| **History** | `checkpoint`, `restore`, `get_history`, `batch` |

### Coordinates

All coordinates are normalized 0.0–1.0 where `(0, 0)` = top-left and `(1, 1)` = bottom-right.

### Relative Positioning

Create tools accept `relative_to` — pass a region ID and coordinates become 0–1 fractions of that region's bounding box:

```json
{"tool": "create_primitive", "shape": {"type":"ellipse","cx":0.5,"cy":0.5,"rx":0.1}, "relative_to": "belt_panel"}
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
- **SVG output** with text, images, gradient defs
- **PNG preview** via rsvg-convert with fontconfig/Unicode support
- **JSON file persistence** per document
