"""Scene operations controller — boolean_operation, transform_objects, manage_group, duplicate_group, etc."""
from __future__ import annotations

from typing import Literal, Required, TypedDict

PIVOT_MODES = Literal["center", "base", "fixed"]

from avge_engine.services.engine import get_graph, resolve_doc


class SubPartsDef(TypedDict, total=False):
    """Typed schema for create_composite_region sub_parts."""
    pattern: Required[Literal["radial_fan", "radial_ring"]]
    """Pattern type: radial_fan (fingers/petals from one edge) or radial_ring (spikes around center)."""
    count: int
    """Number of sub-parts to create (e.g. 5 for fingers)."""
    anchor: str
    """For radial_fan: edge anchor — \"top_edge\", \"bottom_edge\", \"left_edge\", \"right_edge\"."""
    length_range: list[float]
    """Min and max length as [min, max] in normalized units (e.g. [0.12, 0.2])."""
    width: float
    """Base width of each sub-part (normalized units)."""
    angle_spread: float
    """Total angular spread in degrees (e.g. 35 for fingers)."""
    length_variance: bool
    """If True, vary individual sub-part lengths within length_range."""
    taper: float
    """Taper ratio — 0.0 = uniform width, 1.0 = pointy tip."""
    edge_span: float
    """Fraction of the anchor edge to distribute across (0.0–1.0, default 1.0).
       1.0 = full edge width; 0.6 = inner 60% only."""


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
        description="Translate, scale (non-uniform), rotate existing regions. "
        "Use this to reposition or resize objects after creation — the only "
        "alternative is edit_region with manually re-derived coordinates for "
        "every point. "
        "💡 For multi-part objects (cup, book, character), first use "
        "group_regions to collect all parts, then pass the group member "
        "IDs with group_mode=True to resize/reposition as one unit.",
    )
    def transform_objects(
        ids: list[str] | None = None,
        document_id: str | None = None,
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
        """Move, scale, rotate, and/or mirror existing regions.

        When ``group_name`` is set, resolves the group's members as IDs.
        When ``mirror_x`` or ``mirror_y`` is True, the outline is flipped
        around the center point (group center in group_mode).

        Args:
            ids: Region IDs to transform.
            document_id: Document UUID (omit to use active document).
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
        return (
            f"Transformed {len(affected)} region(s): {', '.join(affected)} "
            f"({', '.join(parts)})"
        )

    @mcp.tool(
        name="manage_group",
        description="Unified group operation tool. Use one action per call: "
        "'create' — create or replace a group with the given region IDs. "
        "'add' — add regions to an existing group (creates if missing). "
        "'remove' — remove specific regions from a group (doesn't delete regions). "
        "'delete' — delete an entire named group (regions are not deleted). "
        "💡 Use 'create' once to set up a group, then 'add' incrementally "
        "as you add more regions to the object.",
    )
    def manage_group(
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
        name="duplicate_group",
        description="Duplicate all regions in a named group as a new group, "
        "with optional translation, scale, and rotation applied uniformly "
        "to every copy. The original group is unchanged. "
        "💡 Build one template group, then duplicate_group to create "
        "variations with different offsets/scales.",
    )
    def duplicate_group(
        group_name: str,
        document_id: str | None = None,
        new_prefix: str | None = None,
        dx: float = 0.0,
        dy: float = 0.0,
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        rotate: float = 0.0,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> str:
        """Duplicate a named group with transforms.

        💡 Build one side of a symmetrical object (arm, wing, half a face),
        then call duplicate_group with mirror_x=True to flip the copy
        — no need to author both sides manually.

        Args:
            group_name: Source group to duplicate.
            document_id: Document UUID.
            new_prefix: Prefix for new region IDs and group name.
            dx, dy: Translation.
            scale: Uniform scale.
            sx, sy: Non-uniform scale.
            rotate: Rotation in degrees.
            mirror_x: Mirror horizontally (flip around each region's center).
            mirror_y: Mirror vertically (flip around each region's center).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        try:
            new_ids = scene.duplicate_group(
                group_name=group_name, document_id=doc_id,
                new_prefix=new_prefix,
                dx=dx, dy=dy, scale=scale, sx=sx, sy=sy, rotate=rotate,
                mirror_x=mirror_x, mirror_y=mirror_y,
            )
            prefix = new_prefix or f"{group_name}_copy"
            return (
                f"Duplicated group '{group_name}' as '{prefix}' "
                f"({len(new_ids)} region(s))"
            )
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="extrude_region_outline",
        description="Add small protrusions (bumps/knuckles/jagged edges) at specified "
        "segments of a region's outline. Good for knuckle bumps on fingers, "
        "serrated leaf edges, or spiky hair details. Extrudes outward from "
        "each segment midpoint. Process segments from last to first so "
        "indices remain valid.",
    )
    def extrude_region_outline(
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
        name="create_composite_region",
        description="Create a base region with patterned sub-part protrusions "
        "(fingers, petals, spikes) in one call. Each sub-part is an independent "
        "region — editable, stylable, and groupable afterward. "
        "Supports patterns: radial_fan (fingers/petals fanning from one edge), "
        "radial_ring (spikes pointing radially outward from the shape center). "
        "💡 For a hand: use radial_fan on top_edge of a palm shape with "
        "count=5, angle_spread=35, length_range=[0.12,0.2], width=0.025, "
        "length_variance=true.",
    )
    def create_composite_region(
        outline: list[list[float]],
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        closed: bool = True,
        smoothness: float = 0.5,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        z_index: int = 0,
        sub_parts: SubPartsDef | None = None,
    ) -> str:
        """Create a composite region with base + patterned sub-parts.

        Args:
            outline: Base outline points (the palm/core shape).
            document_id: Document UUID.
            region_id: Optional ID for the base region.
            layer: Layer name.
            closed: Whether the base shape is closed.
            smoothness: Curve smoothness 0.0–1.0.
            fill: Fill color.
            stroke: Stroke color.
            stroke_width: Stroke width.
            opacity: Opacity 0.0–1.0.
            z_index: Base z-index (sub-parts get z_index+1).
            sub_parts: Dict with pattern (required: "radial_fan" or "radial_ring"),
                count, anchor, length_range, width, angle_spread,
                length_variance, taper.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        try:
            result = scene.create_composite_region(
                outline=outline,
                document_id=doc_id,
                region_id=region_id,
                layer=layer,
                z_index=z_index,
                closed=closed,
                smoothness=smoothness,
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                sub_parts=sub_parts,
            )
            lines = [
                f"Composite created: {result['count']} region(s)",
                f"  Base: {result['base_id']}",
            ]
            for sid in result["sub_ids"]:
                if sid != result["base_id"]:
                    lines.append(f"  Sub:  {sid}")
            return "\n".join(lines)
        except (ValueError, RuntimeError) as e:
            return f"Error: {e}"

    @mcp.tool(
        name="move_to_front",
        description="Move a region to the highest z-index (frontmost layer). "
        "Use when an object is hidden behind another and should render on top.",
    )
    def move_to_front(region_id: str, document_id: str | None = None) -> str:
        """Move a region to the highest z-index.

        Args:
            region_id: Region to bring to front.
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        if scene.move_to_front(region_id, doc_id):
            return f"Region '{region_id}' moved to front"
        return f"Error: Region '{region_id}' not found"

    @mcp.tool(
        name="move_to_back",
        description="Move a region to the lowest z-index (backmost layer). "
        "Use when an object should render behind all others.",
    )
    def move_to_back(region_id: str, document_id: str | None = None) -> str:
        """Move a region to the lowest z-index.

        Args:
            region_id: Region to send to back.
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        if scene.move_to_back(region_id, doc_id):
            return f"Region '{region_id}' moved to back"
        return f"Error: Region '{region_id}' not found"
