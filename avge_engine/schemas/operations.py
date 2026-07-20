"""Operation, query, view, and history request schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from avge_engine.schemas.common import DETAIL_LEVEL, GROUP_ACTION, PIVOT_MODES


class TransformObjectsRequest(BaseModel):
    ids: list[str] | None = None
    document_id: str
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    sx: float | None = None
    sy: float | None = None
    rotate: float = 0.0
    group_mode: bool = False
    pivot_x: float | None = None
    pivot_y: float | None = None
    pivot_mode: PIVOT_MODES | None = None
    z_index: int | None = None
    group_name: str | None = None
    mirror_x: bool = False
    mirror_y: bool = False


class ManageGroupRequest(BaseModel):
    action: GROUP_ACTION = "create"
    group_name: str
    region_ids: list[str] | None = None
    document_id: str


class DuplicateGroupRequest(BaseModel):
    group_name: str
    document_id: str
    new_prefix: str | None = None
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    sx: float | None = None
    sy: float | None = None
    rotate: float = 0.0
    mirror_x: bool = False
    mirror_y: bool = False


class ExtrudeOutlineRequest(BaseModel):
    region_id: str
    document_id: str
    segment_indices: list[int] | None = None
    extrusion_length: float = 0.03
    extrusion_width: float = 0.02
    angle_offset: float = 0.0
    direction: Literal["outward", "inward", "extrude"] = "outward"
    shape: Literal["round", "sharp", "bevel"] = "round"


class DescribeSceneRequest(BaseModel):
    detail: DETAIL_LEVEL = "summary"
    filter_layer: str | None = None
    document_id: str


class FindObjectsRequest(BaseModel):
    document_id: str
    fill: str | None = None
    min_x: float | None = None
    max_x: float | None = None
    min_y: float | None = None
    max_y: float | None = None
    min_w: float | None = None
    max_w: float | None = None
    min_h: float | None = None
    max_h: float | None = None
    has_stroke: bool | None = None
    layer: str | None = None
    tags: dict | None = None


class PreviewRequest(BaseModel):
    scale: float = Field(default=1.0, ge=0.25, le=2.0)
    document_id: str | None = None
    exclude_layers: list[str] | None = None
    exclude_region_ids: list[str] | None = None
    exclude_prefixes: list[str] | None = None


class ExportSvgRequest(BaseModel):
    filepath: str = "output/scene.svg"
    document_id: str
    exclude_layers: list[str] | None = None
    exclude_region_ids: list[str] | None = None
    exclude_prefixes: list[str] | None = None


class ReorderLayerRequest(BaseModel):
    layer: str
    z_offset: int
    document_id: str


class CheckpointRequest(BaseModel):
    name: str = "default"
    document_id: str


class BatchRequest(BaseModel):
    ops: list[dict] = Field(min_length=1, max_length=200)
    document_id: str


class DocIdBody(BaseModel):
    """Body for endpoints needing only a document_id."""

    document_id: str


class DocIdLimitBody(BaseModel):
    """Body for endpoints needing document_id + limit."""

    document_id: str
    limit: int = 20


class CritiqueRequest(BaseModel):
    document_id: str
    mode: Literal["rules", "visual", "both"] = "both"
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
