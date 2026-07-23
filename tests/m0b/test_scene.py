"""
M0b test suite — engine document layer, geometry engine, and determinism tests.
"""

import math

import pytest

from avge_engine.document import CurveConstraints, ElementNode, Style
from avge_engine.services.document_structure_service import DocumentStructureService
from avge_engine.services.engine import get_document_operations, reset_documents
from avge_engine.services.style_service import StyleService
from avge_engine.geometry import fit_curves, compute_bounds, normalize_outline
from avge_engine.renderer import svg_serialize


class TestDocumentLayer:
    def test_create_document(self):
        reset_documents()
        scene = get_document_operations()
        doc = scene.create_document(800, 600, background="#F0F0F0")
        assert doc.id.startswith("doc_")
        assert doc.width == 800
        assert doc.height == 600
        assert doc.unit == "px"

    def test_no_document_by_default(self):
        reset_documents()
        scene = get_document_operations()
        assert scene.has_document() is False

    def test_create_document_twice(self):
        """Multi-document: creating twice works, returns different IDs."""
        reset_documents()
        scene = get_document_operations()
        doc1 = scene.create_document()
        doc2 = scene.create_document()
        assert doc1.id != doc2.id

    def test_clone_document_copies_elements_gradients_and_groups(self):
        reset_documents()
        scene = get_document_operations()
        doc = scene.create_document(width=800, height=600, name="source", background="#101820")
        doc.gradients["sky"] = {"type": "linear", "stops": [{"offset": 0, "color": "#000000"}]}
        scene.create_element(
            outline=[(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)],
            element_id="panel",
            document_id=doc.id,
            style=Style(fill="#336699"),
            layer="buildings",
            metadata={"kind": "facade"},
        )
        structure = DocumentStructureService(scene)
        structure.group_elements("facades", ["panel"], document_id=doc.id)

        clone = scene.clone_document(doc.id, name="copy")

        assert clone.id != doc.id
        assert clone.name == "copy"
        assert clone.width == 800
        assert scene.get_element("panel", clone.id).style.fill == "#336699"
        assert scene.get_element("panel", clone.id) is not scene.get_element("panel", doc.id)
        assert scene.get_document(clone.id).gradients == scene.get_document(doc.id).gradients
        assert scene.get_document(clone.id).gradients is not scene.get_document(doc.id).gradients
        assert [r["id"] for r in structure.get_group("facades", clone.id)] == ["panel"]

    def test_create_element(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        element = scene.create_element(
            outline=[(0.1, 0.1), (0.5, 0.8), (0.9, 0.1)],
            element_id="tri",
        )
        assert element.id == "tri"
        assert len(element.outline) == 3
        assert isinstance(element, ElementNode)

    def test_element_aliases_wrap_element_store(self):
        reset_documents()
        scene = get_document_operations()
        doc = scene.create_document()
        element = scene.create_element(
            outline=[(0.1, 0.1), (0.5, 0.8), (0.9, 0.1)],
            element_id="tri",
            document_id=doc.id,
        )

        assert element.id == "tri"
        assert scene.get_element("tri", doc.id) is scene.get_element("tri", doc.id)
        assert scene.has_element("tri", doc.id) is True
        assert scene.element_count(doc.id) == scene.element_count(doc.id) == 1
        assert scene.get_all_elements(doc.id) == scene.get_all_elements(doc.id)
        assert scene.delete_elements(doc.id, ["tri"]) == ["tri"]
        assert scene.has_element("tri", doc.id) is False

    def test_create_element_no_document(self):
        reset_documents()
        scene = get_document_operations()
        with pytest.raises(RuntimeError):
            scene.create_element(outline=[(0, 0), (1, 1)])

    def test_create_element_duplicate_id(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)], element_id="r1")
        with pytest.raises(ValueError):
            scene.create_element(outline=[(0, 0), (1, 0), (1, 1)], element_id="r1")

    def test_get_element(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        r = scene.create_element(outline=[(0, 0), (1, 0), (1, 1)], element_id="r1")
        assert scene.get_element("r1").id == "r1"

    def test_get_element_not_found(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        with pytest.raises(ValueError):
            scene.get_element("nonexistent")

    def test_element_count(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        assert scene.element_count() == 0
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)])
        assert scene.element_count() == 1
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)])
        assert scene.element_count() == 2

    def test_style_objects(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)], element_id="r1")
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)], element_id="r2")

        affected = StyleService(scene).style_objects(["r1", "r2"], fill="#00FF00")
        assert len(affected) == 2
        assert scene.get_element("r1").style.fill == "#00FF00"
        assert scene.get_element("r2").style.fill == "#00FF00"

    def test_style_objects_partial_update(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)], element_id="r1")

        StyleService(scene).style_objects(["r1"], stroke_width=0.02, opacity=0.5)
        r = scene.get_element("r1")
        assert r.style.stroke_width == 0.02
        assert r.style.opacity == 0.5
        assert r.style.fill == "#CCCCCC"  # unchanged
        assert r.style.stroke == "#333333"  # unchanged

    def test_describe_scene_structure(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)], element_id="r1")

        desc = scene.describe_scene()
        assert desc["element_count"] == 1
        assert len(desc["elements"]) == 1
        assert desc["elements"][0]["id"] == "r1"
        assert "document" in desc
        assert "warnings" in desc

    def test_describe_scene_empty(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        desc = scene.describe_scene()
        assert desc["element_count"] == 0

    def test_reset(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document()
        scene.create_element(outline=[(0, 0), (1, 0), (1, 1)])
        scene.reset()
        assert scene.has_document() is False
        # element_count raises RuntimeError after reset (no doc)
        import pytest
        with pytest.raises(RuntimeError):
            scene.element_count()


class TestCurveEngine:
    def test_closed_curve(self):
        segments = fit_curves([(0, 0), (0.5, 1), (1, 0)], closed=True, smoothness=0.5)
        assert len(segments) == 3  # 3 points → 3 segments
        for seg in segments:
            assert len(seg) == 4  # each has 4 control points

    def test_open_curve(self):
        segments = fit_curves([(0, 0), (0.5, 0.5), (1, 0)], closed=False, smoothness=0.5)
        assert len(segments) == 2  # 3 points → 2 segments

    def test_two_points(self):
        segments = fit_curves([(0, 0), (1, 1)], closed=False)
        assert len(segments) == 1
        # Should be a straight line
        assert segments[0][0] == (0, 0)
        assert segments[0][3] == (1, 1)

    def test_single_point(self):
        segments = fit_curves([(0.5, 0.5)], closed=False)
        assert segments == []

    def test_empty_outline(self):
        segments = fit_curves([], closed=False)
        assert segments == []

    def test_smoothness_zero_polygonal(self):
        """smoothness=0 should keep tangent vectors at zero → polygonal."""
        outline = [(0, 0), (0.5, 1), (1, 0)]
        segments = fit_curves(outline, closed=True, smoothness=0.0)
        for seg in segments:
            # At smoothness=0, control points 1 and 2 equal the endpoints
            assert seg[0] == seg[1]
            assert seg[2] == seg[3]

    def test_smoothness_high(self):
        """smoothness=1 should pull control points further."""
        outline = [(0, 0), (0.5, 1), (1, 0)]
        seg_low = fit_curves(outline, closed=True, smoothness=0.0)
        seg_high = fit_curves(outline, closed=True, smoothness=1.0)
        # Higher smoothness should move control points further from endpoints
        for i in range(len(seg_low)):
            d_low = abs(seg_low[i][1][0] - seg_low[i][0][0])
            d_high = abs(seg_high[i][1][0] - seg_high[i][0][0])
            assert d_high >= d_low

    def test_star_geometric(self):
        """Star at smoothness=0 should have control points at vertices."""
        pts = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            r = 0.4 if i % 2 == 0 else 0.17
            pts.append((0.5 + r * math.cos(angle), 0.5 + r * math.sin(angle)))
        segments = fit_curves(pts, closed=True, smoothness=0.0)
        for seg in segments:
            assert seg[0] == seg[1]  # sharp corners


class TestGeometry:
    def test_compute_bounds(self):
        bounds = compute_bounds([(0.1, 0.2), (0.5, 0.8), (0.9, 0.1)])
        assert bounds["x"] == 0.1
        assert bounds["y"] == 0.1
        assert bounds["w"] == 0.8
        assert bounds["h"] == 0.7

    def test_compute_bounds_empty(self):
        assert compute_bounds([]) is None

    def test_normalize_outline(self):
        outline = normalize_outline([(0.5, 0.5), (1.5, -0.5)])
        assert outline[0] == (0.5, 0.5)
        assert outline[1] == (1.0, 0.0)  # clamped

    def test_normalize_outline_too_few(self):
        with pytest.raises(ValueError):
            normalize_outline([(0.5, 0.5)])

    def test_normalize_outline_too_many(self):
        pts = [(i / 3000, i / 3000) for i in range(3000)]
        with pytest.raises(ValueError):
            normalize_outline(pts, max_points=2000)


class TestDeterminism:
    def _make_scene(self):
        reset_documents()
        scene = get_document_operations()
        scene.create_document(1000, 1000)
        scene.create_element(
            element_id="r1",
            outline=[(0.1, 0.2), (0.5, 0.8), (0.9, 0.3)],
            constraints=CurveConstraints(smoothness=0.3, closed=True),
            style=Style(fill="#FF0000", stroke="#000000"),
        )
        scene.create_element(
            element_id="r2",
            outline=[(0.2, 0.1), (0.4, 0.5), (0.7, 0.4)],
            constraints=CurveConstraints(smoothness=0.7, closed=False),
            style=Style(fill=None, stroke="#333333", stroke_width=0.01),
        )
        return scene

    def test_byte_identical_svg(self):
        """Same scene must produce byte-identical SVG every time."""
        scene = self._make_scene()
        svg1 = svg_serialize(scene)
        svg2 = svg_serialize(scene)
        assert svg1 == svg2

    def test_deterministic_across_multiple_renders(self):
        """Multiple renders should all be identical."""
        scene = self._make_scene()
        svgs = [svg_serialize(scene) for _ in range(5)]
        for i in range(1, 5):
            assert svgs[0] == svgs[i]

    def test_curve_fitting_deterministic(self):
        """Same input must produce identical curve segments every time."""
        outline = [(0.1, 0.2), (0.5, 0.8), (0.9, 0.3), (0.4, 0.1), (0.2, 0.6)]
        segments1 = fit_curves(outline, closed=True, smoothness=0.4)
        segments2 = fit_curves(outline, closed=True, smoothness=0.4)
        assert segments1 == segments2
        # Verify float precision
        for s1, s2 in zip(segments1, segments2):
            for p1, p2 in zip(s1, s2):
                assert p1 == p2
