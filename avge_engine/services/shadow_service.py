"""Shadow and directional shading service."""
from __future__ import annotations

from typing import Any, Literal

from avge_engine.effects.color import apply_hsl_offset
from avge_engine.schemas.service_results import ShadowResult, ShadingResult
from avge_engine.services.base import BaseService
from avge_engine.services.engine import resolve_doc
from avge_engine.services.selector_service import select_element_ids


class ShadowService(BaseService):
    """Application service for shadows and directional shading."""

    def create_shadow(
        self,
        *,
        element_id: str,
        onto_element_id: str | None = None,
        document_id: str | None = None,
        direction: float = 45.0,
        distance: float = 0.03,
        softness: float = 4.0,
        opacity: float = 0.22,
        color: str = "#000000",
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        z_offset: int | None = None,
        new_element_id: str | None = None,
    ) -> ShadowResult:
        """Create a soft shadow from an existing element outline."""
        doc_id = resolve_doc(document_id)
        receiver = self.graph.get_element(onto_element_id, doc_id) if onto_element_id else None
        resolved_z_offset = z_offset if z_offset is not None else (1 if receiver else -1)
        shadow = self.graph.add_depth_shadow(
            element_id,
            document_id=doc_id,
            new_element_id=new_element_id,
            direction=direction,
            distance=max(0.0, min(1.0, distance)),
            softness=max(0.0, min(64.0, softness)),
            opacity=max(0.0, min(1.0, opacity)),
            color=color,
            scale=max(0.01, min(10.0, scale)),
            sx=sx,
            sy=sy,
            z_offset=0 if receiver else resolved_z_offset,
            clip_to=onto_element_id,
            layer=receiver.layer if receiver else None,
        )
        if receiver:
            shadow.z_index = receiver.z_index + resolved_z_offset
            self.graph.get_document(doc_id).version += 1
            self.graph._persist(doc_id)
        return ShadowResult(
            shadow=shadow,
            source_id=element_id,
            onto_element_id=onto_element_id,
            clipped=receiver is not None,
            softness=softness,
            direction=direction,
            distance=distance,
        )

    def add_shading(
        self,
        *,
        element_id: str | None = None,
        selector: dict[str, Any] | None = None,
        light_direction: float = 135,
        document_id: str | None = None,
        intensity: float = 0.5,
        mode: Literal["two_tone", "gradient"] = "two_tone",
        highlight_color: str | None = None,
        mid_color: str | None = None,
        shadow_color: str | None = None,
    ) -> ShadingResult:
        """Add directional shading to one or more elements."""
        import math
        import time as _time

        doc_id = resolve_doc(document_id)
        if selector:
            target_ids = select_element_ids(self.graph, doc_id, selector)
        elif element_id:
            target_ids = [element_id]
        else:
            raise ValueError("element_id or selector required")
        if not target_ids:
            raise LookupError("No matching elements found via selector")
        if mode not in ("two_tone", "gradient"):
            raise ValueError("mode must be 'two_tone' or 'gradient'")

        angle = math.radians(light_direction)
        targets = []
        for rid in target_ids:
            element = self.graph.get_element(rid, doc_id)
            cur_fill = element.style.fill
            if not isinstance(cur_fill, str) or not cur_fill.startswith("#"):
                raise ValueError(f"add_shading requires a hex fill color on '{rid}'")
            highlight = highlight_color or apply_hsl_offset(cur_fill, l_offset=intensity * 25, s_offset=-10)
            middle = mid_color or cur_fill
            shadow = shadow_color or apply_hsl_offset(cur_fill, l_offset=-intensity * 30, s_offset=15)
            targets.append((element, highlight, middle, shadow))

        if mode == "gradient":
            for element, highlight, middle, shadow in targets:
                grad = {
                    "type": "linear",
                    "stops": [
                        {"offset": 0.0, "color": highlight},
                        {"offset": 0.52, "color": middle},
                        {"offset": 1.0, "color": shadow},
                    ],
                    "x1": round(0.5 - 0.5 * math.cos(angle), 2),
                    "y1": round(0.5 - 0.5 * math.sin(angle), 2),
                    "x2": round(0.5 + 0.5 * math.cos(angle), 2),
                    "y2": round(0.5 + 0.5 * math.sin(angle), 2),
                }
                self.graph.edit_element(element_id=element.id, document_id=doc_id, fill=grad)
            return ShadingResult(
                mode=mode,
                target_count=len(targets),
                overlay_count=0,
                light_direction=light_direction,
            )

        offset = intensity * 0.015
        dx = math.cos(angle) * offset
        dy = math.sin(angle) * offset
        seq = int(_time.time() * 1000) % 100000
        created = []
        for element, highlight, _middle, shadow in targets:
            h_dup = self.graph.duplicate_element(
                element.id,
                document_id=doc_id,
                new_element_id=f"{element.id}_highlight_{seq}",
                offset_x=-dx,
                offset_y=-dy,
                fill=highlight,
                stroke=None,
                z_index=element.z_index + 1,
            )
            s_dup = self.graph.duplicate_element(
                element.id,
                document_id=doc_id,
                new_element_id=f"{element.id}_shadow_{seq}",
                offset_x=dx,
                offset_y=dy,
                fill=shadow,
                stroke=None,
                z_index=element.z_index - 1,
            )
            created.extend([h_dup.id, s_dup.id])
        return ShadingResult(
            mode=mode,
            target_count=len(targets),
            overlay_count=len(created),
            light_direction=light_direction,
        )
