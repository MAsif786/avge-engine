"""Color helpers shared by style tools."""
from __future__ import annotations

from avge_engine.utils.math_utils import clamp01


def hex_to_rgb(color: str) -> tuple[int, int, int] | None:
    """Parse a #RRGGBB color string into RGB channels."""
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return None
    try:
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    except ValueError:
        return None


def mix_hex(color: str, target: str, amount: float) -> str | None:
    """Blend two #RRGGBB colors by amount 0..1."""
    src = hex_to_rgb(color)
    dst = hex_to_rgb(target)
    if src is None or dst is None:
        return None
    t = clamp01(amount)
    rgb = [round(src[i] + (dst[i] - src[i]) * t) for i in range(3)]
    return "#{:02X}{:02X}{:02X}".format(*rgb)

