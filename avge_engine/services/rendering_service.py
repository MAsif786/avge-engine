"""Document rendering/export application service."""
from __future__ import annotations

from pathlib import Path
import re

from avge_engine.renderer import render_preview_base64, render_preview_png, svg_serialize
from avge_engine.services.base import BaseService
from avge_engine.services.document_load_service import DocumentLoadService


class RenderingService(BaseService):
    """Application service for SVG and raster preview rendering."""

    def svg(
        self,
        *,
        document_id: str | None = None,
        load_from_storage: bool = False,
        exclude_layers: list[str] | None = None,
        exclude_element_ids: list[str] | None = None,
        exclude_prefixes: list[str] | None = None,
    ) -> str:
        doc_id = self._resolve_doc_id(document_id, load_from_storage=load_from_storage)
        return svg_serialize(
            self.graph,
            doc_id,
            exclude_layers=exclude_layers,
            exclude_element_ids=exclude_element_ids,
            exclude_prefixes=exclude_prefixes,
        )

    def preview_base64(
        self,
        *,
        document_id: str | None = None,
        scale: float = 1.0,
        exclude_layers: list[str] | None = None,
        exclude_element_ids: list[str] | None = None,
        exclude_prefixes: list[str] | None = None,
    ) -> str:
        svg = self.svg(
            document_id=document_id,
            exclude_layers=exclude_layers,
            exclude_element_ids=exclude_element_ids,
            exclude_prefixes=exclude_prefixes,
        )
        return render_preview_base64(svg, scale=max(0.25, min(2.0, scale)))

    def cropped_preview_base64(
        self,
        *,
        document_id: str | None = None,
        scale: float = 1.0,
        element_id: str | None = None,
        bbox: dict | None = None,
    ) -> str:
        doc_id = self.documents.require_id(document_id)
        crop = bbox
        if element_id:
            element = self.documents.get_element(doc_id, element_id)
            b = element.bounds
            margin = 0.05
            crop = {
                "x": b["x"] - margin,
                "y": b["y"] - margin,
                "w": b["w"] + margin * 2,
                "h": b["h"] + margin * 2,
            }
        if not crop:
            raise ValueError("Provide element_id or bbox for cropped preview")

        doc = self.documents.get(doc_id)
        svg = self.svg(document_id=doc_id)
        vx = crop["x"] * doc.width
        vy = crop["y"] * doc.height
        vw = crop["w"] * doc.width
        vh = crop["h"] * doc.height
        svg = re.sub(
            r'viewBox="[^"]*"',
            f'viewBox="{vx:.0f} {vy:.0f} {vw:.0f} {vh:.0f}"',
            svg,
        )
        return render_preview_base64(svg, scale=scale)

    def preview_png(self, *, document_id: str, scale: float = 1.0) -> bytes:
        svg = self.svg(document_id=document_id, load_from_storage=True)
        return render_preview_png(svg, scale=scale)

    def export_svg(
        self,
        *,
        filepath: str,
        document_id: str | None = None,
        exclude_layers: list[str] | None = None,
        exclude_element_ids: list[str] | None = None,
        exclude_prefixes: list[str] | None = None,
    ) -> dict[str, str | int]:
        svg = self.svg(
            document_id=document_id,
            exclude_layers=exclude_layers,
            exclude_element_ids=exclude_element_ids,
            exclude_prefixes=exclude_prefixes,
        )
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg)
        return {"filepath": str(path.resolve()), "chars": len(svg)}

    def download_svg(self, *, document_id: str) -> tuple[str, bytes]:
        doc_id = self._resolve_doc_id(document_id, load_from_storage=True)
        doc = self.documents.get(doc_id)
        safe_name = self._download_name(doc.name or doc_id)
        return safe_name, self.svg(document_id=doc_id).encode("utf-8")

    def _resolve_doc_id(self, document_id: str | None, *, load_from_storage: bool) -> str:
        if load_from_storage:
            if document_id is None:
                raise ValueError("Document ID is required")
            return DocumentLoadService(self.graph).ensure_loaded_from_storage(document_id)
        return self.documents.require_id(document_id)

    @staticmethod
    def _download_name(name: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name.strip())
        return safe.strip("_") or "document"
