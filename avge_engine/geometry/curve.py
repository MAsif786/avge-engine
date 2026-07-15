"""
Production curve engine — closed-form Catmull-Rom → cubic Bézier fitting.

§8.1 Determinism:
- Uses a closed-form, non-iterative fitting method (Catmull-Rom-to-cubic-Bézier).
- All floating-point math uses IEEE-754 float64 throughout.
- Fixed evaluation order (no SIMD paths that reorder summation).
- No adaptive/tolerance-based early exit.

The smoothness guidance from §4.5d (validated in MVP spike) should be
included in the LLM's system prompt:
- 0.0–0.1: geometric/polygonal (houses, stars, rectangles)
- 0.2–0.5: mixed rigid/organic (cup body, tree trunk)
- 0.6–0.8: organic/curved (foliage, faces, ellipses)
"""

from __future__ import annotations

import numpy as np


def fit_curves(
    outline: list[tuple[float, float]],
    *,
    closed: bool = True,
    smoothness: float = 0.5,
    tensions: list[float] | None = None,
    handle_in: list[tuple[float, float]] | None = None,
    handle_out: list[tuple[float, float]] | None = None,
) -> list[list[tuple[float, float]]]:
    """
    Fit cubic Bézier curves to a coarse point outline.

    Parameters
    ----------
    outline : list of (x, y) tuples in normalized space.
    closed : bool
        True for closed loop, False for open path.
    smoothness : float, 0.0–1.0
        Controls tangent scale. 0.0 = polygonal, 1.0 = very smooth.
    handle_in, handle_out : list of (dx, dy) or None
        Per-point Bézier handle vectors. When provided, they override
        the Catmull-Rom tangent computation. Each entry is a relative
        offset from the anchor point. Must match outline length.

    Returns
    -------
    list of cubic Bézier segments, each a list of 4 (x, y) control points.
    """
    if len(outline) < 2:
        return []
    if len(outline) == 2:
        # Degenerate: return a straight line segment
        return [[outline[0], outline[0], outline[1], outline[1]]]

    # When explicit Bézier handles are provided, use them directly
    if handle_in is not None and handle_out is not None:
        return _fit_with_handles(outline, handle_in, handle_out, closed)

    points = np.array(outline, dtype=np.float64)
    n = len(points)
    if tensions is not None:
        tens_arr = np.clip(np.array(tensions, dtype=np.float64), 0.0, 1.0) * 0.5
    else:
        tens_arr = np.full(n, np.clip(smoothness, 0.0, 1.0) * 0.5)
    if closed and n >= 3:
        return _fit_closed_ppt(points, tens_arr, n)
    else:
        return _fit_open_ppt(points, tens_arr, n)


def _fit_with_handles(
    outline: list[tuple[float, float]],
    handle_in: list[tuple[float, float]],
    handle_out: list[tuple[float, float]],
    closed: bool,
) -> list[list[tuple[float, float]]]:
    """Build cubic Bézier segments from explicit per-point handles.

    For each segment from outline[i] to outline[i+1]:
      cp0 = outline[i]
      cp1 = outline[i] + handle_out[i]
      cp2 = outline[i+1] - handle_in[i+1]
      cp3 = outline[i+1]
    """
    n = len(outline)
    segments: list[list[tuple[float, float]]] = []

    if closed:
        for i in range(n):
            p0 = outline[i]
            p1 = outline[(i + 1) % n]
            ho = handle_out[i]
            hi = handle_in[(i + 1) % n]
            segments.append([
                (_r(p0[0]), _r(p0[1])),
                (_r(p0[0] + ho[0]), _r(p0[1] + ho[1])),
                (_r(p1[0] - hi[0]), _r(p1[1] - hi[1])),
                (_r(p1[0]), _r(p1[1])),
            ])
    else:
        for i in range(n - 1):
            p0 = outline[i]
            p1 = outline[i + 1]
            ho = handle_out[i]
            hi = handle_in[i + 1]
            segments.append([
                (_r(p0[0]), _r(p0[1])),
                (_r(p0[0] + ho[0]), _r(p0[1] + ho[1])),
                (_r(p1[0] - hi[0]), _r(p1[1] - hi[1])),
                (_r(p1[0]), _r(p1[1])),
            ])

    return segments


def _fit_closed(
    points: np.ndarray, tension: float, n: int
) -> list[list[tuple[float, float]]]:
    """Closed Catmull-Rom → cubic Bézier. Wraps indices mod n."""
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
            (_r(cp0[0]), _r(cp0[1])),
            (_r(cp1[0]), _r(cp1[1])),
            (_r(cp2[0]), _r(cp2[1])),
            (_r(cp3[0]), _r(cp3[1])),
        ])
    return segments


def _fit_open(
    points: np.ndarray, tension: float, n: int
) -> list[list[tuple[float, float]]]:
    """Open Catmull-Rom → cubic Bézier. Mirrors tangents at endpoints."""
    segments: list[list[tuple[float, float]]] = []
    for i in range(n - 1):
        p0 = points[i]
        p1 = points[i + 1]

        if i > 0:
            p_prev = points[i - 1]
        else:
            p_prev = p0 - (p1 - p0)

        if i + 2 < n:
            p_next = points[i + 2]
        else:
            p_next = p1 + (p1 - p0)

        cp0 = p0
        cp1 = p0 + (p1 - p_prev) * tension / 3.0
        cp2 = p1 - (p_next - p0) * tension / 3.0
        cp3 = p1

        segments.append([
            (_r(cp0[0]), _r(cp0[1])),
            (_r(cp1[0]), _r(cp1[1])),
            (_r(cp2[0]), _r(cp2[1])),
            (_r(cp3[0]), _r(cp3[1])),
        ])
    return segments


def sample_curve(
    segments: list[list[tuple[float, float]]],
    samples_per_segment: int = 32,
) -> list[tuple[float, float]]:
    """Sample a piecewise cubic Bézier curve at evenly-spaced parameters.

    Useful for outline fidelity metrics (§11.6) and golden regression tests.
    """
    if not segments:
        return []
    t = np.linspace(0.0, 1.0, samples_per_segment)
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


def _r(v: float) -> float:
    """Round to 6 decimal places (determinism gate)."""
    return round(float(v), 6)


def _fit_closed_ppt(
    points: np.ndarray, tens: np.ndarray, n: int
) -> list[list[tuple[float, float]]]:
    """Closed Catmull-Rom with per-point tension."""
    segments: list[list[tuple[float, float]]] = []
    for i in range(n):
        p0, p1 = points[i], points[(i+1)%n]
        p_prev = points[(i-1)%n]
        p_next = points[(i+2)%n]
        t_i, t_ip1 = tens[i], tens[(i+1)%n]
        cp0, cp3 = p0, p1
        cp1 = p0 + (p1 - p_prev) * t_i / 3.0
        cp2 = p1 - (p_next - p0) * t_ip1 / 3.0
        segments.append([(_r(cp0[0]),_r(cp0[1])),(_r(cp1[0]),_r(cp1[1])),(_r(cp2[0]),_r(cp2[1])),(_r(cp3[0]),_r(cp3[1]))])
    return segments


def _fit_open_ppt(
    points: np.ndarray, tens: np.ndarray, n: int
) -> list[list[tuple[float, float]]]:
    """Open Catmull-Rom with per-point tension."""
    segments: list[list[tuple[float, float]]] = []
    for i in range(n-1):
        p0, p1 = points[i], points[i+1]
        p_prev = points[i-1] if i>0 else p0-(p1-p0)
        p_next = points[i+2] if i+2<n else p1+(p1-p0)
        t_i, t_ip1 = tens[i], tens[i+1]
        cp0, cp3 = p0, p1
        cp1 = p0 + (p1 - p_prev) * t_i / 3.0
        cp2 = p1 - (p_next - p0) * t_ip1 / 3.0
        segments.append([(_r(cp0[0]),_r(cp0[1])),(_r(cp1[0]),_r(cp1[1])),(_r(cp2[0]),_r(cp2[1])),(_r(cp3[0]),_r(cp3[1]))])
    return segments
