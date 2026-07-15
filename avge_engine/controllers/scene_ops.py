"""Scene operations controller — boolean_operation, transform_objects, edit_group, etc."""
from __future__ import annotations

from typing import Literal

PIVOT_MODES = Literal["center", "base", "fixed"]

from avge_engine.services.engine import get_graph, resolve_doc


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
        stroke_width: float | None = None,
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
            stroke_width: Stroke width for the result region.
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
        "💡 For multi-part objects, use group_name to transform all members.",
    )
    def transform_objects(
        ids: list[str] | None = None,
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
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> str:
        """Move, scale, rotate, mirror, or align existing regions.

        When ``group_name`` is set, resolves the group's members as IDs.
        When ``mirror_x`` or ``mirror_y`` is True, the outline is flipped
        around the center point (group center in group_mode).

        Args:
            ids: Region IDs to transform.
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
        """
        scene = get_graph()

        # ── Align mode ──
        if mode == "align":
            from avge_engine.geometry import compute_bounds
            try:
                doc_id = resolve_doc(document_id)
            except RuntimeError:
                return "Error: No active document"
            if not ids:
                return "Error: No region IDs provided"
            bounds_list = []
            for rid in ids:
                try:
                    r = scene.get_region(rid, doc_id)
                    b = compute_bounds(r.outline)
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
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        if group_name is not None:
            members = scene.get_group(group_name, doc_id)
            if not members:
                return f"Error: Group '{group_name}' not found"
            ids = [m["id"] for m in members]
        elif not ids:
            return "Error: No region IDs provided"

        try:
            affected = scene.transform_objects(
                ids=ids,
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
            from avge_engine.geometry import compute_bounds
            r = scene.get_region(affected[0], doc_id)
            b = compute_bounds(r.outline)
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
        "  single — one copy with offset/mirror/scale. Params: region_id, dx, dy, mirror_x, scale\n"
        "  linear — N copies in a row. Params: region_id, count, dx, dy\n"
        "  grid — N×M grid. Params: region_id, columns, rows, spacing_x, spacing_y\n"
        "  radial — circular array. Params: region_id, count, center_x, center_y, radius\n"
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
        scale: float = 1.0,
        rotate: float = 0.0,
        shadow_mode: bool = False,
        new_prefix: str | None = None,
        variations: dict | None = None,
        z_index: int | None = None,
    ) -> str:
        """Make copies of a region or group.

        Args:
            pattern: "single", "linear", "grid", "radial", or "group".
            region_id: Source region (required for single/linear/grid/radial).
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
            scale: Uniform scale.
            rotate: Rotation degrees.
            shadow_mode: Auto-style as shadow (darkened, no stroke, z behind).
            new_prefix: ID prefix for copies.
            variations: Per-copy property overrides (single/linear only).
            z_index: Explicit z-index for copies.
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

        # ── Single/Linear/Grid/Radial — require region_id ──
        if not region_id:
            return "Error: region_id required for pattern '{pattern}'"
        try:
            orig = scene.get_region(region_id, doc_id)
        except ValueError:
            return f"Error: Region '{region_id}' not found"

        ox = min(p[0] for p in orig.outline)
        oy = min(p[1] for p in orig.outline)
        ow = max(p[0] for p in orig.outline) - ox
        oh = max(p[1] for p in orig.outline) - oy

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
                    shadow_mode=shadow_mode, z_index=resolved_z,
                )
                created.append(dup.id)
            except (ValueError, RuntimeError) as e:
                return f"Error: {e}"

        elif pattern == "linear":
            for i in range(count):
                new_id = f"{new_prefix or region_id}_copy_{i}"
                try:
                    dup = scene.duplicate_region(
                        region_id=region_id, document_id=doc_id,
                        new_region_id=new_id,
                        offset_x=dx * (i + 1), offset_y=dy * (i + 1),
                        scale=scale, rotate=rotate,
                        mirror_x=mirror_x, mirror_y=mirror_y,
                        shadow_mode=shadow_mode, z_index=resolved_z,
                    )
                    created.append(dup.id)
                except (ValueError, RuntimeError) as e:
                    return f"Error at copy {i}: {e}"

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
            return f"Error: Unknown pattern '{pattern}'. Valid: single, linear, grid, radial, group"

        return f"Duplicated '{region_id}' ({pattern}): {len(created)} copy(ies), ids: {', '.join(created[:5])}{'...' if len(created) > 5 else ''}"

    @mcp.tool(
        name="add_shading",
        description="Derive directional highlight + core shadow for a region. "
        "Creates two copies offset perpendicular to the light direction, "
        "auto-colored via HSL lightness offset.",
    )
    def add_shading(
        region_id: str,
        light_direction: float = 135,
        document_id: str | None = None,
        intensity: float = 0.5,
    ) -> str:
        """Add directional shading to a region.

        Args:
            region_id: Region to shade.
            light_direction: Angle in degrees (0=right, 90=top).
            document_id: Document UUID.
            intensity: 0.0–1.0 contrast strength.
        """
        from avge_engine.effects.color import apply_hsl_offset
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        try:
            r = scene.get_region(region_id, doc_id)
        except ValueError:
            return f"Error: Region '{region_id}' not found"
        import math
        angle = math.radians(light_direction)
        offset = intensity * 0.015
        dx = math.cos(angle) * offset
        dy = math.sin(angle) * offset
        cur_fill = r.style.fill
        if not isinstance(cur_fill, str) or not cur_fill.startswith("#"):
            return "Error: add_shading requires a hex fill color"
        highlight = apply_hsl_offset(cur_fill, l_offset=intensity * 25, s_offset=-10)
        shadow = apply_hsl_offset(cur_fill, l_offset=-intensity * 30, s_offset=15)
        h_dup = scene.duplicate_region(
            region_id, document_id=doc_id,
            offset_x=-dx, offset_y=-dy,
            fill=highlight, stroke=None,
            z_index=r.z_index + 1,
        )
        s_dup = scene.duplicate_region(
            region_id, document_id=doc_id,
            offset_x=dx, offset_y=dy,
            fill=shadow, stroke=None,
            z_index=r.z_index - 1,
        )
        return f"Shading added: highlight='{h_dup.id}' shadow='{s_dup.id}', light={light_direction:.0f}deg"

    # Individual z-ordering: use edit_region(region_id, z_index=N)
    # Layer z-ordering: use shift_layer_z
