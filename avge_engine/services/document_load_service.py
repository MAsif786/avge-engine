"""Document loading policy helpers.

API routes may need to hydrate documents from storage because the API and MCP
servers can run in separate processes. MCP tools should keep using explicit
document IDs or the active in-memory document flow for ordinary operations.
"""
from __future__ import annotations

from avge_engine.services.base import BaseService


class DocumentLoadService(BaseService):
    """Hydrate documents from storage for API read/render paths."""

    def ensure_loaded_from_storage(self, document_id: str) -> str:
        """Load a persisted document into this process or raise ValueError."""
        if self.documents.load(document_id):
            return document_id
        raise ValueError(f"Document '{document_id}' not found")

    def require_loaded(self, document_id: str) -> str:
        """Require a document already loaded in memory; do not hit storage."""
        if not self.documents.has(document_id):
            raise ValueError(f"Document '{document_id}' is not loaded")
        return document_id
