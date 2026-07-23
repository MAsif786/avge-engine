"""Shared element selection service."""
from __future__ import annotations

from typing import Any

from avge_engine.document import DocumentRepository, DocumentSessionManager
from avge_engine.services.element_query import find_matching_elements


class SelectorService:
    """Resolve AVGE shared selectors into ordered element IDs."""

    def __init__(self, graph) -> None:
        self.graph = graph
        self.documents = DocumentRepository(graph, DocumentSessionManager(graph))

    def select_element_ids(
        self,
        doc_id: str,
        selector: dict[str, Any] | None,
        *,
        default_all: bool = False,
    ) -> list[str]:
        """Resolve a common AVGE selector to ordered element IDs.

        Supported selector keys:
        ids, group_name, layer, fill, tags, bounds, z_min, z_max, has_stroke.
        Multiple keys are AND-ed except ids/group_name, which establish the
        initial candidate set before filters are applied.
        """
        if not selector:
            return [r.id for r in self.graph.get_all_elements(doc_id)] if default_all else []

        candidates: list[str] | None = None
        if selector.get("ids"):
            candidates = list(selector["ids"])
        elif selector.get("group_name"):
            members = self.documents.get_group(doc_id, selector["group_name"])
            candidates = [m["id"] for m in members] if members else []

        bounds = selector.get("bounds") or {}
        query_kwargs: dict[str, Any] = {
            "document_id": doc_id,
            "fill": selector.get("fill"),
            "layer": selector.get("layer"),
            "tags": dict(selector["tags"]) if selector.get("tags") else None,
            "min_x": bounds.get("min_x", selector.get("min_x")),
            "max_x": bounds.get("max_x", selector.get("max_x")),
            "min_y": bounds.get("min_y", selector.get("min_y")),
            "max_y": bounds.get("max_y", selector.get("max_y")),
            "min_w": bounds.get("min_w", selector.get("min_w")),
            "max_w": bounds.get("max_w", selector.get("max_w")),
            "min_h": bounds.get("min_h", selector.get("min_h")),
            "max_h": bounds.get("max_h", selector.get("max_h")),
            "z_min": selector.get("z_min"),
            "z_max": selector.get("z_max"),
            "has_stroke": selector.get("has_stroke"),
        }
        has_filters = any(v is not None for k, v in query_kwargs.items() if k != "document_id")
        if has_filters:
            matched = [
                r["id"]
                for r in find_matching_elements(
                    self.documents.list_elements(doc_id),
                    fill=query_kwargs["fill"],
                    min_x=query_kwargs["min_x"],
                    max_x=query_kwargs["max_x"],
                    min_y=query_kwargs["min_y"],
                    max_y=query_kwargs["max_y"],
                    min_w=query_kwargs["min_w"],
                    max_w=query_kwargs["max_w"],
                    min_h=query_kwargs["min_h"],
                    max_h=query_kwargs["max_h"],
                    z_min=query_kwargs["z_min"],
                    z_max=query_kwargs["z_max"],
                    has_stroke=query_kwargs["has_stroke"],
                    layer=query_kwargs["layer"],
                    tags=query_kwargs["tags"],
                )
            ]
            if candidates is not None:
                matched_set = set(matched)
                return [rid for rid in candidates if rid in matched_set]
            return matched

        if candidates is not None:
            return candidates
        return [r.id for r in self.graph.get_all_elements(doc_id)] if default_all else []


def select_element_ids(graph, doc_id: str, selector: dict[str, Any] | None, *, default_all: bool = False) -> list[str]:
    """Compatibility helper for simple call sites."""
    return SelectorService(graph).select_element_ids(doc_id, selector, default_all=default_all)


def selector_from_legacy(
    *,
    ids: list[str] | None = None,
    group_name: str | None = None,
    layer: str | None = None,
) -> dict[str, Any] | None:
    """Build a selector from legacy top-level targeting params."""
    selector: dict[str, Any] = {}
    if ids:
        selector["ids"] = ids
    if group_name:
        selector["group_name"] = group_name
    if layer:
        selector["layer"] = layer
    return selector or None
