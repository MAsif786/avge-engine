"""Style controller — style_objects."""
from __future__ import annotations

import json
from typing import Any, Literal

from avge_engine.services.engine import get_graph, resolve_doc

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "soft-light", "hard-light",
]

PRESET_NAMES = Literal["warm_shaded", "cool_shaded", "metallic", "glow", "shadow", "wood", "car_paint", "deep_shadow", "chrome", "meme_title", "meme_caption", "label", "label_light", "title", "subtitle", "comic"]


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
        "Consolidates style_objects, recolor_conditional, and recolor_palette "
        "into one tool. Select regions via ``selector``, then apply changes "
        "via ``mode``.\n"
        "Modes:\n"
        "  exact — set fill/stroke/opacity directly (like style_objects)\n"
        "  hsl_offset — shift each region's current color by HSL delta\n"
        "  palette_swap — replace one exact fill color with another\n"
        "Selector (choose one): ids=[...], group_name='...', fill='#...', layer='...'",
    )
    def restyle(
        selector: dict | None = None,
        mode: str = "exact",
        document_id: str | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        z_index: int | None = None,
        fill_gradient: Any | None = None,
        blend_mode: BLEND_MODES | None = None,
        fill_hsl_offset: dict | None = None,
        stroke_hsl_offset: dict | None = None,
        from_color: str | None = None,
        to_color: str | None = None,
        preset: str | None = None,
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
            opacity: New opacity.
            fill_gradient: Gradient definition.
            blend_mode: CSS mix-blend-mode.
            fill_hsl_offset: Dict with h, s, l keys for HSL shift (hsl_offset mode).
            stroke_hsl_offset: Dict with h, s, l keys for stroke HSL shift.
            from_color: Source fill color to replace (palette_swap mode).
            to_color: Replacement fill color (palette_swap mode).
            preset: Named style preset.
        """
        import json
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

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
                                        fill_hsl_offset, stroke_hsl_offset, from_color, preset]):
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
