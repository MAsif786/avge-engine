from avge_engine.document import DocumentRepository
from avge_engine.document import ElementNode, Style
from avge_engine.services.engine import get_document_operations, reset_documents


def test_document_repository_resolves_active_document_and_commits():
    reset_documents()
    graph = get_document_operations()
    doc = graph.create_document(width=600, height=400, name="repo")
    repo = DocumentRepository(graph)

    assert repo.require_id(None) == doc.id

    before = repo.get(doc.id).version
    repo.commit(doc.id, action="unit_test", target="doc")

    assert repo.get(doc.id).version == before + 1


def test_document_repository_adds_element_without_service_graph_private_access():
    reset_documents()
    graph = get_document_operations()
    doc = graph.create_document(width=600, height=400, name="repo")
    repo = DocumentRepository(graph)
    element = ElementNode(
        id="repo_box",
        outline=[(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)],
        style=Style(fill="#CC3333"),
    )

    repo.add_element(doc.id, element)

    assert repo.get_element(doc.id, "repo_box").style.fill == "#CC3333"


def test_document_repository_updates_deletes_and_lists_layers():
    reset_documents()
    graph = get_document_operations()
    doc = graph.create_document(width=600, height=400, name="repo")
    repo = DocumentRepository(graph)
    repo.create_element_node(
        doc.id,
        element_id="repo_box",
        outline=[(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)],
        layer="props",
        style=Style(fill="#CC3333"),
    )

    repo.update_element(doc.id, "repo_box", fill="#00AA66", layer="foreground")

    assert repo.get_element(doc.id, "repo_box").style.fill == "#00AA66"
    assert repo.list_layers(doc.id) == [{"layer": "foreground", "count": 1}]
    assert repo.delete_elements(doc.id, ["repo_box", "missing"]) == ["repo_box"]
    assert repo.list_elements(doc.id) == []
