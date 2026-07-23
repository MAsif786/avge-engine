"""Element, primitive, curve, and boolean creation service."""
from __future__ import annotations

import json
import uuid
from typing import Any

from avge_engine.document import CurveConstraints, ElementNode, Style
from avge_engine.geometry import fit_curves, sample_curve
from avge_engine.schemas.service_results import (
    BooleanOperationResult,
    CreateCurveResult,
    CreatePrimitiveResult,
    CreateElementResult,
)
from avge_engine.services.base_element import BaseElementService


class CreationService(BaseElementService):
    """Application service for graph creation operations."""

    def create_element(
        self,
        *,
        outline: list[list[float]],
        document_id: str | None = None,
        element_id: str | None = None,
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
    ) -> CreateElementResult:
        doc_id = self.require_document_id(document_id)
        resolved_fill = self._resolve_fill(fill, fill_gradient)
        metadata = self._resolve_tags(tags)
        stroke_width_norm = self.stroke_width_to_norm(doc_id, stroke_width) or 0.005
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
        resolved_element_id = element_id or f"r_{uuid.uuid4().hex[:8]}"
        element = self.documents.create_element_node(
            doc_id,
            element_id=resolved_element_id,
            outline=[(float(p[0]), float(p[1])) for p in outline],
            layer=layer,
            z_index=z_index,
            clip_to=clip_to,
            constraints=constraints,
            style=style,
            metadata=metadata,
        )
        self.commit(doc_id, action="create_element", target=element.id)
        warnings = []
        if len(outline) > 30:
            warnings.append(f"Advisory: {len(outline)} points is high")
        return CreateElementResult(
            element_id=element.id,
            bounds=element.bounds,
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
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        blend_mode: str | None = None,
    ) -> CreatePrimitiveResult:
        doc_id = self.require_document_id(document_id)
        element = self.documents.create_rect(
            doc_id,
            x=x,
            y=y,
            width=width,
            height=height,
            rx=rx,
            element_id=element_id,
            layer=layer,
            z_index=z_index,
            fill=fill,
            stroke=stroke,
            stroke_width=self.stroke_width_to_norm(doc_id, stroke_width) or 0.005,
            opacity=opacity,
            blend_mode=blend_mode,
        )
        self.commit(doc_id, action="create_rect", target=element.id)
        return CreatePrimitiveResult(element_id=element.id)

    def create_ellipse(
        self,
        *,
        cx: float,
        cy: float,
        rx: float,
        ry: float | None = None,
        document_id: str | None = None,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        blend_mode: str | None = None,
    ) -> CreatePrimitiveResult:
        doc_id = self.require_document_id(document_id)
        element = self.documents.create_ellipse(
            doc_id,
            cx=cx,
            cy=cy,
            rx=rx,
            ry=ry,
            element_id=element_id,
            layer=layer,
            z_index=z_index,
            fill=fill,
            stroke=stroke,
            stroke_width=self.stroke_width_to_norm(doc_id, stroke_width) or 0.005,
            opacity=opacity,
            blend_mode=blend_mode,
        )
        self.commit(doc_id, action="create_ellipse", target=element.id)
        return CreatePrimitiveResult(element_id=element.id)

    def create_line(
        self,
        *,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        document_id: str | None = None,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        blend_mode: str | None = None,
    ) -> CreatePrimitiveResult:
        doc_id = self.require_document_id(document_id)
        element = self.documents.create_line(
            doc_id,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            element_id=element_id,
            layer=layer,
            z_index=z_index,
            stroke=stroke,
            stroke_width=self.stroke_width_to_norm(doc_id, stroke_width) or 0.005,
            opacity=opacity,
            blend_mode=blend_mode,
        )
        self.commit(doc_id, action="create_line", target=element.id)
        return CreatePrimitiveResult(element_id=element.id)

    def create_curve(
        self,
        *,
        points: list[list[float]],
        document_id: str | None = None,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        stroke: str | None = "#333333",
        stroke_width: float | None = None,
        opacity: float = 1.0,
        smoothness: float = 0.5,
        blend_mode: str | None = None,
        stroke_linecap: str | None = "round",
    ) -> CreateCurveResult:
        doc_id = self.require_document_id(document_id)
        stroke_width_norm = self.stroke_width_to_norm(doc_id, stroke_width) or 0.005
        if len(points) == 2:
            x1, y1 = points[0]
            x2, y2 = points[1]
            element = self.documents.create_line(
                doc_id,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                element_id=element_id,
                layer=layer,
                z_index=z_index,
                stroke=stroke,
                stroke_width=stroke_width_norm,
                opacity=opacity,
                blend_mode=blend_mode,
                stroke_linecap=stroke_linecap,
            )
        else:
            element = self.documents.create_line(
                doc_id,
                points=points,
                element_id=element_id,
                layer=layer,
                z_index=z_index,
                stroke=stroke,
                stroke_width=stroke_width_norm,
                opacity=opacity,
                blend_mode=blend_mode,
                stroke_linecap=stroke_linecap,
                smoothness=smoothness,
            )
        self.commit(doc_id, action="create_line", target=element.id)
        return CreateCurveResult(element_id=element.id, points=len(points), smoothness=smoothness)

    def boolean_operation(
        self,
        *,
        operation: str = "union",
        element_ids: list[str],
        new_element_id: str | None = None,
        document_id: str | None = None,
        keep_originals: bool = False,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
    ) -> BooleanOperationResult:
        doc_id = self.require_document_id(document_id)
        result = self._boolean_operation(
            operation=operation,
            element_ids=element_ids,
            new_element_id=new_element_id,
            document_id=doc_id,
            keep_originals=keep_originals,
            fill=fill,
            stroke=stroke,
            stroke_width=self.stroke_width_to_norm(doc_id, stroke_width),
            opacity=opacity,
        )
        return BooleanOperationResult(element_id=result.id, outline_points=len(result.outline))

    def create_composite_element(
        self,
        outline: list[list[float]],
        document_id: str | None = None,
        *,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        closed: bool = True,
        smoothness: float = 0.5,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        sub_parts: dict | None = None,
    ) -> dict[str, Any]:
        """Create a base element with patterned sub-part protrusions."""
        import math

        doc_id = self.require_document_id(document_id)
        result_id = element_id or f"composite_{uuid.uuid4().hex[:6]}"
        base = self.documents.create_element_node(
            doc_id,
            element_id=result_id,
            outline=[(float(p[0]), float(p[1])) for p in outline],
            layer=layer,
            z_index=z_index,
            constraints=CurveConstraints(smoothness=smoothness, closed=closed),
            style=Style(
                fill=fill,
                stroke=stroke,
                stroke_width=max(0.001, min(0.1, stroke_width)),
                opacity=max(0.0, min(1.0, opacity)),
            ),
        )
        self.commit(doc_id, action="create_composite_element", target=base.id)

        sub_ids: list[str] = [base.id]
        if not sub_parts:
            return {"base_id": base.id, "sub_ids": sub_ids, "count": 1}

        count = int(sub_parts.get("count", 0))
        if count < 1:
            return {"base_id": base.id, "sub_ids": sub_ids, "count": 1}

        pattern = sub_parts.get("pattern", "radial_fan")
        anchor = sub_parts.get("anchor", "top_edge")
        length_range = sub_parts.get("length_range", [0.1, 0.15])
        part_width = sub_parts.get("width", 0.025)
        angle_spread = sub_parts.get("angle_spread", 30)
        length_var = sub_parts.get("length_variance", False)
        taper = sub_parts.get("taper", 0.5)

        points = list(base.outline)
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        if anchor == "top_edge":
            edge_points = sorted([point for point in points if point[1] < min_y + (max_y - min_y) * 0.1], key=lambda point: point[0])
        elif anchor == "bottom_edge":
            edge_points = sorted([point for point in points if point[1] > max_y - (max_y - min_y) * 0.1], key=lambda point: point[0])
        elif anchor == "left_edge":
            edge_points = sorted([point for point in points if point[0] < min_x + (max_x - min_x) * 0.1], key=lambda point: point[1])
        elif anchor == "right_edge":
            edge_points = sorted([point for point in points if point[0] > max_x - (max_x - min_x) * 0.1], key=lambda point: point[1])
        else:
            edge_points = sorted(points, key=lambda point: point[0])
        if len(edge_points) < 2:
            edge_points = points[:2]

        origins: list[tuple[float, float]] = []
        edge_span = sub_parts.get("edge_span", 1.0)
        edge_pad = (1.0 - max(0.0, min(1.0, edge_span))) / 2
        for index in range(count):
            t = edge_pad + (index / (count - 1) if count > 1 else 0.5) * (1 - 2 * edge_pad)
            total_segment = len(edge_points) - 1
            edge_pos = t * total_segment
            idx_a = min(int(edge_pos), total_segment - 1)
            idx_b = idx_a + 1
            frac = edge_pos - idx_a
            ox = edge_points[idx_a][0] + (edge_points[idx_b][0] - edge_points[idx_a][0]) * frac
            oy = edge_points[idx_a][1] + (edge_points[idx_b][1] - edge_points[idx_a][1]) * frac
            origins.append((ox, oy))

        outward = {
            "top_edge": (0, -1),
            "bottom_edge": (0, 1),
            "left_edge": (-1, 0),
            "right_edge": (1, 0),
        }.get(anchor, (0, -1))
        half_spread = angle_spread / 2

        for index, (ox, oy) in enumerate(origins):
            t_fan = index / (count - 1) if count > 1 else 0.5
            if pattern == "radial_fan":
                fan_angle = math.radians(-half_spread + t_fan * angle_spread)
                dx = outward[0] * math.cos(fan_angle) - outward[1] * math.sin(fan_angle)
                dy = outward[0] * math.sin(fan_angle) + outward[1] * math.cos(fan_angle)
            else:
                cx = (min_x + max_x) / 2
                cy = (min_y + max_y) / 2
                rdx = ox - cx
                rdy = oy - cy
                distance = math.sqrt(rdx * rdx + rdy * rdy)
                if distance < 1e-10:
                    dx, dy = outward
                else:
                    dx = rdx / distance
                    dy = rdy / distance
            if length_var and count > 1:
                length_t = 1 - abs(t_fan - 0.5) * 2
                part_len = length_range[0] + length_t * (length_range[1] - length_range[0])
            else:
                part_len = (length_range[0] + length_range[1]) / 2
            sub_id = self._create_protrusion(
                doc_id,
                part_len=part_len,
                part_width=part_width,
                taper=taper,
                ox=ox,
                oy=oy,
                dx=dx,
                dy=dy,
                base_id=base.id,
                index=index,
                layer=layer,
                z_index=z_index + 1,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
            )
            sub_ids.append(sub_id)

        return {"base_id": base.id, "sub_ids": sub_ids, "count": len(sub_ids)}

    def _create_protrusion(
        self,
        doc_id: str,
        *,
        part_len: float,
        part_width: float,
        taper: float,
        ox: float,
        oy: float,
        dx: float,
        dy: float,
        base_id: str,
        index: int,
        layer: str,
        z_index: int,
        fill: str | None,
        stroke: str | None,
        stroke_width: float,
        opacity: float,
    ) -> str:
        half_width = part_width / 2
        tip_width = half_width * taper
        px = dx * part_len
        py = dy * part_len
        perp_x = -dy
        perp_y = dx
        mid_fraction = 0.35
        mid_width = half_width * (0.3 + 0.7 * taper)
        sub_id = f"{base_id}_sub{index}"
        self.documents.create_element_node(
            doc_id,
            element_id=sub_id,
            layer=layer,
            z_index=z_index,
            outline=[
                (ox - perp_x * half_width, oy - perp_y * half_width),
                (ox + px * mid_fraction - perp_x * mid_width, oy + py * mid_fraction - perp_y * mid_width),
                (ox + px + perp_x * tip_width, oy + py + perp_y * tip_width),
                (ox + px - perp_x * tip_width, oy + py - perp_y * tip_width),
                (ox + px * mid_fraction + perp_x * mid_width, oy + py * mid_fraction + perp_y * mid_width),
                (ox + perp_x * half_width, oy + perp_y * half_width),
            ],
            constraints=CurveConstraints(smoothness=0.5, closed=True),
            style=Style(fill=fill, stroke=stroke, stroke_width=stroke_width, opacity=opacity),
        )
        self.commit(doc_id, action="create_composite_element", target=sub_id)
        return sub_id

    def _boolean_operation(
        self,
        *,
        operation: str,
        element_ids: list[str],
        new_element_id: str | None,
        document_id: str,
        keep_originals: bool,
        fill: str | None,
        stroke: str | None,
        stroke_width: float | None,
        opacity: float | None,
    ) -> ElementNode:
        """Perform boolean geometry on elements using shapely."""
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        if len(element_ids) < 2:
            raise ValueError("Need at least 2 elements for boolean operation")

        elements = self.elements_map(document_id)
        polys: list[Polygon] = []
        for element_id in element_ids:
            element = elements.get(element_id)
            if element is None:
                raise ValueError(f"Element '{element_id}' not found")
            segments = fit_curves(
                element.outline,
                closed=element.constraints.closed,
                smoothness=element.constraints.smoothness,
                tensions=list(element.constraints.tensions) if element.constraints.tensions else None,
                handle_in=list(element.constraints.handle_in) if element.constraints.handle_in else None,
                handle_out=list(element.constraints.handle_out) if element.constraints.handle_out else None,
            )
            points = sample_curve(segments, samples_per_segment=64)
            if len(points) < 3:
                raise ValueError(f"Element '{element_id}' has too few boundary points ({len(points)})")
            poly = Polygon(points)
            if not poly.is_valid:
                poly = poly.buffer(0)
            polys.append(poly)

        try:
            if operation == "union":
                geometry = unary_union(polys)
                if hasattr(geometry, "is_valid") and not geometry.is_valid:
                    geometry = geometry.buffer(0)
            elif operation == "intersect":
                geometry = polys[0]
                for poly in polys[1:]:
                    geometry = geometry.intersection(poly)
            elif operation in ("subtract", "difference"):
                geometry = polys[0]
                for poly in polys[1:]:
                    geometry = geometry.difference(poly)
            elif operation in ("xor", "sym_diff"):
                geometry = polys[0]
                for poly in polys[1:]:
                    geometry = geometry.symmetric_difference(poly)
            else:
                raise ValueError(f"Unknown operation: {operation}")
        except Exception as exc:
            raise RuntimeError(f"Boolean {operation} failed: {exc}") from exc

        if geometry.is_empty or geometry.area < 0.0001:
            raise RuntimeError(f"Boolean {operation} produced empty result")
        coords = list(geometry.exterior.coords)
        if len(coords) > 2 and coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) < 3:
            raise RuntimeError("Boolean result has too few points")

        result_id = new_element_id or f"bool_{uuid.uuid4().hex[:6]}"
        element = ElementNode(
            id=result_id,
            outline=[(float(x), float(y)) for x, y in coords],
            constraints=CurveConstraints(smoothness=0.3, closed=True),
            style=Style(
                fill=fill if fill is not None else "#CCCCCC",
                stroke=stroke,
                stroke_width=max(0.001, min(0.1, stroke_width)) if stroke_width is not None else 0.005,
                opacity=max(0.0, min(1.0, opacity)) if opacity is not None else 1.0,
            ),
        )
        self.add_element(document_id, element)
        if not keep_originals:
            self.documents.delete_elements(document_id, element_ids)
        self.commit(document_id, action=f"boolean_{operation}", target=result_id)
        return element

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
