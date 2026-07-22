"""Scene operations controller — boolean_operation, transform_objects, edit_group, etc."""
from __future__ import annotations

import random
from typing import Literal

PIVOT_MODES = Literal["center", "base", "fixed"]
BACKGROUND_ASSET_MODES = Literal[
    "facade_detail",
    "tree_cluster",
    "cloud_bank",
    "water_ripples",
    "rock_cluster",
    "grass_patch",
]
COMIC_LAYOUT_MODES = Literal["grid", "feature_top", "feature_left", "vertical_stack", "horizontal_strip"]
READING_DIRECTIONS = Literal["ltr", "rtl", "ttb"]
WARP_MODES = Literal["bend", "bulge", "pinch", "wave", "handle_shift"]

from avge_engine.services.engine import StrokeWidthInput, get_graph, resolve_doc, stroke_width_to_norm
from avge_engine.services.scene_construction_service import SceneConstructionService
from avge_engine.services.selector_service import select_region_ids, selector_from_legacy
from avge_engine.services.shadow_service import ShadowService


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def create_tools(mcp):
    """Register scene operations tools on the given FastMCP instance."""

    @mcp.tool(
        name="boolean_operation",
        description="Perform boolean geometry on regions using shapely/GEOS. "
        "Operations: union, intersect, subtract, xor. "
        "Use for cutouts (windows, mug handle hole) and compound shapes "
        "without hand-tracing the result.",
    )
    def boolean_operation(
        operation: Literal["union", "intersect", "subtract", "xor"],
        region_ids: list[str],
        new_region_id: str | None = None,
        document_id: str | None = None,
        keep_originals: bool = False,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = None,
        simplify_tolerance: float | None = None,
    ) -> str:
        """Perform a boolean operation on two or more regions.

        Args:
            operation: "union", "intersect", "subtract", or "xor".
            region_ids: IDs of at least 2 regions to combine.
            new_region_id: Optional ID for the result region (auto-generated if omitted).
            document_id: Document UUID (omit to use active document).
            keep_originals: If True, keep input regions (default False — they are deleted).
            fill: Fill color for the result region.
            stroke: Stroke color for the result region.
            stroke_width: Stroke width in canvas pixels for the result region.
            opacity: Opacity for the result region.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        if len(region_ids) < 2:
            return "Error: Need at least 2 region IDs for boolean operation"

        valid_ops = ("union", "intersect", "subtract", "xor", "difference", "sym_diff")
        if operation not in valid_ops:
            return f"Error: Invalid operation '{operation}'. Valid: union, intersect, subtract, xor"

        stroke_width = stroke_width_to_norm(doc_id, stroke_width)

        try:
            result = scene.boolean_operation(
                operation=operation,
                region_ids=region_ids,
                new_region_id=new_region_id,
                document_id=doc_id,
                keep_originals=keep_originals,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
            )
            if simplify_tolerance is not None and result:
                try:
                    from shapely.geometry import Polygon
                    poly = Polygon(result.outline)
                    simplified = poly.simplify(simplify_tolerance, preserve_topology=True)
                    new_pts = [(round(x, 6), round(y, 6)) for x, y in simplified.exterior.coords[:-1]]
                    if len(new_pts) >= 3:
                        result.outline = new_pts
                except Exception:
                    pass
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

        delete_note = ""
        if not keep_originals:
            delete_note = f" (input regions {', '.join(region_ids)} removed)"
        return (
            f"Boolean {operation} → region '{result.id}' "
            f"({len(result.outline)} boundary points){delete_note}"
        )

    @mcp.tool(
        name="transform_objects",
        description="Move, scale, rotate, mirror, or align existing regions. "
        "Use to reposition/resize objects after creation, or set mode='align' "
        "to align/distribute regions. "
        "💡 For multi-part objects, use group_name to transform all members. "
        "Or layer='sky' to transform everything in a layer without listing IDs.",
    )
    def transform_objects(
        ids: list[str] | None = None,
        selector: dict[str, object] | None = None,
        document_id: str | None = None,
        mode: str = "transform",
        alignment: str | None = None,
        dx: float = 0.0,
        dy: float = 0.0,
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        rotate: float = 0.0,
        group_mode: bool = False,
        pivot_x: float | None = None,
        pivot_y: float | None = None,
        pivot_mode: PIVOT_MODES | None = None,
        z_index: int | None = None,
        group_name: str | None = None,
        layer: str | None = None,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> str:
        """Move, scale, rotate, mirror, or align existing regions.

        Prefer ``selector`` for targeting. Legacy ``ids``, ``group_name``,
        and ``layer`` are converted into the same selector path.
        When ``mirror_x`` or ``mirror_y`` is True, the outline is flipped
        around the center point (group center in group_mode).

        Args:
            selector: Shared selector. Keys: ids, group_name, layer, fill,
                tags, bounds, z_min, z_max, has_stroke.
            ids: Legacy region IDs to transform.
            document_id: Document UUID (omit to use active document).
            mode: "transform" (default) or "align". In align mode,
                ignores dx/dy/scale/rotate and applies ``alignment`` instead.
            alignment: Only used when mode="align". One of: top, bottom,
                left, right, center_h, center_v, distribute_h, distribute_v.
            dx: X translation in normalized units (positive = right).
            dy: Y translation in normalized units (positive = down).
            scale: Uniform scale factor (overridden by sx/sy when set).
            sx: Non-uniform X scale (e.g. 0.7 to squash horizontally).
            sy: Non-uniform Y scale (e.g. 0.8 to shorten vertically).
            rotate: Rotation in degrees (positive = clockwise).
            group_mode: Use collective center.
            pivot_x, pivot_y: Fixed rotation/scale origin —
                tilts a flower from its stem base.
            mirror_x: Mirror horizontally (flip around center).
            mirror_y: Mirror vertically (flip around center).
            layer: Layer name — transforms all regions in that layer.
                💡 transform_objects(layer='sky', dy=0.02) shifts whole skyline.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        resolved_selector = selector or selector_from_legacy(ids=ids, group_name=group_name, layer=layer)
        target_ids = select_region_ids(scene, doc_id, resolved_selector)

        # ── Align mode ──
        if mode == "align":
            if not target_ids:
                return "Error: No region IDs provided"
            bounds_list = []
            for rid in target_ids:
                try:
                    r = scene.get_region(rid, doc_id)
                    b = r.bounds
                    if b:
                        bounds_list.append({"id": rid, "bounds": b})
                except ValueError:
                    continue
            if len(bounds_list) < 2:
                return "Error: Need at least 2 valid regions"
            a = alignment or "center_h"
            if a == "top":
                t = min(b["bounds"]["y"] for b in bounds_list)
                for b in bounds_list:
                    d = t - b["bounds"]["y"]
                    if abs(d) > 0.0001: scene.transform_objects([b["id"]], document_id=doc_id, dy=d)
            elif a == "bottom":
                t = max(b["bounds"]["y"] + b["bounds"]["h"] for b in bounds_list)
                for b in bounds_list:
                    d = t - (b["bounds"]["y"] + b["bounds"]["h"])
                    if abs(d) > 0.0001: scene.transform_objects([b["id"]], document_id=doc_id, dy=d)
            elif a == "left":
                t = min(b["bounds"]["x"] for b in bounds_list)
                for b in bounds_list:
                    d = t - b["bounds"]["x"]
                    if abs(d) > 0.0001: scene.transform_objects([b["id"]], document_id=doc_id, dx=d)
            elif a == "right":
                t = max(b["bounds"]["x"] + b["bounds"]["w"] for b in bounds_list)
                for b in bounds_list:
                    d = t - (b["bounds"]["x"] + b["bounds"]["w"])
                    if abs(d) > 0.0001: scene.transform_objects([b["id"]], document_id=doc_id, dx=d)
            elif a == "center_h":
                avg = sum(b["bounds"]["x"] + b["bounds"]["w"]/2 for b in bounds_list) / len(bounds_list)
                for b in bounds_list:
                    d = avg - (b["bounds"]["x"] + b["bounds"]["w"]/2)
                    if abs(d) > 0.0001: scene.transform_objects([b["id"]], document_id=doc_id, dx=d)
            elif a == "center_v":
                avg = sum(b["bounds"]["y"] + b["bounds"]["h"]/2 for b in bounds_list) / len(bounds_list)
                for b in bounds_list:
                    d = avg - (b["bounds"]["y"] + b["bounds"]["h"]/2)
                    if abs(d) > 0.0001: scene.transform_objects([b["id"]], document_id=doc_id, dy=d)
            elif a in ("distribute_h", "distribute_v"):
                horiz = a == "distribute_h"
                sb = sorted(bounds_list, key=lambda x: x["bounds"]["x" if horiz else "y"])
                dim = "w" if horiz else "h"
                pos = "x" if horiz else "y"
                total = sum(b["bounds"][dim] for b in sb)
                first = sb[0]["bounds"][pos]
                last = sb[-1]["bounds"][pos] + sb[-1]["bounds"][dim]
                gap = (last - first - total) / (len(sb) - 1)
                cursor = sb[0]["bounds"][pos] + sb[0]["bounds"][dim] + gap
                for b in sb[1:-1]:
                    d = cursor - b["bounds"][pos]
                    if abs(d) > 0.0001:
                        kw = {"dx": d} if horiz else {"dy": d}
                        scene.transform_objects([b["id"]], document_id=doc_id, **kw)
                    cursor += b["bounds"][dim] + gap
            else:
                return f"Error: Unknown alignment '{a}'"
            return f"Aligned {len(bounds_list)} region(s): '{a}'"

        # ── Transform mode ──
        if not target_ids:
            return "Error: No region IDs provided"

        try:
            affected = scene.transform_objects(
                ids=target_ids,
                document_id=doc_id,
                dx=dx,
                dy=dy,
                scale=scale,
                sx=sx,
                sy=sy,
                rotate=rotate,
                group_mode=group_mode,
                pivot_x=pivot_x,
                pivot_y=pivot_y,
                pivot_mode=pivot_mode,
                z_index=z_index,
                group_name=group_name,
                mirror_x=mirror_x,
                mirror_y=mirror_y,
            )
        except RuntimeError as e:
            return f"Error: {e}"

        parts = [f"dx={dx}", f"dy={dy}"]
        if sx is not None:
            parts.append(f"sx={sx}")
        if sy is not None:
            parts.append(f"sy={sy}")
        if rotate:
            parts.append(f"rotate={rotate}°")
        if mirror_x:
            parts.append("mirror_x")
        if mirror_y:
            parts.append("mirror_y")
        if group_mode:
            parts.append("group_mode")
        # Include new bounds for first affected region
        bounds_info = ""
        if affected:
            r = scene.get_region(affected[0], doc_id)
            b = r.bounds
            if b:
                bounds_info = (
                    f" [{affected[0]}] bounds: "
                    f"x={b['x']:.4f} y={b['y']:.4f} "
                    f"w={b['w']:.4f} h={b['h']:.4f}"
                )
        return (
            f"Transformed {len(affected)} region(s): {', '.join(affected)} "
            f"({', '.join(parts)}){bounds_info}"
            )

    @mcp.tool(
        name="warp_region",
        description="Apply non-affine vector outline deformation to one region. "
        "Modes: bend, bulge, pinch, wave, handle_shift. Use transform_objects for move/scale/rotate; "
        "use project_quad for rectangular perspective projection; use warp_region for organic or freeform deformation.",
    )
    def warp_region(
        region_id: str,
        mode: WARP_MODES = "bend",
        document_id: str | None = None,
        strength: float = 0.15,
        axis: Literal["x", "y"] = "x",
        center: list[float] | None = None,
        radius: float = 0.5,
        frequency: float = 1.0,
        phase: float = 0.0,
        handles: list[dict[str, float]] | None = None,
        falloff: float = 1.0,
        preserve_corners: bool = False,
        smoothness: float | None = None,
    ) -> str:
        """Warp a region outline in normalized coordinates."""
        import math

        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        try:
            region = scene.get_region(region_id, doc_id)
        except ValueError as exc:
            return f"Error: {exc}"
        if len(region.outline) < 2:
            return "Error: warp_region requires a region with at least 2 points"
        bounds = region.bounds
        if not bounds or bounds["w"] <= 0 or bounds["h"] <= 0:
            return "Error: Cannot warp degenerate region"

        strength = max(-2.0, min(2.0, float(strength)))
        falloff = max(0.05, min(8.0, float(falloff)))
        radius = max(0.001, min(4.0, float(radius)))
        cx = float(center[0]) if center and len(center) >= 2 else bounds["x"] + bounds["w"] / 2
        cy = float(center[1]) if center and len(center) >= 2 else bounds["y"] + bounds["h"] / 2
        corner_indices = {0, len(region.outline) - 1}
        if len(region.outline) == 4:
            corner_indices = {0, 1, 2, 3}

        def normalized(x: float, y: float) -> tuple[float, float]:
            return (
                (x - bounds["x"]) / max(bounds["w"], 0.001),
                (y - bounds["y"]) / max(bounds["h"], 0.001),
            )

        def radial_weight(x: float, y: float) -> float:
            dist = math.hypot(x - cx, y - cy)
            return max(0.0, 1.0 - dist / radius) ** falloff

        new_outline: list[tuple[float, float]] = []
        for idx, (x, y) in enumerate(region.outline):
            if preserve_corners and idx in corner_indices:
                new_outline.append((x, y))
                continue
            u, v = normalized(x, y)
            nx, ny = float(x), float(y)
            if mode == "bend":
                bend = (u - 0.5) ** 2 * strength
                if axis == "x":
                    ny += bend
                else:
                    nx += bend
            elif mode == "wave":
                wave = math.sin(((u if axis == "x" else v) * frequency + phase) * math.tau) * strength
                if axis == "x":
                    ny += wave
                else:
                    nx += wave
            elif mode in ("bulge", "pinch"):
                weight = radial_weight(x, y)
                sign = 1.0 if mode == "bulge" else -1.0
                nx += (x - cx) * strength * sign * weight
                ny += (y - cy) * strength * sign * weight
            elif mode == "handle_shift":
                if not handles:
                    return "Error: handles required for mode 'handle_shift'"
                total_dx = 0.0
                total_dy = 0.0
                total_w = 0.0
                for handle in handles:
                    hx = float(handle.get("x", cx))
                    hy = float(handle.get("y", cy))
                    hw = max(0.001, float(handle.get("radius", radius)))
                    weight = max(0.0, 1.0 - math.hypot(x - hx, y - hy) / hw) ** falloff
                    total_dx += float(handle.get("dx", 0.0)) * weight
                    total_dy += float(handle.get("dy", 0.0)) * weight
                    total_w += weight
                if total_w > 0:
                    nx += total_dx
                    ny += total_dy
            else:
                return f"Error: Unknown warp mode '{mode}'"
            new_outline.append((round(nx, 6), round(ny, 6)))

        region.outline = new_outline
        region.primitive = None
        if smoothness is not None:
            region.constraints.smoothness = max(0.0, min(1.0, float(smoothness)))
        region.metadata.update({
            "tool": "warp_region",
            "warp_mode": mode,
            "warp_strength": strength,
            "warp_axis": axis,
        })
        region.version += 1
        scene.get_document(doc_id).version += 1
        scene._auto_checkpoint(doc_id, "warp_region", region_id)
        scene._persist(doc_id)
        return f"Warped region '{region_id}': mode={mode}, points={len(new_outline)}"

    @mcp.tool(
        name="project_quad",
        description="Create or perspective-warp a rectangular/panel region into a target quadrilateral. "
        "Use for realistic tables, windows, floor tiles, wall panels, screens, and signs. "
        "target_quad order is top-left, top-right, bottom-right, bottom-left. "
        "Pass source_region_id to warp an existing region; omit it to create a projected panel.",
    )
    def project_quad(
        target_quad: list[list[float]],
        document_id: str | None = None,
        region_id: str | None = None,
        source_region_id: str | None = None,
        replace_source: bool = False,
        columns: int = 1,
        rows: int = 1,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = 1.0,
        blend_mode: str | None = None,
        smoothness: float = 0.0,
        group_name: str | None = None,
        inherit_style: bool = False,
    ) -> str:
        """Create or warp a region through a unit-square homography.

        Args:
            target_quad: Four normalized points in order: top-left, top-right,
                bottom-right, bottom-left.
            source_region_id: Existing region to warp. If omitted, creates a
                projected rectangle/panel using target_quad.
            replace_source: If True with source_region_id, updates the source
                region in place. Otherwise creates a new projected copy.
            columns, rows: Optional edge subdivisions for newly-created panels,
                useful when later adding seams or tile grids.
            inherit_style: When warping a source region, copy its style unless
                explicit style values are supplied.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        if len(target_quad) != 4:
            return "Error: target_quad must contain exactly four [x,y] points"

        if source_region_id and inherit_style:
            fill = None
            stroke = None
            stroke_width = None
            opacity = None
            blend_mode = None
        else:
            stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.005

        try:
            region = scene.project_quad(
                target_quad=[(float(p[0]), float(p[1])) for p in target_quad],
                document_id=doc_id,
                region_id=region_id,
                source_region_id=source_region_id,
                replace_source=replace_source,
                columns=columns,
                rows=rows,
                layer=layer,
                z_index=z_index,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                blend_mode=blend_mode,
                smoothness=smoothness,
                metadata={"projection": "quad"},
            )
            if group_name:
                scene.add_to_group(group_name, [region.id], doc_id)
        except (ValueError, RuntimeError, TypeError) as e:
            return f"Error: {e}"

        action = "Warped" if source_region_id else "Projected"
        return f"{action} quad region: id={region.id}, points={len(region.outline)}"

    @mcp.tool(
        name="create_perspective_grid",
        description="Create two-point perspective construction guides from shared vanishing points. "
        "Use before project_quad/create_facade_grid so building edges, signs, rails, and street objects "
        "converge to the same off-canvas vanishing points. Emits editable compound-path guide regions.",
    )
    def create_perspective_grid(
        vanishing_points: list[list[float]],
        horizon_y: float = 0.5,
        document_id: str | None = None,
        region_id: str | None = None,
        verticals: int = 9,
        horizontals: int = 9,
        bounds: list[float] | None = None,
        include_horizon: bool = True,
        layer: str = "guides",
        z_index: int = -100,
        stroke: str = "#55C7FF",
        stroke_width: StrokeWidthInput = None,
        opacity: float = 0.35,
    ) -> str:
        """Create two-point perspective guide lines.

        Args:
            vanishing_points: Two [x,y] points. They may be off-canvas.
            horizon_y: Normalized Y coordinate of the horizon line.
            verticals: Number of vertical guide lines across bounds.
            horizontals: Number of guide samples on each side.
            bounds: Optional [x0,y0,x1,y1] construction area, default canvas.
            include_horizon: Also create a horizon guide line.
            stroke_width: Pixel stroke width.
        """
        try:
            result = SceneConstructionService().create_perspective_grid(
                vanishing_points=vanishing_points,
                horizon_y=horizon_y,
                document_id=document_id,
                region_id=region_id,
                verticals=verticals,
                horizontals=horizontals,
                bounds=bounds,
                include_horizon=include_horizon,
                layer=layer,
                z_index=z_index,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
            )
        except RuntimeError:
            return "Error: No active document — call create_document first"
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"
        return (
            f"Perspective grid created: {', '.join(result.ids)} "
            f"(vp_left={result.vp_left}, vp_right={result.vp_right}, horizon_y={result.horizon_y})"
        )

    @mcp.tool(
        name="create_facade_grid",
        description="Create a perspective-aware building facade with repeated window quads. "
        "Supports lit_ratio, deterministic seed, and subtle per-window inset variation so night-city "
        "facades read as buildings instead of flat sign slabs.",
    )
    def create_facade_grid(
        target_quad: list[list[float]],
        rows: int,
        columns: int,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "architecture",
        z_index: int = 0,
        facade_fill: str = "#2C3542",
        facade_stroke: str = "#0A1018",
        window_fill: str = "#182536",
        lit_fill: str = "#FFE8A3",
        window_stroke: str | None = "#A9C8D6",
        stroke_width: StrokeWidthInput = None,
        opacity: float = 1.0,
        lit_ratio: float = 0.22,
        margin_u: float = 0.18,
        margin_v: float = 0.18,
        variation: float = 0.08,
        seed: int = 1,
        create_base: bool = True,
    ) -> str:
        """Create a facade panel plus individually editable window regions.

        Args:
            target_quad: Four facade corners, top-left/top-right/bottom-right/bottom-left.
            rows, columns: Window grid dimensions.
            lit_ratio: Fraction of windows using lit_fill.
            variation: Deterministic inset variation per window.
            stroke_width: Pixel stroke width.
        """
        try:
            result = SceneConstructionService().create_facade_grid(
                target_quad=target_quad,
                rows=rows,
                columns=columns,
                document_id=document_id,
                region_id=region_id,
                layer=layer,
                z_index=z_index,
                facade_fill=facade_fill,
                facade_stroke=facade_stroke,
                window_fill=window_fill,
                lit_fill=lit_fill,
                window_stroke=window_stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                lit_ratio=lit_ratio,
                margin_u=margin_u,
                margin_v=margin_v,
                variation=variation,
                seed=seed,
                create_base=create_base,
            )
        except RuntimeError:
            return "Error: No active document — call create_document first"
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

        return (
            f"Facade grid created: {result.prefix} with {result.windows} window(s), "
            f"lit_ratio={result.lit_ratio:.2f}, regions={result.region_count}"
        )

    @mcp.tool(
        name="edit_group",
        description="Unified group operation tool. Use one action per call: "
        "'create' — create or replace a group with the given region IDs. "
        "'add' — add regions to an existing group (creates if missing). "
        "'remove' — remove specific regions from a group (doesn't delete regions). "
        "'delete' — delete an entire named group (regions are not deleted). "
        "💡 Use 'create' once to set up a group, then 'add' incrementally "
        "as you add more regions to the object.",
    )
    def edit_group(
        action: Literal["create", "add", "remove", "delete"],
        group_name: str,
        region_ids: list[str] | None = None,
        document_id: str | None = None,
    ) -> str:
        """Manage named region groups — create, add to, remove from, or delete.

        Args:
            action: "create" (set or replace), "add" (append), "remove" (remove members), "delete" (remove group).
            group_name: Name of the group.
            region_ids: Region IDs for create/add/remove actions (omit for delete).
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        if action == "delete":
            result = scene.ungroup_regions(group_name, doc_id)
            if result:
                return f"Group '{group_name}' deleted"
            return f"Error: Group '{group_name}' not found"

        if not region_ids:
            return "Error: No region IDs provided"

        if action == "create":
            members = scene.group_regions(
                group_name=group_name, region_ids=region_ids,
                document_id=doc_id, replace=True,
            )
        elif action == "add":
            members = scene.add_to_group(
                group_name=group_name, region_ids=region_ids,
                document_id=doc_id,
            )
        elif action == "remove":
            try:
                removed = scene.remove_from_group(
                    group_name=group_name, region_ids=region_ids,
                    document_id=doc_id,
                )
            except ValueError as e:
                return f"Error: {e}"
            return (
                f"Removed {len(removed)} region(s) from '{group_name}': "
                f"{', '.join(removed)}"
            )
        else:
            return f"Error: Unknown action '{action}'. Valid: create, add, remove, delete"

        return (
            f"Group '{group_name}': {len(members)} member(s) "
            f"({', '.join(members)})"
        )

    @mcp.tool(
        name="list_groups",
        description="List all named groups and their member counts.",
    )
    def list_groups(document_id: str | None = None) -> str:
        """List all region groups in the current document."""
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        groups = scene.list_groups(document_id=doc_id)
        if not groups:
            return "(no groups)"

        lines = [f"Groups ({len(groups)}):"]
        for g in groups:
            lines.append(f"  {g['name']}: {g['count']} region(s)")
        return "\n".join(lines)

    @mcp.tool(
        name="create_comic_panel_layout",
        description="Create grouped editable comic/page panel regions with gutters and reading-order metadata. "
        "Layouts: grid, feature_top, feature_left, vertical_stack, horizontal_strip. "
        "Use the generated panels as clip_to targets for artwork instead of manually aligning panel rectangles.",
    )
    def create_comic_panel_layout(
        layout: COMIC_LAYOUT_MODES = "grid",
        document_id: str | None = None,
        rows: int = 2,
        columns: int = 2,
        count: int | None = None,
        bounds: list[float] | None = None,
        margin: float = 0.04,
        gutter_x: float = 0.018,
        gutter_y: float = 0.018,
        reading_direction: READING_DIRECTIONS = "ltr",
        panel_prefix: str = "panel",
        group_name: str = "comic_panels",
        fill: str = "#FFFFFF",
        stroke: str = "#111111",
        stroke_width: StrokeWidthInput = None,
        layer: str = "panels",
        z_index: int = 0,
        clip_content: bool = True,
    ) -> str:
        """Create page/comic panels as editable regions."""
        from avge_engine.scene import CurveConstraints, Style

        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        rows = max(1, min(12, int(rows)))
        columns = max(1, min(12, int(columns)))
        gutter_x = max(0.0, min(0.25, float(gutter_x)))
        gutter_y = max(0.0, min(0.25, float(gutter_y)))
        if bounds is None:
            margin = max(0.0, min(0.45, float(margin)))
            x, y, w, h = margin, margin, 1 - 2 * margin, 1 - 2 * margin
        else:
            if len(bounds) != 4:
                return "Error: bounds must be [x, y, width, height]"
            x, y, w, h = [float(v) for v in bounds]
        if w <= 0 or h <= 0:
            return "Error: layout bounds width and height must be positive"

        def grid_rects(g_rows: int, g_cols: int, gx: float, gy: float, gw: float, gh: float):
            usable_w = gw - gutter_x * (g_cols - 1)
            usable_h = gh - gutter_y * (g_rows - 1)
            if usable_w <= 0 or usable_h <= 0:
                return []
            cw = usable_w / g_cols
            ch = usable_h / g_rows
            return [
                (gx + col * (cw + gutter_x), gy + row * (ch + gutter_y), cw, ch)
                for row in range(g_rows)
                for col in range(g_cols)
            ]

        panel_count = max(1, min(36, int(count))) if count is not None else None
        rects: list[tuple[float, float, float, float]]
        if layout == "grid":
            rects = grid_rects(rows, columns, x, y, w, h)
        elif layout == "vertical_stack":
            rects = grid_rects(panel_count or rows, 1, x, y, w, h)
        elif layout == "horizontal_strip":
            rects = grid_rects(1, panel_count or columns, x, y, w, h)
        elif layout == "feature_top":
            top_h = h * 0.46
            bottom_h = h - top_h - gutter_y
            rects = [(x, y, w, top_h)]
            rects.extend(grid_rects(1, max(1, panel_count - 1 if panel_count else columns), x, y + top_h + gutter_y, w, bottom_h))
        elif layout == "feature_left":
            left_w = w * 0.48
            right_w = w - left_w - gutter_x
            rects = [(x, y, left_w, h)]
            rects.extend(grid_rects(max(1, panel_count - 1 if panel_count else rows), 1, x + left_w + gutter_x, y, right_w, h))
        else:
            return f"Error: Unknown comic panel layout '{layout}'"
        if panel_count is not None:
            rects = rects[:panel_count]
        if not rects:
            return "Error: gutters are too large for layout bounds"

        if reading_direction == "rtl":
            reading_order = sorted(range(len(rects)), key=lambda i: (round(rects[i][1], 6), -rects[i][0]))
        elif reading_direction == "ttb":
            reading_order = sorted(range(len(rects)), key=lambda i: (round(rects[i][0], 6), rects[i][1]))
        else:
            reading_order = sorted(range(len(rects)), key=lambda i: (round(rects[i][1], 6), rects[i][0]))
        reading_index = {panel_idx: order for order, panel_idx in enumerate(reading_order)}

        sw = stroke_width_to_norm(doc_id, stroke_width) or stroke_width_to_norm(doc_id, 3) or 0.003
        created: list[str] = []
        for idx, (px, py, pw, ph) in enumerate(rects):
            rid = f"{panel_prefix}_{idx + 1:02d}"
            outline = [(px, py), (px + pw, py), (px + pw, py + ph), (px, py + ph)]
            region = scene.create_region(
                outline=outline,
                document_id=doc_id,
                region_id=rid,
                layer=layer,
                z_index=z_index + idx,
                constraints=CurveConstraints(smoothness=0.0, closed=True),
                style=Style(fill=fill, stroke=stroke, stroke_width=sw, opacity=1.0),
                metadata={
                    "tool": "create_comic_panel_layout",
                    "layout": layout,
                    "panel_index": idx,
                    "reading_index": reading_index[idx],
                    "reading_direction": reading_direction,
                    "clip_content": clip_content,
                },
            )
            created.append(region.id)

        scene.group_regions(group_name, created, doc_id, replace=True)
        scene._persist(doc_id)
        return f"Comic panel layout created: layout={layout}, panels={len(created)}, group={group_name}, ids={', '.join(created)}"

    @mcp.tool(
        name="add_bumps",
        description="Add small protrusions (bumps/knuckles/jagged edges) at specified "
        "segments of a region's outline. Good for knuckle bumps on fingers, "
        "serrated leaf edges, or spiky hair details. Extrudes outward from "
        "each segment midpoint. Process segments from last to first so "
        "indices remain valid.",
    )
    def add_bumps(
        region_id: str,
        document_id: str | None = None,
        segment_indices: list[int] | None = None,
        extrusion_length: float = 0.03,
        extrusion_width: float = 0.02,
        angle_offset: float = 0.0,
        direction: Literal["outward", "inward", "extrude"] = "outward",
        shape: Literal["round", "sharp", "bevel"] = "round",
    ) -> str:
        """Extrude segments of a region's outline, with direction and shape control.
        Use inward direction for notches/indentations, shape=sharp for knuckle ridges.

        Args:
            region_id: Region to modify.
            document_id: Document UUID.
            segment_indices: List of segment indices to extrude (e.g. [0, 2, 4]).
                Omit to extrude all segments evenly (rough edge effect).
            extrusion_length: How far the bump protrudes (normalized, default 0.03).
            extrusion_width: Base width of the bump (normalized, default 0.02).
            angle_offset: Angular offset in degrees to skew extrusion direction.
            direction: "outward" (bump protrudes out) or "inward" (notch/indentation).
            shape: "round" (smooth rounded bump) or "sharp" (pointy ridge).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        try:
            scene.extrude_region_outline(
                region_id=region_id,
                document_id=doc_id,
                segment_indices=segment_indices,
                extrusion_length=extrusion_length,
                extrusion_width=extrusion_width,
                angle_offset=angle_offset,
                direction=direction,
                shape=shape,
            )
            idx_str = str(segment_indices) if segment_indices else "all"
            return (
                f"Extruded region '{region_id}' at segments {idx_str} "
                f"(length={extrusion_length}, width={extrusion_width}, "
                f"direction={direction}, shape={shape})"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="duplicate",
        description="Make copies of a region or group according to a placement "
        "pattern. Consolidates duplicate_region, duplicate_grid, duplicate_radial, "
        "and duplicate_group into one configurable tool.\n"
        "Patterns:\n"
        "  single — one copy with offset/mirror/scale. Params: region_id, dx, dy, mirror_x, mirror_axis_x, scale\n"
        "  linear — N copies in a row. Params: region_id, count, dx, dy, spacing_falloff, scale_falloff\n"
        "  grid — N×M grid. Params: region_id, columns, rows, spacing_x, spacing_y\n"
        "  radial — circular array. Params: region_id, count, center_x, center_y, radius\n"
        "  scatter — random copies in bounds. Params: region_id, count, bounds, seed, scale\n"
        "  group — duplicate group with transforms. Params: group_name, dx, dy, scale, rotate",
    )
    def duplicate(
        pattern: str,
        region_id: str | None = None,
        group_name: str | None = None,
        document_id: str | None = None,
        count: int = 1,
        columns: int = 1,
        rows: int = 1,
        dx: float = 0.0,
        dy: float = 0.0,
        spacing_x: float = 0.02,
        spacing_y: float = 0.02,
        center_x: float = 0.5,
        center_y: float = 0.5,
        radius: float = 0.2,
        start_angle: float = 0.0,
        rotate_copies: bool = True,
        mirror_x: bool = False,
        mirror_y: bool = False,
        mirror_axis_x: float | None = None,
        mirror_axis_y: float | None = None,
        scale: float = 1.0,
        rotate: float = 0.0,
        shadow_mode: bool = False,
        new_prefix: str | None = None,
        variations: dict | None = None,
        jitter: dict | None = None,
        bounds: list[float] | None = None,
        seed: int = 0,
        z_index: int | None = None,
        spacing_falloff: float = 1.0,
        scale_falloff: float = 1.0,
    ) -> str:
        """Make copies of a region or group.

        Args:
            pattern: "single", "linear", "grid", "radial", "scatter", or "group".
            region_id: Source region (required for single/linear/grid/radial/scatter).
            group_name: Source group (required for group pattern).
            document_id: Document UUID.
            count: Number of copies (linear/radial).
            columns, rows: Grid dimensions (grid pattern).
            dx, dy: Translation offset for each copy (linear/single/group).
            spacing_x, spacing_y: Gap between copies (grid pattern).
            center_x, center_y: Center point (radial pattern).
            radius: Distance from center (radial pattern).
            start_angle: Starting angle degrees (radial pattern).
            rotate_copies: Rotate copies to face center (radial pattern).
            mirror_x, mirror_y: Mirror across axis.
            mirror_axis_x: Fixed X position for mirror axis (e.g. 0.5 = canvas center).
                Defaults to the region's own center if omitted.
            mirror_axis_y: Fixed Y position for mirror axis.
            scale: Uniform scale.
            rotate: Rotation degrees.
            shadow_mode: Auto-style as shadow (darkened, no stroke, z behind).
            new_prefix: ID prefix for copies.
            variations: Per-copy property overrides (single/linear only).
            jitter: Controlled randomness for organic feel.
                Keys: hue (max deg shift), size (max fraction), rotation (max deg),
                seed (int, for reproducibility).
                💡 jitter={'hue':5,'size':0.02,'rotation':3,'seed':42}
            bounds: Scatter placement rectangle [x, y, width, height] in normalized coordinates.
            seed: Scatter random seed.
            z_index: Explicit z-index for copies.
            spacing_falloff: Linear-only multiplier applied to each step's dx/dy
                so repeated objects recede toward a vanishing point.
            scale_falloff: Linear-only multiplier applied to each copy's scale.
        """
        import math
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        # ── Group pattern ──
        if pattern == "group":
            if not group_name:
                return "Error: group_name required for pattern 'group'"
            try:
                new_ids = scene.duplicate_group(
                    group_name=group_name, document_id=doc_id,
                    new_prefix=new_prefix, dx=dx, dy=dy,
                    scale=scale, rotate=rotate,
                    mirror_x=mirror_x, mirror_y=mirror_y,
                )
                if variations:
                    prefix = new_prefix or f"{group_name}_copy"
                    for orig_id, props in variations.items():
                        cid = f"{prefix}_{orig_id}"
                        if scene.has_region(cid, doc_id):
                            try:
                                scene.edit_region(region_id=cid, document_id=doc_id, **props)
                            except (ValueError, RuntimeError):
                                pass
                return f"Duplicated group '{group_name}' ({len(new_ids)} copies)"
            except (ValueError, RuntimeError) as e:
                return f"Error: {e}"

        # ── Single/Linear/Grid/Radial/Scatter — require region_id ──
        if not region_id:
            return f"Error: region_id required for pattern '{pattern}'"
        try:
            orig = scene.get_region(region_id, doc_id)
        except ValueError:
            return f"Error: Region '{region_id}' not found"

        ox = min(p[0] for p in orig.outline)
        oy = min(p[1] for p in orig.outline)
        ow = max(p[0] for p in orig.outline) - ox
        oh = max(p[1] for p in orig.outline) - oy
        ocx = ox + ow / 2
        ocy = oy + oh / 2

        created = []
        resolved_z = z_index

        if pattern == "single":
            new_id = new_prefix or f"{region_id}_copy"
            try:
                dup = scene.duplicate_region(
                    region_id=region_id, document_id=doc_id,
                    offset_x=dx, offset_y=dy,
                    scale=scale, rotate=rotate,
                    mirror_x=mirror_x, mirror_y=mirror_y,
                    mirror_axis_x=mirror_axis_x, mirror_axis_y=mirror_axis_y,
                    shadow_mode=shadow_mode, z_index=resolved_z,
                )
                created.append(dup.id)
            except (ValueError, RuntimeError) as e:
                return f"Error: {e}"

        elif pattern == "linear":
            cur_x = 0.0
            cur_y = 0.0
            step_scale = 1.0
            for i in range(count):
                cur_x += dx * step_scale
                cur_y += dy * step_scale
                copy_scale = scale * (scale_falloff ** i)
                new_id = f"{new_prefix or region_id}_copy_{i}"
                try:
                    dup = scene.duplicate_region(
                        region_id=region_id, document_id=doc_id,
                        new_region_id=new_id,
                        offset_x=cur_x, offset_y=cur_y,
                        scale=copy_scale, rotate=rotate,
                        mirror_x=mirror_x, mirror_y=mirror_y,
                        shadow_mode=shadow_mode, z_index=resolved_z,
                    )
                    created.append(dup.id)
                except (ValueError, RuntimeError) as e:
                    return f"Error at copy {i}: {e}"
                step_scale *= spacing_falloff

        elif pattern == "grid":
            for row in range(rows):
                for col in range(columns):
                    if row == 0 and col == 0:
                        continue
                    off_x = col * (ow + spacing_x)
                    off_y = row * (oh + spacing_y)
                    new_id = f"{new_prefix or region_id}_g{row}_{col}"
                    try:
                        dup = scene.duplicate_region(
                            region_id=region_id, document_id=doc_id,
                            new_region_id=new_id,
                            offset_x=off_x, offset_y=off_y,
                            z_index=resolved_z,
                        )
                        created.append(dup.id)
                    except (ValueError, RuntimeError) as e:
                        return f"Error at ({row},{col}): {e}"

        elif pattern == "scatter":
            if bounds is None or len(bounds) != 4:
                return "Error: bounds=[x,y,width,height] required for pattern 'scatter'"
            bx, by, bw, bh = [float(v) for v in bounds]
            if bw <= 0 or bh <= 0:
                return "Error: scatter bounds width and height must be positive"
            rng = random.Random(seed)
            for i in range(count):
                tx = bx + rng.random() * bw
                ty = by + rng.random() * bh
                new_id = f"{new_prefix or region_id}_scatter_{i}"
                try:
                    dup = scene.duplicate_region(
                        region_id=region_id, document_id=doc_id,
                        new_region_id=new_id,
                        offset_x=tx - ocx, offset_y=ty - ocy,
                        scale=scale, rotate=rotate,
                        mirror_x=mirror_x, mirror_y=mirror_y,
                        shadow_mode=shadow_mode, z_index=resolved_z,
                    )
                    created.append(dup.id)
                except (ValueError, RuntimeError) as e:
                    return f"Error at scatter copy {i}: {e}"

        elif pattern == "radial":
            for i in range(count):
                angle = math.radians(start_angle + i * (360.0 / count))
                tx = center_x + radius * math.cos(angle)
                ty = center_y + radius * math.sin(angle)
                off_x = tx - ox
                off_y = ty - oy
                rotation = math.degrees(angle) if rotate_copies else 0.0
                new_id = f"{new_prefix or region_id}_rad_{i}"
                try:
                    dup = scene.duplicate_region(
                        region_id=region_id, document_id=doc_id,
                        new_region_id=new_id,
                        offset_x=off_x, offset_y=off_y,
                        rotate=rotation, scale=scale,
                        z_index=resolved_z,
                    )
                    created.append(dup.id)
                except (ValueError, RuntimeError) as e:
                    return f"Error at copy {i}: {e}"

        else:
            return f"Error: Unknown pattern '{pattern}'. Valid: single, linear, grid, radial, scatter, group"

        # ── Apply controlled jitter to copies ──
        if jitter and created:
            import random as _r, math as _m
            _r.seed(jitter.get("seed", 0))
            h_max = float(jitter.get("hue", 0))
            s_max = float(jitter.get("size", 0))
            r_max = float(jitter.get("rotation", 0))
            for cid in created:
                try:
                    r = scene.get_region(cid, doc_id)
                    if r is None:
                        continue
                    kw = {}
                    if s_max or r_max:
                        scene.transform_objects([cid], document_id=doc_id,
                            scale=1.0 + _r.uniform(-s_max, s_max) if s_max else 1.0,
                            rotate=_r.uniform(-r_max, r_max) if r_max else 0.0,
                        )
                    if h_max and r.style.fill and isinstance(r.style.fill, str) and r.style.fill.startswith("#"):
                        from avge_engine.effects.color import apply_hsl_offset
                        scene.edit_region(region_id=cid, document_id=doc_id,
                            fill=apply_hsl_offset(r.style.fill, h_offset=_r.uniform(-h_max, h_max)),
                        )
                except (ValueError, RuntimeError):
                    pass

        return f"Duplicated '{region_id}' ({pattern}): {len(created)} copy(ies), ids: {', '.join(created[:5])}{'...' if len(created) > 5 else ''}"

    @mcp.tool(
        name="add_shading",
        description="Add directional shading to one region or a shared selector of regions. "
        "mode='two_tone' creates highlight + shadow copies; mode='gradient' "
        "applies a soft gradient fill across existing regions for architecture. "
        "Selector keys: ids, group_name, layer, fill, tags, bounds, z_min, z_max, has_stroke.",
    )
    def add_shading(
        region_id: str | None = None,
        selector: dict[str, object] | None = None,
        light_direction: float = 135,
        document_id: str | None = None,
        intensity: float = 0.5,
        mode: Literal["two_tone", "gradient"] = "two_tone",
        highlight_color: str | None = None,
        mid_color: str | None = None,
        shadow_color: str | None = None,
    ) -> str:
        """Add directional shading to a region.

        Args:
            region_id: Legacy single region to shade.
            selector: Shared selector. Keys: ids, group_name, layer, fill,
                tags, bounds, z_min, z_max, has_stroke.
            light_direction: Angle in degrees (0=right, 90=top).
            document_id: Document UUID.
            intensity: 0.0–1.0 contrast strength.
            mode: "two_tone" for highlight/shadow copies, "gradient" for
                continuous plane shading on the existing region.
            highlight_color: Optional explicit highlight stop color.
            mid_color: Optional explicit middle stop color.
            shadow_color: Optional explicit shadow stop color.
        """
        try:
            result = ShadowService().add_shading(
                region_id=region_id,
                selector=selector,
                light_direction=light_direction,
                document_id=document_id,
                intensity=intensity,
                mode=mode,
                highlight_color=highlight_color,
                mid_color=mid_color,
                shadow_color=shadow_color,
            )
        except RuntimeError:
            return "Error: No active document"
        except LookupError:
            return "Error: No matching regions found via selector"
        except ValueError as e:
            return f"Error: {e}"
        if result.mode == "gradient":
            return f"Gradient shading applied to {result.target_count} region(s), light={result.light_direction:.0f}deg"
        return (
            f"Shading added to {result.target_count} region(s), "
            f"overlays={result.overlay_count}, light={result.light_direction:.0f}deg"
        )

    @mcp.tool(
        name="generate_cloud",
        description="Create a soft irregular cloud from overlapping blurred puffs, "
        "with lighter top lobes and subtle shaded underside. Use instead of "
        "hard single ellipses for sky detail.",
    )
    def generate_cloud(
        cx: float,
        cy: float,
        width: float,
        height: float,
        document_id: str | None = None,
        region_id: str | None = None,
        puff_count: int = 7,
        puff_variance: float = 0.28,
        shade_direction: float = 135.0,
        blur: float = 3.0,
        opacity: float = 0.82,
        fill: str = "#F4FDFF",
        shade_fill: str = "#CFEAF5",
        layer: str = "sky",
        z_index: int = -70,
        seed: int = 1,
    ) -> str:
        """Create an editable cloud group from multiple soft puffs.

        Args:
            cx, cy: Cloud center in normalized coordinates.
            width, height: Overall cloud size in normalized units.
            puff_count: Number of overlapping lobes.
            puff_variance: Size/position irregularity from 0.0–1.0.
            shade_direction: Light direction in degrees; underside is offset opposite it.
            blur: Gaussian blur radius in pixels.
            opacity: Overall cloud opacity.
            fill: Main/lit cloud color.
            shade_fill: Underside shadow color.
        """
        import math
        from avge_engine.scene import CurveConstraints, Style

        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        if width <= 0 or height <= 0:
            return "Error: width and height must be positive"
        puff_count = max(2, min(32, int(puff_count)))
        rng = random.Random(seed)
        prefix = region_id or f"cloud_{abs(hash((cx, cy, width, height, seed))) & 0xFFFF:x}"
        angle = math.radians(shade_direction + 180.0)
        shade_dx = math.cos(angle) * width * 0.035
        shade_dy = abs(math.sin(angle)) * height * 0.12 + height * 0.08

        created: list[str] = []
        try:
            # Underpaint shadow puffs first so the lit lobes sit on top.
            for pass_name, color, pass_opacity, dy_extra, z in (
                ("shade", shade_fill, opacity * 0.42, shade_dy, z_index),
                ("puff", fill, opacity, 0.0, z_index + 1),
            ):
                for i in range(puff_count):
                    t = i / (puff_count - 1) if puff_count > 1 else 0.5
                    jitter_x = (rng.random() - 0.5) * width * puff_variance * 0.35
                    jitter_y = (rng.random() - 0.5) * height * puff_variance * 0.45
                    px = cx - width * 0.42 + width * 0.84 * t + jitter_x + (shade_dx if pass_name == "shade" else 0.0)
                    py = cy + math.sin(t * math.pi) * -height * 0.16 + jitter_y + dy_extra
                    rx = width / max(3.2, puff_count * 0.72) * (0.9 + rng.random() * puff_variance)
                    ry = height * (0.25 + rng.random() * 0.22)
                    outline = [(px - rx, py - ry), (px + rx, py - ry), (px + rx, py + ry), (px - rx, py + ry)]
                    r = scene.create_region(
                        outline=outline,
                        region_id=f"{prefix}_{pass_name}_{i:02d}",
                        document_id=doc_id,
                        layer=layer,
                        z_index=z,
                        constraints=CurveConstraints(smoothness=0.72, closed=True),
                        style=Style(fill=color, stroke=None, opacity=pass_opacity, blur=max(0.0, blur)),
                        metadata={"tool": "generate_cloud", "cloud": prefix, "part": pass_name},
                    )
                    created.append(r.id)
            # A broad low-opacity body fill ties the lobes together.
            body = scene.create_region(
                outline=[
                    (cx - width * 0.46, cy + height * 0.05),
                    (cx - width * 0.20, cy - height * 0.28),
                    (cx + width * 0.23, cy - height * 0.24),
                    (cx + width * 0.48, cy + height * 0.04),
                    (cx + width * 0.22, cy + height * 0.22),
                    (cx - width * 0.28, cy + height * 0.20),
                ],
                region_id=f"{prefix}_body",
                document_id=doc_id,
                layer=layer,
                z_index=z_index,
                constraints=CurveConstraints(smoothness=0.78, closed=True),
                style=Style(fill=fill, stroke=None, opacity=opacity * 0.38, blur=max(0.0, blur * 0.7)),
                metadata={"tool": "generate_cloud", "cloud": prefix, "part": "body"},
            )
            created.append(body.id)
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"
        return f"Cloud generated: {prefix}, puffs={puff_count}, regions={len(created)}"

    @mcp.tool(
        name="generate_background_asset",
        description="Generate reusable editable background details from one generic tool. "
        "Modes: facade_detail, tree_cluster, cloud_bank, water_ripples, rock_cluster, grass_patch. "
        "Use this for secondary environment density after perspective/massing is correct, instead of "
        "adding separate object-specific tools for every cloud, tree, rock, grass, pipe, sill, or ripple.",
    )
    def generate_background_asset(
        mode: BACKGROUND_ASSET_MODES,
        bounds: list[float],
        document_id: str | None = None,
        region_id: str | None = None,
        count: int = 12,
        density: float = 1.0,
        seed: int = 1,
        detail: list[str] | None = None,
        color: str | None = None,
        secondary_color: str | None = None,
        layer: str = "background_detail",
        z_index: int = 0,
        opacity: float = 1.0,
        clip_to: str | None = None,
    ) -> str:
        """Generate editable background asset clusters inside a bounds rectangle."""
        from avge_engine.scene import CurveConstraints, Style

        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        if len(bounds) != 4:
            return "Error: bounds must be [x, y, width, height]"
        x, y, w, h = [float(v) for v in bounds]
        if w <= 0 or h <= 0:
            return "Error: bounds width and height must be positive"

        rng = random.Random(seed)
        safe_count = max(1, min(400, int(count * max(0.1, density))))
        prefix = region_id or f"bg_{mode}_{seed}"
        created: list[str] = []

        def add_line(name: str, pts, stroke: str, sw: float, op: float, smooth: float = 0.0):
            r = scene.create_line(
                points=pts,
                document_id=doc_id,
                region_id=f"{prefix}_{name}_{len(created):03d}",
                layer=layer,
                z_index=z_index + len(created),
                stroke=stroke,
                stroke_width=stroke_width_to_norm(doc_id, sw) or 0.002,
                opacity=_clamp01(opacity * op),
                stroke_linecap="round",
                smoothness=smooth,
            )
            r.clip_to = clip_to
            r.metadata.update({"tool": "generate_background_asset", "mode": mode, "part": name})
            created.append(r.id)
            return r

        def add_region(name: str, outline, fill: str, stroke: str | None, sw: float, op: float, smooth: float = 0.2):
            r = scene.create_region(
                outline=outline,
                document_id=doc_id,
                region_id=f"{prefix}_{name}_{len(created):03d}",
                layer=layer,
                z_index=z_index + len(created),
                clip_to=clip_to,
                constraints=CurveConstraints(smoothness=smooth, closed=True),
                style=Style(
                    fill=fill,
                    stroke=stroke,
                    stroke_width=stroke_width_to_norm(doc_id, sw) or 0.001,
                    opacity=_clamp01(opacity * op),
                ),
                metadata={"tool": "generate_background_asset", "mode": mode, "part": name},
            )
            created.append(r.id)
            return r

        if mode == "facade_detail":
            enabled = set(detail or ["mullions", "sills", "pipes", "cornice"])
            stroke = color or "#39464D"
            accent = secondary_color or "#D8E2E5"
            if "mullions" in enabled:
                cols = max(2, min(18, safe_count // 2))
                for i in range(1, cols):
                    px = x + w * i / cols
                    add_line("mullion", [(px, y), (px, y + h)], stroke, 1.2, 0.55)
            if "sills" in enabled:
                rows = max(2, min(12, safe_count // 3))
                for i in range(1, rows + 1):
                    py = y + h * i / (rows + 1)
                    add_line("sill", [(x + 0.04 * w, py), (x + 0.96 * w, py)], accent, 1.4, 0.7)
            if "pipes" in enabled:
                for _ in range(max(1, min(4, safe_count // 8))):
                    px = x + w * rng.uniform(0.08, 0.92)
                    wobble = w * rng.uniform(-0.015, 0.015)
                    add_line("pipe", [(px, y), (px + wobble, y + h)], stroke, 2.0, 0.65, 0.35)
            if "cornice" in enabled:
                ch = h * 0.05
                add_region("cornice", [(x, y), (x + w, y), (x + w * 0.96, y + ch), (x + w * 0.04, y + ch)], accent, stroke, 1.0, 0.85)
        elif mode == "tree_cluster":
            trunk = secondary_color or "#5A3A25"
            leaf = color or "#3F7A43"
            for _ in range(safe_count):
                cx = x + rng.random() * w
                base = y + h * rng.uniform(0.72, 0.98)
                th = h * rng.uniform(0.18, 0.34)
                add_line("trunk", [(cx, base), (cx + rng.uniform(-0.01, 0.01) * w, base - th)], trunk, 2.0, 0.75, 0.15)
                for _ in range(rng.randint(2, 4)):
                    rx = w * rng.uniform(0.025, 0.055)
                    ry = h * rng.uniform(0.035, 0.075)
                    pcx = cx + rng.uniform(-0.04, 0.04) * w
                    pcy = base - th + rng.uniform(-0.035, 0.035) * h
                    add_region("leaf", [(pcx, pcy - ry), (pcx + rx, pcy), (pcx, pcy + ry), (pcx - rx, pcy)], leaf, None, 0.5, rng.uniform(0.65, 0.92), 0.75)
        elif mode == "cloud_bank":
            fill = color or "#FFFFFF"
            shadow = secondary_color or "#BFD4E2"
            for _ in range(safe_count):
                cx = x + rng.random() * w
                cy = y + h * rng.uniform(0.2, 0.78)
                rx = w * rng.uniform(0.04, 0.12)
                ry = h * rng.uniform(0.10, 0.26)
                add_region("cloud_shadow", [(cx - rx, cy), (cx, cy - ry * 0.7), (cx + rx, cy), (cx, cy + ry * 0.42)], shadow, None, 0.5, 0.24, 0.82)
                add_region("cloud_puff", [(cx - rx * 0.9, cy), (cx, cy - ry), (cx + rx * 0.9, cy), (cx, cy + ry * 0.55)], fill, None, 0.5, 0.55, 0.85)
        elif mode == "water_ripples":
            stroke = color or "#A8F7FF"
            accent = secondary_color or "#FFFFFF"
            for i in range(safe_count):
                py = y + rng.random() * h
                px = x + rng.random() * w
                length = w * rng.uniform(0.08, 0.32)
                wave = h * rng.uniform(0.008, 0.025)
                add_line("ripple", [(px, py), (px + length * 0.35, py - wave), (px + length, py + wave * 0.25)], stroke if i % 4 else accent, 1.3, rng.uniform(0.24, 0.62), 0.6)
        elif mode == "rock_cluster":
            fill = color or "#7E8079"
            stroke = secondary_color or "#4C504B"
            for _ in range(safe_count):
                cx = x + rng.random() * w
                cy = y + rng.random() * h
                rw = w * rng.uniform(0.015, 0.055)
                rh = h * rng.uniform(0.025, 0.08)
                add_region("rock", [(cx - rw, cy + rh * 0.2), (cx - rw * 0.3, cy - rh), (cx + rw * 0.75, cy - rh * 0.55), (cx + rw, cy + rh * 0.45), (cx, cy + rh)], fill, stroke, 0.8, rng.uniform(0.65, 0.95), 0.18)
        elif mode == "grass_patch":
            stroke = color or "#3F7F3F"
            accent = secondary_color or "#A8D26B"
            for i in range(safe_count):
                px = x + rng.random() * w
                base = y + h * rng.uniform(0.72, 1.0)
                blade = h * rng.uniform(0.08, 0.26)
                lean = w * rng.uniform(-0.025, 0.025)
                add_line("grass", [(px, base), (px + lean, base - blade)], stroke if i % 5 else accent, 1.1, rng.uniform(0.35, 0.85), 0.35)
        else:
            return f"Error: Unknown background asset mode '{mode}'"

        scene.group_regions(prefix, created, doc_id, replace=True)
        scene._persist(doc_id)
        return f"Background asset generated: mode={mode}, regions={len(created)}, group={prefix}, ids={', '.join(created[:6])}"

    @mcp.tool(
        name="create_surface_stripes",
        description="Create evenly spaced project_quad stripes on a road/floor surface. "
        "Use for crosswalks, lane markings, floor tiles, and plaza seams that "
        "must converge with the same surface perspective.",
    )
    def create_surface_stripes(
        target_quad: list[list[float]],
        count: int,
        document_id: str | None = None,
        region_id: str | None = None,
        orientation: Literal["u", "v"] = "u",
        start: float = 0.08,
        end: float = 0.92,
        stripe_width: float = 0.05,
        gap: float | None = None,
        spacing_falloff: float = 1.0,
        fill: str = "#F1F7F8",
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float = 0.95,
        layer: str = "road",
        z_index: int = 0,
    ) -> str:
        """Create a stripe set in normalized surface coordinates.

        Args:
            target_quad: Surface corners top-left, top-right, bottom-right, bottom-left.
            count: Number of stripes.
            orientation: "u" creates crosswise bands varying along U; "v" creates lengthwise bands.
            start, end: Surface-coordinate range for stripe placement.
            stripe_width: Stripe width in surface-coordinate units.
            gap: Optional initial gap; defaults to evenly filling the range.
            spacing_falloff: Multiplier applied to each next gap, for receding spacing.
        """
        try:
            result = SceneConstructionService().create_surface_stripes(
                target_quad=target_quad,
                count=count,
                document_id=document_id,
                region_id=region_id,
                orientation=orientation,
                start=start,
                end=end,
                stripe_width=stripe_width,
                gap=gap,
                spacing_falloff=spacing_falloff,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                layer=layer,
                z_index=z_index,
            )
        except RuntimeError:
            return "Error: No active document"
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"
        return (
            f"Surface stripes created: {len(result.ids)} stripe(s), "
            f"ids={', '.join(result.ids[:5])}{'...' if len(result.ids) > 5 else ''}"
        )

    @mcp.tool(
        name="create_shadow",
        description="Create a soft shadow from a region outline. "
        "Omit onto_region_id for a grounding/depth shadow, or pass onto_region_id "
        "to clip the shadow onto another region for a cast shadow. "
        "direction is degrees (0=right, 90=down); distance is normalized canvas units; "
        "softness is blur radius in pixels.",
    )
    def create_shadow(
        region_id: str,
        onto_region_id: str | None = None,
        document_id: str | None = None,
        direction: float = 45.0,
        distance: float = 0.03,
        softness: float = 4.0,
        opacity: float = 0.22,
        color: str = "#000000",
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        z_offset: int | None = None,
        new_region_id: str | None = None,
    ) -> str:
        """Create a blurred, low-opacity shadow derived from a region.

        Args:
            region_id: Source region.
            onto_region_id: Optional receiver region. When provided, the shadow
                is clipped to this region and layered relative to the receiver.
            document_id: Document UUID.
            direction: Offset angle in degrees. 0=right, 90=down.
            distance: Offset distance in normalized canvas units.
            softness: Gaussian blur radius in pixels.
            opacity: Shadow opacity.
            color: Shadow fill color.
            scale, sx, sy: Scale the shadow around the source center. Use
                ``sy=0.35`` for ground shadows.
            z_offset: Relative z-index from the source, usually negative.
            new_region_id: Optional explicit shadow ID.
        """
        try:
            result = ShadowService().create_shadow(
                region_id=region_id,
                onto_region_id=onto_region_id,
                document_id=document_id,
                direction=direction,
                distance=distance,
                softness=softness,
                opacity=opacity,
                color=color,
                scale=scale,
                sx=sx,
                sy=sy,
                z_offset=z_offset,
                new_region_id=new_region_id,
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"
        if result.clipped:
            return (
                f"Shadow created: id='{result.shadow.id}', source='{result.source_id}', "
                f"onto='{result.onto_region_id}', clipped=true, softness={result.softness:g}"
            )
        return (
            f"Shadow created: id='{result.shadow.id}', source='{result.source_id}', "
            f"direction={result.direction:g}, distance={result.distance:g}, softness={result.softness:g}"
        )

    # Individual z-ordering: use edit_region(region_id, z_index=N)
    # Layer z-ordering: use shift_layer_z
