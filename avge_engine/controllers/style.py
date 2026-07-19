"""Style controller — restyle, material presets, generate_palette, define_gradient."""
from __future__ import annotations

import json
from typing import Any, Literal

from avge_engine.effects import Style
from avge_engine.geometry import CurveConstraints, compute_bounds
from avge_engine.scene.models import RegionNode
from avge_engine.services.engine import get_graph, resolve_doc, stroke_width_px_to_norm

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "soft-light", "hard-light",
]

PRESET_NAMES = Literal["warm_shaded", "cool_shaded", "metallic", "glow", "shadow", "wood", "car_paint", "deep_shadow", "chrome", "meme_title", "meme_caption", "label", "label_light", "title", "subtitle", "comic"]
MATERIAL_NAMES = Literal["glass", "brushed_metal", "concrete", "wood", "tile", "foliage"]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


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
        "Selector (choose one): ids=[...], group_name='...', fill='#...', layer='...'\n"
        "💡 restyle(selector={'ids':['window']}, material='glass') — apply a material preset",
    )
    def restyle(
        selector: dict | None = None,
        mode: str = "exact",
        document_id: str | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        stroke_width_px: float | None = None,
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
            selector: Dict selecting target regions. One of:
                {"ids": [...]}, {"group_name": "..."}, {"fill": "#..."},
                {"layer": "..."}, {"tags": {...}}.
            mode: "exact" (default), "hsl_offset", or "palette_swap".
            document_id: Document UUID.
            fill: New fill color (exact mode) or target color (palette_swap mode).
            stroke: New stroke color (exact mode).
            stroke_width: New stroke width.
            stroke_width_px: New stroke width in canvas pixels. Overrides stroke_width.
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

        px_width = stroke_width_px_to_norm(doc_id, stroke_width_px)
        if px_width is not None:
            stroke_width = px_width

        # Resolve target region IDs from selector
        target_ids = None
        if selector:
            if "ids" in selector:
                target_ids = selector["ids"]
            elif "group_name" in selector:
                members = scene.get_group(selector["group_name"], doc_id)
                if members:
                    target_ids = [m["id"] for m in members]
            elif "fill" in selector:
                results = scene.find_objects(document_id=doc_id, fill=selector["fill"])
                target_ids = [r["id"] for r in results]
            elif "layer" in selector:
                results = scene.find_objects(document_id=doc_id, layer=selector["layer"])
                target_ids = [r["id"] for r in results]
            elif "tags" in selector:
                results = scene.find_objects(document_id=doc_id, tags=selector["tags"])
                target_ids = [r["id"] for r in results]

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
        name="apply_depth_haze",
        description="Apply atmospheric perspective to existing regions by blending fills/strokes toward a haze color "
        "based on distance. Use for far buildings, skyline, canals, and background layers so scenes gain depth "
        "without manually restyling every region.",
    )
    def apply_depth_haze(
        document_id: str | None = None,
        selector: dict | None = None,
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
            selector: Optional selector like restyle: {"ids":[...]}, {"layer":"..."},
                {"tags":{...}}, or {"fill":"#..."}; omitted means all regions.
            haze_color: Hex color to blend toward, typically sky/horizon color.
            near_y: Regions at or below this center-y get no haze.
            far_y: Regions at or above this center-y get max_strength haze.
            max_strength: Maximum blend amount.
            affect_fill: Blend hex fills.
            affect_stroke: Blend hex strokes.
            opacity_falloff: Optional opacity reduction at maximum haze.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        if _hex_to_rgb(haze_color) is None:
            return "Error: haze_color must be a #RRGGBB hex color"

        target_ids: list[str]
        if selector:
            if "ids" in selector:
                target_ids = list(selector["ids"])
            elif "group_name" in selector:
                members = scene.get_group(selector["group_name"], doc_id)
                target_ids = [m["id"] for m in members]
            elif "fill" in selector:
                target_ids = [r["id"] for r in scene.find_objects(document_id=doc_id, fill=selector["fill"])]
            elif "layer" in selector:
                target_ids = [r["id"] for r in scene.find_objects(document_id=doc_id, layer=selector["layer"])]
            elif "tags" in selector:
                target_ids = [r["id"] for r in scene.find_objects(document_id=doc_id, tags=selector["tags"])]
            else:
                return "Error: Unsupported selector. Use ids, group_name, fill, layer, or tags."
        else:
            target_ids = [r.id for r in scene.get_all_regions(doc_id)]

        if not target_ids:
            return "Error: No matching regions found"

        denom = near_y - far_y
        if abs(denom) < 1e-6:
            return "Error: near_y and far_y must differ"

        affected = 0
        for rid in target_ids:
            try:
                region = scene.get_region(rid, doc_id)
            except ValueError:
                continue
            bounds = compute_bounds(region.outline)
            if not bounds:
                continue
            cy = bounds["y"] + bounds["h"] / 2
            depth_t = _clamp01((near_y - cy) / denom)
            strength = _clamp01(depth_t * max_strength)
            if strength <= 0:
                continue

            kwargs: dict[str, Any] = {}
            if affect_fill and isinstance(region.style.fill, str):
                mixed_fill = _mix_hex(region.style.fill, haze_color, strength)
                if mixed_fill:
                    kwargs["fill"] = mixed_fill
            if affect_stroke and isinstance(region.style.stroke, str):
                mixed_stroke = _mix_hex(region.style.stroke, haze_color, strength)
                if mixed_stroke:
                    kwargs["stroke"] = mixed_stroke
            if opacity_falloff > 0:
                kwargs["opacity"] = max(0.0, region.style.opacity * (1.0 - opacity_falloff * depth_t))
            if not kwargs:
                continue
            scene.edit_region(region_id=rid, document_id=doc_id, **kwargs)
            affected += 1

        return (
            f"Depth haze applied to {affected} region(s) "
            f"(haze_color={haze_color}, max_strength={max_strength})"
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
        "💡 Apply after building a scene to enforce consistent line hierarchy.",
    )
    def apply_line_hierarchy(
        document_id: str | None = None,
        outer_width: float = 0.006,
        inner_width: float = 0.003,
        basis: str = "z_index",
    ) -> str:
        """Apply stroke-weight hierarchy.

        Args:
            document_id: Document UUID.
            outer_width: Stroke width for silhouette/outer regions.
            inner_width: Stroke width for internal detail regions.
            basis: "z_index", "layer", or "bounding_size".
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        regions = list(scene.get_all_regions(doc_id))
        if not regions:
            return "Error: No regions found"

        if basis == "z_index":
            regions.sort(key=lambda r: r.z_index, reverse=True)
        elif basis == "layer":
            layers = {}
            for r in regions:
                layers.setdefault(r.layer, []).append(r)
            regions = [r for layer_regs in layers.values() for r in layer_regs]
        elif basis == "bounding_size":
            from avge_engine.geometry import compute_bounds
            regions.sort(key=lambda r: (compute_bounds(r.outline) or {}).get("w", 0) or 0, reverse=True)
        else:
            return f"Error: Unknown basis '{basis}'"

        cutoff = max(1, len(regions) // 3)
        outer = regions[:cutoff]
        inner = regions[cutoff:]

        affected = 0
        for r in outer:
            try:
                scene.edit_region(region_id=r.id, document_id=doc_id, stroke_width=outer_width)
                affected += 1
            except (ValueError, RuntimeError):
                pass
        for r in inner:
            try:
                scene.edit_region(region_id=r.id, document_id=doc_id, stroke_width=inner_width)
                affected += 1
            except (ValueError, RuntimeError):
                pass

        return f"Line hierarchy applied: {len(outer)} outer ({outer_width}), {len(inner)} inner ({inner_width})"

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
