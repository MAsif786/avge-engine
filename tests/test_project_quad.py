from avge_engine.controllers import scene_ops
from avge_engine.geometry.perspective import project_unit_points
from avge_engine.scene import SceneGraph, Style
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_project_unit_square_to_quad_corners():
    quad = [(0.1, 0.2), (0.8, 0.1), (0.72, 0.62), (0.18, 0.7)]
    pts = project_unit_points([(0, 0), (1, 0), (1, 1), (0, 1)], quad)

    assert pts == quad


def test_scene_project_quad_creates_panel():
    scene = SceneGraph()
    did = scene.create_document().id
    r = scene.project_quad(
        target_quad=[(0.1, 0.2), (0.8, 0.1), (0.72, 0.62), (0.18, 0.7)],
        document_id=did,
        element_id="panel",
        columns=2,
        rows=2,
        fill="#ABCDEF",
        stroke="none",
    )

    assert r.id == "panel"
    assert len(r.outline) == 8
    assert r.style.fill == "#ABCDEF"
    assert r.style.stroke is None


def test_scene_project_quad_warps_source_element_copy():
    scene = SceneGraph()
    did = scene.create_document().id
    scene.create_element(
        document_id=did,
        element_id="src",
        outline=[(0.2, 0.2), (0.5, 0.2), (0.5, 0.5), (0.2, 0.5)],
        style=Style(fill="#112233", stroke="#445566"),
    )
    r = scene.project_quad(
        target_quad=[(0.1, 0.1), (0.7, 0.2), (0.8, 0.7), (0.2, 0.8)],
        document_id=did,
        source_element_id="src",
        element_id="warped",
        fill=None,
        stroke=None,
        stroke_width=None,
        opacity=None,
    )

    assert r.id == "warped"
    assert scene.has_element("src", did)
    assert r.style.fill == "#112233"
    assert r.style.stroke == "#445566"


def test_scene_project_quad_replace_source():
    scene = SceneGraph()
    did = scene.create_document().id
    scene.create_element(
        document_id=did,
        element_id="src",
        outline=[(0.2, 0.2), (0.5, 0.2), (0.5, 0.5), (0.2, 0.5)],
    )
    r = scene.project_quad(
        target_quad=[(0.1, 0.1), (0.7, 0.2), (0.8, 0.7), (0.2, 0.8)],
        document_id=did,
        source_element_id="src",
        replace_source=True,
    )

    assert r.id == "src"
    assert scene.element_count(did) == 1
    assert r.outline[0] == (0.1, 0.1)


def test_project_quad_controller_tool_creates_element():
    reset_graph()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document()

    result = mcp.tools["project_quad"](
        document_id=doc.id,
        element_id="tile",
        target_quad=[[0.1, 0.2], [0.8, 0.12], [0.72, 0.62], [0.16, 0.72]],
        fill="#DDDDEE",
        stroke="none",
    )

    assert "Projected quad element: id=tile" in result
    assert graph.has_element("tile", doc.id)
