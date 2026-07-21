"""Style controller — restyle, material presets, generate_palette, define_gradient."""
from __future__ import annotations

import json
import math
import random
from typing import Any, Literal

from avge_engine.effects import Style
from avge_engine.effects.brushes import BRUSH_PRESETS, BrushName, brush_preset_catalog
from avge_engine.effects.style import VALID_BLEND_MODES
from avge_engine.geometry import CurveConstraints, compute_bounds
from avge_engine.scene.models import RegionNode
from avge_engine.services.engine import StrokeWidthInput, get_graph, resolve_doc, stroke_width_to_norm
from avge_engine.services.selector_service import select_region_ids
from avge_engine.services.style_service import StyleService

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "linear-dodge", "color-burn", "soft-light", "hard-light",
    "difference", "hue", "saturation", "color", "luminosity", "add",
]

PRESET_NAMES = Literal["warm_shaded", "cool_shaded", "metallic", "glow", "shadow", "wood", "car_paint", "deep_shadow", "chrome", "meme_title", "meme_caption", "label", "label_light", "title", "subtitle", "comic"]
MATERIAL_NAMES = Literal["glass", "brushed_metal", "concrete", "wood", "tile", "foliage"]
LAYER_ROLES = Literal[
    "sketch", "line_art", "base_color", "shadow", "highlight",
    "glow", "texture", "fx", "background", "guide", "mask",
]
TEXTURE_EFFECTS = Literal[
    "noise", "paper", "fabric", "halftone", "screen_tone",
    "bloom", "particles", "gradient_light", "rim_light",
]
FX_TYPES = Literal["lens_flare", "motion_blur", "speed_lines", "impact_lines", "particles"]
COLOR_MIX_OUTPUTS = Literal["return_color", "apply_source", "apply_target", "new_region"]

LAYER_ROLE_Z = {
    "background": -1000,
    "sketch": -700,
    "guide": -650,
    "base_color": -100,
    "texture": 120,
    "shadow": 160,
    "highlight": 220,
    "glow": 260,
    "line_art": 320,
    "fx": 380,
    "mask": 500,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _scene_bounds_for_ids(scene, doc_id: str, ids: list[str]) -> dict[str, float] | None:
    boxes = []
    for rid in ids:
        try:
            bounds = compute_bounds(scene.get_region(rid, doc_id).outline)
        except ValueError:
            continue
        if bounds:
            boxes.append(bounds)
    if not boxes:
        return None
    min_x = min(b["x"] for b in boxes)
    min_y = min(b["y"] for b in boxes)
    max_x = max(b["x"] + b["w"] for b in boxes)
    max_y = max(b["y"] + b["h"] for b in boxes)
    return {"x": min_x, "y": min_y, "w": max_x - min_x, "h": max_y - min_y}


def _append_unique(base: str, suffix: str) -> str:
    return f"{base}_{suffix}_{random.randint(1000, 9999)}"


MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    "glass": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#F8FFFF"},
            {"offset": 0.35, "color": "#BFDDE6"},
            {"offset": 1.0, "color": "#6F9DAA"},
        ]},
        "stroke": "#D9F3F8", "stroke_width": 0.002, "opacity": 0.58, "blend_mode": "screen",
    },
    "brushed_metal": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 0, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#F5F6F4"},
            {"offset": 0.18, "color": "#8F989B"},
            {"offset": 0.32, "color": "#D4D8D7"},
            {"offset": 0.58, "color": "#6B7377"},
            {"offset": 1.0, "color": "#C9CECD"},
        ]},
        "stroke": "#596064", "stroke_width": 0.0025, "opacity": 1.0,
    },
    "concrete": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#D7D4C8"},
            {"offset": 0.55, "color": "#A9AA9F"},
            {"offset": 1.0, "color": "#7E8379"},
        ]},
        "stroke": "#6F746C", "stroke_width": 0.002, "opacity": 1.0,
    },
    "wood": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 0, "stops": [
            {"offset": 0.0, "color": "#E3B06B"},
            {"offset": 0.28, "color": "#9B622E"},
            {"offset": 0.52, "color": "#D1974E"},
            {"offset": 1.0, "color": "#70451F"},
        ]},
        "stroke": "#5E3719", "stroke_width": 0.002, "opacity": 1.0,
    },
    "tile": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#F4EEE2"},
            {"offset": 0.7, "color": "#CDBFA8"},
            {"offset": 1.0, "color": "#A99B83"},
        ]},
        "stroke": "#8D826F", "stroke_width": 0.0025, "opacity": 1.0,
    },
    "foliage": {
        "fill_gradient": {"type": "radial", "cx": 0.42, "cy": 0.34, "r": 0.72, "stops": [
            {"offset": 0.0, "color": "#D8E88E"},
            {"offset": 0.45, "color": "#6EA03F"},
            {"offset": 1.0, "color": "#244C2E"},
        ]},
        "stroke": "#2C5631", "stroke_width": 0.0018, "opacity": 1.0,
    },
}


def _material_tag(region_id: str, material: str) -> dict[str, str]:
    return {"material_source": region_id, "material": material}


def _hex_to_rgb(color: str) -> tuple[int, int, int] | None:
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return None
    try:
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    except ValueError:
        return None


def _mix_hex(color: str, target: str, amount: float) -> str | None:
    src = _hex_to_rgb(color)
    dst = _hex_to_rgb(target)
    if src is None or dst is None:
        return None
    t = max(0.0, min(1.0, amount))
    rgb = [round(src[i] + (dst[i] - src[i]) * t) for i in range(3)]
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _add_overlay_region(scene, doc_id: str, source, rid: str, outline, fill, opacity: float,
                        z_offset: int, material: str, blend_mode: str | None = None,
                        stroke: str | None = None, stroke_width: float = 0.001,
                        smoothness: float = 0.2) -> str:
    region = scene.create_region(
        document_id=doc_id,
        region_id=rid,
        outline=outline,
        layer=source.layer,
        z_index=source.z_index + z_offset,
        clip_to=source.id,
        constraints=CurveConstraints(smoothness=smoothness, closed=True),
        style=Style(
            fill=fill,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=max(0.0, min(1.0, opacity)),
            blend_mode=blend_mode,
        ),
        metadata=_material_tag(source.id, material),
    )
    return region.id


def _add_overlay_line(scene, doc_id: str, source, rid: str, p1, p2, stroke: str,
                      opacity: float, z_offset: int, material: str,
                      stroke_width: float = 0.0012, blend_mode: str | None = None,
                      dasharray: str | None = None) -> str:
    region = RegionNode(
        id=rid,
        layer=source.layer,
        z_index=source.z_index + z_offset,
        clip_to=source.id,
        outline=[p1, p2],
        constraints=CurveConstraints(smoothness=0.0, closed=False),
        style=Style(
            fill=None,
            stroke=stroke,
            stroke_width=stroke_width,
            opacity=max(0.0, min(1.0, opacity)),
            blend_mode=blend_mode,
            stroke_linecap="round",
            stroke_dasharray=dasharray,
        ),
        metadata=_material_tag(source.id, material),
    )
    scene._regions_for(doc_id)[rid] = region
    scene.get_document(doc_id).version += 1
    scene._auto_checkpoint(doc_id, "material_overlay", rid)
    scene._persist(doc_id)
    return rid


def _create_material_overlays(scene, doc_id: str, region_id: str, material: str, intensity: float) -> list[str]:
    source = scene.get_region(region_id, doc_id)
    bounds = compute_bounds(source.outline)
    if bounds is None:
        return []
    min_x = bounds["x"]
    min_y = bounds["y"]
    w = max(0.001, bounds["w"])
    h = max(0.001, bounds["h"])
    max_x = min_x + w
    max_y = min_y + h
    intensity = max(0.0, min(1.0, intensity))
    created: list[str] = []

    def oid(suffix: str) -> str:
        return f"{region_id}_{material}_{suffix}"

    # Replace previous generated material details for this source.
    stale = [
        r.id for r in scene.get_all_regions(doc_id)
        if r.metadata.get("material_source") == region_id
    ]
    if stale:
        scene.delete_regions(doc_id, stale)

    if material == "glass":
        created.append(_add_overlay_region(scene, doc_id, source, oid("shine"),
            [(min_x + 0.08 * w, min_y + 0.08 * h), (min_x + 0.88 * w, min_y + 0.03 * h),
             (min_x + 0.72 * w, min_y + 0.22 * h), (min_x + 0.18 * w, min_y + 0.28 * h)],
            "#FFFFFF", 0.22 + 0.18 * intensity, 2, material, "screen", None, 0.001, 0.35))
        created.append(_add_overlay_region(scene, doc_id, source, oid("shade"),
            [(min_x + 0.12 * w, max_y - 0.20 * h), (max_x, max_y - 0.34 * h),
             (max_x, max_y), (min_x, max_y)],
            "#285765", 0.08 + 0.12 * intensity, 1, material, "multiply", None, 0.001, 0.2))
    elif material == "brushed_metal":
        for i, y_frac in enumerate((0.22, 0.36, 0.52, 0.68, 0.82)):
            color = "#F7FAFA" if i % 2 == 0 else "#596267"
            created.append(_add_overlay_line(scene, doc_id, source, oid(f"grain_{i}"),
                (min_x + 0.04 * w, min_y + y_frac * h),
                (max_x - 0.04 * w, min_y + (y_frac - 0.035) * h),
                color, 0.13 + 0.13 * intensity, 1, material, 0.0008, "screen" if i % 2 == 0 else "multiply"))
    elif material == "concrete":
        for i, (x_frac, y_frac, s) in enumerate(((0.18, 0.28, 0.018), (0.46, 0.18, 0.012),
                                                 (0.72, 0.40, 0.015), (0.30, 0.68, 0.011),
                                                 (0.82, 0.76, 0.014))):
            cx = min_x + x_frac * w
            cy = min_y + y_frac * h
            rw = s * w
            rh = s * h
            created.append(_add_overlay_region(scene, doc_id, source, oid(f"speck_{i}"),
                [(cx - rw, cy - rh), (cx + rw, cy - rh * 0.7), (cx + rw * 0.8, cy + rh), (cx - rw * 0.6, cy + rh * 0.8)],
                "#5E625B" if i % 2 else "#F0EEE4", 0.10 + 0.10 * intensity, 1, material,
                "multiply" if i % 2 else "screen", None, 0.001, 0.55))
    elif material == "wood":
        for i, y_frac in enumerate((0.18, 0.31, 0.48, 0.61, 0.78)):
            created.append(_add_overlay_line(scene, doc_id, source, oid(f"grain_{i}"),
                (min_x + 0.05 * w, min_y + y_frac * h),
                (max_x - 0.05 * w, min_y + (y_frac + (0.035 if i % 2 else -0.025)) * h),
                "#5A3014", 0.18 + 0.16 * intensity, 1, material, 0.0011, "multiply"))
    elif material == "tile":
        for i, x_frac in enumerate((0.33, 0.66)):
            created.append(_add_overlay_line(scene, doc_id, source, oid(f"v_seam_{i}"),
                (min_x + x_frac * w, min_y + 0.04 * h), (min_x + x_frac * w, max_y - 0.04 * h),
                "#776D5D", 0.32 + 0.18 * intensity, 1, material, 0.0014, "multiply"))
        for i, y_frac in enumerate((0.5,)):
            created.append(_add_overlay_line(scene, doc_id, source, oid(f"h_seam_{i}"),
                (min_x + 0.04 * w, min_y + y_frac * h), (max_x - 0.04 * w, min_y + y_frac * h),
                "#FFFFFF", 0.18 + 0.16 * intensity, 2, material, 0.0012, "screen"))
    elif material == "foliage":
        for i, (x_frac, y_frac, scale) in enumerate(((0.25, 0.30, 0.11), (0.55, 0.25, 0.09),
                                                     (0.74, 0.50, 0.10), (0.35, 0.68, 0.08),
                                                     (0.58, 0.76, 0.12))):
            cx = min_x + x_frac * w
            cy = min_y + y_frac * h
            rw = scale * w
            rh = scale * h
            created.append(_add_overlay_region(scene, doc_id, source, oid(f"leaf_{i}"),
                [(cx, cy - rh), (cx + rw, cy), (cx, cy + rh), (cx - rw, cy)],
                "#B8D96E" if i % 2 == 0 else "#2F6B35", 0.20 + 0.16 * intensity, 1, material,
                "screen" if i % 2 == 0 else "multiply", None, 0.001, 0.75))

    if created:
        scene.group_regions(f"material_{material}_{region_id}", [region_id, *created], doc_id, replace=True)
    return created


def _apply_preset(preset_name: str, scene, doc_id: str, ids: list[str]) -> str | None:
    """Apply a named style preset to a list of region IDs.
    Returns error string on failure, None on success.
    """
    presets = getattr(scene, "PRESETS", None)
    if presets is None or preset_name not in presets:
        available = ", ".join(presets.keys()) if presets else "(none)"
        return f"Error: Unknown preset '{preset_name}'. Available: {available}"

    cfg = presets[preset_name].copy()
    fg = cfg.pop("fill_gradient", None)
    bm = cfg.pop("blend_mode", None)
    fill = json.loads(fg) if fg else cfg.get("fill")
    stroke = cfg.get("stroke")
    sw = cfg.get("stroke_width")
    for rid in ids:
        try:
            scene.edit_region(
                region_id=rid, document_id=doc_id,
                fill=fill, stroke=stroke, stroke_width=sw,
                opacity=cfg.get("opacity"), blend_mode=bm,
            )
        except (ValueError, RuntimeError) as e:
            return f"Error applying '{preset_name}' to '{rid}': {e}"
    return None


def create_tools(mcp):
    """Register style tools on the given FastMCP instance."""

    @mcp.tool(
        name="restyle",
        description="Change the appearance of a selection of regions. "
        "Consolidates recolor_conditional and recolor_palette "
        "into one tool. Select regions via ``selector``, then apply changes "
        "via ``mode``.\n"
        "Modes:\n"
        "  exact — set fill/stroke/opacity directly (directly)\n"
        "  hsl_offset — shift each region's current color by HSL delta\n"
        "  palette_swap — replace one exact fill color with another\n"
        "Materials: glass, brushed_metal, concrete, wood, tile, foliage\n"
        "Selector keys: ids, group_name, layer, fill, tags, bounds, z_min, z_max, has_stroke\n"
        "Use material=... for substance/surface presets; use apply_brush_style for medium/linework presets.\n"
        "💡 restyle(selector={'ids':['window']}, material='glass') — apply a material preset",
    )
    def restyle(
        selector: dict[str, Any] | None = None,
        mode: str = "exact",
        document_id: str | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = None,
        z_index: int | None = None,
        fill_gradient: Any | None = None,
        blend_mode: BLEND_MODES | None = None,
        fill_hsl_offset: dict | None = None,
        stroke_hsl_offset: dict | None = None,
        from_color: str | None = None,
        to_color: str | None = None,
        preset: str | None = None,
        material: MATERIAL_NAMES | None = None,
        material_detail: bool = True,
        material_intensity: float = 0.65,
    ) -> str:
        """Change region appearance with flexible selection and mode.

        Args:
            selector: Shared selector. Keys: ids, group_name, layer, fill,
                tags, bounds, z_min, z_max, has_stroke.
            mode: "exact" (default), "hsl_offset", or "palette_swap".
            document_id: Document UUID.
            fill: New fill color (exact mode) or target color (palette_swap mode).
            stroke: New stroke color (exact mode).
            stroke_width: New stroke width in canvas pixels.
            opacity: New opacity.
            fill_gradient: Gradient definition.
            blend_mode: CSS mix-blend-mode.
            fill_hsl_offset: Dict with h, s, l keys for HSL shift (hsl_offset mode).
            stroke_hsl_offset: Dict with h, s, l keys for stroke HSL shift.
            from_color: Source fill color to replace (palette_swap mode).
            to_color: Replacement fill color (palette_swap mode).
            preset: Named style preset.
            material: Built-in material preset: glass, brushed_metal,
                concrete, wood, tile, or foliage. Applies base style and,
                by default, generated highlight/shadow/texture overlays.
            material_detail: If True, generate editable overlay regions.
            material_intensity: Overlay strength from 0.0 to 1.0.
        """
        import json
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        stroke_width = stroke_width_to_norm(doc_id, stroke_width)

        target_ids = select_region_ids(scene, doc_id, selector)

        if not target_ids:
            return "Error: No matching regions found via selector"

        # Set z_index if provided (applied before mode dispatch)
        if z_index is not None:
            for rid in target_ids:
                try:
                    scene.edit_region(region_id=rid, document_id=doc_id, z_index=z_index)
                except (ValueError, RuntimeError):
                    pass
            if all(p is None for p in [fill, stroke, stroke_width, opacity, fill_gradient, blend_mode,
                                        fill_hsl_offset, stroke_hsl_offset, from_color, preset, material]):
                return f"z_index set to {z_index} on {len(target_ids)} region(s)"

        # Dispatch by mode
        if mode == "palette_swap":
            if not from_color or not to_color:
                return "Error: from_color and to_color required for palette_swap"
            matches = scene.find_objects(document_id=doc_id, fill=from_color)
            p_ids = [m["id"] for m in matches if m["id"] in target_ids]
            if not p_ids:
                return f"No regions found with fill='{from_color}'"
            resolved = None if to_color in ("none", "transparent") else to_color
            affected = scene.style_objects(ids=p_ids, document_id=doc_id, fill=resolved)
            return f"Palette swap: replaced '{from_color}' with '{to_color}' on {len(affected)} region(s)"

        if mode == "hsl_offset":
            affected = 0
            for rid in target_ids:
                try:
                    r = scene.get_region(rid, doc_id)
                    kwargs = {}
                    if fill_hsl_offset:
                        cur = r.style.fill
                        if isinstance(cur, str) and cur.startswith("#"):
                            from avge_engine.effects.color import apply_hsl_offset
                            kwargs["fill"] = apply_hsl_offset(
                                cur, h_offset=fill_hsl_offset.get("h", 0),
                                s_offset=fill_hsl_offset.get("s", 0),
                                l_offset=fill_hsl_offset.get("l", 0),
                            )
                    if stroke_hsl_offset:
                        cur = r.style.stroke
                        if isinstance(cur, str) and cur.startswith("#"):
                            from avge_engine.effects.color import apply_hsl_offset
                            kwargs["stroke"] = apply_hsl_offset(
                                cur, h_offset=stroke_hsl_offset.get("h", 0),
                                s_offset=stroke_hsl_offset.get("s", 0),
                                l_offset=stroke_hsl_offset.get("l", 0),
                            )
                    if opacity is not None:
                        kwargs["opacity"] = max(0.0, min(1.0, opacity))
                    if kwargs:
                        scene.edit_region(region_id=rid, document_id=doc_id, **kwargs)
                        affected += 1
                except (ValueError, RuntimeError):
                    pass
            return f"HSL offset applied to {affected} region(s)"

        # Exact mode (default) — matches style_objects behavior
        if material is None and preset in MATERIAL_PRESETS:
            material = preset  # Allow older preset=wood-style calls to use richer material logic.

        if material:
            if material not in MATERIAL_PRESETS:
                available = ", ".join(MATERIAL_PRESETS)
                return f"Error: Unknown material '{material}'. Available: {available}"
            cfg = MATERIAL_PRESETS[material]
            affected = scene.style_objects(
                ids=target_ids,
                document_id=doc_id,
                fill_gradient=cfg.get("fill_gradient"),
                stroke=stroke if stroke is not None else cfg.get("stroke"),
                stroke_width=stroke_width if stroke_width is not None else cfg.get("stroke_width"),
                opacity=opacity if opacity is not None else cfg.get("opacity"),
                blend_mode=blend_mode if blend_mode is not None else cfg.get("blend_mode"),
            )
            overlays: list[str] = []
            if material_detail:
                for rid in affected:
                    try:
                        overlays.extend(_create_material_overlays(scene, doc_id, rid, material, material_intensity))
                    except (ValueError, RuntimeError):
                        pass
            detail = f" with {len(overlays)} detail region(s)" if material_detail else ""
            return f"Material '{material}' applied to {len(affected)} region(s){detail}"

        if preset:
            presets = getattr(scene, "PRESETS", {})
            if preset in presets:
                cfg = presets[preset].copy()
                fg = cfg.pop("fill_gradient", None)
                bm = cfg.pop("blend_mode", None)
                preset_fill = json.loads(fg) if fg else cfg.get("fill")
                preset_stroke = cfg.get("stroke")
                preset_sw = cfg.get("stroke_width")
                for rid in target_ids:
                    scene.edit_region(
                        region_id=rid, document_id=doc_id,
                        fill=preset_fill, stroke=preset_stroke,
                        stroke_width=preset_sw,
                        opacity=cfg.get("opacity"), blend_mode=bm,
                    )
                return f"Preset '{preset}' applied to {len(target_ids)} region(s)"

        # Resolve named gradient reference (defined via define_gradient)
        if isinstance(fill_gradient, str):
            # Try to resolve as a named gradient stored by define_gradient
            doc = scene.get_document(doc_id)
            if doc and fill_gradient in doc.gradients:
                fill_gradient = doc.gradients[fill_gradient]
            # else: treat as-is (might be a URL or hex)

        # Normalize inline gradient: convert angle to x1/y1/x2/y2
        if isinstance(fill_gradient, dict) and fill_gradient.get("type") == "linear":
            ang = fill_gradient.pop("angle", None)
            if ang is not None:
                _rad = __import__("math").radians(ang)
                fill_gradient["x1"] = round(0.5 - 0.5 * __import__("math").cos(_rad), 2)
                fill_gradient["y1"] = round(0.5 - 0.5 * __import__("math").sin(_rad), 2)
                fill_gradient["x2"] = round(0.5 + 0.5 * __import__("math").cos(_rad), 2)
                fill_gradient["y2"] = round(0.5 + 0.5 * __import__("math").sin(_rad), 2)

        affected = scene.style_objects(
            ids=target_ids, document_id=doc_id,
            fill=fill, stroke=stroke,
            stroke_width=stroke_width, opacity=opacity,
            fill_gradient=fill_gradient, blend_mode=blend_mode,
        )
        return f"Restyled {len(affected)} region(s)"


    @mcp.tool(
        name="list_brush_presets",
        description="List supported brush presets grouped by purpose. "
        "Use this to discover brush names before apply_brush_style. "
        "Brush presets control editable stroke medium/linework; use restyle(material=...) "
        "for substance/surface looks and apply_texture_effect for overlay grain/FX.",
    )
    def list_brush_presets(
        group: Literal["all", "line_art", "paint", "texture", "natural", "fx"] = "all",
        include_details: bool = True,
    ) -> dict[str, Any]:
        """Return available brush presets grouped by role."""
        return brush_preset_catalog(group=group, include_details=include_details)


    @mcp.tool(
        name="apply_brush_style",
        description="Apply a digital art brush preset to existing regions. "
        "Use list_brush_presets to discover supported presets for line art, paint, texture, natural strokes, and FX. "
        "Use restyle(material=...) for substance/surface looks like glass, wood, concrete, tile, or foliage. "
        "Use apply_texture_effect for separate overlay FX such as paper grain, halftone, bloom, and particles; "
        "stack brush first, then texture if both are needed. "
        "This changes editable vector style properties; optional rough/pressure behavior creates "
        "small overlay strokes rather than raster pixels.",
    )
    def apply_brush_style(
        selector: dict[str, Any] | None = None,
        brush: BrushName = "ink",
        document_id: str | None = None,
        color: str | None = None,
        size: StrokeWidthInput = None,
        opacity: float | None = None,
        apply_to: Literal["stroke", "fill", "both"] = "stroke",
        blend_mode: BLEND_MODES | None = None,
        pressure: bool | None = None,
        texture_strength: float = 0.0,
    ) -> str:
        """Apply a brush preset to selected regions.

        Args:
            selector: Common selector: ids, group_name, fill, layer, or tags.
            brush: Brush preset name returned by list_brush_presets.
            color: Override preset color.
            size: Override stroke width in canvas pixels.
            apply_to: Whether to affect stroke, fill, or both.
            pressure: Mark linework as pressure-sensitive in metadata.
            texture_strength: 0.0-1.0 amount of extra rough overlay strokes.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        if brush not in BRUSH_PRESETS:
            return f"Error: Unknown brush '{brush}'"
        target_ids = select_region_ids(scene, doc_id, selector)
        if not target_ids:
            return "Error: No matching regions found"

        cfg = BRUSH_PRESETS[brush]
        stroke_color = color or cfg["stroke"]
        stroke_width = stroke_width_to_norm(doc_id, size) or stroke_width_to_norm(doc_id, cfg["stroke_width"]) or 0.005
        resolved_opacity = _clamp01(opacity if opacity is not None else cfg["opacity"])
        resolved_blend = blend_mode if blend_mode is not None else cfg.get("blend_mode")
        linecap = cfg.get("linecap", "round")
        resolved_pressure = cfg.get("pressure", False) if pressure is None else pressure
        affected = 0
        overlays: list[str] = []
        rng = random.Random(abs(hash((brush, len(target_ids)))) & 0xFFFF)

        for rid in target_ids:
            try:
                region = scene.get_region(rid, doc_id)
                kwargs: dict[str, Any] = {
                    "opacity": resolved_opacity,
                    "blend_mode": resolved_blend,
                    "metadata": {"brush": brush, "brush_pressure": resolved_pressure},
                }
                if apply_to in ("stroke", "both"):
                    kwargs.update({
                        "stroke": stroke_color,
                        "stroke_width": stroke_width,
                        "stroke_linecap": linecap,
                    })
                if apply_to in ("fill", "both"):
                    kwargs["fill"] = stroke_color
                if cfg.get("blur", 0) > 0:
                    kwargs["blur"] = float(cfg["blur"])
                scene.edit_region(region_id=rid, document_id=doc_id, **kwargs)
                affected += 1

                if texture_strength > 0 and len(region.outline) >= 2:
                    passes = max(1, min(5, round(texture_strength * 5)))
                    for i in range(passes):
                        pts = [
                            (
                                max(0.0, min(1.0, p[0] + rng.uniform(-0.004, 0.004) * texture_strength)),
                                max(0.0, min(1.0, p[1] + rng.uniform(-0.004, 0.004) * texture_strength)),
                            )
                            for p in region.outline
                        ]
                        if region.constraints.closed and len(pts) > 2:
                            pts.append(pts[0])
                        overlay = scene.create_line(
                            points=pts,
                            document_id=doc_id,
                            region_id=f"{rid}_{brush}_grain_{i}",
                            layer=region.layer,
                            z_index=region.z_index + 1,
                            stroke=stroke_color,
                            stroke_width=stroke_width * rng.uniform(0.45, 0.8),
                            opacity=resolved_opacity * 0.35 * texture_strength,
                            blend_mode=resolved_blend,
                            stroke_linecap="round",
                            smoothness=region.constraints.smoothness,
                        )
                        overlay.metadata.update({"brush_overlay_for": rid, "brush": brush})
                        overlays.append(overlay.id)
            except (ValueError, RuntimeError):
                continue

        return f"Brush '{brush}' applied to {affected} region(s), overlays={len(overlays)}"


    @mcp.tool(
        name="set_layer_role",
        description="Assign an art workflow role to an existing layer and optionally normalize its z-order/style. "
        "Roles: sketch, line_art, base_color, shadow, highlight, glow, texture, fx, background, guide, mask.",
    )
    def set_layer_role(
        layer: str,
        role: LAYER_ROLES,
        document_id: str | None = None,
        z_base: int | None = None,
        opacity: float | None = None,
        blend_mode: BLEND_MODES | None = None,
    ) -> str:
        """Tag every region on a layer with a workflow role."""
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        target_ids = select_region_ids(scene, doc_id, {"layer": layer})
        if not target_ids:
            return f"Error: No regions found on layer '{layer}'"
        base = LAYER_ROLE_Z.get(role, 0) if z_base is None else z_base
        affected = 0
        for idx, rid in enumerate(target_ids):
            try:
                kwargs: dict[str, Any] = {
                    "z_index": base + idx,
                    "metadata": {"layer_role": role},
                }
                if opacity is not None:
                    kwargs["opacity"] = opacity
                elif role == "sketch":
                    kwargs["opacity"] = 0.35
                elif role == "guide":
                    kwargs["opacity"] = 0.25
                if blend_mode is not None:
                    kwargs["blend_mode"] = blend_mode
                elif role == "shadow":
                    kwargs["blend_mode"] = "multiply"
                elif role in ("highlight", "glow", "fx"):
                    kwargs["blend_mode"] = "screen"
                scene.edit_region(region_id=rid, document_id=doc_id, **kwargs)
                affected += 1
            except (ValueError, RuntimeError):
                continue
        return f"Layer '{layer}' role set to '{role}' on {affected} region(s)"


    @mcp.tool(
        name="apply_texture_effect",
        description="Create editable vector texture and FX overlays for selected art. "
        "Effects: noise, paper, fabric, halftone, screen_tone, bloom, particles, "
        "gradient_light, rim_light. This is an overlay/FX pass, not a medium preset; "
        "use apply_brush_style first for pencil/ink/watercolor/chalk stroke quality, then stack texture effects. "
        "Uses clipping when possible so effects stay inside the target.",
    )
    def apply_texture_effect(
        effect: TEXTURE_EFFECTS,
        selector: dict[str, Any] | None = None,
        document_id: str | None = None,
        bounds: list[float] | None = None,
        clip_to: str | None = None,
        color: str = "#FFFFFF",
        secondary_color: str | None = None,
        density: int = 24,
        size: StrokeWidthInput = None,
        opacity: float = 0.35,
        angle: float = 0.0,
        blend_mode: BLEND_MODES | None = None,
        layer: str | None = None,
        z_index: int | None = None,
        seed: int = 1,
    ) -> str:
        """Add vector texture/effect overlays."""
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        target_ids = select_region_ids(scene, doc_id, selector)
        if clip_to and not target_ids:
            target_ids = [clip_to]
        box = None
        if bounds:
            box = {"x": float(bounds[0]), "y": float(bounds[1]), "w": float(bounds[2]), "h": float(bounds[3])}
        elif target_ids:
            box = _scene_bounds_for_ids(scene, doc_id, target_ids)
        if not box:
            return "Error: bounds or matching regions required"

        base_clip = clip_to or (target_ids[0] if len(target_ids) == 1 else None)
        base_layer = layer
        base_z = z_index
        if base_clip:
            try:
                src = scene.get_region(base_clip, doc_id)
                base_layer = base_layer or src.layer
                base_z = base_z if base_z is not None else src.z_index + 4
            except ValueError:
                pass
        base_layer = base_layer or "texture"
        base_z = 100 if base_z is None else base_z
        wnorm = stroke_width_to_norm(doc_id, size) or 0.004
        rng = random.Random(seed)
        created: list[str] = []
        x, y, w, h = box["x"], box["y"], max(0.001, box["w"]), max(0.001, box["h"])
        resolved_blend = blend_mode

        def mark(region):
            region.clip_to = base_clip
            region.metadata.update({"tool": "apply_texture_effect", "effect": effect})
            created.append(region.id)

        try:
            if effect in ("halftone", "screen_tone"):
                cols = max(2, min(80, density))
                rows = max(2, round(cols * h / max(w, 0.001)))
                dot_r = max(wnorm, min(w / cols, h / rows) * (0.38 if effect == "halftone" else 0.22))
                for row in range(rows):
                    for col in range(cols):
                        if effect == "screen_tone" and (row + col) % 2:
                            continue
                        px = x + (col + 0.5) * w / cols
                        py = y + (row + 0.5) * h / rows
                        r = scene.create_ellipse(
                            px, py, dot_r * rng.uniform(0.75, 1.15),
                            document_id=doc_id,
                            region_id=f"fx_{effect}_{len(created):03d}",
                            layer=base_layer,
                            z_index=base_z,
                            fill=color,
                            stroke=None,
                            opacity=opacity * rng.uniform(0.75, 1.0),
                            blend_mode=resolved_blend or ("multiply" if color != "#FFFFFF" else "screen"),
                        )
                        mark(r)
            elif effect in ("noise", "paper", "fabric"):
                count = max(4, min(450, density * (6 if effect == "noise" else 4)))
                for i in range(count):
                    px = x + rng.random() * w
                    py = y + rng.random() * h
                    length = wnorm * rng.uniform(1.5, 5.0)
                    theta = math.radians(angle + (rng.uniform(-35, 35) if effect != "fabric" else (0 if i % 2 else 90)))
                    p2 = (px + math.cos(theta) * length, py + math.sin(theta) * length)
                    r = scene.create_line(
                        points=[(px, py), p2],
                        document_id=doc_id,
                        region_id=f"fx_{effect}_{i:03d}",
                        layer=base_layer,
                        z_index=base_z,
                        stroke=color if i % 3 else (secondary_color or color),
                        stroke_width=wnorm * rng.uniform(0.35, 0.95),
                        opacity=opacity * rng.uniform(0.25, 0.75),
                        blend_mode=resolved_blend or ("multiply" if effect != "paper" else "overlay"),
                        stroke_linecap="round",
                    )
                    mark(r)
            elif effect == "bloom":
                ids = target_ids or ([base_clip] if base_clip else [])
                for rid in ids:
                    try:
                        src = scene.get_region(rid, doc_id)
                    except ValueError:
                        continue
                    r = scene.create_region(
                        outline=src.outline,
                        document_id=doc_id,
                        region_id=_append_unique(rid, "bloom"),
                        layer=base_layer,
                        z_index=src.z_index + 3,
                        constraints=src.constraints,
                        style=Style(fill=color, stroke=None, opacity=opacity, blend_mode=resolved_blend or "screen", blur=max(3.0, wnorm * 2200)),
                        metadata={"tool": "apply_texture_effect", "effect": effect, "source": rid},
                    )
                    created.append(r.id)
            elif effect == "particles":
                count = max(1, min(300, density))
                for i in range(count):
                    px = x + rng.random() * w
                    py = y + rng.random() * h
                    dot = wnorm * rng.uniform(0.65, 2.8)
                    r = scene.create_ellipse(
                        px, py, dot,
                        document_id=doc_id,
                        region_id=f"fx_particle_{i:03d}",
                        layer=base_layer,
                        z_index=base_z + i % 3,
                        fill=color if i % 4 else (secondary_color or color),
                        stroke=None,
                        opacity=opacity * rng.uniform(0.3, 1.0),
                        blend_mode=resolved_blend or "screen",
                    )
                    mark(r)
            elif effect in ("gradient_light", "rim_light"):
                if effect == "gradient_light":
                    grad = {
                        "type": "linear",
                        "x1": round(0.5 - 0.5 * math.cos(math.radians(angle)), 2),
                        "y1": round(0.5 - 0.5 * math.sin(math.radians(angle)), 2),
                        "x2": round(0.5 + 0.5 * math.cos(math.radians(angle)), 2),
                        "y2": round(0.5 + 0.5 * math.sin(math.radians(angle)), 2),
                        "stops": [
                            {"offset": 0.0, "color": color, "opacity": opacity},
                            {"offset": 1.0, "color": secondary_color or color, "opacity": 0.0},
                        ],
                    }
                    fill = grad
                    outline = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                    stroke = None
                    sw = 0.001
                else:
                    fill = None
                    stroke = color
                    sw = max(wnorm, min(w, h) * 0.035)
                    outline = [(x + 0.06 * w, y + 0.08 * h), (x + 0.55 * w, y), (x + 0.94 * w, y + 0.20 * h)]
                r = scene.create_region(
                    outline=outline,
                    document_id=doc_id,
                    region_id=f"fx_{effect}_{seed}",
                    layer=base_layer,
                    z_index=base_z,
                    clip_to=base_clip,
                    constraints=CurveConstraints(smoothness=0.45, closed=effect == "gradient_light"),
                    style=Style(fill=fill, stroke=stroke, stroke_width=sw, opacity=opacity, blend_mode=resolved_blend or "screen", stroke_linecap="round"),
                    metadata={"tool": "apply_texture_effect", "effect": effect},
                )
                created.append(r.id)
            else:
                return f"Error: Unknown effect '{effect}'"
        except (ValueError, RuntimeError, TypeError) as exc:
            return f"Error: {exc}"

        scene._persist(doc_id)
        return f"Texture effect '{effect}' created {len(created)} region(s)"


    @mcp.tool(
        name="apply_fx",
        description="Create editable vector FX overlays for directional and radiant effects. "
        "Types: lens_flare, motion_blur, speed_lines, impact_lines, particles. "
        "Use apply_texture_effect for surface overlays like paper, halftone, bloom, or grain; "
        "use apply_fx for scene/action effects with direction, center, rays, streaks, or particles.",
    )
    def apply_fx(
        type: FX_TYPES,
        selector: dict[str, Any] | None = None,
        document_id: str | None = None,
        bounds: list[float] | None = None,
        center: list[float] | None = None,
        direction: float = 0.0,
        count: int = 24,
        color: str = "#FFFFFF",
        secondary_color: str | None = None,
        intensity: float = 0.65,
        length: float = 0.18,
        spread: float = 35.0,
        size: StrokeWidthInput = None,
        opacity: float = 0.55,
        blend_mode: BLEND_MODES | None = None,
        layer: str = "fx",
        z_index: int = 380,
        clip_to: str | None = None,
        seed: int = 1,
    ) -> str:
        """Create vector FX regions and lines."""
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        target_ids = select_region_ids(scene, doc_id, selector)
        box = None
        if bounds:
            if len(bounds) != 4:
                return "Error: bounds must be [x, y, width, height]"
            box = {"x": float(bounds[0]), "y": float(bounds[1]), "w": float(bounds[2]), "h": float(bounds[3])}
        elif target_ids:
            box = _scene_bounds_for_ids(scene, doc_id, target_ids)
        if not box:
            return "Error: bounds or matching selector required"
        x, y, w, h = box["x"], box["y"], max(0.001, box["w"]), max(0.001, box["h"])
        if center and len(center) >= 2:
            cx, cy = float(center[0]), float(center[1])
        else:
            cx, cy = x + w / 2, y + h / 2

        rng = random.Random(seed)
        created: list[str] = []
        base_width = stroke_width_to_norm(doc_id, size) or 0.003
        resolved_blend = blend_mode or "screen"
        resolved_opacity = _clamp01(opacity * intensity)
        safe_count = max(1, min(500, int(count)))

        def mark(region, part: str):
            region.clip_to = clip_to
            region.metadata.update({"tool": "apply_fx", "fx_type": type, "part": part})
            created.append(region.id)
            return region

        def add_line(part: str, points, stroke: str, sw: float, op: float, smooth: float = 0.0):
            r = scene.create_line(
                points=points,
                document_id=doc_id,
                region_id=f"fx_{type}_{part}_{len(created):03d}",
                layer=layer,
                z_index=z_index + len(created),
                stroke=stroke,
                stroke_width=sw,
                opacity=_clamp01(op),
                blend_mode=resolved_blend,
                stroke_linecap="round",
                smoothness=smooth,
            )
            return mark(r, part)

        def add_dot(part: str, px: float, py: float, radius: float, fill: str, op: float):
            r = scene.create_ellipse(
                px,
                py,
                radius,
                radius,
                document_id=doc_id,
                region_id=f"fx_{type}_{part}_{len(created):03d}",
                layer=layer,
                z_index=z_index + len(created),
                fill=fill,
                stroke=None,
                opacity=_clamp01(op),
                blend_mode=resolved_blend,
            )
            return mark(r, part)

        try:
            if type == "speed_lines":
                theta = math.radians(direction)
                nx = -math.sin(theta)
                ny = math.cos(theta)
                for i in range(safe_count):
                    t = (i + 0.5) / safe_count
                    base_x = x + w * t + nx * rng.uniform(-0.12, 0.12) * w
                    base_y = y + h * rng.random()
                    line_len = length * rng.uniform(0.65, 1.25)
                    p1 = (base_x, base_y)
                    p2 = (base_x + math.cos(theta) * line_len, base_y + math.sin(theta) * line_len)
                    add_line("speed", [p1, p2], color if i % 4 else (secondary_color or color), base_width * rng.uniform(0.5, 1.4), resolved_opacity * rng.uniform(0.35, 0.9))
            elif type == "impact_lines":
                for i in range(safe_count):
                    angle = math.radians(i * 360.0 / safe_count + rng.uniform(-spread, spread) * 0.08)
                    inner = length * rng.uniform(0.08, 0.22)
                    outer = length * rng.uniform(0.65, 1.35)
                    p1 = (cx + math.cos(angle) * inner, cy + math.sin(angle) * inner)
                    p2 = (cx + math.cos(angle) * outer, cy + math.sin(angle) * outer)
                    add_line("impact", [p1, p2], color, base_width * rng.uniform(0.6, 1.8), resolved_opacity * rng.uniform(0.45, 1.0))
            elif type == "particles":
                for i in range(safe_count):
                    px = x + rng.random() * w
                    py = y + rng.random() * h
                    dot = base_width * rng.uniform(0.6, 3.5)
                    add_dot("particle", px, py, dot, color if i % 5 else (secondary_color or color), resolved_opacity * rng.uniform(0.25, 1.0))
            elif type == "lens_flare":
                theta = math.radians(direction)
                add_dot("core", cx, cy, max(base_width * 5, min(w, h) * 0.06), color, resolved_opacity)
                add_dot("halo", cx, cy, max(base_width * 12, min(w, h) * 0.14), secondary_color or color, resolved_opacity * 0.24)
                for i in range(max(3, min(10, safe_count // 3))):
                    offset = (i - 2) * length * 0.42
                    px = cx + math.cos(theta) * offset
                    py = cy + math.sin(theta) * offset
                    add_dot("orb", px, py, base_width * rng.uniform(2.0, 7.0), secondary_color or color, resolved_opacity * rng.uniform(0.18, 0.48))
                for angle in (direction, direction + 90):
                    theta2 = math.radians(angle)
                    add_line("ray", [(cx - math.cos(theta2) * length, cy - math.sin(theta2) * length), (cx + math.cos(theta2) * length, cy + math.sin(theta2) * length)], color, base_width * 0.8, resolved_opacity * 0.7)
            elif type == "motion_blur":
                theta = math.radians(direction)
                ids = target_ids
                if ids:
                    for rid in ids:
                        try:
                            src = scene.get_region(rid, doc_id)
                        except ValueError:
                            continue
                        for i in range(max(2, min(8, safe_count))):
                            d = length * (i + 1) / max(2, min(8, safe_count))
                            outline = [(px - math.cos(theta) * d, py - math.sin(theta) * d) for px, py in src.outline]
                            r = scene.create_region(
                                outline=outline,
                                document_id=doc_id,
                                region_id=f"fx_motion_blur_{rid}_{i}",
                                layer=layer,
                                z_index=z_index + len(created),
                                constraints=src.constraints,
                                style=Style(fill=color, stroke=None, opacity=resolved_opacity * (0.35 / (i + 1)), blend_mode=resolved_blend, blur=max(1.0, base_width * 650)),
                                metadata={"tool": "apply_fx", "fx_type": type, "part": "trail", "source": rid},
                            )
                            created.append(r.id)
                else:
                    for i in range(safe_count):
                        py = y + rng.random() * h
                        px = x + rng.random() * w
                        p2 = (px - math.cos(theta) * length * rng.uniform(0.5, 1.2), py - math.sin(theta) * length * rng.uniform(0.5, 1.2))
                        add_line("blur", [(px, py), p2], color, base_width * rng.uniform(1.0, 2.5), resolved_opacity * rng.uniform(0.2, 0.55), 0.35)
            else:
                return f"Error: Unknown FX type '{type}'"
        except (ValueError, RuntimeError, TypeError) as exc:
            return f"Error: {exc}"

        scene._persist(doc_id)
        return f"FX '{type}' created {len(created)} region(s)"


    @mcp.tool(
        name="mix_region_colors",
        description="Mix colors from two existing regions and return, apply, or duplicate the result. "
        "Use this when a requested color should be derived from existing artwork instead of invented manually. "
        "Only solid hex fill/stroke colors are mixed; gradients and named paints are rejected.",
    )
    def mix_region_colors(
        source_region_id: str,
        target_region_id: str,
        document_id: str | None = None,
        mix_ratio: float = 0.5,
        source_channel: Literal["fill", "stroke"] = "fill",
        target_channel: Literal["fill", "stroke"] = "fill",
        output: COLOR_MIX_OUTPUTS = "return_color",
        apply_to: Literal["fill", "stroke", "both"] = "fill",
        new_region_id: str | None = None,
        offset_x: float = 0.02,
        offset_y: float = 0.02,
        opacity: float | None = None,
        blend_mode: BLEND_MODES | None = None,
    ) -> dict[str, Any] | str:
        """Mix two existing region colors and optionally apply the result."""
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        try:
            source = scene.get_region(source_region_id, doc_id)
            target = scene.get_region(target_region_id, doc_id)
        except ValueError as exc:
            return f"Error: {exc}"

        source_color = getattr(source.style, source_channel)
        target_color = getattr(target.style, target_channel)
        if not isinstance(source_color, str) or _hex_to_rgb(source_color) is None:
            return f"Error: Source {source_channel} must be a solid #RRGGBB color"
        if not isinstance(target_color, str) or _hex_to_rgb(target_color) is None:
            return f"Error: Target {target_channel} must be a solid #RRGGBB color"

        ratio = _clamp01(mix_ratio)
        mixed = _mix_hex(source_color, target_color, ratio)
        if mixed is None:
            return "Error: Could not mix colors"
        metadata = {
            "tool": "mix_region_colors",
            "source_region_id": source_region_id,
            "target_region_id": target_region_id,
            "source_color": source_color,
            "target_color": target_color,
            "mix_ratio": ratio,
            "mixed_color": mixed,
        }

        if output == "return_color":
            return metadata

        def style_kwargs() -> dict[str, Any]:
            kwargs: dict[str, Any] = {"metadata": metadata}
            if apply_to in ("fill", "both"):
                kwargs["fill"] = mixed
            if apply_to in ("stroke", "both"):
                kwargs["stroke"] = mixed
            if opacity is not None:
                kwargs["opacity"] = _clamp01(opacity)
            if blend_mode is not None:
                kwargs["blend_mode"] = blend_mode
            return kwargs

        if output == "apply_source":
            scene.edit_region(region_id=source_region_id, document_id=doc_id, **style_kwargs())
            return f"Mixed color {mixed} applied to source region '{source_region_id}'"
        if output == "apply_target":
            scene.edit_region(region_id=target_region_id, document_id=doc_id, **style_kwargs())
            return f"Mixed color {mixed} applied to target region '{target_region_id}'"
        if output == "new_region":
            rid = new_region_id or f"{source_region_id}_mix_{target_region_id}"
            duplicate = scene.duplicate_region(
                region_id=source_region_id,
                new_region_id=rid,
                document_id=doc_id,
                offset_x=offset_x,
                offset_y=offset_y,
                fill=mixed if apply_to in ("fill", "both") else None,
                stroke=mixed if apply_to in ("stroke", "both") else None,
                opacity=_clamp01(opacity) if opacity is not None else None,
                blend_mode=blend_mode,
                z_index=source.z_index + 1,
            )
            duplicate.metadata.update(metadata)
            scene._auto_checkpoint(doc_id, "mix_region_colors", duplicate.id)
            scene._persist(doc_id)
            return f"Mixed color {mixed} created new region '{duplicate.id}'"
        return f"Error: Unknown output '{output}'"


    @mcp.tool(
        name="apply_depth_haze",
        description="Apply atmospheric perspective to existing regions by blending fills/strokes toward a haze color "
        "based on distance. Use for far buildings, skyline, canals, and background layers so scenes gain depth "
        "without manually restyling every region.",
    )
    def apply_depth_haze(
        document_id: str | None = None,
        selector: dict[str, Any] | None = None,
        haze_color: str = "#7FB8D6",
        near_y: float = 0.75,
        far_y: float = 0.25,
        max_strength: float = 0.55,
        affect_fill: bool = True,
        affect_stroke: bool = True,
        opacity_falloff: float = 0.0,
    ) -> str:
        """Blend selected regions toward haze_color based on their vertical depth.

        Args:
            selector: Shared selector. Omitted means all regions.
            haze_color: Hex color to blend toward, typically sky/horizon color.
            near_y: Regions at or below this center-y get no haze.
            far_y: Regions at or above this center-y get max_strength haze.
            max_strength: Maximum blend amount.
            affect_fill: Blend hex fills.
            affect_stroke: Blend hex strokes.
            opacity_falloff: Optional opacity reduction at maximum haze.
        """
        try:
            result = StyleService().apply_depth_haze(
                document_id=document_id,
                selector=selector,
                haze_color=haze_color,
                near_y=near_y,
                far_y=far_y,
                max_strength=max_strength,
                affect_fill=affect_fill,
                affect_stroke=affect_stroke,
                opacity_falloff=opacity_falloff,
            )
        except RuntimeError:
            return "Error: No active document"
        except LookupError:
            return "Error: No matching regions found"
        except ValueError as e:
            return f"Error: {e}"

        return (
            f"Depth haze applied to {result.affected} region(s) "
            f"(haze_color={result.haze_color}, max_strength={result.max_strength})"
        )


    @mcp.tool(
        name="generate_palette",
        description="Generate a color harmony palette. Returns hex values "
        "the agent can use for fills/strokes. "
        "💡 Use instead of inventing arbitrary hex values per region. "
        "Feed the output into restyle(selector={...}, fill="#...").",
    )
    def generate_palette(
        base_hue: float | None = None,
        mood: str | None = None,
        harmony: str = "complementary",
        count: int | None = None,
        include_shades: bool = False,
    ) -> str:
        """Generate a color harmony palette.

        Args:
            base_hue: Seed hue in degrees 0–360. Required unless mood is given.
            mood: Descriptive seed like "warm autumn", "cool cyberpunk".
                Used instead of an explicit hue.
            harmony: "complementary", "analogous", "triadic", or "split_complementary".
            count: Number of colors to return. Defaults per harmony type.
            include_shades: If True, also returns lighter/darker variants.
        """
        import math, colorsys

        # Resolve base hue from mood keyword
        if base_hue is None:
            mood_map = {
                "warm": 30, "autumn": 20, "summer": 60, "spring": 80,
                "cool": 200, "winter": 220, "cyberpunk": 280, "neon": 300,
                "ocean": 210, "forest": 120, "sunset": 350, "dawn": 40,
                "pastel": 180, "vintage": 30, "dark": 0, "moody": 260,
            }
            if mood:
                mood_lower = mood.lower()
                for key, hue in mood_map.items():
                    if key in mood_lower:
                        base_hue = hue
                        break
            if base_hue is None:
                import random as _r
                base_hue = _r.randint(0, 360)

        harmony_angles = {
            "complementary": [0, 180],
            "analogous": [0, 30, 60],
            "triadic": [0, 120, 240],
            "split_complementary": [0, 150, 210],
        }
        angles = harmony_angles.get(harmony, harmony_angles["complementary"])
        base_hue = base_hue % 360

        if count is None:
            count = len(angles)

        palette = []
        for i in range(count):
            h = (base_hue + angles[i % len(angles)]) / 360.0
            s = 0.6 + (i * 0.05) % 0.3
            l_val = 0.4 + (i * 0.06) % 0.3
            r, g, b = colorsys.hls_to_rgb(h, l_val, s)
            hex_c = "#{:02X}{:02X}{:02X}".format(int(r*255), int(g*255), int(b*255))
            palette.append(hex_c)
            if include_shades:
                r2, g2, b2 = colorsys.hls_to_rgb(h, max(0.1, l_val - 0.2), s)
                palette.append("#{:02X}{:02X}{:02X}".format(int(r2*255), int(g2*255), int(b2*255)))
                r3, g3, b3 = colorsys.hls_to_rgb(h, min(0.9, l_val + 0.2), s)
                palette.append("#{:02X}{:02X}{:02X}".format(int(r3*255), int(g3*255), int(b3*255)))

        result = ", ".join(palette[:count * (3 if include_shades else 1)])
        return f"Palette ({harmony}): {result}"

    @mcp.tool(
        name="define_gradient",
        description="Store a named gradient definition. The returned gradient "
        "dict can be referenced in restyle(fill_gradient=...) or "
        "create_region(fill_gradient=...). "
        "💡 Define once, reuse across many regions.",
    )
    def define_gradient(
        name: str,
        type: str = "linear",
        stops: list[dict] | None = None,
        angle: float = 0.0,
        document_id: str | None = None,
    ) -> str:
        """Define a reusable gradient.

        Args:
            name: Identifier to reference this gradient (e.g. "metal_panel").
            type: "linear" or "radial".
            stops: [{offset: 0-1, color: "#..."}, ...] — at least 2 stops.
            angle: Direction in degrees (linear only).
            document_id: Document UUID.
        """
        if not stops or len(stops) < 2:
            return "Error: At least 2 gradient stops required"
        for s in stops:
            if "offset" not in s or "color" not in s:
                return "Error: Each stop needs 'offset' and 'color'"
        grad = {"type": type, "stops": stops}
        if type == "linear":
            rad = __import__("math").radians(angle)
            grad["x1"] = round(0.5 - 0.5 * __import__("math").cos(rad), 2)
            grad["y1"] = round(0.5 - 0.5 * __import__("math").sin(rad), 2)
            grad["x2"] = round(0.5 + 0.5 * __import__("math").cos(rad), 2)
            grad["y2"] = round(0.5 + 0.5 * __import__("math").sin(rad), 2)
        # Store in document for reference by name
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
            doc = scene.get_document(doc_id)
            if doc:
                doc.gradients[name] = grad
                scene._persist(doc_id)
        except RuntimeError:
            pass
        return f"Gradient '{name}' defined. Reference in restyle via fill_gradient: \"{name}\""

    @mcp.tool(
        name="apply_line_hierarchy",
        description="Automate stroke-weight by depth: outer silhouette regions "
        "get thicker strokes, internal detail gets thinner. "
        "Accepts the shared selector shape to limit the pass to ids, group_name, layer, fill, tags, bounds, z_min, z_max, or has_stroke. "
        "💡 Apply after building a scene to enforce consistent line hierarchy.",
    )
    def apply_line_hierarchy(
        document_id: str | None = None,
        selector: dict[str, Any] | None = None,
        outer_width: StrokeWidthInput = 6,
        inner_width: StrokeWidthInput = 3,
        basis: str = "z_index",
    ) -> str:
        """Apply stroke-weight hierarchy.

        Args:
            document_id: Document UUID.
            selector: Shared selector. Omit/null to process all regions.
            outer_width: Stroke width for silhouette/outer regions in canvas pixels.
            inner_width: Stroke width for internal detail regions in canvas pixels.
            basis: "z_index", "layer", or "bounding_size".
        """
        try:
            result = StyleService().apply_line_hierarchy(
                document_id=document_id,
                selector=selector,
                outer_width=outer_width,
                inner_width=inner_width,
                basis=basis,
            )
        except RuntimeError:
            return "Error: No active document"
        except LookupError:
            return "Error: No regions found"
        except ValueError as e:
            return f"Error: {e}"

        return (
            f"Line hierarchy applied: {result.outer_count} outer ({result.outer_width}px), "
            f"{result.inner_count} inner ({result.inner_width}px)"
        )

    @mcp.tool(
        name="compare_style_consistency",
        description="Compare palette and stroke-width across multiple documents. "
        "Flags mismatches (e.g. a character's skin tone differing between pages). "
        "💡 Use before finishing a multi-panel or multi-page work.",
    )
    def compare_style_consistency(
        document_ids: list[str],
    ) -> str:
        """Compare style consistency across documents.

        Args:
            document_ids: Two or more document UUIDs to compare.
        """
        scene = get_graph()
        results = []
        for doc_id in document_ids:
            if not scene.load_document(doc_id):
                results.append(f"[{doc_id}] not found")
                continue
            regions = scene.get_all_regions(doc_id)
            fills = set()
            strokes = set()
            sws = set()
            for r in regions:
                if isinstance(r.style.fill, str) and r.style.fill.startswith("#"):
                    fills.add(r.style.fill.upper())
                if isinstance(r.style.stroke, str) and r.style.stroke.startswith("#"):
                    strokes.add(r.style.stroke.upper())
                sws.add(round(r.style.stroke_width, 4))
            results.append(
                f"[{doc_id}] fills={len(fills)} strokes={len(strokes)} "
                f"stroke_widths={sorted(sws)}"
            )

        if len(document_ids) >= 2:
            results.append("")
            results.append("--- Consistency Check ---")
            # Compare fills across docs
            all_fills = [set() for _ in document_ids]
            for i, doc_id in enumerate(document_ids):
                if scene.load_document(doc_id):
                    for r in scene.get_all_regions(doc_id):
                        if isinstance(r.style.fill, str) and r.style.fill.startswith("#"):
                            all_fills[i].add(r.style.fill.upper())
            if len(document_ids) >= 2:
                common_fills = all_fills[0].intersection(*all_fills[1:]) if len(all_fills) > 1 else all_fills[0]
                for i in range(len(document_ids)):
                    unique = all_fills[i] - common_fills
                    if unique:
                        results.append(f"  [{document_ids[i]}] unique fills: {sorted(unique)[:5]}...")

        return "\n".join(results)
