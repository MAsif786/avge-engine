"""Element transform application service."""
from __future__ import annotations

import math
from typing import Any

from avge_engine.geometry import normalize_outline
from avge_engine.services.base_element import BaseElementService
from avge_engine.services.selector_service import select_element_ids, selector_from_legacy


class TransformService(BaseElementService):
    """Application service for target resolution, alignment, and transforms."""

    def transform_objects(
        self,
        *,
        ids: list[str] | None = None,
        selector: dict[str, Any] | None = None,
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
        pivot_mode: str | None = None,
        z_index: int | None = None,
        group_name: str | None = None,
        layer: str | None = None,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> dict[str, Any]:
        doc_id = self.require_document_id(document_id)
        resolved_selector = selector or selector_from_legacy(ids=ids, group_name=group_name, layer=layer)
        target_ids = select_element_ids(self.graph, doc_id, resolved_selector)
        if not target_ids:
            raise ValueError("No element IDs provided")

        if mode == "align":
            return self._align(doc_id, target_ids, alignment or "center_h")
        if mode != "transform":
            raise ValueError(f"Unknown transform mode '{mode}'")

        affected = self._apply_transform(
            doc_id,
            target_ids,
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
            mirror_x=mirror_x,
            mirror_y=mirror_y,
        )
        return {"affected": affected, "count": len(affected), "document_id": doc_id}

    def _align(self, doc_id: str, target_ids: list[str], alignment: str) -> dict[str, Any]:
        bounds_list = []
        for element_id in target_ids:
            try:
                bounds = self.get_element(doc_id, element_id).bounds
            except ValueError:
                continue
            if bounds:
                bounds_list.append({"id": element_id, "bounds": bounds})
        if len(bounds_list) < 2:
            raise ValueError("Need at least 2 valid elements")

        if alignment == "top":
            target = min(item["bounds"]["y"] for item in bounds_list)
            for item in bounds_list:
                self._shift_if_needed(doc_id, item["id"], dy=target - item["bounds"]["y"])
        elif alignment == "bottom":
            target = max(item["bounds"]["y"] + item["bounds"]["h"] for item in bounds_list)
            for item in bounds_list:
                self._shift_if_needed(doc_id, item["id"], dy=target - (item["bounds"]["y"] + item["bounds"]["h"]))
        elif alignment == "left":
            target = min(item["bounds"]["x"] for item in bounds_list)
            for item in bounds_list:
                self._shift_if_needed(doc_id, item["id"], dx=target - item["bounds"]["x"])
        elif alignment == "right":
            target = max(item["bounds"]["x"] + item["bounds"]["w"] for item in bounds_list)
            for item in bounds_list:
                self._shift_if_needed(doc_id, item["id"], dx=target - (item["bounds"]["x"] + item["bounds"]["w"]))
        elif alignment == "center_h":
            avg = sum(item["bounds"]["x"] + item["bounds"]["w"] / 2 for item in bounds_list) / len(bounds_list)
            for item in bounds_list:
                self._shift_if_needed(doc_id, item["id"], dx=avg - (item["bounds"]["x"] + item["bounds"]["w"] / 2))
        elif alignment == "center_v":
            avg = sum(item["bounds"]["y"] + item["bounds"]["h"] / 2 for item in bounds_list) / len(bounds_list)
            for item in bounds_list:
                self._shift_if_needed(doc_id, item["id"], dy=avg - (item["bounds"]["y"] + item["bounds"]["h"] / 2))
        elif alignment in ("distribute_h", "distribute_v"):
            self._distribute(doc_id, bounds_list, horizontal=alignment == "distribute_h")
        else:
            raise ValueError(f"Unknown alignment '{alignment}'")

        return {
            "affected": [item["id"] for item in bounds_list],
            "count": len(bounds_list),
            "alignment": alignment,
            "document_id": doc_id,
        }

    def _distribute(self, doc_id: str, bounds_list: list[dict[str, Any]], *, horizontal: bool) -> None:
        dim = "w" if horizontal else "h"
        pos = "x" if horizontal else "y"
        delta_key = "dx" if horizontal else "dy"
        sorted_bounds = sorted(bounds_list, key=lambda item: item["bounds"][pos])
        total = sum(item["bounds"][dim] for item in sorted_bounds)
        first = sorted_bounds[0]["bounds"][pos]
        last = sorted_bounds[-1]["bounds"][pos] + sorted_bounds[-1]["bounds"][dim]
        gap = (last - first - total) / (len(sorted_bounds) - 1)
        cursor = sorted_bounds[0]["bounds"][pos] + sorted_bounds[0]["bounds"][dim] + gap
        for item in sorted_bounds[1:-1]:
            delta = cursor - item["bounds"][pos]
            self._shift_if_needed(doc_id, item["id"], **{delta_key: delta})
            cursor += item["bounds"][dim] + gap

    def _shift_if_needed(self, doc_id: str, element_id: str, *, dx: float = 0.0, dy: float = 0.0) -> None:
        if abs(dx) <= 0.0001 and abs(dy) <= 0.0001:
            return
        self._apply_transform(doc_id, [element_id], dx=dx, dy=dy)

    def _apply_transform(
        self,
        doc_id: str,
        ids: list[str],
        *,
        dx: float = 0.0,
        dy: float = 0.0,
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        rotate: float = 0.0,
        group_mode: bool = False,
        pivot_x: float | None = None,
        pivot_y: float | None = None,
        pivot_mode: str | None = None,
        z_index: int | None = None,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> list[str]:
        """Apply geometric transforms to concrete element IDs."""
        elements = self.elements_map(doc_id)
        affected: list[str] = []

        scale_x = sx if sx is not None else scale
        scale_y = sy if sy is not None else scale
        if mirror_x:
            scale_x = -abs(scale_x)
        if mirror_y:
            scale_y = -abs(scale_y)
        angle = math.radians(rotate)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        gcx = gcy = 0.0
        if group_mode and ids:
            count = 0
            for element_id in ids:
                element = elements.get(element_id)
                if element is None:
                    continue
                for px, py in element.outline:
                    gcx += px
                    gcy += py
                    count += 1
            if count:
                gcx /= count
                gcy /= count

        if pivot_x is not None and pivot_y is not None:
            gcx, gcy = pivot_x, pivot_y

        for element_id in ids:
            element = elements.get(element_id)
            if element is None:
                continue

            if pivot_mode == "base":
                bounds = element.bounds
                cx = bounds["x"] + bounds["w"] / 2
                cy = bounds["y"] + bounds["h"]
            elif pivot_mode == "center":
                bounds = element.bounds
                cx = bounds["x"] + bounds["w"] / 2
                cy = bounds["y"] + bounds["h"] / 2
            elif group_mode or (pivot_x is not None and pivot_y is not None):
                cx, cy = gcx, gcy
            else:
                cx = sum(p[0] for p in element.outline) / len(element.outline)
                cy = sum(p[1] for p in element.outline) / len(element.outline)

            new_outline = []
            for x, y in element.outline:
                lx = (x - cx) * scale_x
                ly = (y - cy) * scale_y
                rx = lx * cos_a - ly * sin_a
                ry = lx * sin_a + ly * cos_a
                new_outline.append((rx + cx + dx, ry + cy + dy))

            element.outline = normalize_outline(new_outline)
            if element.primitive:
                has_scale = abs(scale_x - 1) > 0.001 or abs(scale_y - 1) > 0.001
                has_rotate = abs(rotate) > 0.001
                primitive = element.primitive
                primitive_type = primitive.get("type")

                if has_scale and not has_rotate and not mirror_x and not mirror_y:
                    if primitive_type == "ellipse":
                        primitive["cx"] = round((primitive["cx"] - cx) * scale_x + cx + dx, 6)
                        primitive["cy"] = round((primitive["cy"] - cy) * scale_y + cy + dy, 6)
                        primitive["rx"] = round(primitive["rx"] * scale_x, 6)
                        primitive["ry"] = round(primitive["ry"] * scale_y, 6)
                    elif primitive_type == "rect":
                        primitive["x"] = round((primitive["x"] - cx) * scale_x + cx + dx, 6)
                        primitive["y"] = round((primitive["y"] - cy) * scale_y + cy + dy, 6)
                        primitive["width"] = round(primitive["width"] * scale_x, 6)
                        primitive["height"] = round(primitive["height"] * scale_y, 6)
                    elif primitive_type == "line":
                        primitive["x1"] = round((primitive["x1"] - cx) * scale_x + cx + dx, 6)
                        primitive["y1"] = round((primitive["y1"] - cy) * scale_y + cy + dy, 6)
                        primitive["x2"] = round((primitive["x2"] - cx) * scale_x + cx + dx, 6)
                        primitive["y2"] = round((primitive["y2"] - cy) * scale_y + cy + dy, 6)
                elif has_rotate and not mirror_x and not mirror_y:
                    object.__setattr__(element.transform, "rotate", element.transform.rotate + rotate)
                elif abs(dx) > 0.001 or abs(dy) > 0.001:
                    if primitive_type == "ellipse":
                        primitive["cx"] += dx
                        primitive["cy"] += dy
                    elif primitive_type == "rect":
                        primitive["x"] += dx
                        primitive["y"] += dy
                    elif primitive_type == "line":
                        primitive["x1"] += dx
                        primitive["y1"] += dy
                        primitive["x2"] += dx
                        primitive["y2"] += dy

            element.version += 1
            affected.append(element_id)

        if z_index is not None:
            for element_id in affected:
                element = elements.get(element_id)
                if element is not None:
                    element.z_index = z_index

        if affected:
            self.commit(doc_id, action="transform_objects", target=str(affected))
        return affected
