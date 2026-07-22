import json

from avge_engine.storage.compact import decode_snapshot, encode_snapshot
from avge_engine.storage.file_adapter import FileStorageAdapter
from avge_engine.scene.models import ElementNode
from scripts.migrate_compact_storage import _normalize_element_keys


def _snapshot():
    style = {
        "fill": "#112233",
        "stroke": "#445566",
        "stroke_width": 0.002,
        "opacity": 1.0,
        "blend_mode": None,
        "stroke_linecap": None,
        "stroke_dasharray": None,
        "blur": 0.0,
    }
    return {
        "document": {
            "id": "doc_test",
            "name": "Compact Test",
            "width": 800,
            "height": 600,
            "unit": "px",
            "background": "#FFFFFF",
            "version": 3,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "gradients": {},
        },
        "elements": {
            "r1": {
                "id": "r1",
                "type": "element",
                "layer": "default",
                "z_index": 0,
                "clip_to": None,
                "outline": [(0.1, 0.2), (0.3, 0.4), (0.5, 0.2)],
                "constraints": {
                    "smoothness": 0.5,
                    "closed": True,
                    "corner_style": "round",
                    "tensions": None,
                    "handle_in": None,
                    "handle_out": None,
                },
                "style": style,
                "transform": {
                    "translate": (0.0, 0.0),
                    "rotate": 0.0,
                    "scale": (1.0, 1.0),
                },
                "metadata": {},
                "version": 1,
                "primitive": None,
            },
            "r2": {
                "id": "r2",
                "type": "element",
                "layer": "default",
                "z_index": 2,
                "clip_to": None,
                "outline": [(0.2, 0.2), (0.4, 0.4), (0.6, 0.2)],
                "constraints": {
                    "smoothness": 0.2,
                    "closed": True,
                    "corner_style": "round",
                    "tensions": None,
                    "handle_in": None,
                    "handle_out": None,
                },
                "style": style,
                "transform": {
                    "translate": (0.1, 0.0),
                    "rotate": 0.0,
                    "scale": (1.0, 1.0),
                },
                "metadata": {},
                "version": 1,
                "primitive": None,
            },
        },
        "metadata": {"updated": "2026-01-01T00:00:00"},
        "groups": {"pair": ["r1", "r2"]},
    }


def test_compact_snapshot_interns_styles_and_omits_defaults():
    compact = encode_snapshot(_snapshot())

    assert compact["metadata"]["storage_format"] == "avge.compact.v1"
    assert len(compact["styles"]) == 1
    assert "style" not in compact["elements"]["r1"]
    assert "style_id" in compact["elements"]["r1"]
    assert "outline" not in compact["elements"]["r1"]
    assert "outline_q" in compact["elements"]["r1"]
    assert "transform" not in compact["elements"]["r1"]
    assert compact["elements"]["r2"]["transform"] == {"translate": [0.1, 0.0]}
    assert "blend_mode" not in compact["styles"]["s0"]
    assert "stroke_linecap" not in compact["styles"]["s0"]
    assert "stroke_dasharray" not in compact["styles"]["s0"]


def test_default_style_is_omitted_entirely():
    snapshot = _snapshot()
    for element in snapshot["elements"].values():
        element["style"] = {
            "fill": "#CCCCCC",
            "stroke": "#333333",
            "stroke_width": 0.005,
            "opacity": 1.0,
            "blend_mode": None,
            "stroke_linecap": None,
            "stroke_dasharray": None,
            "blur": 0.0,
        }

    compact = encode_snapshot(snapshot)

    assert "styles" not in compact
    assert "style_id" not in compact["elements"]["r1"]


def test_decode_snapshot_restores_full_element_shape():
    decoded = decode_snapshot(encode_snapshot(_snapshot()))

    element = decoded["elements"]["r1"]
    assert element["style"]["fill"] == "#112233"
    assert element["outline"] == [(0.1, 0.2), (0.3, 0.4), (0.5, 0.2)]
    assert element["constraints"]["closed"] is True
    assert element["transform"]["scale"] == [1.0, 1.0]


def test_encode_snapshot_is_idempotent_for_compact_input():
    compact = encode_snapshot(_snapshot())
    compact_again = encode_snapshot(compact)

    assert compact_again["elements"]["r1"]["outline_q"] == compact["elements"]["r1"]["outline_q"]
    assert decode_snapshot(compact_again)["elements"]["r1"]["outline"] == [
        (0.1, 0.2),
        (0.3, 0.4),
        (0.5, 0.2),
    ]


def test_file_adapter_writes_compact_and_loads_full_shape(tmp_path):
    adapter = FileStorageAdapter(str(tmp_path))
    assert adapter.save("doc_test", _snapshot())

    raw = json.loads((tmp_path / "doc_test.json").read_text())
    assert raw["metadata"]["storage_format"] == "avge.compact.v1"
    assert "styles" in raw
    assert "outline_q" in raw["elements"]["r1"]

    loaded = adapter.load("doc_test")
    assert loaded is not None
    assert "styles" not in loaded
    assert loaded["elements"]["r2"]["style"]["stroke"] == "#445566"
    assert loaded["elements"]["r2"]["transform"]["translate"] == [0.1, 0.0]


def test_migration_normalizes_legacy_persisted_keys():
    legacy = {
        "document": {"id": "doc_old", "region_count": 1},
        "regions": {"old": {"id": "old", "type": "region", "outline": [[0, 0], [1, 1]]}},
        "metadata": {"region_count": 1},
    }

    normalized = _normalize_element_keys(legacy)
    compact = encode_snapshot(decode_snapshot(normalized))

    assert "regions" not in normalized
    assert normalized["document"] == {"id": "doc_old", "element_count": 1}
    assert normalized["metadata"] == {"element_count": 1}
    assert normalized["elements"]["old"]["type"] == "element"
    assert "elements" in compact
    assert "regions" not in compact


def test_element_node_caches_decoded_outline_and_dumps_quantized_shape():
    element = ElementNode(id="r1", outline=[(0.1, 0.2), (0.3, 0.4)])

    first = element.outline
    second = element.outline
    assert first is second
    assert element.bounds == {"x": 0.1, "y": 0.2, "w": 0.2, "h": 0.2}
    assert element.bounds is element.bounds
    assert element.model_dump()["outline_q"] == [10000, 20000, 30000, 40000]
    assert "outline" not in element.model_dump()

    element.outline = [(0.5, 0.6), (0.7, 0.8)]
    assert element.outline == [(0.5, 0.6), (0.7, 0.8)]
    assert element.outline_q == [50000, 60000, 70000, 80000]
    assert element.bounds == {"x": 0.5, "y": 0.6, "w": 0.2, "h": 0.2}
