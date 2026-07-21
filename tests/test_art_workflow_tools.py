from avge_engine.controllers import region, style
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
    style_mcp = _FakeMCP()
    region.create_tools(region_mcp)
    style.create_tools(style_mcp)
    graph = region.get_graph()
    doc = graph.create_document(width=1000, height=800)
    graph.create_region(
        document_id=doc.id,
        region_id="panel",
        outline=[(0.2, 0.2), (0.8, 0.2), (0.8, 0.7), (0.2, 0.7)],
        layer="base",
    )
    graph.create_line(
        points=[(0.25, 0.3), (0.45, 0.25), (0.65, 0.36)],
        document_id=doc.id,
        region_id="line",
        layer="ink",
    )
    return graph, doc, style_mcp


def test_apply_brush_style_updates_vector_style_and_metadata():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["apply_brush_style"](
        document_id=doc.id,
        selector={"ids": ["line"]},
        brush="g_pen",
        color="#111111",
        size=5,
        texture_strength=0.4,
    )

    line = graph.get_region("line", doc.id)
    overlays = [r for r in graph.get_all_regions(doc.id) if r.metadata.get("brush_overlay_for") == "line"]
    assert "Brush 'g_pen' applied" in result
    assert line.style.stroke == "#111111"
    assert line.metadata["brush"] == "g_pen"
    assert line.metadata["brush_pressure"] is True
    assert overlays


def test_apply_brush_style_supports_line_art_pen_presets():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["apply_brush_style"](
        document_id=doc.id,
        selector={"ids": ["line"]},
        brush="technical_pen",
    )

    line = graph.get_region("line", doc.id)
    assert "Brush 'technical_pen' applied" in result
    assert line.metadata["brush"] == "technical_pen"
    assert line.style.stroke == "#101010"


def test_list_brush_presets_exposes_generic_alias_groups():
    _, _, style_mcp = _setup()

    result = style_mcp.tools["list_brush_presets"](group="texture", include_details=False)

    assert result == {
        "texture": [
            "texture",
            "fabric_brush",
            "stone_brush",
            "wood_grain_brush",
            "metal_brush",
            "pattern_brush",
        ]
    }


def test_apply_brush_style_supports_background_and_fx_aliases():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["apply_brush_style"](
        document_id=doc.id,
        selector={"ids": ["line"]},
        brush="water_brush",
    )

    line = graph.get_region("line", doc.id)
    assert "Brush 'water_brush' applied" in result
    assert line.metadata["brush"] == "water_brush"
    assert line.style.blend_mode == "screen"


def test_refine_line_tool_corrects_existing_linework():
    graph, doc, _ = _setup()
    region_mcp = _FakeMCP()
    region.create_tools(region_mcp)

    result = region_mcp.tools["refine_line"](
        document_id=doc.id,
        region_id="line",
        mode="straighten",
        smoothness=0.0,
    )

    line = graph.get_region("line", doc.id)
    assert "Line refined: id=line" in result
    assert len(line.outline) == 2
    assert line.constraints.smoothness == 0.0


def test_set_layer_role_normalizes_layer_metadata_and_style():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["set_layer_role"](
        document_id=doc.id,
        layer="base",
        role="shadow",
    )

    panel = graph.get_region("panel", doc.id)
    assert "role set to 'shadow'" in result
    assert panel.metadata["layer_role"] == "shadow"
    assert panel.style.blend_mode == "multiply"


def test_apply_texture_effect_creates_clipped_halftone_overlay():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["apply_texture_effect"](
        document_id=doc.id,
        effect="halftone",
        selector={"ids": ["panel"]},
        color="#000000",
        density=6,
        opacity=0.2,
        size=3,
    )

    created = [
        r for r in graph.get_all_regions(doc.id)
        if r.metadata.get("tool") == "apply_texture_effect"
    ]
    assert "Texture effect 'halftone'" in result
    assert created
    assert all(r.clip_to == "panel" for r in created)


def test_apply_texture_effect_creates_bloom_with_blur():
    graph, doc, style_mcp = _setup()

    style_mcp.tools["apply_texture_effect"](
        document_id=doc.id,
        effect="bloom",
        selector={"ids": ["panel"]},
        color="#8EEBFF",
        opacity=0.45,
        size=8,
    )

    blooms = [
        r for r in graph.get_all_regions(doc.id)
        if r.metadata.get("effect") == "bloom"
    ]
    assert len(blooms) == 1
    assert blooms[0].style.blur > 0
    assert blooms[0].style.blend_mode == "screen"
