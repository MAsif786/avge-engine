"""Style constants shared by style controllers and services."""
from __future__ import annotations

from typing import Any

LAYER_ROLE_Z = {
    "background": -1000,
    "sketch": -700,
    "guide": -650,
    "base_color": -100,
    "texture": 120,
    "shadow": 160,
    "highlight": 220,
    "glow": 260,
    "line_art": 320,
    "fx": 380,
    "mask": 500,
}

MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    "glass": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#F8FFFF"},
            {"offset": 0.35, "color": "#BFDDE6"},
            {"offset": 1.0, "color": "#6F9DAA"},
        ]},
        "stroke": "#D9F3F8", "stroke_width": 0.002, "opacity": 0.58, "blend_mode": "screen",
    },
    "brushed_metal": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 0, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#F5F6F4"},
            {"offset": 0.18, "color": "#8F989B"},
            {"offset": 0.32, "color": "#D4D8D7"},
            {"offset": 0.58, "color": "#6B7377"},
            {"offset": 1.0, "color": "#C9CECD"},
        ]},
        "stroke": "#596064", "stroke_width": 0.0025, "opacity": 1.0,
    },
    "concrete": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#D7D4C8"},
            {"offset": 0.55, "color": "#A9AA9F"},
            {"offset": 1.0, "color": "#7E8379"},
        ]},
        "stroke": "#6F746C", "stroke_width": 0.002, "opacity": 1.0,
    },
    "wood": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 0, "stops": [
            {"offset": 0.0, "color": "#E3B06B"},
            {"offset": 0.28, "color": "#9B622E"},
            {"offset": 0.52, "color": "#D1974E"},
            {"offset": 1.0, "color": "#70451F"},
        ]},
        "stroke": "#5E3719", "stroke_width": 0.002, "opacity": 1.0,
    },
    "tile": {
        "fill_gradient": {"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "stops": [
            {"offset": 0.0, "color": "#F4EEE2"},
            {"offset": 0.7, "color": "#CDBFA8"},
            {"offset": 1.0, "color": "#A99B83"},
        ]},
        "stroke": "#8D826F", "stroke_width": 0.0025, "opacity": 1.0,
    },
    "foliage": {
        "fill_gradient": {"type": "radial", "cx": 0.42, "cy": 0.34, "r": 0.72, "stops": [
            {"offset": 0.0, "color": "#D8E88E"},
            {"offset": 0.45, "color": "#6EA03F"},
            {"offset": 1.0, "color": "#244C2E"},
        ]},
        "stroke": "#2C5631", "stroke_width": 0.0018, "opacity": 1.0,
    },
}

