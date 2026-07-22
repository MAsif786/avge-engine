"""Procedural drawing application service.

Controllers keep MCP/API schemas and response text; this service owns scene
mutation and procedural orchestration that is shared by tool wrappers.
"""

from __future__ import annotations

import math
import random
from typing import Any

from avge_engine.scene import CurveConstraints, Style
from avge_engine.services.base import BaseService
from avge_engine.services.engine import StrokeWidthInput, resolve_doc, stroke_width_to_norm


class ProceduralService(BaseService):
    """Application service for procedural drawing tools."""

    def create_line_pattern(
        self,
        *,
        pattern: str,
        document_id: str | None = None,
        region_id: str | None = None,
        points: list[list[float]] | None = None,
        bounds: list[float] | None = None,
        center: list[float] | None = None,
        radius: float = 0.15,
        turns: float = 2.0,
        count: int = 12,
        amplitude: float = 0.025,
        frequency: float = 6.0,
        angle: float = 0.0,
        jitter: float = 0.0,
        density: int = 16,
        seed: int = 1,
        stroke: str | None = "#333333",
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = None,
        linecap: str = "round",
        dash: str | None = None,
        width_profile: str = "uniform",
        start_width: StrokeWidthInput = None,
        end_width: StrokeWidthInput = None,
        layer: str = "linework",
        z_index: int = 0,
        smoothness: float = 0.45,
        role: str = "art",
    ) -> str:
        """Create procedural linework and return the created region IDs."""
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        base_width = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        start_norm = stroke_width_to_norm(doc_id, start_width) or base_width
        end_norm = stroke_width_to_norm(doc_id, end_width) or max(0.001, base_width * 0.25)
        resolved_opacity = _role_opacity(role, opacity)
        resolved_dash = dash if dash is not None else _role_dash(role, pattern)
        prefix = region_id or f"line_pattern_{abs(hash((pattern, seed, count))) & 0xFFFF:x}"

        try:
            created: list[str] = []
            if pattern in ("straight", "curve", "wavy", "zigzag", "spiral"):
                path = _line_pattern_points(pattern, points, center, radius, turns, count, amplitude, frequency)
                path = _jitter_points(path, jitter, random.Random(seed))
                if width_profile == "uniform":
                    r = self.graph.create_line(
                        points=path,
                        document_id=doc_id,
                        region_id=prefix,
                        layer=layer,
                        z_index=z_index,
                        stroke=stroke,
                        stroke_width=base_width,
                        opacity=resolved_opacity,
                        stroke_linecap=linecap,
                        stroke_dasharray=resolved_dash,
                        smoothness=smoothness if pattern != "zigzag" else 0.0,
                    )
                else:
                    widths = _width_profile_values(len(path), width_profile, start_norm, end_norm, base_width)
                    outline = _ribbon_outline(path, widths)
                    r = self.graph.create_region(
                        outline=outline,
                        document_id=doc_id,
                        region_id=prefix,
                        layer=layer,
                        z_index=z_index,
                        constraints=CurveConstraints(smoothness=smoothness, closed=True),
                        style=Style(fill=stroke, stroke=None, opacity=resolved_opacity),
                        metadata={"tool": "create_line_pattern", "pattern": pattern, "role": role, "width_profile": width_profile},
                    )
                r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role, "width_profile": width_profile})
                created.append(r.id)
            elif pattern in ("hatch", "cross_hatch", "contour_hatch"):
                subpaths = _hatch_subpaths(bounds, density, angle, pattern, amplitude, jitter, random.Random(seed))
                r = self.graph.create_compound_path(
                    subpaths=subpaths,
                    document_id=doc_id,
                    region_id=prefix,
                    layer=layer,
                    z_index=z_index,
                    fill=None,
                    stroke=stroke,
                    stroke_width=base_width,
                    opacity=resolved_opacity,
                    stroke_linecap=linecap,
                    stroke_dasharray=resolved_dash,
                    smoothness=smoothness if pattern == "contour_hatch" else 0.0,
                    closed=False,
                )
                r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role})
                created.append(r.id)
            elif pattern == "scribble":
                rng = random.Random(seed)
                for i, path in enumerate(_scribble_paths(bounds, count, jitter, rng)):
                    r = self.graph.create_line(
                        points=path,
                        document_id=doc_id,
                        region_id=f"{prefix}_{i:02d}",
                        layer=layer,
                        z_index=z_index,
                        stroke=stroke,
                        stroke_width=base_width * rng.uniform(0.65, 1.25),
                        opacity=resolved_opacity,
                        stroke_linecap=linecap,
                        smoothness=0.65,
                    )
                    r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role})
                    created.append(r.id)
            elif pattern == "stipple":
                rng = random.Random(seed)
                x, y, w, h = _resolve_bounds(bounds)
                total = max(1, min(600, int(density if density else count)))
                for i in range(total):
                    px = x + rng.random() * w
                    py = y + rng.random() * h
                    dot_w = base_width * rng.uniform(0.7, 1.6)
                    r = self.graph.create_ellipse(
                        px,
                        py,
                        dot_w,
                        dot_w,
                        document_id=doc_id,
                        region_id=f"{prefix}_{i:03d}",
                        layer=layer,
                        z_index=z_index,
                        fill=stroke,
                        stroke=None,
                        opacity=resolved_opacity * rng.uniform(0.55, 1.0),
                    )
                    r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role})
                    created.append(r.id)
            else:
                return f"Error: Unknown line pattern '{pattern}'"
        except (ValueError, RuntimeError, TypeError) as e:
            return f"Error: {e}"

        self.graph._persist(doc_id)
        return (
            f"Line pattern created: pattern={pattern}, regions={len(created)}, "
            f"width_profile={width_profile}, role={role}, ids={', '.join(created[:6])}"
        )


def _role_opacity(role: str, opacity: float | None) -> float:
    if opacity is not None:
        return max(0.0, min(1.0, float(opacity)))
    return {
        "construction": 0.28,
        "center": 0.45,
        "gesture": 0.55,
        "implied": 0.42,
        "decorative": 0.82,
    }.get(role, 1.0)


def _role_dash(role: str, pattern: str) -> str | None:
    if role == "construction":
        return "5,5"
    if role == "center":
        return "9,4,2,4"
    if role == "implied":
        return "2,7"
    if pattern == "stipple":
        return None
    return None


def _resolve_bounds(bounds: list[float] | None) -> tuple[float, float, float, float]:
    vals = bounds or [0.1, 0.1, 0.8, 0.8]
    if len(vals) != 4:
        raise ValueError("bounds must be [x, y, width, height]")
    x, y, w, h = [float(v) for v in vals]
    if w <= 0 or h <= 0:
        raise ValueError("bounds width/height must be positive")
    return x, y, w, h


def _line_pattern_points(
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


def _jitter_points(points: list[list[float]], jitter: float, rng: random.Random) -> list[list[float]]:
    if jitter <= 0:
        return points
    result = []
    for i, p in enumerate(points):
        if i in (0, len(points) - 1):
            result.append(p)
        else:
            result.append([p[0] + rng.uniform(-jitter, jitter), p[1] + rng.uniform(-jitter, jitter)])
    return result


def _width_profile_values(count: int, profile: str, start_width: float, end_width: float, base_width: float) -> list[float]:
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


def _ribbon_outline(points: list[list[float]], widths: list[float]) -> list[tuple[float, float]]:
    if len(points) < 2:
        raise ValueError("variable-width line requires at least 2 points")
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    for i, p in enumerate(points):
        if i == 0:
            dx = points[1][0] - p[0]
            dy = points[1][1] - p[1]
        elif i == len(points) - 1:
            dx = p[0] - points[i - 1][0]
            dy = p[1] - points[i - 1][1]
        else:
            dx = points[i + 1][0] - points[i - 1][0]
            dy = points[i + 1][1] - points[i - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        half = widths[min(i, len(widths) - 1)] / 2
        left.append((p[0] + nx * half, p[1] + ny * half))
        right.append((p[0] - nx * half, p[1] - ny * half))
    return left + list(reversed(right))


def _line_rect_intersection(
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


def _hatch_subpaths(
    bounds: list[float] | None,
    density: int,
    angle: float,
    pattern: str,
    amplitude: float,
    jitter: float,
    rng: random.Random,
) -> list[list[list[float]]]:
    x, y, w, h = _resolve_bounds(bounds)
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
            line = _line_rect_intersection(cx + nx * t, cy + ny * t, ux, uy, x, y, w, h)
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


def _scribble_paths(bounds: list[float] | None, count: int, jitter: float, rng: random.Random) -> list[list[list[float]]]:
    x, y, w, h = _resolve_bounds(bounds)
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
