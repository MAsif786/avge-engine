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


def svg_serialize(scene: SceneGraph, document_id: str | None = None) -> str:
    """Produce a canonical SVG string from the scene graph.

    Args:
        scene: The scene graph instance.
        document_id: Specific doc to render (uses last active if omitted).

    Returns byte-identical SVG for identical scene graph input.
    """
    doc_id = document_id or scene._last_doc_id
    if not doc_id or not scene.has_document(doc_id):
        return ""  # No document to render
    doc = scene.get_document(doc_id)
    regions = scene.get_all_regions(doc_id)

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

    # Clip path defs (dedup by clip target ID)
    seen_clips: set[str] = set()
    for region in sorted(regions, key=lambda r: r.z_index):
        if region.clip_to and region.clip_to not in seen_clips:
            seen_clips.add(region.clip_to)
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

    # Path elements (sorted by z_index for proper layering)
    for region in sorted(regions, key=lambda r: r.z_index):
        svg_elem = _region_to_path(region, doc.width, doc.height)
        if svg_elem:
            lines.append(svg_elem)

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _region_to_path(region, canvas_w: int, canvas_h: int) -> str | None:
    """Convert a single region to an SVG element. Handles both primitives and paths."""
    canvas_min = min(canvas_w, canvas_h)

    # Common style attributes
    stroke = resolve_stroke(region.style.stroke)
    sw = _fmt(region.style.stroke_width * canvas_min)
    fill = resolve_fill(region.style.fill)

    def _append_style(parts: list[str]) -> None:
        parts.append(f' fill="{fill}" stroke="{stroke}" stroke-width="{sw}"')
        if region.style.opacity < 1.0:
            parts.append(f' opacity="{_fmt(region.style.opacity)}"')
        if region.style.blend_mode:
            parts.append(f' style="mix-blend-mode:{region.style.blend_mode}"')
        if region.style.stroke_linecap:
            parts.append(f' stroke-linecap="{region.style.stroke_linecap}"')
        if region.clip_to:
            parts.append(f' clip-path="url(#clip_{region.clip_to})"')

    def _append_transform(parts: list[str], cx: float, cy: float) -> None:
        tx, ty = region.transform.translate
        rot = region.transform.rotate
        sx, sy = region.transform.scale
        t_parts = []
        if sx != 1 or sy != 1:
            t_parts.append(f"scale({_fmt(sx)},{_fmt(sy)})")
        if rot != 0:
            t_parts.append(f"rotate({_fmt(rot)},{_fmt(cx * canvas_w)},{_fmt(cy * canvas_h)})")
        if tx != 0 or ty != 0:
            t_parts.append(f"translate({_fmt(tx * canvas_w)},{_fmt(ty * canvas_h)})")
        if t_parts:
            parts.append(f' transform="{" ".join(t_parts)}"')

    # ── Primitive shapes ───────────────────────────────────────────
    if region.primitive:
        ptype = region.primitive.get("type")
        if ptype == "rect":
            x = region.primitive["x"] * canvas_w
            y = region.primitive["y"] * canvas_h
            w = region.primitive["width"] * canvas_w
            h = region.primitive["height"] * canvas_h
            rx = region.primitive.get("rx", 0) * canvas_min
            rx_attr = f' rx="{_fmt(rx)}"' if rx > 0 else ""
            parts = [f'    <rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}"{rx_attr}']
            _append_style(parts)
            _append_transform(parts, region.primitive["x"] + region.primitive["width"] / 2,
                              region.primitive["y"] + region.primitive["height"] / 2)
            parts.append("/>")
            return "".join(parts)

        if ptype == "ellipse":
            cx = region.primitive["cx"] * canvas_w
            cy = region.primitive["cy"] * canvas_h
            rxx = region.primitive["rx"] * canvas_w
            ryy = region.primitive["ry"] * canvas_h
            parts = [f'    <ellipse cx="{_fmt(cx)}" cy="{_fmt(cy)}" rx="{_fmt(rxx)}" ry="{_fmt(ryy)}"']
            _append_style(parts)
            _append_transform(parts, region.primitive["cx"], region.primitive["cy"])
            parts.append("/>")
            return "".join(parts)

        if ptype == "line":
            x1 = region.primitive["x1"] * canvas_w
            y1 = region.primitive["y1"] * canvas_h
            x2 = region.primitive["x2"] * canvas_w
            y2 = region.primitive["y2"] * canvas_h
            mid_x = (region.primitive["x1"] + region.primitive["x2"]) / 2
            mid_y = (region.primitive["y1"] + region.primitive["y2"]) / 2
            parts = [f'    <line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}"']
            _append_style(parts)
            _append_transform(parts, mid_x, mid_y)
            parts.append("/>")
            return "".join(parts)

    # ── Polygon / polyline mode (smoothness ≈ 0 — straight lines) ──
    if region.constraints.smoothness <= 0.001 and region.outline and not region.primitive:
        pts = " ".join(
            f"{_fmt(p[0] * canvas_w)},{_fmt(p[1] * canvas_h)}"
            for p in region.outline
        )
        tag = "polygon" if region.constraints.closed else "polyline"
        parts = [f'    <{tag} points="{pts}"']
        _append_style(parts)
        bounds = compute_bounds(region.outline)
        if bounds:
            _append_transform(parts, bounds["x"] + bounds["w"] / 2, bounds["y"] + bounds["h"] / 2)
        parts.append("/>")
        return "".join(parts)

    # ── Path-based regions (fallback) ──────────────────────────────
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

    path_data = _build_path_data(segments, canvas_w, canvas_h, region.constraints.closed)

    parts = [f'    <path d="{path_data}"']

    _append_style(parts)

    # Transform (use center of bounds for path-based regions)
    if region.outline:
        bounds = compute_bounds(region.outline)
        if bounds:
            _append_transform(parts, bounds["x"] + bounds["w"] / 2, bounds["y"] + bounds["h"] / 2)

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
