"""Style application service."""
from __future__ import annotations

import json
from typing import Any

from avge_engine.constants.style import MATERIAL_PRESETS
from avge_engine.effects import Style
from avge_engine.effects.color import apply_hsl_offset
from avge_engine.geometry import CurveConstraints
from avge_engine.effects import GradientDef
from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import DepthHazeResult, LineHierarchyResult, MaterialApplyResult
from avge_engine.services.base_element import BaseElementService
from avge_engine.services.selector_service import select_element_ids
from avge_engine.document.models import ElementNode
from avge_engine.utils.color_utils import hex_to_rgb, mix_hex
from avge_engine.utils.math_utils import clamp01


class StyleService(BaseElementService):
    """Application service for style operations shared by MCP/API callers."""

    def style_objects(
        self,
        ids: list[str],
        document_id: str | None = None,
        *,
        fill: str | GradientDef | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        fill_gradient: str | dict | None = None,
        blend_mode: str | None = None,
        clip_to: str | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        blur: float | None = None,
        fill_hsl_offset: dict | None = None,
        stroke_hsl_offset: dict | None = None,
    ) -> list[str]:
        """Update style on existing elements. Returns list of actually updated IDs."""
        doc_id = self.require_document_id(document_id)
        affected: list[str] = []
        for element_id in ids:
            try:
                element = self.get_element(doc_id, element_id)
            except ValueError:
                continue
            old = element.style
            resolved_fill = fill
            if fill_gradient is not None:
                if isinstance(fill_gradient, str):
                    try:
                        resolved_fill = json.loads(fill_gradient)
                    except json.JSONDecodeError:
                        resolved_fill = fill_gradient
                else:
                    resolved_fill = fill_gradient
            elif fill is not None:
                resolved_fill = fill
            elif fill_hsl_offset is not None and isinstance(old.fill, str) and old.fill.startswith("#"):
                resolved_fill = apply_hsl_offset(
                    old.fill,
                    h_offset=fill_hsl_offset.get("h", 0),
                    s_offset=fill_hsl_offset.get("s", 0),
                    l_offset=fill_hsl_offset.get("l", 0),
                )

            resolved_stroke = stroke
            if stroke is None and stroke_hsl_offset is not None and isinstance(old.stroke, str) and old.stroke.startswith("#"):
                resolved_stroke = apply_hsl_offset(
                    old.stroke,
                    h_offset=stroke_hsl_offset.get("h", 0),
                    s_offset=stroke_hsl_offset.get("s", 0),
                    l_offset=stroke_hsl_offset.get("l", 0),
                )

            self.documents.update_element(
                doc_id,
                element_id,
                fill=resolved_fill if resolved_fill is not None else old.fill,
                stroke=resolved_stroke if resolved_stroke is not None else old.stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                blend_mode=blend_mode,
                stroke_linecap=stroke_linecap,
                stroke_dasharray=stroke_dasharray,
                blur=blur,
            )
            if clip_to is not None:
                element.clip_to = clip_to
            affected.append(element_id)
        if affected:
            self.commit(doc_id, action="style_objects", target=str(affected))
        return affected

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
        """Blend selected elements toward haze_color based on vertical depth."""
        doc_id = self.require_document_id(document_id)

        if hex_to_rgb(haze_color) is None:
            raise ValueError("haze_color must be a #RRGGBB hex color")

        target_ids = select_element_ids(self.graph, doc_id, selector, default_all=True)
        if not target_ids:
            raise LookupError("No matching elements found")

        denom = near_y - far_y
        if abs(denom) < 1e-6:
            raise ValueError("near_y and far_y must differ")

        affected = 0
        for rid in target_ids:
            try:
                element = self.get_element(doc_id, rid)
            except ValueError:
                continue
            bounds = element.bounds
            if not bounds:
                continue
            cy = bounds["y"] + bounds["h"] / 2
            depth_t = clamp01((near_y - cy) / denom)
            strength = clamp01(depth_t * max_strength)
            if strength <= 0:
                continue

            kwargs: dict[str, Any] = {}
            if affect_fill and isinstance(element.style.fill, str):
                mixed_fill = mix_hex(element.style.fill, haze_color, strength)
                if mixed_fill:
                    kwargs["fill"] = mixed_fill
            if affect_stroke and isinstance(element.style.stroke, str):
                mixed_stroke = mix_hex(element.style.stroke, haze_color, strength)
                if mixed_stroke:
                    kwargs["stroke"] = mixed_stroke
            if opacity_falloff > 0:
                kwargs["opacity"] = max(0.0, element.style.opacity * (1.0 - opacity_falloff * depth_t))
            if not kwargs:
                continue
            self.documents.update_element(doc_id, rid, **kwargs)
            self.commit(doc_id, action="apply_depth_haze", target=rid)
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
        """Apply stroke-weight hierarchy to selected elements."""
        doc_id = self.require_document_id(document_id)
        outer_norm = self.stroke_width_to_norm(doc_id, outer_width)
        inner_norm = self.stroke_width_to_norm(doc_id, inner_width)

        target_ids = set(select_element_ids(self.graph, doc_id, selector, default_all=True))
        elements = [r for r in self.list_elements(doc_id) if r.id in target_ids]
        if not elements:
            raise LookupError("No elements found")

        if basis == "z_index":
            elements.sort(key=lambda r: r.z_index, reverse=True)
        elif basis == "layer":
            layers: dict[str, list[Any]] = {}
            for r in elements:
                layers.setdefault(r.layer, []).append(r)
            elements = [r for layer_elements in layers.values() for r in layer_elements]
        elif basis == "bounding_size":
            elements.sort(key=lambda r: (r.bounds or {}).get("w", 0) or 0, reverse=True)
        else:
            raise ValueError(f"Unknown basis '{basis}'")

        cutoff = max(1, len(elements) // 3)
        outer = elements[:cutoff]
        inner = elements[cutoff:]

        for r in outer:
            try:
                self.documents.update_element(doc_id, r.id, stroke_width=outer_norm)
                self.commit(doc_id, action="apply_line_hierarchy", target=r.id)
            except (ValueError, RuntimeError):
                pass
        for r in inner:
            try:
                self.documents.update_element(doc_id, r.id, stroke_width=inner_norm)
                self.commit(doc_id, action="apply_line_hierarchy", target=r.id)
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
        doc_id = self.require_document_id(document_id)
        if material not in MATERIAL_PRESETS:
            available = ", ".join(MATERIAL_PRESETS)
            raise ValueError(f"Unknown material '{material}'. Available: {available}")

        resolved_stroke_width = self.stroke_width_to_norm(doc_id, stroke_width)
        cfg = MATERIAL_PRESETS[material]
        affected = self.style_objects(
            ids,
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

    def _create_material_overlays(self, doc_id: str, element_id: str, material: str, intensity: float) -> list[str]:
        source = self.get_element(doc_id, element_id)
        bounds = source.bounds
        if bounds is None:
            return []
        min_x = bounds["x"]
        min_y = bounds["y"]
        w = max(0.001, bounds["w"])
        h = max(0.001, bounds["h"])
        max_x = min_x + w
        max_y = min_y + h
        intensity = clamp01(intensity)
        created: list[str] = []

        def oid(suffix: str) -> str:
            return f"{element_id}_{material}_{suffix}"

        stale = [
            r.id for r in self.list_elements(doc_id)
            if r.metadata.get("material_source") == element_id
        ]
        if stale:
            self.documents.delete_elements(doc_id, stale)

        if material == "glass":
            created.append(self._add_overlay_element(doc_id, source, oid("shine"),
                [(min_x + 0.08 * w, min_y + 0.08 * h), (min_x + 0.88 * w, min_y + 0.03 * h),
                 (min_x + 0.72 * w, min_y + 0.22 * h), (min_x + 0.18 * w, min_y + 0.28 * h)],
                "#FFFFFF", 0.22 + 0.18 * intensity, 2, material, "screen", None, 0.001, 0.35))
            created.append(self._add_overlay_element(doc_id, source, oid("shade"),
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
                created.append(self._add_overlay_element(doc_id, source, oid(f"speck_{i}"),
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
                created.append(self._add_overlay_element(doc_id, source, oid(f"leaf_{i}"),
                    [(cx, cy - rh), (cx + rw, cy), (cx, cy + rh), (cx - rw, cy)],
                    "#B8D96E" if i % 2 == 0 else "#2F6B35", 0.20 + 0.16 * intensity, 1, material,
                    "screen" if i % 2 == 0 else "multiply", None, 0.001, 0.75))

        if created:
            from avge_engine.services.document_structure_service import DocumentStructureService

            DocumentStructureService(self.graph).group_elements(
                f"material_{material}_{element_id}",
                [element_id, *created],
                document_id=doc_id,
                replace=True,
            )
        return created

    def _add_overlay_element(self, doc_id: str, source, rid: str, outline, fill, opacity: float,
                            z_offset: int, material: str, blend_mode: str | None = None,
                            stroke: str | None = None, stroke_width: float = 0.001,
                            smoothness: float = 0.2) -> str:
        element = self.documents.create_element_node(
            doc_id,
            element_id=rid,
            outline=outline,
            layer=source.layer,
            z_index=source.z_index + z_offset,
            clip_to=source.id,
            constraints=CurveConstraints(smoothness=smoothness, closed=True),
            style=Style(
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=clamp01(opacity),
                blend_mode=blend_mode,
            ),
            metadata=_material_tag(source.id, material),
        )
        self.commit(doc_id, action="material_overlay", target=rid)
        return element.id

    def _add_overlay_line(self, doc_id: str, source, rid: str, p1, p2, stroke: str,
                          opacity: float, z_offset: int, material: str,
                          stroke_width: float = 0.0012, blend_mode: str | None = None,
                          dasharray: str | None = None) -> str:
        element = ElementNode(
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
                opacity=clamp01(opacity),
                blend_mode=blend_mode,
                stroke_linecap="round",
                stroke_dasharray=dasharray,
            ),
            metadata=_material_tag(source.id, material),
        )
        self.add_element(doc_id, element)
        self.commit(doc_id, action="material_overlay", target=rid)
        return rid

def _material_tag(element_id: str, material: str) -> dict[str, str]:
    return {"material_source": element_id, "material": material}
