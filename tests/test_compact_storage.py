import json

from avge_engine.storage.compact import decode_snapshot, encode_snapshot
from avge_engine.storage.file_adapter import FileStorageAdapter
from avge_engine.scene.models import RegionNode


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
        "regions": {
            "r1": {
                "id": "r1",
                "type": "region",
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
                "type": "region",
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
    assert "style" not in compact["regions"]["r1"]
    assert "style_id" in compact["regions"]["r1"]
    assert "outline" not in compact["regions"]["r1"]
    assert "outline_q" in compact["regions"]["r1"]
    assert "transform" not in compact["regions"]["r1"]
    assert compact["regions"]["r2"]["transform"] == {"translate": [0.1, 0.0]}
    assert "blend_mode" not in compact["styles"]["s0"]
    assert "stroke_linecap" not in compact["styles"]["s0"]
    assert "stroke_dasharray" not in compact["styles"]["s0"]


def test_default_style_is_omitted_entirely():
    snapshot = _snapshot()
    for region in snapshot["regions"].values():
        region["style"] = {
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
    assert "style_id" not in compact["regions"]["r1"]


def test_decode_snapshot_restores_full_region_shape():
    decoded = decode_snapshot(encode_snapshot(_snapshot()))

    region = decoded["regions"]["r1"]
    assert region["style"]["fill"] == "#112233"
    assert region["outline"] == [(0.1, 0.2), (0.3, 0.4), (0.5, 0.2)]
    assert region["constraints"]["closed"] is True
    assert region["transform"]["scale"] == [1.0, 1.0]


def test_encode_snapshot_is_idempotent_for_compact_input():
    compact = encode_snapshot(_snapshot())
    compact_again = encode_snapshot(compact)

    assert compact_again["regions"]["r1"]["outline_q"] == compact["regions"]["r1"]["outline_q"]
    assert decode_snapshot(compact_again)["regions"]["r1"]["outline"] == [
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
    assert "outline_q" in raw["regions"]["r1"]

    loaded = adapter.load("doc_test")
    assert loaded is not None
    assert "styles" not in loaded
    assert loaded["regions"]["r2"]["style"]["stroke"] == "#445566"
    assert loaded["regions"]["r2"]["transform"]["translate"] == [0.1, 0.0]


def test_region_node_caches_decoded_outline_and_dumps_quantized_shape():
    region = RegionNode(id="r1", outline=[(0.1, 0.2), (0.3, 0.4)])

    first = region.outline
    second = region.outline
    assert first is second
    assert region.bounds == {"x": 0.1, "y": 0.2, "w": 0.2, "h": 0.2}
    assert region.bounds is region.bounds
    assert region.model_dump()["outline_q"] == [10000, 20000, 30000, 40000]
    assert "outline" not in region.model_dump()

    region.outline = [(0.5, 0.6), (0.7, 0.8)]
    assert region.outline == [(0.5, 0.6), (0.7, 0.8)]
    assert region.outline_q == [50000, 60000, 70000, 80000]
    assert region.bounds == {"x": 0.5, "y": 0.6, "w": 0.2, "h": 0.2}
