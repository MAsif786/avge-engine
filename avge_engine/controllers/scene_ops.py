"""Scene operations controller — boolean_operation, transform_objects, edit_group, etc."""
from __future__ import annotations

import random
from typing import Literal

PIVOT_MODES = Literal["center", "base", "fixed"]

from avge_engine.services.engine import StrokeWidthInput, get_graph, resolve_doc, stroke_width_to_norm


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _lerp_point(a: list[float] | tuple[float, float], b: list[float] | tuple[float, float], t: float) -> list[float]:
    return [float(a[0]) + (float(b[0]) - float(a[0])) * t, float(a[1]) + (float(b[1]) - float(a[1])) * t]


def _quad_point(quad: list[list[float]], u: float, v: float) -> list[float]:
    top = _lerp_point(quad[0], quad[1], u)
    bottom = _lerp_point(quad[3], quad[2], u)
    return _lerp_point(top, bottom, v)


def _cell_quad(
    quad: list[list[float]],
    u0: float,
    v0: float,
    u1: float,
    v1: float,
    margin_u: float,
    margin_v: float,
) -> list[list[float]]:
    du = max(0.0, u1 - u0)
    dv = max(0.0, v1 - v0)
    uu0 = u0 + du * margin_u
    uu1 = u1 - du * margin_u
    vv0 = v0 + dv * margin_v
    vv1 = v1 - dv * margin_v
    return [
        _quad_point(quad, uu0, vv0),
        _quad_point(quad, uu1, vv0),
        _quad_point(quad, uu1, vv1),
        _quad_point(quad, uu0, vv1),
    ]


def _clip_line_to_bounds(
    p1: list[float],
    p2: list[float],
    bounds: tuple[float, float, float, float],
) -> list[list[float]] | None:
    """Clip an infinite line through p1/p2 to an axis-aligned bounds rectangle."""
    x0, y0, x1, y1 = bounds
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None

    hits: list[tuple[float, list[float]]] = []
    if abs(dx) > 1e-9:
        for x in (x0, x1):
            t = (x - p1[0]) / dx
            y = p1[1] + dy * t
            if y0 - 1e-9 <= y <= y1 + 1e-9:
                hits.append((t, [x, y]))
    if abs(dy) > 1e-9:
        for y in (y0, y1):
            t = (y - p1[1]) / dy
            x = p1[0] + dx * t
            if x0 - 1e-9 <= x <= x1 + 1e-9:
                hits.append((t, [x, y]))

    unique: list[tuple[float, list[float]]] = []
    for t, pt in sorted(hits, key=lambda item: item[0]):
        if not any(abs(pt[0] - u[1][0]) < 1e-6 and abs(pt[1] - u[1][1]) < 1e-6 for u in unique):
            unique.append((t, pt))
    if len(unique) < 2:
        return None
    return [unique[0][1], unique[-1][1]]


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
            layer: Layer name — transforms all regions in that layer.
                💡 transform_objects(layer='sky', dy=0.02) shifts whole skyline.
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
        elif layer is not None:
            all_regions = scene._regions_for(doc_id)
            ids = [rid for rid, r in all_regions.items() if r.layer == layer]
            if not ids:
                return f"Error: No regions found in layer '{layer}'"
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
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        if len(vanishing_points) != 2:
            return "Error: vanishing_points must contain exactly two [x,y] points"
        vp_l = [float(vanishing_points[0][0]), float(vanishing_points[0][1])]
        vp_r = [float(vanishing_points[1][0]), float(vanishing_points[1][1])]
        x0, y0, x1, y1 = [float(v) for v in (bounds or [0.0, 0.0, 1.0, 1.0])]
        if x1 <= x0 or y1 <= y0:
            return "Error: bounds must be [x0,y0,x1,y1] with positive size"

        stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.001

        subpaths: list[list[list[float]]] = []
        vertical_count = max(2, int(verticals))
        horizontal_count = max(2, int(horizontals))
        for i in range(vertical_count):
            x = x0 + (x1 - x0) * (i / (vertical_count - 1))
            subpaths.append([[x, y0], [x, y1]])
        for i in range(horizontal_count):
            y = y0 + (y1 - y0) * (i / (horizontal_count - 1))
            left_line = _clip_line_to_bounds(vp_l, [x1, y], (x0, y0, x1, y1))
            right_line = _clip_line_to_bounds(vp_r, [x0, y], (x0, y0, x1, y1))
            if left_line:
                subpaths.append(left_line)
            if right_line:
                subpaths.append(right_line)

        rid = region_id or "perspective_grid"
        try:
            grid = scene.create_compound_path(
                subpaths=subpaths,
                document_id=doc_id,
                region_id=rid,
                layer=layer,
                z_index=z_index,
                fill=None,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=max(0.0, min(1.0, opacity)),
                smoothness=0.0,
                closed=False,
            )
            ids = [grid.id]
            if include_horizon:
                horizon = scene.create_line(
                    points=[[x0, horizon_y], [x1, horizon_y]],
                    document_id=doc_id,
                    region_id=f"{rid}_horizon",
                    layer=layer,
                    z_index=z_index,
                    stroke=stroke,
                    stroke_width=stroke_width,
                    opacity=max(0.0, min(1.0, opacity * 1.25)),
                    smoothness=0.0,
                )
                ids.append(horizon.id)
            return (
                f"Perspective grid created: {', '.join(ids)} "
                f"(vp_left={vp_l}, vp_right={vp_r}, horizon_y={horizon_y})"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

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
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        if len(target_quad) != 4:
            return "Error: target_quad must contain exactly four [x,y] points"
        if rows < 1 or columns < 1:
            return "Error: rows and columns must be >= 1"

        quad = [[float(p[0]), float(p[1])] for p in target_quad]
        stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.001

        prefix = region_id or "facade"
        rng = random.Random(seed)
        created: list[str] = []
        try:
            if create_base:
                base = scene.project_quad(
                    quad,
                    document_id=doc_id,
                    region_id=prefix,
                    layer=layer,
                    z_index=z_index,
                    fill=facade_fill,
                    stroke=facade_stroke,
                    stroke_width=stroke_width,
                    opacity=opacity,
                    metadata={"tool": "create_facade_grid", "part": "facade"},
                )
                created.append(base.id)

            for row in range(rows):
                for col in range(columns):
                    cell_noise = (rng.random() - 0.5) * max(0.0, variation)
                    mu = _clamp01(margin_u + cell_noise)
                    mv = _clamp01(margin_v - cell_noise * 0.5)
                    win_quad = _cell_quad(
                        quad,
                        col / columns,
                        row / rows,
                        (col + 1) / columns,
                        (row + 1) / rows,
                        mu,
                        mv,
                    )
                    lit = rng.random() < _clamp01(lit_ratio)
                    rid = f"{prefix}_w{row:02d}_{col:02d}"
                    win = scene.project_quad(
                        win_quad,
                        document_id=doc_id,
                        region_id=rid,
                        layer=layer,
                        z_index=z_index + 1,
                        fill=lit_fill if lit else window_fill,
                        stroke=window_stroke,
                        stroke_width=stroke_width,
                        opacity=opacity,
                        metadata={
                            "tool": "create_facade_grid",
                            "part": "window",
                            "facade": prefix,
                            "row": row,
                            "column": col,
                            "lit": lit,
                        },
                    )
                    created.append(win.id)
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

        return (
            f"Facade grid created: {prefix} with {rows * columns} window(s), "
            f"lit_ratio={lit_ratio:.2f}, regions={len(created)}"
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
        "  single — one copy with offset/mirror/scale. Params: region_id, dx, dy, mirror_x, mirror_axis_x, scale\n"
        "  linear — N copies in a row. Params: region_id, count, dx, dy, spacing_falloff, scale_falloff\n"
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
        mirror_axis_x: float | None = None,
        mirror_axis_y: float | None = None,
        scale: float = 1.0,
        rotate: float = 0.0,
        shadow_mode: bool = False,
        new_prefix: str | None = None,
        variations: dict | None = None,
        jitter: dict | None = None,
        z_index: int | None = None,
        spacing_falloff: float = 1.0,
        scale_falloff: float = 1.0,
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
        description="Add directional shading to a region. "
        "mode='two_tone' creates highlight + shadow copies; mode='gradient' "
        "applies a soft gradient fill across the existing region for architecture.",
    )
    def add_shading(
        region_id: str,
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
            region_id: Region to shade.
            light_direction: Angle in degrees (0=right, 90=top).
            document_id: Document UUID.
            intensity: 0.0–1.0 contrast strength.
            mode: "two_tone" for highlight/shadow copies, "gradient" for
                continuous plane shading on the existing region.
            highlight_color: Optional explicit highlight stop color.
            mid_color: Optional explicit middle stop color.
            shadow_color: Optional explicit shadow stop color.
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
        highlight = highlight_color or apply_hsl_offset(cur_fill, l_offset=intensity * 25, s_offset=-10)
        middle = mid_color or cur_fill
        shadow = shadow_color or apply_hsl_offset(cur_fill, l_offset=-intensity * 30, s_offset=15)
        if mode == "gradient":
            grad = {
                "type": "linear",
                "angle": light_direction,
                "stops": [
                    {"offset": 0.0, "color": highlight},
                    {"offset": 0.52, "color": middle},
                    {"offset": 1.0, "color": shadow},
                ],
            }
            # Normalize angle the same way restyle does.
            grad_angle = grad.pop("angle")
            grad["x1"] = round(0.5 - 0.5 * math.cos(angle), 2)
            grad["y1"] = round(0.5 - 0.5 * math.sin(angle), 2)
            grad["x2"] = round(0.5 + 0.5 * math.cos(angle), 2)
            grad["y2"] = round(0.5 + 0.5 * math.sin(angle), 2)
            scene.edit_region(region_id=region_id, document_id=doc_id, fill=grad)
            return f"Gradient shading applied to '{region_id}', light={grad_angle:.0f}deg"
        if mode != "two_tone":
            return "Error: mode must be 'two_tone' or 'gradient'"
        import uuid as _uuid, time as _time
        _seq = int(_time.time() * 1000) % 100000
        h_dup = scene.duplicate_region(
            region_id, document_id=doc_id,
            new_region_id=f"{region_id}_highlight_{_seq}",
            offset_x=-dx, offset_y=-dy,
            fill=highlight, stroke=None,
            z_index=r.z_index + 1,
        )
        s_dup = scene.duplicate_region(
            region_id, document_id=doc_id,
            new_region_id=f"{region_id}_shadow_{_seq}",
            offset_x=dx, offset_y=dy,
            fill=shadow, stroke=None,
            z_index=r.z_index - 1,
        )
        return f"Shading added: highlight='{h_dup.id}' shadow='{s_dup.id}', light={light_direction:.0f}deg"

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
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        if len(target_quad) != 4:
            return "Error: target_quad must contain exactly four points"
        count = max(1, min(100, int(count)))
        stroke_width = stroke_width_to_norm(doc_id, stroke_width)
        prefix = region_id or "surface_stripe"
        start = _clamp01(start)
        end = _clamp01(end)
        if end <= start:
            return "Error: end must be greater than start"
        if gap is None:
            gap = max(0.0, (end - start - stripe_width * count) / max(1, count - 1))

        pos = start
        created: list[str] = []
        try:
            for i in range(count):
                w = max(0.001, stripe_width * (spacing_falloff ** i if spacing_falloff < 1.0 else 1.0))
                p0 = pos
                p1 = min(end, pos + w)
                if p1 <= p0:
                    break
                if orientation == "u":
                    quad = [
                        _quad_point(target_quad, p0, 0.0),
                        _quad_point(target_quad, p1, 0.0),
                        _quad_point(target_quad, p1, 1.0),
                        _quad_point(target_quad, p0, 1.0),
                    ]
                else:
                    quad = [
                        _quad_point(target_quad, 0.0, p0),
                        _quad_point(target_quad, 1.0, p0),
                        _quad_point(target_quad, 1.0, p1),
                        _quad_point(target_quad, 0.0, p1),
                    ]
                r = scene.project_quad(
                    quad,
                    document_id=doc_id,
                    region_id=f"{prefix}_{i:02d}",
                    layer=layer,
                    z_index=z_index + i,
                    fill=fill,
                    stroke=stroke,
                    stroke_width=stroke_width,
                    opacity=opacity,
                    metadata={"tool": "create_surface_stripes", "stripe_index": i},
                )
                created.append(r.id)
                pos = p1 + gap * (spacing_falloff ** i)
                if pos >= end:
                    break
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"
        return f"Surface stripes created: {len(created)} stripe(s), ids={', '.join(created[:5])}{'...' if len(created) > 5 else ''}"

    @mcp.tool(
        name="add_depth_shadow",
        description="Create a soft offset shadow from a region outline. "
        "Use to ground objects quickly without manually drawing shadow blobs. "
        "direction is degrees (0=right, 90=down); distance is normalized canvas units; "
        "softness is blur radius in pixels.",
    )
    def add_depth_shadow(
        region_id: str,
        document_id: str | None = None,
        direction: float = 45.0,
        distance: float = 0.03,
        softness: float = 4.0,
        opacity: float = 0.22,
        color: str = "#000000",
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        z_offset: int = -1,
        new_region_id: str | None = None,
    ) -> str:
        """Create a blurred, low-opacity shadow derived from a region.

        Args:
            region_id: Source region.
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
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
            shadow = scene.add_depth_shadow(
                region_id,
                document_id=doc_id,
                new_region_id=new_region_id,
                direction=direction,
                distance=max(0.0, min(1.0, distance)),
                softness=max(0.0, min(64.0, softness)),
                opacity=max(0.0, min(1.0, opacity)),
                color=color,
                scale=max(0.01, min(10.0, scale)),
                sx=sx,
                sy=sy,
                z_offset=z_offset,
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"
        return (
            f"Depth shadow added: id='{shadow.id}', source='{region_id}', "
            f"direction={direction:g}, distance={distance:g}, softness={softness:g}"
        )

    @mcp.tool(
        name="cast_shadow",
        description="Create a soft shadow from one region clipped onto another region. "
        "Use for objects casting onto floors, walls, tables, platforms, or panels.",
    )
    def cast_shadow(
        from_region_id: str,
        onto_region_id: str,
        document_id: str | None = None,
        direction: float = 45.0,
        distance: float = 0.04,
        softness: float = 5.0,
        opacity: float = 0.20,
        color: str = "#000000",
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        z_offset: int = 1,
        new_region_id: str | None = None,
    ) -> str:
        """Create a clipped cast shadow from one region onto another."""
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
            onto = scene.get_region(onto_region_id, doc_id)
            shadow = scene.add_depth_shadow(
                from_region_id,
                document_id=doc_id,
                new_region_id=new_region_id,
                direction=direction,
                distance=max(0.0, min(1.0, distance)),
                softness=max(0.0, min(64.0, softness)),
                opacity=max(0.0, min(1.0, opacity)),
                color=color,
                scale=max(0.01, min(10.0, scale)),
                sx=sx,
                sy=sy,
                z_offset=0,
                clip_to=onto_region_id,
                layer=onto.layer,
            )
            shadow.z_index = onto.z_index + z_offset
            scene.get_document(doc_id).version += 1
            scene._persist(doc_id)
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"
        return (
            f"Cast shadow added: id='{shadow.id}', from='{from_region_id}', "
            f"onto='{onto_region_id}', clipped=true"
        )

    # Individual z-ordering: use edit_region(region_id, z_index=N)
    # Layer z-ordering: use shift_layer_z
