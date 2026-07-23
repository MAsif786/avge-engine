from avge_engine.controllers import element, style
from avge_engine.effects import Style
from avge_engine.services.engine import get_document_operations, reset_documents


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def _setup():
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
        layer="base",
    )
    graph.create_line(
        points=[(0.25, 0.3), (0.45, 0.25), (0.65, 0.36)],
        document_id=doc.id,
        element_id="line",
        layer="ink",
    )
    graph.create_element(
        document_id=doc.id,
        element_id="warm",
        outline=[(0.1, 0.75), (0.25, 0.75), (0.25, 0.9), (0.1, 0.9)],
        layer="swatches",
        style=Style(fill="#FF0000"),
    )
    graph.create_element(
        document_id=doc.id,
        element_id="cool",
        outline=[(0.3, 0.75), (0.45, 0.75), (0.45, 0.9), (0.3, 0.9)],
        layer="swatches",
        style=Style(fill="#0000FF"),
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

    line = graph.get_element("line", doc.id)
    overlays = [r for r in graph.get_all_elements(doc.id) if r.metadata.get("brush_overlay_for") == "line"]
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

    line = graph.get_element("line", doc.id)
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

    line = graph.get_element("line", doc.id)
    assert "Brush 'water_brush' applied" in result
    assert line.metadata["brush"] == "water_brush"
    assert line.style.blend_mode == "screen"


def test_refine_line_tool_corrects_existing_linework():
    graph, doc, _ = _setup()
    element_mcp = _FakeMCP()
    element.create_tools(element_mcp)

    result = element_mcp.tools["refine_line"](
        document_id=doc.id,
        element_id="line",
        mode="straighten",
        smoothness=0.0,
    )

    line = graph.get_element("line", doc.id)
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

    panel = graph.get_element("panel", doc.id)
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
        r for r in graph.get_all_elements(doc.id)
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
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("effect") == "bloom"
    ]
    assert len(blooms) == 1
    assert blooms[0].style.blur > 0
    assert blooms[0].style.blend_mode == "screen"


def test_apply_fx_creates_speed_lines_from_bounds():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["apply_fx"](
        document_id=doc.id,
        type="speed_lines",
        bounds=[0.1, 0.1, 0.6, 0.4],
        count=8,
        direction=12,
        size=2,
    )

    created = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("tool") == "apply_fx"
    ]
    assert "FX 'speed_lines' created 8 element" in result
    assert all(r.metadata["fx_type"] == "speed_lines" for r in created)
    assert all(r.style.blend_mode == "screen" for r in created)


def test_apply_fx_motion_blur_uses_selector_source_elements():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["apply_fx"](
        document_id=doc.id,
        type="motion_blur",
        selector={"ids": ["panel"]},
        count=3,
        length=0.05,
        color="#88CCFF",
    )

    trails = [
        r for r in graph.get_all_elements(doc.id)
        if r.metadata.get("fx_type") == "motion_blur"
    ]
    assert "FX 'motion_blur' created 3 element" in result
    assert all(r.metadata.get("source") == "panel" for r in trails)


def test_mix_element_colors_can_return_mixed_color():
    _, doc, style_mcp = _setup()

    result = style_mcp.tools["mix_element_colors"](
        document_id=doc.id,
        source_element_id="warm",
        target_element_id="cool",
        mix_ratio=0.5,
    )

    assert result["mixed_color"] == "#800080"
    assert result["source_color"] == "#FF0000"
    assert result["target_color"] == "#0000FF"


def test_mix_element_colors_can_apply_to_target():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["mix_element_colors"](
        document_id=doc.id,
        source_element_id="warm",
        target_element_id="cool",
        mix_ratio=0.25,
        output="apply_target",
    )

    cool = graph.get_element("cool", doc.id)
    assert "applied to target element 'cool'" in result
    assert cool.style.fill == "#BF0040"
    assert cool.metadata["mixed_color"] == "#BF0040"


def test_mix_element_colors_can_create_new_element():
    graph, doc, style_mcp = _setup()

    result = style_mcp.tools["mix_element_colors"](
        document_id=doc.id,
        source_element_id="warm",
        target_element_id="cool",
        mix_ratio=0.75,
        output="new_element",
        new_element_id="mixed_swatch",
    )

    mixed = graph.get_element("mixed_swatch", doc.id)
    assert "created new element 'mixed_swatch'" in result
    assert mixed.style.fill == "#4000BF"
    assert mixed.metadata["tool"] == "mix_element_colors"
