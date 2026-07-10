"""Region controller — create_region, delete_region, edit_region, duplicate_region."""
from __future__ import annotations

import json as _json
from typing import Any, Literal

from avge_engine.services.engine import get_graph, resolve_doc, validate_input
from avge_engine.scene import CurveConstraints, Style
from avge_engine.geometry import compute_bounds

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "soft-light", "hard-light",
]


def create_tools(mcp):
    """Register region tools on the given FastMCP instance."""

    @mcp.tool(
        name="create_region",
        description="Create a vector region from a coarse point outline. "
        "The engine fits smooth Bézier curves to your points. "
        "⚠️ Coordinates MUST be in normalized 0.0–1.0 space "
        "((0,0)=top-left, (1,1)=bottom-right). Passing pixel "
        "coordinates (0-1000) will be rejected with an error. "
        "Edit incrementally: add regions here, use style_objects "
        "to recolor, delete_region to remove — never rebuild "
        "the whole document from scratch. "
        "📏 Proportion tip: an object's canvas footprint must "
        "match its real-world size. A desk is ~90%+ of canvas "
        "width; headphones on it are ~15–25%; a bottle ~6–8%. "
        "If it sits on a surface, its width ≤ ¼ of the surface. "
        "See resource avge://skill/design-guidelines Rule 5. "
        "⚠️ When adding a new object to a scene with existing objects, "
        "first check existing object sizes via describe_scene and match "
        "the perspective convention already established (check existing "
        "outlines to choose top-down vs. front-elevation). Objects resting "
        "on a surface must share their contact edge y with the surface's "
        "top edge — check the surface's bounds first to avoid a gap. "
        "Smoothness guidance (per-region): "
        "- Geometric/polygonal (houses, stars, rectangles): smoothness=0.0–0.1 "
        "- Mixed rigid/organic (cup body, tree trunk, saucer): smoothness=0.2–0.5 "
        "- Organic/curved (foliage, faces, circles): smoothness=0.6–0.8 "
        "- Smoothness=0.5 is the default — adjust per-region per the above. "
        "For filled shapes, prefer two-tone shading "
        "(a base fill + a darker adjacent region along one edge) "
        "over a single flat fill to imply depth. See resource "
        "avge://skill/design-guidelines for full conventions.",
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
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        fill_gradient: Any | None = None,
        smoothness_per_point: list[float] | None = None,
        z_index: int = 0,
        clip_to: str | None = None,
        blend_mode: BLEND_MODES | None = None,
        tags: dict | None = None,
        shape: dict | None = None,
        stroke_linecap: str | None = None,
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
            region_id: Optional unique ID (auto-generated if omitted).
            document_id: Document UUID (omit to use active document).
            layer: Layer name (default "default").
            closed: Whether polygon shape is closed (default True).
            smoothness: 0.0–1.0. See description above for per-category guidance.
            fill: Fill hex color, or omit for no fill.
            stroke: Stroke hex color, or omit for no stroke.
            stroke_width: Stroke width in normalized units.
            opacity: Object opacity 0.0–1.0.
            fill_gradient: Gradient definition dict or JSON string.
            smoothness_per_point: JSON array of per-vertex tension values.
            z_index: Paint order (higher = on top).
            clip_to: Region ID to constrain rendering inside that region's outline.
            blend_mode: CSS mix-blend-mode.
            tags: JSON object of key/value metadata tags.
            stroke_linecap: Line end style for line shapes — "butt", "round", or "square".
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        # ── SVG primitive path ────────────────────────────────────────
        if shape is not None:
            stype = shape.get("type")
            try:
                if stype == "rect":
                    r = scene.create_rect(
                        shape["x"], shape["y"], shape["width"], shape["height"],
                        rx=shape.get("rx", 0.0),
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=z_index,
                        fill=fill, stroke=stroke,
                        stroke_width=stroke_width, opacity=opacity,
                        blend_mode=blend_mode,
                        taper=shape.get("taper", 0.0),
                    )
                    rxn = f", rx={shape.get('rx',0)}" if shape.get('rx',0) > 0 else ""
                    tpn = f", taper={shape.get('taper',0)}" if shape.get('taper',0) else ""
                    return f"Rect created: id={r.id}, {shape.get('x',0):.4f},{shape.get('y',0):.4f} {shape.get('width',0):.4f}x{shape.get('height',0):.4f}{rxn}{tpn}"
                elif stype == "ellipse":
                    e = scene.create_ellipse(
                        shape["cx"], shape["cy"], shape["rx"],
                        ry=shape.get("ry", None),
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=z_index,
                        fill=fill, stroke=stroke,
                        stroke_width=stroke_width, opacity=opacity,
                        blend_mode=blend_mode,
                    )
                    rys = shape.get("ry", shape["rx"])
                    return f"Ellipse created: id={e.id}, cx={shape['cx']:.4f} cy={shape['cy']:.4f} rx={shape['rx']:.4f} ry={rys:.4f}"
                elif stype == "line":
                    pts = shape.get("points")
                    if pts is not None and len(pts) > 2:
                        lr = scene.create_line(
                            points=pts,
                            document_id=doc_id, region_id=region_id,
                            layer=layer, z_index=z_index,
                            stroke=stroke, stroke_width=stroke_width,
                            opacity=opacity, blend_mode=blend_mode,
                            stroke_linecap=stroke_linecap,
                        )
                        return f"Polyline created: id={lr.id}, {len(pts)} points"
                    else:
                        lr = scene.create_line(
                            shape["x1"], shape["y1"], shape["x2"], shape["y2"],
                            document_id=doc_id, region_id=region_id,
                            layer=layer, z_index=z_index,
                            stroke=stroke, stroke_width=stroke_width,
                            opacity=opacity, blend_mode=blend_mode,
                            stroke_linecap=stroke_linecap,
                        )
                        return f"Line created: id={lr.id}, ({shape['x1']:.4f},{shape['y1']:.4f}) → ({shape['x2']:.4f},{shape['y2']:.4f})"
                else:
                    return f"Error: Unknown shape type '{stype}'. Supported: rect, ellipse, line"
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
        )

        resolved_fill = fill
        if fill_gradient is not None:
            if isinstance(fill_gradient, str):
                try:
                    resolved_fill = _json.loads(fill_gradient)
                except _json.JSONDecodeError:
                    return f"Error: invalid fill_gradient JSON: {fill_gradient}"
            elif isinstance(fill_gradient, dict):
                resolved_fill = fill_gradient

        style = Style(
            fill=None if resolved_fill is None or resolved_fill == "none" else resolved_fill,
            stroke=None if stroke is None or stroke == "none" else stroke,
            stroke_width=max(0.001, min(0.1, stroke_width)),
            opacity=max(0.0, min(1.0, opacity)),
            blend_mode=blend_mode,
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
                z_index=z_index,
                clip_to=clip_to,
                constraints=constraints,
                style=style,
                metadata=metadata,
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

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
            f"{advisory}"
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
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        deleted = scene.delete_regions(doc_id, ids)
        if not deleted:
            return "No matching regions found to delete"
        return f"Deleted {len(deleted)} region(s): {', '.join(deleted)}"

    @mcp.tool(
        name="edit_region",
        description="Modify an existing region's outline, smoothness, style, z_index, "
        "blend_mode, clip_to, layer, or shape. Only provided fields are changed; "
        "omitted fields keep their values. This is the primary refinement "
        "tool — use it to nudge existing shapes rather than deleting and "
        "recreating them.",
    )
    def edit_region(
        region_id: str,
        document_id: str | None = None,
        outline: list[list[float]] | None = None,
        smoothness: float | None = None,
        smoothness_per_point: list[float] | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        z_index: int | None = None,
        blend_mode: BLEND_MODES | None = None,
        clip_to: str | None = None,
        layer: str | None = None,
        tags: dict | None = None,
        shape: dict | None = None,
        stroke_linecap: str | None = None,
    ) -> str:
        """Modify an existing region's properties.

        Args:
            region_id: ID of the region to edit.
            document_id: Document UUID (omit for active doc).
            outline: New outline coordinates (omit to keep current).
            smoothness: New smoothness value (omit to keep current).
            smoothness_per_point: JSON array of per-vertex tensions.
            fill: New fill hex color or gradient (omit to keep current).
            stroke: New stroke color.
            stroke_width: New stroke width.
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
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        try:
            tensions = smoothness_per_point

            metadata = None
            if tags:
                metadata = dict(tags)

            scene.edit_region(
                region_id=region_id,
                document_id=doc_id,
                outline=outline,
                smoothness=smoothness,
                tensions=tensions,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                z_index=z_index,
                blend_mode=blend_mode,
                clip_to=clip_to,
                layer=layer,
                metadata=metadata,
                shape=shape,
                stroke_linecap=stroke_linecap,
            )
            return f"Region '{region_id}' updated"
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="create_shape",
        description="Create an SVG primitive shape (rect, ellipse, line) "
        "or a polyline. "
        "Use for geometric objects where polygon outlines would be imprecise. "
        "💡 Fingers: rect with rx=half the width gives perfect pill shapes. "
        "💡 Palm creases: line for stroke-only wrinkles. "
        "💡 Curved lines: use points array for multi-point smooth curves.",
    )
    def create_shape(
        shape: dict,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#E8C8A0",
        stroke: str | None = "#5A4A3A",
        stroke_width: float = 0.006,
        opacity: float = 1.0,
        blend_mode: BLEND_MODES | None = None,
        stroke_linecap: str | None = None,
    ) -> str:
        """Create an SVG primitive shape.

        Args:
            shape: Dict with ``type`` ("rect", "ellipse", "line") and params.
                rect:   {"type":"rect", "x":0.1, "y":0.1, "width":0.3, "height":0.15, "rx":0.02}
                rect with taper: {"type":"rect", "x":0.1, "y":0.1, "width":0.3, "height":0.5, "rx":0.02, "taper":0.3}
                ellipse: {"type":"ellipse", "cx":0.5, "cy":0.5, "rx":0.1}
                line:   {"type":"line", "x1":0.1, "y1":0.5, "x2":0.9, "y2":0.5}
                polyline: {"type":"line", "points":[[0.1,0.5],[0.3,0.4],[0.5,0.5],[0.7,0.4]]}
            document_id: Document UUID (omit to use active document).
            region_id: Optional unique ID.
            layer: Layer name.
            z_index: Paint order.
            fill: Fill color (ignored for line).
            stroke: Stroke color.
            stroke_width: Stroke width.
            opacity: Opacity 0.0–1.0.
            blend_mode: CSS mix-blend-mode.
            stroke_linecap: Line end style — "butt", "round", or "square" (mainly for line shapes).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."
        stype = shape.get("type")
        try:
            if stype == "rect":
                r = scene.create_rect(
                    shape["x"], shape["y"], shape["width"], shape["height"],
                    rx=shape.get("rx", 0.0),
                    document_id=doc_id, region_id=region_id,
                    layer=layer, z_index=z_index,
                    fill=fill, stroke=stroke,
                    stroke_width=stroke_width, opacity=opacity,
                    blend_mode=blend_mode,
                    taper=shape.get("taper", 0.0),
                )
                rxn = f", rx={shape.get('rx',0)}" if shape.get('rx',0) > 0 else ""
                tpn = f", taper={shape.get('taper',0)}" if shape.get('taper',0) else ""
                return f"Rect created: id={r.id}, {shape['x']:.4f},{shape['y']:.4f} {shape['width']:.4f}x{shape['height']:.4f}{rxn}{tpn}"
            elif stype == "ellipse":
                e = scene.create_ellipse(
                    shape["cx"], shape["cy"], shape["rx"],
                    ry=shape.get("ry"),
                    document_id=doc_id, region_id=region_id,
                    layer=layer, z_index=z_index,
                    fill=fill, stroke=stroke,
                    stroke_width=stroke_width, opacity=opacity,
                    blend_mode=blend_mode,
                )
                rys = shape.get("ry", shape["rx"])
                return f"Ellipse created: id={e.id}, cx={shape['cx']:.4f} cy={shape['cy']:.4f} rx={shape['rx']:.4f} ry={rys:.4f}"
            elif stype == "line":
                pts = shape.get("points")
                if pts is not None and len(pts) > 2:
                    lr = scene.create_line(
                        points=pts,
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=z_index,
                        stroke=stroke, stroke_width=stroke_width,
                        opacity=opacity, blend_mode=blend_mode,
                        stroke_linecap=stroke_linecap,
                    )
                    return f"Polyline created: id={lr.id}, {len(pts)} points"
                else:
                    lr = scene.create_line(
                        shape.get("x1", 0.0), shape.get("y1", 0.0),
                        shape.get("x2", 0.5), shape.get("y2", 0.5),
                        document_id=doc_id, region_id=region_id,
                        layer=layer, z_index=z_index,
                        stroke=stroke, stroke_width=stroke_width,
                        opacity=opacity, blend_mode=blend_mode,
                        stroke_linecap=stroke_linecap,
                    )
                    return f"Line created: id={lr.id}, ({shape.get('x1',0):.4f},{shape.get('y1',0):.4f}) → ({shape.get('x2',0.5):.4f},{shape.get('y2',0.5):.4f})"
            else:
                return f"Error: Unknown shape type '{stype}'. Supported: rect, ellipse, line"
        except (ValueError, RuntimeError, KeyError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="create_curve",
        description="Create a smooth curved line through 3+ control points. "
        "Unlike create_region (filled shapes) or create_shape (primitives), "
        "create_curve produces a thin stroked path that curves through your "
        "points with Catmull-Rom interpolation. "
        "💡 Hair strands: 4-6 points with smoothness=0.5, stroke='#3D2B1F', "
        "stroke_width=0.003, stroke_linecap='round' "
        "💡 Wrinkles/creases: 3-4 points with smoothness=0.4, "
        "stroke_width=0.0015, stroke_linecap='round' "
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
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        smoothness: float = 0.5,
        blend_mode: BLEND_MODES | None = None,
        stroke_linecap: str | None = "round",
    ) -> str:
        """Create a smooth curved line through 3+ control points.

        Args:
            points: List of [x, y] control points in normalized space (3+ required).
            document_id: Document UUID (omit to use active document).
            region_id: Optional unique ID.
            layer: Layer name (default "default").
            z_index: Paint order (higher = on top).
            stroke: Stroke color (default "#333333").
            stroke_width: Stroke width in normalized units.
            opacity: Object opacity 0.0–1.0.
            smoothness: Curve smoothness 0.0–1.0 (default 0.5).
            blend_mode: CSS mix-blend-mode.
            stroke_linecap: Line end style — "round" (default), "butt", or "square".
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        if not points or len(points) < 2:
            return "Error: Need at least 2 points"
        if len(points) > 100:
            return f"Error: Too many points ({len(points)}), max 100"

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
                )
            else:
                lr = scene.create_line(
                    points=points,
                    document_id=doc_id, region_id=region_id,
                    layer=layer, z_index=z_index,
                    stroke=stroke, stroke_width=stroke_width,
                    opacity=opacity, blend_mode=blend_mode,
                    stroke_linecap=stroke_linecap,
                    smoothness=smoothness,
                )
            return (
                f"Curve created: id={lr.id}, {len(points)} points, "
                f"smoothness={smoothness}, stroke_width={stroke_width}, "
                f"stroke_linecap='{stroke_linecap}'"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="duplicate_region",
        description="Duplicate an existing region with optional offset, mirror, and recolor. "
        "Use this for highlights and shadow slivers — clone the base "
        "shape, offset it slightly, and change its fill/opacity — "
        "instead of authoring a new outline from scratch. "
        "💡 Use mirror_x=True to flip horizontally (great for symmetrical limbs).",
    )
    def duplicate_region(
        region_id: str,
        new_region_id: str | None = None,
        document_id: str | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        smoothness: float | None = None,
        z_index: int | None = None,
        mirror_x: bool = False,
        mirror_y: bool = False,
        scale: float = 1.0,
        rotate: float = 0.0,
    ) -> str:
        """Duplicate a region with optional offset, mirror, scale, rotation.

        Args:
            region_id: ID of the region to duplicate.
            new_region_id: ID for the copy (auto-generated if omitted).
            document_id: Document UUID (omit for active doc).
            offset_x: X offset for the copy in normalized units.
            offset_y: Y offset for the copy in normalized units.
            fill: Override fill color for the copy.
            stroke: Override stroke color for the copy.
            stroke_width: Override stroke width for the copy.
            opacity: Override opacity for the copy.
            smoothness: Override smoothness for the copy.
            z_index: Z-index for the copy (defaults to original + 1).
            mirror_x: Mirror horizontally (flip around original's center).
            mirror_y: Mirror vertically (flip around original's center).
            scale: Uniform scale factor (0.5 = half size, 2.0 = double).
            rotate: Rotation in degrees (positive = clockwise around center).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        try:
            dup = scene.duplicate_region(
                region_id=region_id,
                new_region_id=new_region_id,
                document_id=doc_id,
                offset_x=offset_x,
                offset_y=offset_y,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                smoothness=smoothness,
                z_index=z_index,
                mirror_x=mirror_x,
                mirror_y=mirror_y,
                scale=scale,
                rotate=rotate,
            )
            parts = [f"offset={offset_x},{offset_y}"]
            if scale != 1.0:
                parts.append(f"scale={scale}")
            if rotate:
                parts.append(f"rotate={rotate}°")
            if mirror_x:
                parts.append("mirror_x")
            if mirror_y:
                parts.append("mirror_y")
            return (
                f"Duplicated '{region_id}' as '{dup.id}' "
                f"({', '.join(parts)})"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

