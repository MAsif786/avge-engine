"""Perspective projection helpers for quadrilateral warps."""
from __future__ import annotations

from avge_engine.geometry.types import Point2D


def _solve_linear_system(matrix: list[list[float]], values: list[float]) -> list[float]:
    """Solve a small dense linear system with Gaussian elimination."""
    n = len(values)
    a = [row[:] + [values[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("target quadrilateral is degenerate")
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]

        scale = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= scale

        for r in range(n):
            if r == col:
                continue
            factor = a[r][col]
            if abs(factor) < 1e-12:
                continue
            for j in range(col, n + 1):
                a[r][j] -= factor * a[col][j]

    return [a[i][n] for i in range(n)]


def homography_from_unit_square(target_quad: list[Point2D]) -> list[float]:
    """Return homography coefficients mapping unit square to ``target_quad``.

    The target quad order is top-left, top-right, bottom-right, bottom-left.
    Coefficients are returned as ``[h00, h01, h02, h10, h11, h12, h20, h21]``
    with ``h22`` fixed to 1.
    """
    if len(target_quad) != 4:
        raise ValueError("target_quad must contain exactly four points")

    src = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    matrix: list[list[float]] = []
    values: list[float] = []
    for (u, v), (x, y) in zip(src, target_quad):
        matrix.append([u, v, 1.0, 0.0, 0.0, 0.0, -x * u, -x * v])
        values.append(x)
        matrix.append([0.0, 0.0, 0.0, u, v, 1.0, -y * u, -y * v])
        values.append(y)
    return _solve_linear_system(matrix, values)


def apply_homography(point: Point2D, coeffs: list[float]) -> Point2D:
    """Apply homography coefficients returned by ``homography_from_unit_square``."""
    u, v = point
    h00, h01, h02, h10, h11, h12, h20, h21 = coeffs
    denom = h20 * u + h21 * v + 1.0
    if abs(denom) < 1e-12:
        raise ValueError("projected point lies at infinity")
    return (
        round((h00 * u + h01 * v + h02) / denom, 6),
        round((h10 * u + h11 * v + h12) / denom, 6),
    )


def project_unit_points(points: list[Point2D], target_quad: list[Point2D]) -> list[Point2D]:
    """Project unit-square points into a target quadrilateral."""
    coeffs = homography_from_unit_square(target_quad)
    return [apply_homography(p, coeffs) for p in points]


def rectangle_grid_points(columns: int = 1, rows: int = 1) -> list[Point2D]:
    """Return closed unit-square perimeter points with optional edge divisions."""
    cols = max(1, min(64, int(columns)))
    row_count = max(1, min(64, int(rows)))
    pts: list[Point2D] = []

    for i in range(cols + 1):
        pts.append((i / cols, 0.0))
    for j in range(1, row_count + 1):
        pts.append((1.0, j / row_count))
    for i in range(cols - 1, -1, -1):
        pts.append((i / cols, 1.0))
    for j in range(row_count - 1, 0, -1):
        pts.append((0.0, j / row_count))
    return pts


def normalize_points_to_unit(points: list[Point2D]) -> list[Point2D]:
    """Normalize arbitrary points into their own bounding box as unit coords."""
    if not points:
        return []
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1e-12)
    height = max(max_y - min_y, 1e-12)
    return [((x - min_x) / width, (y - min_y) / height) for x, y in points]
