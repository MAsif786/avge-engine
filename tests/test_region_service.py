from avge_engine.scene import Style
from avge_engine.services.engine import reset_graph
from avge_engine.services.region_service import RegionService


def _setup_scene():
    reset_graph()
    service = RegionService()
    graph = service.graph
    source = graph.create_document(width=1000, height=800, name="source")
    target = graph.create_document(width=1000, height=800, name="target")
    graph.create_region(
        document_id=source.id,
        region_id="box",
        outline=[(0.2, 0.2), (0.4, 0.2), (0.4, 0.4), (0.2, 0.4)],
        layer="props",
        style=Style(fill="#CC3333", stroke="#111111", stroke_width=0.002),
        metadata={"kind": "prop"},
    )
    graph.group_regions("props", ["box"], document_id=source.id)
    return service, source, target


def test_region_service_edit_region_point_and_style():
    service, source, _ = _setup_scene()

    result = service.edit_region(
        document_id=source.id,
        region_id="box",
        point_index=0,
        point_dx=0.05,
        fill="#00AA66",
    )

    box = service.graph.get_region("box", source.id)
    assert result.affected == ["box"]
    assert box.outline[0] == (0.25, 0.2)
    assert box.style.fill == "#00AA66"


def test_region_service_edit_regions_rejects_transform_params():
    service, source, _ = _setup_scene()

    result = service.edit_regions(
        document_id=source.id,
        updates=[{"id": "box", "dx": 0.1}],
    )

    assert result.ok == 0
    assert "moved to transform_objects" in result.lines[0]


def test_region_service_delete_regions():
    service, source, _ = _setup_scene()

    deleted = service.delete_regions(document_id=source.id, ids=["box", "missing"])

    assert deleted == ["box"]


def test_region_service_refine_line_straightens_existing_curve():
    service, source, _ = _setup_scene()
    service.graph.create_line(
        points=[(0.1, 0.1), (0.2, 0.18), (0.3, 0.12), (0.4, 0.2)],
        document_id=source.id,
        region_id="rough_line",
    )

    result = service.refine_line(
        document_id=source.id,
        region_id="rough_line",
        mode="straighten",
        smoothness=0.0,
    )

    line = service.graph.get_region("rough_line", source.id)
    assert result.before_points == 4
    assert result.after_points == 2
    assert line.outline == [(0.1, 0.1), (0.4, 0.2)]
    assert line.constraints.smoothness == 0.0
    assert line.metadata["line_refinement"] == "straighten"


def test_region_service_refine_line_simplifies_noisy_curve():
    service, source, _ = _setup_scene()
    service.graph.create_line(
        points=[
            (0.1, 0.1),
            (0.15, 0.101),
            (0.2, 0.102),
            (0.3, 0.2),
            (0.4, 0.3),
        ],
        document_id=source.id,
        region_id="noisy_line",
    )

    result = service.refine_line(
        document_id=source.id,
        region_id="noisy_line",
        mode="simplify",
        simplify_tolerance=0.02,
    )

    assert result.after_points < result.before_points


def test_region_service_copy_element_offsets_primitive_and_outline():
    service, source, target = _setup_scene()

    result = service.copy_element(
        source_document_id=source.id,
        target_document_id=target.id,
        region_id="box",
        new_region_id="box_copy",
        offset_x=0.1,
        offset_y=0.05,
    )

    copied = service.graph.get_region("box_copy", target.id)
    assert result.copied_ids == ["box_copy"]
    assert copied.outline[0] == (0.3, 0.25)
    assert copied.metadata == {"kind": "prop"}


def test_region_service_copy_group_reports_missing_group():
    service, source, target = _setup_scene()

    try:
        service.copy_element(
            source_document_id=source.id,
            target_document_id=target.id,
            group_name="missing",
        )
    except LookupError as exc:
        assert "Group 'missing' not found in source" in str(exc)
    else:
        raise AssertionError("expected missing group error")
