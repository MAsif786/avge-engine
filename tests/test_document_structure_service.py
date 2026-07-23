from avge_engine.document import Style
from avge_engine.services.document_structure_service import DocumentStructureService
from avge_engine.services.engine import get_document_operations, reset_documents


def _setup():
    reset_documents()
    graph = get_document_operations()
    doc = graph.create_document(width=600, height=400, name="structure")
    graph.create_element(
        document_id=doc.id,
        element_id="a",
        outline=[(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)],
        layer="near",
        z_index=1,
        style=Style(fill="#CC3333"),
    )
    graph.create_element(
        document_id=doc.id,
        element_id="b",
        outline=[(0.3, 0.1), (0.4, 0.1), (0.4, 0.2)],
        layer="near",
        z_index=2,
        style=Style(fill="#3366CC"),
    )
    return DocumentStructureService(graph), doc


def test_document_structure_service_groups():
    service, doc = _setup()

    created = service.edit_group(
        document_id=doc.id,
        action="create",
        group_name="pair",
        element_ids=["a", "b"],
    )
    removed = service.edit_group(
        document_id=doc.id,
        action="remove",
        group_name="pair",
        element_ids=["b"],
    )

    assert created["members"] == ["a", "b"]
    assert removed["removed"] == ["b"]
    assert service.list_groups(document_id=doc.id) == [{"name": "pair", "count": 1}]


def test_document_structure_service_duplicate_group():
    service, doc = _setup()
    service.group_elements("pair", ["a", "b"], document_id=doc.id)

    duplicated = service.duplicate_group(
        document_id=doc.id,
        group_name="pair",
        new_prefix="pair_copy",
        dx=0.1,
    )

    assert duplicated == {
        "source_group": "pair",
        "new_ids": ["pair_copy_a", "pair_copy_b"],
        "count": 2,
    }
    assert service.get_element(doc.id, "pair_copy_a").outline[0] == (0.2, 0.1)
    assert service.list_groups(document_id=doc.id) == [
        {"name": "pair", "count": 2},
        {"name": "pair_copy", "count": 2},
    ]


def test_document_structure_service_layers_and_shift():
    service, doc = _setup()

    count = service.shift_layer_z(document_id=doc.id, layer="near", z_offset=5)

    assert count == 2
    assert service.list_layers(document_id=doc.id) == [{"layer": "near", "count": 2}]
    assert service.get_element(doc.id, "a").z_index == 6
    assert service.get_element(doc.id, "b").z_index == 7
