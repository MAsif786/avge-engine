"""Region, primitive, curve, and boolean creation service."""
from __future__ import annotations

import json
from typing import Any

from avge_engine.scene import CurveConstraints, Style
from avge_engine.schemas.service_results import (
    BooleanOperationResult,
    CreateCurveResult,
    CreatePrimitiveResult,
    CreateRegionResult,
)
from avge_engine.services.base import BaseService
from avge_engine.services.engine import stroke_width_to_norm


class CreationService(BaseService):
    """Application service for graph creation operations."""

    def create_region(
        self,
        *,
        outline: list[list[float]],
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        closed: bool = True,
        smoothness: float = 0.5,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        fill_gradient: Any = None,
        smoothness_per_point: list[float] | None = None,
        z_index: int = 0,
        clip_to: str | None = None,
        blend_mode: str | None = None,
        tags: dict | None = None,
        blur: float = 0.0,
    ) -> CreateRegionResult:
        doc_id = self._require_document(document_id)
        resolved_fill = self._resolve_fill(fill, fill_gradient)
        metadata = self._resolve_tags(tags)
        stroke_width_norm = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        constraints = CurveConstraints(
            smoothness=max(0.0, min(1.0, smoothness)),
            closed=closed,
            tensions=smoothness_per_point,
        )
        style = Style(
            fill=None if resolved_fill is None or resolved_fill == "none" else resolved_fill,
            stroke=stroke,
            stroke_width=stroke_width_norm,
            opacity=max(0.0, min(1.0, opacity)),
            blend_mode=blend_mode,
            blur=blur,
        )
        region = self.graph.create_region(
            outline=[(float(p[0]), float(p[1])) for p in outline],
            region_id=region_id,
            document_id=doc_id,
            layer=layer,
            z_index=z_index,
            clip_to=clip_to,
            constraints=constraints,
            style=style,
            metadata=metadata,
        )
        warnings = []
        if len(outline) > 30:
            warnings.append(f"Advisory: {len(outline)} points is high")
        return CreateRegionResult(
            region_id=region.id,
            bounds=region.bounds,
            outline_point_count=len(outline),
            warnings=warnings,
        )

    def create_rect(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        rx: float = 0.0,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        blend_mode: str | None = None,
    ) -> CreatePrimitiveResult:
        doc_id = self._require_document(document_id)
        region = self.graph.create_rect(
            x,
            y,
            width,
            height,
            rx=rx,
            document_id=doc_id,
            region_id=region_id,
            layer=layer,
            z_index=z_index,
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width_to_norm(doc_id, stroke_width) or 0.005,
            opacity=opacity,
            blend_mode=blend_mode,
        )
        return CreatePrimitiveResult(region_id=region.id)

    def create_ellipse(
        self,
        *,
        cx: float,
        cy: float,
        rx: float,
        ry: float | None = None,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        blend_mode: str | None = None,
    ) -> CreatePrimitiveResult:
        doc_id = self._require_document(document_id)
        region = self.graph.create_ellipse(
            cx,
            cy,
            rx,
            ry=ry,
            document_id=doc_id,
            region_id=region_id,
            layer=layer,
            z_index=z_index,
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width_to_norm(doc_id, stroke_width) or 0.005,
            opacity=opacity,
            blend_mode=blend_mode,
        )
        return CreatePrimitiveResult(region_id=region.id)

    def create_line(
        self,
        *,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        blend_mode: str | None = None,
    ) -> CreatePrimitiveResult:
        doc_id = self._require_document(document_id)
        region = self.graph.create_line(
            x1,
            y1,
            x2,
            y2,
            document_id=doc_id,
            region_id=region_id,
            layer=layer,
            z_index=z_index,
            stroke=stroke,
            stroke_width=stroke_width_to_norm(doc_id, stroke_width) or 0.005,
            opacity=opacity,
            blend_mode=blend_mode,
        )
        return CreatePrimitiveResult(region_id=region.id)

    def create_curve(
        self,
        *,
        points: list[list[float]],
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        smoothness: float = 0.5,
        blend_mode: str | None = None,
        stroke_linecap: str | None = "round",
    ) -> CreateCurveResult:
        doc_id = self._require_document(document_id)
        stroke_width_norm = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        if len(points) == 2:
            x1, y1 = points[0]
            x2, y2 = points[1]
            region = self.graph.create_line(
                x1,
                y1,
                x2,
                y2,
                document_id=doc_id,
                region_id=region_id,
                layer=layer,
                z_index=z_index,
                stroke=stroke,
                stroke_width=stroke_width_norm,
                opacity=opacity,
                blend_mode=blend_mode,
                stroke_linecap=stroke_linecap,
            )
        else:
            region = self.graph.create_line(
                points=points,
                document_id=doc_id,
                region_id=region_id,
                layer=layer,
                z_index=z_index,
                stroke=stroke,
                stroke_width=stroke_width_norm,
                opacity=opacity,
                blend_mode=blend_mode,
                stroke_linecap=stroke_linecap,
                smoothness=smoothness,
            )
        return CreateCurveResult(region_id=region.id, points=len(points), smoothness=smoothness)

    def boolean_operation(
        self,
        *,
        operation: str = "union",
        region_ids: list[str],
        new_region_id: str | None = None,
        document_id: str | None = None,
        keep_originals: bool = False,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
    ) -> BooleanOperationResult:
        doc_id = self._require_document(document_id)
        result = self.graph.boolean_operation(
            operation=operation,
            region_ids=region_ids,
            new_region_id=new_region_id,
            document_id=doc_id,
            keep_originals=keep_originals,
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width_to_norm(doc_id, stroke_width),
            opacity=opacity,
        )
        return BooleanOperationResult(region_id=result.id, outline_points=len(result.outline))

    def _require_document(self, document_id: str | None) -> str:
        doc_id = document_id or self.graph.active_document_id()
        if not doc_id or not self.graph.has_document(doc_id):
            raise RuntimeError("No active document")
        return doc_id

    @staticmethod
    def _resolve_fill(fill: str | None, fill_gradient: Any = None) -> Any:
        if fill_gradient is None:
            return fill
        if isinstance(fill_gradient, str):
            try:
                return json.loads(fill_gradient)
            except json.JSONDecodeError as e:
                raise ValueError("invalid fill_gradient JSON") from e
        return fill_gradient

    @staticmethod
    def _resolve_tags(tags: dict | None) -> dict:
        if not tags:
            return {}
        try:
            return dict(tags)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError("tags must be a valid JSON object") from e
