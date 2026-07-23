"""Element edit/copy/delete service."""
from __future__ import annotations

import math
import uuid
from typing import Any

from avge_engine.effects.color import darken_hex
from avge_engine.effects import GradientDef
from avge_engine.geometry import CurveConstraints, chaikin, moving_average, normalize_outline, rdp
from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import (
    CopyElementResult,
    EditElementResult,
    EditElementsResult,
    InsertImageResult,
    RefineLineResult,
)
from avge_engine.services.base_element import BaseElementService
from avge_engine.services.image_import_service import (
    MAX_EMBED_BYTES,
    MAX_SVG_IMPORT_BYTES,
    bytes_to_data_uri,
    is_svg_href,
    read_href_bytes,
    svg_path_elements,
)
from avge_engine.document import ElementNode, Style


class ElementService(BaseElementService):
    """Application service for element lifecycle operations."""

    def delete_elements(self, *, ids: list[str], document_id: str | None = None) -> list[str]:
        doc_id = self.require_document_id(document_id)
        return self.documents.delete_elements(doc_id, ids)

    def add_bumps(
        self,
        *,
        element_id: str,
        document_id: str | None = None,
        segment_indices: list[int],
        extrusion_length: float = 0.05,
        extrusion_width: float = 0.03,
        angle_offset: float = 0.0,
        direction: str = "outward",
        shape: str = "rounded",
    ) -> dict[str, str]:
        doc_id = self.require_document_id(document_id)
        self.extrude_element_outline(
            element_id=element_id,
            document_id=doc_id,
            segment_indices=segment_indices,
            extrusion_length=extrusion_length,
            extrusion_width=extrusion_width,
            angle_offset=angle_offset,
            direction=direction,
            shape=shape,
        )
        return {"element_id": element_id}

    def extrude_element_outline(
        self,
        element_id: str,
        document_id: str | None = None,
        *,
        segment_indices: list[int] | None = None,
        extrusion_length: float = 0.03,
        extrusion_width: float = 0.02,
        angle_offset: float = 0.0,
        direction: str = "outward",
        shape: str = "round",
    ) -> bool:
        """Add protrusions or notches at selected outline segments."""
        doc_id = self.require_document_id(document_id)
        element = self.get_element(doc_id, element_id)
        points = list(element.outline)
        count = len(points)
        if count < 3:
            raise ValueError("Element must have at least 3 outline points")

        angle = math.radians(angle_offset)
        dir_sign = -1.0 if direction == "inward" else 1.0
        indices = segment_indices if segment_indices is not None else list(range(count))
        for index in sorted(indices, reverse=True):
            i = index % count
            j = (i + 1) % count
            mx = (points[i][0] + points[j][0]) / 2
            my = (points[i][1] + points[j][1]) / 2
            dx = points[j][0] - points[i][0]
            dy = points[j][1] - points[i][1]
            nx = -dy
            ny = dx
            length = math.sqrt(nx * nx + ny * ny)
            if length < 1e-10:
                continue
            nx /= length
            ny /= length
            ex = (nx * math.cos(angle) - ny * math.sin(angle)) * dir_sign
            ey = (nx * math.sin(angle) + ny * math.cos(angle)) * dir_sign
            if shape == "sharp":
                points.insert(j, (mx + ex * extrusion_length, my + ey * extrusion_length))
                continue
            half_width = extrusion_width / 2
            t1 = max(0.0, 0.5 - half_width)
            t2 = min(1.0, 0.5 + half_width)
            p1 = (points[i][0] + dx * t1, points[i][1] + dy * t1)
            p2 = (points[i][0] + dx * t2, points[i][1] + dy * t2)
            peak = (mx + ex * extrusion_length, my + ey * extrusion_length)
            points.insert(j, p2)
            points.insert(j, peak)
            points.insert(j, p1)

        element.outline = normalize_outline(points)
        element.version += 1
        self.commit(doc_id, action="extrude_element_outline", target=element_id)
        return True

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
    ) -> EditElementResult:
        """Modify one or more existing elements."""
        doc_id = self.require_document_id(document_id)
        resolved_stroke_width = self.stroke_width_to_norm(doc_id, stroke_width)
        target_ids = ids if ids else ([element_id] if element_id else [])
        if not target_ids:
            raise ValueError("Provide element_id or ids")

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
        for element_id_to_edit in target_ids:
            self.documents.update_element(
                doc_id,
                element_id_to_edit,
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
            self.commit(doc_id, action="edit_element", target=element_id_to_edit)
            affected.append(element_id_to_edit)
        return EditElementResult(affected=affected)

    def edit_elements(self, *, updates: list[dict], document_id: str | None = None) -> EditElementsResult:
        """Edit multiple elements with per-element content/style updates."""
        doc_id = self.require_document_id(document_id)
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
        return EditElementsResult(ok=ok, total=len(updates), lines=lines)

    def refine_line(
        self,
        *,
        element_id: str,
        document_id: str | None = None,
        mode: str = "stabilize",
        strength: float = 0.5,
        simplify_tolerance: float = 0.01,
        smoothness: float | None = None,
        preserve_corners: bool = True,
        iterations: int = 1,
    ) -> RefineLineResult:
        """Refine an existing line/outline without recreating the element."""
        doc_id = self.require_document_id(document_id)
        element = self.get_element(doc_id, element_id)
        points = [(float(x), float(y)) for x, y in element.outline]
        if len(points) < 2:
            raise ValueError("refine_line requires a element with at least 2 points")

        mode = mode.lower()
        strength = max(0.0, min(1.0, float(strength)))
        simplify_tolerance = max(0.0, min(0.25, float(simplify_tolerance)))
        iterations = max(1, min(6, int(iterations)))
        refined = points

        if mode == "straighten":
            refined = [points[0], points[-1]]
        elif mode == "simplify":
            refined = rdp(points, simplify_tolerance)
        elif mode == "smooth":
            refined = points
            for _ in range(iterations):
                refined = chaikin(refined, closed=element.constraints.closed, strength=strength, preserve_corners=preserve_corners)
        elif mode == "stabilize":
            refined = moving_average(points, strength=strength, preserve_corners=preserve_corners)
            if simplify_tolerance > 0:
                refined = rdp(refined, simplify_tolerance * max(0.25, strength))
        else:
            raise ValueError("mode must be one of: stabilize, smooth, simplify, straighten")

        if len(refined) < 2:
            refined = [points[0], points[-1]]
        refined_outline = normalize_outline(refined)
        element.outline = refined_outline
        element.constraints = CurveConstraints(
            smoothness=element.constraints.smoothness if smoothness is None else smoothness,
            closed=element.constraints.closed,
            corner_style=element.constraints.corner_style,
        )
        if element.primitive and element.primitive.get("type") == "line" and len(refined_outline) == 2:
            element.primitive = {
                **element.primitive,
                "x1": refined_outline[0][0],
                "y1": refined_outline[0][1],
                "x2": refined_outline[1][0],
                "y2": refined_outline[1][1],
            }
        element.metadata.update({
            "line_refinement": mode,
            "line_refinement_strength": strength,
        })
        element.version += 1
        self.commit(doc_id, action="refine_line", target=element_id)
        return RefineLineResult(
            element_id=element_id,
            before_points=len(points),
            after_points=len(refined_outline),
            mode=mode,
            smoothness=element.constraints.smoothness,
        )

    def copy_element(
        self,
        *,
        element_id: str | None = None,
        group_name: str | None = None,
        target_document_id: str | None = None,
        source_document_id: str | None = None,
        new_element_id: str | None = None,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        skip_existing: bool = False,
    ) -> CopyElementResult:
        """Copy one element or a group between documents."""
        source_id = self.require_document_id(source_document_id)
        if not target_document_id or not self.documents.has(target_document_id):
            raise ValueError(f"Target document '{target_document_id}' not found")

        if group_name is not None:
            members = self.documents.get_group(source_id, group_name)
            if not members:
                raise LookupError(f"Group '{group_name}' not found in source")
            copied: list[str] = []
            for member in members:
                mid = member["id"]
                try:
                    copied_id = self._copy_single_element(
                        source_id,
                        target_document_id,
                        mid,
                        new_element_id=f"{mid}_copy",
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
            self.commit(target_document_id, action="copy_element_group", target=str(copied))
            return CopyElementResult(
                source_document_id=source_id,
                target_document_id=target_document_id,
                copied_ids=copied,
                group_name=group_name,
            )

        if not element_id:
            raise ValueError("Provide either element_id or group_name")
        copied_id = self._copy_single_element(
            source_id,
            target_document_id,
            element_id,
            new_element_id=new_element_id or f"{element_id}_copy",
            offset_x=offset_x,
            offset_y=offset_y,
            skip_existing=skip_existing,
        )
        self.commit(target_document_id, action="copy_element", target=copied_id)
        return CopyElementResult(
            source_document_id=source_id,
            target_document_id=target_document_id,
            copied_ids=[copied_id] if copied_id else [],
            source_element_id=element_id,
        )

    def duplicate_element(
        self,
        element_id: str,
        new_element_id: str | None = None,
        document_id: str | None = None,
        *,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        z_index: int | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        smoothness: float | None = None,
        mirror_x: bool = False,
        mirror_y: bool = False,
        mirror_axis_x: float | None = None,
        blend_mode: str | None = None,
        layer: str | None = None,
        scale: float = 1.0,
        rotate: float = 0.0,
        shadow_mode: bool = False,
    ) -> ElementNode:
        """Duplicate an element with optional transform and style overrides."""
        doc_id = self.require_document_id(document_id)
        elements = self.elements_map(doc_id)
        original = elements.get(element_id)
        if original is None:
            raise ValueError(f"Element '{element_id}' not found")
        rid = new_element_id or f"{element_id}_copy"
        if rid in elements:
            raise ValueError(f"Element '{rid}' already exists")

        cx = sum(p[0] for p in original.outline) / len(original.outline)
        cy = sum(p[1] for p in original.outline) / len(original.outline)
        if mirror_x and mirror_axis_x is not None:
            offset_x = offset_x + 2 * (mirror_axis_x - cx)

        angle = math.radians(rotate)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        new_outline = []
        for x, y in original.outline:
            nx = (2 * cx - x) if mirror_x else x
            ny = (2 * cy - y) if mirror_y else y
            sx_val = (nx - cx) * scale + cx
            sy_val = (ny - cy) * scale + cy
            rx = (sx_val - cx) * cos_a - (sy_val - cy) * sin_a + cx
            ry = (sx_val - cx) * sin_a + (sy_val - cy) * cos_a + cy
            new_outline.append((rx + offset_x, ry + offset_y))

        if shadow_mode and fill is None:
            orig_fill = original.style.fill
            new_fill = darken_hex(orig_fill) if isinstance(orig_fill, str) and orig_fill.startswith("#") else orig_fill
        else:
            new_fill = fill if fill is not None else original.style.fill
        if shadow_mode and stroke is None:
            new_stroke = None
        elif stroke is not None:
            new_stroke = stroke
        else:
            new_stroke = original.style.stroke
        new_z = original.z_index - 1 if shadow_mode and z_index is None else z_index if z_index is not None else original.z_index + 1

        new_constraints = original.constraints
        if smoothness is not None:
            new_constraints = CurveConstraints(
                smoothness=smoothness,
                closed=original.constraints.closed,
                corner_style=original.constraints.corner_style,
            )
        new_primitive = _transformed_primitive(
            original.primitive,
            cx=cx,
            cy=cy,
            offset_x=offset_x,
            offset_y=offset_y,
            scale=scale,
            rotate=rotate,
            mirror_x=mirror_x,
            mirror_y=mirror_y,
        )
        dup = ElementNode(
            id=rid,
            layer=layer if layer is not None else original.layer,
            z_index=new_z,
            outline=new_outline,
            constraints=new_constraints,
            style=Style(
                fill=new_fill,
                stroke=new_stroke,
                stroke_width=stroke_width if stroke_width is not None else original.style.stroke_width,
                opacity=opacity if opacity is not None else original.style.opacity,
                blend_mode=blend_mode if blend_mode is not None else original.style.blend_mode,
            ),
            transform=original.transform,
            primitive=new_primitive,
        )
        self.add_element(doc_id, dup)
        self.commit(doc_id, action="duplicate_element", target=f"{element_id}->{rid}")
        return dup

    def insert_image(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        href: str,
        document_id: str | None = None,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        preserve_aspect_ratio: str = "xMidYMid meet",
        rotate: float = 0.0,
        clip_to: str | None = None,
        import_mode: str = "image",
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        smoothness: float = 0.0,
        samples_per_curve: int = 12,
        max_paths: int = 50,
    ) -> InsertImageResult:
        """Insert an image, embed image bytes, or import SVG paths as elements."""
        doc_id = self.require_document_id(document_id)
        resolved_href = href
        if import_mode in ("embed", "svg_paths"):
            limit = MAX_SVG_IMPORT_BYTES if import_mode == "svg_paths" else MAX_EMBED_BYTES
            raw, mime = read_href_bytes(href, max_bytes=limit)
            if import_mode == "embed":
                resolved_href = bytes_to_data_uri(raw, mime)
            else:
                if not is_svg_href(href, mime):
                    raise ValueError("import_mode='svg_paths' requires SVG input")
                return self._insert_svg_paths(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    href=href,
                    raw=raw,
                    document_id=doc_id,
                    element_id=element_id,
                    layer=layer,
                    z_index=z_index,
                    rotate=rotate,
                    clip_to=clip_to,
                    fill=fill,
                    stroke=stroke,
                    stroke_width=stroke_width,
                    smoothness=smoothness,
                    samples_per_curve=samples_per_curve,
                    max_paths=max_paths,
                )

        element = self.documents.create_element_node(
            doc_id,
            element_id=element_id or f"img_{uuid.uuid4().hex[:6]}",
            outline=[(x, y), (x + width, y), (x + width, y + height), (x, y + height)],
            layer=layer,
            z_index=z_index,
            clip_to=clip_to,
            constraints=CurveConstraints(smoothness=0.0, closed=True),
            style=Style(fill=None, stroke=None),
            primitive={
                "type": "image",
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "href": resolved_href,
                "preserve_aspect_ratio": preserve_aspect_ratio,
            },
        )
        if abs(rotate) > 0.001:
            object.__setattr__(element.transform, "rotate", rotate)
        self.commit(doc_id, action="create_image", target=element.id)
        return InsertImageResult(
            mode=import_mode,
            x=x,
            y=y,
            width=width,
            height=height,
            href_length=len(resolved_href),
            element_id=element.id,
        )

    def create_text(
        self,
        x: float,
        y: float,
        text: str,
        *,
        document_id: str | None = None,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | GradientDef | None = "#333333",
        font_size: float = 0.04,
        font_family: str = "sans-serif",
        text_anchor: str = "middle",
        font_weight: str = "normal",
        font_style: str = "normal",
        rotate: float = 0.0,
        letter_spacing: float = 0.0,
        opacity: float = 1.0,
        skew_x: float = 0.0,
        skew_y: float = 0.0,
    ) -> ElementNode:
        """Create a text label element."""
        doc_id = self.require_document_id(document_id)
        element = ElementNode(
            id=element_id or f"text_{uuid.uuid4().hex[:6]}",
            layer=layer,
            z_index=z_index,
            outline=[(x, y)],
            constraints=CurveConstraints(smoothness=0.0, closed=False),
            style=Style(fill=fill, stroke=None),
            primitive={
                "type": "text",
                "x": x,
                "y": y,
                "text": text,
                "font_size": font_size,
                "font_family": font_family,
                "text_anchor": text_anchor,
                "font_weight": font_weight,
                "font_style": font_style,
                "letter_spacing": letter_spacing if letter_spacing else None,
                "opacity": opacity if opacity < 1.0 else None,
                "skew_x": skew_x if skew_x else None,
                "skew_y": skew_y if skew_y else None,
            },
        )
        if abs(rotate) > 0.001:
            object.__setattr__(element.transform, "rotate", rotate)
        self.add_element(doc_id, element)
        element.version += 1
        self.commit(doc_id, action="create_text", target=element.id)
        return element

    def _outline_with_point_edit(
        self,
        doc_id: str,
        element_id: str,
        *,
        point_index: int,
        point_coords: list[float] | None,
        point_dx: float | None,
        point_dy: float | None,
    ) -> list[tuple[float, float]]:
        element = self.get_element(doc_id, element_id)
        points = list(element.outline)
        if point_index < 0 or point_index >= len(points):
            raise IndexError(f"point_index {point_index} out of range (0-{len(points)-1})")
        if point_coords is not None:
            points[point_index] = (float(point_coords[0]), float(point_coords[1]))
        elif point_dx is not None or point_dy is not None:
            off_x = point_dx if point_dx is not None else 0.0
            off_y = point_dy if point_dy is not None else 0.0
            points[point_index] = (points[point_index][0] + off_x, points[point_index][1] + off_y)
        return points

    def _insert_svg_paths(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        href: str,
        raw: bytes,
        document_id: str,
        element_id: str | None,
        layer: str,
        z_index: int,
        rotate: float,
        clip_to: str | None,
        fill: str | None,
        stroke: str | None,
        stroke_width: StrokeWidthInput,
        smoothness: float,
        samples_per_curve: int,
        max_paths: int,
    ) -> InsertImageResult:
        sw = self.stroke_width_to_norm(document_id, stroke_width) or 0.005
        path_defs = svg_path_elements(
            raw.decode("utf-8"),
            x=x,
            y=y,
            width=width,
            height=height,
            fill_override=fill,
            stroke_override=stroke,
            stroke_width=sw,
            samples_per_curve=samples_per_curve,
            max_paths=max_paths,
        )
        if not path_defs:
            raise ValueError("SVG contained no supported <path d=\"...\"> elements")

        created: list[str] = []
        prefix = element_id or "svg_path"
        for idx, path_def in enumerate(path_defs):
            element = self.documents.create_element_node(
                document_id,
                outline=path_def["outline"],
                element_id=f"{prefix}_{idx:02d}" if len(path_defs) > 1 else prefix,
                layer=layer,
                z_index=z_index + idx,
                clip_to=clip_to,
                constraints=CurveConstraints(smoothness=smoothness, closed=True),
                style=Style(
                    fill=path_def["fill"],
                    stroke=path_def["stroke"],
                    stroke_width=path_def["stroke_width"],
                ),
                metadata={"tool": "insert_image", "import_mode": "svg_paths", "source_href": href},
            )
            if abs(rotate) > 0.001:
                object.__setattr__(element.transform, "rotate", rotate)
            created.append(element.id)
        if len(created) > 1:
            from avge_engine.services.document_structure_service import DocumentStructureService

            DocumentStructureService(self.graph).group_elements(
                element_id or "svg_paths",
                created,
                document_id=document_id,
                replace=True,
            )
        self.commit(document_id, action="insert_svg_paths", target=",".join(created))
        return InsertImageResult(
            mode="svg_paths",
            x=x,
            y=y,
            width=width,
            height=height,
            created_ids=created,
        )

    def _apply_update_dict(self, doc_id: str, element_id: str, update: dict[str, Any]) -> None:
        element = self.get_element(doc_id, element_id)
        unsupported = [key for key in ("dx", "dy", "scale", "rotate") if key in update]
        if unsupported:
            joined = ", ".join(unsupported)
            raise ValueError(f"{joined} moved to transform_objects; edit_elements only edits content/style")

        outline = list(element.outline)
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
        self.documents.update_element(
            doc_id,
            element_id,
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
        self.commit(doc_id, action="edit_element", target=element_id)

    def _copy_single_element(
        self,
        source_document_id: str,
        target_document_id: str,
        element_id: str,
        *,
        new_element_id: str,
        offset_x: float,
        offset_y: float,
        skip_existing: bool,
    ) -> str | None:
        original = self.get_element(source_document_id, element_id)
        if self.element_exists(target_document_id, new_element_id):
            if skip_existing:
                return None
            raise ValueError(f"'{new_element_id}' already exists in target")

        duplicate = original.model_copy(deep=True)
        duplicate.id = new_element_id
        duplicate.outline = [
            (round(point[0] + offset_x, 6), round(point[1] + offset_y, 6))
            for point in original.outline
        ]
        if duplicate.primitive:
            duplicate.primitive = _offset_primitive(duplicate.primitive, offset_x, offset_y)
        duplicate.metadata = dict(original.metadata) if original.metadata else {}
        self.add_element(target_document_id, duplicate)
        return new_element_id


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


def _transformed_primitive(
    primitive: dict[str, Any] | None,
    *,
    cx: float,
    cy: float,
    offset_x: float,
    offset_y: float,
    scale: float,
    rotate: float,
    mirror_x: bool,
    mirror_y: bool,
) -> dict[str, Any] | None:
    if not primitive:
        return None
    result = dict(primitive)
    simple_transform = abs(scale - 1) <= 0.001 and abs(rotate) <= 0.001
    if simple_transform and (mirror_x or mirror_y):
        if result.get("type") == "ellipse":
            if mirror_x:
                result["cx"] = 2 * cx - result["cx"] + offset_x
            else:
                result["cx"] += offset_x
            if mirror_y:
                result["cy"] = 2 * cy - result["cy"] + offset_y
            else:
                result["cy"] += offset_y
            return result
        if result.get("type") in ("text", "image"):
            if mirror_x:
                result["x"] = 2 * cx - result["x"] + offset_x
            else:
                result["x"] += offset_x
            if mirror_y:
                result["y"] = 2 * cy - result["y"] + offset_y
            else:
                result["y"] += offset_y
            return result
        if result.get("type") == "rect":
            if mirror_x:
                result["x"] = 2 * cx - (result["x"] + result["width"]) + offset_x
            else:
                result["x"] += offset_x
            if mirror_y:
                result["y"] = 2 * cy - (result["y"] + result["height"]) + offset_y
            else:
                result["y"] += offset_y
            return result
    if not mirror_x and not mirror_y and simple_transform:
        return _offset_primitive(result, offset_x, offset_y)
    return None
