"""
Closed-form Catmull-Rom → cubic Bézier curve fitting.

This is the core deterministic algorithm: given a coarse point outline and
geometric constraints, produce smooth cubic Bézier segments without any
iterative/adaptive optimization (closed-form only — §8.1 of the production TDD).

All floating-point math uses float64 throughout; summation order is fixed.
"""

from __future__ import annotations

import numpy as np


def fit_curves(
    outline: list[tuple[float, float]],
    *,
    closed: bool = True,
    smoothness: float = 0.5,
    _corner_style: str = "round",
) -> list[list[tuple[float, float]]]:
    """
    Fit cubic Bézier curves to a coarse point outline.

    Uses standard Catmull-Rom → cubic Bézier conversion (closed-form,
    non-iterative).

    Parameters
    ----------
    outline : list of (x, y) tuples
        Coarse point outline in normalized coordinates.
    closed : bool
        If True, the curve forms a closed loop (last point connects to first).
    smoothness : float, 0.0–1.0
        0.0 = tight to the outline (sharp), 1.0 = very smooth/loose.
    _corner_style : str
        Reserved for future use; currently all corners use round joining.

    Returns
    -------
    list of list of (x, y) tuples
        Each inner list is one cubic Bézier segment: [P0, P1, P2, P3].
        P0 of segment i+1 = P3 of segment i (continuous).
    """
    if len(outline) < 2:
        return []

    points = np.array(outline, dtype=np.float64)
    n = len(points)
    tension = np.clip(smoothness, 0.0, 1.0) * 0.5  # map 0-1 → 0-0.5 tension

    if closed and n >= 3:
        return _fit_closed(points, tension, n)
    else:
        return _fit_open(points, tension, n)


def _fit_closed(
    points: np.ndarray, tension: float, n: int
) -> list[list[tuple[float, float]]]:
    """
    Catmull-Rom → cubic Bézier for a closed loop.

    For each segment i→i+1 (mod n), the cubic Bézier control points are:
        B0 = P[i]
        B1 = P[i] + (P[i+1] - P[i-1]) / 6  × tension_factor
        B2 = P[i+1] - (P[i+2] - P[i]) / 6  × tension_factor
        B3 = P[i+1]
    """
    segments: list[list[tuple[float, float]]] = []

    for i in range(n):
        p0 = points[i]
        p1 = points[(i + 1) % n]
        p_prev = points[(i - 1) % n]
        p_next = points[(i + 2) % n]

        cp0 = p0
        cp1 = p0 + (p1 - p_prev) * tension / 3.0
        cp2 = p1 - (p_next - p0) * tension / 3.0
        cp3 = p1

        segments.append([
            (float(cp0[0]), float(cp0[1])),
            (float(cp1[0]), float(cp1[1])),
            (float(cp2[0]), float(cp2[1])),
            (float(cp3[0]), float(cp3[1])),
        ])

    return segments


def _fit_open(
    points: np.ndarray, tension: float, n: int
) -> list[list[tuple[float, float]]]:
    """
    Catmull-Rom → cubic Bézier for an open curve.

    First and last points act as endpoints (B0 = P0, B3 = P_{n-1}).
    We use mirrored tangents for the endpoints:
        For first segment (P0→P1):
            B0 = P0
            B1 = P0 + (P1 - P0) * tension / 6.0   (mirror: P_{-1}=P0 - (P1-P0))
        For last segment (P_{n-2}→P_{n-1}):
            B2 = P_{n-1} - (P_{n-1} - P_{n-2}) * tension / 6.0
            B3 = P_{n-1}
    """
    segments: list[list[tuple[float, float]]] = []

    for i in range(n - 1):
        p0 = points[i]
        p1 = points[i + 1]
        p_prev = points[i - 1] if i > 0 else p0 - (p1 - p0)
        p_next = points[i + 2] if i + 2 < n else p1 + (p1 - p0)

        cp0 = p0
        cp1 = p0 + (p1 - p_prev) * tension / 3.0
        cp2 = p1 - (p_next - p0) * tension / 3.0
        cp3 = p1

        segments.append([
            (float(cp0[0]), float(cp0[1])),
            (float(cp1[0]), float(cp1[1])),
            (float(cp2[0]), float(cp2[1])),
            (float(cp3[0]), float(cp3[1])),
        ])

    return segments


def sample_curve(
    segments: list[list[tuple[float, float]]], samples_per_segment: int = 32
) -> list[tuple[float, float]]:
    """
    Sample a piecewise cubic Bézier curve at evenly-spaced parameter values.

    Useful for debugging/visualization or computing outline fidelity metrics.
    """
    if not segments:
        return []
    t = np.linspace(0.0, 1.0, samples_per_segment)
    # Bernstein basis for cubic Bézier
    b0 = (1 - t) ** 3
    b1 = 3 * t * (1 - t) ** 2
    b2 = 3 * t**2 * (1 - t)
    b3 = t**3

    points: list[tuple[float, float]] = []
    for seg in segments:
        seg_arr = np.array(seg, dtype=np.float64)
        x = b0 * seg_arr[0, 0] + b1 * seg_arr[1, 0] + b2 * seg_arr[2, 0] + b3 * seg_arr[3, 0]
        y = b0 * seg_arr[0, 1] + b1 * seg_arr[1, 1] + b2 * seg_arr[2, 1] + b3 * seg_arr[3, 1]
        points.extend(zip(x.tolist(), y.tolist()))
    return points
