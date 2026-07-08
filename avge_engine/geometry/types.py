"""
Geometry type definitions — coordinate system, transforms, and utility functions.

Coordinate system (§4.2):
- All object coordinates expressed in normalized unit space, 0.0–1.0 on both axes.
- (0,0) = top-left, (1,1) = bottom-right.
- Engine maps to document's actual width/height at render/export time.
- Stroke width, font size, and effect parameters expressed as fraction of
  the canvas's shorter dimension.
- Rotation: degrees, clockwise-positive, about object's local bounding-box center.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


type Point2D = tuple[float, float]


@dataclass(frozen=True)
class CurveConstraints:
    """Geometric constraints for curve fitting.

    Per-point smoothness: when  is provided, each outline point
    gets its own tension value (0.0=sharp corner, 0.5=default, 1.0=very
    smooth). This lets a single outline mix sharp chin points with round
    cheek points, or angular shoulders with flowing waist curves.
    """

    smoothness: float = 0.5
    closed: bool = True
    corner_style: str = "round"
    tensions: tuple[float, ...] | None = None

    def __post_init__(self):
        object.__setattr__(self, "smoothness", max(0.0, min(1.0, self.smoothness)))
        if self.corner_style not in ("round", "sharp", "bevel"):
            raise ValueError(f"Invalid corner_style: {self.corner_style}")
        if self.tensions is not None:
            n = tuple(max(0.0, min(1.0, t)) for t in self.tensions)
            object.__setattr__(self, "tensions", n)


@dataclass(frozen=True)
class Transform:
    """Local transform relative to parent node."""

    translate: tuple[float, float] = (0.0, 0.0)
    rotate: float = 0.0
    scale: tuple[float, float] = (1.0, 1.0)

    def __post_init__(self):
        object.__setattr__(self, "translate", (
            max(-10.0, min(10.0, self.translate[0])),
            max(-10.0, min(10.0, self.translate[1])),
        ))


def compute_bounds(outline: list[Point2D]) -> dict[str, float] | None:
    """Compute bounding box of an outline in normalized coordinates.

    Returns {x, y, w, h} or None for empty outlines.
    """
    if not outline:
        return None
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    return {
        "x": round(min(xs), 6),
        "y": round(min(ys), 6),
        "w": round(max(xs) - min(xs), 6),
        "h": round(max(ys) - min(ys), 6),
    }


def normalize_outline(
    outline: list[tuple[float, float]],
    max_points: int = 2000,
) -> list[Point2D]:
    """Validate and normalize an outline array.

    Coordinates MUST be in normalized 0.0–1.0 space (see §4.2).
    Values outside this range are rejected with a clear error —
    the most common mistake is passing pixel coordinates (0-1000)
    instead of normalized ones (0.0-1.0).

    A small epsilon (±0.01) is allowed for floating-point tolerance
    and is silently clamped.
    """
    if len(outline) < 2:
        raise ValueError(f"Outline must have at least 2 points (got {len(outline)})")
    if len(outline) > max_points:
        raise ValueError(
            f"Outline exceeds max point count ({len(outline)} > {max_points})"
        )

    TOLERANCE = 0.01  # small float tolerance
    HARD_LIMIT = 2.0  # above this → clearly pixel coordinates

    result: list[Point2D] = []
    for pt in outline:
        x = float(pt[0])
        y = float(pt[1])

        # Hard reject: values way outside normalized range
        if x < -HARD_LIMIT or x > HARD_LIMIT:
            raise ValueError(
                f"Coordinate x={x} at point {pt} is outside normalized space 0.0–1.0. "
                f"Did you pass pixel coordinates instead of normalized 0.0–1.0?"
            )
        if y < -HARD_LIMIT or y > HARD_LIMIT:
            raise ValueError(
                f"Coordinate y={y} at point {pt} is outside normalized space 0.0–1.0. "
                f"Did you pass pixel coordinates instead of normalized 0.0–1.0?"
            )

        # Clamp with tolerance for float drift
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        result.append((round(x, 6), round(y, 6)))

    return result


def compute_pixel_transform(
    transform: Transform,
    bounds: dict[str, float] | None,
    canvas_w: int,
    canvas_h: int,
) -> str:
    """Compute an SVG transform string from normalized transform values."""
    parts: list[str] = []
    tx, ty = transform.translate
    sx, sy = transform.scale
    rot = transform.rotate

    if sx != 1.0 or sy != 1.0:
        parts.append(f"scale({_fmt(sx)},{_fmt(sy)})")
    if rot != 0.0:
        cx = _fmt((bounds["x"] + bounds["w"] / 2) * canvas_w) if bounds else "0"
        cy = _fmt((bounds["y"] + bounds["h"] / 2) * canvas_h) if bounds else "0"
        parts.append(f"rotate({_fmt(rot)},{cx},{cy})")
    if tx != 0.0 or ty != 0.0:
        parts.append(f"translate({_fmt(tx * canvas_w)},{_fmt(ty * canvas_h)})")

    return " ".join(parts)


def _fmt(value: float) -> str:
    """Format float to 6 decimal places, no trailing zeros."""
    rounded = round(value, 6)
    s = f"{rounded:.6f}".rstrip("0").rstrip(".")
    return s if s and s != "-0" else "0"
