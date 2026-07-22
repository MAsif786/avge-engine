"""Element-facing compatibility service.

The current storage and MCP tool surface still use region terminology, but new
business logic should prefer element naming through this facade.
"""
from __future__ import annotations

from typing import Any

from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import EditRegionResult, EditRegionsResult
from avge_engine.services.region_service import RegionService


class ElementService(RegionService):
    """Preferred element-named facade over RegionService."""

    def delete_elements(self, *, ids: list[str], document_id: str | None = None) -> list[str]:
        return self.delete_regions(ids=ids, document_id=document_id)

    def edit_element(
        self,
        *,
        element_id: str | None = None,
        ids: list[str] | None = None,
        document_id: str | None = None,
        outline: list[list[float]] | None = None,
        point_index: int | None = None,
        point_coords: list[float] | None = None,
        point_dx: float | None = None,
        point_dy: float | None = None,
        smoothness: float | None = None,
        smoothness_per_point: list[float] | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = None,
        z_index: int | None = None,
        blend_mode: str | None = None,
        clip_to: str | None = None,
        layer: str | None = None,
        tags: dict | None = None,
        shape: dict | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        blur: float | None = None,
        handle_in: list[list[float]] | None = None,
        handle_out: list[list[float]] | None = None,
    ) -> EditRegionResult:
        return self.edit_region(
            region_id=element_id,
            ids=ids,
            document_id=document_id,
            outline=outline,
            point_index=point_index,
            point_coords=point_coords,
            point_dx=point_dx,
            point_dy=point_dy,
            smoothness=smoothness,
            smoothness_per_point=smoothness_per_point,
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=opacity,
            z_index=z_index,
            blend_mode=blend_mode,
            clip_to=clip_to,
            layer=layer,
            tags=tags,
            shape=shape,
            stroke_linecap=stroke_linecap,
            stroke_dasharray=stroke_dasharray,
            blur=blur,
            handle_in=handle_in,
            handle_out=handle_out,
        )

    def edit_elements(self, *, updates: list[dict[str, Any]], document_id: str | None = None) -> EditRegionsResult:
        return self.edit_regions(updates=updates, document_id=document_id)
