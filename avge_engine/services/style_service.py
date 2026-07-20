"""Style application service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from avge_engine.geometry import compute_bounds
from avge_engine.services.engine import StrokeWidthInput, get_graph, resolve_doc, stroke_width_to_norm
from avge_engine.services.selector_service import select_region_ids


@dataclass(frozen=True)
class DepthHazeResult:
    affected: int
    haze_color: str
    max_strength: float


@dataclass(frozen=True)
class LineHierarchyResult:
    outer_count: int
    inner_count: int
    outer_width: StrokeWidthInput
    inner_width: StrokeWidthInput


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
            regions.sort(key=lambda r: (compute_bounds(r.outline) or {}).get("w", 0) or 0, reverse=True)
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
