"""Tests for avge_engine.geometry.procedural — pattern functions."""
from avge_engine.geometry.procedural import (
    radial_spread, offset_outline, guide_lines,
    distribute_points, bridge_shapes, interpolate_outlines,
    distribute_linear, apex_from_edge, parse_svg_path,
    segmented_chain,
)


def test_guide_lines():
    lines = guide_lines(bbox_x=0.2, bbox_y=0.1, bbox_w=0.6, bbox_h=0.8, ratios=[0.3, 0.5, 0.7])
    assert len(lines) == 3
    for l in lines:
        assert "start" in l and "end" in l and "ratio" in l
    assert abs(lines[0]["start"][1] - 0.34) < 0.01


def test_guide_lines_horizontal():
    lines = guide_lines(bbox_x=0.1, bbox_y=0.2, bbox_w=0.5, bbox_h=0.5, ratios=[0.5], horizontal=False)
    assert lines[0]["start"][0] == 0.35  # 0.1 + 0.5*0.5


def test_distribute_points():
    rect = [(0.1, 0.1), (0.5, 0.1), (0.9, 0.1), (0.9, 0.5), (0.1, 0.5)]
    pts = distribute_points(rect, count=5, edge="top_edge")
    assert len(pts) == 5
    for p in pts:
        assert abs(p[1] - 0.1) < 0.001


def test_distribute_points_left_edge():
    rect = [(0.1, 0.1), (0.5, 0.1), (0.9, 0.1), (0.9, 0.5), (0.1, 0.5)]
    pts = distribute_points(rect, count=3, edge="left_edge")
    assert len(pts) == 3
    for p in pts:
        assert abs(p[0] - 0.1) < 0.001


def test_radial_spread():
    rect = [(0.1, 0.3), (0.5, 0.3), (0.9, 0.3), (0.9, 0.7), (0.1, 0.7)]
    spikes = radial_spread(rect, count=5, anchor="top_edge", length_range=(0.08, 0.14),
                           width=0.025, angle_spread=30, taper=0.5, length_variance=True)
    assert len(spikes) == 5
    for s in spikes:
        assert len(s) == 6  # 6-point organic shape
        # Base points should be near the anchor edge
        base_y = s[0][1]
        assert abs(base_y - 0.3) < 0.06


def test_radial_spread_single():
    rect = [(0.1, 0.3), (0.5, 0.3), (0.9, 0.3), (0.9, 0.7), (0.1, 0.7)]
    spikes = radial_spread(rect, count=1, anchor="top_edge")
    assert len(spikes) == 1


def test_offset_outline_expand():
    rect = [(0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3)]
    expanded = offset_outline(rect, distance=0.02)
    assert len(expanded) > 0
    # Expanded rect should have min x < 0.1
    xs = [p[0] for p in expanded]
    assert min(xs) < 0.1


def test_offset_outline_contract():
    rect = [(0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3)]
    contracted = offset_outline(rect, distance=-0.01)
    assert contracted  # non-empty for valid contract
    xs = [p[0] for p in contracted]
    assert min(xs) > 0.09


def test_bridge_shapes():
    rect_a = [(0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3)]
    rect_b = [(0.25, 0.15), (0.45, 0.15), (0.45, 0.35), (0.25, 0.35)]
    bridge = bridge_shapes(rect_a, rect_b)
    assert len(bridge) > 0
    # Bridge should span from left of rect_a to right of rect_b
    xs = [p[0] for p in bridge]
    assert max(xs) > 0.4


def test_bridge_no_overlap():
    rect_a = [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)]
    rect_b = [(0.8, 0.1), (0.9, 0.1), (0.9, 0.2), (0.8, 0.2)]
    bridge = bridge_shapes(rect_a, rect_b)
    assert len(bridge) > 0  # convex hull connects them


def test_interpolate_outlines():
    square = [(0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3)]
    big_sq = [(0.05, 0.05), (0.35, 0.05), (0.35, 0.35), (0.05, 0.35)]
    steps = interpolate_outlines(square, big_sq, steps=3)
    assert len(steps) == 3
    for s in steps:
        assert len(s) == 4


def test_interpolate_different_sizes():
    tri = [(0.1, 0.1), (0.5, 0.8), (0.9, 0.1)]
    rect = [(0.1, 0.1), (0.5, 0.1), (0.5, 0.5), (0.1, 0.5)]
    steps = interpolate_outlines(tri, rect, steps=2)
    assert len(steps) == 2


def test_offset_outline_empty_for_tiny_negative():
    rect = [(0.1, 0.1), (0.11, 0.1), (0.11, 0.11), (0.1, 0.11)]
    result = offset_outline(rect, distance=-0.05)
    # Very small rect with large negative offset may produce empty
    assert isinstance(result, list)


def test_distribute_linear():
    pts = distribute_linear(start=(0.1, 0.5), end=(0.9, 0.5), count=5)
    assert len(pts) == 5
    assert abs(pts[0][0] - 0.1) < 0.001
    assert abs(pts[-1][0] - 0.9) < 0.001
    assert abs(pts[1][0] - 0.3) < 0.001


def test_distribute_linear_single():
    pts = distribute_linear(start=(0.1, 0.5), end=(0.9, 0.5), count=2)
    assert len(pts) == 2


def test_apex_from_edge_top():
    wall = [(0.2, 0.5), (0.5, 0.5), (0.5, 0.7), (0.2, 0.7)]
    roof = apex_from_edge(wall, edge="top")
    assert len(roof) == 3  # triangle
    assert roof[0][1] < 0.5  # apex above wall top edge


def test_apex_from_edge_bottom():
    wall = [(0.2, 0.3), (0.5, 0.3), (0.5, 0.5), (0.2, 0.5)]
    roof = apex_from_edge(wall, edge="bottom")
    assert len(roof) == 3
    # Apex should be below (greater y)
    assert roof[0][1] > 0.5


def test_apex_from_edge_explicit_offset():
    wall = [(0.2, 0.5), (0.5, 0.5), (0.5, 0.7), (0.2, 0.7)]
    roof = apex_from_edge(wall, edge="top", apex_offset=0.03)
    assert len(roof) == 3
    assert abs(roof[0][1] - (0.5 - 0.03)) < 0.001


def test_apex_from_edge_inset_overhang():
    """Positive inset makes roof wider than wall (overhang)."""
    wall = [(0.2, 0.5), (0.5, 0.5), (0.5, 0.7), (0.2, 0.7)]
    roof = apex_from_edge(wall, edge="top", inset=0.015)
    assert len(roof) == 3
    # Base should be 0.015 wider on each side
    base_xs = sorted([roof[1][0], roof[2][0]])
    assert abs(base_xs[0] - (0.2 - 0.015)) < 0.001, f"left edge {base_xs[0]} != {0.2 - 0.015}"
    assert abs(base_xs[1] - (0.5 + 0.015)) < 0.001, f"right edge {base_xs[1]} != {0.5 + 0.015}"
    # Apex should be above midpoint of EXPANDED base
    assert abs(roof[0][0] - 0.35) < 0.001  # apex x unchanged (midpoint of expanded base)


def test_parse_svg_path_rect():
    """Parse a simple SVG rectangle path."""
    pts = parse_svg_path("M 0.1 0.1 L 0.9 0.1 L 0.9 0.9 L 0.1 0.9 Z")
    assert len(pts) >= 4
    assert abs(pts[0][0] - 0.1) < 0.001
    assert abs(pts[1][0] - 0.9) < 0.001


def test_parse_svg_path_cubic():
    """Parse SVG path with a cubic bezier curve."""
    pts = parse_svg_path("M 0.1 0.5 C 0.3 0.8 0.7 0.2 0.9 0.5")
    assert len(pts) > 3
    # Points should span from 0.1 to 0.9
    assert pts[0][0] < pts[-1][0]


def test_parse_svg_path_empty():
    assert parse_svg_path("") == []
    assert parse_svg_path("   ") == []


def test_segmented_chain_single():
    """A single straight segment (no bend)."""
    segs = [{"length": 0.1, "width_start": 0.04, "width_end": 0.04, "angle_delta": 0}]
    result = segmented_chain((0.5, 0.5), (1, 0), segs)
    assert len(result["segments"]) == 1
    assert len(result["joints"]) == 0
    # Segment should be roughly horizontal
    xs = [p[0] for p in result["segments"][0]]
    assert max(xs) >= 0.6  # extends right


def test_segmented_chain_bent():
    """Two segments with a bend (like an arm)."""
    segs = [
        {"length": 0.12, "width_start": 0.05, "width_end": 0.04, "angle_delta": 0},
        {"length": 0.1, "width_start": 0.04, "width_end": 0.03, "angle_delta": -35},
    ]
    result = segmented_chain((0.3, 0.5), (1, 0), segs, joint_radius=0.015)
    assert len(result["segments"]) == 2
    assert len(result["joints"]) == 1  # one joint between segments
    # Both segments should have 6-point outlines
    assert all(len(s) == 6 for s in result["segments"])


def test_segmented_chain_fanned():
    """Multiple chains fanned from the same anchor (curled fingers)."""
    segs = [
        {"length": 0.06, "width_start": 0.025, "width_end": 0.02, "angle_delta": 0},
        {"length": 0.05, "width_start": 0.02, "width_end": 0.015, "angle_delta": -20},
    ]
    # Simulate count=5 by calling with different angle_offsets
    result = segmented_chain((0.5, 0.5), (1, 0), segs, angle_offset=0)
    assert len(result["segments"]) == 2
    result2 = segmented_chain((0.5, 0.5), (1, 0), segs, angle_offset=15)
    assert result2["segments"][0][0][0] != result["segments"][0][0][0]  # different position


