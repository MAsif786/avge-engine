"""Document lifecycle service.

Controllers and HTTP handlers should call this service instead of reaching
directly into ``SceneGraph`` internals for document operations.
"""
from __future__ import annotations

from typing import Any

from avge_engine.schemas.service_results import DeleteDocumentsResult, DocumentSummary
from avge_engine.scene.models import DocumentNode
from avge_engine.services.base import BaseService
from avge_engine.services.document_load_service import DocumentLoadService
from avge_engine.services.engine import (
    list_stored_documents,
    resolve_doc,
    set_active_doc,
)


class DocumentService(BaseService):
    """Application service for document lifecycle operations."""

    def create_document(
        self,
        *,
        width: int = 1000,
        height: int = 1000,
        unit: str = "px",
        background: str | dict = "#FFFFFF",
        fill_gradient: Any | None = None,
        name: str = "",
    ) -> DocumentNode:
        bg_resolved = self._resolve_background(background, fill_gradient)
        doc = self.graph.create_document(
            width=max(100, min(width, 4000)),
            height=max(100, min(height, 4000)),
            unit=unit,
            background=bg_resolved,
            name=name,
        )
        set_active_doc(doc.id)
        return doc

    def get_document_summary(self, document_id: str | None = None, *, include_elements: bool = False) -> DocumentSummary:
        doc_id = resolve_doc(document_id)
        desc = self.graph.describe_scene(doc_id)
        return DocumentSummary(
            document=desc["document"],
            element_count=desc["element_count"],
            elements=desc["elements"] if include_elements else None,
        )

    def list_documents(self) -> list[dict[str, Any]]:
        return list_stored_documents()

    def clone_document(
        self,
        *,
        source_document_id: str | None = None,
        name: str | None = None,
        set_active: bool = True,
    ) -> tuple[DocumentNode, str, int]:
        source_id = resolve_doc(source_document_id)
        clone = self.graph.clone_document(source_id, name=name, set_active=set_active)
        if set_active:
            set_active_doc(clone.id)
        desc = self.graph.describe_scene(clone.id)
        return clone, source_id, desc["element_count"]

    def delete_documents(self, ids: list[str], *, confirm: bool = False) -> DeleteDocumentsResult:
        stored = {d["id"]: d for d in list_stored_documents()}
        found = [stored[doc_id] for doc_id in ids if doc_id in stored]
        missing = [doc_id for doc_id in ids if doc_id not in stored]

        if not confirm:
            return DeleteDocumentsResult(
                preview=True,
                found=found,
                missing=missing,
                deleted=[],
                errors=[],
            )

        deleted: list[str] = []
        errors: list[str] = []
        for entry in found:
            doc_id = entry["id"]
            try:
                if self.graph.delete_document(doc_id):
                    deleted.append(doc_id)
                else:
                    errors.append(f"{doc_id}: not deleted")
            except Exception as e:
                errors.append(f"{doc_id}: {e}")
        return DeleteDocumentsResult(
            preview=False,
            found=found,
            missing=missing,
            deleted=deleted,
            errors=errors,
        )

    def set_background(
        self,
        *,
        document_id: str | None = None,
        background: str | dict | None = "#FFFFFF",
        fill_gradient: Any | None = None,
    ) -> DocumentNode:
        doc_id = resolve_doc(document_id)
        if not self.graph.has_document(doc_id):
            raise ValueError(f"Document '{doc_id}' not found")

        resolved = self._resolve_background(background, fill_gradient)
        doc = self.graph.get_document(doc_id)
        object.__setattr__(doc, "background", resolved)
        doc.version += 1
        self.graph._persist(doc_id)
        return doc

    def ensure_loaded_summary(self, document_id: str) -> DocumentSummary:
        DocumentLoadService(self.graph).ensure_loaded_from_storage(document_id)
        desc = self.graph.describe_scene(document_id)
        return DocumentSummary(
            document=desc["document"],
            element_count=desc["element_count"],
            elements=desc["elements"],
        )

    @staticmethod
    def _resolve_background(background: str | dict | None, fill_gradient: Any | None = None) -> str | dict | None:
        import json as _json

        if fill_gradient is not None:
            if isinstance(fill_gradient, str):
                return _json.loads(fill_gradient)
            if isinstance(fill_gradient, dict):
                return fill_gradient
            return fill_gradient

        if isinstance(background, str):
            is_url = background.startswith(("http://", "https://", "data:"))
            is_hex = background.startswith("#") and len(background) in (4, 7, 9)
            if not is_url and background != "none" and not is_hex:
                raise ValueError(f"Invalid background '{background}'")
        return background
