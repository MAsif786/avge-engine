from avge_engine.controllers import procedural, scene_ops, scene_view, style
from avge_engine.document import Style
from avge_engine.services.document_structure_service import DocumentStructureService
from avge_engine.services.engine import get_document_operations, reset_documents


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_create_perspective_grid_clips_off_canvas_vanishing_points():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()

    result = mcp.tools["create_perspective_grid"](
        document_id=doc.id,
        vanishing_points=[[-1.2, 0.42], [2.0, 0.42]],
        horizon_y=0.42,
        verticals=3,
        horizontals=4,
        element_id="street_guides",
    )

    assert "Perspective grid created" in result
    grid = graph.get_element("street_guides", doc.id)
    assert grid.primitive["type"] == "compound_path"
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in grid.outline)
    assert graph.has_element("street_guides_horizon", doc.id)


def test_create_facade_grid_creates_base_and_windows_with_lit_ratio():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()

    result = mcp.tools["create_facade_grid"](
        document_id=doc.id,
        element_id="tower",
        target_quad=[[0.2, 0.1], [0.5, 0.15], [0.55, 0.75], [0.18, 0.7]],
        rows=4,
        columns=3,
        lit_ratio=0.5,
        seed=7,
    )

    assert "Facade grid created: tower" in result
    assert graph.has_element("tower", doc.id)
    windows = [r for r in graph.get_all_elements(doc.id) if r.metadata.get("facade") == "tower"]
    assert len(windows) == 12
    assert any(r.metadata.get("lit") for r in windows)
    assert any(not r.metadata.get("lit") for r in windows)


def test_apply_depth_haze_blends_far_element_toward_haze_color():
    reset_documents()
    scene_mcp = _FakeMCP()
    style_mcp = _FakeMCP()
    scene_ops.create_tools(scene_mcp)
    style.create_tools(style_mcp)
    graph = get_document_operations()
    doc = graph.create_document()
    graph.create_element(
        document_id=doc.id,
        element_id="far_building",
        outline=[(0.1, 0.1), (0.3, 0.1), (0.3, 0.25), (0.1, 0.25)],
    )

    result = style_mcp.tools["apply_depth_haze"](
        document_id=doc.id,
        selector={"ids": ["far_building"]},
        haze_color="#FFFFFF",
        near_y=0.8,
        far_y=0.2,
        max_strength=0.5,
    )

    assert "Depth haze applied to 1 element" in result
    assert graph.get_element("far_building", doc.id).style.fill != "#CCCCCC"


def test_duplicate_linear_supports_spacing_and_scale_falloff():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()
    graph.create_element(
        document_id=doc.id,
        element_id="pole",
        outline=[(0.1, 0.7), (0.12, 0.7), (0.12, 0.9), (0.1, 0.9)],
    )

    result = mcp.tools["duplicate"](
        document_id=doc.id,
        pattern="linear",
        element_id="pole",
        count=3,
        dx=0.1,
        dy=-0.05,
        spacing_falloff=0.5,
        scale_falloff=0.8,
    )

    assert "Duplicated" in result
    first = graph.get_element("pole_copy_0", doc.id)
    second = graph.get_element("pole_copy_1", doc.id)
    assert first.outline[0][0] == 0.2
    assert second.outline[0][0] < 0.3


def test_duplicate_scatter_places_copies_inside_bounds_by_center():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()
    graph.create_element(
        document_id=doc.id,
        element_id="leaf",
        outline=[(0.1, 0.1), (0.12, 0.1), (0.12, 0.12), (0.1, 0.12)],
    )

    result = mcp.tools["duplicate"](
        document_id=doc.id,
        pattern="scatter",
        element_id="leaf",
        count=5,
        bounds=[0.4, 0.3, 0.2, 0.1],
        seed=7,
    )

    assert "Duplicated" in result
    for i in range(5):
        copy = graph.get_element(f"leaf_scatter_{i}", doc.id)
        xs = [p[0] for p in copy.outline]
        ys = [p[1] for p in copy.outline]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        assert 0.4 <= cx <= 0.6
        assert 0.3 <= cy <= 0.4


def test_duplicate_missing_element_message_includes_pattern():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()

    result = mcp.tools["duplicate"](
        document_id=doc.id,
        pattern="scatter",
        count=3,
        bounds=[0.1, 0.1, 0.2, 0.2],
    )

    assert result == "Error: element_id required for pattern 'scatter'"


def test_add_shading_gradient_styles_existing_element():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()
    graph.create_element(
        document_id=doc.id,
        element_id="facade",
        outline=[(0.2, 0.2), (0.6, 0.2), (0.6, 0.7), (0.2, 0.7)],
        style=Style(fill="#406070"),
    )

    result = mcp.tools["add_shading"](
        document_id=doc.id,
        element_id="facade",
        mode="gradient",
        light_direction=135,
        intensity=0.4,
    )

    facade = graph.get_element("facade", doc.id)
    assert "Gradient shading applied" in result
    assert facade.style.fill["type"] == "linear"
    assert len(facade.style.fill["stops"]) == 3


def test_generate_cloud_creates_soft_layered_elements():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()

    result = mcp.tools["generate_cloud"](
        document_id=doc.id,
        element_id="cloud",
        cx=0.45,
        cy=0.18,
        width=0.28,
        height=0.08,
        puff_count=5,
        seed=4,
    )

    cloud_elements = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("tool") == "generate_cloud"
    ]
    assert "Cloud generated: cloud" in result
    assert len(cloud_elements) >= 6
    assert any(r.style.blur > 0 for r in cloud_elements)
    assert {r.metadata.get("part") for r in cloud_elements} >= {"shade", "puff", "body"}


def test_generate_background_asset_facade_detail_groups_parts():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()

    result = mcp.tools["generate_background_asset"](
        document_id=doc.id,
        mode="facade_detail",
        bounds=[0.2, 0.2, 0.4, 0.5],
        element_id="facade_bits",
        count=12,
        detail=["mullions", "sills", "cornice"],
    )

    created = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("tool") == "generate_background_asset"
    ]
    assert "Background asset generated: mode=facade_detail" in result
    assert len(created) >= 5
    assert {r.metadata["part"] for r in created} >= {"mullion", "sill", "cornice"}
    assert {"name": "facade_bits", "count": len(created)} in DocumentStructureService(graph).list_groups(document_id=doc.id)


def test_generate_background_asset_tree_cluster_creates_trunks_and_leaves():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()

    result = mcp.tools["generate_background_asset"](
        document_id=doc.id,
        mode="tree_cluster",
        bounds=[0.1, 0.5, 0.3, 0.25],
        count=3,
        seed=4,
    )

    created = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("mode") == "tree_cluster"
    ]
    assert "Background asset generated: mode=tree_cluster" in result
    assert any(r.metadata.get("part") == "trunk" for r in created)
    assert any(r.metadata.get("part") == "leaf" for r in created)


def test_create_comic_panel_layout_grid_adds_reading_order_metadata():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1200, height=1600)

    result = mcp.tools["create_comic_panel_layout"](
        document_id=doc.id,
        layout="grid",
        rows=2,
        columns=2,
        bounds=[0.05, 0.05, 0.9, 0.9],
        panel_prefix="page_panel",
        group_name="page_one",
        reading_direction="rtl",
    )

    panels = [graph.get_element(f"page_panel_{i:02d}", doc.id) for i in range(1, 5)]
    assert "Comic panel layout created: layout=grid, panels=4" in result
    assert {p.metadata["reading_index"] for p in panels} == {0, 1, 2, 3}
    assert panels[1].metadata["reading_index"] == 0
    assert {"name": "page_one", "count": 4} in DocumentStructureService(graph).list_groups(document_id=doc.id)


def test_create_comic_panel_layout_feature_top_creates_large_opening_panel():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()

    mcp.tools["create_comic_panel_layout"](
        document_id=doc.id,
        layout="feature_top",
        count=3,
        bounds=[0.1, 0.1, 0.8, 0.8],
        panel_prefix="story",
    )

    top = graph.get_element("story_01", doc.id)
    lower = graph.get_element("story_02", doc.id)
    top_height = top.outline[2][1] - top.outline[0][1]
    lower_height = lower.outline[2][1] - lower.outline[0][1]
    assert top_height > lower_height * 0.75
    assert top.metadata["clip_content"] is True


def test_create_surface_stripes_projects_repeated_road_markings():
    reset_documents()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document(width=1200, height=800)

    result = mcp.tools["create_surface_stripes"](
        document_id=doc.id,
        element_id="crosswalk",
        target_quad=[[0.35, 0.45], [0.65, 0.45], [0.92, 0.82], [0.08, 0.82]],
        count=4,
        orientation="u",
        stripe_width=0.08,
        spacing_falloff=0.75,
        stroke_width=2,
    )

    stripes = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("tool") == "create_surface_stripes"
    ]
    assert "Surface stripes created: 4" in result
    assert len(stripes) == 4
    assert all(r.style.stroke_width == 0.0025 for r in stripes)


def test_environment_densify_generate_shape_patterns():
    reset_documents()
    mcp = _FakeMCP()
    procedural.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()
    graph.create_element(
        document_id=doc.id,
        element_id="shop",
        outline=[(0.15, 0.25), (0.45, 0.25), (0.45, 0.72), (0.15, 0.72)],
    )

    assert "cornice: created" in mcp.tools["generate_shape"](
        document_id=doc.id,
        pattern="cornice",
        params={"element_id": "shop", "element_id_out": "shop_cornice", "style": "stepped"},
    )
    assert "awning: created" in mcp.tools["generate_shape"](
        document_id=doc.id,
        pattern="awning",
        params={"element_id": "shop", "element_id_out": "shop_awning", "stripe_count": 3},
    )
    assert "rooftop_props: created" in mcp.tools["generate_shape"](
        document_id=doc.id,
        pattern="rooftop_props",
        params={"element_id": "shop", "count": 4, "seed": 9},
    )

    assert graph.has_element("shop_cornice", doc.id)
    assert graph.has_element("shop_awning", doc.id)
    assert len([r for r in graph.get_all_elements(doc.id) if r.metadata.get("pattern") == "rooftop_props"]) == 4


def test_export_svg_can_exclude_construction_guides(tmp_path):
    reset_documents()
    mcp = _FakeMCP()
    scene_view.create_tools(mcp)
    graph = get_document_operations()
    doc = graph.create_document()
    graph.create_element(
        document_id=doc.id,
        element_id="final_building",
        outline=[(0.2, 0.2), (0.5, 0.2), (0.5, 0.7), (0.2, 0.7)],
        layer="architecture",
        style=Style(fill="#223344"),
    )
    graph.create_element(
        document_id=doc.id,
        element_id="guide_line",
        outline=[(0.0, 0.4), (1.0, 0.4)],
        layer="guides",
        style=Style(fill=None, stroke="#FF00FF"),
    )
    output = tmp_path / "scene.svg"

    result = mcp.tools["export_svg"](
        document_id=doc.id,
        filepath=str(output),
        exclude_layers=["guides"],
    )
    svg = output.read_text()

    assert "SVG saved" in result
    assert "#223344" in svg
    assert "#FF00FF" not in svg
