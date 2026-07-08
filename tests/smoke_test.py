"""
Smoke test: exercises all 5 MCP tools directly (standalone, no LLM).

Run: .venv/bin/python tests/smoke_test.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from avge_mvp.scene import SceneGraph, CurveConstraints, Style
from avge_mvp.renderer import svg_serialize, rasterize_to_base64
from avge_mvp.curve_engine import fit_curves, sample_curve


def test_create_document():
    """Test document creation."""
    scene = SceneGraph()
    doc = scene.create_document(width=800, height=600, background="#F0F0F0")
    assert doc.id.startswith("doc_")
    assert doc.width == 800
    assert doc.height == 600
    assert doc.background == "#F0F0F0"
    print("  ✓ create_document")


def test_create_region():
    """Test creating a region with an outline."""
    scene = SceneGraph()
    scene.create_document()

    # Simple triangle
    region = scene.create_region(
        region_id="triangle",
        outline=[(0.1, 0.1), (0.5, 0.8), (0.9, 0.1)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#FF0000", stroke="#000000"),
    )
    assert region.id == "triangle"
    assert len(region.outline) == 3
    assert region.style.fill == "#FF0000"
    print("  ✓ create_region")


def test_style_objects():
    """Test restyling a region."""
    scene = SceneGraph()
    scene.create_document()
    scene.create_region(region_id="r1", outline=[(0, 0), (1, 0), (1, 1), (0, 1)])

    affected = scene.style_objects(["r1"], fill="#00FF00", stroke_width=0.02)
    assert affected == ["r1"]
    r1 = scene.get_region("r1")
    assert r1.style.fill == "#00FF00"
    assert r1.style.stroke_width == 0.02
    print("  ✓ style_objects")


def test_describe_scene():
    """Test scene description output."""
    scene = SceneGraph()
    scene.create_document()
    scene.create_region(region_id="r1", outline=[(0, 0), (1, 0), (1, 1), (0, 1)])

    desc = scene.describe_scene(detail="summary")
    assert desc["region_count"] == 1
    assert desc["regions"][0]["id"] == "r1"
    assert desc["regions"][0]["outline_point_count"] == 4
    print("  ✓ describe_scene")


def test_curve_fitting():
    """Test closed-form Catmull-Rom → Bézier fitting."""
    # Five-pointed star outline
    import math

    star_pts = []
    for i in range(5):
        angle = math.pi / 2 + i * 4 * math.pi / 5
        star_pts.append((0.5 + 0.4 * math.cos(angle), 0.5 + 0.4 * math.sin(angle)))
        angle2 = angle + 2 * math.pi / 5
        star_pts.append((0.5 + 0.15 * math.cos(angle2), 0.5 + 0.15 * math.sin(angle2)))

    segments = fit_curves(star_pts, closed=True, smoothness=0.3)
    assert len(segments) == len(star_pts)  # one segment per outline point (closed)
    for seg in segments:
        assert len(seg) == 4  # cubic Bézier: P0, P1, P2, P3

    points = sample_curve(segments, samples_per_segment=16)
    assert len(points) > 0
    print("  ✓ curve_fitting")


def test_renderer():
    """Test SVG serialization and rasterization."""
    scene = SceneGraph()
    scene.create_document(width=500, height=500)

    # Draw a simple square
    scene.create_region(
        region_id="square",
        outline=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#4488FF", stroke="#222222", stroke_width=0.01),
    )

    svg = svg_serialize(scene)
    assert "svg" in svg
    assert "4488FF" in svg
    assert "222222" in svg
    print(f"  ✓ svg_serialize ({len(svg)} chars)")

    # Test rasterization
    b64 = rasterize_to_base64(svg, scale=0.5)
    assert len(b64) > 100
    print(f"  ✓ rasterize_to_base64 ({len(b64)} b64 chars)")


def test_scene_with_multiple_regions():
    """Test multi-region scene (house icon)."""
    scene = SceneGraph()
    scene.create_document()

    # House body
    scene.create_region(
        region_id="body",
        outline=[(0.2, 0.4), (0.8, 0.4), (0.8, 0.9), (0.2, 0.9)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#E8D4B0", stroke="#333"),
    )
    # Roof (triangle)
    scene.create_region(
        region_id="roof",
        outline=[(0.15, 0.4), (0.5, 0.1), (0.85, 0.4)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#CC5533", stroke="#333"),
    )
    # Door
    scene.create_region(
        region_id="door",
        outline=[(0.4, 0.6), (0.55, 0.6), (0.55, 0.9), (0.4, 0.9)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#664422", stroke="#333"),
    )

    svg = svg_serialize(scene)
    assert "E8D4B0" in svg
    assert "CC5533" in svg
    assert "664422" in svg
    print(f"  ✓ multi-region scene ({len(svg)} chars)")


def test_deterministic_output():
    """Verify same scene produces byte-identical SVG."""
    scene = SceneGraph()
    scene.create_document()
    scene.create_region(
        region_id="test",
        outline=[(0.1, 0.1), (0.5, 0.8), (0.9, 0.1)],
    )
    svg1 = svg_serialize(scene)
    svg2 = svg_serialize(scene)
    assert svg1 == svg2
    print("  ✓ deterministic output (byte-identical)")


if __name__ == "__main__":
    print("\nAVGE MVP — Smoke Tests\n")

    tests = [
        ("Document", test_create_document),
        ("Regions", test_create_region),
        ("Style", test_style_objects),
        ("Scene Description", test_describe_scene),
        ("Curve Fitting", test_curve_fitting),
        ("Renderer", test_renderer),
        ("Multi-Region", test_scene_with_multiple_regions),
        ("Determinism", test_deterministic_output),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
        except Exception as e:
            print(f"  ✗ {name}: FAILED — {e}")
            raise

    print("\nAll smoke tests passed ✓")
