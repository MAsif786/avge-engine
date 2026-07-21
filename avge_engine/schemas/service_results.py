"""Pydantic result schemas returned by application services."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.scene.models import RegionNode


class DocumentSummary(BaseModel):
    document: dict[str, Any]
    region_count: int
    regions: list[dict[str, Any]] | None = None


class DeleteDocumentsResult(BaseModel):
    preview: bool
    found: list[dict[str, Any]]
    missing: list[str]
    deleted: list[str]
    errors: list[str]


class EditRegionResult(BaseModel):
    affected: list[str]


class EditRegionsResult(BaseModel):
    ok: int
    total: int
    lines: list[str]


class RefineLineResult(BaseModel):
    region_id: str
    before_points: int
    after_points: int
    mode: str
    smoothness: float | None = None


class CopyElementResult(BaseModel):
    source_document_id: str
    target_document_id: str
    copied_ids: list[str]
    group_name: str | None = None
    source_region_id: str | None = None


class CreateRegionResult(BaseModel):
    region_id: str
    bounds: dict[str, float] | None
    outline_point_count: int
    warnings: list[str] = Field(default_factory=list)


class CreatePrimitiveResult(BaseModel):
    region_id: str


class CreateCurveResult(BaseModel):
    region_id: str
    points: int
    smoothness: float


class BooleanOperationResult(BaseModel):
    region_id: str
    outline_points: int


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
    shadow: RegionNode
    source_id: str
    onto_region_id: str | None
    clipped: bool
    softness: float
    direction: float
    distance: float


class ShadingResult(BaseModel):
    mode: Literal["two_tone", "gradient"]
    target_count: int
    overlay_count: int
    light_direction: float
