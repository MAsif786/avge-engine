from avge_engine.controllers import region
from avge_engine.renderer.svg import svg_serialize
from avge_engine.scene import SceneGraph
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_create_line_uses_two_point_points_argument():
    scene = SceneGraph()
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
    reset_graph()
    mcp = _FakeMCP()
    region.create_tools(mcp)
    graph = region.get_graph()
    doc = graph.create_document(width=1000, height=800)

    result = mcp.tools["create_primitive"](
        document_id=doc.id,
        region_id="route",
        shape={"type": "polyline", "points": [[0.1, 0.2], [0.4, 0.25], [0.8, 0.55]], "smoothness": 0.4},
        stroke="#224466",
        stroke_dasharray="4,2",
        fill="none",
    )

    route = graph.get_region("route", doc.id)
    assert "Polyline created" in result
    assert route.constraints.closed is False
    assert route.constraints.smoothness == 0.4
    assert route.style.stroke_dasharray == "4,2"


def test_compound_path_renders_as_single_svg_path_with_subpaths():
    scene = SceneGraph()
    doc = scene.create_document(width=1000, height=800)

    scene.create_compound_path(
        [
            [[0.1, 0.2], [0.9, 0.2]],
            [[0.1, 0.4], [0.9, 0.4]],
            [[0.1, 0.6], [0.9, 0.6]],
        ],
        document_id=doc.id,
        region_id="seams",
        stroke="#333333",
        stroke_dasharray="2,2",
    )
    svg = svg_serialize(scene, doc.id)

    assert svg.count("<path") == 1
    assert svg.count("M") == 3
    assert 'stroke-dasharray="2,2"' in svg


def test_batch_create_primitive_compound_path():
    scene = SceneGraph()
    doc = scene.create_document()

    result = scene.batch([
        {
            "tool": "create_primitive",
            "region_id": "wires",
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
    assert scene.get_region("wires", doc.id).primitive["type"] == "compound_path"
