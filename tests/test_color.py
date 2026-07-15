"""Tests for avge_engine.effects.color — HSL color transforms."""
from avge_engine.effects.color import hex_to_hsl, hsl_to_hex, darken_hex, apply_hsl_offset


def test_hex_to_hsl_roundtrip():
    colors = ["#FF0000", "#00FF00", "#0000FF", "#000000", "#FFFFFF",
              "#6B7B4A", "#E8C8A0", "#1A2744", "#CC2222", "#B8B8C0"]
    for c in colors:
        h, s, l = hex_to_hsl(c)
        back = hsl_to_hex(h, s, l)
        assert back.lower() == c.lower(), f"Roundtrip failed for {c}: got {back}"


def test_darken_hex():
    darker = darken_hex("#6B7B4A")
    assert darker != "#6B7B4A"
    h, s, l = hex_to_hsl(darker)
    _, _, orig_l = hex_to_hsl("#6B7B4A")
    assert l < orig_l, "Darkened color should have lower lightness"


def test_apply_hsl_offset():
    shifted = apply_hsl_offset("#CC2222", h_offset=180)
    h, s, l = hex_to_hsl(shifted)
    assert abs(h - 180) < 5, f"Hue should shift ~180°, got {h}"


def test_apply_lightness_offset():
    result = apply_hsl_offset("#6B7B4A", l_offset=-20)
    assert result != "#6B7B4A"
    h, s, l = hex_to_hsl(result)
    _, _, orig_l = hex_to_hsl("#6B7B4A")
    assert l < orig_l


def test_black_white():
    assert apply_hsl_offset("#000000", l_offset=10) == "#1a1a1a"
    assert apply_hsl_offset("#FFFFFF", l_offset=-10) == "#e6e6e6"


def test_darken_noop_zero_delta():
    c = "#6B7B4A"
    assert darken_hex(c, lightness_delta=0, sat_delta=0) == c.lower()
