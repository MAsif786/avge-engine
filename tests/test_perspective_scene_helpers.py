from avge_engine.controllers import scene_ops, style
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_create_perspective_grid_clips_off_canvas_vanishing_points():
    reset_graph()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document()

    result = mcp.tools["create_perspective_grid"](
        document_id=doc.id,
        vanishing_points=[[-1.2, 0.42], [2.0, 0.42]],
        horizon_y=0.42,
        verticals=3,
        horizontals=4,
        region_id="street_guides",
    )

    assert "Perspective grid created" in result
    grid = graph.get_region("street_guides", doc.id)
    assert grid.primitive["type"] == "compound_path"
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in grid.outline)
    assert graph.has_region("street_guides_horizon", doc.id)


def test_create_facade_grid_creates_base_and_windows_with_lit_ratio():
    reset_graph()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document()

    result = mcp.tools["create_facade_grid"](
        document_id=doc.id,
        region_id="tower",
        target_quad=[[0.2, 0.1], [0.5, 0.15], [0.55, 0.75], [0.18, 0.7]],
        rows=4,
        columns=3,
        lit_ratio=0.5,
        seed=7,
    )

    assert "Facade grid created: tower" in result
    assert graph.has_region("tower", doc.id)
    windows = [r for r in graph.get_all_regions(doc.id) if r.metadata.get("facade") == "tower"]
    assert len(windows) == 12
    assert any(r.metadata.get("lit") for r in windows)
    assert any(not r.metadata.get("lit") for r in windows)


def test_apply_depth_haze_blends_far_region_toward_haze_color():
    reset_graph()
    scene_mcp = _FakeMCP()
    style_mcp = _FakeMCP()
    scene_ops.create_tools(scene_mcp)
    style.create_tools(style_mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document()
    graph.create_region(
        document_id=doc.id,
        region_id="far_building",
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

    assert "Depth haze applied to 1 region" in result
    assert graph.get_region("far_building", doc.id).style.fill != "#CCCCCC"


def test_duplicate_linear_supports_spacing_and_scale_falloff():
    reset_graph()
    mcp = _FakeMCP()
    scene_ops.create_tools(mcp)
    graph = scene_ops.get_graph()
    doc = graph.create_document()
    graph.create_region(
        document_id=doc.id,
        region_id="pole",
        outline=[(0.1, 0.7), (0.12, 0.7), (0.12, 0.9), (0.1, 0.9)],
    )

    result = mcp.tools["duplicate"](
        document_id=doc.id,
        pattern="linear",
        region_id="pole",
        count=3,
        dx=0.1,
        dy=-0.05,
        spacing_falloff=0.5,
        scale_falloff=0.8,
    )

    assert "Duplicated" in result
    first = graph.get_region("pole_copy_0", doc.id)
    second = graph.get_region("pole_copy_1", doc.id)
    assert first.outline[0][0] == 0.2
    assert second.outline[0][0] < 0.3
