"""History/checkpoint application service."""
from __future__ import annotations

from avge_engine.scene import SceneGraph
from avge_engine.schemas.service_results import HistoryEntry
from avge_engine.services.document_load_service import DocumentLoadService
from avge_engine.services.engine import get_graph, resolve_doc


class HistoryService:
    """Application service for checkpoint and version operations."""

    def __init__(self, graph: SceneGraph | None = None) -> None:
        self.graph = graph or get_graph()

    def checkpoint(self, *, name: str = "default", document_id: str | None = None) -> dict:
        doc_id = self._resolve_existing_doc(document_id)
        self.graph.checkpoint(doc_id, name)
        doc = self.graph.get_document(doc_id)
        return {
            "checkpoint": name,
            "region_count": self.graph.region_count(doc_id),
            "version": doc.version,
        }

    def restore(self, *, name: str = "default", document_id: str | None = None) -> dict:
        doc_id = self._resolve_existing_doc(document_id)
        if not self.graph.restore(doc_id, name):
            raise LookupError(f"Checkpoint '{name}' not found")
        doc = self.graph.get_document(doc_id)
        return {
            "checkpoint": name,
            "region_count": self.graph.region_count(doc_id),
            "version": doc.version,
        }

    def entries(self, *, document_id: str | None = None, limit: int | None = 20) -> list[HistoryEntry]:
        doc_id = self._resolve_existing_doc(document_id)
        return [
            HistoryEntry(**entry)
            for entry in self.graph.checkpoint_entries(doc_id, limit=limit)
        ]

    def versions(self, *, document_id: str) -> list[dict]:
        doc_id = self._load_existing_doc(document_id)
        doc = self.graph.get_document(doc_id)
        versions = [{
            "id": "current",
            "name": "Current",
            "label": f"Current - v{doc.version}",
            "current": True,
            "version": doc.version,
            "region_count": self.graph.region_count(doc_id),
        }]
        for entry in self.graph.checkpoint_entries(doc_id):
            versions.append({
                "id": entry["name"],
                "name": entry["name"],
                "label": self.version_label(entry),
                "current": False,
                "time": entry["time"],
                "action": entry["action"],
                "detail": entry["detail"],
                "region_count": entry["region_count"],
            })
        return versions

    def snapshot_graph(self, *, document_id: str, checkpoint_name: str) -> SceneGraph:
        doc_id = self._load_existing_doc(document_id)
        doc, regions = self.graph.checkpoint_snapshot(doc_id, checkpoint_name)
        return SceneGraph.from_snapshot(doc_id, doc, regions)

    @staticmethod
    def version_label(entry: HistoryEntry | dict[str, str]) -> str:
        name = entry.get("name", "")
        action = entry.get("action") or "checkpoint"
        detail = entry.get("detail") or ""
        region_count = entry.get("region_count") or "?"
        suffix = f" - {action}"
        if detail:
            suffix += f" {detail}"
        return f"{name}{suffix} ({region_count} regions)"

    def _resolve_existing_doc(self, document_id: str | None) -> str:
        doc_id = resolve_doc(document_id)
        if not self.graph.has_document(doc_id):
            raise ValueError("Document not found")
        return doc_id

    def _load_existing_doc(self, document_id: str) -> str:
        if self.graph.has_document(document_id):
            return document_id
        return DocumentLoadService(self.graph).ensure_loaded_from_storage(document_id)
