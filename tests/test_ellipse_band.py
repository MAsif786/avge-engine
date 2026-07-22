from avge_engine.controllers import element as element_controller
from avge_engine.geometry import compute_bounds
from avge_engine.geometry.procedural import ellipse_band
from avge_engine.services.engine import reset_graph


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def _decorator(fn):
            self.tools[name] = fn
            return fn
        return _decorator


def test_ellipse_band_full_ring_outline():
    pts = ellipse_band(0.5, 0.5, 0.3, 0.12, thickness=0.03, samples=16)

    assert len(pts) == 34
    bounds = compute_bounds(pts)
    assert bounds["x"] < 0.21
    assert bounds["x"] + bounds["w"] > 0.79
    assert bounds["y"] < 0.39
    assert bounds["y"] + bounds["h"] > 0.61


def test_ellipse_band_partial_arc_outline():
    pts = ellipse_band(
        0.5,
        0.5,
        0.3,
        0.12,
        thickness=0.04,
        start_angle=0,
        end_angle=180,
        samples=8,
    )

    assert len(pts) == 18
    # Partial band should not cover the upper half for this angle range.
    assert min(y for _, y in pts) >= 0.49


def test_ellipse_band_perspective_widens_near_side():
    flat = ellipse_band(0.5, 0.5, 0.3, 0.12, thickness=0.03, samples=24)
    persp = ellipse_band(0.5, 0.5, 0.3, 0.12, thickness=0.03, samples=24, perspective=0.3)

    flat_bottom = max(x for x, y in flat if y > 0.59) - min(x for x, y in flat if y > 0.59)
    persp_bottom = max(x for x, y in persp if y > 0.59) - min(x for x, y in persp if y > 0.59)
    assert persp_bottom > flat_bottom


def test_create_ellipse_band_controller_tool_creates_element():
    reset_graph()
    mcp = _FakeMCP()
    element_controller.create_tools(mcp)
    doc = element_controller.get_graph().create_document()

    result = mcp.tools["create_ellipse_band"](
        document_id=doc.id,
        element_id="ring",
        cx=0.5,
        cy=0.5,
        rx=0.3,
        ry=0.12,
        thickness=0.035,
        fill="#445566",
        stroke="none",
        samples=12,
    )

    assert "Ellipse band created: id=ring" in result
    created = element_controller.get_graph().get_element("ring", doc.id)
    assert len(created.outline) == 26
    assert created.style.fill == "#445566"
    assert created.style.stroke is None
