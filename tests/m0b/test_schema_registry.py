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

    def test_defs_schema_is_not_public_tool(self):
        names = list_tool_names()
        assert "_defs" not in names

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

    def test_clone_document_valid(self):
        errs = validate_input("clone_document", {
            "source_document_id": "doc_source",
            "name": "copy",
            "set_active": True,
        })
        assert errs == []

    def test_clone_document_rejects_unknown_param(self):
        errs = validate_input("clone_document", {"document_id": "doc_source"})
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
            "stroke_width": 2,
            "opacity": 0.8,
        })
        assert errs == []

    def test_create_region_primitive_pattern_options_valid(self):
        errs = validate_input("create_region", {
            "shape": {"type": "rect", "x": 0.2, "y": 0.2, "width": 0.3, "height": 0.2},
            "outline_pattern": "wavy",
            "fill_pattern": "hatch",
            "pattern_density": 8,
            "pattern_amplitude": 0.015,
            "pattern_stroke_width": 2,
        })
        assert errs == []

    def test_create_region_stroke_width_valid(self):
        errs = validate_input("create_region", {
            "outline": [[0.1, 0.1], [0.9, 0.9]],
            "stroke_width": 2,
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

    def test_edit_region_point_nudge_valid(self):
        errs = validate_input("edit_region", {
            "region_id": "shape",
            "point_index": 0,
            "point_dx": 0.02,
            "point_dy": -0.01,
        })
        assert errs == []

    def test_edit_region_rejects_transform_params(self):
        errs = validate_input("edit_region", {
            "region_id": "shape",
            "dx": 0.1,
        })
        assert len(errs) > 0

    def test_edit_regions_style_update_valid(self):
        errs = validate_input("edit_regions", {
            "updates": [
                {"id": "shape", "fill": "#FF0000", "z_index": 5},
                {"id": "line", "point_index": 1, "point_dx": 0.02},
            ],
        })
        assert errs == []

    def test_edit_regions_rejects_transform_params(self):
        errs = validate_input("edit_regions", {
            "updates": [{"id": "shape", "rotate": 15}],
        })
        assert len(errs) > 0

    def test_create_ellipse_band_valid(self):
        errs = validate_input("create_ellipse_band", {
            "cx": 0.5,
            "cy": 0.42,
            "rx": 0.36,
            "ry": 0.12,
            "thickness": 0.035,
            "start_angle": 190,
            "end_angle": 350,
            "perspective": 0.25,
        })
        assert errs == []

    def test_create_ellipse_band_pattern_options_valid(self):
        errs = validate_input("create_ellipse_band", {
            "cx": 0.5,
            "cy": 0.42,
            "rx": 0.36,
            "outline_pattern": "dotted",
            "fill_pattern": "hatch",
            "pattern_density": 8,
            "pattern_stroke_width": 2,
        })
        assert errs == []

    def test_create_ellipse_band_requires_center_and_radius(self):
        errs = validate_input("create_ellipse_band", {"cx": 0.5, "cy": 0.5})
        assert len(errs) > 0

    def test_create_ellipse_band_rejects_bad_perspective(self):
        errs = validate_input("create_ellipse_band", {
            "cx": 0.5,
            "cy": 0.5,
            "rx": 0.3,
            "perspective": 2.0,
        })
        assert len(errs) > 0

    def test_project_quad_valid(self):
        errs = validate_input("project_quad", {
            "target_quad": [[0.1, 0.2], [0.8, 0.12], [0.72, 0.62], [0.16, 0.72]],
            "region_id": "tile",
            "fill": "#DDEEFF",
            "columns": 2,
            "rows": 2,
            "stroke_width": 1.5,
        })
        assert errs == []

    def test_project_quad_requires_four_points(self):
        errs = validate_input("project_quad", {
            "target_quad": [[0.1, 0.2], [0.8, 0.12], [0.72, 0.62]],
        })
        assert len(errs) > 0

    def test_project_quad_rejects_out_of_range_point(self):
        errs = validate_input("project_quad", {
            "target_quad": [[0.1, 0.2], [1.8, 0.12], [0.72, 0.62], [0.16, 0.72]],
        })
        assert len(errs) > 0

    def test_generate_cloud_valid(self):
        errs = validate_input("generate_cloud", {
            "cx": 0.4,
            "cy": 0.2,
            "width": 0.3,
            "height": 0.08,
            "puff_count": 6,
            "blur": 4,
        })
        assert errs == []

    def test_create_surface_stripes_valid(self):
        errs = validate_input("create_surface_stripes", {
            "target_quad": [[0.3, 0.4], [0.7, 0.4], [0.9, 0.85], [0.1, 0.85]],
            "count": 5,
            "orientation": "u",
            "stripe_width": 0.06,
            "stroke_width": 2,
        })
        assert errs == []

    def test_create_line_pattern_valid(self):
        errs = validate_input("create_line_pattern", {
            "pattern": "wavy",
            "points": [[0.1, 0.5], [0.9, 0.5]],
            "amplitude": 0.03,
            "frequency": 4,
            "stroke_width": 3,
            "width_profile": "pressure",
        })
        assert errs == []

    def test_apply_brush_style_valid(self):
        errs = validate_input("apply_brush_style", {
            "selector": {"ids": ["line"], "bounds": {"min_y": 0.2}},
            "brush": "g_pen",
            "color": "#111111",
            "size": 4,
            "texture_strength": 0.4,
        })
        assert errs == []

    def test_apply_brush_style_line_art_presets_valid(self):
        for brush in (
            "turnip_pen",
            "technical_pen",
            "brush_pen",
            "calligraphy_pen",
            "vector_pen",
        ):
            errs = validate_input("apply_brush_style", {
                "selector": {"ids": ["line"]},
                "brush": brush,
            })
            assert errs == []

    def test_apply_brush_style_generic_brush_aliases_valid(self):
        for brush in (
            "paint_brush",
            "blend_brush",
            "fabric_brush",
            "stone_brush",
            "wood_grain_brush",
            "metal_brush",
            "pattern_brush",
            "water_brush",
            "rain_brush",
            "snow_brush",
            "fire_brush",
            "smoke_brush",
            "spark_brush",
        ):
            errs = validate_input("apply_brush_style", {
                "selector": {"ids": ["line"]},
                "brush": brush,
            })
            assert errs == []

    def test_list_brush_presets_valid(self):
        errs = validate_input("list_brush_presets", {
            "group": "texture",
            "include_details": False,
        })
        assert errs == []

    def test_list_brush_presets_rejects_unknown_group(self):
        errs = validate_input("list_brush_presets", {
            "group": "characters",
        })
        assert len(errs) > 0

    def test_apply_brush_style_rejects_bad_selector_key(self):
        errs = validate_input("apply_brush_style", {
            "selector": {"unknown": "x"},
            "brush": "ink",
        })
        assert len(errs) > 0

    def test_refine_line_valid(self):
        errs = validate_input("refine_line", {
            "region_id": "line",
            "mode": "stabilize",
            "strength": 0.6,
            "simplify_tolerance": 0.01,
            "smoothness": 0.5,
        })
        assert errs == []

    def test_refine_line_rejects_bad_mode(self):
        errs = validate_input("refine_line", {
            "region_id": "line",
            "mode": "warp",
        })
        assert len(errs) > 0

    def test_set_layer_role_valid(self):
        errs = validate_input("set_layer_role", {
            "layer": "shadow",
            "role": "shadow",
            "blend_mode": "multiply",
        })
        assert errs == []

    def test_apply_texture_effect_valid(self):
        errs = validate_input("apply_texture_effect", {
            "effect": "halftone",
            "selector": {"layer": "panels", "z_min": 2},
            "color": "#000000",
            "density": 12,
            "blend_mode": "multiply",
        })
        assert errs == []

    def test_apply_fx_valid(self):
        errs = validate_input("apply_fx", {
            "type": "impact_lines",
            "bounds": [0.1, 0.1, 0.8, 0.8],
            "center": [0.5, 0.45],
            "count": 32,
            "direction": 90,
            "length": 0.35,
            "size": 3,
        })
        assert errs == []

    def test_apply_fx_rejects_unknown_type(self):
        errs = validate_input("apply_fx", {
            "type": "sparkle_magic",
            "bounds": [0.1, 0.1, 0.8, 0.8],
        })
        assert len(errs) > 0

    def test_mix_region_colors_valid(self):
        errs = validate_input("mix_region_colors", {
            "source_region_id": "warm",
            "target_region_id": "cool",
            "mix_ratio": 0.35,
            "source_channel": "fill",
            "target_channel": "stroke",
            "output": "new_region",
            "new_region_id": "mixed",
        })
        assert errs == []

    def test_mix_region_colors_rejects_unknown_output(self):
        errs = validate_input("mix_region_colors", {
            "source_region_id": "warm",
            "target_region_id": "cool",
            "output": "palette",
        })
        assert len(errs) > 0

    def test_find_objects_shared_selector_valid(self):
        errs = validate_input("find_objects", {
            "selector": {
                "tags": {"kind": "building"},
                "bounds": {"min_x": 0.1, "max_y": 0.8},
                "has_stroke": True,
            }
        })
        assert errs == []

    def test_transform_objects_shared_selector_valid(self):
        errs = validate_input("transform_objects", {
            "selector": {"group_name": "building", "fill": "#CC3333"},
            "dx": 0.1,
            "dy": -0.05,
        })
        assert errs == []

    def test_warp_region_valid(self):
        errs = validate_input("warp_region", {
            "region_id": "cape",
            "mode": "handle_shift",
            "handles": [{"x": 0.5, "y": 0.5, "dx": 0.04, "dy": -0.02, "radius": 0.2}],
            "falloff": 1.5,
            "smoothness": 0.4,
        })
        assert errs == []

    def test_warp_region_rejects_bad_mode(self):
        errs = validate_input("warp_region", {
            "region_id": "cape",
            "mode": "perspective",
        })
        assert len(errs) > 0

    def test_duplicate_scatter_valid(self):
        errs = validate_input("duplicate", {
            "pattern": "scatter",
            "region_id": "leaf",
            "count": 12,
            "bounds": [0.2, 0.3, 0.4, 0.2],
            "seed": 9,
            "jitter": {"size": 0.2, "rotation": 12, "seed": 4},
        })
        assert errs == []

    def test_duplicate_rejects_unknown_pattern(self):
        errs = validate_input("duplicate", {
            "pattern": "spray",
            "region_id": "leaf",
        })
        assert len(errs) > 0

    def test_generate_background_asset_valid(self):
        errs = validate_input("generate_background_asset", {
            "mode": "facade_detail",
            "bounds": [0.1, 0.2, 0.5, 0.4],
            "count": 12,
            "detail": ["mullions", "sills", "pipes"],
            "color": "#334455",
        })
        assert errs == []

    def test_generate_background_asset_nature_mode_valid(self):
        errs = validate_input("generate_background_asset", {
            "mode": "grass_patch",
            "bounds": [0.1, 0.7, 0.6, 0.2],
            "density": 2.5,
            "seed": 5,
        })
        assert errs == []

    def test_generate_background_asset_rejects_unknown_mode(self):
        errs = validate_input("generate_background_asset", {
            "mode": "city",
            "bounds": [0.1, 0.2, 0.5, 0.4],
        })
        assert len(errs) > 0

    def test_create_comic_panel_layout_valid(self):
        errs = validate_input("create_comic_panel_layout", {
            "layout": "feature_top",
            "rows": 2,
            "columns": 3,
            "bounds": [0.05, 0.05, 0.9, 0.9],
            "reading_direction": "rtl",
            "stroke_width": 4,
        })
        assert errs == []

    def test_create_comic_panel_layout_rejects_unknown_layout(self):
        errs = validate_input("create_comic_panel_layout", {
            "layout": "diagonal",
        })
        assert len(errs) > 0

    def test_add_shading_shared_selector_valid(self):
        errs = validate_input("add_shading", {
            "selector": {"layer": "facades", "bounds": {"max_y": 0.8}},
            "mode": "gradient",
            "light_direction": 135,
            "intensity": 0.4,
        })
        assert errs == []

    def test_apply_line_hierarchy_shared_selector_valid(self):
        errs = validate_input("apply_line_hierarchy", {
            "selector": {"tags": {"kind": "building"}, "has_stroke": True},
            "outer_width": 6,
            "inner_width": 2,
            "basis": "bounding_size",
        })
        assert errs == []

    def test_create_shadow_valid(self):
        errs = validate_input("create_shadow", {
            "region_id": "chair",
            "direction": 90,
            "distance": 0.04,
            "softness": 5,
            "opacity": 0.25,
            "sy": 0.35,
        })
        assert errs == []

    def test_create_shadow_invalid_distance(self):
        errs = validate_input("create_shadow", {
            "region_id": "chair",
            "distance": 2.0,
        })
        assert len(errs) > 0

    def test_create_shadow_clipped_valid(self):
        errs = validate_input("create_shadow", {
            "region_id": "chair",
            "onto_region_id": "floor",
            "direction": 45,
            "distance": 0.05,
        })
        assert errs == []

    def test_create_shadow_receiver_is_optional(self):
        errs = validate_input("create_shadow", {
            "region_id": "chair",
        })
        assert errs == []

    def test_critique_visual_valid(self):
        errs = validate_input("critique", {
            "mode": "visual",
            "min_confidence": 0.5,
            "as_json": True,
        })
        assert errs == []

    def test_critique_invalid_confidence(self):
        errs = validate_input("critique", {
            "min_confidence": 1.5,
        })
        assert len(errs) > 0

    def test_critique_invalid_mode(self):
        errs = validate_input("critique", {
            "mode": "preview",
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

    def test_style_objects_material_valid(self):
        errs = validate_input("style_objects", {
            "ids": ["r1"],
            "material": "glass",
            "material_detail": True,
            "material_intensity": 0.8,
        })
        assert errs == []

    def test_style_objects_material_invalid(self):
        errs = validate_input("style_objects", {
            "ids": ["r1"],
            "material": "plastic",
        })
        assert len(errs) > 0

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
