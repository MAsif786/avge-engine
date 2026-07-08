"""
Deterministic SVG serializer and raster preview generator.

The serializer produces byte-identical SVG for identical scene graph input
(consistent attribute ordering, fixed float precision, no RNG).

Flush: svg_serialize(scene_graph) → SVG string
       rasterize(svg_string, scale) → PNG bytes
"""

from __future__ import annotations

import io
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avge_mvp.scene import SceneGraph

from avge_mvp.curve_engine import fit_curves


# ── SVG Serializer ───────────────────────────────────────────────────

def svg_serialize(scene: SceneGraph) -> str:
    """
    Produce a canonical SVG string from the scene graph.

    Deterministic guarantees:
    - Float values rounded to 6 decimal places.
    - Attribute order is fixed (alphabetical by default for stable output).
    - No RNG, no wall-clock, no thread-sensitive ordering.
    """
    doc = scene.document
    regions = scene.get_all_regions_sorted()

    # SVG header
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg"',
        f'     width="{doc.width}" height="{doc.height}"',
        f'     viewBox="0 0 {doc.width} {doc.height}">',
        f'  <rect width="100%" height="100%" fill="{doc.background}"/>',
    ]

    for region in regions:
        if not region.outline:
            continue

        # Fit curves to the outline
        segments = fit_curves(
            region.outline,
            closed=region.constraints.closed,
            smoothness=region.constraints.smoothness,
            _corner_style=region.constraints.corner_style,
        )

        if not segments:
            continue

        scale_x = doc.width
        scale_y = doc.height

        # Build the SVG path data string
        path_data = _build_path_data(segments, scale_x, scale_y, region.constraints.closed)

        # Style attributes
        fill = region.style.fill or "none"
        stroke = region.style.stroke or "none"
        sw = _fmt(region.style.stroke_width * min(doc.width, doc.height))
        opacity = _fmt(region.style.opacity) if region.style.opacity < 1.0 else None

        # Transform
        tx, ty = region.transform.translate
        rot = region.transform.rotate
        sx, sy = region.transform.scale
        has_transform = tx != 0 or ty != 0 or rot != 0 or sx != 1 or sy != 1

        parts = [f'    <path d="{path_data}"']
        parts.append(f' fill="{fill}" stroke="{stroke}" stroke-width="{sw}"')
        if opacity is not None:
            parts.append(f' opacity="{opacity}"')
        if has_transform:
            transform_parts = []
            if sx != 1 or sy != 1:
                transform_parts.append(f"scale({_fmt(sx)},{_fmt(sy)})")
            if rot != 0:
                cx = _fmt(region.style.stroke_width * min(doc.width, doc.height) / 2)
                cy = _fmt(region.style.stroke_width * min(doc.width, doc.height) / 2)
                transform_parts.append(f"rotate({_fmt(rot)},{cx},{cy})")
            if tx != 0 or ty != 0:
                transform_parts.append(f"translate({_fmt(tx * scale_x)},{_fmt(ty * scale_y)})")
            parts.append(f' transform="{" ".join(transform_parts)}"')
        parts.append("/>")
        lines.append("".join(parts))

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _build_path_data(
    segments: list[list[tuple[float, float]]],
    scale_x: float,
    scale_y: float,
    closed: bool,
) -> str:
    """Build an SVG path 'd' attribute from cubic Bézier segments."""
    if not segments:
        return ""

    parts: list[str] = []

    for i, seg in enumerate(segments):
        p0, p1, p2, p3 = seg
        if i == 0:
            # Move to first point
            parts.append(f"M{_fmt(p0[0] * scale_x)},{_fmt(p0[1] * scale_y)}")
        parts.append(
            f"C{_fmt(p1[0] * scale_x)},{_fmt(p1[1] * scale_y)} "
            f"{_fmt(p2[0] * scale_x)},{_fmt(p2[1] * scale_y)} "
            f"{_fmt(p3[0] * scale_x)},{_fmt(p3[1] * scale_y)}"
        )

    if closed and segments:
        parts.append("Z")

    return " ".join(parts)


def _fmt(value: float) -> str:
    """Format a float to 6 decimal places, no trailing zeros if possible.

    This is the single formatting gate for all float → string conversions
    in the renderer, guaranteeing byte-identical output for identical input.
    """
    # Round to 6 decimal places (determinism gate)
    rounded = round(value, 6)
    # Use smallest representation that preserves the value
    s = f"{rounded:.6f}".rstrip("0").rstrip(".")
    # Fallback for "0" case
    if s == "" or s == "-0":
        return "0"
    return s


# ── Raster Preview ──────────────────────────────────────────────────

def rasterize(svg_string: str, scale: float = 1.0) -> bytes:
    """Render an SVG string to PNG bytes using cairosvg."""
    try:
        import cairosvg
    except ImportError:
        raise RuntimeError("cairosvg is required for rasterization")

    png_bytes = cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"),
        scale=scale,
    )
    return png_bytes


def rasterize_to_base64(svg_string: str, scale: float = 1.0) -> str:
    """Render SVG to PNG and return as base64-encoded string."""
    import base64

    png_bytes = rasterize(svg_string, scale)
    return base64.b64encode(png_bytes).decode("ascii")
