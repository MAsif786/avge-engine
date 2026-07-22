"""Procedural line-pattern geometry helpers."""
from __future__ import annotations

import math
import random


def role_opacity(role: str, opacity: float | None) -> float:
    if opacity is not None:
        return max(0.0, min(1.0, float(opacity)))
    return {
        "construction": 0.28,
        "center": 0.45,
        "gesture": 0.55,
        "implied": 0.42,
        "decorative": 0.82,
    }.get(role, 1.0)


def role_dash(role: str, pattern: str) -> str | None:
    if role == "construction":
        return "5,5"
    if role == "center":
        return "9,4,2,4"
    if role == "implied":
        return "2,7"
    if pattern == "stipple":
        return None
    return None


def resolve_bounds(bounds: list[float] | None) -> tuple[float, float, float, float]:
    vals = bounds or [0.1, 0.1, 0.8, 0.8]
    if len(vals) != 4:
        raise ValueError("bounds must be [x, y, width, height]")
    x, y, w, h = [float(v) for v in vals]
    if w <= 0 or h <= 0:
        raise ValueError("bounds width/height must be positive")
    return x, y, w, h


def line_pattern_points(
    pattern: str,
    points: list[list[float]] | None,
    center: list[float] | None,
    radius: float,
    turns: float,
    count: int,
    amplitude: float,
    frequency: float,
) -> list[list[float]]:
    samples = max(2, min(240, int(count)))
    if pattern == "spiral":
        c = center or [0.5, 0.5]
        total = max(0.25, float(turns)) * math.tau
        return [
            [
                float(c[0]) + math.cos(total * (i / (samples - 1))) * float(radius) * (i / (samples - 1)),
                float(c[1]) + math.sin(total * (i / (samples - 1))) * float(radius) * (i / (samples - 1)),
            ]
            for i in range(samples)
        ]

    if not points or len(points) < 2:
        raise ValueError(f"{pattern} requires at least 2 points")
    if pattern in ("straight", "curve"):
        return [[float(p[0]), float(p[1])] for p in points]

    a = points[0]
    b = points[-1]
    dx = float(b[0]) - float(a[0])
    dy = float(b[1]) - float(a[1])
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    generated: list[list[float]] = []
    if pattern == "wavy":
        for i in range(samples):
            t = i / (samples - 1)
            wave = math.sin(t * math.tau * max(0.25, float(frequency))) * float(amplitude)
            generated.append([float(a[0]) + dx * t + nx * wave, float(a[1]) + dy * t + ny * wave])
        return generated
    if pattern == "zigzag":
        for i in range(samples):
            t = i / (samples - 1)
            sign = 0.0 if i in (0, samples - 1) else (1.0 if i % 2 else -1.0)
            generated.append([float(a[0]) + dx * t + nx * float(amplitude) * sign, float(a[1]) + dy * t + ny * float(amplitude) * sign])
        return generated
    raise ValueError(f"Unknown path pattern '{pattern}'")


def jitter_points(points: list[list[float]], jitter: float, rng: random.Random) -> list[list[float]]:
    if jitter <= 0:
        return points
    result = []
    for i, point in enumerate(points):
        if i in (0, len(points) - 1):
            result.append(point)
        else:
            result.append([point[0] + rng.uniform(-jitter, jitter), point[1] + rng.uniform(-jitter, jitter)])
    return result


def width_profile_values(count: int, profile: str, start_width: float, end_width: float, base_width: float) -> list[float]:
    values = []
    for i in range(count):
        t = i / (count - 1) if count > 1 else 0.0
        if profile == "tapered":
            width = start_width + (end_width - start_width) * t
        elif profile == "pressure":
            width = end_width + (base_width * 1.45 - end_width) * math.sin(math.pi * t)
        else:
            width = base_width
        values.append(max(0.001, width))
    return values


def ribbon_outline(points: list[list[float]], widths: list[float]) -> list[tuple[float, float]]:
    if len(points) < 2:
        raise ValueError("variable-width line requires at least 2 points")
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    for i, point in enumerate(points):
        if i == 0:
            dx = points[1][0] - point[0]
            dy = points[1][1] - point[1]
        elif i == len(points) - 1:
            dx = point[0] - points[i - 1][0]
            dy = point[1] - points[i - 1][1]
        else:
            dx = points[i + 1][0] - points[i - 1][0]
            dy = points[i + 1][1] - points[i - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        half = widths[min(i, len(widths) - 1)] / 2
        left.append((point[0] + nx * half, point[1] + ny * half))
        right.append((point[0] - nx * half, point[1] - ny * half))
    return left + list(reversed(right))


def line_rect_intersection(
    cx: float,
    cy: float,
    ux: float,
    uy: float,
    x: float,
    y: float,
    w: float,
    h: float,
) -> list[list[float]]:
    hits: list[tuple[float, float, float]] = []
    if abs(ux) > 1e-9:
        for xx in (x, x + w):
            t = (xx - cx) / ux
            yy = cy + uy * t
            if y - 1e-9 <= yy <= y + h + 1e-9:
                hits.append((t, xx, yy))
    if abs(uy) > 1e-9:
        for yy in (y, y + h):
            t = (yy - cy) / uy
            xx = cx + ux * t
            if x - 1e-9 <= xx <= x + w + 1e-9:
                hits.append((t, xx, yy))
    if len(hits) < 2:
        return []
    hits = sorted(hits, key=lambda item: item[0])
    return [[hits[0][1], hits[0][2]], [hits[-1][1], hits[-1][2]]]


def hatch_subpaths(
    bounds: list[float] | None,
    density: int,
    angle: float,
    pattern: str,
    amplitude: float,
    jitter: float,
    rng: random.Random,
) -> list[list[list[float]]]:
    x, y, w, h = resolve_bounds(bounds)
    total = max(1, min(160, int(density)))
    angles = [float(angle)]
    if pattern == "cross_hatch":
        angles.append(float(angle) + 90.0)
    subpaths: list[list[list[float]]] = []
    for deg in angles:
        theta = math.radians(deg)
        ux, uy = math.cos(theta), math.sin(theta)
        nx, ny = -uy, ux
        cx, cy = x + w / 2, y + h / 2
        span = abs(nx) * w + abs(ny) * h
        for i in range(total):
            t = -span / 2 + span * ((i + 0.5) / total)
            if jitter:
                t += rng.uniform(-jitter, jitter)
            line = line_rect_intersection(cx + nx * t, cy + ny * t, ux, uy, x, y, w, h)
            if not line:
                continue
            if pattern == "contour_hatch":
                p0, p1 = line
                mid = [(p0[0] + p1[0]) / 2 + nx * amplitude, (p0[1] + p1[1]) / 2 + ny * amplitude]
                line = [p0, mid, p1]
            subpaths.append(line)
    if not subpaths:
        raise ValueError("No hatch lines generated")
    return subpaths


def scribble_paths(bounds: list[float] | None, count: int, jitter: float, rng: random.Random) -> list[list[list[float]]]:
    x, y, w, h = resolve_bounds(bounds)
    paths = []
    total = max(1, min(80, int(count)))
    noise = max(0.005, float(jitter) or min(w, h) * 0.09)
    for _ in range(total):
        cx = x + rng.random() * w
        cy = y + rng.random() * h
        pts = []
        steps = rng.randint(4, 8)
        for i in range(steps):
            a = rng.random() * math.tau + i * 0.7
            r = noise * rng.uniform(0.4, 1.4)
            pts.append([
                max(0.0, min(1.0, cx + math.cos(a) * r)),
                max(0.0, min(1.0, cy + math.sin(a) * r)),
            ])
        paths.append(pts)
    return paths
