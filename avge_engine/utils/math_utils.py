"""Small math helpers shared across controllers and services."""
from __future__ import annotations


def clamp01(value: float) -> float:
    """Clamp a numeric value to the normalized 0..1 range."""
    return max(0.0, min(1.0, float(value)))

