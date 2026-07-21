from avge_engine.controllers import region
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
    mcp = _FakeMCP()
    region.create_tools(mcp)
    graph = region.get_graph()
    doc = graph.create_document(width=1000, height=800)
    return graph, doc, mcp


def test_insert_image_embed_local_file_as_data_uri(tmp_path):
    graph, doc, mcp = _setup()
    png = tmp_path / "tiny.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    result = mcp.tools["insert_image"](
        document_id=doc.id,
        x=0.1,
        y=0.2,
        width=0.3,
        height=0.4,
        href=str(png),
        region_id="embedded",
        import_mode="embed",
    )

    image = graph.get_region("embedded", doc.id)
    assert "mode=embed" in result
    assert image.primitive["href"].startswith("data:image/png;base64,")


def test_insert_image_imports_svg_paths_as_editable_regions(tmp_path):
    graph, doc, mcp = _setup()
    svg = tmp_path / "icon.svg"
    svg.write_text(
        '<svg viewBox="0 0 100 100">'
        '<path d="M 0 0 L 100 0 L 100 100 L 0 100 Z" fill="#112233"/>'
        '<path d="M 25 25 L 75 25 L 75 75 L 25 75 Z" stroke="#445566" fill="none"/>'
        '</svg>'
    )

    result = mcp.tools["insert_image"](
        document_id=doc.id,
        x=0.2,
        y=0.3,
        width=0.4,
        height=0.2,
        href=str(svg),
        region_id="icon",
        import_mode="svg_paths",
        stroke_width=2,
    )

    outer = graph.get_region("icon_00", doc.id)
    inner = graph.get_region("icon_01", doc.id)
    assert "SVG paths imported: regions=2" in result
    assert outer.style.fill == "#112233"
    assert outer.outline[2] == (0.6, 0.5)
    assert inner.style.fill is None
    assert inner.style.stroke == "#445566"
    assert {"name": "icon", "count": 2} in graph.list_groups(doc.id)
