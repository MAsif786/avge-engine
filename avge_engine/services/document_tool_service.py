"""Transitional service facade for legacy controller tool implementations.

Large MCP tools still contain geometry-specific orchestration in the controller
modules. This service gives those controllers a narrow service boundary while
those tool bodies are moved into focused services.
"""
from __future__ import annotations

from typing import Any

from avge_engine.services.base import BaseService


class DocumentToolService(BaseService):
    """Service boundary for legacy tool bodies that still need low-level document methods."""

    def resolve_doc(self, document_id: str | None = None) -> str:
        return self.documents.resolve_id(document_id)

    def require_doc(self, document_id: str | None = None) -> str:
        return self.documents.require_id(document_id)

    def create_rect(self, x: float, y: float, width: float, height: float, **kwargs):
        doc_id = self.require_doc(kwargs.pop("document_id", None))
        element = self.documents.create_rect(doc_id, x=x, y=y, width=width, height=height, **kwargs)
        self.documents.commit(doc_id, action="create_rect", target=element.id)
        return element

    def create_ellipse(self, cx: float, cy: float, rx: float, ry: float | None = None, **kwargs):
        doc_id = self.require_doc(kwargs.pop("document_id", None))
        element = self.documents.create_ellipse(doc_id, cx=cx, cy=cy, rx=rx, ry=ry, **kwargs)
        self.documents.commit(doc_id, action="create_ellipse", target=element.id)
        return element

    def create_line(self, x1: float = 0.0, y1: float = 0.0, x2: float = 1.0, y2: float = 1.0, **kwargs):
        doc_id = self.require_doc(kwargs.pop("document_id", None))
        element = self.documents.create_line(doc_id, x1=x1, y1=y1, x2=x2, y2=y2, **kwargs)
        self.documents.commit(doc_id, action="create_line", target=element.id)
        return element

    def create_compound_path(self, subpaths: list[list[list[float]]] | None = None, **kwargs):
        doc_id = self.require_doc(kwargs.pop("document_id", None))
        if subpaths is None:
            subpaths = kwargs.pop("subpaths")
        element = self.documents.create_compound_path(doc_id, subpaths=subpaths, **kwargs)
        self.documents.commit(doc_id, action="create_compound_path", target=element.id)
        return element

    def edit_element(self, element_id: str, document_id: str | None = None, **kwargs) -> bool:
        """Legacy controller edit convenience backed by ElementService."""
        from avge_engine.services.element_service import ElementService

        if "metadata" in kwargs and "tags" not in kwargs:
            kwargs["tags"] = kwargs.pop("metadata")
        if "tensions" in kwargs and "smoothness_per_point" not in kwargs:
            kwargs["smoothness_per_point"] = kwargs.pop("tensions")
        ElementService(self.graph).edit_element(
            element_id=element_id,
            document_id=document_id,
            **kwargs,
        )
        return True

    def extrude_element_outline(self, element_id: str, document_id: str | None = None, **kwargs) -> bool:
        """Legacy controller extrusion convenience backed by ElementService."""
        from avge_engine.services.element_service import ElementService

        return ElementService(self.graph).extrude_element_outline(
            element_id,
            document_id=document_id,
            **kwargs,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.graph, name)
