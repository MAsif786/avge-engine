from avge_engine.scene import Style
from avge_engine.services.document_service import DocumentService
from avge_engine.services.engine import reset_graph


def test_document_service_clones_document_deeply():
    reset_graph()
    service = DocumentService()
    doc = service.create_document(width=800, height=600, name="source", background="#101820")
    service.graph.create_element(
        document_id=doc.id,
        element_id="panel",
        outline=[(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)],
        style=Style(fill="#336699"),
        metadata={"kind": "facade"},
    )
    service.graph.group_elements("facades", ["panel"], document_id=doc.id)

    clone, source_id, element_count = service.clone_document(
        source_document_id=doc.id,
        name="copy",
    )

    assert source_id == doc.id
    assert clone.id != doc.id
    assert clone.name == "copy"
    assert element_count == 1
    assert service.graph.get_element("panel", clone.id) is not service.graph.get_element("panel", doc.id)
    assert [r["id"] for r in service.graph.get_group("facades", clone.id)] == ["panel"]


def test_document_service_set_background_updates_version():
    reset_graph()
    service = DocumentService()
    doc = service.create_document(background="#FFFFFF")

    updated = service.set_background(document_id=doc.id, background="#000000")

    assert updated.background == "#000000"
    assert updated.version == doc.version
    assert updated.version > 1
