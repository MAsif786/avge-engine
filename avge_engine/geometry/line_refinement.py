"""Polyline refinement helpers."""
from __future__ import annotations

import math


def moving_average(
    points: list[tuple[float, float]],
    *,
    strength: float,
    preserve_corners: bool,
) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    result = [points[0]]
    for i in range(1, len(points) - 1):
        prev_pt = points[i - 1]
        cur_pt = points[i]
        next_pt = points[i + 1]
        avg = ((prev_pt[0] + cur_pt[0] + next_pt[0]) / 3, (prev_pt[1] + cur_pt[1] + next_pt[1]) / 3)
        if preserve_corners and turn_angle(prev_pt, cur_pt, next_pt) < 120:
            result.append(cur_pt)
        else:
            result.append(lerp_point(cur_pt, avg, strength))
    result.append(points[-1])
    return [round_point(p) for p in result]


def chaikin(
    points: list[tuple[float, float]],
    *,
    closed: bool,
    strength: float,
    preserve_corners: bool,
) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    cut = 0.25 * strength
    result: list[tuple[float, float]] = []
    segment_count = len(points) if closed else len(points) - 1
    if not closed:
        result.append(points[0])
    for i in range(segment_count):
        p0 = points[i]
        p1 = points[(i + 1) % len(points)]
        prev_pt = points[i - 1]
        if preserve_corners and turn_angle(prev_pt, p0, p1) < 110:
            result.append(p0)
            continue
        q = lerp_point(p0, p1, cut)
        r = lerp_point(p0, p1, 1.0 - cut)
        result.extend([q, r])
    if not closed:
        result.append(points[-1])
    return [round_point(p) for p in result]


def rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    """Simplify a polyline with Ramer-Douglas-Peucker."""
    if len(points) < 3 or epsilon <= 0:
        return points
    max_dist = 0.0
    index = 0
    start = points[0]
    end = points[-1]
    for i in range(1, len(points) - 1):
        dist = point_line_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            index = i
    if max_dist > epsilon:
        left = rdp(points[: index + 1], epsilon)
        right = rdp(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def point_line_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def turn_angle(
    prev_pt: tuple[float, float],
    point: tuple[float, float],
    next_pt: tuple[float, float],
) -> float:
    ax, ay = prev_pt[0] - point[0], prev_pt[1] - point[1]
    bx, by = next_pt[0] - point[0], next_pt[1] - point[1]
    amag = math.hypot(ax, ay)
    bmag = math.hypot(bx, by)
    if amag == 0 or bmag == 0:
        return 180.0
    cos_v = max(-1.0, min(1.0, (ax * bx + ay * by) / (amag * bmag)))
    return math.degrees(math.acos(cos_v))


def lerp_point(
    a: tuple[float, float],
    b: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def round_point(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 6), round(point[1], 6))
