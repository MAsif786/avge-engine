"""In-memory document session state.

This class owns process-local document session concerns: which document is
active for MCP-style calls, and whether a document is loaded into the current
process. Services should not depend on this directly; use DocumentRepository.
"""
from __future__ import annotations

from types import ModuleType


class DocumentSessionManager:
    """Track active and loaded documents for one process."""

    def __init__(self, graph: ModuleType) -> None:
        self.graph = graph
        self._active_doc_id: str | None = None

    def active_document_id(self) -> str | None:
        """Return the active document ID, falling back to document operation state."""
        return self._active_doc_id or self.graph.active_document_id()

    def set_active(self, document_id: str) -> None:
        """Set the current active document for this process."""
        self._active_doc_id = document_id
        self.graph.set_active_document_id(document_id)

    def clear_active(self) -> None:
        self._active_doc_id = None

    def resolve_id(self, document_id: str | None = None) -> str:
        """Resolve explicit document ID or active document ID."""
        if document_id:
            return document_id
        active = self.active_document_id()
        if not active:
            raise RuntimeError("No active document. Call create_document first.")
        return active

    def has_loaded(self, document_id: str | None = None) -> bool:
        doc_id = document_id or self.active_document_id()
        return self.graph.has_document(doc_id) if doc_id else False

    def require_loaded_id(self, document_id: str | None = None) -> str:
        """Resolve and require a document to be loaded in this process."""
        doc_id = self.resolve_id(document_id)
        if not self.graph.has_document(doc_id):
            raise ValueError(f"Document '{doc_id}' not found")
        return doc_id

    def load_from_storage(self, document_id: str) -> bool:
        """Load a persisted document into this process and make it active."""
        if not self.graph.load_document(document_id):
            return False
        self.set_active(document_id)
        return True
