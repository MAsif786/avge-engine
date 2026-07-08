"""
Raster preview — SVG → PNG rasterization.

§12.1: M0b uses cairosvg for rasterization (same as MVP).
resvg (§12.1, row "Renderer (rasterization)") will be the production path;
cairosvg is the pragmatic M0b choice while the full build out is underway.
"""

from __future__ import annotations

import base64


def render_preview_png(svg_string: str, scale: float = 1.0) -> bytes:
    """Render an SVG string to PNG bytes."""
    try:
        import cairosvg
    except ImportError:
        raise RuntimeError("cairosvg is required for rasterization")

    return cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"),
        scale=scale,
    )


def render_preview_base64(svg_string: str, scale: float = 1.0) -> str:
    """Render SVG to PNG and return as data-URI-safe base64."""
    png_bytes = render_preview_png(svg_string, scale)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"
