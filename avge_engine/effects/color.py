"""
Color utility — hex ↔ HSL conversions and relative color transforms.

Used by shadow auto-mode (duplicate_element) and HSL offset styling (style_objects)
for cel-shading: "make this 20% darker" without knowing the hex value.
"""

from __future__ import annotations


def hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    """Convert #RRGGBB to (hue, saturation, lightness) in degrees/percent.

    Hue is in [0, 360), saturation and lightness in [0, 100].
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    mx = max(r, g, b)
    mn = min(r, g, b)
    l = (mx + mn) / 2.0

    if mx == mn:
        h = 0.0
        s = 0.0
    else:
        d = mx - mn
        s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = ((g - b) / d + (6.0 if g < b else 0.0)) * 60.0
        elif mx == g:
            h = ((b - r) / d + 2.0) * 60.0
        else:
            h = ((r - g) / d + 4.0) * 60.0

    return (h % 360, s * 100, l * 100)


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert (hue, saturation, lightness) in degrees/percent to #RRGGBB."""
    h = h % 360
    s = max(0.0, min(100.0, s)) / 100.0
    l = max(0.0, min(100.0, l)) / 100.0

    if s == 0.0:
        v = round(l * 255)
        return f"#{v:02x}{v:02x}{v:02x}"

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        t = t % 1.0
        if t < 1.0 / 6.0:
            return p + (q - p) * 6.0 * t
        if t < 1.0 / 2.0:
            return q
        if t < 2.0 / 3.0:
            return p + (q - p) * (2.0 / 3.0 - t) * 6.0
        return p

    q = l * (1.0 + s) if l < 0.5 else l + s - l * s
    p = 2.0 * l - q
    r = round(hue_to_rgb(p, q, h / 360.0 + 1.0 / 3.0) * 255)
    g = round(hue_to_rgb(p, q, h / 360.0) * 255)
    b = round(hue_to_rgb(p, q, h / 360.0 - 1.0 / 3.0) * 255)

    return f"#{r:02x}{g:02x}{b:02x}"


def darken_hex(
    hex_color: str,
    lightness_delta: float = -0.15,
    sat_delta: float = 0.08,
) -> str:
    """Return a darker, more saturated version of the given hex color.

    Defaults produce a visible cel-shadow difference (15% darker, 8% more
    saturated). Pass explicit values to tune per use case.

    Parameters are fractional HSL offsets:
      lightness_delta: -0.15 means 15 percentage points darker
      sat_delta: 0.08 means 8 percentage points more saturated

    Returns a new #RRGGBB string.
    """
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h, s + sat_delta * 100, l + lightness_delta * 100)


def apply_hsl_offset(
    hex_color: str,
    h_offset: float = 0.0,
    s_offset: float = 0.0,
    l_offset: float = 0.0,
) -> str:
    """Apply relative HSL offsets to a hex color.

    All offsets are in their natural units: hue in degrees, saturation
    and lightness in percentage points (e.g. l_offset=-20 means 20%
    darker, s_offset=10 means 10% more saturated).

    Returns a new #RRGGBB string.
    """
    h, s, l = hex_to_hsl(hex_color)
    return hsl_to_hex(h + h_offset, s + s_offset, l + l_offset)
