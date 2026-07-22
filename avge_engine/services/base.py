"""Base class for application services."""
from __future__ import annotations

from avge_engine.scene import SceneGraph
from avge_engine.services.engine import get_graph


class BaseService:
    """Provide a shared graph dependency for services."""

    def __init__(self, graph: SceneGraph | None = None) -> None:
        self.graph = graph or get_graph()
