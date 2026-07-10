"""Style controller — style_objects, apply_style_preset, blend_mode, clip_to."""
from __future__ import annotations

import json
from typing import Any, Literal

from avge_engine.services.engine import get_graph, resolve_doc

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "soft-light", "hard-light",
]

PRESET_NAMES = Literal["warm_shaded", "cool_shaded", "metallic", "glow", "shadow", "wood", "car_paint", "deep_shadow", "chrome"]


def create_tools(mcp):
    """Register style tools on the given FastMCP instance."""

    @mcp.tool(
        name="style_objects",
        description="Update the visual style of existing regions. "
        "Only provided parameters are changed; omit to leave untouched. "
        "Vary stroke width by hierarchy — heavier for outer silhouette, "
        "lighter for internal detail — rather than using one width "
        "throughout. See resource avge://skill/design-guidelines "
        "for full conventions. Supports blend_mode (CSS mix-blend-mode) "
        "and clip_to (constrain rendering inside another region's outline). "
        "💡 Reuse hex values already present in the scene's palette "
        "(check describe_scene) rather than introducing a new arbitrary "
        "color for a minor element like trim or a frame.",
    )
    def style_objects(
        ids: list[str] | None = None,
        document_id: str | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        fill_gradient: Any | None = None,
        blend_mode: BLEND_MODES | None = None,
        clip_to: str | None = None,
        group_name: str | None = None,
    ) -> str:
        """Update the visual style of one or more existing regions.

        Args:
            ids: List of region IDs to restyle.
            document_id: Document UUID (omit to use active document).
            fill: Fill hex color, or empty string for no fill.
            stroke: Stroke hex color, or empty string for no stroke.
            stroke_width: Stroke width in normalized units.
            opacity: Object opacity 0.0–1.0.
            fill_gradient: JSON-encoded gradient definition (string or dict).
            blend_mode: CSS mix-blend-mode value — "multiply", "screen",
                "overlay", "darken", "lighten", "color-dodge", "color-burn",
                "soft-light", "hard-light", "normal".
            clip_to: Region ID — constrain rendering of this region to
                appear only inside the clip region's outline.
            group_name: Group name — resolves group members as IDs.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        # Resolve group_name to member IDs
        if group_name is not None:
            members = scene.get_group(group_name, doc_id)
            if not members:
                return f"Error: Group '{group_name}' not found"
            ids = [m["id"] for m in members]
        elif not ids:
            return "Error: No region IDs provided"

        # Resolve fill: fill_gradient takes precedence over fill
        resolved_fill = None
        if fill_gradient is not None:
            if isinstance(fill_gradient, str):
                try:
                    resolved_fill = json.loads(fill_gradient)
                except json.JSONDecodeError:
                    return f"Error: invalid fill_gradient JSON: {fill_gradient}"
            elif isinstance(fill_gradient, dict):
                resolved_fill = fill_gradient
        elif fill is not None and fill != "none":
            resolved_fill = fill

        resolved_stroke = None if stroke is None or stroke == "none" else stroke
        resolved_sw = max(0.001, min(0.1, stroke_width)) if stroke_width is not None else None
        resolved_op = max(0.0, min(1.0, opacity)) if opacity is not None else None

        # Route through edit_region if blend_mode or clip_to is requested
        # (scene.style_objects doesn't support those, but edit_region does)
        if blend_mode is not None or clip_to is not None:
            affected = []
            for rid in ids:
                try:
                    scene.edit_region(
                        region_id=rid,
                        document_id=doc_id,
                        fill=resolved_fill,
                        stroke=resolved_stroke,
                        stroke_width=resolved_sw,
                        opacity=resolved_op,
                        blend_mode=blend_mode,
                        clip_to=clip_to,
                    )
                    affected.append(rid)
                except ValueError as e:
                    return f"Error updating '{rid}': {e}"
                except RuntimeError as e:
                    return f"Error: {e}"
            return (
                f"Styled {len(affected)} region(s) (via edit_region): "
                f"{', '.join(affected)}"
            )

        # Standard style update via scene.style_objects
        try:
            affected = scene.style_objects(
                ids=ids,
                document_id=doc_id,
                fill=resolved_fill,
                stroke=resolved_stroke,
                stroke_width=resolved_sw,
                opacity=resolved_op,
            )
        except RuntimeError as e:
            return f"Error: {e}"

        if not affected:
            return "No matching regions found"
        return f"Styled {len(affected)} region(s): {', '.join(affected)}"

    @mcp.tool(
        name="apply_style_preset",
        description="Apply a coordinated style preset to one or more regions. "
        "Presets expand fill, gradient, opacity, and blend_mode together "
        "for consistent visual quality: warm_shaded, cool_shaded, metallic, "
        "glow, shadow, wood, car_paint, deep_shadow, chrome. Gives good "
        "defaults to agents that know good design in principle but execute "
        "inconsistently through raw params.",
    )
    def apply_style_preset(
        preset: PRESET_NAMES,
        ids: list[str],
        document_id: str | None = None,
    ) -> str:
        """Apply a named style preset to regions.

        Args:
            preset: Preset name — "warm_shaded", "cool_shaded", "metallic",
                "glow", "shadow", "wood", "car_paint", "deep_shadow", "chrome".
            ids: Region IDs to apply the preset to.
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        if not ids:
            return "Error: No region IDs provided"

        # Access presets from the SceneGraph PRESETS dict
        presets = getattr(scene, "PRESETS", None)
        if presets is None:
            return "Error: Style presets not available"

        if preset not in presets:
            available = ", ".join(presets.keys())
            return (
                f"Error: Unknown preset '{preset}'. "
                f"Available: {available}"
            )

        preset_config = presets[preset].copy()
        fill_gradient = preset_config.pop("fill_gradient", None)
        blend_mode = preset_config.pop("blend_mode", None)

        # Apply to each region
        affected = []
        for rid in ids:
            try:
                # Resolve fill from gradient if needed
                fill = None
                if fill_gradient:
                    try:
                        fill = json.loads(fill_gradient)
                    except json.JSONDecodeError:
                        return f"Error: invalid gradient in preset '{preset}'"

                scene.edit_region(
                    region_id=rid,
                    document_id=doc_id,
                    fill=fill or preset_config.get("fill"),
                    opacity=preset_config.get("opacity"),
                    blend_mode=blend_mode,
                )
                affected.append(rid)
            except (ValueError, RuntimeError) as e:
                return f"Error applying '{preset}' to '{rid}': {e}"

        return (
            f"Applied preset '{preset}' to {len(affected)} region(s): "
            f"{', '.join(affected)}"
        )

    @mcp.tool(
        name="add_shadow",
        description="Create a drop-shadow region behind an object. "
        "Duplicates the region with a small offset, applies dark "
        "multiply-blend styling, and places it behind the original. "
        "💡 Use on car bodies, cups, hands — any object that needs "
        "instant depth without manually duplicating and restyling.",
    )
    def add_shadow(
        region_id: str,
        document_id: str | None = None,
        offset_x: float = 0.015,
        offset_y: float = 0.015,
        opacity: float = 0.25,
    ) -> str:
        """Create a drop-shadow region behind an object.

        Args:
            region_id: Region ID to add shadow to.
            document_id: Document UUID (omit to use active document).
            offset_x: Horizontal shadow offset (normalized 0.0–1.0).
            offset_y: Vertical shadow offset (normalized 0.0–1.0).
            opacity: Shadow opacity 0.0–1.0 (default 0.25).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        try:
            new_rid = f"{region_id}_shadow"
            scene.duplicate_region(
                region_id=region_id,
                new_region_id=new_rid,
                document_id=doc_id,
                offset_x=offset_x,
                offset_y=offset_y,
                fill="#000000",
                opacity=opacity,
                z_index=-9999,
            )
        except (ValueError, RuntimeError) as e:
            return f"Error creating shadow for '{region_id}': {e}"

        return (
            f"Created shadow region '{new_rid}' for '{region_id}' "
            f"(offset={offset_x},{offset_y}, opacity={opacity}). "
            f"Group them with manage_group to keep them together."
        )
