"""Region edit/copy/delete service."""
from __future__ import annotations

from typing import Any

from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import CopyElementResult, EditRegionResult, EditRegionsResult
from avge_engine.services.engine import get_graph, resolve_doc, stroke_width_to_norm


class RegionService:
    """Application service for region lifecycle operations."""

    def __init__(self, graph=None) -> None:
        self.graph = graph or get_graph()

    def delete_regions(self, *, ids: list[str], document_id: str | None = None) -> list[str]:
        doc_id = resolve_doc(document_id)
        return self.graph.delete_regions(doc_id, ids)

    def edit_region(
        self,
        *,
        region_id: str | None = None,
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
        """Modify one or more existing regions."""
        doc_id = resolve_doc(document_id)
        resolved_stroke_width = stroke_width_to_norm(doc_id, stroke_width)
        target_ids = ids if ids else ([region_id] if region_id else [])
        if not target_ids:
            raise ValueError("Provide region_id or ids")

        if point_index is not None and outline is None:
            outline = self._outline_with_point_edit(
                doc_id,
                target_ids[0],
                point_index=point_index,
                point_coords=point_coords,
                point_dx=point_dx,
                point_dy=point_dy,
            )

        metadata = dict(tags) if tags else None
        affected: list[str] = []
        for rid in target_ids:
            self.graph.edit_region(
                region_id=rid,
                document_id=doc_id,
                outline=outline,
                smoothness=smoothness,
                tensions=smoothness_per_point,
                fill=fill,
                stroke=stroke,
                stroke_width=resolved_stroke_width,
                opacity=opacity,
                z_index=z_index,
                blend_mode=blend_mode,
                clip_to=clip_to,
                layer=layer,
                metadata=metadata,
                shape=shape,
                stroke_linecap=stroke_linecap,
                stroke_dasharray=stroke_dasharray,
                blur=blur,
                handle_in=tuple(tuple(p) for p in handle_in) if handle_in else None,
                handle_out=tuple(tuple(p) for p in handle_out) if handle_out else None,
            )
            affected.append(rid)
        return EditRegionResult(affected=affected)

    def edit_regions(self, *, updates: list[dict], document_id: str | None = None) -> EditRegionsResult:
        """Edit multiple regions with per-region content/style updates."""
        doc_id = resolve_doc(document_id)
        lines: list[str] = []
        ok = 0
        for i, update in enumerate(updates):
            rid = update.get("id")
            if not rid:
                lines.append(f"  ✗ [{i}] Missing 'id'")
                continue
            try:
                self._apply_update_dict(doc_id, rid, update)
                ok += 1
                lines.append(f"  ✓ [{i}] {rid}")
            except (ValueError, RuntimeError, IndexError) as e:
                lines.append(f"  ✗ [{i}] {rid}: {e}")
        return EditRegionsResult(ok=ok, total=len(updates), lines=lines)

    def copy_element(
        self,
        *,
        region_id: str | None = None,
        group_name: str | None = None,
        target_document_id: str | None = None,
        source_document_id: str | None = None,
        new_region_id: str | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        skip_existing: bool = False,
    ) -> CopyElementResult:
        """Copy one region or a group between documents."""
        source_id = resolve_doc(source_document_id)
        if not target_document_id or not self.graph.has_document(target_document_id):
            raise ValueError(f"Target document '{target_document_id}' not found")

        if group_name is not None:
            members = self.graph.get_group(group_name, source_id)
            if not members:
                raise LookupError(f"Group '{group_name}' not found in source")
            copied: list[str] = []
            for member in members:
                mid = member["id"]
                try:
                    copied_id = self._copy_single_region(
                        source_id,
                        target_document_id,
                        mid,
                        new_region_id=f"{mid}_copy",
                        offset_x=offset_x,
                        offset_y=offset_y,
                        skip_existing=skip_existing,
                    )
                except ValueError:
                    if skip_existing:
                        continue
                    raise
                if copied_id:
                    copied.append(copied_id)
            self.graph.get_document(target_document_id).version += 1
            self.graph._auto_checkpoint(target_document_id, "copy_element_group", str(copied))
            self.graph._persist(target_document_id)
            return CopyElementResult(
                source_document_id=source_id,
                target_document_id=target_document_id,
                copied_ids=copied,
                group_name=group_name,
            )

        if not region_id:
            raise ValueError("Provide either region_id or group_name")
        copied_id = self._copy_single_region(
            source_id,
            target_document_id,
            region_id,
            new_region_id=new_region_id or f"{region_id}_copy",
            offset_x=offset_x,
            offset_y=offset_y,
            skip_existing=skip_existing,
        )
        self.graph.get_document(target_document_id).version += 1
        self.graph._auto_checkpoint(target_document_id, "copy_element", copied_id)
        self.graph._persist(target_document_id)
        return CopyElementResult(
            source_document_id=source_id,
            target_document_id=target_document_id,
            copied_ids=[copied_id] if copied_id else [],
            source_region_id=region_id,
        )

    def _outline_with_point_edit(
        self,
        doc_id: str,
        region_id: str,
        *,
        point_index: int,
        point_coords: list[float] | None,
        point_dx: float | None,
        point_dy: float | None,
    ) -> list[tuple[float, float]]:
        region = self.graph.get_region(region_id, doc_id)
        points = list(region.outline)
        if point_index < 0 or point_index >= len(points):
            raise IndexError(f"point_index {point_index} out of range (0-{len(points)-1})")
        if point_coords is not None:
            points[point_index] = (float(point_coords[0]), float(point_coords[1]))
        elif point_dx is not None or point_dy is not None:
            off_x = point_dx if point_dx is not None else 0.0
            off_y = point_dy if point_dy is not None else 0.0
            points[point_index] = (points[point_index][0] + off_x, points[point_index][1] + off_y)
        return points

    def _apply_update_dict(self, doc_id: str, region_id: str, update: dict[str, Any]) -> None:
        region = self.graph.get_region(region_id, doc_id)
        unsupported = [key for key in ("dx", "dy", "scale", "rotate") if key in update]
        if unsupported:
            joined = ", ".join(unsupported)
            raise ValueError(f"{joined} moved to transform_objects; edit_regions only edits content/style")

        outline = list(region.outline)
        if "outline" in update:
            outline = [(float(p[0]), float(p[1])) for p in update["outline"]]

        point_index = update.get("point_index")
        if point_index is not None:
            point_coords = update.get("point_coords")
            point_dx = update.get("point_dx", update.get("pdx", 0.0))
            point_dy = update.get("point_dy", update.get("pdy", 0.0))
            if point_index < 0 or point_index >= len(outline):
                raise IndexError(f"point_index {point_index} out of range (0-{len(outline)-1})")
            if point_coords:
                outline[point_index] = (float(point_coords[0]), float(point_coords[1]))
            elif point_dx or point_dy:
                outline[point_index] = (outline[point_index][0] + point_dx, outline[point_index][1] + point_dy)

        style_keys = (
            "fill", "stroke", "stroke_width", "opacity", "z_index",
            "layer", "blend_mode", "clip_to", "stroke_linecap",
            "stroke_dasharray",
        )
        style_kw = {key: update[key] for key in style_keys if key in update}
        self.graph.edit_region(
            region_id=region_id,
            document_id=doc_id,
            outline=outline,
            fill=style_kw.get("fill"),
            stroke=style_kw.get("stroke"),
            stroke_width=style_kw.get("stroke_width"),
            opacity=style_kw.get("opacity"),
            z_index=style_kw.get("z_index"),
            blend_mode=style_kw.get("blend_mode"),
            clip_to=style_kw.get("clip_to"),
            layer=style_kw.get("layer"),
            stroke_linecap=style_kw.get("stroke_linecap"),
            stroke_dasharray=style_kw.get("stroke_dasharray"),
        )

    def _copy_single_region(
        self,
        source_document_id: str,
        target_document_id: str,
        region_id: str,
        *,
        new_region_id: str,
        offset_x: float,
        offset_y: float,
        skip_existing: bool,
    ) -> str | None:
        original = self.graph.get_region(region_id, source_document_id)
        if self.graph.has_region(new_region_id, target_document_id):
            if skip_existing:
                return None
            raise ValueError(f"'{new_region_id}' already exists in target")

        duplicate = original.model_copy(deep=True)
        duplicate.id = new_region_id
        duplicate.outline = [
            (round(point[0] + offset_x, 6), round(point[1] + offset_y, 6))
            for point in original.outline
        ]
        if duplicate.primitive:
            duplicate.primitive = _offset_primitive(duplicate.primitive, offset_x, offset_y)
        duplicate.metadata = dict(original.metadata) if original.metadata else {}
        self.graph._regions_for(target_document_id)[new_region_id] = duplicate
        return new_region_id


def _offset_primitive(primitive: dict[str, Any], offset_x: float, offset_y: float) -> dict[str, Any]:
    result = dict(primitive)
    primitive_type = result.get("type")
    if primitive_type in ("rect", "text", "image"):
        result["x"] = round(result.get("x", 0) + offset_x, 6)
        result["y"] = round(result.get("y", 0) + offset_y, 6)
    elif primitive_type == "ellipse":
        result["cx"] = round(result.get("cx", 0) + offset_x, 6)
        result["cy"] = round(result.get("cy", 0) + offset_y, 6)
    elif primitive_type == "line":
        result["x1"] = round(result.get("x1", 0) + offset_x, 6)
        result["y1"] = round(result.get("y1", 0) + offset_y, 6)
        result["x2"] = round(result.get("x2", 0) + offset_x, 6)
        result["y2"] = round(result.get("y2", 0) + offset_y, 6)
    return result
