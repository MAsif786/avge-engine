from avge_engine.document import Style
from avge_engine.services.engine import get_document_operations, reset_documents
from avge_engine.services.transform_service import TransformService


def _setup():
    reset_documents()
    graph = get_document_operations()
    doc = graph.create_document(width=600, height=400, name="transform")
    graph.create_element(
        document_id=doc.id,
        element_id="a",
        outline=[(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)],
        style=Style(fill="#CC3333"),
    )
    graph.create_element(
        document_id=doc.id,
        element_id="b",
        outline=[(0.3, 0.2), (0.4, 0.2), (0.4, 0.3), (0.3, 0.3)],
        style=Style(fill="#3366CC"),
    )
    return TransformService(graph), doc


def test_transform_service_moves_elements():
    service, doc = _setup()

    result = service.transform_objects(document_id=doc.id, ids=["a"], dx=0.1)

    assert result["affected"] == ["a"]
    assert service.get_element(doc.id, "a").bounds["x"] == 0.2


def test_transform_service_aligns_elements():
    service, doc = _setup()

    result = service.transform_objects(document_id=doc.id, ids=["a", "b"], mode="align", alignment="top")

    assert result["affected"] == ["a", "b"]
    assert service.get_element(doc.id, "a").bounds["y"] == service.get_element(doc.id, "b").bounds["y"]
