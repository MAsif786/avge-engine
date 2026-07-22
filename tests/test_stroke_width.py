from avge_engine.controllers import element, scene_ops, style
from avge_engine.services.engine import reset_graph, stroke_width_to_norm


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_stroke_width_conversion_uses_shorter_canvas_dimension():
    reset_graph()
    graph = element.get_graph()
    doc = graph.create_document(width=1600, height=1000)

    assert stroke_width_to_norm(doc.id, 2) == 0.002


def test_create_curve_accepts_stroke_width():
    reset_graph()
    mcp = _FakeMCP()
    element.create_tools(mcp)
    graph = element.get_graph()
    doc = graph.create_document(width=1600, height=1000)

    mcp.tools["create_curve"](
        document_id=doc.id,
        element_id="cable",
        points=[[0.1, 0.1], [0.9, 0.2]],
        stroke_width=3,
    )

    assert graph.get_element("cable", doc.id).style.stroke_width == 0.003


def test_restyle_accepts_stroke_width():
    reset_graph()
    element_mcp = _FakeMCP()
    style_mcp = _FakeMCP()
    element.create_tools(element_mcp)
    style.create_tools(style_mcp)
    graph = element.get_graph()
    doc = graph.create_document(width=1200, height=800)
    graph.create_element(
        document_id=doc.id,
        element_id="rail",
        outline=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.2), (0.1, 0.2)],
    )

    style_mcp.tools["restyle"](
        document_id=doc.id,
        selector={"ids": ["rail"]},
        stroke_width=4,
    )

    assert graph.get_element("rail", doc.id).style.stroke_width == 0.005


def test_project_quad_accepts_stroke_width():
    reset_graph()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document(width=1600, height=1000)

    mcp.tools["project_quad"](
        document_id=doc.id,
        element_id="panel",
        target_quad=[[0.1, 0.2], [0.8, 0.12], [0.72, 0.62], [0.16, 0.72]],
        stroke_width=2,
    )

    assert graph.get_element("panel", doc.id).style.stroke_width == 0.002
