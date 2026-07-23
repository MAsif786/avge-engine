"""Document inspection and critique service."""
from __future__ import annotations

from typing import Any, Literal

from avge_engine.services.element_query import find_matching_elements
from avge_engine.services.base_element import BaseElementService
from avge_engine.services.selector_service import select_element_ids


class InspectionService(BaseElementService):
    """Application service for read-only scene inspection tools."""

    def describe_scene(
        self,
        *,
        document_id: str | None = None,
        detail: bool | str = True,
        filter_layer: str | None = None,
    ) -> dict[str, Any]:
        doc_id = self.require_document_id(document_id)
        doc = self.documents.get(doc_id)
        elements = self.list_elements(doc_id)
        include_full = detail == "full"
        element_list: list[dict[str, Any]] = []

        for element in elements:
            if filter_layer and element.layer != filter_layer:
                continue
            entry: dict[str, Any] = {
                "id": element.id,
                "type": element.type,
                "layer": element.layer,
                "z_index": element.z_index,
                "clip_to": element.clip_to,
                "outline_point_count": len(element.outline),
                "closed": element.constraints.closed,
                "smoothness": element.constraints.smoothness,
                "style": {
                    "fill": element.style.fill,
                    "stroke": element.style.stroke,
                    "stroke_width": element.style.stroke_width,
                    "opacity": element.style.opacity,
                    "blend_mode": element.style.blend_mode,
                },
                "bounds": element.bounds,
                "version": element.version,
                "metadata": element.metadata if element.metadata else None,
            }
            if include_full:
                entry["outline"] = element.outline
            element_list.append(entry)

        fills: set[str] = set()
        strokes: set[str] = set()
        for element in elements:
            if isinstance(element.style.fill, str) and element.style.fill.startswith("#"):
                fills.add(element.style.fill.upper())
            if isinstance(element.style.stroke, str) and element.style.stroke.startswith("#"):
                strokes.add(element.style.stroke.upper())

        return {
            "document": {
                "id": doc.id,
                "name": doc.name,
                "width": doc.width,
                "height": doc.height,
                "unit": doc.unit,
                "background": doc.background,
                "version": doc.version,
            },
            "elements": element_list,
            "element_count": len(element_list),
            "palette": {
                "fills": sorted(fills) if fills else [],
                "strokes": sorted(strokes) if strokes else [],
            },
            "warnings": self._compute_warnings(doc_id) + self._compute_smoothness_notes(doc_id),
        }

    def find_objects(
        self,
        *,
        document_id: str | None = None,
        selector: dict[str, Any] | None = None,
        fill: str | None = None,
        min_x: float | None = None,
        max_x: float | None = None,
        min_y: float | None = None,
        max_y: float | None = None,
        min_w: float | None = None,
        max_w: float | None = None,
        min_h: float | None = None,
        max_h: float | None = None,
        z_min: int | None = None,
        z_max: int | None = None,
        has_stroke: bool | None = None,
        layer: str | None = None,
        tags: dict | None = None,
    ) -> list[dict[str, Any]]:
        doc_id = self.require_document_id(document_id)
        if selector is not None:
            target_ids = select_element_ids(self.graph, doc_id, selector)
            target_set = set(target_ids)
            return [
                item for item in self._find_objects(document_id=doc_id)
                if item["id"] in target_set
            ]
        return self._find_objects(
            document_id=doc_id,
            fill=fill,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
            min_w=min_w,
            max_w=max_w,
            min_h=min_h,
            max_h=max_h,
            z_min=z_min,
            z_max=z_max,
            has_stroke=has_stroke,
            layer=layer,
            tags=dict(tags) if tags else None,
        )

    def _find_objects(
        self,
        *,
        document_id: str,
        fill: str | None = None,
        min_x: float | None = None,
        max_x: float | None = None,
        min_y: float | None = None,
        max_y: float | None = None,
        min_w: float | None = None,
        max_w: float | None = None,
        min_h: float | None = None,
        max_h: float | None = None,
        z_min: int | None = None,
        z_max: int | None = None,
        has_stroke: bool | None = None,
        layer: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        return find_matching_elements(
            self.list_elements(document_id),
            fill=fill,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
            min_w=min_w,
            max_w=max_w,
            min_h=min_h,
            max_h=max_h,
            z_min=z_min,
            z_max=z_max,
            has_stroke=has_stroke,
            layer=layer,
            tags=tags,
        )

    def critique(
        self,
        *,
        document_id: str | None = None,
        mode: Literal["rules", "visual", "both"] = "both",
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        doc_id = self.require_document_id(document_id)
        rules = self.critique_composition(document_id=doc_id) if mode in ("rules", "both") else []
        visual = [
            finding for finding in self.critique_preview_quality(document_id=doc_id)
            if finding.get("confidence", 0.0) >= min_confidence
        ] if mode in ("visual", "both") else []
        return {
            "mode": mode,
            "rules": {"findings": rules, "count": len(rules)},
            "visual": {"findings": visual, "count": len(visual)},
            "count": len(rules) + len(visual),
        }

    def critique_composition(self, document_id: str | None = None) -> list[str]:
        """Auto-check the scene against design rules."""
        doc_id = self.require_document_id(document_id)
        elements = self.elements_map(doc_id)
        findings: list[str] = []

        flat_count = sum(
            1 for element in elements.values()
            if isinstance(element.style.fill, str) and element.style.fill and element.style.opacity >= 0.95
        )
        gradient_count = sum(1 for element in elements.values() if isinstance(element.style.fill, dict))
        if flat_count > gradient_count * 3 and flat_count > 5:
            findings.append(
                f"Rule 1 (depth): {flat_count} flat fills, only {gradient_count} gradients — consider more depth shading"
            )

        widths = [element.style.stroke_width for element in elements.values() if element.style.stroke]
        if len(widths) > 3 and len(set(f"{width:.4f}" for width in widths)) <= 1:
            findings.append(
                f"Rule 2 (stroke hierarchy): all {len(widths)} stroked elements use the same width — vary by silhouette vs detail"
            )

        fills = [
            str(element.style.fill)
            for element in elements.values()
            if element.style.fill and isinstance(element.style.fill, str)
        ]
        unique_fills = len(set(fills))
        if unique_fills > 8:
            findings.append(f"Rule 3 (palette): {unique_fills} unique fill colors — aim for 3-5 cohesive colors")
        if unique_fills <= 1 and len(fills) > 5:
            findings.append(f"Rule 3 (palette): only 1 fill color across {len(fills)} elements — add variation")

        sorted_elements = sorted(elements.values(), key=lambda element: element.z_index)
        for i, outer in enumerate(sorted_elements):
            if outer.z_index < 0:
                continue
            ob = outer.bounds
            if not ob or ob["w"] < 0.05 or ob["h"] < 0.05:
                continue
            ox1, oy1 = ob["x"], ob["y"]
            ox2, oy2 = ob["x"] + ob["w"], ob["y"] + ob["h"]
            for inner in sorted_elements[i + 1:]:
                if inner.z_index <= outer.z_index:
                    continue
                ib = inner.bounds
                if not ib:
                    continue
                ix1, iy1 = ib["x"], ib["y"]
                ix2, iy2 = ib["x"] + ib["w"], ib["y"] + ib["h"]
                cx = (ix1 + ix2) / 2
                cy = (iy1 + iy2) / 2
                if cx < ox1 or cx > ox2 or cy < oy1 or cy > oy2:
                    continue
                if ib["h"] > ob["h"] * 1.2 and ix1 >= ox1 and ix2 <= ox2:
                    continue
                margin = 0.02
                if ix1 < ox1 - margin or iy1 < oy1 - margin or ix2 > ox2 + margin or iy2 > oy2 + margin:
                    findings.append(
                        f"Rule 5 (overlap): element '{inner.id}' (z={inner.z_index}) "
                        f"extends outside '{outer.id}' (z={outer.z_index}) — "
                        f"inner should stay inside outer bounds for correct layering"
                    )
                    break

        for element in elements.values():
            bounds = element.bounds
            if bounds and (
                bounds["x"] + bounds["w"] < 0
                or bounds["x"] > 1.0
                or bounds["y"] + bounds["h"] < 0
                or bounds["y"] > 1.0
            ):
                findings.append(f"Rule 6 (grounding): element '{element.id}' is off-canvas")

        if not elements:
            findings.append("Scene is empty — nothing to critique")
        return findings

    def critique_preview_quality(self, document_id: str | None = None) -> list[dict[str, Any]]:
        """Preview-oriented visual critique with actionable findings."""
        doc_id = self.require_document_id(document_id)
        elements = self.list_elements(doc_id)
        findings: list[dict[str, Any]] = []
        if not elements:
            return [{
                "code": "empty_scene",
                "severity": "high",
                "confidence": 1.0,
                "message": "Scene is empty — there is no preview to critique.",
                "suggestion": "Call create_element/create_primitive before preview critique.",
                "element_ids": [],
            }]

        visible = [element for element in elements if element.style.opacity > 0.02]
        filled = [element for element in visible if element.style.fill is not None]
        shadows = [
            element for element in visible
            if element.metadata.get("shadow_source")
            or (element.style.blur > 0 and element.style.fill in ("#000000", "#000", "black"))
            or element.style.blend_mode == "multiply" and element.style.opacity <= 0.35
        ]
        gradients = [element for element in filled if isinstance(element.style.fill, dict)]
        material_elements = [
            element for element in visible
            if element.metadata.get("material") or element.metadata.get("material_source")
        ]
        flat = [
            element for element in filled
            if isinstance(element.style.fill, str)
            and element.style.fill not in ("none", "transparent")
            and element.style.opacity >= 0.9
            and not element.metadata.get("shadow_source")
            and not element.metadata.get("material_source")
        ]

        def add(
            code: str,
            severity: str,
            confidence: float,
            message: str,
            suggestion: str,
            element_ids: list[str] | None = None,
        ) -> None:
            findings.append({
                "code": code,
                "severity": severity,
                "confidence": round(max(0.0, min(1.0, confidence)), 2),
                "message": message,
                "suggestion": suggestion,
                "element_ids": element_ids or [],
            })

        if len(filled) >= 4:
            flat_ratio = len(flat) / max(1, len(filled))
            depth_marks = len(gradients) + len(material_elements) + len(shadows)
            if flat_ratio >= 0.72 and depth_marks <= max(1, len(filled) // 5):
                add(
                    "too_flat",
                    "high" if flat_ratio > 0.85 else "medium",
                    flat_ratio,
                    f"{len(flat)} of {len(filled)} filled elements are opaque flat colors with little depth treatment.",
                    "Use restyle(material=...), fill_gradient, create_shadow, or add_shading on major objects.",
                    [element.id for element in flat[:6]],
                )

        rounded_ids: list[str] = []
        for element in visible:
            if element.primitive and element.primitive.get("type") == "rect":
                primitive = element.primitive
                rx = float(primitive.get("rx", 0.0))
                shortest = min(float(primitive.get("width", 0.0)), float(primitive.get("height", 0.0)))
                if shortest > 0 and rx >= shortest * 0.42:
                    rounded_ids.append(element.id)
            elif element.constraints.closed and element.constraints.smoothness >= 0.78 and len(element.outline) <= 7:
                rounded_ids.append(element.id)
        if len(rounded_ids) >= 3 and len(rounded_ids) / max(1, len(visible)) >= 0.28:
            add(
                "over_rounded",
                "medium",
                min(1.0, len(rounded_ids) / max(1, len(visible)) + 0.25),
                f"{len(rounded_ids)} elements look highly rounded/pill-like, which can make the preview toy-like.",
                "Reduce rx/smoothness on structural surfaces; reserve high smoothness for organic forms.",
                rounded_ids[:8],
            )

        shadow_sources = {str(element.metadata.get("shadow_source")) for element in shadows if element.metadata.get("shadow_source")}
        candidates: list[str] = []
        for element in visible:
            if element.id in shadow_sources or element.metadata.get("shadow_source") or element.metadata.get("material_source"):
                continue
            bounds = element.bounds
            if not bounds:
                continue
            if bounds["w"] * bounds["h"] >= 0.015 and bounds["y"] + bounds["h"] >= 0.45 and element.style.fill is not None:
                candidates.append(element.id)
        if candidates and not shadows:
            add(
                "missing_contact_shadows",
                "high" if len(candidates) >= 3 else "medium",
                0.82,
                f"{len(candidates)} sizeable lower-scene object(s) have no visible contact/depth shadow.",
                "Call create_shadow(element_id, direction=90, distance=0.03, softness=5, sy=0.35) for grounded objects.",
                candidates[:6],
            )
        elif len(candidates) >= 4 and len(shadows) < len(candidates) // 3:
            add(
                "missing_contact_shadows",
                "medium",
                0.68,
                f"Only {len(shadows)} shadow-like element(s) for {len(candidates)} sizeable grounded object(s).",
                "Add depth shadows to the main foreground objects, or cast shadows onto the floor/table plane.",
                candidates[:6],
            )

        suspect_quads: list[str] = []
        ratios: list[float] = []
        for element in visible:
            if not element.constraints.closed or len(element.outline) != 4:
                continue
            points = element.outline
            top_w = ((points[1][0] - points[0][0]) ** 2 + (points[1][1] - points[0][1]) ** 2) ** 0.5
            bottom_w = ((points[2][0] - points[3][0]) ** 2 + (points[2][1] - points[3][1]) ** 2) ** 0.5
            if top_w <= 0.001 or bottom_w <= 0.001:
                continue
            ratio = bottom_w / top_w
            ratios.append(ratio)
            left_skew = abs(points[3][0] - points[0][0])
            right_skew = abs(points[2][0] - points[1][0])
            bounds = element.bounds
            if (left_skew > 0.025 or right_skew > 0.025) and abs(ratio - 1.0) < 0.06 and bounds and bounds["w"] * bounds["h"] > 0.025:
                suspect_quads.append(element.id)
        if suspect_quads:
            add(
                "bad_perspective",
                "medium",
                0.72,
                f"{len(suspect_quads)} skewed quadrilateral panel(s) have almost no near/far foreshortening.",
                "Use project_quad with a wider near edge or create_ellipse_band(perspective=...) for circular planes.",
                suspect_quads[:6],
            )
        elif len(ratios) >= 4 and max(ratios) - min(ratios) > 0.55:
            add(
                "bad_perspective",
                "low",
                0.55,
                "Several quadrilateral planes use very different near/far width ratios.",
                "Normalize perspective direction across floor, table, wall, and window panels.",
                [],
            )

        filled_bounds = [(element, element.bounds) for element in filled]
        filled_bounds = [(element, bounds) for element, bounds in filled_bounds if bounds]
        if len(filled_bounds) >= 3:
            areas = [(element, bounds["w"] * bounds["h"]) for element, bounds in filled_bounds]
            total_area = sum(area for _, area in areas)
            largest, largest_area = max(areas, key=lambda item: item[1])
            if total_area > 0 and largest_area / total_area >= 0.58:
                is_blob = largest.constraints.smoothness >= 0.65 or len(largest.outline) >= 10 or not largest.primitive
                if is_blob:
                    add(
                        "dominant_blob_shape",
                        "medium",
                        min(0.9, largest_area / total_area),
                        f"Element '{largest.id}' visually dominates the scene and may read as a single blob.",
                        "Break it into planes/details, add line hierarchy, or add material/shadow overlays.",
                        [largest.id],
                    )

        return findings

    def _compute_warnings(self, document_id: str) -> list[str]:
        warnings: list[str] = []
        for element in self.list_elements(document_id):
            bounds = element.bounds
            if bounds and (
                bounds["x"] + bounds["w"] < 0
                or bounds["x"] > 1.0
                or bounds["y"] + bounds["h"] < 0
                or bounds["y"] > 1.0
            ):
                warnings.append(f"Element '{element.id}' is entirely off-canvas")
        return warnings

    def _compute_smoothness_notes(self, document_id: str) -> list[str]:
        notes: list[str] = []
        for element in self.list_elements(document_id):
            point_count = len(element.outline)
            smoothness = element.constraints.smoothness
            if point_count >= 20 and smoothness <= 0.1:
                notes.append(
                    f"Element '{element.id}': {point_count} points with smoothness={smoothness:.1f} "
                    f"(many points + sharp corners may produce jagged output; "
                    f"consider increasing smoothness or reducing point count)"
                )
        return notes
