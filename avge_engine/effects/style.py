"""
Style engine — fill, stroke, opacity, and effects resolution.

§6.3: Effects are composable and order-preserving. The engine applies
them in array order (first = bottom, last = top in paint order).

Gradient fills (§6.3): fill may be a hex string or a dict with
gradient parameters. Two types are supported:
  Linear: {"type": "linear", "x1":0, "y1":0, "x2":1, "y2":0,
            "stops": [{"offset":0, "color":"#000"}, {"offset":1, "color":"#FFF"}]}
  Radial: {"type": "radial", "cx":0.5, "cy":0.5, "r":0.5,
            "stops": [...]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ── Gradient type ───────────────────────────────────────────────────

type GradientDef = dict[str, Any]
"""A gradient definition dict. See module docstring for structure."""


def is_gradient(value: Any) -> bool:
    """Check if a value is a gradient dict rather than a hex string."""
    return isinstance(value, dict) and "type" in value and "stops" in value


def validate_gradient(g: GradientDef) -> list[str]:
    """Validate a gradient definition. Returns list of error messages (empty = valid)."""
    errs: list[str] = []
    gtype = g.get("type")
    if gtype not in ("linear", "radial"):
        errs.append(f"gradient type must be 'linear' or 'radial', got '{gtype}'")
        return errs  # can't validate further

    stops = g.get("stops", [])
    if not stops or len(stops) < 2:
        errs.append("gradient must have at least 2 stops")
        return errs

    for i, stop in enumerate(stops):
        if "offset" not in stop:
            errs.append(f"stop {i} missing 'offset'")
        elif not (0.0 <= stop["offset"] <= 1.0):
            errs.append(f"stop {i} offset {stop['offset']} out of range [0,1]")
        color = stop.get("color", "")
        if not _is_hex(color):
            errs.append(f"stop {i} invalid color '{color}'")

    if gtype == "linear":
        for key in ("x1", "y1", "x2", "y2"):
            if key not in g:
                errs.append(f"linear gradient missing '{key}'")

    if gtype == "radial":
        for key in ("cx", "cy", "r"):
            if key not in g:
                errs.append(f"radial gradient missing '{key}'")

    return errs


def resolve_fill(fill: str | GradientDef | None) -> str:
    """Resolve a fill value to an SVG-compatible string.

    Returns "none", a hex color, or a gradient reference URL like
    "url(#grad_xxx)".
    """
    if fill is None:
        return "none"
    if is_gradient(fill):
        return f"url(#{_gradient_id(fill)})"
    return fill  # hex string


# ── Style dataclass ────────────────────────────────────────────────

GLOBAL_GRADIENT_COUNTER: int = 0


def _gradient_id(g: GradientDef) -> str:
    """Generate a stable-ish gradient ID based on content hash."""
    raw = json.dumps(g, sort_keys=True)
    h = str(hash(raw) & 0xFFFFFFFF)
    return f"grad_{h}"


@dataclass(frozen=True)
class Style:
    """Visual style for a region.

    Fill may be:
    - None (transparent / no fill)
    - A hex color string like "#FF0000"
    - A gradient dict {"type": "linear"|"radial", ...}

    Stroke is always a hex color or None.
    The engine never interprets semantic meaning from style values.
    """

    fill: str | GradientDef | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float = 0.005
    opacity: float = 1.0
    blend_mode: str | None = None
    stroke_linecap: str | None = None
    stroke_dasharray: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "stroke_width", max(0.0, min(0.1, self.stroke_width)))
        object.__setattr__(self, "opacity", max(0.0, min(1.0, self.opacity)))
        # Normalize empty stroke_dasharray to None
        if self.stroke_dasharray is not None and self.stroke_dasharray.strip() == "":
            object.__setattr__(self, "stroke_dasharray", None)
        # Validate stroke_linecap
        if self.stroke_linecap is not None and self.stroke_linecap not in ("butt", "round", "square"):
            raise ValueError(f"Invalid stroke_linecap: {self.stroke_linecap}. Valid: butt, round, square")
        # Validate fill
        if self.fill is not None:
            if self.fill == "none" or self.fill == "transparent":
                object.__setattr__(self, "fill", None)
            elif is_gradient(self.fill):
                errs = validate_gradient(self.fill)
                if errs:
                    raise ValueError(f"Invalid gradient: {'; '.join(errs)}")
            elif isinstance(self.fill, dict):
                raise ValueError(
                    f"Invalid gradient fill: dict must contain 'type' and 'stops' keys, "
                    f"got keys: {list(self.fill.keys())}"
                )
            elif not _is_color(self.fill):
                raise ValueError(f"Invalid fill: {self.fill}")
        # Validate stroke — "none" maps to None (no stroke)
        if self.stroke is not None:
            if self.stroke == "none":
                object.__setattr__(self, "stroke", None)
            elif not _is_color(self.stroke):
                raise ValueError(f"Invalid stroke color: {self.stroke}")
        # Validate blend mode
        if self.blend_mode is not None:
            valid = ("normal","multiply","screen","overlay","darken","lighten",
                     "color-dodge","color-burn","soft-light","hard-light")
            if self.blend_mode not in valid:
                raise ValueError(f"Invalid blend_mode: {self.blend_mode}. Valid: {valid}")


def resolve_stroke(stroke: str | None) -> str:
    """Resolve a stroke value to an SVG-compatible string."""
    if stroke is None:
        return "none"
    return stroke


def _is_hex(value: str) -> bool:
    """Check if value is a valid hex color (#RGB, #RRGGBB, or #RRGGBBAA)."""
    if not value.startswith("#") or len(value) not in (4, 7, 9):
        return False
    try:
        int(value[1:], 16)
        return True
    except ValueError:
        return False


def _is_color(value: str) -> bool:
    """Check if value is a valid CSS color (hex, rgba, hsla, or named)."""
    if _is_hex(value):
        return True
    if value.startswith("rgba(") and value.endswith(")"):
        parts = [p.strip() for p in value[5:-1].split(",")]
        if len(parts) != 4:
            return False
        try:
            r, g, b, a = int(parts[0]), int(parts[1]), int(parts[2]), float(parts[3])
            return 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255 and 0.0 <= a <= 1.0
        except (ValueError, IndexError):
            return False
    if value.startswith("hsla(") and value.endswith(")"):
        parts = [p.strip() for p in value[5:-1].split(",")]
        if len(parts) != 4:
            return False
        try:
            h, s, l, a = int(parts[0]), int(parts[1].rstrip("%")), int(parts[2].rstrip("%")), float(parts[3])
            return 0 <= h <= 360 and 0 <= s <= 100 and 0 <= l <= 100 and 0.0 <= a <= 1.0
        except (ValueError, IndexError):
            return False
    # Named CSS colors
    _NAMED = {"none", "transparent", "black", "white", "red", "blue", "green",
              "yellow", "orange", "purple", "pink", "gray", "grey", "brown",
              "cyan", "magenta", "navy", "teal", "olive", "maroon", "silver",
              "lime", "aqua", "fuchsia", "gold", "coral", "indigo", "violet",
              "turquoise", "plum", "tan", "salmon", "crimson", "orchid",
              "khaki", "lavender", "mistyrose", "peachpuff"}
    return value.strip().lower() in _NAMED


# ── Gradient SVG generation ────────────────────────────────────────

def gradient_to_svg_def(g: GradientDef) -> str:
    """Generate an SVG <linearGradient> or <radialGradient> element string."""
    gid = _gradient_id(g)
    stops_xml = "".join(
        f'    <stop offset="{s["offset"]}" stop-color="{s["color"]}"/>\n'
        for s in g.get("stops", [])
    )
    if g["type"] == "linear":
        return (
            f'  <linearGradient id="{gid}" '
            f'x1="{g.get("x1", 0)}" y1="{g.get("y1", 0)}" '
            f'x2="{g.get("x2", 1)}" y2="{g.get("y2", 1)}">\n'
            f'{stops_xml}  </linearGradient>\n'
        )
    else:  # radial
        return (
            f'  <radialGradient id="{gid}" '
            f'cx="{g.get("cx", 0.5)}" cy="{g.get("cy", 0.5)}" '
            f'r="{g.get("r", 0.5)}">\n'
            f'{stops_xml}  </radialGradient>\n'
        )
