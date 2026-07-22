"""Document loading policy helpers.

API routes may need to hydrate documents from storage because the API and MCP
servers can run in separate processes. MCP tools should keep using the active
in-memory document flow through ``resolve_doc`` and should not call this service
for ordinary tool operations.
"""
from __future__ import annotations

from avge_engine.scene import SceneGraph
from avge_engine.services.engine import get_graph, set_active_doc


class DocumentLoadService:
    """Hydrate documents from storage for API read/render paths."""

    def __init__(self, graph: SceneGraph | None = None) -> None:
        self.graph = graph or get_graph()

    def ensure_loaded_from_storage(self, document_id: str) -> str:
        """Load a persisted document into this process or raise ValueError."""
        if self.graph.load_document(document_id):
            set_active_doc(document_id)
            return document_id
        raise ValueError(f"Document '{document_id}' not found")

    def require_loaded(self, document_id: str) -> str:
        """Require a document already loaded in memory; do not hit storage."""
        if self.graph.has_document(document_id):
            return document_id
        raise ValueError(f"Document '{document_id}' is not loaded")
