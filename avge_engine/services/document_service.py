"""Document lifecycle service.

Controllers and HTTP handlers should call this service instead of reaching
directly into document-store internals for document layer.
"""
from __future__ import annotations

from typing import Any

from avge_engine.schemas.service_results import DeleteDocumentsResult, DocumentSummary
from avge_engine.document.models import DocumentNode
from avge_engine.services.base import BaseService
from avge_engine.services.document_load_service import DocumentLoadService
from avge_engine.services.engine import set_active_doc


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
        doc_id = self.documents.require_id(document_id)
        from avge_engine.services.inspection_service import InspectionService

        desc = InspectionService(self.graph).describe_scene(document_id=doc_id)
        return DocumentSummary(
            document=desc["document"],
            element_count=desc["element_count"],
            elements=desc["elements"] if include_elements else None,
        )

    def list_documents(self) -> list[dict[str, Any]]:
        return self.documents.list_stored()

    def clone_document(
        self,
        *,
        source_document_id: str | None = None,
        name: str | None = None,
        set_active: bool = True,
    ) -> tuple[DocumentNode, str, int]:
        source_id = self.documents.require_id(source_document_id)
        clone = self.graph.clone_document(source_id, name=name, set_active=set_active)
        if set_active:
            set_active_doc(clone.id)
        from avge_engine.services.inspection_service import InspectionService

        desc = InspectionService(self.graph).describe_scene(document_id=clone.id)
        return clone, source_id, desc["element_count"]

    def delete_documents(self, ids: list[str], *, confirm: bool = False) -> DeleteDocumentsResult:
        stored = {d["id"]: d for d in self.documents.list_stored()}
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
                if self.documents.delete(doc_id):
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
        doc_id = self.documents.require_id(document_id)

        resolved = self._resolve_background(background, fill_gradient)
        doc = self.graph.get_document(doc_id)
        object.__setattr__(doc, "background", resolved)
        self.documents.commit(doc_id, action="set_background", target=doc_id)
        return doc

    def ensure_loaded_summary(self, document_id: str) -> DocumentSummary:
        DocumentLoadService(self.graph).ensure_loaded_from_storage(document_id)
        from avge_engine.services.inspection_service import InspectionService

        desc = InspectionService(self.graph).describe_scene(document_id=document_id)
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
