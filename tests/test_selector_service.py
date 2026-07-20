from avge_engine.services.engine import reset_graph
from avge_engine.services.selector_service import SelectorService, selector_from_legacy


def _setup_scene():
    reset_graph()
    from avge_engine.services.engine import get_graph

    graph = get_graph()
    doc = graph.create_document(width=1000, height=800)
    graph.create_region(
        document_id=doc.id,
        region_id="near_red",
        outline=[(0.1, 0.65), (0.2, 0.65), (0.2, 0.8), (0.1, 0.8)],
        layer="props",
        metadata={"kind": "target"},
    )
    graph.edit_region("near_red", document_id=doc.id, fill="#CC3333")
    graph.create_region(
        document_id=doc.id,
        region_id="far_red",
        outline=[(0.12, 0.12), (0.22, 0.12), (0.22, 0.24), (0.12, 0.24)],
        layer="props",
        metadata={"kind": "target"},
    )
    graph.edit_region("far_red", document_id=doc.id, fill="#CC3333")
    graph.create_region(
        document_id=doc.id,
        region_id="blue",
        outline=[(0.55, 0.65), (0.7, 0.65), (0.7, 0.8), (0.55, 0.8)],
        layer="other",
        metadata={"kind": "skip"},
    )
    graph.edit_region("blue", document_id=doc.id, fill="#3366CC")
    graph.group_regions("targets", ["near_red", "far_red"], document_id=doc.id)
    return graph, doc


def test_selector_service_filters_group_and_bounds():
    graph, doc = _setup_scene()
    selector = SelectorService(graph)

    result = selector.select_region_ids(
        doc.id,
        {"group_name": "targets", "bounds": {"max_y": 0.3}},
    )

    assert result == ["far_red"]


def test_selector_service_default_all_and_legacy_selector():
    graph, doc = _setup_scene()
    selector = SelectorService(graph)

    assert len(selector.select_region_ids(doc.id, None, default_all=True)) == 3
    assert selector_from_legacy(ids=["blue"]) == {"ids": ["blue"]}
