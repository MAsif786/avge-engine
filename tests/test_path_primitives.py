from avge_engine.controllers import element
from avge_engine.renderer.svg import svg_serialize
from avge_engine.services.engine import get_document_operations, reset_documents
from avge_engine.services.engine import get_document_operations, reset_documents


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_create_line_uses_two_point_points_argument():
    reset_documents()
    scene = get_document_operations()
    doc = scene.create_document()

    line = scene.create_line(points=[[0.2, 0.3], [0.7, 0.8]], document_id=doc.id)

    assert line.primitive == {
        "type": "line",
        "x1": 0.2,
        "y1": 0.3,
        "x2": 0.7,
        "y2": 0.8,
    }


def test_create_primitive_polyline_supports_dasharray_and_smoothness():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_primitive"](
        document_id=doc.id,
        element_id="route",
        shape={"type": "polyline", "points": [[0.1, 0.2], [0.4, 0.25], [0.8, 0.55]], "smoothness": 0.4},
        stroke="#224466",
        stroke_dasharray="4,2",
        fill="none",
    )

    route = graph.get_element("route", doc.id)
    assert "Polyline created" in result
    assert route.constraints.closed is False
    assert route.constraints.smoothness == 0.4
    assert route.style.stroke_dasharray == "4,2"


def test_compound_path_renders_as_single_svg_path_with_subpaths():
    reset_documents()
    scene = get_document_operations()
    doc = scene.create_document(width=1000, height=800)

    scene.create_compound_path(
        [
            [[0.1, 0.2], [0.9, 0.2]],
            [[0.1, 0.4], [0.9, 0.4]],
            [[0.1, 0.6], [0.9, 0.6]],
        ],
        document_id=doc.id,
        element_id="seams",
        stroke="#333333",
        stroke_dasharray="2,2",
    )
    svg = svg_serialize(scene, doc.id)

    assert svg.count("<path") == 1
    assert svg.count("M") == 3
    assert 'stroke-dasharray="2,2"' in svg


def test_batch_create_primitive_compound_path():
    reset_documents()
    scene = get_document_operations()
    doc = scene.create_document()

    result = scene.batch([
        {
            "tool": "create_primitive",
            "element_id": "wires",
            "shape": {
                "type": "compound_path",
                "subpaths": [
                    [[0.1, 0.1], [0.8, 0.15]],
                    [[0.1, 0.2], [0.8, 0.25]],
                ],
            },
            "stroke": "#111111",
        }
    ], document_id=doc.id)

    assert result[0]["status"] == "ok"
    assert scene.get_element("wires", doc.id).primitive["type"] == "compound_path"


def test_create_primitive_rect_supports_wavy_outline_pattern():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_element"](
        document_id=doc.id,
        element_id="box",
        shape={"type": "rect", "x": 0.2, "y": 0.2, "width": 0.4, "height": 0.25},
        fill="#E5E7EB",
        stroke="#111827",
        outline_pattern="wavy",
        pattern_density=8,
        pattern_amplitude=0.015,
        pattern_stroke_width=2,
    )

    overlay = graph.get_element("box_wavy_outline", doc.id)
    assert "pattern_elements=1" in result
    assert overlay.primitive["type"] == "compound_path"
    assert overlay.metadata["base"] == "box"
    assert overlay.metadata["pattern"] == "wavy"


def test_create_primitive_ellipse_supports_clipped_hatch_fill_pattern():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_element"](
        document_id=doc.id,
        element_id="badge",
        shape={"type": "ellipse", "cx": 0.5, "cy": 0.45, "rx": 0.2, "ry": 0.12},
        fill="#F8FAFC",
        stroke="#334155",
        fill_pattern="cross_hatch",
        pattern_density=6,
        pattern_stroke_width=1,
        pattern_opacity=0.4,
    )

    fill = graph.get_element("badge_cross_hatch_fill", doc.id)
    assert "pattern_elements=1" in result
    assert fill.primitive["type"] == "compound_path"
    assert fill.clip_to == "badge"
    assert fill.style.opacity == 0.4


def test_create_primitive_polygon_supports_dotted_outline_pattern():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    mcp.tools["create_element"](
        document_id=doc.id,
        element_id="hex",
        shape={"type": "polygon", "cx": 0.5, "cy": 0.5, "r": 0.2, "sides": 6},
        fill="#FFFFFF",
        stroke="#0F172A",
        outline_pattern="dotted",
        pattern_stroke_width=2,
    )

    dotted = graph.get_element("hex_dotted_outline", doc.id)
    assert dotted.style.stroke_dasharray == "1,5"
    assert dotted.style.stroke_linecap == "round"


def test_create_element_outline_supports_patterned_outline_and_fill():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_element"](
        document_id=doc.id,
        element_id="blob",
        outline=[[0.2, 0.2], [0.55, 0.18], [0.62, 0.52], [0.28, 0.58]],
        fill="#EEF2FF",
        stroke="#3730A3",
        outline_pattern="rough",
        fill_pattern="hatch",
        pattern_density=5,
        pattern_stroke_width=1,
    )

    rough = graph.get_element("blob_rough_outline_00", doc.id)
    hatch = graph.get_element("blob_hatch_fill", doc.id)
    assert "pattern_elements=2" in result
    assert rough.metadata["base"] == "blob"
    assert hatch.clip_to == "blob"


def test_create_curve_supports_outline_pattern_without_closing_curve():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_curve"](
        document_id=doc.id,
        element_id="motion",
        points=[[0.1, 0.8], [0.35, 0.45], [0.8, 0.55]],
        outline_pattern="sketch",
        pattern_jitter=0.01,
        pattern_stroke_width=2,
    )

    sketch = graph.get_element("motion_sketch_outline_00", doc.id)
    assert "pattern_elements=2" in result
    assert sketch.constraints.closed is False
    assert sketch.outline[0] != sketch.outline[-1]


def test_create_ellipse_band_supports_dotted_outline_pattern():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_ellipse_band"](
        document_id=doc.id,
        element_id="ring",
        cx=0.5,
        cy=0.5,
        rx=0.22,
        ry=0.08,
        thickness=0.025,
        outline_pattern="dotted",
        pattern_stroke_width=2,
    )

    dotted = graph.get_element("ring_dotted_outline", doc.id)
    assert "pattern_elements=1" in result
    assert dotted.style.stroke_dasharray == "1,5"


def test_create_primitive_supports_pattern_options_directly():
    reset_documents()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_primitive"](
        document_id=doc.id,
        element_id="tile",
        shape={"type": "rect", "x": 0.15, "y": 0.15, "width": 0.3, "height": 0.2},
        fill="#FFFFFF",
        stroke="#111827",
        outline_pattern="zigzag",
        fill_pattern="stipple",
        pattern_density=10,
        pattern_stroke_width=1.5,
    )

    outline = graph.get_element("tile_zigzag_outline", doc.id)
    dots = [r for r in graph.get_all_elements(doc.id) if r.metadata.get("base") == "tile" and r.metadata.get("pattern") == "stipple"]
    assert "pattern_elements=11" in result
    assert outline.primitive["type"] == "compound_path"
    assert len(dots) == 10
