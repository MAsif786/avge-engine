"""Shared element query helpers."""
from __future__ import annotations

from typing import Any

from avge_engine.document import ElementNode


def find_matching_elements(
    elements: list[ElementNode],
    *,
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
    """Query elements by visual properties, bounds, z-index, and metadata tags."""
    results: list[dict[str, Any]] = []
    for element in elements:
        if fill is not None and element.style.fill != fill:
            continue
        if layer is not None and element.layer != layer:
            continue
        if has_stroke is not None:
            if has_stroke and element.style.stroke is None:
                continue
            if not has_stroke and element.style.stroke is not None:
                continue
        if tags is not None and not all(element.metadata.get(k) == v for k, v in tags.items()):
            continue
        if z_min is not None and element.z_index < z_min:
            continue
        if z_max is not None and element.z_index > z_max:
            continue
        bounds = element.bounds
        if bounds is None:
            continue
        if min_x is not None and bounds["x"] < min_x:
            continue
        if max_x is not None and bounds["x"] > max_x:
            continue
        if min_y is not None and bounds["y"] < min_y:
            continue
        if max_y is not None and bounds["y"] > max_y:
            continue
        if min_w is not None and bounds["w"] < min_w:
            continue
        if max_w is not None and bounds["w"] > max_w:
            continue
        if min_h is not None and bounds["h"] < min_h:
            continue
        if max_h is not None and bounds["h"] > max_h:
            continue
        results.append({
            "id": element.id,
            "fill": element.style.fill,
            "stroke": element.style.stroke,
            "bounds": bounds,
            "layer": element.layer,
            "z_index": element.z_index,
            "clip_to": element.clip_to,
        })
    return results
