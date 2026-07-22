"""Geometry types and engines."""

from avge_engine.geometry.curve import fit_curves, sample_curve
from avge_engine.geometry.line_refinement import chaikin, moving_average, rdp
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
from avge_engine.geometry.quad import cell_quad, clip_line_to_bounds, lerp_point, quad_point

__all__ = [
    "fit_curves",
    "sample_curve",
    "chaikin",
    "moving_average",
    "rdp",
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
    "cell_quad",
    "clip_line_to_bounds",
    "lerp_point",
    "quad_point",
]
