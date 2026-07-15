"""
Raster preview — SVG → PNG rasterization.

§12.1: M0b uses rsvg-convert (librsvg) for rasterization. It provides
proper Unicode symbol rendering via Pango/fontconfig, unlike cairosvg
which uses a limited font stack. Falls back to cairosvg if rsvg-convert
is unavailable.
"""

from __future__ import annotations

import base64
import subprocess
import tempfile


def render_preview_png(svg_string: str, scale: float = 1.0) -> bytes:
    """Render an SVG string to PNG bytes.

    Uses rsvg-convert for proper Unicode/emoji/symbol rendering.
    Falls back to cairosvg if rsvg-convert is not available.
    """
    # Try rsvg-convert first (better symbol/Unicode support)
    try:
        return _render_rsvg(svg_string, scale)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Fallback to cairosvg
    try:
        return _render_cairo(svg_string, scale)
    except ImportError:
        raise RuntimeError("No SVG rasterizer available (try: brew install librsvg)")


def _render_rsvg(svg_string: str, scale: float = 1.0) -> bytes:
    """Render SVG to PNG using rsvg-convert (librsvg)."""
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w") as f:
        f.write(svg_string)
        svg_path = f.name

    png_path = svg_path + ".png"
    try:
        subprocess.run(
            [
                "rsvg-convert",
                "--background-color=white",
                "--format=png",
                f"--zoom={scale}",
                "--output=" + png_path,
                svg_path,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        with open(png_path, "rb") as f:
            return f.read()
    finally:
        import os
        try:
            os.unlink(svg_path)
            os.unlink(png_path)
        except OSError:
            pass


def _render_cairo(svg_string: str, scale: float = 1.0) -> bytes:
    """Render SVG to PNG using cairosvg (fallback)."""
    import cairosvg

    return cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"),
        scale=scale,
    )


def render_preview_base64(svg_string: str, scale: float = 1.0) -> str:
    """Render SVG to PNG and return as data-URI-safe base64."""
    png_bytes = render_preview_png(svg_string, scale)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"
