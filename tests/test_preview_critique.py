import json

from avge_engine.controllers import query
from avge_engine.scene import CurveConstraints, SceneGraph, Style
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def _codes(findings):
    return {f["code"] for f in findings}


def test_preview_critique_flags_too_flat_and_missing_contact_shadows():
    scene = SceneGraph()
    doc = scene.create_document()
    for i in range(6):
        x = 0.08 + i * 0.13
        scene.create_region(
            document_id=doc.id,
            region_id=f"flat_{i}",
            outline=[(x, 0.52), (x + 0.09, 0.52), (x + 0.09, 0.72), (x, 0.72)],
            style=Style(fill="#CC3333", stroke="#333333"),
        )

    findings = scene.critique_preview_quality(doc.id)

    assert "too_flat" in _codes(findings)
    assert "missing_contact_shadows" in _codes(findings)


def test_preview_critique_flags_over_rounded_rects():
    scene = SceneGraph()
    doc = scene.create_document()
    for i in range(4):
        scene.create_rect(
            0.1 + i * 0.18,
            0.3,
            0.12,
            0.12,
            rx=0.06,
            document_id=doc.id,
            region_id=f"pill_{i}",
        )

    findings = scene.critique_preview_quality(doc.id)

    assert "over_rounded" in _codes(findings)


def test_preview_critique_flags_bad_perspective_quad():
    scene = SceneGraph()
    doc = scene.create_document()
    scene.create_region(
        document_id=doc.id,
        region_id="skewed_panel",
        outline=[(0.2, 0.2), (0.7, 0.25), (0.8, 0.65), (0.3, 0.6)],
        constraints=CurveConstraints(smoothness=0.0, closed=True),
        style=Style(fill={"type": "linear", "x1": 0, "y1": 0, "x2": 1, "y2": 1,
                          "stops": [{"offset": 0, "color": "#EEEEEE"}, {"offset": 1, "color": "#AAAAAA"}]}),
    )
    scene.create_region(
        document_id=doc.id,
        region_id="support",
        outline=[(0.1, 0.7), (0.9, 0.7), (0.9, 0.78), (0.1, 0.78)],
    )

    findings = scene.critique_preview_quality(doc.id)

    assert "bad_perspective" in _codes(findings)


def test_preview_critique_flags_dominant_blob_shape():
    scene = SceneGraph()
    doc = scene.create_document()
    scene.create_region(
        document_id=doc.id,
        region_id="blob",
        outline=[
            (0.12, 0.2), (0.24, 0.1), (0.48, 0.08), (0.72, 0.16),
            (0.88, 0.36), (0.82, 0.68), (0.54, 0.86), (0.22, 0.76),
            (0.08, 0.52), (0.1, 0.32),
        ],
        constraints=CurveConstraints(smoothness=0.75, closed=True),
        style=Style(fill="#66AA77"),
    )
    for i in range(3):
        scene.create_region(
            document_id=doc.id,
            region_id=f"detail_{i}",
            outline=[(0.2 + i * 0.1, 0.3), (0.24 + i * 0.1, 0.3), (0.24 + i * 0.1, 0.34), (0.2 + i * 0.1, 0.34)],
            style=Style(fill="#224433"),
        )

    findings = scene.critique_preview_quality(doc.id)

    assert "dominant_blob_shape" in _codes(findings)


def test_critique_tool_visual_json_output():
    reset_graph()
    mcp = _FakeMCP()
    query.create_tools(mcp)
    graph = query.get_graph()
    doc = graph.create_document()
    for i in range(4):
        graph.create_region(
            document_id=doc.id,
            region_id=f"obj_{i}",
            outline=[(0.1 + i * 0.15, 0.55), (0.2 + i * 0.15, 0.55), (0.2 + i * 0.15, 0.75), (0.1 + i * 0.15, 0.75)],
        )

    payload = mcp.tools["critique"](document_id=doc.id, mode="visual", as_json=True)
    data = json.loads(payload)

    assert data["count"] >= 1
    assert "visual" in data
    assert all("code" in f for f in data["visual"]["findings"])


def test_critique_tool_both_json_output_includes_rules_and_visual():
    reset_graph()
    mcp = _FakeMCP()
    query.create_tools(mcp)
    graph = query.get_graph()
    doc = graph.create_document()
    for i in range(6):
        graph.create_region(
            document_id=doc.id,
            region_id=f"obj_{i}",
            outline=[(0.1 + i * 0.1, 0.55), (0.17 + i * 0.1, 0.55), (0.17 + i * 0.1, 0.7), (0.1 + i * 0.1, 0.7)],
        )

    payload = mcp.tools["critique"](document_id=doc.id, mode="both", as_json=True)
    data = json.loads(payload)

    assert data["mode"] == "both"
    assert "rules" in data
    assert "visual" in data
