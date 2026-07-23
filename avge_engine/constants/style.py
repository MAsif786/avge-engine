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

STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "warm_shaded": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":1,"y2":1,"stops":[{"offset":0,"color":"#F5E6D0"},{"offset":1,"color":"#D4B898"}]}', "opacity": 1.0},
    "cool_shaded": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":1,"y2":1,"stops":[{"offset":0,"color":"#D0E4F0"},{"offset":1,"color":"#8AB0C8"}]}', "opacity": 1.0},
    "metallic": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#E8E8E8"},{"offset":0.5,"color":"#C0C0C0"},{"offset":1,"color":"#888888"}]}', "opacity": 1.0},
    "glow": {"fill": "#FFE8A0", "opacity": 0.6, "blend_mode": "screen"},
    "shadow": {"fill": "#000000", "opacity": 0.2, "blend_mode": "multiply"},
    "wood": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#D4A868"},{"offset":1,"color":"#A07840"}]}', "opacity": 1.0},
    "car_paint": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#CC3333"},{"offset":0.15,"color":"#991111"},{"offset":0.5,"color":"#CC3333"},{"offset":1,"color":"#660000"}]}', "opacity": 1.0},
    "deep_shadow": {"fill_gradient": '{"type":"radial","cx":0.5,"cy":0.5,"r":0.5,"stops":[{"offset":0,"color":"#000000"},{"offset":0.7,"color":"#000000"},{"offset":1,"color":"#FFFFFF"}]}', "opacity": 0.35, "blend_mode": "multiply"},
    "chrome": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#FFFFFF"},{"offset":0.3,"color":"#CCCCCC"},{"offset":0.5,"color":"#888888"},{"offset":0.7,"color":"#CCCCCC"},{"offset":1,"color":"#AAAAAA"}]}', "opacity": 1.0},
    "meme_title": {"fill": "#FFFFFF", "stroke": "#000000", "stroke_width": 0.003, "opacity": 1.0},
    "meme_caption": {"fill": "#FF0000", "opacity": 1.0},
    "label": {"fill": "#333333", "opacity": 1.0},
    "label_light": {"fill": "#888888", "opacity": 1.0},
    "title": {"fill": "#111111", "stroke": "#333333", "stroke_width": 0.001, "opacity": 1.0},
    "subtitle": {"fill": "#555555", "opacity": 0.85},
    "comic": {"fill": "#111111", "stroke": "#333333", "stroke_width": 0.001, "opacity": 1.0},
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
