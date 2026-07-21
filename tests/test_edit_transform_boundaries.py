from avge_engine.controllers import region, scene_ops
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def _setup():
    reset_graph()
    region_mcp = _FakeMCP()
    scene_mcp = _FakeMCP()
    region.create_tools(region_mcp)
    scene_ops.create_tools(scene_mcp)
    graph = region.get_graph()
    doc = graph.create_document(width=1000, height=800)
    graph.create_region(
        document_id=doc.id,
        region_id="box",
        outline=[(0.2, 0.2), (0.4, 0.2), (0.4, 0.4), (0.2, 0.4)],
    )
    return graph, doc, region_mcp, scene_mcp


def test_edit_region_uses_point_dx_not_whole_region_dx():
    graph, doc, region_mcp, _ = _setup()

    result = region_mcp.tools["edit_region"](
        document_id=doc.id,
        region_id="box",
        point_index=0,
        point_dx=0.05,
        point_dy=0.02,
    )
    box = graph.get_region("box", doc.id)

    assert result == "Region 'box' updated"
    assert box.outline[0] == (0.25, 0.22)
    assert box.outline[1] == (0.4, 0.2)


def test_edit_regions_rejects_whole_region_transform_params():
    _, doc, region_mcp, _ = _setup()

    result = region_mcp.tools["edit_regions"](
        document_id=doc.id,
        updates=[{"id": "box", "dx": 0.1}],
    )

    assert "0/1 updated" in result
    assert "moved to transform_objects" in result


def test_transform_objects_remains_transform_source_of_truth():
    graph, doc, _, scene_mcp = _setup()

    result = scene_mcp.tools["transform_objects"](
        document_id=doc.id,
        ids=["box"],
        dx=0.1,
        dy=0.05,
    )
    box = graph.get_region("box", doc.id)

    assert "Transformed" in result
    assert box.outline[0] == (0.3, 0.25)


def test_warp_region_bend_deforms_outline_without_affine_transform():
    graph, doc, _, scene_mcp = _setup()
    before = list(graph.get_region("box", doc.id).outline)

    result = scene_mcp.tools["warp_region"](
        document_id=doc.id,
        region_id="box",
        mode="bend",
        strength=0.1,
        axis="x",
    )

    box = graph.get_region("box", doc.id)
    assert "Warped region 'box': mode=bend" in result
    assert box.outline != before
    assert box.outline[0][1] > before[0][1]
    assert box.metadata["warp_mode"] == "bend"


def test_warp_region_handle_shift_moves_points_near_handle():
    graph, doc, _, scene_mcp = _setup()

    result = scene_mcp.tools["warp_region"](
        document_id=doc.id,
        region_id="box",
        mode="handle_shift",
        handles=[{"x": 0.4, "y": 0.2, "dx": 0.05, "dy": 0.02, "radius": 0.3}],
        falloff=1.0,
        preserve_corners=False,
    )

    box = graph.get_region("box", doc.id)
    assert "Warped region 'box': mode=handle_shift" in result
    assert box.outline[1][0] > 0.4
    assert box.primitive is None
