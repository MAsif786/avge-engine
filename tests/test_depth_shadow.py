from avge_engine.controllers import scene_ops
from avge_engine.renderer.svg import svg_serialize
from avge_engine.scene import SceneGraph
from avge_engine.scene import Style
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_scene_graph_add_depth_shadow_creates_blurred_shadow():
    scene = SceneGraph()
    doc = scene.create_document(width=1000, height=800)
    scene.create_region(
        document_id=doc.id,
        region_id="box",
        z_index=5,
        outline=[(0.2, 0.2), (0.5, 0.2), (0.5, 0.5), (0.2, 0.5)],
        style=Style(fill="#CC3333"),
    )

    shadow = scene.add_depth_shadow(
        "box",
        document_id=doc.id,
        new_region_id="box_shadow",
        direction=90,
        distance=0.05,
        softness=6,
        opacity=0.3,
        sy=0.45,
    )

    assert shadow.id == "box_shadow"
    assert shadow.z_index == 4
    assert shadow.style.fill == "#000000"
    assert shadow.style.stroke is None
    assert shadow.style.blur == 6
    assert shadow.style.opacity == 0.3
    assert shadow.metadata["shadow_source"] == "box"
    assert shadow.metadata["shadow_kind"] == "depth"
    source_center_y = 0.35
    shadow_center_y = sum(y for _, y in shadow.outline) / len(shadow.outline)
    assert shadow_center_y > source_center_y


def test_add_depth_shadow_tool_renders_blur_filter():
    reset_graph()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document(width=1000, height=800)
    graph.create_region(
        document_id=doc.id,
        region_id="object",
        outline=[(0.25, 0.2), (0.55, 0.2), (0.55, 0.45), (0.25, 0.45)],
    )

    result = mcp.tools["add_depth_shadow"](
        document_id=doc.id,
        region_id="object",
        new_region_id="object_shadow",
        softness=5,
    )
    svg = svg_serialize(graph, doc.id)

    assert "Depth shadow added" in result
    assert "object_shadow" in result
    assert 'filter="url(#blur_5.00)"' in svg


def test_cast_shadow_clips_to_receiver():
    reset_graph()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document(width=1000, height=800)
    graph.create_region(
        document_id=doc.id,
        region_id="floor",
        z_index=2,
        outline=[(0.1, 0.55), (0.9, 0.55), (0.9, 0.85), (0.1, 0.85)],
    )
    graph.create_region(
        document_id=doc.id,
        region_id="chair",
        z_index=5,
        outline=[(0.35, 0.25), (0.55, 0.25), (0.55, 0.55), (0.35, 0.55)],
    )

    result = mcp.tools["cast_shadow"](
        document_id=doc.id,
        from_region_id="chair",
        onto_region_id="floor",
        new_region_id="chair_cast_shadow",
        sy=0.35,
    )
    shadow = graph.get_region("chair_cast_shadow", doc.id)

    assert "Cast shadow added" in result
    assert shadow.clip_to == "floor"
    assert shadow.z_index == 3
    assert shadow.layer == graph.get_region("floor", doc.id).layer
    assert shadow.metadata["shadow_kind"] == "cast"


def test_batch_add_depth_shadow():
    scene = SceneGraph()
    doc = scene.create_document()
    scene.create_region(
        document_id=doc.id,
        region_id="vase",
        outline=[(0.4, 0.2), (0.6, 0.2), (0.6, 0.6), (0.4, 0.6)],
    )

    result = scene.batch([
        {
            "tool": "add_depth_shadow",
            "region_id": "vase",
            "new_region_id": "vase_shadow",
            "direction": 90,
            "distance": 0.04,
        }
    ], document_id=doc.id)

    assert result[0]["status"] == "ok"
    assert scene.get_region("vase_shadow", doc.id).metadata["shadow_source"] == "vase"
