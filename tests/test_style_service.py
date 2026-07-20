from avge_engine.scene import Style
from avge_engine.services.engine import reset_graph
from avge_engine.services.style_service import StyleService


def _setup_scene():
    reset_graph()
    service = StyleService()
    graph = service.graph
    doc = graph.create_document(width=1000, height=800)
    graph.create_region(
        document_id=doc.id,
        region_id="near",
        outline=[(0.1, 0.65), (0.25, 0.65), (0.25, 0.8), (0.1, 0.8)],
        layer="props",
        z_index=5,
        style=Style(fill="#CC3333", stroke="#111111", stroke_width=0.002),
    )
    graph.create_region(
        document_id=doc.id,
        region_id="far",
        outline=[(0.1, 0.1), (0.22, 0.1), (0.22, 0.2), (0.1, 0.2)],
        layer="props",
        z_index=1,
        style=Style(fill="#CC3333", stroke="#111111", stroke_width=0.002),
    )
    graph.create_region(
        document_id=doc.id,
        region_id="other",
        outline=[(0.6, 0.65), (0.75, 0.65), (0.75, 0.8), (0.6, 0.8)],
        layer="other",
        z_index=0,
        style=Style(fill="#3366CC", stroke="#111111", stroke_width=0.002),
    )
    return service, doc


def test_style_service_apply_depth_haze_uses_selector():
    service, doc = _setup_scene()

    result = service.apply_depth_haze(
        document_id=doc.id,
        selector={"layer": "props"},
        haze_color="#99CCFF",
        near_y=0.8,
        far_y=0.1,
        max_strength=0.6,
    )

    assert result.affected == 2
    assert service.graph.get_region("far", doc.id).style.fill != "#CC3333"
    assert service.graph.get_region("other", doc.id).style.fill == "#3366CC"


def test_style_service_apply_line_hierarchy_uses_selector():
    service, doc = _setup_scene()
    other_width = service.graph.get_region("other", doc.id).style.stroke_width

    result = service.apply_line_hierarchy(
        document_id=doc.id,
        selector={"layer": "props"},
        outer_width=6,
        inner_width=2,
        basis="z_index",
    )

    assert result.outer_count == 1
    assert result.inner_count == 1
    assert service.graph.get_region("near", doc.id).style.stroke_width != 0.002
    assert service.graph.get_region("far", doc.id).style.stroke_width != 0.002
    assert service.graph.get_region("other", doc.id).style.stroke_width == other_width
