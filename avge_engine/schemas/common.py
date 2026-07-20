"""Shared API schema primitives."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "linear-dodge", "color-burn", "soft-light", "hard-light",
    "difference", "hue", "saturation", "color", "luminosity", "add",
]

BOOLEAN_OPS = Literal["union", "intersect", "subtract", "xor"]
DETAIL_LEVEL = Literal["summary", "full"]
GROUP_ACTION = Literal["create", "add", "remove", "delete"]
PRESET_NAMES = Literal[
    "warm_shaded",
    "cool_shaded",
    "metallic",
    "glow",
    "shadow",
    "wood",
    "car_paint",
    "deep_shadow",
    "chrome",
]
PIVOT_MODES = Literal["center", "base", "fixed"]

StrokeWidthInput = Annotated[
    float | None,
    Field(
        description="Stroke width in canvas pixels.",
        ge=0.0,
        le=512,
    ),
]


class ToolResponse(BaseModel):
    status: str = "ok"
    data: Any = None
    warnings: list[str] = Field(default_factory=list)
    version: int | None = None
