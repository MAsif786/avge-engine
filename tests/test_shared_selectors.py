from avge_engine.controllers import query, element, scene_ops, style
from avge_engine.services.document_structure_service import DocumentStructureService
from avge_engine.services.engine import get_document_operations, reset_documents


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def _setup():
    reset_documents()
    qm = _FakeMCP()
    rm = _FakeMCP()
    sm = _FakeMCP()
    tm = _FakeMCP()
    query.create_tools(qm)
    element.create_tools(rm)
    style.create_tools(sm)
    scene_ops.create_tools(tm)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)
    graph.create_element(
        document_id=doc.id,
        element_id="near_red",
        outline=[(0.1, 0.65), (0.2, 0.65), (0.2, 0.8), (0.1, 0.8)],
        layer="props",
        metadata={"kind": "target"},
    )
    graph.edit_element("near_red", document_id=doc.id, fill="#CC3333")
    graph.create_element(
        document_id=doc.id,
        element_id="far_red",
        outline=[(0.12, 0.12), (0.22, 0.12), (0.22, 0.24), (0.12, 0.24)],
        layer="props",
        metadata={"kind": "target"},
    )
    graph.edit_element("far_red", document_id=doc.id, fill="#CC3333")
    graph.create_element(
        document_id=doc.id,
        element_id="blue",
        outline=[(0.55, 0.65), (0.7, 0.65), (0.7, 0.8), (0.55, 0.8)],
        layer="other",
        metadata={"kind": "skip"},
    )
    graph.edit_element("blue", document_id=doc.id, fill="#3366CC")
    DocumentStructureService(graph).group_elements("targets", ["near_red", "far_red"], document_id=doc.id)
    return graph, doc, qm, sm, tm


def test_find_objects_accepts_shared_selector_bounds_and_tags():
    _, doc, qm, _, _ = _setup()

    result = qm.tools["find_objects"](
        document_id=doc.id,
        selector={"tags": {"kind": "target"}, "bounds": {"max_y": 0.3}},
    )

    assert "far_red" in result
    assert "near_red" not in result


def test_restyle_accepts_shared_selector_group_and_fill():
    graph, doc, _, sm, _ = _setup()

    result = sm.tools["restyle"](
        document_id=doc.id,
        selector={"group_name": "targets", "fill": "#CC3333"},
        fill="#00AA66",
    )

    assert "Restyled 2 element" in result
    assert graph.get_element("near_red", doc.id).style.fill == "#00AA66"
    assert graph.get_element("far_red", doc.id).style.fill == "#00AA66"
    assert graph.get_element("blue", doc.id).style.fill == "#3366CC"


def test_depth_haze_accepts_shared_selector_bounds():
    graph, doc, _, sm, _ = _setup()

    result = sm.tools["apply_depth_haze"](
        document_id=doc.id,
        selector={"bounds": {"max_y": 0.3}},
        haze_color="#99CCFF",
        near_y=0.8,
        far_y=0.1,
        max_strength=0.6,
    )

    assert "Depth haze applied to 1 element" in result
    assert graph.get_element("far_red", doc.id).style.fill != "#CC3333"
    assert graph.get_element("near_red", doc.id).style.fill == "#CC3333"


def test_transform_objects_accepts_shared_selector_layer_and_fill():
    graph, doc, _, _, tm = _setup()

    result = tm.tools["transform_objects"](
        document_id=doc.id,
        selector={"layer": "props", "fill": "#CC3333"},
        dx=0.05,
    )

    assert "Transformed 2 element" in result
    assert graph.get_element("near_red", doc.id).outline[0][0] == 0.15
    assert graph.get_element("far_red", doc.id).outline[0][0] == 0.17
    assert graph.get_element("blue", doc.id).outline[0][0] == 0.55


def test_add_shading_accepts_shared_selector_layer():
    graph, doc, _, _, tm = _setup()

    result = tm.tools["add_shading"](
        document_id=doc.id,
        selector={"layer": "props"},
        mode="gradient",
        light_direction=135,
        intensity=0.4,
    )

    assert "Gradient shading applied to 2 element" in result
    assert graph.get_element("near_red", doc.id).style.fill["type"] == "linear"
    assert graph.get_element("far_red", doc.id).style.fill["type"] == "linear"
    assert graph.get_element("blue", doc.id).style.fill == "#3366CC"


def test_apply_line_hierarchy_accepts_shared_selector_layer():
    graph, doc, _, sm, _ = _setup()
    graph.edit_element("near_red", document_id=doc.id, stroke="#111111", stroke_width=1)
    graph.edit_element("far_red", document_id=doc.id, stroke="#111111", stroke_width=1)
    graph.edit_element("blue", document_id=doc.id, stroke="#111111", stroke_width=1)
    blue_width = graph.get_element("blue", doc.id).style.stroke_width

    result = sm.tools["apply_line_hierarchy"](
        document_id=doc.id,
        selector={"layer": "props"},
        outer_width=6,
        inner_width=2,
        basis="z_index",
    )

    assert "Line hierarchy applied" in result
    assert graph.get_element("near_red", doc.id).style.stroke_width != 1
    assert graph.get_element("far_red", doc.id).style.stroke_width != 1
    assert graph.get_element("blue", doc.id).style.stroke_width == blue_width
