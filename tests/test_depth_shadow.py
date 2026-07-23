from avge_engine.controllers import scene_ops
from avge_engine.renderer.svg import svg_serialize
from avge_engine.services.engine import get_document_operations, reset_documents
from avge_engine.document import Style
from avge_engine.services.engine import get_document_operations, reset_documents


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_scene_graph_add_depth_shadow_creates_blurred_shadow():
    reset_documents()
    scene = get_document_operations()
    doc = scene.create_document(width=1000, height=800)
    scene.create_element(
        document_id=doc.id,
        element_id="box",
        z_index=5,
        outline=[(0.2, 0.2), (0.5, 0.2), (0.5, 0.5), (0.2, 0.5)],
        style=Style(fill="#CC3333"),
    )

    shadow = scene.add_depth_shadow(
        "box",
        document_id=doc.id,
        new_element_id="box_shadow",
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


def test_create_shadow_tool_renders_blur_filter():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)
    graph.create_element(
        document_id=doc.id,
        element_id="object",
        outline=[(0.25, 0.2), (0.55, 0.2), (0.55, 0.45), (0.25, 0.45)],
    )

    result = mcp.tools["create_shadow"](
        document_id=doc.id,
        element_id="object",
        new_element_id="object_shadow",
        softness=5,
        z_offset=-1,
    )
    svg = svg_serialize(graph, doc.id)

    assert "Shadow created" in result
    assert "object_shadow" in result
    assert 'filter="url(#blur_5.00)"' in svg


def test_create_shadow_clips_to_receiver():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)
    graph.create_element(
        document_id=doc.id,
        element_id="floor",
        z_index=2,
        outline=[(0.1, 0.55), (0.9, 0.55), (0.9, 0.85), (0.1, 0.85)],
    )
    graph.create_element(
        document_id=doc.id,
        element_id="chair",
        z_index=5,
        outline=[(0.35, 0.25), (0.55, 0.25), (0.55, 0.55), (0.35, 0.55)],
    )

    result = mcp.tools["create_shadow"](
        document_id=doc.id,
        element_id="chair",
        onto_element_id="floor",
        new_element_id="chair_cast_shadow",
        sy=0.35,
    )
    shadow = graph.get_element("chair_cast_shadow", doc.id)

    assert "Shadow created" in result
    assert shadow.clip_to == "floor"
    assert shadow.z_index == 3
    assert shadow.layer == graph.get_element("floor", doc.id).layer
    assert shadow.metadata["shadow_kind"] == "cast"


def test_batch_create_shadow():
    reset_documents()
    scene = get_document_operations()
    doc = scene.create_document()
    scene.create_element(
        document_id=doc.id,
        element_id="vase",
        outline=[(0.4, 0.2), (0.6, 0.2), (0.6, 0.6), (0.4, 0.6)],
    )

    result = scene.batch([
        {
            "tool": "create_shadow",
            "element_id": "vase",
            "new_element_id": "vase_shadow",
            "direction": 90,
            "distance": 0.04,
            "z_offset": -1,
        }
    ], document_id=doc.id)

    assert result[0]["status"] == "ok"
    assert scene.get_element("vase_shadow", doc.id).metadata["shadow_source"] == "vase"
