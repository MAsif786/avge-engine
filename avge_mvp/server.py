"""
AVGE MVP — MCP Server with 5 tools.

This is the primary interface an LLM interacts with. The 5 tools implement
the minimal validation spike from the MVP TDD v0.1.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from avge_mvp.scene import (
    SceneGraph,
    CurveConstraints,
    Style,
    Transform,
)
from avge_mvp.renderer import svg_serialize, rasterize_to_base64

# ── Global scene graph instance (MVP: single in-memory document) ────
_scene: SceneGraph | None = None


def _get_scene() -> SceneGraph:
    global _scene
    if _scene is None:
        _scene = SceneGraph()
    return _scene


# ── Server Setup ────────────────────────────────────────────────────

mcp = FastMCP(
    "AVGE MVP",
    instructions="""AI-Native Vector Graphics Engine — MVP Validation Spike.

You have 5 tools to create and inspect vector graphics:

1. **create_document** — Set up a canvas (required first).
2. **create_region** — Draw a shape by supplying a coarse point outline
   and geometric constraints (smoothness, closed/open).
3. **style_objects** — Change fill color, stroke color, stroke width,
   and opacity on existing regions.
4. **describe_scene** — Get a text description of everything on the canvas
   (object list, bounds, warnings). Use this to inspect your work.
5. **render_preview** — Get a visual PNG preview of the current canvas.
   Returns a base64-encoded image.

Guidelines:
- Coordinates are normalized 0.0–1.0, where (0,0) = top-left, (1,1) = bottom-right.
- Keep outlines to 3–30 points for best curve quality. Use smoothness/closed
  constraints to control shape instead of adding more points.
- You can call describe_scene and render_preview as many times as you like
  to iterate and refine.
""",
)


# ── Tool 1: create_document ──────────────────────────────────────────

@mcp.tool()
def create_document(
    width: int = 1000,
    height: int = 1000,
    unit: str = "px",
    background: str = "#FFFFFF",
) -> str:
    """Create a new canvas. Must be called first before any other tool.

    Args:
        width: Canvas width in pixels (default 1000).
        height: Canvas height in pixels (default 1000).
        unit: Unit of measurement (default "px").
        background: Background color as hex string (default "#FFFFFF").

    Returns:
        Confirmation with document details.
    """
    scene = _get_scene()
    try:
        doc = scene.create_document(
            width=max(100, min(width, 4000)),
            height=max(100, min(height, 4000)),
            unit=unit,
            background=background,
        )
        return (
            f"Document created: id={doc.id}, "
            f"{doc.width}x{doc.height} {doc.unit}, "
            f"background={doc.background}\n\n"
            f"💡 Tip: before styling, see resource avge://skill/design-guidelines "
            f"— flat single-tone fills on every region is a common miss."
        )
    except RuntimeError as e:
        return f"Error: {e}"


# ── Tool 2: create_region ───────────────────────────────────────────

@mcp.tool()
def create_region(
    outline: list[list[float]],
    region_id: str | None = None,
    layer: str = "default",
    closed: bool = True,
    smoothness: float = 0.5,
    corner_style: str = "round",
    fill: str | None = "#CCCCCC",
    stroke: str | None = "#333333",
    stroke_width: float = 0.005,
    opacity: float = 1.0,
    metadata_tags: list[str] | None = None,
) -> str:
    """Create a vector region from a coarse point outline.

    This is the core drawing primitive. Supply a series of (x, y) coordinate
    pairs and the engine will fit smooth Bézier curves to them.

    Design guidance: for filled shapes, prefer two-tone shading (a base fill
    + a darker adjacent region along one edge) over a single flat fill to
    imply depth. See avge://skill/design-guidelines for full conventions.

    Args:
        outline: List of [x, y] coordinate pairs in normalized space (0.0–1.0).
            ⚠️ NOT pixel coordinates. (0,0)=top-left, (1,1)=bottom-right.
            Keep to 3–30 points for best results.
        region_id: Optional unique ID for the region (auto-generated if omitted).
        layer: Layer name for organization (default "default").
        closed: Whether the shape is closed (True) or an open path (False).
        smoothness: Curve smoothness 0.0–1.0 (0.0=sharp/polygonal, 1.0=very smooth).
        corner_style: Corner treatment — "round", "sharp", or "bevel".
        fill: Fill color as hex string, or "none" for no fill (default "#CCCCCC").
        stroke: Stroke color as hex string, or "none" for no stroke (default "#333333").
        stroke_width: Stroke width in normalized units (default 0.005).
        opacity: Object opacity 0.0–1.0 (default 1.0).
        metadata_tags: Optional list of semantic tags (stored as opaque strings).

    Returns:
        Confirmation with region ID and derived bounds.
    """
    scene = _get_scene()

    # Validate outline
    if not outline or len(outline) < 2:
        return "Error: Outline must have at least 2 points"
    if len(outline) > 200:
        return (
            f"Warning: outline has {len(outline)} points; "
            f"consider fewer points + smoothness constraints for better curve quality. "
            f"Region not created."
        )

    # Pass raw outline (normalize_outline validates range internally)
    norm_outline = [(float(pt[0]), float(pt[1])) for pt in outline]

    constraints = CurveConstraints(
        smoothness=max(0.0, min(1.0, smoothness)),
        closed=closed,
        corner_style=corner_style,
    )
    style = Style(
        fill=fill if fill and fill.lower() != "none" else None,
        stroke=stroke if stroke and stroke.lower() != "none" else None,
        stroke_width=max(0.001, min(0.1, stroke_width)),
        opacity=max(0.0, min(1.0, opacity)),
    )

    try:
        region = scene.create_region(
            region_id=region_id,
            layer=layer,
            outline=norm_outline,
            constraints=constraints,
            style=style,
        )
    except (ValueError, RuntimeError) as e:
        return f"Error: {e}"

    bounds = scene._compute_bounds(region)  # noqa: SLF001 — MVP only
    bounds_str = (
        f"x={bounds['x']:.4f} y={bounds['y']:.4f} "
        f"w={bounds['w']:.4f} h={bounds['h']:.4f}"
        if bounds
        else "N/A"
    )
    warning = ""
    if len(outline) > 30:
        warning = (
            f" Advisory: outline has {len(outline)} points. "
            f"Use fewer points + smoothness constraints for better curve quality."
        )

    return (
        f"Region created: id={region.id}, layer={region.layer}, "
        f"bounds=({bounds_str}), outline_points={len(outline)}"
        f"{warning}"
    )


# ── Tool 3: style_objects ───────────────────────────────────────────

@mcp.tool()
def style_objects(
    ids: list[str],
    fill: str | None = None,
    stroke: str | None = None,
    stroke_width: float | None = None,
    opacity: float | None = None,
) -> str:
    """Update the visual style of one or more existing regions.

    Only provided parameters are changed; omitted parameters are left untouched.

    Design guidance: vary stroke width by hierarchy — heavier for outer
    silhouette, lighter for internal detail — rather than using one width
    throughout. See avge://skill/design-guidelines for full conventions.

    Args:
        ids: List of region IDs to style.
        fill: Fill color as hex string (e.g. "#FF0000"), or "none" for no fill.
        stroke: Stroke color as hex string, or "none" for no stroke.
        stroke_width: Stroke width in normalized units (e.g. 0.01).
        opacity: Object opacity 0.0–1.0.

    Returns:
        List of affected region IDs.
    """
    scene = _get_scene()

    resolved_fill = fill if fill is None or fill.lower() == "none" else fill
    resolved_stroke = stroke if stroke is None or stroke.lower() == "none" else stroke
    resolved_sw = max(0.001, min(0.1, stroke_width)) if stroke_width is not None else None
    resolved_opacity = max(0.0, min(1.0, opacity)) if opacity is not None else None

    try:
        affected = scene.style_objects(
            ids=ids,
            fill=resolved_fill,
            stroke=resolved_stroke,
            stroke_width=resolved_sw,
            opacity=resolved_opacity,
        )
    except RuntimeError as e:
        return f"Error: {e}"

    if not affected:
        return "No matching regions found"
    return f"Styled {len(affected)} region(s): {', '.join(affected)}"


# ── Tool 4: describe_scene ──────────────────────────────────────────

@mcp.tool()
def describe_scene(detail: str = "summary") -> str:
    """Get a text description of the current canvas contents.

    Use this to inspect what you've drawn — object counts, positions,
    bounds, and any warnings about off-canvas objects.

    Args:
        detail: Level of detail — "summary" (default) or "full" (includes
            all outline coordinates).

    Returns:
        A structured text description of the scene.
    """
    scene = _get_scene()
    try:
        desc = scene.describe_scene(detail=detail)
    except RuntimeError as e:
        return f"Error: {e}"

    lines: list[str] = []
    d = desc["document"]
    lines.append(f"Document: {d['id']}")
    lines.append(f"Canvas: {d['width']}x{d['height']} {d['unit']}, bg={d['background']}")
    lines.append(f"Version: {d['version']}")
    lines.append(f"Region count: {desc['region_count']}")
    lines.append("")

    if not desc["regions"]:
        lines.append("(No regions on canvas)")
    else:
        for r in desc["regions"]:
            bounds = r.get("bounds")
            bounds_str = (
                f"x={bounds['x']:.4f} y={bounds['y']:.4f} "
                f"w={bounds['w']:.4f} h={bounds['h']:.4f}"
                if bounds
                else "no bounds"
            )
            lines.append(f"  [{r['id']}] layer={r['layer']}")
            lines.append(f"    Bounds: {bounds_str}")
            lines.append(f"    Outline: {r['outline_point_count']} pts, "
                         f"{'closed' if r['closed'] else 'open'}, "
                         f"smoothness={r['smoothness']}")
            lines.append(f"    Style: fill={r['style']['fill']}, "
                         f"stroke={r['style']['stroke']}, "
                         f"width={r['style']['stroke_width']}")
            lines.append("")

    if desc.get("warnings"):
        lines.append("Warnings:")
        for w in desc["warnings"]:
            lines.append(f"  ⚠ {w}")

    return "\n".join(lines)


# ── Tool 5: render_preview ──────────────────────────────────────────

@mcp.tool()
def render_preview(scale: float = 1.0) -> str:
    """Get a visual PNG preview of the current canvas as a base64-encoded image.

    Use this to visually inspect your work. The image is rendered from the
    current scene graph state.

    Args:
        scale: Render scale factor (1.0 = full resolution, 0.5 = half, etc.).
            Default 1.0. Minimum 0.25, maximum 2.0.

    Returns:
        Base64-encoded PNG image data.
    """
    scene = _get_scene()

    try:
        svg = svg_serialize(scene)
    except RuntimeError as e:
        return f"Error: {e}"

    scale = max(0.25, min(2.0, scale))

    try:
        b64 = rasterize_to_base64(svg, scale=scale)
    except RuntimeError as e:
        return f"Error rendering preview: {e}"

    return f"data:image/png;base64,{b64}"


# ── Entry ───────────────────────────────────────────────────────────

def run() -> None:
    """Run the MCP server using stdio transport (default for MCP SDK)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
