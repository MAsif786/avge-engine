from avge_engine.scene import Style
from avge_engine.services.engine import reset_graph
from avge_engine.services.shadow_service import ShadowService


def _setup_scene():
    reset_graph()
    service = ShadowService()
    graph = service.graph
    doc = graph.create_document(width=1000, height=800)
    graph.create_element(
        document_id=doc.id,
        element_id="box",
        outline=[(0.2, 0.2), (0.4, 0.2), (0.4, 0.4), (0.2, 0.4)],
        z_index=5,
        style=Style(fill="#6699CC", stroke="#111111", stroke_width=0.002),
    )
    graph.create_element(
        document_id=doc.id,
        element_id="floor",
        outline=[(0.1, 0.5), (0.9, 0.5), (0.9, 0.9), (0.1, 0.9)],
        layer="floor",
        z_index=2,
        style=Style(fill="#DDDDDD", stroke=None),
    )
    return service, doc


def test_shadow_service_creates_clipped_shadow():
    service, doc = _setup_scene()

    result = service.create_shadow(
        document_id=doc.id,
        element_id="box",
        onto_element_id="floor",
        new_element_id="box_cast",
        z_offset=1,
    )

    shadow = service.graph.get_element("box_cast", doc.id)
    assert result.clipped is True
    assert result.shadow.id == "box_cast"
    assert shadow.clip_to == "floor"
    assert shadow.layer == "floor"
    assert shadow.z_index == 3
    assert shadow.metadata["shadow_kind"] == "cast"


def test_shadow_service_adds_gradient_shading_by_selector():
    service, doc = _setup_scene()

    result = service.add_shading(
        document_id=doc.id,
        selector={"ids": ["box"]},
        mode="gradient",
        light_direction=135,
        intensity=0.4,
    )

    assert result.mode == "gradient"
    assert result.target_count == 1
    assert service.graph.get_element("box", doc.id).style.fill["type"] == "linear"
