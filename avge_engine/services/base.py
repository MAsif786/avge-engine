"""Base class for application services."""
from __future__ import annotations

from types import ModuleType

from avge_engine.document import DocumentRepository, DocumentSessionManager
from avge_engine.services.engine import get_document_operations, get_session_manager


class BaseService:
    """Provide shared engine dependencies for application services."""

    def __init__(self, graph: ModuleType | None = None) -> None:
        if graph is None:
            self.graph = get_document_operations()
            session = get_session_manager()
        else:
            self.graph = graph
            session = DocumentSessionManager(graph)
        self.documents = DocumentRepository(self.graph, session)
