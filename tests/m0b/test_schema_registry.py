"""
M0b test suite — schema registry tests.

Verifies:
  - All schema files load and are valid Draft 2020-12
  - Input validation passes for valid inputs
  - Input validation rejects invalid inputs
"""

import json
from pathlib import Path

import pytest

from avge_engine.schema_registry import (
    load_all,
    validate_input,
    list_tool_names,
    get_input_schema,
)

HERE = Path(__file__).resolve().parent.parent.parent
SCHEMAS_DIR = HERE / "schemas"


class TestSchemaRegistry:
    def setup_method(self):
        load_all()  # ensure loaded

    def test_all_schemas_load(self):
        """All schema files must be valid Draft 2020-12 JSON Schema."""
        names = list_tool_names()
        assert len(names) >= 4, f"Expected >=4 tools, got {names}"

    def test_schema_directory_has_all_files(self):
        """Every .json file in schemas/ must be loadable."""
        json_files = sorted(SCHEMAS_DIR.glob("*.json"))
        assert len(json_files) >= 4
        for f in json_files:
            content = json.loads(f.read_text())
            assert "$schema" in content
            assert content["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_create_document_valid(self):
        errs = validate_input("create_document", {
            "width": 800, "height": 600, "background": "#FFFFFF",
        })
        assert errs == []

    def test_create_document_valid_minimal(self):
        errs = validate_input("create_document", {})
        assert errs == []  # all fields have defaults

    def test_create_document_invalid_width(self):
        errs = validate_input("create_document", {"width": 5000})
        assert len(errs) > 0

    def test_create_document_invalid_bg(self):
        errs = validate_input("create_document", {"background": "white"})
        assert len(errs) > 0

    def test_create_region_valid(self):
        errs = validate_input("create_region", {
            "outline": [[0.1, 0.1], [0.5, 0.8], [0.9, 0.1]],
        })
        assert errs == []

    def test_create_region_missing_outline(self):
        errs = validate_input("create_region", {})
        assert len(errs) > 0  # outline is required

    def test_create_region_outline_too_few(self):
        errs = validate_input("create_region", {"outline": [[0.1, 0.1]]})
        assert len(errs) > 0

    def test_create_region_with_all_options(self):
        errs = validate_input("create_region", {
            "outline": [[0.1, 0.1], [0.9, 0.9]],
            "region_id": "test_1",
            "layer": "main",
            "closed": True,
            "smoothness": 0.3,
            "fill": "#FF0000",
            "stroke": "#000000",
            "stroke_width": 0.01,
            "opacity": 0.8,
        })
        assert errs == []

    def test_create_region_invalid_smoothness(self):
        errs = validate_input("create_region", {
            "outline": [[0, 0], [1, 0], [1, 1]],
            "smoothness": 5.0,
        })
        assert len(errs) > 0

    def test_create_region_invalid_coords(self):
        errs = validate_input("create_region", {
            "outline": [[-0.5, 1.5], [1, 0], [0, 1]],
        })
        assert len(errs) > 0

    def test_style_objects_valid(self):
        errs = validate_input("style_objects", {
            "ids": ["r1", "r2"],
            "fill": "#FF0000",
        })
        assert errs == []

    def test_style_objects_missing_ids(self):
        errs = validate_input("style_objects", {"fill": "#FF0000"})
        assert len(errs) > 0  # ids required

    def test_style_objects_no_style_change(self):
        errs = validate_input("style_objects", {"ids": ["r1"]})
        assert len(errs) > 0  # at least one style field required

    def test_describe_scene_valid(self):
        errs = validate_input("describe_scene", {})
        assert errs == []

    def test_describe_scene_invalid_detail(self):
        errs = validate_input("describe_scene", {"detail": "super_full"})
        assert len(errs) > 0

    def test_render_preview_valid(self):
        errs = validate_input("render_preview", {"scale": 0.5})
        assert errs == []

    def test_render_preview_invalid_format(self):
        errs = validate_input("render_preview", {"format": "jpg"})
        assert len(errs) > 0

    def test_get_input_schema_structure(self):
        schema = get_input_schema("create_region")
        assert "properties" in schema
        assert "outline" in schema["properties"]
        assert "smoothness" in schema["properties"]
        assert schema["type"] == "object"
