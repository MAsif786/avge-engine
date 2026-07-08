"""
Deterministic SVG serializer.

§8.3 rules applied:
  - Float rounding to 6 decimal places at every serialization boundary.
  - Fixed attribute ordering.
  - No RNG, no wall-clock, no thread-sensitive ordering.

Gradient fill support: regions with gradient fills generate <defs>
entries and reference them via url(#grad_xxx). All defs are emitted
before any <path> elements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avge_engine.scene import SceneGraph

from avge_engine.geometry import compute_bounds, fit_curves
from avge_engine.effects import resolve_fill, resolve_stroke, is_gradient, gradient_to_svg_def


def svg_serialize(scene: SceneGraph) -> str:
    """Produce a canonical SVG string from the scene graph.

    Returns byte-identical SVG for identical scene graph input.
    """
    if not scene._last_doc_id or not scene.has_document(scene._last_doc_id):
        return ""  # No document to render
    doc = scene.get_document(scene._last_doc_id)
    regions = scene.get_all_regions(scene._last_doc_id)

    # Collect gradient definitions
    gradient_defs: list[str] = []
    for region in regions:
        if is_gradient(region.style.fill):
            gdef = gradient_to_svg_def(region.style.fill)
            if gdef not in gradient_defs:
                gradient_defs.append(gdef)

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg"',
        f'     width="{doc.width}" height="{doc.height}"',
        f'     viewBox="0 0 {doc.width} {doc.height}">',
    ]

    # Background
    lines.append(f'  <rect width="100%" height="100%" fill="{doc.background}"/>')

    # Gradient defs (if any)
    if gradient_defs:
        lines.append("  <defs>")
        lines.extend(gradient_defs)
        lines.append("  </defs>")

    # Clip path defs
    for region in regions:
        if region.clip_to:
            clip_r = next((r for r in regions if r.id == region.clip_to), None)
            if clip_r and clip_r.outline:
                segs = fit_curves(clip_r.outline, closed=clip_r.constraints.closed,
                    smoothness=clip_r.constraints.smoothness,
                    tensions=list(clip_r.constraints.tensions) if clip_r.constraints.tensions else None)
                if segs:
                    pd = _build_path_data(segs, doc.width, doc.height, clip_r.constraints.closed)
                    lines.append(f'  <clipPath id="clip_{region.clip_to}">')
                    lines.append(f'    <path d="{pd}"/>')
                    lines.append(f'  </clipPath>')

    # Path elements
    for region in regions:
        svg_elem = _region_to_path(region, doc.width, doc.height)
        if svg_elem:
            lines.append(svg_elem)

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _region_to_path(region, canvas_w: int, canvas_h: int) -> str | None:
    """Convert a single region to an SVG <path> element or None."""
    if not region.outline:
        return None

    segments = fit_curves(
        region.outline,
        closed=region.constraints.closed,
        smoothness=region.constraints.smoothness,
        tensions=list(region.constraints.tensions) if region.constraints.tensions else None,
    )
    if not segments:
        return None

    # Build path data
    path_data = _build_path_data(segments, canvas_w, canvas_h, region.constraints.closed)

    # Style
    fill = resolve_fill(region.style.fill)
    stroke = resolve_stroke(region.style.stroke)
    sw = _fmt(region.style.stroke_width * min(canvas_w, canvas_h))

    parts = [f'    <path d="{path_data}"']
    parts.append(f' fill="{fill}" stroke="{stroke}" stroke-width="{sw}"')

    if region.style.opacity < 1.0:
        parts.append(f' opacity="{_fmt(region.style.opacity)}"')

    if region.style.blend_mode:
        parts.append(f' style="mix-blend-mode:{region.style.blend_mode}"')

    if region.clip_to:
        parts.append(f' clip-path="url(#clip_{region.clip_to})"')

    # Transform
    tx, ty = region.transform.translate
    rot = region.transform.rotate
    sx, sy = region.transform.scale
    has_transform = tx != 0 or ty != 0 or rot != 0 or sx != 1 or sy != 1
    if has_transform:
        t_parts = []
        if sx != 1 or sy != 1:
            t_parts.append(f"scale({_fmt(sx)},{_fmt(sy)})")
        if rot != 0:
            bounds = compute_bounds(region.outline)
            if bounds:
                cx = _fmt((bounds["x"] + bounds["w"] / 2) * canvas_w)
                cy = _fmt((bounds["y"] + bounds["h"] / 2) * canvas_h)
                t_parts.append(f"rotate({_fmt(rot)},{cx},{cy})")
        if tx != 0 or ty != 0:
            t_parts.append(f"translate({_fmt(tx * canvas_w)},{_fmt(ty * canvas_h)})")
        parts.append(f' transform="{" ".join(t_parts)}"')

    parts.append("/>")
    return "".join(parts)


def _build_path_data(segments, scale_x: float, scale_y: float, closed: bool) -> str:
    """Build SVG path 'd' attribute from cubic Bézier segments."""
    if not segments:
        return ""
    parts: list[str] = []
    for i, seg in enumerate(segments):
        p0, p1, p2, p3 = seg
        if i == 0:
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
    """Deterministic float formatting — 6 decimal places, no trailing zeros."""
    rounded = round(value, 6)
    s = f"{rounded:.6f}".rstrip("0").rstrip(".")
    return s if s and s != "-0" else "0"
