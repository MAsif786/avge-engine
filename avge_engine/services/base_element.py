"""Shared helpers for services that operate on drawable elements."""
from __future__ import annotations

from avge_engine.document import ElementNode
from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.services.base import BaseService


class BaseElementService(BaseService):
    """Common document/element mechanics for element-oriented services."""

    def require_document_id(self, document_id: str | None = None) -> str:
        return self.documents.require_id(document_id)

    def get_element(self, document_id: str, element_id: str) -> ElementNode:
        return self.documents.get_element(document_id, element_id)

    def get_elements(self, document_id: str, ids: list[str]) -> list[ElementNode]:
        return [self.get_element(document_id, element_id) for element_id in ids]

    def element_exists(self, document_id: str, element_id: str) -> bool:
        return self.documents.has_element(document_id, element_id)

    def elements_map(self, document_id: str) -> dict[str, ElementNode]:
        return self.documents.elements(document_id)

    def list_elements(self, document_id: str) -> list[ElementNode]:
        return self.documents.list_elements(document_id)

    def add_element(self, document_id: str, element: ElementNode) -> None:
        self.documents.add_element(document_id, element)

    def delete_elements(self, document_id: str, ids: list[str]) -> list[str]:
        return self.documents.delete_elements(document_id, ids)

    def commit(self, document_id: str, *, action: str | None = None, target: str | None = None) -> None:
        self.documents.commit(document_id, action=action, target=target)

    def stroke_width_to_norm(self, document_id: str, stroke_width: StrokeWidthInput) -> float | None:
        if stroke_width is None:
            return None
        doc = self.documents.get(document_id)
        shorter = max(1, min(doc.width, doc.height))
        return max(0.001, min(0.1, float(stroke_width) / shorter))
