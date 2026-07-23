from avge_engine.document import DocumentRepository, DocumentSessionManager
from avge_engine.services.engine import get_document_operations, reset_documents, resolve_doc, set_active_doc


def test_engine_active_document_uses_session_manager():
    reset_documents()
    graph = get_document_operations()
    first = graph.create_document(name="first")
    second = graph.create_document(name="second")

    set_active_doc(first.id)
    assert resolve_doc(None) == first.id

    set_active_doc(second.id)
    assert resolve_doc(None) == second.id


def test_document_repository_uses_injected_session():
    reset_documents()
    graph = get_document_operations()
    first = graph.create_document(name="first")
    second = graph.create_document(name="second")
    session = DocumentSessionManager(graph)
    repo = DocumentRepository(graph, session)

    session.set_active(first.id)
    assert repo.require_id(None) == first.id

    session.set_active(second.id)
    assert repo.require_id(None) == second.id
