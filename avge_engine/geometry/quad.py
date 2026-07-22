"""Quadrilateral interpolation and guide helpers."""
from __future__ import annotations


def lerp_point(
    a: list[float] | tuple[float, float],
    b: list[float] | tuple[float, float],
    t: float,
) -> list[float]:
    return [float(a[0]) + (float(b[0]) - float(a[0])) * t, float(a[1]) + (float(b[1]) - float(a[1])) * t]


def quad_point(quad: list[list[float]], u: float, v: float) -> list[float]:
    top = lerp_point(quad[0], quad[1], u)
    bottom = lerp_point(quad[3], quad[2], u)
    return lerp_point(top, bottom, v)


def cell_quad(
    quad: list[list[float]],
    u0: float,
    v0: float,
    u1: float,
    v1: float,
    margin_u: float,
    margin_v: float,
) -> list[list[float]]:
    du = max(0.0, u1 - u0)
    dv = max(0.0, v1 - v0)
    uu0 = u0 + du * margin_u
    uu1 = u1 - du * margin_u
    vv0 = v0 + dv * margin_v
    vv1 = v1 - dv * margin_v
    return [
        quad_point(quad, uu0, vv0),
        quad_point(quad, uu1, vv0),
        quad_point(quad, uu1, vv1),
        quad_point(quad, uu0, vv1),
    ]


def clip_line_to_bounds(
    p1: list[float],
    p2: list[float],
    bounds: tuple[float, float, float, float],
) -> list[list[float]] | None:
    """Clip an infinite line through p1/p2 to an axis-aligned bounds rectangle."""
    x0, y0, x1, y1 = bounds
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None

    hits: list[tuple[float, list[float]]] = []
    if abs(dx) > 1e-9:
        for x in (x0, x1):
            t = (x - p1[0]) / dx
            y = p1[1] + dy * t
            if y0 - 1e-9 <= y <= y1 + 1e-9:
                hits.append((t, [x, y]))
    if abs(dy) > 1e-9:
        for y in (y0, y1):
            t = (y - p1[1]) / dy
            x = p1[0] + dx * t
            if x0 - 1e-9 <= x <= x1 + 1e-9:
                hits.append((t, [x, y]))

    unique: list[tuple[float, list[float]]] = []
    for t, pt in sorted(hits, key=lambda item: item[0]):
        if not any(abs(pt[0] - u[1][0]) < 1e-6 and abs(pt[1] - u[1][1]) < 1e-6 for u in unique):
            unique.append((t, pt))
    if len(unique) < 2:
        return None
    return [unique[0][1], unique[-1][1]]
