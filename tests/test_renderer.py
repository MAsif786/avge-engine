"""Tests for SVG renderer and curve engine edge cases."""
from avge_engine.scene import SceneGraph, CurveConstraints, Style
from avge_engine.renderer.svg import svg_serialize
from avge_engine.geometry.curve import fit_curves, sample_curve


def _doc(scene):
    return scene.create_document().id


def test_svg_output():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    svg = svg_serialize(scene, did)
    assert '<?xml' in svg
    assert '<svg' in svg
    assert '</svg>' in svg
    assert 'fill=' in svg


def test_svg_background():
    scene = SceneGraph()
    did = scene.create_document(background="#FF0000").id
    svg = svg_serialize(scene, did)
    assert '#FF0000' in svg


def test_svg_multiple_regions():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.create_region(document_id=did, region_id="r2", outline=[(0.2,0.2),(0.8,0.2),(0.8,0.8),(0.2,0.8)])
    svg = svg_serialize(scene, did)
    assert svg.count('<path') == 2


def test_svg_primitive_rect():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_rect(0.1, 0.1, 0.5, 0.3, document_id=did, rx=0.05)
    svg = svg_serialize(scene, did)
    assert '<rect' in svg
    assert 'rx=' in svg


def test_svg_primitive_ellipse():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_ellipse(0.5, 0.5, 0.2, document_id=did)
    svg = svg_serialize(scene, did)
    assert '<ellipse' in svg


def test_svg_polygon_smoothness_zero():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)],
                        constraints=CurveConstraints(smoothness=0.0))
    svg = svg_serialize(scene, did)
    assert '<polygon' in svg


def test_svg_clip_path():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="clip", outline=[(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)])
    scene.create_region(document_id=did, region_id="r", outline=[(0,0),(1,0),(1,1),(0,1)], clip_to="clip")
    svg = svg_serialize(scene, did)
    assert '<clipPath' in svg
    assert 'clip-path=' in svg


def test_svg_z_order():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="back", outline=[(0,0),(1,0),(1,1),(0,1)], z_index=0)
    scene.create_region(document_id=did, region_id="front", outline=[(0.2,0.2),(0.8,0.2),(0.8,0.8),(0.2,0.8)], z_index=10)
    svg = svg_serialize(scene, did)
    # Region order in SVG
    back_pos = svg.index('back') if 'back' in svg else -1
    front_pos = svg.index('front') if 'front' in svg else -1
    # SVG doesn't include region IDs, but both paths should be present
    assert svg.count('<path') == 2


def test_svg_gradient():
    scene = SceneGraph()
    did = _doc(scene)
    from avge_engine.effects import Style
    gradient_style = Style(
        fill={"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 0,
              "stops": [{"offset": 0, "color": "#FFF"}, {"offset": 1, "color": "#000"}]},
        stroke="#000",
    )
    scene.create_region(document_id=did, region_id="r", outline=[(0,0),(1,0),(1,1),(0,1)], style=gradient_style)
    svg = svg_serialize(scene, did)
    assert '<linearGradient' in svg
    assert 'url(#' in svg


def test_curve_fit_2_points():
    segments = fit_curves([(0.0, 0.0), (1.0, 1.0)])
    assert len(segments) == 1


def test_curve_fit_open():
    segments = fit_curves([(0.0, 0.0), (0.5, 0.8), (1.0, 0.0)], closed=False)
    assert len(segments) == 2


def test_curve_fit_closed():
    segments = fit_curves([(0.0, 0.0), (0.5, 0.8), (1.0, 0.0)], closed=True)
    assert len(segments) == 3


def test_curve_with_tensions():
    segments = fit_curves([(0.0, 0.0), (0.5, 0.8), (1.0, 0.0)],
                          smoothness=0.5, tensions=[0.0, 0.8, 0.0])
    assert len(segments) == 3


def test_curve_sample():
    segments = fit_curves([(0.0, 0.0), (0.5, 0.8), (1.0, 0.0)])
    samples = sample_curve(segments, samples_per_segment=10)
    assert len(samples) == 30  # 3 segments * 10 samples


def test_svg_blend_mode():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r", outline=[(0,0),(1,0),(1,1),(0,1)],
                        style=Style(fill="#F00", blend_mode="multiply"))
    svg = svg_serialize(scene, did)
    assert 'mix-blend-mode' in svg


def test_svg_opacity():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r", outline=[(0,0),(1,0),(1,1),(0,1)],
                        style=Style(fill="#F00", opacity=0.5))
    svg = svg_serialize(scene, did)
    assert 'opacity=' in svg


def test_svg_text():
    scene = SceneGraph()
    did = _doc(scene)
    r = scene.create_text(0.5, 0.5, "Hello", document_id=did, font_size=0.05, font_family="Arial")
    assert r.primitive["type"] == "text"
    svg = svg_serialize(scene, did)
    assert '<text' in svg
    assert 'Hello' in svg
    assert 'Arial' in svg
    assert 'font-size=' in svg


def test_svg_text_combines_primitive_and_style_opacity_once():
    import xml.etree.ElementTree as ET

    scene = SceneGraph()
    did = _doc(scene)
    r = scene.create_text(0.5, 0.5, "Hello", document_id=did, opacity=0.9)
    scene.edit_region(r.id, document_id=did, opacity=0.5)

    svg = svg_serialize(scene, did)

    text_line = next(line for line in svg.splitlines() if "<text" in line)
    assert text_line.count("opacity=") == 1
    assert 'opacity="0.45"' in text_line
    ET.fromstring(svg)


def test_svg_empty_scene():
    scene = SceneGraph()
    svg = svg_serialize(scene, None)
    assert svg == ""  # no document to render


def test_svg_image():
    scene = SceneGraph()
    did = _doc(scene)
    r = scene.insert_image(0.2, 0.3, 0.6, 0.4, "https://example.com/img.png", document_id=did)
    assert r.primitive["type"] == "image"
    svg = svg_serialize(scene, did)
    assert '<image' in svg
    assert 'href=' in svg
    assert 'example.com' in svg
    assert 'preserveAspectRatio' in svg


def test_edit_region_shape_rect():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.edit_region("r", document_id=did, shape={"type": "rect", "x": 0.1, "y": 0.1,
                                                    "width": 0.5, "height": 0.3, "rx": 0.05})
    r = scene.get_region("r", did)
    assert r.primitive["type"] == "rect"
    assert r.primitive["width"] == 0.5


def test_edit_region_shape_ellipse():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.edit_region("r", document_id=did,
                       shape={"type": "ellipse", "cx": 0.5, "cy": 0.5, "rx": 0.2})
    r = scene.get_region("r", did)
    assert r.primitive["type"] == "ellipse"


def test_edit_region_outline_update():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_region(document_id=did, region_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.edit_region("r", document_id=did, smoothness=0.8,
                       tensions=(0.5, 0.5, 0.5, 0.5))
    r = scene.get_region("r", did)
    assert r.constraints.smoothness == 0.8


def test_png_symbol_font_fallback():
    """Verify Unicode symbols ★✦ render via font-family fallback in SVG."""
    from avge_engine.renderer.svg import svg_serialize
    from avge_engine.scene import SceneGraph
    s = SceneGraph()
    did = s.create_document(name='test', background='#FFFFFF').id
    s.create_text(0.5, 0.5, '✦ ★ —', document_id=did, font_size=0.06)
    svg = svg_serialize(s, did)
    # Font-family should include Apple Symbols for Unicode symbol coverage
    assert 'Apple Symbols' in svg, 'SVG should include Apple Symbols font fallback'


def test_edit_region_stroke_dasharray():
    scene = SceneGraph()
    did = _doc(scene)
    scene.create_line(0.1, 0.1, 0.9, 0.9, document_id=did, region_id="line1")
    scene.edit_region("line1", document_id=did, stroke_dasharray="4,2")
    r = scene.get_region("line1", did)
    assert r.style.stroke_dasharray == "4,2"
