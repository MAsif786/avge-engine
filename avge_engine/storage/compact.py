"""Compact persisted document format helpers.

The public API and in-memory scene graph use the full RegionNode-compatible
shape. Storage can use a smaller representation as long as load normalizes it
back to the full shape before SceneGraph hydrates models.
"""

from __future__ import annotations

import json
from typing import Any


FORMAT_NAME = "avge.compact.v1"
OUTLINE_QUANTIZATION = 100_000

_DEFAULT_STYLE = {
    "fill": "#CCCCCC",
    "stroke": "#333333",
    "stroke_width": 0.005,
    "opacity": 1.0,
    "blend_mode": None,
    "stroke_linecap": None,
    "stroke_dasharray": None,
    "blur": 0.0,
}

_DEFAULT_CONSTRAINTS = {
    "smoothness": 0.5,
    "closed": True,
    "corner_style": "round",
    "tensions": None,
    "handle_in": None,
    "handle_out": None,
}

_DEFAULT_TRANSFORM = {
    "translate": [0.0, 0.0],
    "rotate": 0.0,
    "scale": [1.0, 1.0],
}

_DEFAULT_REGION = {
    "type": "region",
    "layer": "default",
    "z_index": 0,
    "clip_to": None,
    "metadata": {},
    "version": 1,
    "primitive": None,
}


def encode_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Return a compact storage representation for a full document snapshot."""
    if _looks_compact(data):
        data = decode_snapshot(data)

    regions = data.get("regions", {})
    style_ids: dict[str, str] = {}
    styles: dict[str, dict[str, Any]] = {}
    compact_regions: dict[str, dict[str, Any]] = {}

    for rid, region in regions.items():
        compact = _compact_region(region)
        style = _compact_style(region.get("style", {}))
        if style:
            style_key = json.dumps(style, sort_keys=True, separators=(",", ":"), default=str)
            style_id = style_ids.get(style_key)
            if style_id is None:
                style_id = f"s{len(style_ids)}"
                style_ids[style_key] = style_id
                styles[style_id] = style
            compact["style_id"] = style_id
        compact_regions[rid] = compact

    metadata = dict(data.get("metadata", {}))
    metadata["storage_format"] = FORMAT_NAME
    compact_doc = {
        "document": data.get("document", {}),
        "regions": compact_regions,
        "metadata": metadata,
        "groups": data.get("groups", {}),
    }
    if styles:
        compact_doc["styles"] = styles
    return compact_doc


def decode_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize old or compact storage data into the full snapshot shape."""
    styles = data.get("styles", {})
    regions: dict[str, dict[str, Any]] = {}
    for rid, region in data.get("regions", {}).items():
        regions[rid] = _expand_region(rid, region, styles)
    result = dict(data)
    result["regions"] = regions
    result.pop("styles", None)
    return result


def _looks_compact(data: dict[str, Any]) -> bool:
    if data.get("styles"):
        return True
    if data.get("metadata", {}).get("storage_format") == FORMAT_NAME:
        return True
    return any("outline_q" in region for region in data.get("regions", {}).values())


def _compact_region(region: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {"id": region.get("id")}

    for key, default in _DEFAULT_REGION.items():
        value = region.get(key, default)
        if value != default:
            compact[key] = value

    if region.get("outline_q"):
        compact["outline_q"] = list(region["outline_q"])
    elif (outline := region.get("outline") or []):
        compact["outline_q"] = encode_outline_q(outline)

    constraints = _omit_defaults(region.get("constraints") or {}, _DEFAULT_CONSTRAINTS)
    if constraints:
        compact["constraints"] = constraints

    transform = _omit_defaults(_normalize_transform(region.get("transform") or {}), _DEFAULT_TRANSFORM)
    if transform:
        compact["transform"] = transform

    return compact


def _expand_region(
    rid: str,
    region: dict[str, Any],
    styles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    # Old documents already have the full shape. Normalize anyway so omitted
    # defaults from compact documents are restored for RegionNode validation.
    expanded = dict(_DEFAULT_REGION)
    expanded.update(region)
    expanded["id"] = expanded.get("id") or rid

    if "outline_q" in expanded:
        expanded["outline"] = _decode_outline(
            expanded.pop("outline_q"),
            int(expanded.pop("outline_q_scale", OUTLINE_QUANTIZATION)),
        )
    else:
        expanded["outline"] = expanded.get("outline") or []

    style_id = expanded.pop("style_id", None)
    if style_id is not None:
        expanded["style"] = _normalize_style(styles.get(style_id, {}))
    else:
        expanded["style"] = _normalize_style(expanded.get("style") or {})

    expanded["constraints"] = {
        **_DEFAULT_CONSTRAINTS,
        **(expanded.get("constraints") or {}),
    }
    expanded["transform"] = {
        **_DEFAULT_TRANSFORM,
        **_normalize_transform(expanded.get("transform") or {}),
    }
    expanded["metadata"] = expanded.get("metadata") or {}
    expanded["clip_to"] = expanded.get("clip_to")
    expanded["primitive"] = expanded.get("primitive")
    return expanded


def _normalize_style(style: dict[str, Any]) -> dict[str, Any]:
    return {**_DEFAULT_STYLE, **style}


def _compact_style(style: dict[str, Any]) -> dict[str, Any]:
    return _omit_defaults(_normalize_style(style), _DEFAULT_STYLE)


def _normalize_transform(transform: dict[str, Any]) -> dict[str, Any]:
    normalized = {**_DEFAULT_TRANSFORM, **transform}
    if isinstance(normalized.get("translate"), tuple):
        normalized["translate"] = list(normalized["translate"])
    if isinstance(normalized.get("scale"), tuple):
        normalized["scale"] = list(normalized["scale"])
    return normalized


def _omit_defaults(values: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        normalized = list(value) if isinstance(value, tuple) else value
        default = defaults.get(key)
        if isinstance(default, tuple):
            default = list(default)
        if normalized != default:
            result[key] = normalized
    return result


def encode_outline_q(outline: list[Any]) -> list[int]:
    """Encode normalized outline points as a flat quantized integer array."""
    scale = OUTLINE_QUANTIZATION
    flat: list[int] = []
    for point in outline:
        flat.append(round(float(point[0]) * scale))
        flat.append(round(float(point[1]) * scale))
    return flat


def decode_outline_q(
    values: list[int],
    scale: int = OUTLINE_QUANTIZATION,
) -> list[tuple[float, float]]:
    """Decode a flat quantized integer array into normalized outline points."""
    if len(values) % 2 != 0:
        raise ValueError("outline_q must contain x/y pairs")
    return [
        (round(values[i] / scale, 6), round(values[i + 1] / scale, 6))
        for i in range(0, len(values), 2)
    ]


_decode_outline = decode_outline_q
