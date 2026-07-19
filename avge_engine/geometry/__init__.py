"""Geometry types and engines."""

from avge_engine.geometry.curve import fit_curves, sample_curve
from avge_engine.geometry.types import (
    CurveConstraints,
    Point2D,
    Transform,
    compute_bounds,
    normalize_outline,
)
from avge_engine.geometry.perspective import (
    apply_homography,
    homography_from_unit_square,
    normalize_points_to_unit,
    project_unit_points,
    rectangle_grid_points,
)

__all__ = [
    "fit_curves",
    "sample_curve",
    "CurveConstraints",
    "Point2D",
    "Transform",
    "compute_bounds",
    "normalize_outline",
    "apply_homography",
    "homography_from_unit_square",
    "normalize_points_to_unit",
    "project_unit_points",
    "rectangle_grid_points",
]
