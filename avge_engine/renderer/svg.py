"""
Deterministic SVG serializer.

§8.3 rules applied:
  - Float rounding to 6 decimal places at every serialization boundary.
  - Fixed attribute ordering.
  - No RNG, no wall-clock, no thread-sensitive ordering.

Gradient fill support: elements with gradient fills generate <defs>
entries and reference them via url(#grad_xxx). All defs are emitted
before any <path> elements.
"""

from __future__ import annotations

from avge_engine.geometry import fit_curves
from avge_engine.effects import resolve_fill, resolve_stroke, is_gradient, gradient_to_svg_def
from avge_engine.document.models import DocumentNode, ElementNode


def svg_serialize(
    scene,
    document_id: str | None = None,
    exclude_layers: list[str] | None = None,
    exclude_element_ids: list[str] | None = None,
    exclude_prefixes: list[str] | None = None,
) -> str:
    """Produce a canonical SVG string from the current document state.

    Args:
        scene: Object exposing document lookup methods.
        document_id: Specific doc to render (uses last active if omitted).

    Returns byte-identical SVG for identical document input.
    """
    doc_id = document_id or scene.active_document_id()
    if not doc_id or not scene.has_document(doc_id):
        return ""  # No document to render
    doc = scene.get_document(doc_id)
    elements = scene.get_all_elements(doc_id)
    return svg_serialize_document(
        doc,
        elements,
        exclude_layers=exclude_layers,
        exclude_element_ids=exclude_element_ids,
        exclude_prefixes=exclude_prefixes,
    )


def svg_serialize_document(
    doc: DocumentNode,
    elements: list[ElementNode],
    *,
    exclude_layers: list[str] | None = None,
    exclude_element_ids: list[str] | None = None,
    exclude_prefixes: list[str] | None = None,
) -> str:
    """Produce a canonical SVG string from a document and element snapshot."""
    if exclude_layers or exclude_element_ids or exclude_prefixes:
        layer_set = set(exclude_layers or [])
        id_set = set(exclude_element_ids or [])
        prefixes = tuple(exclude_prefixes or [])
        elements = [
            r for r in elements
            if r.layer not in layer_set
            and r.id not in id_set
            and not (prefixes and r.id.startswith(prefixes))
        ]

    # Collect gradient definitions (elements + document background)
    gradient_defs: list[str] = []
    blur_values: set[float] = set()
    for element in elements:
        if element.style.blur > 0:
            blur_values.add(round(element.style.blur, 2))
        if is_gradient(element.style.fill):
            gdef = gradient_to_svg_def(element.style.fill)
            if gdef not in gradient_defs:
                gradient_defs.append(gdef)
        if is_gradient(element.style.stroke):
            gdef = gradient_to_svg_def(element.style.stroke)
            if gdef not in gradient_defs:
                gradient_defs.append(gdef)
    if is_gradient(doc.background):
        gdef = gradient_to_svg_def(doc.background)
        if gdef not in gradient_defs:
            gradient_defs.insert(0, gdef)  # background first

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg"',
        '     xmlns:xlink="http://www.w3.org/1999/xlink"',
        f'     width="{doc.width}" height="{doc.height}"',
        f'     viewBox="0 0 {doc.width} {doc.height}">',
    ]

    # Background (hex color, image URL, or gradient)
    bg = doc.background
    if is_gradient(bg):
        gid = f"bg_{hash(str(bg)) & 0xFFFFFFFF}"
        lines.append(f'  <rect width="100%" height="100%" fill="url(#{gid})"/>')
    elif isinstance(bg, str) and bg.startswith(("http://", "https://", "data:")):
        lines.append(f'  <image width="100%" height="100%" preserveAspectRatio="xMidYMid slice" href="{_escape_xml(bg)}"/>')
    else:
        lines.append(f'  <rect width="100%" height="100%" fill="{bg}"/>')

    # Defs: gradients + blur filters
    has_defs = bool(gradient_defs) or bool(blur_values)
    if has_defs:
        lines.append("  <defs>")
        for gd in gradient_defs:
            lines.append(gd)
        for bv in sorted(blur_values):
            lines.append(f'    <filter id="blur_{bv:.2f}"><feGaussianBlur stdDeviation="{bv:.2f}"/></filter>')
        lines.append("  </defs>")

    # Clip path defs (dedup by clip target ID)
    seen_clips: set[str] = set()
    for element in sorted(elements, key=lambda r: r.z_index):
        if element.clip_to and element.clip_to not in seen_clips:
            seen_clips.add(element.clip_to)
            clip_r = next((r for r in elements if r.id == element.clip_to), None)
            clip_def = _clip_path_definition(clip_r, element.clip_to, doc.width, doc.height) if clip_r else None
            if clip_def:
                lines.extend(clip_def)

    # Path elements (sorted by z_index for proper layering)
    for element in sorted(elements, key=lambda r: r.z_index):
        svg_elem = _element_to_path(element, doc.width, doc.height)
        if svg_elem:
            lines.append(svg_elem)

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _clip_path_definition(element, clip_id: str, canvas_w: int, canvas_h: int) -> list[str] | None:
    """Build a clipPath definition, preserving primitive clip geometry."""
    if element.primitive:
        ptype = element.primitive.get("type")
        if ptype == "rect":
            canvas_min = min(canvas_w, canvas_h)
            x = element.primitive["x"] * canvas_w
            y = element.primitive["y"] * canvas_h
            w = element.primitive["width"] * canvas_w
            h = element.primitive["height"] * canvas_h
            rx = element.primitive.get("rx", 0) * canvas_min
            rx_attr = f' rx="{_fmt(rx)}"' if rx > 0 else ""
            return [
                f'  <clipPath id="clip_{clip_id}">',
                f'    <rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}"{rx_attr}/>',
                "  </clipPath>",
            ]
        if ptype == "ellipse":
            cx = element.primitive["cx"] * canvas_w
            cy = element.primitive["cy"] * canvas_h
            rxx = element.primitive["rx"] * canvas_w
            ryy = element.primitive["ry"] * canvas_h
            return [
                f'  <clipPath id="clip_{clip_id}">',
                f'    <ellipse cx="{_fmt(cx)}" cy="{_fmt(cy)}" rx="{_fmt(rxx)}" ry="{_fmt(ryy)}"/>',
                "  </clipPath>",
            ]

    if not element.outline:
        return None
    segs = fit_curves(
        element.outline,
        closed=element.constraints.closed,
        smoothness=element.constraints.smoothness,
        tensions=list(element.constraints.tensions) if element.constraints.tensions else None,
        handle_in=list(element.constraints.handle_in) if element.constraints.handle_in else None,
        handle_out=list(element.constraints.handle_out) if element.constraints.handle_out else None,
    )
    if not segs:
        return None
    pd = _build_path_data(segs, canvas_w, canvas_h, element.constraints.closed)
    return [
        f'  <clipPath id="clip_{clip_id}">',
        f'    <path d="{pd}"/>',
        "  </clipPath>",
    ]


def _element_to_path(element, canvas_w: int, canvas_h: int) -> str | None:
    """Convert a single element to an SVG element. Handles both primitives and paths."""
    canvas_min = min(canvas_w, canvas_h)

    # Common style attributes
    stroke = resolve_stroke(element.style.stroke)
    sw = _fmt(element.style.stroke_width * canvas_min)
    fill = resolve_fill(element.style.fill)

    def _append_style(parts: list[str], *, include_opacity: bool = True) -> None:
        parts.append(f' fill="{fill}" stroke="{stroke}" stroke-width="{sw}"')
        if include_opacity and element.style.opacity < 1.0:
            parts.append(f' opacity="{_fmt(element.style.opacity)}"')
        if element.style.blend_mode:
            parts.append(f' style="mix-blend-mode:{element.style.blend_mode}"')
        if element.style.stroke_linecap:
            parts.append(f' stroke-linecap="{element.style.stroke_linecap}"')
        if element.style.stroke_dasharray:
            parts.append(f' stroke-dasharray="{element.style.stroke_dasharray}"')
        if element.style.blur > 0:
            parts.append(f' filter="url(#blur_{element.style.blur:.2f})"')
        if element.clip_to:
            parts.append(f' clip-path="url(#clip_{element.clip_to})"')

    def _append_transform(parts: list[str], cx: float, cy: float) -> None:
        tx, ty = element.transform.translate
        rot = element.transform.rotate
        sx, sy = element.transform.scale
        t_parts = []
        if sx != 1 or sy != 1:
            t_parts.append(f"scale({_fmt(sx)},{_fmt(sy)})")
        if rot != 0:
            t_parts.append(f"rotate({_fmt(rot)},{_fmt(cx * canvas_w)},{_fmt(cy * canvas_h)})")
        if tx != 0 or ty != 0:
            t_parts.append(f"translate({_fmt(tx * canvas_w)},{_fmt(ty * canvas_h)})")
        # Skew from primitive (for isometric perspective text)
        skx = element.primitive.get("skew_x", 0) if element.primitive else 0
        sky = element.primitive.get("skew_y", 0) if element.primitive else 0
        if skx:
            t_parts.append(f"skewX({_fmt(skx)})")
        if sky:
            t_parts.append(f"skewY({_fmt(sky)})")
        if t_parts:
            parts.append(f' transform="{" ".join(t_parts)}"')

    # ── Primitive shapes ───────────────────────────────────────────
    if element.primitive:
        ptype = element.primitive.get("type")
        if ptype == "rect":
            x = element.primitive["x"] * canvas_w
            y = element.primitive["y"] * canvas_h
            w = element.primitive["width"] * canvas_w
            h = element.primitive["height"] * canvas_h
            rx = element.primitive.get("rx", 0) * canvas_min
            rx_attr = f' rx="{_fmt(rx)}"' if rx > 0 else ""
            parts = [f'    <rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}"{rx_attr}']
            _append_style(parts)
            _append_transform(parts, element.primitive["x"] + element.primitive["width"] / 2,
                              element.primitive["y"] + element.primitive["height"] / 2)
            parts.append("/>")
            return "".join(parts)

        if ptype == "ellipse":
            cx = element.primitive["cx"] * canvas_w
            cy = element.primitive["cy"] * canvas_h
            rxx = element.primitive["rx"] * canvas_w
            ryy = element.primitive["ry"] * canvas_h
            parts = [f'    <ellipse cx="{_fmt(cx)}" cy="{_fmt(cy)}" rx="{_fmt(rxx)}" ry="{_fmt(ryy)}"']
            _append_style(parts)
            _append_transform(parts, element.primitive["cx"], element.primitive["cy"])
            parts.append("/>")
            return "".join(parts)

        if ptype == "line":
            x1 = element.primitive["x1"] * canvas_w
            y1 = element.primitive["y1"] * canvas_h
            x2 = element.primitive["x2"] * canvas_w
            y2 = element.primitive["y2"] * canvas_h
            mid_x = (element.primitive["x1"] + element.primitive["x2"]) / 2
            mid_y = (element.primitive["y1"] + element.primitive["y2"]) / 2
            parts = [f'    <line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}"']
            _append_style(parts)
            _append_transform(parts, mid_x, mid_y)
            parts.append("/>")
            return "".join(parts)

        if ptype == "compound_path":
            path_data = _build_compound_path_data(
                element.primitive.get("subpaths", []),
                canvas_w,
                canvas_h,
                bool(element.primitive.get("closed", False)),
                float(element.primitive.get("smoothness", element.constraints.smoothness)),
            )
            if not path_data:
                return None
            parts = [f'    <path d="{path_data}"']
            _append_style(parts)
            bounds = element.bounds
            if bounds:
                _append_transform(parts, bounds["x"] + bounds["w"] / 2, bounds["y"] + bounds["h"] / 2)
            parts.append("/>")
            return "".join(parts)

        if ptype == "text":
            tx = element.primitive["x"] * canvas_w
            ty = element.primitive["y"] * canvas_h
            text = element.primitive.get("text", "")
            font_size = element.primitive.get("font_size", 0.04) * canvas_h
            font_family = element.primitive.get("font_family", "sans-serif") + ", Apple Symbols, sans-serif"
            text_anchor = element.primitive.get("text_anchor", "middle")
            font_weight = element.primitive.get("font_weight", "normal")
            font_style = element.primitive.get("font_style", "normal")
            parts = [
                f'    <text x="{_fmt(tx)}" y="{_fmt(ty)}"',
                f' font-size="{_fmt(font_size)}"',
                f' font-family="{font_family}"',
                f' font-weight="{font_weight}"',
                f' font-style="{font_style}"',
                f' text-anchor="{text_anchor}"',
            ]
            ls = element.primitive.get("letter_spacing")
            if ls:
                parts.append(f' letter-spacing="{_fmt(ls)}"')
            primitive_opacity = element.primitive.get("opacity")
            effective_opacity = element.style.opacity
            if primitive_opacity is not None:
                effective_opacity *= float(primitive_opacity)
            if effective_opacity < 1.0:
                parts.append(f' opacity="{_fmt(effective_opacity)}"')
            _append_style(parts, include_opacity=False)
            _append_transform(parts, element.primitive["x"], element.primitive["y"])
            parts.append(f">{_escape_xml(text)}</text>")
            return "".join(parts)

        if ptype == "image":
            ix = element.primitive["x"] * canvas_w
            iy = element.primitive["y"] * canvas_h
            iw = element.primitive["width"] * canvas_w
            ih = element.primitive["height"] * canvas_h
            href = element.primitive.get("href", "")
            aspect = element.primitive.get("preserve_aspect_ratio", "xMidYMid meet")
            parts = [f'    <image x="{_fmt(ix)}" y="{_fmt(iy)}"',
                     f' width="{_fmt(iw)}" height="{_fmt(ih)}"',
                     f' preserveAspectRatio="{aspect}"',
                     f' href="{_escape_xml(href)}"',
                     f' xlink:href="{_escape_xml(href)}"']
            if element.style.opacity < 1.0:
                parts.append(f' opacity="{_fmt(element.style.opacity)}"')
            if element.style.blend_mode:
                parts.append(f' style="mix-blend-mode:{element.style.blend_mode}"')
            if element.style.blur > 0:
                parts.append(f' filter="url(#blur_{element.style.blur:.2f})"')
            if element.clip_to:
                parts.append(f' clip-path="url(#clip_{element.clip_to})"')
            _append_transform(parts, element.primitive["x"] + element.primitive["width"] / 2,
                              element.primitive["y"] + element.primitive["height"] / 2)
            parts.append("/>")
            return "".join(parts)

    # ── Polygon / polyline mode (smoothness ≈ 0 — straight lines) ──
    if element.constraints.smoothness <= 0.001 and element.outline and not element.primitive:
        pts = " ".join(
            f"{_fmt(p[0] * canvas_w)},{_fmt(p[1] * canvas_h)}"
            for p in element.outline
        )
        tag = "polygon" if element.constraints.closed else "polyline"
        parts = [f'    <{tag} points="{pts}"']
        _append_style(parts)
        bounds = element.bounds
        if bounds:
            _append_transform(parts, bounds["x"] + bounds["w"] / 2, bounds["y"] + bounds["h"] / 2)
        parts.append("/>")
        return "".join(parts)

    # ── Path-based elements (fallback) ──────────────────────────────
    if not element.outline:
        return None

    segments = fit_curves(
        element.outline,
        closed=element.constraints.closed,
        smoothness=element.constraints.smoothness,
        tensions=list(element.constraints.tensions) if element.constraints.tensions else None,
        handle_in=list(element.constraints.handle_in) if element.constraints.handle_in else None,
        handle_out=list(element.constraints.handle_out) if element.constraints.handle_out else None,
    )
    if not segments:
        return None

    path_data = _build_path_data(segments, canvas_w, canvas_h, element.constraints.closed)

    parts = [f'    <path d="{path_data}"']

    _append_style(parts)

    # Transform (use center of bounds for path-based elements)
    if element.outline:
        bounds = element.bounds
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


def _build_compound_path_data(
    subpaths,
    scale_x: float,
    scale_y: float,
    closed: bool,
    smoothness: float,
) -> str:
    """Build SVG path data for multiple independent subpaths."""
    parts: list[str] = []
    for subpath in subpaths:
        if len(subpath) < 2:
            continue
        if smoothness <= 0.001:
            first = subpath[0]
            parts.append(f"M{_fmt(first[0] * scale_x)},{_fmt(first[1] * scale_y)}")
            for p in subpath[1:]:
                parts.append(f"L{_fmt(p[0] * scale_x)},{_fmt(p[1] * scale_y)}")
            if closed:
                parts.append("Z")
        else:
            segments = fit_curves(subpath, closed=closed, smoothness=smoothness)
            path_data = _build_path_data(segments, scale_x, scale_y, closed)
            if path_data:
                parts.append(path_data)
    return " ".join(parts)


def _escape_xml(text: str) -> str:
    """Escape special XML characters in text content."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def _fmt(value: float) -> str:
    """Deterministic float formatting — 6 decimal places, no trailing zeros."""
    rounded = round(value, 6)
    s = f"{rounded:.6f}".rstrip("0").rstrip(".")
    return s if s and s != "-0" else "0"
