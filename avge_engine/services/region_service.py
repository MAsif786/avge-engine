"""Region edit/copy/delete service."""
from __future__ import annotations

from typing import Any

from avge_engine.geometry import CurveConstraints, normalize_outline
from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import (
    CopyElementResult,
    EditRegionResult,
    EditRegionsResult,
    InsertImageResult,
    RefineLineResult,
)
from avge_engine.services.engine import get_graph, resolve_doc, stroke_width_to_norm
from avge_engine.services.image_import_service import (
    MAX_EMBED_BYTES,
    MAX_SVG_IMPORT_BYTES,
    bytes_to_data_uri,
    is_svg_href,
    read_href_bytes,
    svg_path_regions,
)
from avge_engine.scene import Style


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

    def refine_line(
        self,
        *,
        region_id: str,
        document_id: str | None = None,
        mode: str = "stabilize",
        strength: float = 0.5,
        simplify_tolerance: float = 0.01,
        smoothness: float | None = None,
        preserve_corners: bool = True,
        iterations: int = 1,
    ) -> RefineLineResult:
        """Refine an existing line/outline without recreating the region."""
        doc_id = resolve_doc(document_id)
        region = self.graph.get_region(region_id, doc_id)
        points = [(float(x), float(y)) for x, y in region.outline]
        if len(points) < 2:
            raise ValueError("refine_line requires a region with at least 2 points")

        mode = mode.lower()
        strength = max(0.0, min(1.0, float(strength)))
        simplify_tolerance = max(0.0, min(0.25, float(simplify_tolerance)))
        iterations = max(1, min(6, int(iterations)))
        refined = points

        if mode == "straighten":
            refined = [points[0], points[-1]]
        elif mode == "simplify":
            refined = _rdp(points, simplify_tolerance)
        elif mode == "smooth":
            refined = points
            for _ in range(iterations):
                refined = _chaikin(refined, closed=region.constraints.closed, strength=strength, preserve_corners=preserve_corners)
        elif mode == "stabilize":
            refined = _moving_average(points, strength=strength, preserve_corners=preserve_corners)
            if simplify_tolerance > 0:
                refined = _rdp(refined, simplify_tolerance * max(0.25, strength))
        else:
            raise ValueError("mode must be one of: stabilize, smooth, simplify, straighten")

        if len(refined) < 2:
            refined = [points[0], points[-1]]
        refined_outline = normalize_outline(refined)
        region.outline = refined_outline
        region.constraints = CurveConstraints(
            smoothness=region.constraints.smoothness if smoothness is None else smoothness,
            closed=region.constraints.closed,
            corner_style=region.constraints.corner_style,
        )
        if region.primitive and region.primitive.get("type") == "line" and len(refined_outline) == 2:
            region.primitive = {
                **region.primitive,
                "x1": refined_outline[0][0],
                "y1": refined_outline[0][1],
                "x2": refined_outline[1][0],
                "y2": refined_outline[1][1],
            }
        region.metadata.update({
            "line_refinement": mode,
            "line_refinement_strength": strength,
        })
        region.version += 1
        self.graph.get_document(doc_id).version += 1
        self.graph._auto_checkpoint(doc_id, "refine_line", region_id)
        self.graph._persist(doc_id)
        return RefineLineResult(
            region_id=region_id,
            before_points=len(points),
            after_points=len(refined_outline),
            mode=mode,
            smoothness=region.constraints.smoothness,
        )

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

    def insert_image(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        href: str,
        document_id: str | None = None,
        region_id: str | None = None,
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
        """Insert an image, embed image bytes, or import SVG paths as regions."""
        doc_id = resolve_doc(document_id)
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
                    region_id=region_id,
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

        region = self.graph.insert_image(
            x,
            y,
            width,
            height,
            resolved_href,
            document_id=doc_id,
            region_id=region_id,
            layer=layer,
            z_index=z_index,
            preserve_aspect_ratio=preserve_aspect_ratio,
            rotate=rotate,
            clip_to=clip_to,
        )
        return InsertImageResult(
            mode=import_mode,
            x=x,
            y=y,
            width=width,
            height=height,
            href_length=len(resolved_href),
            region_id=region.id,
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
        region_id: str | None,
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
        sw = stroke_width_to_norm(document_id, stroke_width) or 0.005
        path_defs = svg_path_regions(
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
        prefix = region_id or "svg_path"
        for idx, path_def in enumerate(path_defs):
            region = self.graph.create_region(
                outline=path_def["outline"],
                document_id=document_id,
                region_id=f"{prefix}_{idx:02d}" if len(path_defs) > 1 else prefix,
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
                object.__setattr__(region.transform, "rotate", rotate)
            created.append(region.id)
        if len(created) > 1:
            self.graph.group_regions(region_id or "svg_paths", created, document_id, replace=True)
        self.graph._persist(document_id)
        return InsertImageResult(
            mode="svg_paths",
            x=x,
            y=y,
            width=width,
            height=height,
            created_ids=created,
        )

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


def _moving_average(
    points: list[tuple[float, float]],
    *,
    strength: float,
    preserve_corners: bool,
) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    result = [points[0]]
    for i in range(1, len(points) - 1):
        prev_pt = points[i - 1]
        cur_pt = points[i]
        next_pt = points[i + 1]
        avg = ((prev_pt[0] + cur_pt[0] + next_pt[0]) / 3, (prev_pt[1] + cur_pt[1] + next_pt[1]) / 3)
        if preserve_corners and _turn_angle(prev_pt, cur_pt, next_pt) < 120:
            result.append(cur_pt)
        else:
            result.append(_lerp_point(cur_pt, avg, strength))
    result.append(points[-1])
    return [_round_point(p) for p in result]


def _chaikin(
    points: list[tuple[float, float]],
    *,
    closed: bool,
    strength: float,
    preserve_corners: bool,
) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    cut = 0.25 * strength
    result: list[tuple[float, float]] = []
    segment_count = len(points) if closed else len(points) - 1
    if not closed:
        result.append(points[0])
    for i in range(segment_count):
        p0 = points[i]
        p1 = points[(i + 1) % len(points)]
        prev_pt = points[i - 1]
        next_pt = points[(i + 2) % len(points)]
        if preserve_corners and _turn_angle(prev_pt, p0, p1) < 110:
            result.append(p0)
            continue
        q = _lerp_point(p0, p1, cut)
        r = _lerp_point(p0, p1, 1.0 - cut)
        result.extend([q, r])
    if not closed:
        result.append(points[-1])
    return [_round_point(p) for p in result]


def _rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) < 3 or epsilon <= 0:
        return points
    max_dist = 0.0
    index = 0
    start = points[0]
    end = points[-1]
    for i in range(1, len(points) - 1):
        dist = _point_line_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            index = i
    if max_dist > epsilon:
        left = _rdp(points[: index + 1], epsilon)
        right = _rdp(points[index:], epsilon)
        return left[:-1] + right
    return [start, end]


def _point_line_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    import math

    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def _turn_angle(
    prev_pt: tuple[float, float],
    point: tuple[float, float],
    next_pt: tuple[float, float],
) -> float:
    import math

    ax, ay = prev_pt[0] - point[0], prev_pt[1] - point[1]
    bx, by = next_pt[0] - point[0], next_pt[1] - point[1]
    amag = math.hypot(ax, ay)
    bmag = math.hypot(bx, by)
    if amag == 0 or bmag == 0:
        return 180.0
    cos_v = max(-1.0, min(1.0, (ax * bx + ay * by) / (amag * bmag)))
    return math.degrees(math.acos(cos_v))


def _lerp_point(
    a: tuple[float, float],
    b: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _round_point(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 6), round(point[1], 6))
