"""
Data models for AVGE documents.

ElementNode and DocumentNode are Pydantic models.
"""
from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from avge_engine.geometry import CurveConstraints, Point2D, Transform, compute_bounds
from avge_engine.effects import Style
from avge_engine.storage.compact import decode_outline_q, encode_outline_q


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


# ── Core data objects ──────────────────────────────────────────────

class ElementNode(BaseModel):
    """A drawable element node in a document."""

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

    _elements: dict[str, ElementNode] = PrivateAttr(default_factory=dict)
    _groups: dict[str, list[str]] = PrivateAttr(default_factory=dict)
    _checkpoints: dict[str, tuple[dict[str, Any], dict[str, ElementNode], dict[str, list[str]]]] = PrivateAttr(default_factory=dict)
    _checkpoint_meta: dict[str, dict[str, str]] = PrivateAttr(default_factory=dict)
    _auto_checkpoint_counter: int = PrivateAttr(default=0)
    _tool_calls: dict[str, int] = PrivateAttr(default_factory=dict)

    def set_elements(self, elements: dict[str, ElementNode]) -> None:
        self._elements = dict(elements)

    def elements(self) -> dict[str, ElementNode]:
        return self._elements

    def list_elements(self) -> list[ElementNode]:
        return list(self._elements.values())

    def element_count(self) -> int:
        return len(self._elements)

    def add_element(self, element: ElementNode) -> None:
        if element.id in self._elements:
            raise ValueError(f"Element '{element.id}' already exists in document '{self.id}'")
        self._elements[element.id] = element

    def get_element(self, element_id: str) -> ElementNode:
        element = self._elements.get(element_id)
        if element is None:
            raise ValueError(f"Element '{element_id}' not found in document '{self.id}'")
        return element

    def has_element(self, element_id: str) -> bool:
        return element_id in self._elements

    def delete_element(self, element_id: str) -> bool:
        if element_id not in self._elements:
            return False
        del self._elements[element_id]
        return True

    def delete_elements(self, ids: list[str]) -> list[str]:
        deleted: list[str] = []
        for element_id in ids:
            if self.delete_element(element_id):
                deleted.append(element_id)
        return deleted

    def set_groups(self, groups: dict[str, list[str]]) -> None:
        self._groups = {name: list(ids) for name, ids in groups.items()}

    def groups(self) -> dict[str, list[str]]:
        return self._groups

    def group_elements(self, group_name: str, element_ids: list[str], *, replace: bool = False) -> list[str]:
        members = [] if replace else list(self._groups.get(group_name, []))
        for element_id in element_ids:
            if self.has_element(element_id) and element_id not in members:
                members.append(element_id)
        self._groups[group_name] = members
        return members

    def add_to_group(self, group_name: str, element_ids: list[str]) -> list[str]:
        return self.group_elements(group_name, element_ids, replace=False)

    def remove_from_group(self, group_name: str, element_ids: list[str]) -> list[str]:
        if group_name not in self._groups:
            raise ValueError(f"Group '{group_name}' not found")
        removed = [element_id for element_id in element_ids if element_id in self._groups[group_name]]
        self._groups[group_name] = [
            element_id for element_id in self._groups[group_name]
            if element_id not in element_ids
        ]
        return removed

    def ungroup_elements(self, group_name: str | list[str]) -> bool | list[str]:
        if isinstance(group_name, str):
            return self._groups.pop(group_name, None) is not None
        removed: list[str] = []
        for name in group_name:
            if self._groups.pop(name, None) is not None:
                removed.append(name)
        return removed

    def get_group(self, group_name: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for element_id in self._groups.get(group_name, []):
            element = self._elements.get(element_id)
            if element is not None:
                result.append({"id": element_id, "bounds": element.bounds})
        return result

    def list_groups(self) -> list[dict[str, int]]:
        return [
            {"name": name, "count": len(ids)}
            for name, ids in sorted(self._groups.items())
        ]

    def list_layers(self) -> list[dict[str, int]]:
        layers: dict[str, int] = {}
        for element in self._elements.values():
            layers[element.layer] = layers.get(element.layer, 0) + 1
        return [{"layer": layer, "count": count} for layer, count in sorted(layers.items())]

    def track_op(self, tool_name: str) -> None:
        self._tool_calls[tool_name] = self._tool_calls.get(tool_name, 0) + 1

    def tool_stats_summary(self) -> dict[str, Any]:
        calls = dict(self._tool_calls)
        return {
            "document_id": self.id,
            "tool_calls": calls,
            "total_calls": sum(calls.values()),
        }

    def checkpoint(self, name: str, *, action: str = "manual_checkpoint", detail: str = "") -> str:
        import datetime as _dt

        self._checkpoints[name] = (
            copy.deepcopy(self.model_dump()),
            copy.deepcopy(self._elements),
            copy.deepcopy(self._groups),
        )
        self._checkpoint_meta[name] = {
            "name": name,
            "time": _dt.datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "detail": detail,
            "element_count": str(len(self._elements)),
        }
        return name

    def auto_checkpoint(self, *, action: str, detail: str = "") -> str:
        self._auto_checkpoint_counter += 1
        return self.checkpoint(
            f"auto_{self._auto_checkpoint_counter:03d}",
            action=action,
            detail=detail,
        )

    def restore_checkpoint(self, name: str) -> bool:
        snapshot = self._checkpoints.get(name)
        if snapshot is None:
            return False
        doc_data, elements, groups = copy.deepcopy(snapshot)
        restored = DocumentNode(**doc_data)
        for field_name in type(self).model_fields:
            setattr(self, field_name, getattr(restored, field_name))
        self.set_elements(elements)
        self.set_groups(groups)
        return True

    def list_checkpoints(self) -> list[str]:
        return list(self._checkpoints)

    def checkpoint_entries(self, limit: int | None = None) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for name in self.list_checkpoints():
            entry = dict(self._checkpoint_meta.get(name, {}))
            entry.setdefault("name", name)
            entry.setdefault("time", "?")
            entry.setdefault("action", "?")
            entry.setdefault("detail", "")
            entry.setdefault("element_count", "?")
            entries.append(entry)
        return entries[:limit] if limit is not None else entries

    def checkpoint_snapshot(self, name: str) -> tuple["DocumentNode", dict[str, ElementNode]]:
        snapshot = self._checkpoints.get(name)
        if snapshot is None:
            raise KeyError(name)
        doc_data, elements, groups = copy.deepcopy(snapshot)
        doc = DocumentNode(**doc_data)
        doc.set_elements(elements)
        doc.set_groups(groups)
        return doc, elements
