"""
Smoke test: exercises core engine components directly.

Run: .venv/bin/python tests/smoke_test.py
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from avge_engine.scene import SceneGraph, CurveConstraints, Style
from avge_engine.renderer import svg_serialize, render_preview_base64
from avge_engine.geometry import fit_curves, sample_curve


def _doc(scene):
    """Helper: create a document and return its ID."""
    return scene.create_document().id


def test_create_document():
    scene = SceneGraph()
    doc = scene.create_document(width=800, height=600, background="#F0F0F0")
    assert doc.id.startswith("doc_")
    assert doc.width == 800
    assert doc.height == 600
    assert doc.background == "#F0F0F0"
    print("  ✓ create_document")


def test_create_region():
    scene = SceneGraph()
    did = _doc(scene)
    region = scene.create_region(
        document_id=did, region_id="triangle",
        outline=[(0.1, 0.1), (0.5, 0.8), (0.9, 0.1)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#FF0000", stroke="#000000"),
    )
    assert region.id == "triangle"
    assert len(region.outline) == 3
    assert region.style.fill == "#FF0000"
    print("  ✓ create_region")


def test_style_objects():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)])
    affected = scene.style_objects(["r1"], document_id=did, fill="#00FF00", stroke_width=0.02)
    assert affected == ["r1"]
    r1 = scene.get_region("r1", did)
    assert r1.style.fill == "#00FF00"
    assert r1.style.stroke_width == 0.02
    print("  ✓ style_objects")


def test_describe_scene():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)])
    desc = scene.describe_scene(detail="summary", document_id=did)
    assert desc["region_count"] == 1
    assert desc["regions"][0]["id"] == "r1"
    assert desc["regions"][0]["outline_point_count"] == 4
    print("  ✓ describe_scene")


def test_curve_fitting():
    star_pts = []
    for i in range(5):
        angle = math.pi/2 + i*4*math.pi/5
        star_pts.append((0.5+0.4*math.cos(angle), 0.5+0.4*math.sin(angle)))
        angle2 = angle+2*math.pi/5
        star_pts.append((0.5+0.15*math.cos(angle2), 0.5+0.15*math.sin(angle2)))
    segments = fit_curves(star_pts, closed=True, smoothness=0.3)
    assert len(segments) == len(star_pts)
    for seg in segments:
        assert len(seg) == 4
    points = sample_curve(segments, samples_per_segment=16)
    assert len(points) > 0
    print("  ✓ curve_fitting")


def test_renderer():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="sq",
        outline=[(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#4488FF", stroke="#222", stroke_width=0.01))
    svg = svg_serialize(scene)
    assert "svg" in svg
    assert "4488FF" in svg
    assert "#222" in svg
    b64 = render_preview_base64(svg, scale=0.5)
    assert len(b64) > 100
    print(f"  ✓ renderer ({len(svg)} chars svg, {len(b64)} b64)")


def test_multi_region():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="body",
        outline=[(0.2,0.4),(0.8,0.4),(0.8,0.9),(0.2,0.9)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#E8D4B0", stroke="#333"))
    scene.create_region(document_id=did, region_id="roof",
        outline=[(0.15,0.4),(0.5,0.1),(0.85,0.4)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill="#CC5533", stroke="#333"))
    svg = svg_serialize(scene)
    assert "E8D4B0" in svg and "CC5533" in svg
    print(f"  ✓ multi-region scene ({len(svg)} chars)")


def test_deterministic():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="t", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    svg1 = svg_serialize(scene)
    svg2 = svg_serialize(scene)
    assert svg1 == svg2
    print("  ✓ deterministic output")


if __name__ == "__main__":
    print("\nAVGE Engine — Smoke Tests\n")
    tests = [
        ("Document", test_create_document),
        ("Regions", test_create_region),
        ("Style", test_style_objects),
        ("Describe", test_describe_scene),
        ("Curve Fitting", test_curve_fitting),
        ("Renderer", test_renderer),
        ("Multi-Region", test_multi_region),
        ("Determinism", test_deterministic),
    ]
    for name, fn in tests:
        try:
            fn()
        except Exception as e:
            print(f"  ✗ {name}: FAILED — {e}")
            raise
    print("\nAll smoke tests passed ✓")
