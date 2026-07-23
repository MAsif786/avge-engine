from avge_engine.controllers import element, style
from avge_engine.services.engine import get_document_operations, reset_documents


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def _setup_scene():
    reset_documents()
    element_mcp = _FakeMCP()
    style_mcp = _FakeMCP()
    element.create_tools(element_mcp)
    style.create_tools(style_mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1000, height=800)
    graph.create_element(
        document_id=doc.id,
        element_id="panel",
        outline=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.7), (0.2, 0.7)],
    )
    return graph, doc, style_mcp


def test_restyle_material_applies_base_style_and_details():
    graph, doc, style_mcp = _setup_scene()

    result = style_mcp.tools["restyle"](
        document_id=doc.id,
        selector={"ids": ["panel"]},
        material="glass",
    )

    panel = graph.get_element("panel", doc.id)
    detail_elements = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("material_source") == "panel"
    ]
    assert "Material 'glass' applied" in result
    assert isinstance(panel.style.fill, dict)
    assert panel.style.opacity == 0.58
    assert len(detail_elements) == 2
    assert all(r.clip_to == "panel" for r in detail_elements)


def test_restyle_material_detail_can_be_disabled():
    graph, doc, style_mcp = _setup_scene()

    style_mcp.tools["restyle"](
        document_id=doc.id,
        selector={"ids": ["panel"]},
        material="brushed_metal",
        material_detail=False,
    )

    detail_elements = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("material_source") == "panel"
    ]
    assert detail_elements == []


def test_restyle_material_replaces_previous_details():
    graph, doc, style_mcp = _setup_scene()

    style_mcp.tools["restyle"](
        document_id=doc.id,
        selector={"ids": ["panel"]},
        material="glass",
    )
    first_detail_ids = {
        r.id for r in graph.get_all_elements(doc.id)
        if r.metadata.get("material_source") == "panel"
    }

    style_mcp.tools["restyle"](
        document_id=doc.id,
        selector={"ids": ["panel"]},
        material="wood",
    )
    second_detail_ids = {
        r.id for r in graph.get_all_elements(doc.id)
        if r.metadata.get("material_source") == "panel"
    }

    assert first_detail_ids
    assert second_detail_ids
    assert first_detail_ids.isdisjoint(second_detail_ids)
    assert all("_wood_" in rid for rid in second_detail_ids)
