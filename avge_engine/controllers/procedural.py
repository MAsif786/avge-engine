"""Procedural geometry controller — generate_shape tool."""
from __future__ import annotations

from typing import Any, Literal

from avge_engine.services.engine import get_graph, resolve_doc
from avge_engine.scene import CurveConstraints, Style
from avge_engine.geometry import compute_bounds

PATTERNS = Literal[
    "radial_spread",
    "offset_outline",
    "guide_lines",
    "distribute_points",
    "bridge_shapes",
    "interpolate_outlines",
    "distribute_linear",
    "apex_from_edge",
    "segmented_chain",
    "speech_bubble",
    "create_burst",
    "armature",
    "foreshorten",
    "surface_detail",
    "isometric_box",
]


def create_tools(mcp):
    """Register procedural geometry tools on the given FastMCP instance."""

    @mcp.tool(
        name="generate_shape",
        description="Generate geometry from a generic pattern function. "
        "Each pattern is a pure geometric operation — no domain knowledge. "
        "Patterns:\n"
        "  radial_spread — Fan N protrusions from one edge of a base shape.\n"
        "    Params: region_id, count, anchor, length_range, width, angle_spread, taper, length_variance\n"
        "  offset_outline — Expand (positive) or contract (negative) an outline uniformly.\n"
        "    Params: region_id, distance\n"
        "  guide_lines — Generate proportional division markers within a bounding box.\n"
        "    Params: bbox_x, bbox_y, bbox_w, bbox_h, ratios, horizontal\n"
        "  distribute_points — Place N evenly-spaced points along one edge.\n"
        "    Params: region_id, count, edge\n"
        "  bridge_shapes — Connect two overlapping outlines into one.\n"
        "    Params: region_id_a, region_id_b\n"
        "  interpolate_outlines — Create N morph steps between two outlines.\n"
        "    Params: region_id_a, region_id_b, steps\n"
        "  distribute_linear — Generate evenly-spaced points along a line.\n"
        "    Params: start (x,y), end (x,y), count\n"
        "    Returns coordinate list — feed into batch or create primitives.\n"
        "    💡 Place building walls, fence posts, window columns in one call.\n"
        "  apex_from_edge — Project a triangle (roof) from an outline edge.\n"
        "    Params: region_id (source outline), edge (top/bottom/left/right), apex_offset, inset\n"
        "    Creates a new region — roof triangle from a wall rect.\n"
        "    💡 Wall rect + apex_from_edge = complete building in 2 calls.\n"
        "    💡 inset=0.015 for roof overhang (wider than wall).\n"
        "  segmented_chain — Create a bent limb or curled finger chain.\n"
        "    Params: region_id (anchor), anchor (edge name), segments (list of dicts),\n"
        "    joint_radius, count (fan multiple chains), angle_spread\n"
        "    💡 One bent arm (2 segments + joint) or 5 curled fingers in 1 call.\n"
        "  create_burst — Radiating lines from center (impact/speed lines).\n"
        "    Params: cx, cy, count, radius_inner, radius_outer, start_angle, angle_span, taper, fill, stroke\n"
        "    💡 Sunbursts, impact effects, speed lines, auras in one call.\n"
        "  speech_bubble — Generate a speech bubble outline (rounded rect + tail).\n"
        "    Params: cx, cy, width, height, tail_direction (top/bottom/left/right),\n"
        "    tail_length, tail_width, rx (corner radius), fill, stroke\n"
        "    💡 Creates a region — add text inside with create_text.\n"
        "  isometric_box — Generate 3 visible faces of an isometric 3D box.\n"
        "    Params: x, y, width, depth, height, angle, fill, top_fill, left_fill, right_fill,\n"
        "      skip_faces (e.g. [\"top\"] for hidden leg faces), shadow (bool),\n"
        "      shadow_opacity (default 0.12), z_index, opacity, layer,\n"
        "      top_slant (vertical offset at front edge for slanted surfaces)\n"
        "    💡 relative_to positions legs at visual 0-1 of face bbox.\n"
        "      leg at (0.12,0.85) = front-left, (0.85,0.76) = front-right,\n"
        "      (0.12,0.15) = back-left, (0.85,0.24) = back-right.\n"
        "    💡 One gold bar = 1 call. Table leg: skip_faces=[\"top\"], shadow=true",
    )
    def generate_shape(
        pattern: PATTERNS,
        params: dict[str, Any],
        document_id: str | None = None,
        relative_to: str | None = None,
    ) -> str:
        """Generate geometry from a generic pattern.

        Args:
            pattern: Pattern name — which geometric operation to run.
            params: Pattern-specific parameters (see pattern descriptions).
            document_id: Document UUID (omit to use active document).
            relative_to: Region ID for relative coordinate mapping. When set,
                ``x`` and ``y`` are treated as 0–1 fractions of the reference
                region's bounding box. ``width``, ``depth``, ``height`` are
                always absolute (not scaled).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        # Resolve relative_to: transform coordinate params
        if relative_to is not None:
            _resolve_relative_box(scene, doc_id, relative_to, params)

        from avge_engine.geometry import procedural as geo

        try:
            if pattern == "radial_spread":
                return _do_radial_spread(scene, doc_id, params)
            elif pattern == "offset_outline":
                return _do_offset_outline(scene, doc_id, params)
            elif pattern == "guide_lines":
                return _do_guide_lines(params)
            elif pattern == "distribute_points":
                return _do_distribute_points(scene, doc_id, params)
            elif pattern == "bridge_shapes":
                return _do_bridge_shapes(scene, doc_id, params)
            elif pattern == "interpolate_outlines":
                return _do_interpolate(scene, doc_id, params)
            elif pattern == "distribute_linear":
                return _do_distribute_linear(params)
            elif pattern == "apex_from_edge":
                return _do_apex_from_edge(scene, doc_id, params)
            elif pattern == "segmented_chain":
                return _do_segmented_chain(scene, doc_id, params)
            elif pattern == "speech_bubble":
                return _do_speech_bubble(scene, doc_id, params)
            elif pattern == "create_burst":
                return _do_create_burst(scene, doc_id, params)
            elif pattern == "armature":
                return _do_armature(scene, doc_id, params)
            elif pattern == "foreshorten":
                return _do_foreshorten(scene, doc_id, params)
            elif pattern == "surface_detail":
                return _do_surface_detail(scene, doc_id, params)
            elif pattern == "isometric_box":
                return _do_isometric_box(scene, doc_id, params)
            else:
                return f"Error: Unknown pattern '{pattern}'"
        except (ValueError, RuntimeError, KeyError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="import_svg_path",
        description="Import an SVG path data string as a vector region. "
        "Parses M, L, C, Q, Z commands into outline points. "
        "💡 Use for complex silhouettes, logos, or any shape where "
        "typing coordinates manually would be impractical. "
        "Combine with smoothness=0.0 to preserve straight edges.",
    )
    def import_svg_path(
        path_data: str,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        smoothness: float = 0.0,
        closed: bool = True,
        samples_per_curve: int = 12,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> str:
        """Import an SVG path data string as a vector region.

        Args:
            path_data: SVG path data string (e.g. "M 0.1 0.1 C 0.5 0.8 0.9 0.1 1.0 0.5 Z").
            document_id: Document UUID (omit to use active document).
            region_id: Optional unique ID.
            layer: Layer name.
            z_index: Paint order.
            fill: Fill hex color.
            stroke: Stroke hex color.
            stroke_width: Stroke width.
            smoothness: Curve smoothness (0.0 = preserve straight edges).
            closed: Whether the path is closed.
            samples_per_curve: Points per bezier segment (higher = smoother curves).
            mirror_x: Mirror horizontally (flip around x-axis center).
                💡 Import one half of a symmetrical character, mirror it.
            mirror_y: Mirror vertically.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        from avge_engine.geometry.procedural import parse_svg_path

        outline = parse_svg_path(path_data, samples_per_curve=samples_per_curve)
        if not outline or len(outline) < 2:
            return "Error: Could not parse SVG path data — check syntax"

        if len(outline) > 500:
            return f"Error: Outline too large ({len(outline)} points, max 500)"

        # Apply mirror after parsing
        if mirror_x or mirror_y:
            xs = [p[0] for p in outline]
            ys = [p[1] for p in outline]
            cx = (min(xs) + max(xs)) / 2 if mirror_x else 0
            cy = (min(ys) + max(ys)) / 2 if mirror_y else 0
            outline = [
                ((2 * cx - p[0]) if mirror_x else p[0],
                 (2 * cy - p[1]) if mirror_y else p[1])
                for p in outline
            ]

        try:
            r = scene.create_region(
                outline=outline,
                region_id=region_id,
                document_id=doc_id,
                layer=layer,
                z_index=z_index,
                constraints=CurveConstraints(
                    smoothness=max(0.0, min(1.0, smoothness)),
                    closed=closed,
                ),
                style=Style(fill=fill, stroke=stroke, stroke_width=max(0.001, min(0.1, stroke_width))),
            )
            return (
                f"SVG path imported: id={r.id}, "
                f"{len(outline)} points, "
                f"smoothness={smoothness}"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"


def _resolve_params(params: dict, *keys: str) -> list:
    """Extract required keys from params dict, raising on missing ones."""
    result = []
    for key in keys:
        if key not in params:
            raise KeyError(f"Missing required param '{key}' for this pattern")
        result.append(params[key])
    return result


def _do_radial_spread(scene, doc_id: str, params: dict) -> str:
    """Create protrusions fanning from one edge of a region."""
    region_id = params.get("region_id")
    if not region_id or not scene.has_region(region_id, doc_id):
        return "Error: region_id is required and must exist"

    region = scene.get_region(region_id, doc_id)
    from avge_engine.geometry.procedural import radial_spread

    protrusions = radial_spread(
        region.outline,
        count=params.get("count", 5),
        anchor=params.get("anchor", "top_edge"),
        length_range=tuple(params.get("length_range", [0.1, 0.15])),
        width=params.get("width", 0.025),
        angle_spread=params.get("angle_spread", 30.0),
        taper=params.get("taper", 0.5),
        length_variance=params.get("length_variance", False),
    )

    if not protrusions:
        return "Error: No protrusions generated (check outline vs anchor)"

    fill = params.get("fill", region.style.fill)
    stroke = params.get("stroke", region.style.stroke)
    stroke_width = params.get("stroke_width", region.style.stroke_width)
    z_base = params.get("z_index", region.z_index + 1)

    created: list[str] = []
    for i, outline in enumerate(protrusions):
        rid = f"{region_id}_spread{i}"
        r = scene.create_region(
            outline=outline,
            region_id=rid,
            document_id=doc_id,
            layer=region.layer,
            z_index=z_base + i,
            constraints=CurveConstraints(smoothness=0.5, closed=True),
            style=Style(fill=fill, stroke=stroke, stroke_width=stroke_width),
        )
        created.append(r.id)

    return (
        f"radial_spread: created {len(created)} protrusion(s) on '{region_id}': "
        f"{', '.join(created)}"
    )


def _do_offset_outline(scene, doc_id: str, params: dict) -> str:
    """Inset or outset a region's outline."""
    region_id = params.get("region_id")
    if not region_id or not scene.has_region(region_id, doc_id):
        return "Error: region_id is required and must exist"

    region = scene.get_region(region_id, doc_id)
    distance = params.get("distance", 0.02)

    from avge_engine.geometry.procedural import offset_outline

    new_outline = offset_outline(
        region.outline,
        distance=distance,
        closed=region.constraints.closed,
    )

    if not new_outline or len(new_outline) < 3:
        return f"Error: offset produced degenerate outline ({len(new_outline)} pts)"

    new_rid = f"{region_id}_offset"
    r = scene.create_region(
        outline=new_outline,
        region_id=new_rid,
        document_id=doc_id,
        layer=region.layer,
        z_index=params.get("z_index", region.z_index + 1),
        constraints=CurveConstraints(smoothness=region.constraints.smoothness, closed=region.constraints.closed),
        style=Style(
            fill=params.get("fill", region.style.fill),
            stroke=params.get("stroke", region.style.stroke),
            stroke_width=params.get("stroke_width", region.style.stroke_width),
            opacity=params.get("opacity", region.style.opacity),
        ),
    )
    direction = "expanded" if distance > 0 else "contracted"
    return (
        f"offset_outline: {direction} '{region_id}' by {abs(distance)} "
        f"→ '{r.id}' ({len(new_outline)} pts)"
    )


def _do_guide_lines(params: dict) -> str:
    """Generate proportional division markers. Returns line coordinates."""
    from avge_engine.geometry.procedural import guide_lines

    divisions = params.get("divisions")
    if divisions:
        all_lines = []
        for div in divisions:
            is_h = div.get("axis", "h") == "h"
            lines = guide_lines(
                bbox_x=params.get("bbox_x", 0.0),
                bbox_y=params.get("bbox_y", 0.0),
                bbox_w=params.get("bbox_w", 1.0),
                bbox_h=params.get("bbox_h", 1.0),
                ratios=div.get("ratios", [0.5]),
                horizontal=is_h,
            )
            label = div.get("label", "")
            for l in lines:
                if label:
                    l["label"] = f"{label}:{l['label']}"
            all_lines.extend(lines)
        lines = all_lines
    else:
        lines = guide_lines(
            bbox_x=params.get("bbox_x", 0.0),
            bbox_y=params.get("bbox_y", 0.0),
            bbox_w=params.get("bbox_w", 1.0),
            bbox_h=params.get("bbox_h", 1.0),
            ratios=params.get("ratios", [0.25, 0.5, 0.75]),
            horizontal=params.get("horizontal", True),
        )

    lines_fmt = "; ".join(
        f"{l['label']}: ({l['start'][0]:.4f},{l['start'][1]:.4f})→({l['end'][0]:.4f},{l['end'][1]:.4f})"
        for l in lines
    )
    return f"guide_lines: {len(lines)} division(s): {lines_fmt}"


def _do_distribute_points(scene, doc_id: str, params: dict) -> str:
    """Place evenly-spaced points along an edge of a region."""
    region_id = params.get("region_id")
    if not region_id or not scene.has_region(region_id, doc_id):
        return "Error: region_id is required and must exist"

    region = scene.get_region(region_id, doc_id)
    from avge_engine.geometry.procedural import distribute_points

    points = distribute_points(
        region.outline,
        count=params.get("count", 5),
        edge=params.get("edge", "top_edge"),
        closed=region.constraints.closed,
    )

    pts_fmt = ", ".join(f"({p[0]:.4f},{p[1]:.4f})" for p in points)
    return f"distribute_points: {len(points)} point(s) on '{region_id}': {pts_fmt}"


def _do_bridge_shapes(scene, doc_id: str, params: dict) -> str:
    """Connect two overlapping regions into a single bridge shape."""
    rid_a = params.get("region_id_a")
    rid_b = params.get("region_id_b")
    if not rid_a or not rid_b:
        return "Error: region_id_a and region_id_b are required"
    if not scene.has_region(rid_a, doc_id):
        return f"Error: region '{rid_a}' not found"
    if not scene.has_region(rid_b, doc_id):
        return f"Error: region '{rid_b}' not found"

    region_a = scene.get_region(rid_a, doc_id)
    region_b = scene.get_region(rid_b, doc_id)

    from avge_engine.geometry.procedural import bridge_shapes

    new_outline = bridge_shapes(region_a.outline, region_b.outline)

    if not new_outline or len(new_outline) < 3:
        return f"Error: bridge produced degenerate outline ({len(new_outline)} pts)"

    new_rid = f"{rid_a}_bridge_{rid_b}"
    r = scene.create_region(
        outline=new_outline,
        region_id=new_rid,
        document_id=doc_id,
        layer=params.get("layer", region_a.layer),
        z_index=params.get("z_index", max(region_a.z_index, region_b.z_index) + 1),
        constraints=CurveConstraints(smoothness=0.4, closed=True),
        style=Style(
            fill=params.get("fill", "#CCCCCC"),
            stroke=params.get("stroke", "#333333"),
            stroke_width=params.get("stroke_width", 0.005),
        ),
    )
    return f"bridge_shapes: joined '{rid_a}' + '{rid_b}' → '{r.id}' ({len(new_outline)} pts)"


def _do_interpolate(scene, doc_id: str, params: dict) -> str:
    """Create intermediate outlines morphing between two source regions."""
    rid_a = params.get("region_id_a")
    rid_b = params.get("region_id_b")
    if not rid_a or not rid_b:
        return "Error: region_id_a and region_id_b are required"
    if not scene.has_region(rid_a, doc_id):
        return f"Error: region '{rid_a}' not found"
    if not scene.has_region(rid_b, doc_id):
        return f"Error: region '{rid_b}' not found"

    region_a = scene.get_region(rid_a, doc_id)
    region_b = scene.get_region(rid_b, doc_id)
    steps = params.get("steps", 3)

    from avge_engine.geometry.procedural import interpolate_outlines

    outlines = interpolate_outlines(
        region_a.outline,
        region_b.outline,
        steps=steps,
        closed=region_a.constraints.closed,
    )

    if not outlines:
        return "Error: interpolation produced no outlines"

    fill = params.get("fill", "#CCCCCC")
    stroke = params.get("stroke", "#333333")
    stroke_width = params.get("stroke_width", 0.005)
    z_base = params.get("z_index", max(region_a.z_index, region_b.z_index) + 1)

    created: list[str] = []
    for i, outline in enumerate(outlines):
        rid = f"interp_{rid_a}_{rid_b}_{i}"
        r = scene.create_region(
            outline=outline,
            region_id=rid,
            document_id=doc_id,
            layer=region_a.layer,
            z_index=z_base + i,
            constraints=CurveConstraints(
                smoothness=region_a.constraints.smoothness,
                closed=region_a.constraints.closed,
            ),
            style=Style(fill=fill, stroke=stroke, stroke_width=stroke_width),
        )
        created.append(r.id)

    return (
        f"interpolate_outlines: {len(created)} step(s) between '{rid_a}' and '{rid_b}': "
        f"{', '.join(created)}"
    )


def _do_distribute_linear(params: dict) -> str:
    """Generate evenly-spaced points along a line segment."""
    start = params.get("start")
    end = params.get("end")
    count = params.get("count", 5)
    if not start or not end:
        return "Error: 'start' and 'end' params required (each a list of [x, y])"

    from avge_engine.geometry.procedural import distribute_linear
    points = distribute_linear(
        start=tuple(start),
        end=tuple(end),
        count=count,
    )
    pts_fmt = ", ".join(f"({p[0]:.4f},{p[1]:.4f})" for p in points)
    return f"distribute_linear: {len(points)} points: {pts_fmt}"


def _do_apex_from_edge(scene, doc_id: str, params: dict) -> str:
    """Project a triangle (roof) from one edge of a region."""
    region_id = params.get("region_id")
    if not region_id or not scene.has_region(region_id, doc_id):
        return "Error: region_id is required and must exist"

    region = scene.get_region(region_id, doc_id)
    edge = params.get("edge", "top")
    apex_offset = params.get("apex_offset")

    from avge_engine.geometry.procedural import apex_from_edge
    inset = params.get("inset", 0.0)
    triangle = apex_from_edge(
        region.outline,
        edge=edge,
        apex_offset=apex_offset,
        inset=inset,
    )

    if not triangle or len(triangle) < 3:
        return f"Error: apex_from_edge produced degenerate triangle ({len(triangle)} pts)"

    new_rid = f"{region_id}_{edge}_apex"
    r = scene.create_region(
        outline=triangle,
        region_id=new_rid,
        document_id=doc_id,
        layer=region.layer,
        z_index=params.get("z_index", region.z_index + 1),
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(
            fill=params.get("fill", region.style.fill),
            stroke=params.get("stroke", region.style.stroke),
            stroke_width=params.get("stroke_width", region.style.stroke_width),
        ),
    )
    return (
        f"apex_from_edge: projected triangle from '{region_id}' {edge} edge "
        f"→ '{r.id}' ({len(triangle)} pts)"
    )

def _do_segmented_chain(scene, doc_id: str, params: dict) -> str:
    """Create a connected chain of tapered segments (bent limb, curled finger)."""
    region_id = params.get("region_id")
    if not region_id or not scene.has_region(region_id, doc_id):
        return "Error: region_id is required and must exist"

    region = scene.get_region(region_id, doc_id)
    segments = params.get("segments")
    if not segments or not isinstance(segments, list) or len(segments) < 1:
        return "Error: 'segments' param is required (list of segment dicts)"

    anchor = params.get("anchor", "right_edge")
    joint_radius = params.get("joint_radius", 0.0)
    count = max(1, min(20, params.get("count", 1)))
    angle_spread = params.get("angle_spread", 30.0)
    length_scales = params.get("length_scales")

    from avge_engine.geometry.procedural import segmented_chain, _filter_edge, _outward_dir

    # Get anchor position and direction from the base region
    edge_pts = _filter_edge(region.outline, anchor)
    if not edge_pts or len(edge_pts) < 2:
        return f"Error: Could not find '{anchor}' edge on region"
    # Anchor at midpoint of edge
    ax = (edge_pts[0][0] + edge_pts[-1][0]) / 2
    ay = (edge_pts[0][1] + edge_pts[-1][1]) / 2
    out_dir = _outward_dir(anchor)

    fill = params.get("fill", region.style.fill)
    stroke = params.get("stroke", region.style.stroke)
    stroke_width = params.get("stroke_width", region.style.stroke_width)
    smoothness = params.get("smoothness", 0.4)
    z_base = params.get("z_index", region.z_index + 1)

    created: list[str] = []
    for i in range(count):
        # Each chain gets an angle offset for fanning
        t_fan = i / (count - 1) if count > 1 else 0.5
        ao = -angle_spread / 2 + t_fan * angle_spread if count > 1 else 0.0

        # Apply per-chain length scaling
        chain_segments = segments
        if length_scales and i < len(length_scales):
            sc = length_scales[i]
            chain_segments = [{**s, "length": s.get("length", 0.1) * sc,
                               "width_start": s.get("width_start", 0.04) * sc,
                               "width_end": s.get("width_end", 0.04) * sc}
                              for s in segments]

        result = segmented_chain(
            anchor_pos=(ax, ay),
            anchor_direction=out_dir,
            segments=chain_segments,
            joint_radius=joint_radius,
            angle_offset=ao,
        )

        # Create segment regions
        for si, outline in enumerate(result.get("segments", [])):
            rid = f"{region_id}_seg_{i}_{si}"
            try:
                r = scene.create_region(
                    outline=outline,
                    region_id=rid,
                    document_id=doc_id,
                    layer=region.layer,
                    z_index=z_base + si,
                    constraints=CurveConstraints(smoothness=smoothness, closed=True),
                    style=Style(fill=fill, stroke=stroke, stroke_width=stroke_width),
                )
                created.append(r.id)
            except (ValueError, RuntimeError) as e:
                return f"Error creating segment {si}: {e}"

        # Create joint cover regions
        for ji, outline in enumerate(result.get("joints", [])):
            rid = f"{region_id}_joint_{i}_{ji}"
            try:
                r = scene.create_region(
                    outline=outline,
                    region_id=rid,
                    document_id=doc_id,
                    layer=region.layer,
                    z_index=z_base + len(segments) + ji,
                    constraints=CurveConstraints(smoothness=0.3, closed=True),
                    style=Style(fill=fill, stroke=None),
                )
                created.append(r.id)
            except (ValueError, RuntimeError) as e:
                return f"Error creating joint {ji}: {e}"

    return (
        f"segmented_chain: {len(created)} region(s) created from "
        f"{len(segments)} segments × {count} chain(s): {', '.join(created)}"
    )

def _do_speech_bubble(scene, doc_id: str, params: dict) -> str:
    """Create a speech bubble region (rounded rect + tail)."""
    from avge_engine.geometry.procedural import speech_bubble

    cx = params.get("cx", 0.5)
    cy = params.get("cy", 0.5)
    width = params.get("width", 0.4)
    height = params.get("height", 0.2)
    rx = params.get("rx")
    tail_dir = params.get("tail_direction", "bottom")
    tail_len = params.get("tail_length", 0.04)
    tail_w = params.get("tail_width", 0.03)

    outline = speech_bubble(
        cx, cy, width, height,
        rx=rx, tail_direction=tail_dir,
        tail_length=tail_len, tail_width=tail_w,
    )

    if not outline or len(outline) < 3:
        return "Error: speech_bubble produced degenerate outline"

    rid = params.get("region_id") or f"bubble_{cx:.3f}_{cy:.3f}".replace(".", "_")
    r = scene.create_region(
        outline=outline,
        region_id=rid,
        document_id=doc_id,
        layer=params.get("layer", "default"),
        z_index=params.get("z_index", 0),
        constraints=CurveConstraints(smoothness=params.get("smoothness", 0.0), closed=True),
        style=Style(
            fill=params.get("fill", "#FFFFFF"),
            stroke=params.get("stroke", "#333333"),
            stroke_width=params.get("stroke_width", 0.005),
        ),
    )
    return (
        f"speech_bubble: created '{r.id}', "
        f"({cx:.4f},{cy:.4f}) {width:.4f}x{height:.4f}, "
        f"tail={tail_dir} ({tail_len:.3f}), "
        f"{len(outline)} pts"
    )


def _do_create_burst(scene, doc_id: str, params: dict) -> str:
    """Create radiating lines for impact/speed effects."""
    from avge_engine.geometry.procedural import create_burst

    outlines = create_burst(
        cx=params.get("cx", 0.5), cy=params.get("cy", 0.5),
        count=params.get("count", 12),
        radius_inner=params.get("radius_inner", 0.05),
        radius_outer=params.get("radius_outer", 0.15),
        start_angle=params.get("start_angle", 0.0),
        angle_span=params.get("angle_span", 360.0),
        taper=params.get("taper", 0.3),
    )
    if not outlines:
        return "Error: create_burst produced no lines"

    fill = params.get("fill", "#333333")
    stroke = params.get("stroke", "none")
    sw = params.get("stroke_width", 0.0)
    z_base = params.get("z_index", 0)

    created: list[str] = []
    for i, outline in enumerate(outlines):
        rid = params.get("region_id") or f"burst_{i}"
        rid_uniq = f"{rid}_{i}" if params.get("region_id") else rid
        try:
            r = scene.create_region(
                outline=outline,
                region_id=rid_uniq,
                document_id=doc_id,
                layer=params.get("layer", "default"),
                z_index=z_base + i,
                constraints=CurveConstraints(smoothness=0.0, closed=True),
                style=Style(fill=fill, stroke=stroke, stroke_width=sw),
            )
            created.append(r.id)
        except (ValueError, RuntimeError) as e:
            return f"Error at line {i}: {e}"

    return f"create_burst: {len(created)} line(s) from ({params.get('cx',0.5):.2f},{params.get('cy',0.5):.2f})"


def _do_armature(scene, doc_id: str, params: dict) -> str:
    from avge_engine.geometry.procedural import armature
    nodes = params.get("nodes", [])
    edges = params.get("edges", [])
    if not nodes or not edges:
        return "Error: nodes and edges required"
    result = armature(
        nodes=nodes, edges=edges,
        smoothness=params.get("smoothness", 0.3),
        curved=params.get("curved", False),
        junction_separation=params.get("junction_separation", 0.0),
        junction_radius=params.get("junction_radius", 0.0),
        overlap=params.get("overlap", 0.0),
    )
    segments = result.get("segments", [])
    if not segments:
        return "Error: armature produced no segments"
    fill = params.get("fill", "#CCCCCC")
    stroke = params.get("stroke", "#333333")
    sw = params.get("stroke_width", 0.005)
    opacity_val = params.get("opacity", 1.0)
    z_base = params.get("z_index", 0)
    created = []
    import time
    _arm_seq = int(time.time() * 1000) % 1000000
    for i, outline in enumerate(segments):
        rid = f"arm_{_arm_seq}_{i}"
        try:
            r = scene.create_region(
                outline=outline, region_id=rid, document_id=doc_id,
                constraints=CurveConstraints(smoothness=params.get("smoothness", 0.3), closed=True),
                style=Style(fill=fill, stroke=stroke, stroke_width=sw, opacity=opacity_val),
                z_index=z_base + i,
            )
            created.append(r.id)
        except (ValueError, RuntimeError) as e:
            return f"Error at segment {i}: {e}"
    if params.get("output") == "union" and len(created) > 1:
        try:
            from shapely.geometry import Polygon, MultiPolygon
            from shapely import unary_union
            seg_polys = []
            for cid in created:
                r = scene.get_region(cid, doc_id)
                if r and len(r.outline) >= 3:
                    seg_polys.append(Polygon(r.outline))
            if seg_polys:
                # buffer(0) on each polygon fixes self-intersections
                clean_polys = [p.buffer(0) for p in seg_polys if not p.is_empty]
                if not clean_polys:
                    return f"armature: all segments produced invalid geometry"
                merged = unary_union(clean_polys)
                merged = merged.buffer(0)  # fix any union-introduced invalidities
                if merged.is_empty:
                    return f"armature: union produced empty result"
                if isinstance(merged, MultiPolygon):
                    parts = list(merged.geoms)
                    merged = max(parts, key=lambda p: p.area)
                outline = [(round(x, 6), round(y, 6)) for x, y in merged.exterior.coords[:-1]]
                for cid in created:
                    scene.delete_region(document_id=doc_id, region_id=cid)
                r = scene.create_region(
                    outline=outline, document_id=doc_id,
                    constraints=CurveConstraints(smoothness=params.get("smoothness", 0.3), closed=True),
                    style=Style(fill=fill, stroke=stroke, stroke_width=sw),
                    z_index=z_base,
                )
                return f"armature (merged): id={r.id}, {len(outline)} pts"
            return f"armature: {len(created)} segment(s), union skipped"
        except Exception as e:
            return f"armature: {len(created)} segment(s), union failed: {e}"
    return f"armature: {len(created)} segment(s), ids: {', '.join(created)}"


def _do_foreshorten(scene, doc_id: str, params: dict) -> str:
    from avge_engine.geometry.procedural import foreshorten
    region_id = params.get("region_id")
    if not region_id or not scene.has_region(region_id, doc_id):
        return "Error: region_id required"
    region = scene.get_region(region_id, doc_id)
    new_outline = foreshorten(
        region.outline,
        depth_factor=params.get("depth_factor", 0.5),
        pivot_end=params.get("pivot_end", "start"),
    )
    scene.edit_region(region_id=region_id, document_id=doc_id, outline=new_outline)
    return f"foreshorten: '{region_id}' compressed (depth={params.get('depth_factor',0.5)})"


def _do_surface_detail(scene, doc_id: str, params: dict) -> str:
    from avge_engine.geometry.procedural import surface_detail
    region_id = params.get("region_id")
    if not region_id or not scene.has_region(region_id, doc_id):
        return "Error: region_id required"
    region = scene.get_region(region_id, doc_id)
    results = surface_detail(
        region.outline,
        motif=params.get("motif", "scale"),
        density=params.get("density", 5),
        direction=params.get("direction", 0),
        size_range=tuple(params.get("size_range", [0.005, 0.015])),
    )
    fill = params.get("fill", region.style.fill)
    stroke = params.get("stroke", region.style.stroke)
    sw = params.get("stroke_width", region.style.stroke_width)
    z_base = params.get("z_index", region.z_index + 1)
    created = []
    for i, outline in enumerate(results):
        rid = f"{region_id}_detail_{i}"
        try:
            r = scene.create_region(
                outline=outline, region_id=rid, document_id=doc_id,
                constraints=CurveConstraints(smoothness=0.0, closed=True),
                style=Style(fill=fill, stroke=stroke, stroke_width=sw),
                z_index=z_base + i,
            )
            created.append(r.id)
        except (ValueError, RuntimeError) as e:
            return f"Error at detail {i}: {e}"
    return f"surface_detail: {len(created)} motif(s) on '{region_id}'"


def _resolve_relative_box(scene, doc_id, relative_to, params):
    """Transform isometric_box x,y from 0-1 within a parent region.

    Maps (0,0) = visual top-left of the region's bounding box,
    (1,1) = visual bottom-right. y increases downward (SVG coords).
    Only x and y are relative; width, depth, height stay as-is.
    """
    region = scene.get_region(relative_to, doc_id)
    if region is None:
        return
    from avge_engine.geometry import compute_bounds
    b = compute_bounds(region.outline)
    bx, by, bw, bh = b["x"], b["y"], b["w"], b["h"]
    if bw < 1e-10:
        bw = 1e-10
    if bh < 1e-10:
        bh = 1e-10
    if "x" in params:
        params["x"] = bx + float(params["x"]) * bw
    if "y" in params:
        params["y"] = by + float(params["y"]) * bh


def _do_isometric_box(scene, doc_id: str, params: dict) -> str:
    """Generate 3 faces of an isometric box (gold bar, crate, etc.)."""
    from avge_engine.geometry.procedural import isometric_box

    faces = isometric_box(
        x=params.get("x", 0.35), y=params.get("y", 0.35),
        width=params.get("width", 0.2),
        depth=params.get("depth", 0.12),
        height=params.get("height", 0.08),
        angle=params.get("angle", 30.0),
        top_slant=params.get("top_slant", 0.0),
    )
    if not faces:
        return "Error: isometric_box produced no faces"

    # Unique region ID prefix (required for >1 box per document)
    prefix = params.get("new_prefix") or params.get("region_id", "box")
    if scene.has_region(f"{prefix}_top", doc_id):
        # Auto-deduplicate by appending counter
        counter = 0
        while scene.has_region(f"{prefix}_{counter}_top", doc_id):
            counter += 1
        prefix = f"{prefix}_{counter}"

    # Per-face styles with sensible 3D defaults
    # Accept both fill_top and top_fill naming conventions
    face_conf = {
        "top": {
            "fill": params.get("top_fill") or params.get("fill_top") or params.get("fill", "#FFD700"),
            "stroke": params.get("top_stroke") or params.get("stroke_top") or params.get("stroke", "#333333"),
            "sw": params.get("top_stroke_width") or params.get("stroke_width_top") or params.get("stroke_width", 0.003),
        },
        "left": {
            "fill": params.get("left_fill") or params.get("fill_left") or params.get("fill", "#DAA520"),
            "stroke": params.get("left_stroke") or params.get("stroke_left") or params.get("stroke", "#333333"),
            "sw": params.get("left_stroke_width") or params.get("stroke_width_left") or params.get("stroke_width", 0.003),
        },
        "right": {
            "fill": params.get("right_fill") or params.get("fill_right") or params.get("fill", "#B8860B"),
            "stroke": params.get("right_stroke") or params.get("stroke_right") or params.get("stroke", "#333333"),
            "sw": params.get("right_stroke_width") or params.get("stroke_width_right") or params.get("stroke_width", 0.003),
        },
    }
    layer = params.get("layer", "default")
    z_base = params.get("z_index", 0)
    opacity = params.get("opacity", 1.0)
    blend_mode = params.get("blend_mode")

    # Painter's algorithm: right face behind left face behind top face
    z_order = {"right": 0, "left": 1, "top": 2}
    # Skip hidden faces (e.g. table leg top face hidden inside table)
    skip_faces = params.get("skip_faces") or params.get("hide", [])

    created = []
    for face in faces:
        fname = face["face"]
        if fname in skip_faces:
            continue
        outline = face["outline"]
        cfg = face_conf[fname]
        rid = f"{prefix}_{fname}"
        try:
            r = scene.create_region(
                outline=outline, region_id=rid,
                document_id=doc_id, layer=layer,
                z_index=z_base + z_order.get(fname, 0),
                constraints=CurveConstraints(smoothness=0.0, closed=True),
                style=Style(fill=cfg["fill"], stroke=cfg["stroke"],
                            stroke_width=cfg["sw"], opacity=opacity,
                            blend_mode=blend_mode),
            )
            created.append(r.id)
        except (ValueError, RuntimeError) as e:
            return f"Error at face {fname}: {e}"

    # ── Optional ground shadow ──
    if params.get("shadow") or params.get("shadow_opacity"):
        import math as _m
        w = params.get("width", 0.2)
        d = params.get("depth", 0.12)
        h = params.get("height", 0.08)
        ang = _m.radians(params.get("angle", 30.0))
        # Bottom center = top vertex + half width offset + half depth offset + height
        scx = round(params.get("x", 0.35) + (-_m.cos(ang) * w + _m.cos(ang) * d) / 2, 6)
        scy = round(params.get("y", 0.35) + (_m.sin(ang) * w + _m.sin(ang) * d) / 2 + h, 6)
        sr = round(max(w, d) * _m.cos(ang) * 0.5, 6)
        sr2 = round(max(w, d) * _m.cos(ang) * 0.15, 6)
        if sr > 0.001 and sr2 > 0.001:
            sop = params.get("shadow_opacity", 0.12)
            shadow_rid = f"{prefix}_shadow"
            try:
                scene.create_ellipse(
                    scx, scy, sr, ry=sr2,
                    document_id=doc_id, region_id=shadow_rid,
                    layer=layer, z_index=z_base - 1,
                    fill="#000000", stroke="none",
                    opacity=sop, blend_mode="multiply",
                )
                created.insert(0, shadow_rid)
            except (ValueError, RuntimeError):
                pass  # shadow is optional

    return (f"isometric_box: {len(created)} face(s) "
            f"({', '.join(f['face'] for f in faces)})")
