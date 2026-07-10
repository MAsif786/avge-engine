"""Shared engine services — graph access, doc resolution, validation, storage.

Controllers import these helpers to avoid duplicating global state management.
The storage adapter is attached at startup so every mutation auto-persists to disk.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from avge_engine.scene import SceneGraph
from avge_engine.schema_registry import validate_input as _validate
from avge_engine.storage import FileStorageAdapter

# ── Global scene graph (single-process, M0b) ──────────────────────
_graph: SceneGraph | None = None
_active_doc: str | None = None

# Storage directory (relative to project root)
STORAGE_DIR: str = ".avge_data"

# ── Tool usage stats ────────────────────────────────────────────
_tool_stats: dict[str, Counter] = {}
"""Per-tool call/error counts."""


def track_tool_call(tool_name: str) -> None:
    if tool_name not in _tool_stats:
        _tool_stats[tool_name] = Counter()
    _tool_stats[tool_name]["calls"] += 1


def track_tool_error(tool_name: str) -> None:
    if tool_name not in _tool_stats:
        _tool_stats[tool_name] = Counter()
    _tool_stats[tool_name]["errors"] += 1


def get_tool_stats() -> dict[str, dict[str, int]]:
    return {name: dict(c) for name, c in _tool_stats.items()}


def reset_tool_stats() -> None:
    _tool_stats.clear()


def with_stats(tool_name: str):
    """Decorator that wraps a tool function with call/error tracking."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            track_tool_call(tool_name)
            try:
                return fn(*args, **kwargs)
            except Exception:
                track_tool_error(tool_name)
                raise
        wrapper.__name__ = fn.__name__
        wrapper.__qualname__ = fn.__qualname__
        return wrapper
    return decorator


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


# ── Design guidelines resource ────────────────────────────────────

DESIGN_GUIDELINES_PATH: Path | None = None  # resolved on first access


def load_design_guidelines() -> str:
    """Load the design guidelines markdown file, or return a fallback string."""
    global DESIGN_GUIDELINES_PATH
    if DESIGN_GUIDELINES_PATH is None:
        DESIGN_GUIDELINES_PATH = (
            Path(__file__).resolve().parent.parent.parent / "design-guidelines.md"
        )
    if DESIGN_GUIDELINES_PATH.exists():
        return DESIGN_GUIDELINES_PATH.read_text()
    return "# Design Guidelines\n\n(See design-guidelines.md — file not found on this server.)"


# ── Tool descriptions with §4.5d smoothness guidance ─────────────

SMOOTHNESS_GUIDANCE = """
Smoothness guidance (per-region):
  - Geometric/polygonal (houses, stars, rectangles): smoothness=0.0–0.1
  - Mixed rigid/organic (cup body, tree trunk, saucer): smoothness=0.2–0.5
  - Organic/curved (foliage, faces, circles): smoothness=0.6–0.8
  - Smoothness=0.5 is the default — adjust per-region per the above.
"""
