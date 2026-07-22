"""Pydantic result schemas returned by application services."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.scene.models import ElementNode


class DocumentSummary(BaseModel):
    document: dict[str, Any]
    element_count: int
    elements: list[dict[str, Any]] | None = None


class DeleteDocumentsResult(BaseModel):
    preview: bool
    found: list[dict[str, Any]]
    missing: list[str]
    deleted: list[str]
    errors: list[str]


class HistoryEntry(BaseModel):
    name: str
    time: str = "?"
    action: str = "?"
    detail: str = ""
    element_count: str = "?"


class EditElementResult(BaseModel):
    affected: list[str]


class EditElementsResult(BaseModel):
    ok: int
    total: int
    lines: list[str]


class RefineLineResult(BaseModel):
    element_id: str
    before_points: int
    after_points: int
    mode: str
    smoothness: float | None = None


class CopyElementResult(BaseModel):
    source_document_id: str
    target_document_id: str
    copied_ids: list[str]
    group_name: str | None = None
    source_element_id: str | None = None


class InsertImageResult(BaseModel):
    mode: str
    x: float
    y: float
    width: float
    height: float
    href_length: int | None = None
    element_id: str | None = None
    created_ids: list[str] = Field(default_factory=list)


class CreateElementResult(BaseModel):
    element_id: str
    bounds: dict[str, float] | None
    outline_point_count: int
    warnings: list[str] = Field(default_factory=list)


class CreatePrimitiveResult(BaseModel):
    element_id: str


class CreateCurveResult(BaseModel):
    element_id: str
    points: int
    smoothness: float


class BooleanOperationResult(BaseModel):
    element_id: str
    outline_points: int


class PerspectiveGridResult(BaseModel):
    ids: list[str]
    vp_left: list[float]
    vp_right: list[float]
    horizon_y: float


class FacadeGridResult(BaseModel):
    prefix: str
    windows: int
    lit_ratio: float
    element_count: int


class SurfaceStripesResult(BaseModel):
    ids: list[str]


class MaterialApplyResult(BaseModel):
    material: str
    affected: int
    detail_count: int


class DepthHazeResult(BaseModel):
    affected: int
    haze_color: str
    max_strength: float


class LineHierarchyResult(BaseModel):
    outer_count: int
    inner_count: int
    outer_width: StrokeWidthInput
    inner_width: StrokeWidthInput


class ShadowResult(BaseModel):
    shadow: ElementNode
    source_id: str
    onto_element_id: str | None
    clipped: bool
    softness: float
    direction: float
    distance: float


class ShadingResult(BaseModel):
    mode: Literal["two_tone", "gradient"]
    target_count: int
    overlay_count: int
    light_direction: float
