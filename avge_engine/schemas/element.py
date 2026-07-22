"""Element and primitive request schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from avge_engine.schemas.common import BLEND_MODES, BOOLEAN_OPS


class CreateElementRequest(BaseModel):
    outline: list[list[float]]
    document_id: str | None = None
    element_id: str | None = None
    layer: str = "default"
    closed: bool = True
    smoothness: float = Field(default=0.5, ge=0.0, le=1.0)
    fill: str | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float | None = Field(default=None, ge=0.0, le=512, description="Stroke width in canvas pixels.")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    fill_gradient: Any = None
    smoothness_per_point: list[float] | None = None
    z_index: int = 0
    clip_to: str | None = None
    blend_mode: BLEND_MODES | None = None
    tags: dict | None = None
    shape: dict | None = None
    stroke_linecap: str | None = None
    blur: float = Field(default=0.0, ge=0.0, le=80.0)


class EditElementRequest(BaseModel):
    element_id: str
    document_id: str
    outline: list[list[float]] | None = None
    smoothness: float | None = Field(default=None, ge=0.0, le=1.0)
    smoothness_per_point: list[float] | None = None
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=512, description="Stroke width in canvas pixels.")
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    z_index: int | None = None
    blend_mode: BLEND_MODES | None = None
    clip_to: str | None = None
    layer: str | None = None
    tags: dict | None = None
    shape: dict | None = None
    stroke_linecap: str | None = None
    blur: float | None = Field(default=None, ge=0.0, le=80.0)


class DeleteElementRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    document_id: str
    confirm: bool = False


class CopyElementRequest(BaseModel):
    source_document_id: str | None = None
    target_document_id: str
    element_id: str | None = None
    group: str | None = None
    new_element_id: str | None = None
    offset_x: float = 0.0
    offset_y: float = 0.0


class BooleanOpRequest(BaseModel):
    operation: BOOLEAN_OPS = "union"
    element_ids: list[str] = Field(min_length=2)
    new_element_id: str | None = None
    document_id: str
    keep_originals: bool = False
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=512, description="Stroke width in canvas pixels.")
    opacity: float | None = None


class CreateCurveRequest(BaseModel):
    points: list[list[float]] = Field(min_length=2, max_length=100)
    document_id: str
    element_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    stroke: str | None = "#333333"
    stroke_width: float | None = Field(default=None, ge=0.0, le=512, description="Stroke width in canvas pixels.")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    smoothness: float = Field(default=0.5, ge=0.0, le=1.0)
    blend_mode: BLEND_MODES | None = None
    stroke_linecap: str | None = "round"


class CreateRectRequest(BaseModel):
    x: float
    y: float
    width: float
    height: float
    rx: float = 0.0
    document_id: str
    element_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    fill: str | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float | None = Field(default=None, ge=0.0, le=512, description="Stroke width in canvas pixels.")
    opacity: float = 1.0
    blend_mode: str | None = None


class CreateEllipseRequest(BaseModel):
    cx: float
    cy: float
    rx: float
    ry: float | None = None
    document_id: str
    element_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    fill: str | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float | None = Field(default=None, ge=0.0, le=512, description="Stroke width in canvas pixels.")
    opacity: float = 1.0
    blend_mode: str | None = None


class CreateLineRequest(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    document_id: str
    element_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    stroke: str | None = "#333333"
    stroke_width: float | None = Field(default=None, ge=0.0, le=512, description="Stroke width in canvas pixels.")
    opacity: float = 1.0
    blend_mode: str | None = None
