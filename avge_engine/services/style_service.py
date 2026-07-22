"""Style application service."""
from __future__ import annotations

from typing import Any

from avge_engine.effects import Style
from avge_engine.geometry import CurveConstraints
from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import DepthHazeResult, LineHierarchyResult, MaterialApplyResult
from avge_engine.services.engine import get_graph, resolve_doc, stroke_width_to_norm
from avge_engine.services.selector_service import select_region_ids
from avge_engine.scene.models import RegionNode


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


class StyleService:
    """Application service for style operations shared by MCP/API callers."""

    def __init__(self, graph=None) -> None:
        self.graph = graph or get_graph()

    def apply_depth_haze(
        self,
        *,
        document_id: str | None = None,
        selector: dict[str, Any] | None = None,
        haze_color: str = "#7FB8D6",
        near_y: float = 0.75,
        far_y: float = 0.25,
        max_strength: float = 0.55,
        affect_fill: bool = True,
        affect_stroke: bool = True,
        opacity_falloff: float = 0.0,
    ) -> DepthHazeResult:
        """Blend selected regions toward haze_color based on vertical depth."""
        doc_id = resolve_doc(document_id)

        if _hex_to_rgb(haze_color) is None:
            raise ValueError("haze_color must be a #RRGGBB hex color")

        target_ids = select_region_ids(self.graph, doc_id, selector, default_all=True)
        if not target_ids:
            raise LookupError("No matching regions found")

        denom = near_y - far_y
        if abs(denom) < 1e-6:
            raise ValueError("near_y and far_y must differ")

        affected = 0
        for rid in target_ids:
            try:
                region = self.graph.get_region(rid, doc_id)
            except ValueError:
                continue
            bounds = region.bounds
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
            self.graph.edit_region(region_id=rid, document_id=doc_id, **kwargs)
            affected += 1

        return DepthHazeResult(affected=affected, haze_color=haze_color, max_strength=max_strength)

    def apply_line_hierarchy(
        self,
        *,
        document_id: str | None = None,
        selector: dict[str, Any] | None = None,
        outer_width: StrokeWidthInput = 6,
        inner_width: StrokeWidthInput = 3,
        basis: str = "z_index",
    ) -> LineHierarchyResult:
        """Apply stroke-weight hierarchy to selected regions."""
        doc_id = resolve_doc(document_id)
        outer_norm = stroke_width_to_norm(doc_id, outer_width)
        inner_norm = stroke_width_to_norm(doc_id, inner_width)

        target_ids = set(select_region_ids(self.graph, doc_id, selector, default_all=True))
        regions = [r for r in self.graph.get_all_regions(doc_id) if r.id in target_ids]
        if not regions:
            raise LookupError("No regions found")

        if basis == "z_index":
            regions.sort(key=lambda r: r.z_index, reverse=True)
        elif basis == "layer":
            layers: dict[str, list[Any]] = {}
            for r in regions:
                layers.setdefault(r.layer, []).append(r)
            regions = [r for layer_regions in layers.values() for r in layer_regions]
        elif basis == "bounding_size":
            regions.sort(key=lambda r: (r.bounds or {}).get("w", 0) or 0, reverse=True)
        else:
            raise ValueError(f"Unknown basis '{basis}'")

        cutoff = max(1, len(regions) // 3)
        outer = regions[:cutoff]
        inner = regions[cutoff:]

        for r in outer:
            try:
                self.graph.edit_region(region_id=r.id, document_id=doc_id, stroke_width=outer_norm)
            except (ValueError, RuntimeError):
                pass
        for r in inner:
            try:
                self.graph.edit_region(region_id=r.id, document_id=doc_id, stroke_width=inner_norm)
            except (ValueError, RuntimeError):
                pass

        return LineHierarchyResult(
            outer_count=len(outer),
            inner_count=len(inner),
            outer_width=outer_width,
            inner_width=inner_width,
        )

    def apply_material(
        self,
        *,
        ids: list[str],
        material: str,
        document_id: str | None = None,
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = None,
        blend_mode: str | None = None,
        material_detail: bool = True,
        material_intensity: float = 0.65,
    ) -> MaterialApplyResult:
        """Apply a built-in material preset and optional generated detail overlays."""
        doc_id = resolve_doc(document_id)
        if material not in MATERIAL_PRESETS:
            available = ", ".join(MATERIAL_PRESETS)
            raise ValueError(f"Unknown material '{material}'. Available: {available}")

        resolved_stroke_width = stroke_width_to_norm(doc_id, stroke_width)
        cfg = MATERIAL_PRESETS[material]
        affected = self.graph.style_objects(
            ids=ids,
            document_id=doc_id,
            fill_gradient=cfg.get("fill_gradient"),
            stroke=stroke if stroke is not None else cfg.get("stroke"),
            stroke_width=resolved_stroke_width if resolved_stroke_width is not None else cfg.get("stroke_width"),
            opacity=opacity if opacity is not None else cfg.get("opacity"),
            blend_mode=blend_mode if blend_mode is not None else cfg.get("blend_mode"),
        )
        overlays: list[str] = []
        if material_detail:
            for rid in affected:
                try:
                    overlays.extend(self._create_material_overlays(doc_id, rid, material, material_intensity))
                except (ValueError, RuntimeError):
                    pass
        return MaterialApplyResult(material=material, affected=len(affected), detail_count=len(overlays))

    def _create_material_overlays(self, doc_id: str, region_id: str, material: str, intensity: float) -> list[str]:
        source = self.graph.get_region(region_id, doc_id)
        bounds = source.bounds
        if bounds is None:
            return []
        min_x = bounds["x"]
        min_y = bounds["y"]
        w = max(0.001, bounds["w"])
        h = max(0.001, bounds["h"])
        max_x = min_x + w
        max_y = min_y + h
        intensity = _clamp01(intensity)
        created: list[str] = []

        def oid(suffix: str) -> str:
            return f"{region_id}_{material}_{suffix}"

        stale = [
            r.id for r in self.graph.get_all_regions(doc_id)
            if r.metadata.get("material_source") == region_id
        ]
        if stale:
            self.graph.delete_regions(doc_id, stale)

        if material == "glass":
            created.append(self._add_overlay_region(doc_id, source, oid("shine"),
                [(min_x + 0.08 * w, min_y + 0.08 * h), (min_x + 0.88 * w, min_y + 0.03 * h),
                 (min_x + 0.72 * w, min_y + 0.22 * h), (min_x + 0.18 * w, min_y + 0.28 * h)],
                "#FFFFFF", 0.22 + 0.18 * intensity, 2, material, "screen", None, 0.001, 0.35))
            created.append(self._add_overlay_region(doc_id, source, oid("shade"),
                [(min_x + 0.12 * w, max_y - 0.20 * h), (max_x, max_y - 0.34 * h),
                 (max_x, max_y), (min_x, max_y)],
                "#285765", 0.08 + 0.12 * intensity, 1, material, "multiply", None, 0.001, 0.2))
        elif material == "brushed_metal":
            for i, y_frac in enumerate((0.22, 0.36, 0.52, 0.68, 0.82)):
                color = "#F7FAFA" if i % 2 == 0 else "#596267"
                created.append(self._add_overlay_line(doc_id, source, oid(f"grain_{i}"),
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
                created.append(self._add_overlay_region(doc_id, source, oid(f"speck_{i}"),
                    [(cx - rw, cy - rh), (cx + rw, cy - rh * 0.7), (cx + rw * 0.8, cy + rh), (cx - rw * 0.6, cy + rh * 0.8)],
                    "#5E625B" if i % 2 else "#F0EEE4", 0.10 + 0.10 * intensity, 1, material,
                    "multiply" if i % 2 else "screen", None, 0.001, 0.55))
        elif material == "wood":
            for i, y_frac in enumerate((0.18, 0.31, 0.48, 0.61, 0.78)):
                created.append(self._add_overlay_line(doc_id, source, oid(f"grain_{i}"),
                    (min_x + 0.05 * w, min_y + y_frac * h),
                    (max_x - 0.05 * w, min_y + (y_frac + (0.035 if i % 2 else -0.025)) * h),
                    "#5A3014", 0.18 + 0.16 * intensity, 1, material, 0.0011, "multiply"))
        elif material == "tile":
            for i, x_frac in enumerate((0.33, 0.66)):
                created.append(self._add_overlay_line(doc_id, source, oid(f"v_seam_{i}"),
                    (min_x + x_frac * w, min_y + 0.04 * h), (min_x + x_frac * w, max_y - 0.04 * h),
                    "#776D5D", 0.32 + 0.18 * intensity, 1, material, 0.0014, "multiply"))
            for i, y_frac in enumerate((0.5,)):
                created.append(self._add_overlay_line(doc_id, source, oid(f"h_seam_{i}"),
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
                created.append(self._add_overlay_region(doc_id, source, oid(f"leaf_{i}"),
                    [(cx, cy - rh), (cx + rw, cy), (cx, cy + rh), (cx - rw, cy)],
                    "#B8D96E" if i % 2 == 0 else "#2F6B35", 0.20 + 0.16 * intensity, 1, material,
                    "screen" if i % 2 == 0 else "multiply", None, 0.001, 0.75))

        if created:
            self.graph.group_regions(f"material_{material}_{region_id}", [region_id, *created], doc_id, replace=True)
        return created

    def _add_overlay_region(self, doc_id: str, source, rid: str, outline, fill, opacity: float,
                            z_offset: int, material: str, blend_mode: str | None = None,
                            stroke: str | None = None, stroke_width: float = 0.001,
                            smoothness: float = 0.2) -> str:
        region = self.graph.create_region(
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
                opacity=_clamp01(opacity),
                blend_mode=blend_mode,
            ),
            metadata=_material_tag(source.id, material),
        )
        return region.id

    def _add_overlay_line(self, doc_id: str, source, rid: str, p1, p2, stroke: str,
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
                opacity=_clamp01(opacity),
                blend_mode=blend_mode,
                stroke_linecap="round",
                stroke_dasharray=dasharray,
            ),
            metadata=_material_tag(source.id, material),
        )
        self.graph._regions_for(doc_id)[rid] = region
        self.graph.get_document(doc_id).version += 1
        self.graph._auto_checkpoint(doc_id, "material_overlay", rid)
        self.graph._persist(doc_id)
        return rid


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


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
    t = _clamp01(amount)
    rgb = [round(src[i] + (dst[i] - src[i]) * t) for i in range(3)]
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _material_tag(region_id: str, material: str) -> dict[str, str]:
    return {"material_source": region_id, "material": material}
