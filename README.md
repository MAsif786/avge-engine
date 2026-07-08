# AVGE MVP — AI-Native Vector Graphics Engine Validation Spike

**Status:** ✅ Built & Tested  
**Version:** 0.1.0  

A minimal MCP server to test whether a general-purpose LLM can produce usable vector art through a coarse-outline + JSON-tool-call interface.

## Quick Start

```bash
.venv/bin/python -m avge_mvp          # Start MCP server (stdio)
.venv/bin/python tests/smoke_test.py  # Run smoke tests
.venv/bin/python run_benchmarks.py    # Run all 5 benchmark evaluations
```

## 5 MCP Tools

| Tool | Description |
|---|---|
| `create_document` | Set up canvas (width, height, bg color) |
| `create_region` | Draw shape from coarse point outline + constraints |
| `style_objects` | Update fill/stroke/opacity on existing regions |
| `describe_scene` | Text feedback — object list, bounds, warnings |
| `render_preview` | Visual feedback — base64 PNG via cairosvg |

## Benchmark Results

| Prompt | Regions | Tool Calls | Result |
|---|---|---|---|
| ☕ Coffee cup | 5 (body, rim, handle, liquid, saucer) | 8 | ✅ |
| 🏠 House icon | 6 (walls, roof, door, 2 windows, chimney) | 9 | ✅ |
| 😊 Smiley face | 4 (face, 2 eyes, mouth) | 7 | ✅ |
| 🌳 Tree | 6 (trunk, 4 foliage layers, ground) | 9 | ✅ |
| ⭐ Five-pointed star | 1 (10-point star polygon) | 4 | ✅ |

Output SVGs: `output/svg/` directory  
Preview PNGs: `output/*/preview_*.png`

## Project Structure

```
avge/
├── avge_mvp/
│   ├── server.py         # MCP server (5 tools)
│   ├── scene.py          # In-memory scene graph (normalized coords 0.0-1.0)
│   ├── curve_engine.py   # Catmull-Rom → cubic Bézier (closed-form, deterministic)
│   └── renderer.py       # SVG serializer + cairosvg raster preview
├── tests/smoke_test.py   # 8 unit tests
├── run_benchmarks.py     # Automated benchmark runner
├── eval_harness.py       # Evaluation harness (dry-run/interactive/summary)
├── gen_svgs.py           # Generate SVGs from benchmark definitions
├── prompts/benchmark.json # 5 benchmark prompt definitions
└── output/               # Generated artifacts
```

## Architecture

- **Python 3.12** with MCP SDK (`mcp` 1.x)
- **Normalized coordinates** (0.0–1.0), resolved to canvas pixels at render time
- **Curve fitting**: closed-form Catmull-Rom → cubic Bézier via numpy (no iterative/adaptive algorithms — fully deterministic)
- **Deterministic SVG**: float rounding to 6 decimal places, fixed attribute ordering
- **Raster preview**: SVG → PNG via cairosvg
- In-memory only, single document per process (MVP scope)
