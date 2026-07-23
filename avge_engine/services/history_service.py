"""History/checkpoint application service."""
from __future__ import annotations

from avge_engine.document.models import DocumentNode, ElementNode
from avge_engine.schemas.service_results import HistoryEntry
from avge_engine.services.base import BaseService
from avge_engine.services.document_load_service import DocumentLoadService


class HistoryService(BaseService):
    """Application service for checkpoint and version operations."""

    def checkpoint(self, *, name: str = "default", document_id: str | None = None) -> dict:
        doc_id = self._resolve_existing_doc(document_id)
        self.graph.checkpoint(doc_id, name)
        doc = self.graph.get_document(doc_id)
        return {
            "checkpoint": name,
            "element_count": self.graph.element_count(doc_id),
            "version": doc.version,
        }

    def restore(self, *, name: str = "default", document_id: str | None = None) -> dict:
        doc_id = self._resolve_existing_doc(document_id)
        if not self.graph.restore(doc_id, name):
            raise LookupError(f"Checkpoint '{name}' not found")
        doc = self.graph.get_document(doc_id)
        return {
            "checkpoint": name,
            "element_count": self.graph.element_count(doc_id),
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
            "element_count": self.graph.element_count(doc_id),
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
                "element_count": entry["element_count"],
            })
        return versions

    def snapshot_document(self, *, document_id: str, checkpoint_name: str) -> tuple[DocumentNode, list[ElementNode]]:
        doc_id = self._load_existing_doc(document_id)
        doc, elements = self.graph.checkpoint_snapshot(doc_id, checkpoint_name)
        return doc, list(elements.values())

    def checkpoint_diff(self, *, name: str = "default", document_id: str | None = None) -> str:
        doc_id = self._resolve_existing_doc(document_id)
        checkpoints = self.graph.list_checkpoints(doc_id)
        if not checkpoints:
            return f"No checkpoints found for document '{doc_id}'"

        current_elements = {
            element.id: self._diff_fields(element)
            for element in self.documents.list_elements(doc_id)
        }

        try:
            _doc_snap, elements_snap = self.graph.checkpoint_snapshot(doc_id, name)
        except KeyError:
            return f"Checkpoint '{name}' not found (available: {checkpoints})"

        checkpoint_elements = {
            element_id: self._diff_fields(element)
            for element_id, element in elements_snap.items()
        }

        current_ids = set(current_elements)
        checkpoint_ids = set(checkpoint_elements)
        added_ids = current_ids - checkpoint_ids
        removed_ids = checkpoint_ids - current_ids
        common_ids = current_ids & checkpoint_ids

        modified = []
        for element_id in sorted(common_ids):
            cur = current_elements[element_id]
            chk = checkpoint_elements[element_id]
            changes = []
            for field in ("fill", "stroke", "stroke_width", "z_index", "layer", "outline_len", "primitive_type"):
                if cur[field] != chk[field]:
                    changes.append(f"{field}: {chk[field]} -> {cur[field]}")
            if changes:
                modified.append({"id": element_id, "changes": changes})

        lines = [
            f"Checkpoint: '{name}'",
            f"Added: {sorted(added_ids)}" if added_ids else "Added: (none)",
            f"Removed: {sorted(removed_ids)}" if removed_ids else "Removed: (none)",
            f"Modified: {len(modified)} element(s)",
        ]
        if not added_ids and not removed_ids and not modified:
            lines.append("  (no changes since checkpoint)")
        for item in modified:
            lines.append(f"  {item['id']}: {'; '.join(item['changes'])}")
        return "\n".join(lines)

    def render_diff(self, *, name: str = "default", document_id: str | None = None, scale: float = 1.0) -> str:
        doc_id = self._resolve_existing_doc(document_id)
        checkpoints = self.graph.list_checkpoints(doc_id)
        if not checkpoints:
            return f"No checkpoints found for '{doc_id}'"

        try:
            _doc_snap, checkpoint_elements = self.graph.checkpoint_snapshot(doc_id, name)
        except KeyError:
            return f"Checkpoint '{name}' not found"

        current_elements = {element.id: element for element in self.documents.list_elements(doc_id)}
        doc = self.documents.get(doc_id)
        w, h = doc.width, doc.height
        svg_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            f'  <rect width="{w}" height="{h}" fill="#1a1a2e"/>',
            '  <text x="10" y="20" font-size="14" font-family="monospace" fill="#888">',
            f'    Diff vs checkpoint "{name}" - green=added, red=removed, yellow=modified</text>',
        ]

        checkpoint_ids = set(checkpoint_elements)
        current_ids = set(current_elements)
        added = current_ids - checkpoint_ids
        removed = checkpoint_ids - current_ids

        for element_id in sorted(checkpoint_ids):
            element = checkpoint_elements[element_id]
            if not element.outline:
                continue
            pts = " ".join(f"{p[0] * w:.1f},{p[1] * h:.1f}" for p in element.outline)
            if element.constraints.closed:
                svg_lines.append(f'  <polygon points="{pts}" fill="#666" fill-opacity="0.12" stroke="#666" stroke-opacity="0.25" stroke-width="1"/>')
            else:
                svg_lines.append(f'  <polyline points="{pts}" fill="none" stroke="#666" stroke-opacity="0.25" stroke-width="1"/>')

        for element_id in sorted(current_ids):
            element = current_elements[element_id]
            if not element.outline:
                continue
            if element_id in added:
                color = "#33ff33"
            elif element_id in removed:
                continue
            else:
                checkpoint_element = checkpoint_elements.get(element_id)
                if checkpoint_element:
                    if str(element.style.fill) == str(checkpoint_element.style.fill) and len(element.outline) == len(checkpoint_element.outline):
                        continue
                color = "#ffdd33"

            pts = " ".join(f"{p[0] * w:.1f},{p[1] * h:.1f}" for p in element.outline)
            svg_lines.append(f'  <polygon points="{pts}" fill="{color}" fill-opacity="0.35" stroke="{color}" stroke-width="2"/>')

        for element_id in sorted(removed):
            element = checkpoint_elements[element_id]
            if not element.outline:
                continue
            pts = " ".join(f"{p[0] * w:.1f},{p[1] * h:.1f}" for p in element.outline)
            svg_lines.append(f'  <polygon points="{pts}" fill="#ff3333" fill-opacity="0.25" stroke="#ff3333" stroke-width="2"/>')
            cx = sum(p[0] for p in element.outline) / len(element.outline) * w
            cy = sum(p[1] for p in element.outline) / len(element.outline) * h
            size = 6
            svg_lines.append(f'  <line x1="{cx-size}" y1="{cy-size}" x2="{cx+size}" y2="{cy+size}" stroke="#ff3333" stroke-width="2"/>')
            svg_lines.append(f'  <line x1="{cx-size}" y1="{cy+size}" x2="{cx+size}" y2="{cy-size}" stroke="#ff3333" stroke-width="2"/>')

        svg_lines.append("</svg>")
        try:
            from avge_engine.renderer.raster import render_preview_base64

            b64 = render_preview_base64("\n".join(svg_lines), scale=scale)
            return f"Diff rendered: data:image/png;base64,{b64[:50]}... ({len(b64)} chars)"
        except Exception as e:
            return f"Diff SVG generated but PNG render failed: {e}"

    @staticmethod
    def version_label(entry: HistoryEntry | dict[str, str]) -> str:
        name = entry.get("name", "")
        action = entry.get("action") or "checkpoint"
        detail = entry.get("detail") or ""
        element_count = entry.get("element_count") or "?"
        suffix = f" - {action}"
        if detail:
            suffix += f" {detail}"
        return f"{name}{suffix} ({element_count} elements)"

    @staticmethod
    def _diff_fields(element) -> dict:
        return {
            "fill": element.style.fill,
            "stroke": element.style.stroke,
            "stroke_width": element.style.stroke_width,
            "z_index": element.z_index,
            "layer": element.layer,
            "version": element.version,
            "outline_len": len(element.outline),
            "primitive_type": element.primitive.get("type") if element.primitive else None,
        }

    def _resolve_existing_doc(self, document_id: str | None) -> str:
        return self.documents.require_id(document_id)

    def _load_existing_doc(self, document_id: str) -> str:
        if self.documents.has(document_id):
            return document_id
        return DocumentLoadService(self.graph).ensure_loaded_from_storage(document_id)
