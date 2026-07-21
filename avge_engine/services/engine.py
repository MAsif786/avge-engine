"""Shared engine services — graph access, doc resolution, validation, storage.

Controllers import these helpers to avoid duplicating global state management.
The storage adapter is attached at startup so every mutation auto-persists to disk.
"""
from __future__ import annotations

from pathlib import Path

from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.scene import SceneGraph
from avge_engine.schema_registry import validate_input as _validate
from avge_engine.storage import FileStorageAdapter

# ── Global scene graph (single-process, M0b) ──────────────────────
_graph: SceneGraph | None = None
_active_doc: str | None = None

# Storage directory (relative to project root)
STORAGE_DIR: str = ".avge_data"

def get_graph() -> SceneGraph:
    """Return the singleton SceneGraph instance (lazily created).

    Attaches the file-storage adapter on first creation so every
    document mutation is persisted to ``.avge_data/<doc_id>.json``.
    """
    global _graph
    if _graph is None:
        _graph = SceneGraph()
        adapter = FileStorageAdapter(directory=STORAGE_DIR)
        _graph.attach_storage(adapter)
    return _graph


def resolve_doc(document_id: str | None = None) -> str:
    """Resolve document_id from explicit value or active session.

    Raises RuntimeError if neither is available.
    """
    global _active_doc
    if document_id:
        return document_id
    if _active_doc is None:
        raise RuntimeError("No active document. Call create_document first.")
    return _active_doc


def set_active_doc(doc_id: str) -> None:
    """Set the active document ID (called by create_document)."""
    global _active_doc
    _active_doc = doc_id


def reset_graph() -> None:
    """Reset the scene graph (used by /tools/reset and between benchmarks)."""
    global _graph, _active_doc
    _graph = None
    _active_doc = None


def validate_input(tool_name: str, data: dict) -> list[str]:
    """Validate tool input against the schema registry. Returns error list (empty = valid)."""
    return _validate(tool_name, data)


# ── Storage helpers ───────────────────────────────────────────────


def list_stored_documents() -> list[dict]:
    """List all persisted documents from storage.

    Returns:
        List of summary dicts (id, name, version, region_count, updated).
        Empty list when no stored documents exist.
    """
    return get_graph().list_stored_documents()


def load_stored_document(doc_id: str) -> bool:
    """Load a persisted document into the scene graph.

    Args:
        doc_id: Document UUID to load.

    Returns:
        True if the document was loaded, False if not found.
    """
    sg = get_graph()
    if sg.load_document(doc_id):
        set_active_doc(doc_id)
        return True
    return False


def get_storage_dir() -> str:
    """Return the absolute path of the storage directory."""
    return str(Path(STORAGE_DIR).resolve())


def stroke_width_to_norm(document_id: str, stroke_width: float | None) -> float | None:
    """Convert a pixel stroke width to AVGE normalized stroke width.

    Stroke widths are stored as a fraction of the shorter canvas dimension.
    Returning ``None`` lets callers preserve omitted style values.
    """
    if stroke_width is None:
        return None
    doc = get_graph().get_document(document_id)
    shorter = max(1, min(doc.width, doc.height))
    return max(0.001, min(0.1, float(stroke_width) / shorter))


# ── Skill guideline resources ─────────────────────────────────────

DESIGN_GUIDELINES_PATH: Path | None = None  # resolved on first access
ENVIRONMENT_GUIDELINES_PATH: Path | None = None


def load_design_guidelines() -> str:
    """Load the design guidelines markdown file, or return a fallback string."""
    global DESIGN_GUIDELINES_PATH
    if DESIGN_GUIDELINES_PATH is None:
        DESIGN_GUIDELINES_PATH = (
            Path(__file__).resolve().parent.parent.parent / "docs" / "design-guidelines.md"
        )
    if DESIGN_GUIDELINES_PATH.exists():
        return DESIGN_GUIDELINES_PATH.read_text()
    return "# Design Guidelines\n\n(See design-guidelines.md — file not found on this server.)"


def load_environment_guidelines() -> str:
    """Load the environment guidelines markdown file, or return a fallback string."""
    global ENVIRONMENT_GUIDELINES_PATH
    if ENVIRONMENT_GUIDELINES_PATH is None:
        ENVIRONMENT_GUIDELINES_PATH = (
            Path(__file__).resolve().parent.parent.parent / "docs" / "environment-guidelines.md"
        )
    if ENVIRONMENT_GUIDELINES_PATH.exists():
        return ENVIRONMENT_GUIDELINES_PATH.read_text()
    return (
        "# Environment Guidelines\n\n"
        "(See docs/environment-guidelines.md — file not found on this server.)"
    )


TOOL_REFERENCE_PATH: Path | None = None


def load_tool_reference() -> str:
    """Load the tool reference markdown file (generated from MCP tool registrations)."""
    global TOOL_REFERENCE_PATH
    if TOOL_REFERENCE_PATH is None:
        TOOL_REFERENCE_PATH = (
            Path(__file__).resolve().parent.parent.parent / "docs" / "TOOL_REFERENCE.md"
        )
    if TOOL_REFERENCE_PATH.exists():
        return TOOL_REFERENCE_PATH.read_text()
    return "# Tool Reference\n\n(See docs/TOOL_REFERENCE.md — file not found on this server.)"


# ── Centralized tool map — single source of truth ────────────────

TOOL_MAP = """📋 TOOL MAP (60 tools — all available in batch):

🗂 Document:   create_document · list_documents · load_document ·
               clone_document · delete_document · set_background
✏️  Create:     create_region · create_primitive · create_curve ·
               create_ellipse_band · generate_cloud · create_text ·
               insert_image · import_svg_path
🔧 Edit:       edit_region · edit_regions · delete_region ·
               refine_line · get_region · copy_element
🔄 Transform:  transform_objects · project_quad · create_perspective_grid ·
               create_facade_grid · create_surface_stripes ·
               generate_background_asset · duplicate ·
               boolean_operation
🕶 Depth:      create_shadow · add_shading
🎨 Style:      restyle · list_brush_presets · apply_brush_style · set_layer_role ·
               apply_texture_effect · apply_depth_haze · add_bumps ·
               generate_palette · define_gradient ·
               apply_line_hierarchy · compare_style_consistency
               (restyle supports material presets: glass, brushed_metal,
               concrete, wood, tile, foliage)
👥 Groups:     edit_group · list_groups · list_layers · shift_layer_z
📚 Comic:      create_comic_panel_layout
🔷 Procedural: create_line_pattern · generate_shape (19 patterns — see tool description)
👁 View:       describe_scene · critique · render_preview ·
               render_diff · checkpoint_diff · export_svg
📜 History:    checkpoint · restore · get_history
⚡ Batch:      batch (wraps ALL tools above)

⚠️ DEPRECATED — use new names:
  style_objects     → restyle(selector={...}, mode="exact")
  group_regions     → edit_group(action="create", ...)
  ungroup_regions   → edit_group(action="delete", ...)
  duplicate_region  → duplicate(pattern="single", ...)
  duplicate_grid    → duplicate(pattern="grid", ...)
  duplicate_radial  → duplicate(pattern="radial", ...)
"""

# ── Tool descriptions with §4.5d smoothness guidance ─────────────

SMOOTHNESS_GUIDANCE = """
Smoothness guidance (per-region):
  - Geometric/polygonal (houses, stars, rectangles): smoothness=0.0–0.1
  - Mixed rigid/organic (cup body, tree trunk, saucer): smoothness=0.2–0.5
  - Organic/curved (foliage, faces, circles): smoothness=0.6–0.8
  - Smoothness=0.5 is the default — adjust per-region per the above.
"""
