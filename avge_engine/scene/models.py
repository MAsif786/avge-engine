"""
Data models for the AVGE scene graph.

RegionNode and DocumentNode are Pydantic models.
ToolStats provides lightweight per-document call tracking.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from avge_engine.geometry import CurveConstraints, Point2D, Transform
from avge_engine.effects import Style


# ── Per-document tool stats ─────────────────────────────────────
_DocStats = dict[str, dict[str, int]]


class ToolStats:
    """Per-document tool usage tracking."""

    def __init__(self) -> None:
        self._calls: _DocStats = {}

    def track_call(self, doc_id: str, tool_name: str) -> None:
        if doc_id not in self._calls:
            self._calls[doc_id] = {}
        self._calls[doc_id][tool_name] = self._calls[doc_id].get(tool_name, 0) + 1

    def get_doc_calls(self, doc_id: str) -> dict[str, int]:
        return dict(self._calls.get(doc_id, {}))

    def to_metadata(self) -> dict:
        return {"calls": {k: dict(v) for k, v in self._calls.items()}}

    def from_metadata(self, data: dict) -> None:
        for doc_id, tools in data.get("calls", {}).items():
            if doc_id not in self._calls:
                self._calls[doc_id] = {}
            self._calls[doc_id].update(tools)


# ── Core data objects ──────────────────────────────────────────────

class RegionNode(BaseModel):
    """A region node in the scene graph."""

    id: str
    type: str = "region"
    layer: str = "default"
    z_index: int = 0
    clip_to: str | None = None
    outline: list[Point2D] = Field(default_factory=list)
    constraints: CurveConstraints = Field(default_factory=CurveConstraints)
    style: Style = Field(default_factory=Style)
    transform: Transform = Field(default_factory=Transform)
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    primitive: dict | None = None

    model_config = {"arbitrary_types_allowed": True}


class DocumentNode(BaseModel):
    """Root document node."""

    id: str
    name: str = ""
    width: int = 1000
    height: int = 1000
    unit: str = "px"
    background: str | dict = "#FFFFFF"
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    gradients: dict[str, dict] = Field(default_factory=dict)  # named gradient definitions
