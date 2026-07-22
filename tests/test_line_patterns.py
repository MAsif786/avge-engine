from avge_engine.controllers import procedural
from avge_engine.renderer.svg import svg_serialize
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def _setup():
    reset_graph()
    mcp = _FakeMCP()
    procedural.create_tools(mcp)
    graph = procedural.get_graph()
    doc = graph.create_document(width=1000, height=800)
    return mcp, graph, doc


def test_create_line_pattern_wavy_uniform_stroke():
    mcp, graph, doc = _setup()

    result = mcp.tools["create_line_pattern"](
        document_id=doc.id,
        pattern="wavy",
        element_id="wave",
        points=[[0.1, 0.5], [0.9, 0.5]],
        count=24,
        amplitude=0.04,
        frequency=3,
        stroke_width=3,
    )

    wave = graph.get_element("wave", doc.id)
    assert "Line pattern created: pattern=wavy" in result
    assert wave.constraints.closed is False
    assert wave.constraints.smoothness == 0.45
    assert len(wave.outline) == 24
    assert wave.style.stroke_width == 0.00375


def test_create_line_pattern_tapered_creates_filled_ribbon():
    mcp, graph, doc = _setup()

    mcp.tools["create_line_pattern"](
        document_id=doc.id,
        pattern="curve",
        element_id="gesture",
        points=[[0.2, 0.8], [0.45, 0.3], [0.8, 0.5]],
        width_profile="tapered",
        start_width=12,
        end_width=2,
        stroke="#223344",
        role="gesture",
    )

    gesture = graph.get_element("gesture", doc.id)
    assert gesture.constraints.closed is True
    assert gesture.style.fill == "#223344"
    assert gesture.style.stroke is None
    assert gesture.style.opacity == 0.55
    assert len(gesture.outline) == 6
    assert gesture.metadata["width_profile"] == "tapered"


def test_create_line_pattern_hatch_renders_compound_path():
    mcp, graph, doc = _setup()

    mcp.tools["create_line_pattern"](
        document_id=doc.id,
        pattern="cross_hatch",
        element_id="shade",
        bounds=[0.2, 0.2, 0.4, 0.3],
        density=5,
        angle=30,
        stroke_width=1,
    )
    shade = graph.get_element("shade", doc.id)
    svg = svg_serialize(graph, doc.id)

    assert shade.primitive["type"] == "compound_path"
    assert len(shade.primitive["subpaths"]) == 10
    assert svg.count("M") >= 10


def test_create_line_pattern_stipple_creates_dots():
    mcp, graph, doc = _setup()

    result = mcp.tools["create_line_pattern"](
        document_id=doc.id,
        pattern="stipple",
        element_id="grain",
        bounds=[0.1, 0.1, 0.2, 0.2],
        density=12,
        stroke_width=2,
        seed=2,
    )

    dots = [r for r in graph.get_all_elements(doc.id) if r.metadata.get("pattern") == "stipple"]
    assert "elements=12" in result
    assert len(dots) == 12
    assert all(r.primitive["type"] == "ellipse" for r in dots)


def test_create_line_pattern_role_defaults_to_construction_dash():
    mcp, graph, doc = _setup()

    mcp.tools["create_line_pattern"](
        document_id=doc.id,
        pattern="straight",
        element_id="centerline",
        points=[[0.5, 0.1], [0.5, 0.9]],
        role="construction",
        stroke_width=1,
    )

    centerline = graph.get_element("centerline", doc.id)
    assert centerline.style.opacity == 0.28
    assert centerline.style.stroke_dasharray == "5,5"
