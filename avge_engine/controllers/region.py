"""Region controller — create_region, delete_region, edit_region, duplicate_region."""
from __future__ import annotations

import math
import json as _json
import random
import base64
import mimetypes
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from avge_engine.services.engine import (
    StrokeWidthInput,
    get_graph,
    resolve_doc,
    validate_input,
    stroke_width_to_norm,
)
from avge_engine.services.region_service import RegionService
from avge_engine.geometry.procedural import compute_arc, compute_polygon, compute_star, ellipse_band
from avge_engine.scene import CurveConstraints, Style
from avge_engine.geometry import compute_bounds

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "soft-light", "hard-light",
]
IMAGE_IMPORT_MODES = Literal["image", "embed", "svg_paths"]
MAX_EMBED_BYTES = 2_000_000
MAX_SVG_IMPORT_BYTES = 1_000_000


def _read_href_bytes(href: str, max_bytes: int = MAX_EMBED_BYTES) -> tuple[bytes, str]:
    """Read bytes from http(s), file path, or data URI with a hard size cap."""
    if href.startswith("data:"):
        header, _, payload = href.partition(",")
        if not payload:
            raise ValueError("Invalid data URI")
        raw = base64.b64decode(payload) if ";base64" in header else payload.encode("utf-8")
        mime = header[5:].split(";")[0] or "application/octet-stream"
        if len(raw) > max_bytes:
            raise ValueError(f"Image too large ({len(raw)} bytes, max {max_bytes})")
        return raw, mime

    parsed = urlparse(href)
    if parsed.scheme in ("http", "https"):
        req = Request(href, headers={"User-Agent": "AVGE/0.5"})
        with urlopen(req, timeout=10) as response:
            mime = response.headers.get_content_type() or "application/octet-stream"
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"Image too large (max {max_bytes} bytes)")
        return raw, mime
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("Only http, https, file, local path, and data URI hrefs are supported")

    path = Path(parsed.path if parsed.scheme == "file" else href).expanduser()
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError(f"Image too large ({len(raw)} bytes, max {max_bytes})")
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return raw, mime


def _bytes_to_data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _is_svg_href(href: str, mime: str | None = None) -> bool:
    if mime == "image/svg+xml":
        return True
    clean = href.split("?", 1)[0].lower()
    return clean.endswith(".svg") or href.startswith("data:image/svg+xml")


def _parse_svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)", value)
    return float(match.group(1)) if match else None


def _svg_viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    view_box = root.attrib.get("viewBox")
    if view_box:
        nums = [float(v) for v in re.findall(r"[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?", view_box)]
        if len(nums) == 4 and nums[2] > 0 and nums[3] > 0:
            return nums[0], nums[1], nums[2], nums[3]
    width = _parse_svg_length(root.attrib.get("width")) or 1.0
    height = _parse_svg_length(root.attrib.get("height")) or 1.0
    return 0.0, 0.0, max(0.001, width), max(0.001, height)


def _map_svg_outline(
    outline: list[tuple[float, float]],
    view_box: tuple[float, float, float, float],
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[tuple[float, float]]:
    vb_x, vb_y, vb_w, vb_h = view_box
    return [
        (x + ((px - vb_x) / vb_w) * width, y + ((py - vb_y) / vb_h) * height)
        for px, py in outline
    ]


def _svg_path_regions(
    svg_text: str,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    fill_override: str | None,
    stroke_override: str | None,
    stroke_width: float,
    samples_per_curve: int,
    max_paths: int,
) -> list[dict[str, Any]]:
    from avge_engine.geometry.procedural import parse_svg_path

    root = ET.fromstring(svg_text)
    view_box = _svg_viewbox(root)
    regions: list[dict[str, Any]] = []
    for path_node in root.iter():
        if path_node.tag.rsplit("}", 1)[-1] != "path":
            continue
        path_data = path_node.attrib.get("d")
        if not path_data:
            continue
        outline = parse_svg_path(path_data, samples_per_curve=samples_per_curve)
        if len(outline) < 2:
            continue
        mapped = _map_svg_outline(outline, view_box, x, y, width, height)
        fill = fill_override if fill_override is not None else path_node.attrib.get("fill", "#CCCCCC")
        stroke = stroke_override if stroke_override is not None else path_node.attrib.get("stroke", "#333333")
        if fill in ("none", "transparent"):
            fill = None
        if stroke in ("none", "transparent"):
            stroke = None
        regions.append({"outline": mapped, "fill": fill, "stroke": stroke, "stroke_width": stroke_width})
        if len(regions) >= max_paths:
            break
    return regions


def _relative_to_absolute(scene, doc_id, relative_to, points):
    """Transform relative (0-1) coordinates to absolute within a reference region's bounds.

    Args:
        scene: Scene graph instance.
        doc_id: Document ID.
        relative_to: Region ID to use as reference bounding box.
        points: List of [x, y] or (x, y) coordinates in 0-1 space.

    Returns:
        Transformed coordinates in absolute canvas space.
    """
    region = scene.get_region(relative_to, doc_id)
    if region is None:
        raise ValueError(f"Reference region '{relative_to}' not found")
    from avge_engine.geometry import compute_bounds
    b = compute_bounds(region.outline)
    bx, by, bw, bh = b["x"], b["y"], b["w"], b["h"]
    if bw < 1e-10:
        bw = 1e-10
    if bh < 1e-10:
        bh = 1e-10
    return [(bx + p[0] * bw, by + p[1] * bh) for p in points]


def _relative_shape(scene, doc_id, relative_to, shape):
    """Transform a shape dict's coordinate keys from relative to absolute."""
    region = scene.get_region(relative_to, doc_id)
    if region is None:
        raise ValueError(f"Reference region '{relative_to}' not found")
    from avge_engine.geometry import compute_bounds
    b = compute_bounds(region.outline)
    bx, by, bw, bh = b["x"], b["y"], b["w"], b["h"]
    if bw < 1e-10:
        bw = 1e-10
    if bh < 1e-10:
        bh = 1e-10
    s = dict(shape)
    st = s.get("type")
    if st == "rect":
        s["x"] = bx + s["x"] * bw
        s["y"] = by + s["y"] * bh
        s["width"] = s["width"] * bw
        s["height"] = s["height"] * bh
        if "rx" in s:
            s["rx"] = s["rx"] * min(bw, bh)
    elif st == "ellipse":
        s["cx"] = bx + s["cx"] * bw
        s["cy"] = by + s["cy"] * bh
        s["rx"] = s["rx"] * bw
        if "ry" in s:
            s["ry"] = s["ry"] * bh
    elif st in ("line", "polyline"):
        if "points" in s:
            s["points"] = [(bx + p[0] * bw, by + p[1] * bh) for p in s["points"]]
        else:
            s["x1"] = bx + s["x1"] * bw
            s["y1"] = by + s["y1"] * bh
            s["x2"] = bx + s["x2"] * bw
            s["y2"] = by + s["y2"] * bh
    elif st in ("compound_path", "path"):
        if "subpaths" in s:
            s["subpaths"] = [
                [(bx + p[0] * bw, by + p[1] * bh) for p in subpath]
                for subpath in s["subpaths"]
            ]
        elif "points" in s:
            s["points"] = [(bx + p[0] * bw, by + p[1] * bh) for p in s["points"]]
    elif st in ("arc", "polygon", "star"):
        s["cx"] = bx + s["cx"] * bw
        s["cy"] = by + s["cy"] * bh
        s["r"] = s["r"] * min(bw, bh)
        if "r_inner" in s:
            s["r_inner"] = s["r_inner"] * min(bw, bh)
    return s


def _sample_region_outline(region, samples_per_segment: int = 8) -> list[list[float]]:
    """Return a dense closed outline suitable for patterned primitive borders."""
    if region.primitive:
        p = region.primitive
        ptype = p.get("type")
        if ptype == "rect":
            x, y, w, h = p["x"], p["y"], p["width"], p["height"]
            return [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]
        if ptype == "ellipse":
            cx, cy, rx, ry = p["cx"], p["cy"], p["rx"], p["ry"]
            n = max(24, samples_per_segment * 8)
            return [
                [cx + math.cos(math.tau * i / n) * rx, cy + math.sin(math.tau * i / n) * ry]
                for i in range(n + 1)
            ]
    pts = [[float(x), float(y)] for x, y in region.outline]
    if pts and region.constraints.closed and pts[0] != pts[-1]:
        pts.append(list(pts[0]))
    return pts


def _apply_primitive_patterns(
    scene,
    doc_id: str,
    base_region,
    outline_pattern: str | None,
    fill_pattern: str | None,
    pattern_density: int,
    pattern_amplitude: float,
    pattern_jitter: float,
    pattern_seed: int,
    stroke: str | None,
    pattern_width: float,
    pattern_opacity: float | None,
    layer: str,
    z_index: int,
) -> list[str]:
    """Create line-pattern overlays for a primitive outline and/or clipped fill."""
    from avge_engine.controllers import procedural as line_tools

    created: list[str] = []
    color = stroke or "#333333"
    opacity = pattern_opacity

    if outline_pattern in ("dashed", "dotted"):
        dash = "1,5" if outline_pattern == "dotted" else "7,5"
        sampled = _sample_region_outline(base_region)
        r = scene.create_line(
            points=sampled,
            document_id=doc_id,
            region_id=f"{base_region.id}_{outline_pattern}_outline",
            layer=layer,
            z_index=z_index + 2,
            stroke=color,
            stroke_width=pattern_width,
            opacity=opacity if opacity is not None else 1.0,
            stroke_linecap="round" if outline_pattern == "dotted" else "butt",
            stroke_dasharray=dash,
            smoothness=0.0 if len(sampled) <= 6 else 0.65,
        )
        r.metadata.update({"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id})
        created.append(r.id)
    elif outline_pattern in ("wavy", "zigzag", "rough", "sketch", "tapered", "pressure"):
        sampled = _sample_region_outline(base_region)
        rng = random.Random(pattern_seed)
        if outline_pattern in ("rough", "sketch"):
            repeats = 2 if outline_pattern == "sketch" else 1
            for i in range(repeats):
                pts = line_tools._jitter_points(sampled, max(pattern_jitter, pattern_amplitude * 0.45), rng)
                r = scene.create_line(
                    points=pts,
                    document_id=doc_id,
                    region_id=f"{base_region.id}_{outline_pattern}_outline_{i:02d}",
                    layer=layer,
                    z_index=z_index + 2 + i,
                    stroke=color,
                    stroke_width=pattern_width * (0.8 + i * 0.2),
                    opacity=opacity if opacity is not None else (0.55 if outline_pattern == "sketch" else 0.75),
                    stroke_linecap="round",
                    smoothness=0.55,
                )
                r.metadata.update({"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id})
                created.append(r.id)
        elif outline_pattern in ("tapered", "pressure"):
            widths = line_tools._width_profile_values(
                len(sampled),
                outline_pattern,
                pattern_width * 2.2,
                max(0.001, pattern_width * 0.35),
                pattern_width,
            )
            ribbon = line_tools._ribbon_outline(sampled, widths)
            r = scene.create_region(
                outline=ribbon,
                document_id=doc_id,
                region_id=f"{base_region.id}_{outline_pattern}_outline",
                layer=layer,
                z_index=z_index + 2,
                constraints=CurveConstraints(smoothness=0.55, closed=True),
                style=Style(fill=color, stroke=None, opacity=opacity if opacity is not None else 0.85),
                metadata={"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id},
            )
            created.append(r.id)
        else:
            subpaths = []
            for i in range(len(sampled) - 1):
                subpaths.append(line_tools._line_pattern_points(
                    outline_pattern,
                    [sampled[i], sampled[i + 1]],
                    None,
                    0.1,
                    1.0,
                    max(4, int(pattern_density)),
                    pattern_amplitude,
                    1.0,
                ))
            r = scene.create_compound_path(
                subpaths=subpaths,
                document_id=doc_id,
                region_id=f"{base_region.id}_{outline_pattern}_outline",
                layer=layer,
                z_index=z_index + 2,
                fill=None,
                stroke=color,
                stroke_width=pattern_width,
                opacity=opacity if opacity is not None else 1.0,
                stroke_linecap="round",
                smoothness=0.65 if outline_pattern == "wavy" else 0.0,
                closed=False,
            )
            r.metadata.update({"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id})
            created.append(r.id)

    if base_region.constraints.closed and fill_pattern in ("hatch", "cross_hatch", "contour_hatch", "scribble", "stipple"):
        b = compute_bounds(base_region.outline)
        if b:
            bounds = [b["x"], b["y"], b["w"], b["h"]]
            rng = random.Random(pattern_seed)
            if fill_pattern in ("hatch", "cross_hatch", "contour_hatch"):
                subpaths = line_tools._hatch_subpaths(
                    bounds, pattern_density, 25.0, fill_pattern, pattern_amplitude, pattern_jitter, rng
                )
                r = scene.create_compound_path(
                    subpaths=subpaths,
                    document_id=doc_id,
                    region_id=f"{base_region.id}_{fill_pattern}_fill",
                    layer=layer,
                    z_index=z_index + 1,
                    fill=None,
                    stroke=color,
                    stroke_width=pattern_width,
                    opacity=opacity if opacity is not None else 0.45,
                    stroke_linecap="round",
                    smoothness=0.55 if fill_pattern == "contour_hatch" else 0.0,
                    closed=False,
                )
                r.clip_to = base_region.id
                r.metadata.update({"tool": "create_region_pattern", "pattern": fill_pattern, "base": base_region.id})
                created.append(r.id)
            elif fill_pattern == "scribble":
                for i, pts in enumerate(line_tools._scribble_paths(bounds, pattern_density, pattern_jitter, rng)):
                    r = scene.create_line(
                        points=pts,
                        document_id=doc_id,
                        region_id=f"{base_region.id}_{fill_pattern}_{i:02d}",
                        layer=layer,
                        z_index=z_index + 1,
                        stroke=color,
                        stroke_width=pattern_width * rng.uniform(0.65, 1.25),
                        opacity=opacity if opacity is not None else 0.45,
                        stroke_linecap="round",
                        smoothness=0.65,
                    )
                    r.clip_to = base_region.id
                    r.metadata.update({"tool": "create_region_pattern", "pattern": fill_pattern, "base": base_region.id})
                    created.append(r.id)
            elif fill_pattern == "stipple":
                total = max(1, min(600, int(pattern_density)))
                for i in range(total):
                    dot_w = pattern_width * rng.uniform(0.7, 1.6)
                    r = scene.create_ellipse(
                        b["x"] + rng.random() * b["w"],
                        b["y"] + rng.random() * b["h"],
                        dot_w,
                        dot_w,
                        document_id=doc_id,
                        region_id=f"{base_region.id}_{fill_pattern}_{i:03d}",
                        layer=layer,
                        z_index=z_index + 1,
                        fill=color,
                        stroke=None,
                        opacity=opacity if opacity is not None else rng.uniform(0.25, 0.65),
                    )
                    r.clip_to = base_region.id
                    r.metadata.update({"tool": "create_region_pattern", "pattern": fill_pattern, "base": base_region.id})
                    created.append(r.id)

    if created:
        scene._persist(doc_id)
    return created


def create_tools(mcp):
    """Register region tools on the given FastMCP instance."""

    @mcp.tool(
        name="create_region",
        description="Create a vector region from an outline defined by points. "
        "The engine fits smooth Bézier curves to your points. "
        "⚠️ Coordinates MUST be normalized 0.0–1.0 "
        "((0,0)=top-left, (1,1)=bottom-right). "
        "💡 Refine incrementally: add regions here, use "
        "``restyle`` to recolor, ``edit_region`` to nudge points — "
        "never rebuild from scratch. "
        "💡 blur=N adds Gaussian blur for soft glows, shadows, and fog.",
    )
    def create_region(
        outline: list[list[float]] | None = None,
        region_id: str | None = None,
        document_id: str | None = None,
        layer: str = "default",
        closed: bool = True,
        smoothness: float = 0.5,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        relative_to: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float = 1.0,
        fill_gradient: Any | None = None,
        smoothness_per_point: list[float] | None = None,
        z_index: int = 0,
        z_before: str | None = None,
        z_after: str | None = None,
        clip_to: str | None = None,
        blend_mode: BLEND_MODES | None = None,
        tags: dict | None = None,
        shape: dict | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        blur: float = 0.0,
        rotate: float = 0.0,
        handle_in: list[list[float]] | None = None,
        handle_out: list[list[float]] | None = None,
        groups: list[str] | None = None,
        outline_pattern: str | None = None,
        fill_pattern: str | None = None,
        pattern_density: int = 12,
        pattern_amplitude: float = 0.02,
        pattern_jitter: float = 0.0,
        pattern_seed: int = 1,
        pattern_stroke_width: StrokeWidthInput = None,
        pattern_opacity: float | None = None,
    ) -> str:
        """Create a vector region. Use ``outline`` for polygon/curve shapes,
        or ``shape`` dict for SVG primitives (rect, ellipse, line).
        When ``shape`` is set, ``outline`` is ignored.

        Args:
            outline: List of [x, y] pairs in normalized space (0.0–1.0).
                For SVG primitives use ``shape`` instead.
            shape: SVG primitive — ``{"type":"rect","x":0.1,"y":0.1,"width":0.3,"height":0.15,"rx":0.02}``
                rect: x, y, width, height, rx (corner radius, half min dim=pill)
                ellipse: cx, cy, rx, ry (ry optional)
                line: x1, y1, x2, y2 (stroke only, fill ignored)
                star: cx, cy, r, r_inner?, points? (default 5), rotate?
                polygon: cx, cy, r, sides? (default 6), rotate?
            region_id: Optional unique ID (auto-generated if omitted).
            document_id: Document UUID (omit to use active document).
            layer: Layer name (default "default").
            closed: Whether polygon shape is closed (default True).
            smoothness: 0.0–1.0. See description above for per-category guidance.
            fill: Fill hex color, or omit for no fill.
            stroke: Stroke hex color, or omit for no stroke.
            stroke_width: Stroke width in canvas pixels.
            opacity: Object opacity 0.0–1.0.
            fill_gradient: Gradient definition (dict or JSON string).
                Linear: {"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,
                "stops":[{"offset":0,"color":"#FFF"},{"offset":1,"color":"#000"}]}
                Radial: {"type":"radial","cx":0.5,"cy":0.5,"r":0.5,
                "stops":[{"offset":0,"color":"#FFF"},{"offset":1,"color":"#000"}]}
                💡 Use for smooth lighting on panels, bottles, glass reflections.
            smoothness_per_point: JSON array of per-vertex tension values.
            z_index: Paint order (higher = on top).
            z_before: Place this region directly behind the region with this ID.
                Overrides z_index if the referenced region exists.
            z_after: Place this region directly in front of the region with this ID.
                Overrides z_index if the referenced region exists.
            clip_to: Region ID to constrain rendering inside that region's outline.
            blend_mode: CSS mix-blend-mode.
            tags: JSON object of key/value metadata tags.
            stroke_linecap: Line end style for line shapes — "butt", "round", or "square".
            stroke_dasharray: Dash pattern for strokes (e.g. "4,2" for 4px dash, 2px gap).
            blur: Gaussian blur radius in pixels — soft glows, shadows, fog.
                💡 One blur region replaces 4-5 stacked low-opacity ellipses.
            rotate: Rotation in degrees around the shape center. 💡 For rotated primitives
                via the shape parameter, or use transform_objects post-hoc for existing regions.
            handle_in: Per-point incoming Bézier handle vectors [[dx,dy],...]. Overrides Catmull-Rom.
            handle_out: Per-point outgoing Bézier handle vectors [[dx,dy],...].
            relative_to: Region ID to use as coordinate reference. When set,
                outline points are treated as 0.0-1.0 fractions of the reference
                region's bounding box, then mapped to absolute canvas coordinates.
                💡 Place a bolt at (0.5, 0.5) on a belt panel without measuring.
            groups: Optional list of group names to add this region to.
            outline_pattern: Optional primitive outline style: dashed, dotted,
                wavy, zigzag, rough, sketch, tapered, or pressure.
            fill_pattern: Optional clipped interior texture: hatch, cross_hatch,
                contour_hatch, scribble, or stipple.
            pattern_density/amplitude/jitter/seed: Controls for generated
                outline/fill pattern overlays.
            pattern_stroke_width: Pattern overlay stroke width in canvas pixels.
            pattern_opacity: Pattern overlay opacity.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        pattern_width = stroke_width_to_norm(doc_id, pattern_stroke_width) or stroke_width

        # Resolve z_index from z_before/z_after
        resolved_z = z_index
        try:
            if z_before is not None:
                ref = scene.get_region(z_before, doc_id)
                resolved_z = ref.z_index - 1
            elif z_after is not None:
                ref = scene.get_region(z_after, doc_id)
                resolved_z = ref.z_index + 1
        except ValueError:
            return f"Error: Reference region for z-ordering not found"

        # Resolve fill from fill_gradient (applies to both shape and outline paths)
        resolved_fill = fill
        if fill_gradient is not None:
            if isinstance(fill_gradient, str):
                try:
                    resolved_fill = _json.loads(fill_gradient)
                except _json.JSONDecodeError:
                    return f"Error: invalid fill_gradient JSON: {fill_gradient}"
            elif isinstance(fill_gradient, dict):
                resolved_fill = fill_gradient

        # Transform relative coords to absolute if relative_to is set (applies to both shape and outline)
        if relative_to is not None and shape is not None:
            shape = _relative_shape(scene, doc_id, relative_to, shape)
        elif relative_to is not None and outline is not None:
            outline = _relative_to_absolute(scene, doc_id, relative_to, outline)

        # ── SVG primitive path ────────────────────────────────────────
        if shape is not None:
            stype = shape.get("type")
            try:
                if stype == "rect":
                    r = scene.create_rect(
                        shape["x"], shape["y"], shape["width"], shape["height"],
                        rx=shape.get("rx", 0.0),
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=resolved_z,
                        fill=resolved_fill, stroke=stroke,
                        stroke_width=stroke_width, opacity=opacity,
                        blend_mode=blend_mode,
                        taper=shape.get("taper", 0.0),
                        rotate=rotate,
                    )
                    if groups:
                        for g in groups:
                            scene.add_to_group(g, [r.id], doc_id)
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, r, outline_pattern, fill_pattern,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    rxn = f", rx={shape.get('rx',0)}" if shape.get('rx',0) > 0 else ""
                    tpn = f", taper={shape.get('taper',0)}" if shape.get('taper',0) else ""
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Rect created: id={r.id}, {shape.get('x',0):.4f},{shape.get('y',0):.4f} {shape.get('width',0):.4f}x{shape.get('height',0):.4f}{rxn}{tpn}{extra}"
                elif stype == "ellipse":
                    e = scene.create_ellipse(
                        shape["cx"], shape["cy"], shape["rx"],
                        ry=shape.get("ry", None),
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=resolved_z,
                        fill=resolved_fill, stroke=stroke,
                        stroke_width=stroke_width, opacity=opacity,
                        blend_mode=blend_mode,
                        rotate=rotate,
                    )
                    if groups:
                        for g in groups:
                            scene.add_to_group(g, [e.id], doc_id)
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, e, outline_pattern, fill_pattern,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    rys = shape.get("ry", shape["rx"])
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Ellipse created: id={e.id}, cx={shape['cx']:.4f} cy={shape['cy']:.4f} rx={shape['rx']:.4f} ry={rys:.4f}{extra}"
                elif stype == "line":
                    pts = shape.get("points")
                    if pts is not None and len(pts) > 2:
                        lr = scene.create_line(
                            points=pts,
                            document_id=doc_id, region_id=region_id,
                            layer=layer, z_index=resolved_z,
                            stroke=stroke, stroke_width=stroke_width,
                            opacity=opacity, blend_mode=blend_mode,
                            stroke_linecap=stroke_linecap,
                            rotate=rotate,
                        )
                        if groups:
                            for g in groups:
                                scene.add_to_group(g, [lr.id], doc_id)
                        return f"Polyline created: id={lr.id}, {len(pts)} points"
                    else:
                        lr = scene.create_line(
                            shape["x1"], shape["y1"], shape["x2"], shape["y2"],
                            document_id=doc_id, region_id=region_id,
                            layer=layer, z_index=resolved_z,
                            stroke=stroke, stroke_width=stroke_width,
                            opacity=opacity, blend_mode=blend_mode,
                            stroke_linecap=stroke_linecap,
                            rotate=rotate,
                        )
                        if groups:
                            for g in groups:
                                scene.add_to_group(g, [lr.id], doc_id)
                        return f"Line created: id={lr.id}, ({shape['x1']:.4f},{shape['y1']:.4f}) → ({shape['x2']:.4f},{shape['y2']:.4f})"
                elif  stype == "arc":
                    pts = compute_arc(shape["cx"], shape["cy"], shape["r"],
                        start_angle=shape.get("start_angle", 0.0), end_angle=shape.get("end_angle", 180.0))
                    r = scene.create_region(outline=pts, document_id=doc_id, region_id=region_id, layer=layer, z_index=resolved_z,
                        constraints=CurveConstraints(smoothness=0.5, closed=False),
                        style=Style(fill=resolved_fill, stroke=stroke, stroke_width=stroke_width, opacity=opacity, blur=blur))
                    return f"Arc created: id={r.id}, ({shape['cx']:.4f},{shape['cy']:.4f}) r={shape['r']:.4f}"
                elif  stype == "polygon":
                    pts = compute_polygon(shape["cx"], shape["cy"], shape["r"],
                        sides=shape.get("sides", 6), rotation=shape.get("rotate", shape.get("rotation", 0.0)))
                    r = scene.create_region(outline=pts, document_id=doc_id, region_id=region_id, layer=layer, z_index=resolved_z,
                        constraints=CurveConstraints(smoothness=0.0, closed=True),
                        style=Style(fill=resolved_fill, stroke=stroke, stroke_width=stroke_width, opacity=opacity, blur=blur))
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, r, outline_pattern, fill_pattern,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Polygon created: id={r.id}, {shape.get('sides',6)} sides{extra}"
                elif  stype == "star":
                    inner_radius = shape.get("r_inner")
                    if inner_radius is None:
                        inner_radius = shape["r"] * 0.5
                    pts = compute_star(shape["cx"], shape["cy"], shape["r"],
                        inner_radius, points=shape.get("points", 5), rotation=shape.get("rotate", shape.get("rotation", 0.0)))
                    r = scene.create_region(outline=pts, document_id=doc_id, region_id=region_id, layer=layer, z_index=resolved_z,
                        constraints=CurveConstraints(smoothness=0.0, closed=True),
                        style=Style(fill=resolved_fill, stroke=stroke, stroke_width=stroke_width, opacity=opacity, blur=blur))
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, r, outline_pattern, fill_pattern,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Star created: id={r.id}, {shape.get('points',5)} points{extra}"
                else:
                    return f"Error: Unknown shape type '{stype}'. Supported: rect, ellipse, line, arc, polygon, star"
            except (ValueError, RuntimeError, KeyError) as e:
                return f"Error: {e}"

        # ── Polygon/Catmull-Rom path ──────────────────────────────────
        if not outline or len(outline) < 2:
            return "Error: Outline must have at least 2 points"
        if len(outline) > 200:
            return (
                f"Error: outline has {len(outline)} points "
                f"(max 200 for M0b; consider fewer points + smoothness constraints)"
            )

        norm_outline = [(float(p[0]), float(p[1])) for p in outline]

        tensions = smoothness_per_point  # now directly a list from MCP

        constraints = CurveConstraints(
            smoothness=max(0.0, min(1.0, smoothness)),
            closed=closed,
            tensions=tensions,
            handle_in=tuple(tuple(p) for p in handle_in) if handle_in else None,
            handle_out=tuple(tuple(p) for p in handle_out) if handle_out else None,
        )

        style = Style(
            fill=None if resolved_fill is None or resolved_fill in ("none", "transparent") else resolved_fill,
            stroke=None if stroke is None or stroke == "none" else stroke,
            stroke_width=max(0.001, min(0.1, stroke_width)),
            opacity=max(0.0, min(1.0, opacity)),
            blend_mode=blend_mode,
            stroke_dasharray=stroke_dasharray,
            blur=blur,
        )

        metadata = {}
        if tags:
            metadata = dict(tags)

        try:
            region = scene.create_region(
                outline=norm_outline,
                region_id=region_id,
                document_id=doc_id,
                layer=layer,
                z_index=resolved_z,
                clip_to=clip_to,
                constraints=constraints,
                style=style,
                metadata=metadata,
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

        pattern_ids = _apply_primitive_patterns(
            scene, doc_id, region, outline_pattern, fill_pattern,
            pattern_density, pattern_amplitude, pattern_jitter,
            pattern_seed, stroke, pattern_width, pattern_opacity,
            layer, resolved_z,
        )

        bounds = compute_bounds(region.outline)
        bounds_str = (
            f"x={bounds['x']:.4f} y={bounds['y']:.4f} "
            f"w={bounds['w']:.4f} h={bounds['h']:.4f}"
            if bounds
            else "N/A"
        )

        advisory = ""
        if len(outline) > 30:
            advisory = (
                f" Advisory: {len(outline)} points is high; "
                f"use fewer points + smoothness constraints for better curve quality."
            )

        return (
            f"Region created: id={region.id}, layer={region.layer}, "
            f"bounds=({bounds_str}), points={len(outline)}"
            f"{', pattern_regions=' + str(len(pattern_ids)) if pattern_ids else ''}"
            f"{advisory}"
        )

    @mcp.tool(
        name="create_ellipse_band",
        description="Create a filled elliptical ring or arc band in one call. "
        "Use for realistic circular balconies, overhead rings, rail strips, "
        "counters, curved floors, rims, and glass bands. "
        "Set start_angle/end_angle for partial arcs; use perspective>0 to "
        "widen the lower/near side and narrow the upper/far side; use skew_x "
        "for oblique architectural views.",
    )
    def create_ellipse_band(
        cx: float,
        cy: float,
        rx: float,
        ry: float | None = None,
        thickness: float | None = 0.03,
        inner_rx: float | None = None,
        inner_ry: float | None = None,
        start_angle: float = 0.0,
        end_angle: float = 360.0,
        rotation: float = 0.0,
        samples: int = 64,
        perspective: float = 0.0,
        skew_x: float = 0.0,
        region_id: str | None = None,
        document_id: str | None = None,
        layer: str = "default",
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: StrokeWidthInput = None,
        opacity: float = 1.0,
        fill_gradient: Any | None = None,
        smoothness: float = 0.0,
        z_index: int = 0,
        z_before: str | None = None,
        z_after: str | None = None,
        clip_to: str | None = None,
        blend_mode: BLEND_MODES | None = None,
        tags: dict | None = None,
        groups: list[str] | None = None,
        outline_pattern: str | None = None,
        fill_pattern: str | None = None,
        pattern_density: int = 12,
        pattern_amplitude: float = 0.02,
        pattern_jitter: float = 0.0,
        pattern_seed: int = 1,
        pattern_stroke_width: StrokeWidthInput = None,
        pattern_opacity: float | None = None,
    ) -> str:
        """Create an annular ellipse/arc band as a closed vector region.

        Args:
            cx, cy: Center in normalized coordinates.
            rx, ry: Outer radii. If ry is omitted, a circle is used before
                perspective/rotation transforms.
            thickness: Uniform inward thickness when inner radii are omitted.
            inner_rx, inner_ry: Explicit inner radii. Use for tapered-looking
                architectural bands or different horizontal/vertical thickness.
            start_angle, end_angle: Arc range in degrees; 0 is right, 90 is down.
                A 360-degree sweep creates a full ring with a small seam.
            rotation: Rotate the band around its center in degrees.
            samples: Points sampled per edge, clamped to 4..180.
            perspective: -0.75..0.75. Positive values widen the lower/near side
                and narrow the upper/far side.
            skew_x: Horizontal shear based on vertical position.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        pattern_width = stroke_width_to_norm(doc_id, pattern_stroke_width) or stroke_width

        resolved_z = z_index
        try:
            if z_before is not None:
                ref = scene.get_region(z_before, doc_id)
                resolved_z = ref.z_index - 1
            elif z_after is not None:
                ref = scene.get_region(z_after, doc_id)
                resolved_z = ref.z_index + 1
        except ValueError:
            return "Error: Reference region for z-ordering not found"

        resolved_fill = fill
        if fill_gradient is not None:
            if isinstance(fill_gradient, str):
                try:
                    resolved_fill = _json.loads(fill_gradient)
                except _json.JSONDecodeError:
                    return f"Error: invalid fill_gradient JSON: {fill_gradient}"
            elif isinstance(fill_gradient, dict):
                resolved_fill = fill_gradient

        try:
            outline = ellipse_band(
                cx=cx,
                cy=cy,
                rx=rx,
                ry=ry,
                thickness=thickness,
                inner_rx=inner_rx,
                inner_ry=inner_ry,
                start_angle=start_angle,
                end_angle=end_angle,
                rotation=rotation,
                samples=samples,
                perspective=perspective,
                skew_x=skew_x,
            )
            region = scene.create_region(
                outline=outline,
                region_id=region_id,
                document_id=doc_id,
                layer=layer,
                z_index=resolved_z,
                clip_to=clip_to,
                constraints=CurveConstraints(
                    smoothness=max(0.0, min(1.0, smoothness)),
                    closed=True,
                ),
                style=Style(
                    fill=None if resolved_fill is None or resolved_fill in ("none", "transparent") else resolved_fill,
                    stroke=None if stroke is None or stroke == "none" else stroke,
                    stroke_width=max(0.001, min(0.1, stroke_width)),
                    opacity=max(0.0, min(1.0, opacity)),
                    blend_mode=blend_mode,
                ),
                metadata=dict(tags) if tags else {},
            )
            if groups:
                for g in groups:
                    scene.add_to_group(g, [region.id], doc_id)
            pattern_ids = _apply_primitive_patterns(
                scene, doc_id, region, outline_pattern, fill_pattern,
                pattern_density, pattern_amplitude, pattern_jitter,
                pattern_seed, stroke, pattern_width, pattern_opacity,
                layer, resolved_z,
            )
        except (ValueError, RuntimeError, KeyError) as e:
            return f"Error: {e}"

        bounds = compute_bounds(region.outline)
        bounds_str = (
            f"x={bounds['x']:.4f} y={bounds['y']:.4f} "
            f"w={bounds['w']:.4f} h={bounds['h']:.4f}"
            if bounds
            else "N/A"
        )
        return (
            f"Ellipse band created: id={region.id}, "
            f"bounds=({bounds_str}), points={len(region.outline)}, "
            f"angles={start_angle:g}→{end_angle:g}"
            f"{', pattern_regions=' + str(len(pattern_ids)) if pattern_ids else ''}"
        )

    @mcp.tool(
        name="delete_region",
        description="Delete one or more regions by ID. Returns list of "
        "actually removed IDs. Use this to clean up stray geometry, "
        "botched outlines, or elements you want to replace.",
    )
    def delete_region(ids: list[str], document_id: str | None = None) -> str:
        """Delete one or more regions by ID.

        Args:
            ids: List of region IDs to delete (e.g. ["tag", "steam1"]).
            document_id: Document UUID (omit to use active document).
        """
        try:
            deleted = RegionService().delete_regions(ids=ids, document_id=document_id)
        except RuntimeError:
            return "Error: No active document"

        if not deleted:
            return "No matching regions found to delete"
        # Split into multiple lines to avoid output truncation
        summary = f"Deleted {len(deleted)} region(s):"
        lines = [summary]
        for i in range(0, len(deleted), 8):
            lines.append("  " + ", ".join(deleted[i:i+8]))
        return "\n".join(lines)

    @mcp.tool(
        name="edit_region",
        description="Modify an existing region's outline, style, z_index, or shape. "
        "Only provided fields are changed; omitted fields keep their values. "
        "💡 Single-point editing: use ``point_index`` + ``point_coords`` "
        "to nudge one vertex without resending the whole outline. "
        "Use transform_objects for whole-region move/scale/rotate/mirror/align. "
        "💡 Batch z-index: pass ids=[...] with z_index=N to reorder "
        "multiple regions at once.",
    )
    def edit_region(
        region_id: str | None = None,
        ids: list[str] | None = None,
        document_id: str | None = None,
        outline: list[list[float]] | None = None,
        point_index: int | None = None,
        point_coords: list[float] | None = None,
        point_dx: float | None = None,
        point_dy: float | None = None,
        smoothness: float | None = None,
        smoothness_per_point: list[float] | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = None,
        z_index: int | None = None,
        blend_mode: BLEND_MODES | None = None,
        clip_to: str | None = None,
        layer: str | None = None,
        tags: dict | None = None,
        shape: dict | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        handle_in: list[list[float]] | None = None,
        handle_out: list[list[float]] | None = None,
    ) -> str:
        """Modify an existing region's properties.

        Args:
            region_id: ID of the region to edit (omit if using ids).
            document_id: Document UUID (omit for active doc).
            ids: List of region IDs to edit simultaneously.
                💡 Apply the same color/outline change to multiple regions at once.
            outline: New outline coordinates (omit to keep current).
            point_index: Index of a single outline point to move (requires
                ``point_coords`` or ``point_dx``/``point_dy``). Avoids resending the
                entire outline array when adjusting one vertex.
            point_coords: New ``[x, y]`` for the point at ``point_index``.
                Mutually exclusive with ``point_dx``/``point_dy``.
            point_dx: Horizontal offset for the point at ``point_index`` (relative).
            point_dy: Vertical offset for the point at ``point_index`` (relative).
            smoothness: New smoothness value (omit to keep current).
            smoothness_per_point: JSON array of per-vertex tensions.
            fill: New fill hex color or gradient (omit to keep current).
            stroke: New stroke color.
            stroke_width: New stroke width in canvas pixels.
            opacity: New opacity.
            z_index: New paint order (higher = on top).
            blend_mode: CSS mix-blend-mode (multiply, screen, overlay, etc.).
            clip_to: Region ID to clip rendering inside.
            layer: New layer name.
            tags: JSON object of key/value metadata tags (replaces all tags).
            shape: New primitive shape dict for rect/ellipse/line resize.
                rect: {"type":"rect","x":0.1,"y":0.1,"width":0.3,"height":0.5,"rx":0.02}
                ellipse: {"type":"ellipse","cx":0.5,"cy":0.5,"rx":0.1,"ry":0.08}
                line: {"type":"line","x1":0.1,"y1":0.2,"x2":0.9,"y2":0.8}
            stroke_linecap: Line end style — "butt", "round", or "square".
            stroke_dasharray: Dash pattern for strokes (e.g. "4,2").
            handle_in: Per-point incoming Bézier handle vectors [[dx,dy],...].
            handle_out: Per-point outgoing Bézier handle vectors [[dx,dy],...].
        """
        try:
            result = RegionService().edit_region(
                region_id=region_id,
                ids=ids,
                document_id=document_id,
                outline=outline,
                point_index=point_index,
                point_coords=point_coords,
                point_dx=point_dx,
                point_dy=point_dy,
                smoothness=smoothness,
                smoothness_per_point=smoothness_per_point,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                z_index=z_index,
                blend_mode=blend_mode,
                clip_to=clip_to,
                layer=layer,
                tags=tags,
                shape=shape,
                stroke_linecap=stroke_linecap,
                stroke_dasharray=stroke_dasharray,
                handle_in=handle_in,
                handle_out=handle_out,
            )
            if len(result.affected) == 1:
                return f"Region '{result.affected[0]}' updated"
            if len(result.affected) > 1:
                return f"Updated {len(result.affected)} region(s): {', '.join(result.affected)}"
            return "No regions updated"
        except RuntimeError:
            return "Error: No active document"
        except (ValueError, IndexError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="edit_regions",
        description="Edit multiple regions in a single call, each with its own "
        "content/style override. Use transform_objects for move/scale/rotate/mirror/align. "
        "💡 Recolor or relayer many regions without extra calls.\n"
        'Example: [{"id":"belt","fill":"#222"},{"id":"belt_buckle","z_index":20}]',
    )
    def edit_regions(
        updates: list[dict],
        document_id: str | None = None,
    ) -> str:
        """Edit multiple regions with per-region content/style updates.

        Args:
            updates: List of update objects, each with:
                - ``id`` (required): Region ID.
                - ``outline``: Replace outline points.
                - ``fill`` / ``stroke`` / ``stroke_width`` / ``opacity``: Override style.
                - ``z_index``: Override paint order.
                - ``layer``: Move to a different layer.
                - ``point_index`` / ``point_coords`` / ``point_dx`` / ``point_dy``: Edit one point.
                Other ``edit_region`` fields also work.
            document_id: Document UUID (omit for active doc).
        """
        try:
            result = RegionService().edit_regions(updates=updates, document_id=document_id)
        except RuntimeError:
            return "Error: No active document"

        summary = f"edit_regions: {result.ok}/{result.total} updated"
        return "\n".join([summary] + result.lines)


    @mcp.tool(
        name="refine_line",
        description="Correct existing linework without recreating it. "
        "Modes: stabilize removes small hand jitter, smooth rounds a rough path, "
        "simplify reduces excess points, and straighten converts a stroke to a clean straight line. "
        "Use this after create_curve/create_primitive polyline or after rough/sketch linework when the "
        "geometry is right but the stroke needs cleanup.",
    )
    def refine_line(
        region_id: str,
        document_id: str | None = None,
        mode: Literal["stabilize", "smooth", "simplify", "straighten"] = "stabilize",
        strength: float = 0.5,
        simplify_tolerance: float = 0.01,
        smoothness: float | None = None,
        preserve_corners: bool = True,
        iterations: int = 1,
    ) -> str:
        """Refine line/curve geometry in place.

        Args:
            region_id: Existing region/line ID.
            document_id: Document UUID (omit for active doc).
            mode: stabilize, smooth, simplify, or straighten.
            strength: 0.0-1.0 correction strength.
            simplify_tolerance: Normalized tolerance for point reduction.
            smoothness: Optional replacement curve smoothness 0.0-1.0.
            preserve_corners: Keep sharp corners during smoothing/stabilization.
            iterations: Number of smoothing passes for mode='smooth'.
        """
        try:
            result = RegionService().refine_line(
                region_id=region_id,
                document_id=document_id,
                mode=mode,
                strength=strength,
                simplify_tolerance=simplify_tolerance,
                smoothness=smoothness,
                preserve_corners=preserve_corners,
                iterations=iterations,
            )
            return (
                f"Line refined: id={result.region_id}, mode={result.mode}, "
                f"points={result.before_points}->{result.after_points}, "
                f"smoothness={result.smoothness}"
            )
        except RuntimeError:
            return "Error: No active document"
        except (ValueError, IndexError) as e:
            return f"Error: {e}"



    @mcp.tool(
        name="create_text",
        description="Create a text label. "
        "``y`` is the text **baseline** (bottom of text, not center). "
        "Font size is relative to canvas height (0.04 = 4%). "
        "💡 Isometric text: ``skew_y=-30`` for right face, ``30`` for left. "
        "Available fonts for manga/manhwa/comic styling:\n"
        "  Bradley Hand Bold — hand-lettered, closest to English manga\n"
        "  Marker Felt — marker pen style, good for effects\n"
        "  Comic Sans MS — casual comic book style\n"
        "  Hiragino Kaku Gothic ProN — Japanese manga gothic font\n"
        "  Apple SD Gothic Neo — Korean manhwa gothic font\n"
        "  Chalkduster — rough chalkboard style\n"
        "  Brush Script MT — brush stroke, elegant hand-lettering\n"
        "  Arial/Helvetica bold — clean all-caps comic style",
    )
    def create_text(
        x: float,
        y: float,
        text: str,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#333333",
        font_size: float = 0.04,
        font_family: str = "sans-serif",
        text_anchor: str = "middle",
        font_weight: str = "normal",
        font_style: str = "normal",
        rotate: float = 0.0,
        letter_spacing: float = 0.0,
        opacity: float = 1.0,
        skew_x: float = 0.0,
        skew_y: float = 0.0,
        groups: list[str] | None = None,
        background_box: dict | None = None,
    ) -> str:
        """Create a text label.

        Args:
            x: X coordinate in normalized space (0.0–1.0).
            y: Y coordinate in normalized space (0.0–1.0).
                This is the text *baseline* (bottom of the text, not center).
                For typical labels, place y at the bottom of where the text sits.
            text: The text content to display.
            document_id: Document UUID (omit to use active document).
            region_id: Optional unique ID (auto-generated if omitted).
            layer: Layer name (default "default").
            z_index: Paint order (higher = on top).
            fill: Text color (default "#333333").
            font_size: Font size relative to canvas height (0.04 = 4%).
            font_family: CSS font family (default "sans-serif").
                Manga: "Bradley Hand Bold", "Hiragino Kaku Gothic ProN"
                Manhwa: "Apple SD Gothic Neo"
                Comic: "Comic Sans MS", "Marker Felt", "Chalkduster"
            text_anchor: Horizontal anchor — "start" (left), "middle" (center), "end" (right).
            font_weight: Font weight — "normal", "bold", etc.
            font_style: CSS font-style — "normal", "italic", "oblique".
            rotate: Rotation in degrees around the text center.
            letter_spacing: Letter spacing / tracking in normalized units
                (0.0 = default, 0.05 = wide corporate tracking).
            opacity: Text opacity 0.0–1.0.
            skew_x: Skew along X axis in degrees (matches isometric slope).
                For right face text use skew_y=-30, for left face skew_y=30.
            skew_y: Skew along Y axis in degrees.
            groups: Optional list of group names to add this region to.
            background_box: Dict to auto-create a rect behind the text.
                Keys: fill (default "#FFF"), padding (default 0.01), rx (default 0.005),
                stroke (default "none"), z_index_offset (default -1).
                💡 Saves 1 call per text label — no separate rect creation.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        try:
            r = scene.create_text(
                x, y, text,
                document_id=doc_id, region_id=region_id,
                layer=layer, z_index=z_index,
                fill=fill, font_size=font_size, font_family=font_family,
                text_anchor=text_anchor, font_weight=font_weight, font_style=font_style,
                rotate=rotate, letter_spacing=letter_spacing, opacity=opacity,
                skew_x=skew_x, skew_y=skew_y,
            )
            if groups:
                for g in groups:
                    scene.add_to_group(g, [r.id], doc_id)

            box_info = ""
            if background_box is not None:
                pad = background_box.get("padding", 0.01)
                rx = background_box.get("rx", 0.005)
                bf = background_box.get("fill", "#FFFFFF")
                bs = background_box.get("stroke", "none")
                bw = background_box.get("stroke_width", 0.0)
                b_z = z_index + background_box.get("z_index_offset", -1)
                # Approximate text width: ~0.6 × font_size per character
                tw = len(text) * font_size * 0.6
                th = font_size * 1.2
                box_x = x - tw / 2 if text_anchor == "middle" else (x - pad if text_anchor == "start" else x - tw - pad)
                box_y = y - th + pad * 0.5
                box_w = tw + pad * 2
                box_h = th + pad
                box = scene.create_rect(
                    box_x, box_y, box_w, box_h,
                    rx=rx,
                    document_id=doc_id,
                    layer=layer,
                    z_index=b_z,
                    fill=bf, stroke=bs, stroke_width=bw,
                )
                if groups:
                    for g in groups:
                        scene.add_to_group(g, [box.id], doc_id)
                box_info = f", box=({box_x:.4f},{box_y:.4f}) {box_w:.4f}x{box_h:.4f}"

            return (
                f"Text created: id={r.id}, '{text}' at ({x:.4f}, {y:.4f}), "
                f"size={font_size:.3f}, family='{font_family}', "
                f"anchor='{text_anchor}', weight='{font_weight}', style='{font_style}'{box_info}"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="insert_image",
        description="Add an image to the canvas, embed it as a data URI, or import SVG paths as editable vector regions. "
        "import_mode='image' keeps href as an external SVG <image>; import_mode='embed' fetches local/remote bytes "
        "and stores a data URI so previews do not need network access; import_mode='svg_paths' parses SVG <path> "
        "elements into editable regions.",
    )
    def insert_image(
        x: float,
        y: float,
        width: float,
        height: float,
        href: str,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        preserve_aspect_ratio: str = "xMidYMid meet",
        rotate: float = 0.0,
        import_mode: IMAGE_IMPORT_MODES = "image",
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        smoothness: float = 0.0,
        samples_per_curve: int = 12,
        max_paths: int = 50,
    ) -> str:
        """Add an image to the canvas.

        Args:
            x, y: Top-left corner in normalized space.
            width, height: Dimensions in normalized space.
            href: URL or data URI of the image.
            document_id: Document UUID (omit to use active document).
            region_id: Optional unique ID.
            layer: Layer name.
            z_index: Paint order.
            preserve_aspect_ratio: SVG preserveAspectRatio value
                (default "xMidYMid meet").
            rotate: Rotation in degrees around image center.
            import_mode: "image" preserves href, "embed" stores fetched bytes
                as data URI, "svg_paths" imports SVG path data as vector regions.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        try:
            resolved_href = href
            if import_mode in ("embed", "svg_paths"):
                limit = MAX_SVG_IMPORT_BYTES if import_mode == "svg_paths" else MAX_EMBED_BYTES
                raw, mime = _read_href_bytes(href, max_bytes=limit)
                if import_mode == "embed":
                    resolved_href = _bytes_to_data_uri(raw, mime)
                else:
                    if not _is_svg_href(href, mime):
                        return "Error: import_mode='svg_paths' requires SVG input"
                    sw = stroke_width_to_norm(doc_id, stroke_width) or 0.005
                    path_defs = _svg_path_regions(
                        raw.decode("utf-8"),
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                        fill_override=fill,
                        stroke_override=stroke,
                        stroke_width=sw,
                        samples_per_curve=samples_per_curve,
                        max_paths=max_paths,
                    )
                    if not path_defs:
                        return "Error: SVG contained no supported <path d=\"...\"> elements"
                    created: list[str] = []
                    prefix = region_id or "svg_path"
                    for idx, path_def in enumerate(path_defs):
                        r = scene.create_region(
                            outline=path_def["outline"],
                            document_id=doc_id,
                            region_id=f"{prefix}_{idx:02d}" if len(path_defs) > 1 else prefix,
                            layer=layer,
                            z_index=z_index + idx,
                            constraints=CurveConstraints(smoothness=smoothness, closed=True),
                            style=Style(
                                fill=path_def["fill"],
                                stroke=path_def["stroke"],
                                stroke_width=path_def["stroke_width"],
                            ),
                            metadata={"tool": "insert_image", "import_mode": "svg_paths", "source_href": href},
                        )
                        if abs(rotate) > 0.001:
                            object.__setattr__(r.transform, "rotate", rotate)
                        created.append(r.id)
                    if len(created) > 1:
                        scene.group_regions(region_id or "svg_paths", created, doc_id, replace=True)
                    scene._persist(doc_id)
                    return f"SVG paths imported: regions={len(created)}, ids={', '.join(created[:6])}"

            r = scene.insert_image(
                x, y, width, height, resolved_href,
                document_id=doc_id, region_id=region_id,
                layer=layer, z_index=z_index,
                preserve_aspect_ratio=preserve_aspect_ratio,
                rotate=rotate,
            )
            return (
                f"Image added: id={r.id}, mode={import_mode}, "
                f"({x:.4f},{y:.4f}) {width:.4f}x{height:.4f}, "
                f"len(href)={len(resolved_href)}"
            )
        except (ValueError, RuntimeError, ET.ParseError, OSError, UnicodeDecodeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="create_primitive",
        description="Create an SVG primitive shape (rect, ellipse, line, "
        "polygon, star, arc), open polyline, or stroked compound path. "
        "Use for geometric objects where polygon outlines would be imprecise. "
        "💡 Stars: star shape = 4-point star in one call, not 16 tiny circles. "
        "💡 Pentagon: polygon with sides=5. "
        "💡 Fingers: rect with rx=half the width gives perfect pill shapes. "
        "💡 Palm creases: line for stroke-only wrinkles. "
        "💡 Curved lines: use type='polyline' with points and smoothness. "
        "💡 Compound strokes: use type='compound_path' with subpaths to keep many seams/cables as one region. "
        "Shape object keys per type:\n"
        "  rect:     x, y, width, height, rx? (corner radius), taper? (trapezoid)\n"
        "  ellipse:  cx, cy, rx, ry? (ry=rx if omitted)\n"
        "  line:     x1, y1, x2, y2 (or points for backward-compatible polyline)\n"
        "  polyline: points ([[x,y],...]), closed?, smoothness?\n"
        "  compound_path: subpaths ([[[x,y],...], ...]), closed?, smoothness?\n"
        "  polygon:  cx, cy, r, sides? (default 6), rotate?\n"
        "  star:     cx, cy, r, r_inner?, points? (default 5), rotate?\n"
        "  arc:      cx, cy, r, start_angle?, end_angle?",
    )
    def create_primitive(
        shape: dict,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        z_before: str | None = None,
        z_after: str | None = None,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: StrokeWidthInput = None,
        opacity: float = 1.0,
        rotate: float = 0.0,
        blend_mode: BLEND_MODES | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        smoothness: float | None = None,
        closed: bool | None = None,
        groups: list[str] | None = None,
        relative_to: str | None = None,
        outline_pattern: str | None = None,
        fill_pattern: str | None = None,
        pattern_density: int = 12,
        pattern_amplitude: float = 0.02,
        pattern_jitter: float = 0.0,
        pattern_seed: int = 1,
        pattern_stroke_width: StrokeWidthInput = None,
        pattern_opacity: float | None = None,
    ) -> str:
        """Create an SVG primitive shape.

        Args:
            shape: Dict with ``type`` ("rect", "ellipse", "line", "star", "polygon", "arc") and params.
                rect:   {"type":"rect", "x":0.1, "y":0.1, "width":0.3, "height":0.15, "rx":0.02}
                rect with taper: {"type":"rect", "x":0.1, "y":0.1, "width":0.3, "height":0.5, "rx":0.02, "taper":0.3}
                ellipse: {"type":"ellipse", "cx":0.5, "cy":0.5, "rx":0.1}
                line:   {"type":"line", "x1":0.1, "y1":0.5, "x2":0.9, "y2":0.5}
                polyline: {"type":"polyline", "points":[[0.1,0.5],[0.3,0.4],[0.5,0.5]]}
                compound_path: {"type":"compound_path", "subpaths":[[[0.1,0.2],[0.9,0.2]], [[0.1,0.4],[0.9,0.4]]]}
                star:   {"type":"star", "cx":0.5, "cy":0.5, "r":0.12, "points":4, "r_inner":0.05}
                polygon: {"type":"polygon", "cx":0.5, "cy":0.5, "r":0.1, "sides":8}
                arc:    {"type":"arc", "cx":0.5, "cy":0.5, "r":0.1, "start_angle":0, "end_angle":180}
            document_id: Document UUID (omit to use active document).
            region_id: Optional unique ID.
            layer: Layer name.
            z_index: Paint order.
            z_before: Place this region directly behind the region with this ID.
            z_after: Place this region directly in front of the region with this ID.
            fill: Fill hex color, gradient dict, or "none"/"transparent" for no fill.
            stroke: Stroke color.
            stroke_width: Stroke width in canvas pixels.
            opacity: Opacity 0.0–1.0.
            rotate: Rotation in degrees around the shape center (positive = clockwise).
                💡 For hands/pointers: create a vertical rect at center, then rotate.
            blend_mode: CSS mix-blend-mode.
            stroke_linecap: Line end style — "butt", "round", or "square" (mainly for line shapes).
            stroke_dasharray: Dash pattern for stroked primitives.
            smoothness: Default curve smoothness for polyline/compound_path.
            closed: Default closed flag for polyline/compound_path.
            relative_to: Region ID to use as coordinate reference. When set,
                outline points are treated as 0.0-1.0 fractions of the reference
                region's bounding box, then mapped to absolute canvas coordinates.
                💡 Place a bolt at (0.5, 0.5) on a belt panel without measuring.
            groups: Optional list of group names to add this region to.
            outline_pattern: Optional outline style: dashed, dotted, wavy,
                zigzag, rough, sketch, tapered, or pressure.
            fill_pattern: Optional clipped interior texture for closed primitives:
                hatch, cross_hatch, contour_hatch, scribble, or stipple.
            pattern_density/amplitude/jitter/seed: Controls for generated pattern overlays.
            pattern_stroke_width: Pattern overlay stroke width in canvas pixels.
            pattern_opacity: Pattern overlay opacity.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        pattern_width = stroke_width_to_norm(doc_id, pattern_stroke_width) or stroke_width

        # Resolve z_index from z_before/z_after
        resolved_z = z_index
        try:
            if z_before is not None:
                ref = scene.get_region(z_before, doc_id)
                resolved_z = ref.z_index - 1
            elif z_after is not None:
                ref = scene.get_region(z_after, doc_id)
                resolved_z = ref.z_index + 1
        except ValueError:
            return f"Error: Reference region for z-ordering not found"

        # Transform relative coords to absolute if relative_to is set
        if relative_to is not None:
            shape = _relative_shape(scene, doc_id, relative_to, shape)

        stype = shape.get("type")
        try:
            if stype == "rect":
                r = scene.create_rect(
                    shape["x"], shape["y"], shape["width"], shape["height"],
                    rx=shape.get("rx", 0.0),
                    document_id=doc_id, region_id=region_id,
                    layer=layer, z_index=resolved_z,
                    fill=fill, stroke=stroke,
                    stroke_width=stroke_width, opacity=opacity,
                    blend_mode=blend_mode,
                    taper=shape.get("taper", 0.0),
                )
                if groups:
                    for g in groups:
                        scene.add_to_group(g, [r.id], doc_id)
                pattern_ids = _apply_primitive_patterns(
                    scene, doc_id, r, outline_pattern, fill_pattern,
                    pattern_density, pattern_amplitude, pattern_jitter,
                    pattern_seed, stroke, pattern_width, pattern_opacity,
                    layer, resolved_z,
                )
                rxn = f", rx={shape.get('rx',0)}" if shape.get('rx',0) > 0 else ""
                tpn = f", taper={shape.get('taper',0)}" if shape.get('taper',0) else ""
                extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                return f"Rect created: id={r.id}, {shape['x']:.4f},{shape['y']:.4f} {shape['width']:.4f}x{shape['height']:.4f}{rxn}{tpn}{extra}"
            elif stype == "ellipse":
                e = scene.create_ellipse(
                    shape["cx"], shape["cy"], shape["rx"],
                    ry=shape.get("ry"),
                    document_id=doc_id, region_id=region_id,
                    layer=layer, z_index=resolved_z,
                    fill=fill, stroke=stroke,
                    stroke_width=stroke_width, opacity=opacity,
                    blend_mode=blend_mode,
                    rotate=rotate,
                )
                if groups:
                    for g in groups:
                        scene.add_to_group(g, [e.id], doc_id)
                pattern_ids = _apply_primitive_patterns(
                    scene, doc_id, e, outline_pattern, fill_pattern,
                    pattern_density, pattern_amplitude, pattern_jitter,
                    pattern_seed, stroke, pattern_width, pattern_opacity,
                    layer, resolved_z,
                )
                rys = shape.get("ry", shape["rx"])
                extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                return f"Ellipse created: id={e.id}, cx={shape['cx']:.4f} cy={shape['cy']:.4f} rx={shape['rx']:.4f} ry={rys:.4f}{extra}"
            elif stype in ("line", "polyline"):
                pts = shape.get("points")
                if pts is not None:
                    if len(pts) < 2:
                        return "Error: polyline requires at least 2 points"
                    is_closed = bool(shape.get("closed", closed if closed is not None else False))
                    line_smoothness = shape.get("smoothness", smoothness)
                    if is_closed:
                        lr = scene.create_region(
                            outline=[(float(p[0]), float(p[1])) for p in pts],
                            document_id=doc_id, region_id=region_id,
                            layer=layer, z_index=resolved_z,
                            constraints=CurveConstraints(
                                smoothness=max(0.0, min(1.0, line_smoothness if line_smoothness is not None else 0.0)),
                                closed=True,
                            ),
                            style=Style(
                                fill=None if fill in (None, "none", "transparent") else fill,
                                stroke=None if stroke in (None, "none") else stroke,
                                stroke_width=stroke_width,
                                opacity=opacity,
                                blend_mode=blend_mode,
                                stroke_linecap=stroke_linecap,
                                stroke_dasharray=stroke_dasharray,
                            ),
                        )
                    else:
                        lr = scene.create_line(
                            points=pts,
                            document_id=doc_id, region_id=region_id,
                            layer=layer, z_index=resolved_z,
                            stroke=stroke, stroke_width=stroke_width,
                            opacity=opacity, blend_mode=blend_mode,
                            stroke_linecap=stroke_linecap,
                            stroke_dasharray=stroke_dasharray,
                            smoothness=line_smoothness,
                            rotate=rotate,
                        )
                    if groups:
                        for g in groups:
                            scene.add_to_group(g, [lr.id], doc_id)
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, lr, outline_pattern, fill_pattern if is_closed else None,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    closed_note = ", closed" if is_closed else ""
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Polyline created: id={lr.id}, {len(pts)} points{closed_note}{extra}"
                else:
                    lr = scene.create_line(
                        shape.get("x1", 0.0), shape.get("y1", 0.0),
                        shape.get("x2", 0.5), shape.get("y2", 0.5),
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=resolved_z,
                        stroke=stroke, stroke_width=stroke_width,
                        opacity=opacity, blend_mode=blend_mode,
                        stroke_linecap=stroke_linecap,
                        stroke_dasharray=stroke_dasharray,
                        rotate=rotate,
                    )
                    if groups:
                        for g in groups:
                            scene.add_to_group(g, [lr.id], doc_id)
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, lr, outline_pattern, None,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Line created: id={lr.id}, ({shape.get('x1',0):.4f},{shape.get('y1',0):.4f}) → ({shape.get('x2',0.5):.4f},{shape.get('y2',0.5):.4f}){extra}"
            elif stype in ("compound_path", "path"):
                    subpaths = shape.get("subpaths")
                    if subpaths is None and shape.get("points") is not None:
                        subpaths = [shape["points"]]
                    if not subpaths:
                        return "Error: compound_path requires subpaths"
                    r = scene.create_compound_path(
                        subpaths=subpaths,
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=resolved_z,
                        fill=None if fill in (None, "none", "transparent") else fill,
                        stroke=None if stroke in (None, "none") else stroke,
                        stroke_width=stroke_width,
                        opacity=opacity,
                        blend_mode=blend_mode,
                        stroke_linecap=stroke_linecap,
                        stroke_dasharray=stroke_dasharray,
                        smoothness=shape.get("smoothness", smoothness if smoothness is not None else 0.0),
                        closed=bool(shape.get("closed", closed if closed is not None else False)),
                        rotate=rotate,
                    )
                    if groups:
                        for g in groups:
                            scene.add_to_group(g, [r.id], doc_id)
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, r, outline_pattern, fill_pattern if r.constraints.closed else None,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Compound path created: id={r.id}, {len(subpaths)} subpath(s){extra}"
            elif stype == "arc":
                    pts = compute_arc(shape["cx"], shape["cy"], shape["r"],
                        start_angle=shape.get("start_angle", 0.0), end_angle=shape.get("end_angle", 180.0))
                    r = scene.create_region(outline=pts, document_id=doc_id, region_id=region_id, layer=layer, z_index=resolved_z,
                        constraints=CurveConstraints(smoothness=0.5, closed=False),
                        style=Style(fill=fill, stroke=stroke, stroke_width=stroke_width, opacity=opacity))
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, r, outline_pattern, None,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Arc created: id={r.id}, ({shape['cx']:.4f},{shape['cy']:.4f}) r={shape['r']:.4f}{extra}"
            elif stype == "polygon":
                    pts = compute_polygon(shape["cx"], shape["cy"], shape["r"],
                        sides=shape.get("sides", 6), rotation=shape.get("rotate", shape.get("rotation", 0.0)))
                    r = scene.create_region(outline=pts, document_id=doc_id, region_id=region_id, layer=layer, z_index=resolved_z,
                        constraints=CurveConstraints(smoothness=0.0, closed=True),
                        style=Style(fill=fill, stroke=stroke, stroke_width=stroke_width, opacity=opacity))
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, r, outline_pattern, fill_pattern,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Polygon created: id={r.id}, {shape.get('sides',6)} sides{extra}"
            elif stype == "star":
                    inner_radius = shape.get("r_inner")
                    if inner_radius is None:
                        inner_radius = shape["r"] * 0.5
                    pts = compute_star(shape["cx"], shape["cy"], shape["r"],
                        inner_radius, points=shape.get("points", 5), rotation=shape.get("rotate", shape.get("rotation", 0.0)))
                    r = scene.create_region(outline=pts, document_id=doc_id, region_id=region_id, layer=layer, z_index=resolved_z,
                        constraints=CurveConstraints(smoothness=0.0, closed=True),
                        style=Style(fill=fill, stroke=stroke, stroke_width=stroke_width, opacity=opacity))
                    pattern_ids = _apply_primitive_patterns(
                        scene, doc_id, r, outline_pattern, fill_pattern,
                        pattern_density, pattern_amplitude, pattern_jitter,
                        pattern_seed, stroke, pattern_width, pattern_opacity,
                        layer, resolved_z,
                    )
                    extra = f", pattern_regions={len(pattern_ids)}" if pattern_ids else ""
                    return f"Star created: id={r.id}, {shape.get('points',5)} points{extra}"
            else:
                return f"Error: Unknown shape type '{stype}'. Supported: rect, ellipse, line, polyline, compound_path, path, arc, polygon, star"
        except (ValueError, RuntimeError, KeyError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="create_curve",
        description="Create a smooth curved line through 3+ control points. "
        "Unlike create_region (filled shapes) or create_shape (primitives), "
        "create_curve produces a thin stroked path that curves through your "
        "points with Catmull-Rom interpolation. "
        "💡 Hair strands: 4-6 points with smoothness=0.5, stroke='#3D2B1F', "
        "stroke_width=3, stroke_linecap='round' "
        "💡 Wrinkles/creases: 3-4 points with smoothness=0.4, "
        "stroke_width=1.5, stroke_linecap='round' "
        "💡 Eyebrows, smile lines: 3 points, smoothness=0.6, "
        "stroke_linecap='round'",
    )
    def create_curve(
        points: list[list[float]],
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        stroke: str | None = "#333333",
        stroke_width: StrokeWidthInput = None,
        opacity: float = 1.0,
        smoothness: float = 0.5,
        blend_mode: BLEND_MODES | None = None,
        stroke_linecap: str | None = "round",
        stroke_dasharray: str | None = None,
        relative_to: str | None = None,
        outline_pattern: str | None = None,
        pattern_density: int = 12,
        pattern_amplitude: float = 0.02,
        pattern_jitter: float = 0.0,
        pattern_seed: int = 1,
        pattern_stroke_width: StrokeWidthInput = None,
        pattern_opacity: float | None = None,
    ) -> str:
        """Create a smooth curved line through 3+ control points.

        Args:
            points: List of [x, y] control points in normalized space (3+ required).
            document_id: Document UUID (omit to use active document).
            region_id: Optional unique ID.
            layer: Layer name (default "default").
            z_index: Paint order (higher = on top).
            stroke: Stroke color (default "#333333").
            stroke_width: Stroke width in canvas pixels.
            opacity: Object opacity 0.0–1.0.
            smoothness: Curve smoothness 0.0–1.0 (default 0.5).
            blend_mode: CSS mix-blend-mode.
            stroke_linecap: Line end style — "round" (default), "butt", or "square".
            stroke_dasharray: Dash pattern for strokes (e.g. "4,2").
            relative_to: Region ID to use as coordinate reference. Points are
                treated as 0.0-1.0 fractions of the reference region's bounds.
            outline_pattern: Optional line style overlay: dashed, dotted, wavy,
                zigzag, rough, sketch, tapered, or pressure.
            pattern_density/amplitude/jitter/seed: Controls for generated outline pattern.
            pattern_stroke_width: Pattern overlay stroke width in canvas pixels.
            pattern_opacity: Pattern overlay opacity.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        pattern_width = stroke_width_to_norm(doc_id, pattern_stroke_width) or stroke_width

        if not points or len(points) < 2:
            return "Error: Need at least 2 points"
        if len(points) > 100:
            return f"Error: Too many points ({len(points)}), max 100"

        # Transform relative coords to absolute if relative_to is set
        if relative_to is not None:
            points = _relative_to_absolute(scene, doc_id, relative_to, points)

        try:
            if len(points) == 2:
                x1, y1 = points[0]
                x2, y2 = points[1]
                lr = scene.create_line(
                    x1, y1, x2, y2,
                    document_id=doc_id, region_id=region_id,
                    layer=layer, z_index=z_index,
                    stroke=stroke, stroke_width=stroke_width,
                    opacity=opacity, blend_mode=blend_mode,
                    stroke_linecap=stroke_linecap,
                    stroke_dasharray=stroke_dasharray,
                )
            else:
                lr = scene.create_line(
                    points=points,
                    document_id=doc_id, region_id=region_id,
                    layer=layer, z_index=z_index,
                    stroke=stroke, stroke_width=stroke_width,
                    opacity=opacity, blend_mode=blend_mode,
                    stroke_linecap=stroke_linecap,
                    stroke_dasharray=stroke_dasharray,
                    smoothness=smoothness,
                )
            pattern_ids = _apply_primitive_patterns(
                scene, doc_id, lr, outline_pattern, None,
                pattern_density, pattern_amplitude, pattern_jitter,
                pattern_seed, stroke, pattern_width, pattern_opacity,
                layer, z_index,
            )
            return (
                f"Curve created: id={lr.id}, {len(points)} points, "
                f"smoothness={smoothness}, stroke_width={stroke_width}, "
                f"stroke_linecap='{stroke_linecap}'"
                f"{', pattern_regions=' + str(len(pattern_ids)) if pattern_ids else ''}"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="copy_element",
        description="Copy any element (region, rect, text, image, ellipse, line) "
        "or group from one document to another. "
        "💡 Reuse characters, props, or backgrounds across pages "
        "instead of rebuilding from scratch. "
        "Copies all properties: outline, style, primitive, transform, metadata. "
        "💡 Pass group_name='cat' to copy all group members at once. "
        "💡 Use offset_x/y to reposition in the target doc. "
        "Example: copy_element(region_id='head', target_document_id='doc_p2') "
        "Example: copy_element(group_name='building', target_document_id='doc_p2', "
        "source_document_id='doc_p1', offset_x=0.2)",
    )
    def copy_element(
        region_id: str | None = None,
        group_name: str | None = None,
        target_document_id: str | None = None,
        source_document_id: str | None = None,
        new_region_id: str | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> str:
        """Copy any element or group from one document to another.

        Args:
            region_id: ID of the element to copy (omit if using group).
            group_name: Group name — copies all group members at once.
            target_document_id: Destination document UUID.
            source_document_id: Source document UUID (omit for current active doc).
            new_region_id: Optional new ID for the copy (single region only).
            offset_x, offset_y: Position offset for the copy.
        """
        try:
            result = RegionService().copy_element(
                region_id=region_id,
                group_name=group_name,
                target_document_id=target_document_id,
                source_document_id=source_document_id,
                new_region_id=new_region_id,
                offset_x=offset_x,
                offset_y=offset_y,
            )
        except RuntimeError:
            return "Error: No active source document"
        except LookupError as e:
            return f"Error: {e}"
        except ValueError as e:
            return f"Error: {e}"

        if result.group_name is not None:
            return (
                f"Copied group '{result.group_name}' ({len(result.copied_ids)} elements) "
                f"to '{result.target_document_id}': {', '.join(result.copied_ids)}"
            )

        return (
            f"Copied '{result.source_region_id}' from {result.source_document_id} to "
            f"'{result.target_document_id}' as '{result.copied_ids[0]}'"
        )
