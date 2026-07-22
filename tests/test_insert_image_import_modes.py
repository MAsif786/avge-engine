from avge_engine.controllers import element
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
    element.create_tools(mcp)
    graph = element.get_graph()
    doc = graph.create_document(width=1000, height=800)
    return graph, doc, mcp


def test_insert_image_embed_local_file_as_data_uri(tmp_path):
    graph, doc, mcp = _setup()
    png = tmp_path / "tiny.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    graph.create_ellipse(0.25, 0.4, 0.1, document_id=doc.id, element_id="clip")

    result = mcp.tools["insert_image"](
        document_id=doc.id,
        x=0.1,
        y=0.2,
        width=0.3,
        height=0.4,
        href=str(png),
        element_id="embedded",
        import_mode="embed",
        clip_to="clip",
    )

    image = graph.get_element("embedded", doc.id)
    assert "mode=embed" in result
    assert image.primitive["href"].startswith("data:image/png;base64,")
    assert image.clip_to == "clip"


def test_insert_image_imports_svg_paths_as_editable_elements(tmp_path):
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
        element_id="icon",
        import_mode="svg_paths",
        stroke_width=2,
    )

    outer = graph.get_element("icon_00", doc.id)
    inner = graph.get_element("icon_01", doc.id)
    assert "SVG paths imported: elements=2" in result
    assert outer.style.fill == "#112233"
    assert outer.outline[2] == (0.6, 0.5)
    assert inner.style.fill is None
    assert inner.style.stroke == "#445566"
    assert {"name": "icon", "count": 2} in graph.list_groups(doc.id)
