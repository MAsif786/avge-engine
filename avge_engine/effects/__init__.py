"""Style and effects engine."""

from avge_engine.effects.style import (
    Style,
    GradientDef,
    resolve_fill,
    resolve_stroke,
    is_gradient,
    validate_gradient,
    gradient_to_svg_def,
)

__all__ = [
    "Style",
    "GradientDef",
    "resolve_fill",
    "resolve_stroke",
    "is_gradient",
    "validate_gradient",
    "gradient_to_svg_def",
]
