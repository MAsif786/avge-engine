"""Digital brush preset catalog used by style tools."""
from __future__ import annotations

from typing import Any, Literal


BrushName = Literal[
    "pencil", "ink", "g_pen", "mapping_pen", "turnip_pen", "technical_pen",
    "brush_pen", "calligraphy_pen", "vector_pen",
    "flat", "round", "paint_brush", "airbrush", "soft", "hard",
    "watercolor", "gouache", "oil", "chalk", "blend_brush", "mixer_brush",
    "texture", "fabric_brush", "stone_brush", "wood_grain_brush",
    "metal_brush", "pattern_brush",
    "hair", "grass_leaf", "cloud", "water_brush", "particle_fx",
    "rain_brush", "snow_brush", "fire_brush", "smoke_brush", "spark_brush",
]


BRUSH_PRESETS: dict[str, dict[str, Any]] = {
    "pencil": {"group": "line_art", "stroke": "#3E3E3E", "stroke_width": 2.0, "opacity": 0.68, "linecap": "round", "rough": True},
    "ink": {"group": "line_art", "stroke": "#171717", "stroke_width": 3.0, "opacity": 1.0, "linecap": "round"},
    "g_pen": {"group": "line_art", "stroke": "#101010", "stroke_width": 4.0, "opacity": 1.0, "linecap": "round", "pressure": True},
    "mapping_pen": {"group": "line_art", "stroke": "#111111", "stroke_width": 1.25, "opacity": 1.0, "linecap": "round"},
    "turnip_pen": {"group": "line_art", "stroke": "#141414", "stroke_width": 3.0, "opacity": 1.0, "linecap": "round", "pressure": True},
    "technical_pen": {"group": "line_art", "stroke": "#101010", "stroke_width": 1.5, "opacity": 1.0, "linecap": "butt"},
    "brush_pen": {"group": "line_art", "stroke": "#111111", "stroke_width": 5.5, "opacity": 0.96, "linecap": "round", "pressure": True, "rough": True},
    "calligraphy_pen": {"group": "line_art", "stroke": "#101010", "stroke_width": 6.5, "opacity": 0.94, "linecap": "round", "pressure": True},
    "vector_pen": {"group": "line_art", "stroke": "#111111", "stroke_width": 2.0, "opacity": 1.0, "linecap": "round"},
    "flat": {"group": "paint", "stroke": "#2C2C2C", "stroke_width": 6.0, "opacity": 0.95, "linecap": "butt"},
    "round": {"group": "paint", "stroke": "#222222", "stroke_width": 5.0, "opacity": 0.95, "linecap": "round"},
    "paint_brush": {"group": "paint", "stroke": "#2F2A26", "stroke_width": 7.0, "opacity": 0.9, "linecap": "round", "rough": True},
    "airbrush": {"group": "paint", "stroke": "#FFFFFF", "stroke_width": 18.0, "opacity": 0.22, "linecap": "round", "blur": 8.0, "blend_mode": "screen"},
    "soft": {"group": "paint", "stroke": "#FFFFFF", "stroke_width": 10.0, "opacity": 0.35, "linecap": "round", "blur": 4.0},
    "hard": {"group": "paint", "stroke": "#222222", "stroke_width": 4.0, "opacity": 1.0, "linecap": "butt"},
    "watercolor": {"group": "paint", "stroke": "#426B8F", "stroke_width": 7.0, "opacity": 0.42, "linecap": "round", "blur": 1.6},
    "gouache": {"group": "paint", "stroke": "#4F4A43", "stroke_width": 8.0, "opacity": 0.82, "linecap": "round"},
    "oil": {"group": "paint", "stroke": "#564B3F", "stroke_width": 9.0, "opacity": 0.86, "linecap": "round", "rough": True},
    "chalk": {"group": "paint", "stroke": "#F0EEE7", "stroke_width": 6.0, "opacity": 0.62, "linecap": "round", "rough": True},
    "blend_brush": {"group": "paint", "stroke": "#FFFFFF", "stroke_width": 14.0, "opacity": 0.26, "linecap": "round", "blur": 6.0, "blend_mode": "soft-light"},
    "mixer_brush": {"group": "paint", "stroke": "#D8C7A6", "stroke_width": 11.0, "opacity": 0.45, "linecap": "round", "rough": True, "blend_mode": "overlay"},
    "texture": {"group": "texture", "stroke": "#4B4B4B", "stroke_width": 3.0, "opacity": 0.48, "linecap": "round", "rough": True},
    "fabric_brush": {"group": "texture", "stroke": "#6C7480", "stroke_width": 2.0, "opacity": 0.42, "linecap": "butt", "rough": True},
    "stone_brush": {"group": "texture", "stroke": "#6D6B63", "stroke_width": 3.5, "opacity": 0.5, "linecap": "round", "rough": True},
    "wood_grain_brush": {"group": "texture", "stroke": "#6A3F1C", "stroke_width": 2.2, "opacity": 0.62, "linecap": "round", "rough": True},
    "metal_brush": {"group": "texture", "stroke": "#DCE3E4", "stroke_width": 1.7, "opacity": 0.55, "linecap": "butt", "blend_mode": "screen"},
    "pattern_brush": {"group": "texture", "stroke": "#303030", "stroke_width": 2.5, "opacity": 0.65, "linecap": "round", "rough": True},
    "hair": {"group": "natural", "stroke": "#2B1D18", "stroke_width": 1.15, "opacity": 0.9, "linecap": "round", "pressure": True},
    "grass_leaf": {"group": "natural", "stroke": "#315F34", "stroke_width": 1.8, "opacity": 0.82, "linecap": "round", "pressure": True},
    "cloud": {"group": "natural", "stroke": "#FFFFFF", "stroke_width": 12.0, "opacity": 0.36, "linecap": "round", "blur": 6.0, "blend_mode": "screen"},
    "water_brush": {"group": "natural", "stroke": "#7DE8FF", "stroke_width": 4.5, "opacity": 0.48, "linecap": "round", "blend_mode": "screen"},
    "particle_fx": {"group": "fx", "stroke": "#FFFFFF", "stroke_width": 2.0, "opacity": 0.72, "linecap": "round", "blend_mode": "screen"},
    "rain_brush": {"group": "fx", "stroke": "#B8E9FF", "stroke_width": 1.2, "opacity": 0.54, "linecap": "round", "blend_mode": "screen"},
    "snow_brush": {"group": "fx", "stroke": "#FFFFFF", "stroke_width": 3.5, "opacity": 0.72, "linecap": "round", "blur": 1.1, "blend_mode": "screen"},
    "fire_brush": {"group": "fx", "stroke": "#FF7A1A", "stroke_width": 6.0, "opacity": 0.75, "linecap": "round", "blur": 2.2, "blend_mode": "screen", "rough": True},
    "smoke_brush": {"group": "fx", "stroke": "#B8B8B8", "stroke_width": 12.0, "opacity": 0.28, "linecap": "round", "blur": 5.5, "blend_mode": "screen"},
    "spark_brush": {"group": "fx", "stroke": "#FFE98A", "stroke_width": 2.2, "opacity": 0.82, "linecap": "round", "blend_mode": "screen"},
}

BRUSH_GROUPS = ("line_art", "paint", "texture", "natural", "fx")


def brush_preset_catalog(group: str | None = None, include_details: bool = True) -> dict[str, Any]:
    """Return brush presets grouped by purpose for tool discovery."""
    groups = BRUSH_GROUPS if group in (None, "all") else (group,)
    result: dict[str, Any] = {}
    for group_name in groups:
        presets = {
            name: cfg for name, cfg in BRUSH_PRESETS.items()
            if cfg.get("group") == group_name
        }
        if include_details:
            result[group_name] = {
                name: {
                    "stroke": cfg["stroke"],
                    "stroke_width": cfg["stroke_width"],
                    "opacity": cfg["opacity"],
                    "linecap": cfg.get("linecap", "round"),
                    "pressure": bool(cfg.get("pressure", False)),
                    "rough": bool(cfg.get("rough", False)),
                    "blur": cfg.get("blur", 0.0),
                    "blend_mode": cfg.get("blend_mode"),
                }
                for name, cfg in presets.items()
            }
        else:
            result[group_name] = list(presets)
    return result
