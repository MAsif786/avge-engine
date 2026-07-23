"""Tests for DocumentLayer operations — boolean, transform, groups, batch, etc."""
from avge_engine.document import CurveConstraints, Style
from avge_engine.services.document_structure_service import DocumentStructureService
from avge_engine.services.element_service import ElementService
from avge_engine.services.engine import get_document_operations, reset_documents
from avge_engine.services.inspection_service import InspectionService
from avge_engine.services.style_service import StyleService
from avge_engine.services.transform_service import TransformService


def _doc(scene):
    return scene.create_document().id


def test_boolean_union():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r1 = scene.create_element(document_id=did, element_id="a", outline=[(0.1,0.1),(0.5,0.1),(0.5,0.5),(0.1,0.5)])
    r2 = scene.create_element(document_id=did, element_id="b", outline=[(0.3,0.3),(0.7,0.3),(0.7,0.7),(0.3,0.7)])
    r = scene.boolean_operation("union", ["a", "b"], document_id=did)
    assert r is not None
    assert scene.has_element(r.id, did)
    assert not scene.has_element("a", did)  # originals removed
    assert not scene.has_element("b", did)


def test_boolean_keep_originals():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r1 = scene.create_element(document_id=did, element_id="a", outline=[(0.1,0.1),(0.5,0.1),(0.5,0.5),(0.1,0.5)])
    r2 = scene.create_element(document_id=did, element_id="b", outline=[(0.3,0.3),(0.7,0.3),(0.7,0.7),(0.3,0.7)])
    scene.boolean_operation("union", ["a", "b"], document_id=did, keep_originals=True)
    assert scene.has_element("a", did)
    assert scene.has_element("b", did)


def test_boolean_subtract():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r1 = scene.create_element(document_id=did, element_id="a", outline=[(0.1,0.1),(0.5,0.1),(0.5,0.5),(0.1,0.5)])
    r2 = scene.create_element(document_id=did, element_id="b", outline=[(0.2,0.2),(0.4,0.2),(0.4,0.4),(0.2,0.4)])
    r = scene.boolean_operation("subtract", ["a", "b"], document_id=did)
    assert r is not None


def test_transform_translate():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    TransformService(scene).transform_objects(document_id=did, ids=["r"], dx=0.1, dy=0.05)
    r = scene.get_element("r", did)
    assert r.outline[0][0] > 0.15


def test_transform_rotate():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    TransformService(scene).transform_objects(document_id=did, ids=["r"], rotate=45)
    r = scene.get_element("r", did)
    assert r.outline is not None


def test_transform_mirror():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    TransformService(scene).transform_objects(document_id=did, ids=["r"], mirror_x=True)
    r = scene.get_element("r", did)
    assert r.outline is not None


def test_transform_scale():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    TransformService(scene).transform_objects(document_id=did, ids=["r"], scale=2.0)
    r = scene.get_element("r", did)
    assert r.outline is not None


def test_duplicate_element():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    dup = ElementService(scene).duplicate_element("r", document_id=did, offset_x=0.2)
    assert dup.id != "r"
    assert scene.has_element(dup.id, did)


def test_duplicate_with_mirror():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    dup = ElementService(scene).duplicate_element("r", document_id=did, mirror_x=True, mirror_axis_x=0.5)
    assert scene.has_element(dup.id, did)


def test_duplicate_shadow_mode():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    dup = ElementService(scene).duplicate_element("r", document_id=did, shadow_mode=True, offset_x=0.01)
    assert dup.style.stroke is None
    assert dup.z_index == scene.get_element("r", did).z_index - 1


def test_duplicate_with_scale_rotate():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    dup = ElementService(scene).duplicate_element("r", document_id=did, scale=0.5, rotate=30)
    assert scene.has_element(dup.id, did)


def test_groups_create():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    structure = DocumentStructureService(scene)
    scene.create_element(document_id=did, element_id="a", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.create_element(document_id=did, element_id="b", outline=[(0,0),(1,0),(1,1),(0,1)])
    members = structure.group_elements("my_group", ["a", "b"], document_id=did)
    assert len(members) == 2


def test_groups_add_remove():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    structure = DocumentStructureService(scene)
    scene.create_element(document_id=did, element_id="a", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.create_element(document_id=did, element_id="b", outline=[(0,0),(1,0),(1,1),(0,1)])
    structure.group_elements("g", ["a"], document_id=did)
    structure.add_to_group("g", ["b"], document_id=did)
    assert len(structure.get_group("g", did)) == 2
    structure.remove_from_group("g", ["a"], did)
    assert len(structure.get_group("g", did)) == 1


def test_duplicate_group():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    structure = DocumentStructureService(scene)
    scene.create_element(document_id=did, element_id="a", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.create_element(document_id=did, element_id="b", outline=[(0,0),(1,0),(1,1),(0,1)])
    structure.group_elements("g", ["a", "b"], document_id=did)
    new_ids = structure.duplicate_group(group_name="g", document_id=did, dx=0.1)["new_ids"]
    assert len(new_ids) == 2
    # Check copies exist
    for nid in new_ids:
        assert scene.has_element(nid, did)


def test_create_rect():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r = scene.create_rect(0.1, 0.1, 0.5, 0.3, document_id=did)
    assert r.primitive["type"] == "rect"
    assert r.primitive["width"] == 0.5


def test_create_ellipse():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r = scene.create_ellipse(0.5, 0.5, 0.2, document_id=did)
    assert r.primitive["type"] == "ellipse"
    assert r.primitive["rx"] == 0.2


def test_create_line():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r = scene.create_line(0.1, 0.1, 0.9, 0.9, document_id=did)
    assert r.primitive["type"] == "line"


def test_create_polyline():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r = scene.create_line(points=[[0.1,0.1],[0.5,0.8],[0.9,0.1]], document_id=did)
    assert r.primitive is None  # polyline is path-based


def test_find_objects():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)],
                        style=Style(fill="#FF0000"))
    scene.create_element(document_id=did, element_id="r2", outline=[(0,0),(1,0),(1,1),(0,1)],
                        style=Style(fill="#00FF00"))
    results = InspectionService(scene).find_objects(document_id=did, fill="#FF0000")
    assert len(results) == 1
    assert results[0]["id"] == "r1"


def test_find_objects_z_range():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)], z_index=5)
    scene.create_element(document_id=did, element_id="r2", outline=[(0,0),(1,0),(1,1),(0,1)], z_index=15)
    results = InspectionService(scene).find_objects(document_id=did, z_min=10, z_max=20)
    assert len(results) == 1
    assert results[0]["id"] == "r2"


def test_find_objects_layer():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)], layer="bg")
    scene.create_element(document_id=did, element_id="r2", outline=[(0,0),(1,0),(1,1),(0,1)], layer="fg")
    results = InspectionService(scene).find_objects(document_id=did, layer="fg")
    assert len(results) == 1


def test_find_objects_has_stroke():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)],
                        style=Style(fill="#F00", stroke="#000"))
    scene.create_element(document_id=did, element_id="r2", outline=[(0,0),(1,0),(1,1),(0,1)],
                        style=Style(fill="#0F0", stroke=None))
    results = InspectionService(scene).find_objects(document_id=did, has_stroke=True)
    assert len(results) == 1
    results2 = InspectionService(scene).find_objects(document_id=did, has_stroke=False)
    assert len(results2) == 1


def test_extrude_element():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0.1,0.1),(0.5,0.8),(0.9,0.1)])
    scene.extrude_element_outline("r", document_id=did, segment_indices=[0])
    r = scene.get_element("r", did)
    assert len(r.outline) > 3


def test_checkpoint_restore():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)], z_index=1)
    scene.checkpoint(did, "before")
    scene.edit_element("r", document_id=did, z_index=99)
    r = scene.get_element("r", did)
    assert r.z_index == 99
    scene.restore(did, "before")
    r = scene.get_element("r", did)
    assert r.z_index == 1


def test_delete_element():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    assert scene.has_element("r", did)
    deleted = scene.delete_element(document_id=did, element_id="r")
    assert deleted == True  # noqa: E712
    assert not scene.has_element("r", did)


def test_delete_element_not_found():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    deleted = scene.delete_element(document_id=did, element_id="nonexistent")
    assert deleted is False


def test_create_element_defaults():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r = scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    assert r.style.fill == "#CCCCCC"
    assert r.style.stroke == "#333333"
    assert r.style.stroke_width == 0.005
    assert r.z_index == 0
    assert r.layer == "default"


def test_create_element_with_metadata():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    r = scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)],
                            metadata={"part": "handle"})
    assert r.metadata.get("part") == "handle"


def test_edit_element_outline():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.edit_element("r", document_id=did, outline=[(0,0),(1,0),(1,1),(0,1),(0,0)])
    r = scene.get_element("r", did)
    assert len(r.outline) == 5


def test_edit_element_style():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.edit_element("r", document_id=did, fill="#FF0000", stroke="none")
    r = scene.get_element("r", did)
    assert r.style.fill == "#FF0000"
    assert r.style.stroke is None


def test_style_objects():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r1", outline=[(0,0),(1,0),(1,1),(0,1)])
    scene.create_element(document_id=did, element_id="r2", outline=[(0,0),(1,0),(1,1),(0,1)])
    affected = StyleService(scene).style_objects(["r1", "r2"], document_id=did, fill="#00FF00")
    assert len(affected) == 2
    assert scene.get_element("r1", did).style.fill == "#00FF00"


def test_style_objects_partial():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)],
                        style=Style(fill="#F00", stroke="#000"))
    StyleService(scene).style_objects(["r"], document_id=did, stroke_width=0.02)
    r = scene.get_element("r", did)
    assert r.style.fill == "#F00"  # unchanged
    assert r.style.stroke == "#000"  # unchanged
    assert r.style.stroke_width == 0.02  # changed


def test_track_op():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.track_op(did, "test_tool")
    stats = scene.get_doc_stats(did)
    assert "test_tool" in stats["tool_calls"]
    assert stats["tool_calls"]["test_tool"] == 1


def test_describe_scene():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="r", outline=[(0,0),(1,0),(1,1),(0,1)])
    desc = scene.describe_scene(did)
    assert desc["element_count"] == 1
    assert desc["document"]["id"] == did


def test_list_groups():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    scene.create_element(document_id=did, element_id="a", outline=[(0,0),(1,0),(1,1),(0,1)])
    structure = DocumentStructureService(scene)
    structure.group_elements("g", ["a"], document_id=did)
    groups = structure.list_groups(document_id=did)
    assert len(groups) == 1
    assert groups[0]["name"] == "g"


def test_composite_element():
    reset_documents()
    scene = get_document_operations()
    did = _doc(scene)
    result = scene.create_composite_element(
        outline=[(0.1,0.3),(0.5,0.3),(0.9,0.3),(0.9,0.7),(0.1,0.7)],
        document_id=did,
        sub_parts={"pattern": "radial_fan", "count": 3, "anchor": "top_edge",
                    "length_range": [0.05, 0.1], "width": 0.02},
    )
    assert result["count"] == 4  # base + 3 sub-parts
    assert scene.has_element(result["base_id"], did)
