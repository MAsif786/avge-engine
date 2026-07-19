"""
Procedural geometry — generic pattern functions for generating shapes.

Each function is a pure geometric operation with no domain knowledge.
They return raw outlines/points that callers can style and compose.
"""

from __future__ import annotations

import math
from typing import Any

from avge_engine.geometry.types import Point2D


# ── Ellipse / arc bands ───────────────────────────────────────────────

def ellipse_band(
    cx: float,
    cy: float,
    rx: float,
    ry: float | None = None,
    *,
    thickness: float | None = None,
    inner_rx: float | None = None,
    inner_ry: float | None = None,
    start_angle: float = 0.0,
    end_angle: float = 360.0,
    rotation: float = 0.0,
    samples: int = 64,
    perspective: float = 0.0,
    skew_x: float = 0.0,
) -> list[Point2D]:
    """Generate a filled elliptical or partial-arc band outline.

    The returned outline walks the outer arc, then the inner arc in reverse,
    creating a single closed polygon suitable for ``SceneGraph.create_region``.

    Args:
        cx, cy: Center of the band in normalized canvas coordinates.
        rx, ry: Outer ellipse radii. If ``ry`` is omitted it equals ``rx``.
        thickness: Uniform inward thickness used when inner radii are omitted.
        inner_rx, inner_ry: Explicit inner ellipse radii.
        start_angle, end_angle: Arc angles in degrees. 0 is right, 90 is down.
        rotation: Rotate the whole band around ``cx/cy`` in degrees.
        samples: Number of samples along each arc edge.
        perspective: Near/far width adjustment. Positive values widen the
            lower/near half and narrow the upper/far half.
        skew_x: Horizontal shear based on vertical position, useful for
            matching oblique architectural photos.

    Returns:
        Closed outline points: outer arc + reversed inner arc.
    """
    outer_ry = rx if ry is None else ry
    if rx <= 0 or outer_ry <= 0:
        raise ValueError("rx and ry must be positive")

    if inner_rx is None or inner_ry is None:
        t = 0.02 if thickness is None else thickness
        if t <= 0:
            raise ValueError("thickness must be positive")
        inner_rx = rx - t if inner_rx is None else inner_rx
        inner_ry = outer_ry - t if inner_ry is None else inner_ry

    if inner_rx <= 0 or inner_ry <= 0:
        raise ValueError("inner radii must be positive")
    if inner_rx >= rx or inner_ry >= outer_ry:
        raise ValueError("inner radii must be smaller than outer radii")

    sample_count = max(4, min(180, int(samples)))
    sweep = end_angle - start_angle
    if abs(sweep) < 1e-6:
        raise ValueError("start_angle and end_angle must differ")
    if abs(sweep) > 360:
        sweep = 360 if sweep > 0 else -360
        end_angle = start_angle + sweep

    rot = math.radians(rotation)
    cos_r, sin_r = math.cos(rot), math.sin(rot)
    perspective = max(-0.75, min(0.75, perspective))

    def point(angle_deg: float, rad_x: float, rad_y: float) -> Point2D:
        a = math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)
        # Positive perspective makes the lower half (sa > 0) wider and the
        # upper half narrower, mimicking a near/far elliptical ring in photos.
        px = ca * rad_x * (1.0 + perspective * sa)
        py = sa * rad_y
        px += skew_x * py
        x = cx + px * cos_r - py * sin_r
        y = cy + px * sin_r + py * cos_r
        return (round(x, 6), round(y, 6))

    angles = [
        start_angle + sweep * (i / sample_count)
        for i in range(sample_count + 1)
    ]
    outer = [point(a, rx, outer_ry) for a in angles]
    inner = [point(a, inner_rx, inner_ry) for a in reversed(angles)]
    return outer + inner


# ── Edge helpers (shared by radial_spread and distribute_points) ───────

def _filter_edge(
    outline: list[Point2D],
    anchor: str,
) -> list[Point2D]:
    """Filter outline points near a given edge (top/bottom/left/right)."""
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    margin = 0.1
    if anchor == "top_edge":
        threshold = min(ys) + (max(ys) - min(ys)) * margin
        return sorted([p for p in outline if p[1] <= threshold], key=lambda p: p[0])
    elif anchor == "bottom_edge":
        threshold = max(ys) - (max(ys) - min(ys)) * margin
        return sorted([p for p in outline if p[1] >= threshold], key=lambda p: p[0])
    elif anchor == "left_edge":
        threshold = min(xs) + (max(xs) - min(xs)) * margin
        return sorted([p for p in outline if p[0] <= threshold], key=lambda p: p[1])
    elif anchor == "right_edge":
        threshold = max(xs) - (max(xs) - min(xs)) * margin
        return sorted([p for p in outline if p[0] >= threshold], key=lambda p: p[1])
    # Default: use all points sorted by x
    return sorted(outline, key=lambda p: p[0])


def _interpolate_edge(
    edge_pts: list[Point2D],
    t: float,
) -> Point2D:
    """Interpolate a position at fraction t along an edge point list."""
    total = len(edge_pts) - 1
    pos = t * total
    idx_a = min(int(pos), total - 1)
    idx_b = idx_a + 1
    frac = pos - idx_a
    return (
        edge_pts[idx_a][0] + (edge_pts[idx_b][0] - edge_pts[idx_a][0]) * frac,
        edge_pts[idx_a][1] + (edge_pts[idx_b][1] - edge_pts[idx_a][1]) * frac,
    )


def _outward_dir(anchor: str) -> tuple[float, float]:
    """Return the outward normal for an edge anchor."""
    dirs = {
        "top_edge": (0, -1),
        "bottom_edge": (0, 1),
        "left_edge": (-1, 0),
        "right_edge": (1, 0),
    }
    return dirs.get(anchor, (0, -1))


# ── 1. radial_spread ──────────────────────────────────────────────────

def radial_spread(
    outline: list[Point2D],
    *,
    count: int = 5,
    anchor: str = "top_edge",
    length_range: tuple[float, float] = (0.1, 0.15),
    width: float = 0.025,
    angle_spread: float = 30.0,
    taper: float = 0.5,
    length_variance: bool = False,
) -> list[list[Point2D]]:
    """Fan N protrusions from one edge of a base outline.

    Each protrusion is a pill-like organic spike — 6 control points —
    placed at regular intervals along the chosen edge and angled outward.

    Args:
        outline: Source outline points (will use bounding box edge).
        count: Number of protrusions (default 5).
        anchor: ``"top_edge"``, ``"bottom_edge"``, ``"left_edge"``,
            or ``"right_edge"`` (which side of the bounding box to stem from).
        length_range: Min/max protrusion length (default 0.1–0.15).
        width: Base width of each protrusion (default 0.025).
        angle_spread: Total spread angle in degrees (default 30).
        taper: Pointedness of the tip, 0 = round, 1 = sharp (default 0.5).
        length_variance: Randomize lengths within range (default False).

    Returns:
        List of outlines, one per protrusion.
    """
    edge_pts = _filter_edge(outline, anchor)
    if len(edge_pts) < 2:
        return []

    out_dir = _outward_dir(anchor)
    if count < 1:
        return []

    protrusions = []
    for i in range(count):
        t = (i + 0.5) / count  # center of each segment
        bx, by = _interpolate_edge(edge_pts, t)

        if count > 1:
            t_angle = i / (count - 1)
            angle_deg = -angle_spread / 2 + t_angle * angle_spread
        else:
            angle_deg = 0.0

        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        odx, ody = out_dir
        dx = odx * cos_a - ody * sin_a
        dy = odx * sin_a + ody * cos_a

        if length_variance:
            import random
            random.seed(i * 137)
            l_factor = length_range[0] + (length_range[1] - length_range[0]) * random.random()
        else:
            l_factor = (length_range[0] + length_range[1]) * 0.5

        tip = (bx + dx * l_factor, by + dy * l_factor)
        mid = (bx + dx * l_factor * 0.5, by + dy * l_factor * 0.5)

        hw = width / 2
        perp = (-dy, dx)
        bl = (bx - perp[0] * hw, by - perp[1] * hw)
        br = (bx + perp[0] * hw, by + perp[1] * hw)

        taper_offs = width * (1.0 - taper) * 0.3
        ml = (mid[0] - perp[0] * taper_offs, mid[1] - perp[1] * taper_offs)
        mr = (mid[0] + perp[0] * taper_offs, mid[1] + perp[1] * taper_offs)

        protrusions.append([bl, ml, tip, tip, mr, br])

    return protrusions


# ── 2. offset_outline ─────────────────────────────────────────────────

def offset_outline(
    outline: list[Point2D],
    distance: float,
    closed: bool = True,
) -> list[Point2D]:
    """Expand (positive distance) or contract (negative) an outline uniformly.

    Uses shapely's ``buffer()`` internally.

    Args:
        outline: Source outline points.
        distance: Signed offset distance. Positive = expand, negative = contract.
        closed: Whether the outline is a closed ring (default True).

    Returns:
        New offset outline (exterior coords, first point not repeated).
    """
    from shapely.geometry import Polygon, LineString
    if closed and len(outline) >= 3:
        geom = Polygon(outline).buffer(distance, join_style=2)
    elif len(outline) >= 2:
        geom = LineString(outline).buffer(distance, cap_style=2, join_style=2)
    else:
        return list(outline)

    if geom.is_empty:
        return list(outline)
    if geom.geom_type == "Polygon":
        coords = list(geom.exterior.coords)
        return [(round(x, 6), round(y, 6)) for x, y in coords[:-1]]
    # MultiPolygon — take the largest
    parts = sorted(geom.geoms, key=lambda p: p.area, reverse=True)
    coords = list(parts[0].exterior.coords)
    return [(round(x, 6), round(y, 6)) for x, y in coords[:-1]]


# ── 3. guide_lines ────────────────────────────────────────────────────

def guide_lines(
    bbox_x: float,
    bbox_y: float,
    bbox_w: float,
    bbox_h: float,
    ratios: list[float],
    horizontal: bool = True,
) -> list[dict[str, Any]]:
    """Generate proportional division markers within a bounding box.

    Returns a list of line endpoints — each entry has ``start`` and ``end``
    coordinates plus the original ``ratio`` and an optional ``label``.

    Args:
        bbox_x: Left of bounding box.
        bbox_y: Top of bounding box.
        bbox_w: Width of bounding box.
        bbox_h: Height of bounding box.
        ratios: Fractions of dimension (0.0–1.0). Example ``[0.3, 0.5]``.
        horizontal: If True, horizontal lines (y = offset). Else vertical.

    Returns:
        List of dicts: ``{{ratio, label?, start: [x,y], end: [x,y]}}``.
    """
    lines = []
    for i, r in enumerate(ratios):
        if horizontal:
            y = bbox_y + r * bbox_h
            lines.append({
                "ratio": r,
                "label": f"h{i}",
                "start": [bbox_x, round(y, 6)],
                "end": [bbox_x + bbox_w, round(y, 6)],
            })
        else:
            x = bbox_x + r * bbox_w
            lines.append({
                "ratio": r,
                "label": f"v{i}",
                "start": [round(x, 6), bbox_y],
                "end": [round(x, 6), bbox_y + bbox_h],
            })
    return lines


# ── 4. distribute_points ──────────────────────────────────────────────

def distribute_points(
    outline: list[Point2D],
    count: int,
    edge: str = "top_edge",
) -> list[Point2D]:
    """Place N evenly-spaced points along one edge of an outline.

    Args:
        outline: Source outline.
        count: Number of points to place.
        edge: ``"top_edge"``, ``"bottom_edge"``, ``"left_edge"``,
            or ``"right_edge"``.

    Returns:
        List of ``(x, y)`` positions.
    """
    edge_pts = _filter_edge(outline, edge)
    if len(edge_pts) < 2 or count < 1:
        return []
    return [_interpolate_edge(edge_pts, (i + 0.5) / count) for i in range(count)]


# ── 5. bridge_shapes ──────────────────────────────────────────────────

def bridge_shapes(
    outline_a: list[Point2D],
    outline_b: list[Point2D],
) -> list[Point2D]:
    """Create a connecting shape between two overlapping outlines.

    Computes the convex hull of both outlines combined.

    Args:
        outline_a: First outline.
        outline_b: Second outline.

    Returns:
        Hull outline as a connected polygon.
    """
    from shapely.geometry import MultiPoint
    all_pts = outline_a + outline_b
    if len(all_pts) < 3:
        return list(outline_a) if len(outline_a) >= len(outline_b) else list(outline_b)
    hull = MultiPoint(all_pts).convex_hull
    coords = list(hull.exterior.coords)
    return [(round(x, 6), round(y, 6)) for x, y in coords[:-1]]


# ── 6. interpolate_outlines ──────────────────────────────────────────

def interpolate_outlines(
    outline_a: list[Point2D],
    outline_b: list[Point2D],
    steps: int = 4,
) -> list[list[Point2D]]:
    """Create N intermediate outlines morphing between source A and B.

    Both outlines are resampled to the same point count (the max of the two)
    before interpolation.

    Args:
        outline_a: Source outline A.
        outline_b: Source outline B.
        steps: Number of intermediate steps (default 4).

    Returns:
        List of ``steps`` interpolated outlines.
    """
    if len(outline_a) < 2 or len(outline_b) < 2:
        return []

    target = max(len(outline_a), len(outline_b))
    resampled_a = _resample(outline_a, target)
    resampled_b = _resample(outline_b, target)

    result = []
    for step in range(1, steps + 1):
        t = step / (steps + 1)
        interp = [
            (
                round(ax + (bx - ax) * t, 6),
                round(ay + (by - ay) * t, 6),
            )
            for (ax, ay), (bx, by) in zip(resampled_a, resampled_b)
        ]
        result.append(interp)
    return result


def _resample(
    outline: list[Point2D],
    n: int,
) -> list[Point2D]:
    """Resample an outline to exactly N evenly-spaced points."""
    if n <= 0:
        return []
    total_len = sum(
        math.dist(outline[i], outline[i + 1])
        for i in range(len(outline) - 1)
    )
    if total_len == 0:
        return [outline[0]] * n
    pts: list[Point2D] = [outline[0]]
    target = total_len / (n - 1)
    acc = 0.0
    idx = 0
    for i in range(1, n - 1):
        needed = i * target
        while acc < needed and idx < len(outline) - 1:
            seg_len = math.dist(outline[idx], outline[idx + 1])
            if acc + seg_len >= needed:
                frac = (needed - acc) / max(seg_len, 1e-10)
                pts.append((
                    round(outline[idx][0] + (outline[idx + 1][0] - outline[idx][0]) * frac, 6),
                    round(outline[idx][1] + (outline[idx + 1][1] - outline[idx][1]) * frac, 6),
                ))
                acc = needed
            else:
                acc += seg_len
                idx += 1
        if len(pts) < i + 1:
            pts.append(pts[-1])
    pts.append(outline[-1])
    return pts


# ── 7. distribute_linear ──────────────────────────────────────────────

def distribute_linear(
    start: tuple[float, float],
    end: tuple[float, float],
    count: int,
) -> list[tuple[float, float]]:
    """Generate evenly-spaced points along a line segment.

    Args:
        start: ``(x, y)`` start point.
        end: ``(x, y)`` end point.
        count: Number of points (must be >= 2).

    Returns:
        List of ``(x, y)`` from start to end inclusive.
    """
    if count < 2:
        return [start]
    pts = []
    for i in range(count):
        t = i / (count - 1)
        pts.append((
            round(start[0] + (end[0] - start[0]) * t, 6),
            round(start[1] + (end[1] - start[1]) * t, 6),
        ))
    return pts


# ── 8. apex_from_edge ─────────────────────────────────────────────────

def apex_from_edge(
    outline: list[Point2D],
    edge: str = "top_edge",
    apex_offset: float = 0.15,
    inset: float = 0.0,
) -> list[Point2D]:
    """Project a triangle (apex) from one edge of an outline.

    Creates a new triangle outline whose base is the chosen edge of the
    source outline, projected outward by ``apex_offset``.

    Args:
        outline: Source outline.
        edge: ``"top_edge"``, ``"bottom_edge"``, ``"left_edge"``,
            or ``"right_edge"``.
        apex_offset: Distance the apex projects outward.
        inset: How far the base corners inset from the source edge corners.

    Returns:
        Triangle outline ``[base_left, apex, base_right]``.
    """
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]

    if edge in ("top", "top_edge"):
        base = [(min(xs) - inset, min(ys)), (max(xs) + inset, min(ys))]
        cx, cy = (min(xs) + max(xs)) / 2, min(ys)
        apex = (cx, cy - apex_offset)
    elif edge in ("bottom", "bottom_edge"):
        base = [(min(xs) - inset, max(ys)), (max(xs) + inset, max(ys))]
        cx, cy = (min(xs) + max(xs)) / 2, max(ys)
        apex = (cx, cy + apex_offset)
    elif edge in ("left", "left_edge"):
        base = [(min(xs), min(ys) - inset), (min(xs), max(ys) + inset)]
        cx, cy = min(xs), (min(ys) + max(ys)) / 2
        apex = (cx - apex_offset, cy)
    else:
        base = [(max(xs), min(ys) - inset), (max(xs), max(ys) + inset)]
        cx, cy = max(xs), (min(ys) + max(ys)) / 2
        apex = (cx + apex_offset, cy)

    return [
        (round(apex[0], 6), round(apex[1], 6)),
        (round(base[0][0], 6), round(base[0][1], 6)),
        (round(base[1][0], 6), round(base[1][1], 6)),
    ]


# ── 9. segmented_chain ────────────────────────────────────────────────

def segmented_chain(
    anchor_pos: tuple[float, float],
    anchor_direction: tuple[float, float],
    segments: list[dict[str, Any]],
    joint_radius: float = 0.015,
    angle_offset: float = 0.0,
    count: int = 1,
    angle_spread: float = 0.0,
) -> dict[str, Any]:
    """Create a bent limb or curled finger chain.

    Each segment is a pill-rect, connected end-to-end. Joints between
    segments are rounded by ``joint_radius``.

    Args:
        anchor_pos: ``(x, y)`` attachment point on the base shape.
        anchor_direction: ``(dx, dy)`` outward direction from the base.
        segments: List of segment dicts, each with:
            - ``length``: Segment length.
            - ``angle`` or ``angle_delta``: Angle from previous segment (degrees).
            - ``width_start``: Start width.
            - ``width_end``: End width.
        joint_radius: Radius for joint rounding (default 0.015).
        angle_offset: Global rotation offset for the entire chain (degrees).
        count: Number of chains to fan (default 1).
        angle_spread: Total fan spread (degrees, default 0).

    Returns:
        Dict with ``segments: [outline, ..]`` and ``joints: [(x,y), ..]``.
        Each outline is a single pill-rect (6 points).
    """
    if not segments:
        return {"segments": [], "joints": []}

    base_angle = math.atan2(anchor_direction[1], anchor_direction[0])
    outlines = []
    joints = []

    for chain_idx in range(count):
        fan_offset = 0.0
        if count > 1:
            t = chain_idx / (count - 1) if count > 1 else 0.5
            fan_offset = -angle_spread / 2 + t * angle_spread

        angle = base_angle + math.radians(angle_offset + fan_offset)
        chain_pts = [list(anchor_pos)]
        chain_outlines = []

        for seg in segments:
            length = seg.get("length", 0.1)
            angle += math.radians(seg.get("angle", seg.get("angle_delta", 0)))
            ws = seg.get("width_start", 0.03)
            we = seg.get("width_end", 0.02)

            tip = (chain_pts[-1][0] + math.cos(angle) * length,
                   chain_pts[-1][1] + math.sin(angle) * length)

            chain_outlines.append(_pill_rect(chain_pts[-1], tip, ws, we))
            chain_pts.append(tip)

        outlines.extend(chain_outlines)
        # Internal joints only (skip final tip)
        joints.extend(chain_pts[1:-1])

    return {"segments": outlines, "joints": joints}


def _pill_rect(
    start: tuple[float, float],
    end: tuple[float, float],
    ws: float,
    we: float,
) -> list[Point2D]:
    """Generate a 6-point pill-rect between two points with tapering width."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-8:
        return []
    ux, uy = dx / length, dy / length
    perp_x, perp_y = -uy, ux
    hws, hwe = ws / 2, we / 2
    mid = 0.35
    return [
        (round(start[0] - perp_x * hws, 6), round(start[1] - perp_y * hws)),
        (round(start[0] + ux * length * mid - perp_x * hws, 6),
         round(start[1] + uy * length * mid - perp_y * hws)),
        (round(end[0] - perp_x * hwe, 6), round(end[1] - perp_y * hwe)),
        (round(end[0] + perp_x * hwe, 6), round(end[1] + perp_y * hwe)),
        (round(start[0] + ux * length * mid + perp_x * hws, 6),
         round(start[1] + uy * length * mid + perp_y * hws)),
        (round(start[0] + perp_x * hws, 6), round(start[1] + perp_y * hws)),
    ]


# ── 10. speech_bubble ─────────────────────────────────────────────────

def speech_bubble(
    cx: float,
    cy: float,
    width: float,
    height: float,
    tail_direction: str = "bottom",
    tail_length: float = 0.06,
    tail_width: float = 0.03,
    rx: float = 0.03,
) -> list[Point2D]:
    """Generate a speech bubble outline (rounded rect + tail).

    Args:
        cx: Center x.
        cy: Center y.
        width: Bubble width.
        height: Bubble height.
        tail_direction: ``"top"``, ``"bottom"``, ``"left"``, ``"right"``.
        tail_length: How far the tail extends.
        tail_width: Tail base width.
        rx: Corner radius (default 0.03, match edge of canvas).

    Returns:
        Closed outline suitable for create_region.
    """
    left = cx - width / 2
    top = cy - height / 2
    right = cx + width / 2
    bottom = cy + height / 2
    r = min(rx, width / 2, height / 2)
    tw = tail_width / 2

    # Build rounded rect
    pts = []
    # Top edge
    pts.append((left + r, top))
    pts.append((right - r, top))
    # Top-right corner arc
    for t in range(5):
        a = math.pi / 2 * t / 4
        pts.append((right - r + r * math.cos(a), top + r * (1 - math.sin(a))))
    # Right edge
    pts.append((right, top + r))
    pts.append((right, bottom - r))
    # Bottom-right corner arc
    for t in range(5):
        a = math.pi / 2 * t / 4
        pts.append((right - r * math.sin(a), bottom - r + r * (1 - math.cos(a))))
    # Bottom edge
    pts.append((right - r, bottom))
    pts.append((left + r, bottom))
    # Bottom-left corner arc
    for t in range(5):
        a = math.pi / 2 * t / 4
        pts.append((left + r * (1 - math.cos(a)), bottom - r + r * math.sin(a)))
    # Left edge
    pts.append((left, bottom - r))
    pts.append((left, top + r))
    # Top-left corner arc
    for t in range(5):
        a = math.pi / 2 * t / 4
        pts.append((left + r - r * math.sin(a), top + r * (1 - math.cos(a))))

    # Tail
    if tail_direction == "bottom":
        mid_x = cx
        tail_tip = (cx, bottom + tail_length)
        pts.append((mid_x + tw, bottom))
        pts.append(tail_tip)
        pts.append((mid_x - tw, bottom))
    elif tail_direction == "top":
        mid_x = cx
        tail_tip = (cx, top - tail_length)
        pts.append((mid_x - tw, top))
        pts.append(tail_tip)
        pts.append((mid_x + tw, top))
    elif tail_direction == "right":
        mid_y = cy
        tail_tip = (right + tail_length, cy)
        pts.append((right, mid_y + tw))
        pts.append(tail_tip)
        pts.append((right, mid_y - tw))
    elif tail_direction == "left":
        mid_y = cy
        tail_tip = (left - tail_length, cy)
        pts.append((left, mid_y - tw))
        pts.append(tail_tip)
        pts.append((left, mid_y + tw))

    return [(round(p[0], 6), round(p[1], 6)) for p in pts]


# ── 11. create_burst ──────────────────────────────────────────────────

def create_burst(
    cx: float,
    cy: float,
    count: int = 12,
    radius_inner: float = 0.1,
    radius_outer: float = 0.2,
    start_angle: float = 0.0,
    angle_span: float = 360.0,
    taper: float = 1.0,
) -> list[list[Point2D]]:
    """Generate radiating lines from center (impact/speed lines).

    Returns a list of thin triangular or tapered outlines, one per ray.

    Args:
        cx, cy: Center point.
        count: Number of rays.
        radius_inner: Inner radius (gap from center).
        radius_outer: Outer radius (ray length).
        start_angle: Starting angle in degrees.
        angle_span: Total angular coverage in degrees.
        taper: Pointedness (0 = blunt, 1 = sharp tip).

    Returns:
        List of outlines, each a triangle ``[base_left, tip, base_right]``.
    """
    if count < 1:
        return []

    rays = []
    for i in range(count):
        t = i / count
        angle = math.radians(start_angle + t * angle_span)
        dx, dy = math.cos(angle), math.sin(angle)

        inner = (cx + dx * radius_inner, cy + dy * radius_inner)
        tip = (cx + dx * radius_outer, cy + dy * radius_outer)

        perp = (-dy, dx)
        base_hw = 0.003 + taper * 0.005

        base_l = (inner[0] - perp[0] * base_hw, inner[1] - perp[1] * base_hw)
        base_r = (inner[0] + perp[0] * base_hw, inner[1] + perp[1] * base_hw)

        rays.append([
            (round(base_l[0], 6), round(base_l[1], 6)),
            (round(tip[0], 6), round(tip[1], 6)),
            (round(base_r[0], 6), round(base_r[1], 6)),
        ])
    return rays


# ── 12. compute_arc / polygon / star helpers ──────────────────────────

def compute_arc(
    cx: float,
    cy: float,
    radius: float,
    start_angle: float = 0.0,
    end_angle: float = 360.0,
    steps: int = 24,
) -> list[Point2D]:
    """Compute points along a circular arc.

    Args:
        cx, cy: Center.
        radius: Arc radius.
        start_angle, end_angle: In degrees.
        steps: Number of sample points.

    Returns:
        ``[(x, y), ...]`` along the arc.
    """
    pts = []
    for i in range(steps + 1):
        t = i / steps
        a = math.radians(start_angle + (end_angle - start_angle) * t)
        pts.append((
            round(cx + radius * math.cos(a), 6),
            round(cy + radius * math.sin(a), 6),
        ))
    return pts


def compute_polygon(
    cx: float, cy: float, radius: float, sides: int = 6, rotation: float = 0.0,
) -> list[Point2D]:
    """Compute vertices of a regular polygon."""
    pts = []
    for i in range(sides):
        a = math.radians(rotation + 360.0 * i / sides)
        pts.append((
            round(cx + radius * math.cos(a), 6),
            round(cy + radius * math.sin(a), 6),
        ))
    return pts


def compute_star(
    cx: float, cy: float,
    outer_radius: float, inner_radius: float,
    points: int = 5, rotation: float = 0.0,
) -> list[Point2D]:
    """Compute vertices of a star polygon."""
    pts = []
    for i in range(points * 2):
        r = outer_radius if i % 2 == 0 else inner_radius
        a = math.radians(rotation + 360.0 * i / (points * 2) - 90)
        pts.append((
            round(cx + r * math.cos(a), 6),
            round(cy + r * math.sin(a), 6),
        ))
    return pts


# ── 13. armature — node-edge skeleton ──────────────────────────────────

def armature(
    nodes: list[dict],
    edges: list[dict],
    smoothness: float = 0.3,
    curved: bool = False,
    junction_separation: float = 0.0,
    junction_radius: float = 0.0,
    overlap: float = 0.0,
    **kwargs,
) -> dict[str, list[list[tuple[float, float]]]]:
    """Build tapered limb/segment geometry from an abstract node-edge graph.

    Generalizes ``segmented_chain`` to arbitrary graphs — any creature body
    plan, not just humanoid. Each node is a joint; each edge is a segment.

    Args:
        nodes: ``[{id, x, y, radius?}]`` — joint positions.
            ``radius`` controls the segment width at this joint (default 0.02).
        edges: ``[{from, to, width_start?, width_end?}]`` — connections.
            ``width_start/end`` taper the segment between nodes.
        smoothness: Curve smoothness for each segment outline.
        curved: If True, node chains become smooth Catmull-Rom curves.
        junction_separation: If > 0, branch points spread segment bases
            along the node perimeter, creating concave gaps between branches.
        junction_radius: If > 0, fillets the concave V-notch bottoms between
            separated segments using morphological opening (buffer(-r).buffer(r)).
            Turns zig-zag V-gaps into smooth U-gaps. Use with
            ``junction_separation``. Start with 0.005–0.01.
        overlap: Extends segments past their endpoints by this amount,
            useful for creating overlapping geometry at branch points
            that can be unioned into a single polygon.

    Returns:
        Dict with ``segments: [outline, ..]`` — pill-rects or curved outlines.
        When ``junction_radius > 0``, segments are merged and filleted into
        a single outline.
    """
    import math

    node_map = {}
    for n in nodes:
        nid = n["id"]
        node_map[nid] = {
            "x": float(n.get("x", 0.5)),
            "y": float(n.get("y", 0.5)),
            "radius": float(n.get("radius", 0.02)),
        }

    # Count connections per node (for junction detection)
    edge_count: dict[str, int] = {}
    for edge in edges:
        edge_count[edge["from"]] = edge_count.get(edge["from"], 0) + 1
        edge_count[edge["to"]] = edge_count.get(edge["to"], 0) + 1

    # Compute angles for each source node (for junction separation)
    edge_angles: dict[str, list[tuple[str, float]]] = {}
    for edge in edges:
        frm = node_map.get(edge["from"])
        to = node_map.get(edge["to"])
        if not frm or not to:
            continue
        a = math.atan2(to["y"] - frm["y"], to["x"] - frm["x"])
        edge_angles.setdefault(edge["from"], []).append((edge["to"], a))
    for nid in edge_angles:
        edge_angles[nid].sort(key=lambda x: x[1])

    segments = []
    for edge in edges:
        frm = node_map.get(edge["from"])
        to = node_map.get(edge["to"])
        if not frm or not to:
            continue

        dx = to["x"] - frm["x"]
        dy = to["y"] - frm["y"]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            continue

        ux, uy = dx / length, dy / length
        perp_x, perp_y = -uy, ux

        ws = float(edge.get("width_start", frm["radius"] * 2))
        we = float(edge.get("width_end", to["radius"] * 2))
        hws, hwe = ws / 2, we / 2

        cx, cy = frm["x"], frm["y"]

        # Junction separation: offset base along node perimeter
        if junction_separation > 0 and edge_count.get(edge["from"], 0) > 2:
            angles = edge_angles.get(edge["from"], [])
            for i, (tgt, a) in enumerate(angles):
                if tgt == edge["to"]:
                    n_edges = len(angles)
                    a_prev = angles[(i - 1) % n_edges][1]
                    a_next = angles[(i + 1) % n_edges][1]
                    diff_prev = (a - a_prev) % (2 * math.pi)
                    diff_next = (a_next - a) % (2 * math.pi)
                    bisector = a + (diff_next - diff_prev) * 0.25
                    off = junction_separation * frm["radius"] * 0.3
                    cx += math.cos(bisector) * off
                    cy += math.sin(bisector) * off
                    break

        # ── Apply overlap: extend segment past both endpoints ──
        start_x = cx - ux * overlap
        start_y = cy - uy * overlap
        end_x = to["x"] + ux * overlap
        end_y = to["y"] + uy * overlap
        ex_dx = end_x - start_x
        ex_dy = end_y - start_y
        ex_len = math.sqrt(ex_dx * ex_dx + ex_dy * ex_dy) or 1
        e_ux, e_uy = ex_dx / ex_len, ex_dy / ex_len
        e_perp_x, e_perp_y = -e_uy, e_ux
        mid_t = 0.35  # mid-point control at 35% along extended segment

        seg = [
            (round(start_x - e_perp_x * hws, 6), round(start_y - e_perp_y * hws, 6)),
            (round(start_x + ex_dx * mid_t - e_perp_x * hws, 6),
             round(start_y + ex_dy * mid_t - e_perp_y * hws, 6)),
            (round(end_x - e_perp_x * hwe, 6), round(end_y - e_perp_y * hwe, 6)),
            (round(end_x + e_perp_x * hwe, 6), round(end_y + e_perp_y * hwe, 6)),
            (round(start_x + ex_dx * mid_t + e_perp_x * hws, 6),
             round(start_y + ex_dy * mid_t + e_perp_y * hws, 6)),
            (round(start_x + e_perp_x * hws, 6), round(start_y + e_perp_y * hws, 6)),
        ]
        segments.append(seg)

    # Curved mode: Catmull-Rom through node chains
    if curved:
        from avge_engine.geometry.curve import fit_curves, sample_curve
        visited: set[str] = set()
        for edge in edges:
            if edge["from"] in visited:
                continue
            chain = [edge["from"]]
            cur = edge["from"]
            while True:
                nxt = [e for e in edges if e["from"] == cur and e["to"] not in visited]
                if not nxt:
                    break
                chain.append(nxt[0]["to"])
                visited.add(cur)
                cur = nxt[0]["to"]
            if len(chain) < 3:
                continue
            pts = [(node_map[n]["x"], node_map[n]["y"]) for n in chain if n in node_map]
            if len(pts) < 3:
                continue
            curve = fit_curves(pts, closed=False, smoothness=0.5)
            samples = sample_curve(curve, samples_per_segment=12)
            if len(samples) < 2:
                continue
            ws = node_map[chain[0]]["radius"] * 2
            we = node_map[chain[-1]]["radius"] * 2
            left, right = [], []
            for i, (sx, sy) in enumerate(samples):
                t = i / (len(samples) - 1)
                w = ws + (we - ws) * t
                ndx = samples[min(i + 1, len(samples) - 1)][0] - sx
                ndy = samples[min(i + 1, len(samples) - 1)][1] - sy
                if i == len(samples) - 1:
                    ndx = sx - samples[i - 1][0]
                    ndy = sy - samples[i - 1][1]
                nlen = math.sqrt(ndx * ndx + ndy * ndy) or 1
                perp = (-ndy / nlen * w / 2, ndx / nlen * w / 2)
                left.append((round(sx + perp[0], 6), round(sy + perp[1], 6)))
                right.append((round(sx - perp[0], 6), round(sy - perp[1], 6)))
            segments.append(left + right[::-1])

    # ── Junction fillet: morphological opening on merged segments ──
    if junction_radius > 0 and len(segments) > 1:
        try:
            from shapely.geometry import Polygon, MultiPolygon
            from shapely import unary_union
            polys = [Polygon(s) for s in segments if len(s) >= 3]
            if polys:
                merged = unary_union(polys)
                if not merged.is_empty and not merged.geom_type == "GeometryCollection":
                    eroded = merged.buffer(-junction_radius)
                    if not eroded.is_empty and eroded.geom_type != "GeometryCollection":
                        dilated = eroded.buffer(junction_radius)
                        if not dilated.is_empty:
                            if isinstance(dilated, MultiPolygon):
                                parts = sorted(dilated.geoms, key=lambda p: p.area,
                                               reverse=True)
                                dilated = parts[0]
                            outline = [
                                (round(x, 6), round(y, 6))
                                for x, y in dilated.exterior.coords[:-1]
                            ]
                            if len(outline) >= 3:
                                segments = [outline]
        except Exception:
            pass  # Fall back to un-filleted segments on any shapely error

    return {"segments": segments}


# ── 14. foreshorten — compress limb chain toward viewer ──────────────

def foreshorten(
    outline: list[tuple[float, float]],
    depth_factor: float = 0.5,
    pivot_end: str = "start",
) -> list[tuple[float, float]]:
    """Compress an outline along its length to simulate foreshortening.

    The outline is compressed toward one end (``pivot_end``), with width
    expanding proportionally to maintain visual volume.

    Args:
        outline: Source outline (e.g., a limb segment).
        depth_factor: 0.0 = fully side-on (no change), 1.0 = pointing at viewer.
        pivot_end: ``"start"`` (compress toward first point) or ``"end"``.

    Returns:
        Modified outline.
    """
    if not outline or len(outline) < 2 or depth_factor <= 0:
        return list(outline)

    factor = min(1.0, max(0.0, depth_factor))
    pts = list(outline)

    if pivot_end == "start":
        pivot_x, pivot_y = pts[0][0], pts[0][1]
    else:
        pivot_x, pivot_y = pts[-1][0], pts[-1][1]

    # Scale toward pivot: reduce distance from pivot by factor
    result = []
    for x, y in pts:
        dx = x - pivot_x
        dy = y - pivot_y
        nx = pivot_x + dx * (1 - factor * 0.6)
        ny = pivot_y + dy * (1 - factor * 0.6)
        result.append((round(nx, 6), round(ny, 6)))

    return result


# ── 15. surface_detail — edge-level deformations ─────────────────────

def surface_detail(
    outline: list[tuple[float, float]],
    pattern: str = "scale",
    count: int = 8,
    depth: float = 0.02,
    width: float = 0.02,
    flip: bool = False,
) -> list[tuple[float, float]]:
    """Apply repeating deformations along an outline edge.

    Args:
        outline: Source outline (closed polygon).
        pattern: ``"scale"`` (repeated bumps), ``"fur"`` (hair-like spikes),
            ``"feather"`` (V-shaped notches), ``"fold"`` (zigzag creases),
            or ``"segment"`` (straight-segment faceting).
        count: Number of deformations along the full perimeter.
        depth: How far each deformation protrudes.
        width: Width of each deformation at its base.
        flip: If True, deform inward instead of outward.

    Returns:
        Modified outline.
    """
    if len(outline) < 4 or count < 1:
        return list(outline)

    total = len(outline)
    # Distribute deformation points evenly around the outline
    stride = max(1, total // count)
    sign = -1 if flip else 1

    result = list(outline)
    inserted = 0
    for i in range(0, total, stride):
        idx = i + inserted
        if idx >= len(result) - 1:
            break
        p0 = result[idx]
        p1 = result[(idx + 1) % len(result)]

        mx = (p0[0] + p1[0]) / 2
        my = (p0[1] + p1[1]) / 2
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        perp_len = math.sqrt(dx * dx + dy * dy) or 1
        perp_x, perp_y = -dy / perp_len * sign, dx / perp_len * sign

        if pattern == "scale":
            tip = (mx + perp_x * depth, my + perp_y * depth)
            result.insert(idx + 1, (round(tip[0], 6), round(tip[1], 6)))
            inserted += 1
        elif pattern == "fur":
            tip = (mx + perp_x * depth * 2, my + perp_y * depth * 2)
            result.insert(idx + 1, (round(tip[0], 6), round(tip[1], 6)))
            inserted += 1
        elif pattern == "feather":
            hw = width / 2
            l = (mx - perp_x * hw, my - perp_y * hw)
            tip = (mx + perp_x * depth, my + perp_y * depth)
            r = (mx + perp_x * hw, my + perp_y * hw)
            result[idx:idx+1] = [
                (round(l[0], 6), round(l[1], 6)),
                (round(tip[0], 6), round(tip[1], 6)),
                (round(r[0], 6), round(r[1], 6)),
            ]
            inserted += 2
        elif pattern == "fold":
            hw = width / 2
            a = (mx - perp_x * hw, my - perp_y * hw)
            b = (mx + perp_x * depth, my + perp_y * depth)
            c = (mx + perp_x * hw, my + perp_y * hw)
            result[idx:idx+1] = [
                (round(a[0], 6), round(a[1], 6)),
                (round(b[0], 6), round(b[1], 6)),
                (round(c[0], 6), round(c[1], 6)),
            ]
            inserted += 2
        elif pattern == "segment":
            pass  # straight segment — no deformation

    return result


# ── 16. parse_svg_path — SVG path data parser ──────────────────────────

def parse_svg_path(
    path_data: str,
    samples_per_curve: int = 12,
) -> list[tuple[float, float]]:
    """Parse an SVG path data string into outline points.

    Supports M (move), L (line), C (cubic bezier), Q (quadratic bezier),
    A (arc), Z (close) commands. Relative variants (m/l/c/q/a) also supported.

    Args:
        path_data: SVG path data string, e.g. ``"M 0.1 0.1 L 0.9 0.1 ..."``.
        samples_per_curve: Sample points per cubic bezier segment (default 12).

    Returns:
        List of ``(x, y)`` coordinates.
    """
    import re

    tokens = re.findall(r'[MLQCZmlqczAa]|[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?', path_data)
    pts = []
    i = 0
    cx, cy = 0.0, 0.0
    start_x, start_y = 0.0, 0.0

    while i < len(tokens):
        cmd = tokens[i]
        i += 1

        if cmd in ('M', 'm'):
            x = float(tokens[i]); y = float(tokens[i + 1]); i += 2
            if cmd == 'm':
                x += cx; y += cy
            cx, cy = x, y
            start_x, start_y = x, y
            if not pts:
                pts.append((x, y))
        elif cmd in ('L', 'l'):
            x = float(tokens[i]); y = float(tokens[i + 1]); i += 2
            if cmd == 'l':
                x += cx; y += cy
            pts.append((x, y))
            cx, cy = x, y
        elif cmd in ('C', 'c'):
            args = [float(t) for t in tokens[i:i + 6]]; i += 6
            if cmd == 'c':
                args[0] += cx; args[1] += cy
                args[2] += cx; args[3] += cy
                args[4] += cx; args[5] += cy
            pts.extend(_sample_cubic(
                (cx, cy), (args[0], args[1]), (args[2], args[3]), (args[4], args[5]),
                samples_per_curve,
            ))
            cx, cy = args[4], args[5]
        elif cmd in ('Q', 'q'):
            args = [float(t) for t in tokens[i:i + 4]]; i += 4
            if cmd == 'q':
                args[0] += cx; args[1] += cy
                args[2] += cx; args[3] += cy
            # Quadratic → cubic control points
            cp1 = (cx + 2 * args[0]) / 3, (cy + 2 * args[1]) / 3
            cp2 = (args[2] + 2 * args[0]) / 3, (args[3] + 2 * args[1]) / 3
            pts.extend(_sample_cubic(
                (cx, cy), cp1, cp2, (args[2], args[3]),
                samples_per_curve,
            ))
            cx, cy = args[2], args[3]
        elif cmd in ('A', 'a'):
            rx = float(tokens[i]); ry = float(tokens[i + 1])
            x_rot = float(tokens[i + 2])
            laf = int(float(tokens[i + 3]))
            sf = int(float(tokens[i + 4]))
            x = float(tokens[i + 5]); y = float(tokens[i + 6]); i += 7
            if cmd == 'a':
                x += cx; y += cy
            pts.extend(_sample_arc(
                (cx, cy), (x, y), rx, ry, x_rot, laf, sf,
                samples_per_curve,
            ))
            cx, cy = x, y
        elif cmd in ('Z', 'z'):
            pts.append((start_x, start_y))
            cx, cy = start_x, start_y

    return pts


def _sample_cubic(
    p0, p1, p2, p3,
    samples: int = 12,
) -> list[tuple[float, float]]:
    """Sample points along a cubic bezier curve."""
    pts = []
    for i in range(1, samples + 1):
        t = i / samples
        u = 1 - t
        x = u ** 3 * p0[0] + 3 * u ** 2 * t * p1[0] + 3 * u * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = u ** 3 * p0[1] + 3 * u ** 2 * t * p1[1] + 3 * u * t ** 2 * p2[1] + t ** 3 * p3[1]
        pts.append((round(x, 6), round(y, 6)))
    return pts


def _sample_arc(
    p1: tuple[float, float],
    p2: tuple[float, float],
    rx: float, ry: float,
    x_axis_rotation: float = 0.0,
    large_arc_flag: int = 0,
    sweep_flag: int = 0,
    samples: int = 16,
) -> list[tuple[float, float]]:
    """Sample points along an SVG elliptical arc from p1 to p2.

    Implements the SVG arc endpoint-to-center parameterization (SVG spec
    F.6.5) and samples evenly by angle.
    """
    import math

    x1, y1 = p1
    x2, y2 = p2

    # Step 1: if radii are zero, treat as straight line
    if rx < 1e-10 or ry < 1e-10:
        return _sample_line(p1, p2, samples)

    # Step 2: ensure radii are at least large enough
    dx2 = (x1 - x2) / 2
    dy2 = (y1 - y2) / 2
    phi = math.radians(x_axis_rotation)
    cos_p = math.cos(phi)
    sin_p = math.sin(phi)

    # Step 3: transform to (x1', y1') in rotated coordinate system (SVG spec F.6.5.1)
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2

    # Ensure radii are large enough (F.6.6 correction)
    rx = abs(rx)
    ry = abs(ry)
    lambda_check = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lambda_check > 1.0:
        sqrt_l = math.sqrt(lambda_check)
        rx *= sqrt_l
        ry *= sqrt_l

    # Step 4: compute center (cx', cy') in rotated coordinates (F.6.5.2)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    if num < 0:
        num = 0.0
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    if den < 1e-10:
        return _sample_line(p1, p2, samples)
    sqrt_val = math.sqrt(num / den)
    if large_arc_flag == sweep_flag:
        sqrt_val = -sqrt_val
    cxp = sqrt_val * (rx * y1p) / ry
    cyp = sqrt_val * (-ry * x1p) / rx

    # Step 5: transform back to get actual center (cx, cy) (F.6.5.3)
    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2

    # Step 6: compute start angle and sweep (F.6.5.4-5)
    vec_ux = (x1p - cxp) / rx
    vec_uy = (y1p - cyp) / ry
    vec_vx = (-x1p - cxp) / rx
    vec_vy = (-y1p - cyp) / ry

    # Start angle
    start_angle = math.atan2(
        vec_ux * 0 + vec_uy * 1,  # cross product sign
        vec_ux * 1 + vec_uy * 0,  # dot product
    )
    # More precise:
    len_u = math.hypot(vec_ux, vec_uy)
    len_v = math.hypot(vec_vx, vec_vy)
    if len_u > 1e-10 and len_v > 1e-10:
        dot = max(-1.0, min(1.0, (vec_ux * vec_vx + vec_uy * vec_vy) / (len_u * len_v)))
        angle_delta = math.acos(dot)
        cross = vec_ux * vec_vy - vec_uy * vec_vx
        if cross < 0:
            angle_delta = -angle_delta
        if sweep_flag == 0 and angle_delta > 0:
            angle_delta -= 2 * math.pi
        elif sweep_flag == 1 and angle_delta < 0:
            angle_delta += 2 * math.pi
    else:
        angle_delta = 0.0

    # Step 7: sample points along the arc
    pts = []
    num_samples = max(2, samples)
    for i in range(1, num_samples + 1):
        t = i / num_samples
        theta = start_angle + angle_delta * t
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        px = cx + rx * cos_p * cos_t - ry * sin_p * sin_t
        py = cy + rx * sin_p * cos_t + ry * cos_p * sin_t
        pts.append((round(px, 6), round(py, 6)))
    return pts


def _sample_line(
    p1: tuple[float, float],
    p2: tuple[float, float],
    samples: int = 8,
) -> list[tuple[float, float]]:
    """Sample points along a straight line."""
    pts = []
    for i in range(1, samples + 1):
        t = i / samples
        pts.append((
            round(p1[0] + (p2[0] - p1[0]) * t, 6),
            round(p1[1] + (p2[1] - p1[1]) * t, 6),
        ))
    return pts


# ── 17. isometric_box — 3D box with 3 visible faces ─────────────────

def isometric_box(
    x: float, y: float,
    width: float = 0.2,
    depth: float = 0.12,
    height: float = 0.08,
    angle: float = 30.0,
    top_slant: float = 0.0,
) -> list[dict]:
    """Generate 3 visible faces of an isometric box (gold bar, crate, etc.).

    Returns a list of face dicts, each with ``outline`` and ``face`` name
    (``"top"``, ``"left"``, ``"right"``). The controller should fill the
    top face lightest and side faces darker for the 3D effect.

    Coordinate system:
        ``(x, y)`` is the **topmost vertex** (back-top corner).
        ``width`` extends **left-down** from the top vertex.
        ``depth`` extends **right-down** from the top vertex.
        ``height`` extends **straight down** (positive y in SVG coords).
        So the box expands rightward and downward from the top vertex —
        place ``(x, y)`` at the highest point of the box.

    With ``top_slant``, the top face shears so the front edge sits at a
    different height than the back edge — useful for matching a box leg
    to a slanted frame bottom. Positive = front edge lower.

    Args:
        x: X of the topmost corner (back-top point — the highest point).
        y: Y of the topmost corner.
        width: Box width along the left-forward axis (extends left-down).
        depth: Box depth along the right-forward axis (extends right-down).
        height: Box height, extends straight down (positive y).
        angle: Isometric angle in degrees (default 30).
        top_slant: Vertical offset at the front edge relative to the back
            edge. Positive = front edge lower (matches a downward slope).
            Applied linearly: front vertex gets full slant, side vertices
            get half. Default 0 (flat top).

    Returns:
        ``[{face: "top"|"left"|"right", outline: [(x,y), ...]}, ...]``
    """
    import math
    rad = math.radians(angle)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Axis vectors (SVG coords: y increases downward)
    # left-forward:  (-cos, sin)
    # right-forward: (cos, sin)
    # up:            (0, -1)
    lx = -cos_a * width
    ly = sin_a * width
    rx = cos_a * depth
    ry = sin_a * depth

    # Compute vertices
    # Unslanted base positions (before slant adjustment)
    hs = top_slant / 2
    bx = x + lx          # base x for left vertex
    by = y + ly          # base y for left vertex
    fx = x + lx + rx     # base x for front vertex
    fy = y + ly + ry     # base y for front vertex
    rx_p = x + rx        # base x for right vertex
    ry_p = y + ry        # base y for right vertex

    # Top face — with top_slant: full offset at front, half at sides
    p0 = (x, y)                                              # back
    p1 = (round(bx, 6), round(by + hs, 6))                   # left
    p2 = (round(fx, 6), round(fy + top_slant, 6))            # front
    p3 = (round(rx_p, 6), round(ry_p + hs, 6))               # right

    # Bottom of side faces (always at the original flat bottom)
    p4 = (round(bx, 6), round(by + height, 6))               # left-bottom
    p5 = (round(fx, 6), round(fy + height, 6))               # front-bottom
    p6 = (round(rx_p, 6), round(ry_p + height, 6))           # right-bottom

    return [
        {"face": "top",   "outline": [p0, p1, p2, p3]},
        {"face": "left",  "outline": [p1, p4, p5, p2]},
        {"face": "right", "outline": [p3, p2, p5, p6]},
    ]
