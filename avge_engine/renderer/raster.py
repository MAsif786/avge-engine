"""
Raster preview — SVG to PNG/PDF/JPEG rendering.

§12.1: M0b uses rsvg-convert (librsvg) for rasterization. It provides
proper Unicode symbol rendering via Pango/fontconfig, unlike cairosvg
which uses a limited font stack. Falls back to cairosvg if rsvg-convert
is unavailable.
"""

from __future__ import annotations

import base64
import io
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
    return _render_rsvg_format(svg_string, "png", scale=scale, background=True)


def render_preview_pdf(svg_string: str) -> bytes:
    """Render an SVG string to PDF bytes."""
    try:
        return _render_rsvg_format(svg_string, "pdf")
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    try:
        import cairosvg

        return cairosvg.svg2pdf(bytestring=svg_string.encode("utf-8"))
    except ImportError:
        raise RuntimeError("No SVG PDF renderer available (try: brew install librsvg)")


def render_preview_jpeg(svg_string: str, scale: float = 1.0, quality: int = 92) -> bytes:
    """Render an SVG string to JPEG bytes via PNG + Pillow."""
    from PIL import Image

    png = render_preview_png(svg_string, scale=scale)
    with Image.open(io.BytesIO(png)) as image:
        rgb = image.convert("RGB")
        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=max(1, min(quality, 100)), optimize=True)
        return out.getvalue()


def _render_rsvg_format(
    svg_string: str,
    output_format: str,
    *,
    scale: float = 1.0,
    background: bool = False,
) -> bytes:
    """Render SVG using rsvg-convert in the requested output format."""
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w") as f:
        f.write(svg_string)
        svg_path = f.name

    out_path = svg_path + f".{output_format}"
    try:
        cmd = ["rsvg-convert", f"--format={output_format}", f"--output={out_path}"]
        if background:
            cmd.insert(1, "--background-color=white")
        if scale != 1.0:
            cmd.insert(-1, f"--zoom={scale}")
        cmd.append(svg_path)
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        import os
        try:
            os.unlink(svg_path)
            os.unlink(out_path)
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
