"""
Data models for the AVGE scene graph.

ElementNode and DocumentNode are Pydantic models.
ToolStats provides lightweight per-document call tracking.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from avge_engine.geometry import CurveConstraints, Point2D, Transform, compute_bounds
from avge_engine.effects import Style
from avge_engine.storage.compact import decode_outline_q, encode_outline_q


# ── Per-document tool stats ─────────────────────────────────────
_DocStats = dict[str, dict[str, int]]


def cached_model_property(func):
    """Cache a computed property on models with a private ``_property_cache``."""
    name = func.__name__

    @property
    def wrapper(self):
        cache = self._property_cache
        if name not in cache:
            cache[name] = func(self)
        return cache[name]

    return wrapper


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

class ElementNode(BaseModel):
    """A drawable element node in the scene graph."""

    id: str
    type: str = "element"
    layer: str = "default"
    z_index: int = 0
    clip_to: str | None = None
    outline_q: list[int] = Field(default_factory=list)
    constraints: CurveConstraints = Field(default_factory=CurveConstraints)
    style: Style = Field(default_factory=Style)
    transform: Transform = Field(default_factory=Transform)
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    primitive: dict | None = None

    model_config = {"arbitrary_types_allowed": True}
    _property_cache: dict[str, Any] = PrivateAttr(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _encode_outline_input(cls, data: Any) -> Any:
        if isinstance(data, dict) and "outline" in data and "outline_q" not in data:
            data = dict(data)
            data["outline_q"] = encode_outline_q(data.pop("outline") or [])
        return data

    @property
    def outline(self) -> list[Point2D]:
        return self._cached_outline

    @outline.setter
    def outline(self, value: list[Point2D]) -> None:
        outline = list(value or [])
        self.outline_q = encode_outline_q(outline)
        self._property_cache["_cached_outline"] = outline
        self._property_cache.pop("bounds", None)

    @cached_model_property
    def _cached_outline(self) -> list[Point2D]:
        return decode_outline_q(self.outline_q)

    @cached_model_property
    def bounds(self) -> dict[str, float] | None:
        return compute_bounds(self.outline)


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
