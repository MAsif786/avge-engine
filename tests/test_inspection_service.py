from avge_engine.document import Style
from avge_engine.services.engine import get_document_operations, reset_documents
from avge_engine.services.inspection_service import InspectionService


def _setup():
    reset_documents()
    graph = get_document_operations()
    doc = graph.create_document(width=600, height=400, name="inspect")
    graph.create_element(
        document_id=doc.id,
        element_id="red_box",
        outline=[(0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3)],
        layer="props",
        style=Style(fill="#CC3333", stroke="#111111"),
        metadata={"kind": "box"},
    )
    return InspectionService(graph), doc


def test_inspection_service_describes_and_finds_objects():
    service, doc = _setup()

    desc = service.describe_scene(document_id=doc.id)
    results = service.find_objects(document_id=doc.id, fill="#CC3333")

    assert desc["element_count"] == 1
    assert [item["id"] for item in results] == ["red_box"]


def test_inspection_service_critique_returns_sections():
    service, doc = _setup()

    result = service.critique(document_id=doc.id, mode="both")

    assert result["mode"] == "both"
    assert "rules" in result
    assert "visual" in result
