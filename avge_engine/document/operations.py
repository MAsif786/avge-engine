"""Process-local document operations and persistence."""
from __future__ import annotations

import copy
import uuid
from typing import Any

from avge_engine.geometry import (
    CurveConstraints,
    Point2D,
    Transform,
    normalize_outline,
)
from avge_engine.effects import Style
from avge_engine.storage import StorageAdapter
from avge_engine.document.models import ElementNode, DocumentNode

from types import SimpleNamespace

_state = SimpleNamespace(docs={}, auto_enabled=True, last_doc_id=None, storage=None)


def __getattr__(name: str):
    """Expose old graph-style conveniences as lazy service delegates."""
    if name in {"create_rect", "create_ellipse", "create_line", "create_compound_path", "edit_element", "extrude_element_outline"}:
        from avge_engine.services.document_tool_service import DocumentToolService

        return getattr(DocumentToolService(), name)
    if name == "boolean_operation":
        return _boolean_operation_delegate
    if name == "project_quad":
        from avge_engine.services.scene_construction_service import SceneConstructionService

        return SceneConstructionService().project_quad
    if name == "add_depth_shadow":
        from avge_engine.services.shadow_service import ShadowService

        return ShadowService().add_depth_shadow
    if name == "describe_scene":
        return _describe_scene_delegate
    if name == "critique_composition":
        from avge_engine.services.inspection_service import InspectionService

        return InspectionService().critique_composition
    if name == "critique_preview_quality":
        from avge_engine.services.inspection_service import InspectionService

        return InspectionService().critique_preview_quality
    if name == "create_composite_element":
        from avge_engine.services.creation_service import CreationService

        return CreationService().create_composite_element
    if name == "batch":
        return _batch_delegate
    raise AttributeError(name)


def _boolean_operation_delegate(*args, **kwargs):
    from avge_engine.services.creation_service import CreationService

    return CreationService()._boolean_operation(
        operation=args[0] if args else kwargs.pop("operation"),
        element_ids=args[1] if len(args) > 1 else kwargs.pop("element_ids"),
        new_element_id=args[2] if len(args) > 2 else kwargs.pop("new_element_id", None),
        document_id=kwargs.pop("document_id", None),
        keep_originals=kwargs.pop("keep_originals", False),
        fill=kwargs.pop("fill", None),
        stroke=kwargs.pop("stroke", None),
        stroke_width=kwargs.pop("stroke_width", None),
        opacity=kwargs.pop("opacity", None),
    )


def _batch_delegate(ops: list[dict], document_id: str | None = None) -> list[dict]:
    from avge_engine.services.tool_execution_service import ToolExecutionService

    results = ToolExecutionService().execute_batch(ops, document_id=document_id)
    return [result.as_api_dict() for result in results]


def _describe_scene_delegate(document_id: str | None = None, **kwargs):
    from avge_engine.services.inspection_service import InspectionService

    return InspectionService().describe_scene(document_id=document_id, **kwargs)

def attach_storage(adapter: StorageAdapter) -> None:
    _state.storage = adapter

def _persist(doc_id: str) -> None:
    if not _state.storage:
        return
    doc = _state.docs.get(doc_id)
    if doc:
        import datetime as _dt
        doc.updated_at = _dt.datetime.now().isoformat()
    elements = doc.elements() if doc else {}
    groups_data = doc.groups() if doc else {}
    ts = __import__("datetime").datetime.now().isoformat()
    _state.storage.save(doc_id, {
        "document": doc.model_dump() if doc else {},
        "elements": {k: v.model_dump() for k, v in elements.items()},
        "metadata": {
            "updated": ts,
        },
        "groups": groups_data,
    })

def load_document(document_id: str) -> bool:
    if not _state.storage:
        return False
    data = _state.storage.load(document_id)
    if not data:
        return False
    from avge_engine.document.models import DocumentNode, ElementNode
    d = data.get("document", {})
    _state.docs[document_id] = DocumentNode(**d)
    elements = {}
    for rid, r in data.get("elements", {}).items():
        if "constraints" in r and isinstance(r["constraints"], dict):
            r["constraints"] = CurveConstraints(**r["constraints"])
        if "style" in r and isinstance(r["style"], dict):
            r["style"] = Style(**r["style"])
        if "transform" in r and isinstance(r["transform"], dict):
            r["transform"] = Transform(**r["transform"])
        elements[rid] = ElementNode(**r)
    _state.docs[document_id].set_elements(elements)
    _state.last_doc_id = document_id
    # Restore groups from storage
    groups_data = data.get("groups", {})
    if groups_data:
        _state.docs[document_id].set_groups(groups_data)
    return True

def list_stored_documents() -> list[dict]:
    """List all documents in the attached storage."""
    if not _state.storage:
        return []
    return _state.storage.list_documents()

def _resolve_doc(document_id: str | None = None) -> str:
    """Resolve document_id: use explicit value or fall back to last created."""
    if document_id:
        return document_id
    if _state.last_doc_id is None:
        raise RuntimeError("No document exists. Call create_document first.")
    return _state.last_doc_id

def active_document_id() -> str | None:
    """Return the active document ID, if any."""
    return _state.last_doc_id

def set_active_document_id(document_id: str | None) -> None:
    """Set the active document ID for no-document tool calls."""
    _state.last_doc_id = document_id

def reset() -> None:
    """Clear all process-local document state."""
    _state.docs.clear()
    _state.auto_enabled = True
    _state.last_doc_id = None
    _state.storage = None

# ── Document management ─────────────────────────────────────────

def create_document(
    width: int = 1000,
    height: int = 1000,
    unit: str = "px",
    background: str = "#FFFFFF",
    name: str = "",
) -> DocumentNode:
    """Create a new document with a unique UUID.

    Args:
        width, height, unit, background: canvas properties.
        name: Optional human-readable name for identification.

    Returns:
        DocumentNode with auto-generated id (UUID).
    """
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    import datetime as _dt
    now = _dt.datetime.now().isoformat()
    doc = DocumentNode(
        id=doc_id,
        name=name,
        width=width,
        height=height,
        unit=unit,
        background=background,
        created_at=now,
        updated_at=now,
    )
    _state.docs[doc_id] = doc
    _state.last_doc_id = doc_id
    _auto_checkpoint(doc_id, "create_document", f"{width}x{height}")
    _persist(doc_id)
    return doc

def clone_document(
    source_document_id: str | None = None,
    name: str | None = None,
    set_active: bool = True,
) -> DocumentNode:
    """Deep-copy a document and all of its elements into a new document ID."""
    source_id = _resolve_doc(source_document_id)
    if source_id not in _state.docs and _state.storage:
        load_document(source_id)
    source = get_document(source_id)
    clone_id = f"doc_{uuid.uuid4().hex[:12]}"
    import datetime as _dt
    now = _dt.datetime.now().isoformat()
    clone = source.model_copy(deep=True)
    clone.id = clone_id
    clone.name = name if name is not None else f"{source.name or 'Untitled'} copy"
    clone.version = 1
    clone.created_at = now
    clone.updated_at = now
    clone.gradients = copy.deepcopy(source.gradients)

    _state.docs[clone_id] = clone
    clone.set_elements({
        rid: element.model_copy(deep=True)
        for rid, element in source.elements().items()
    })
    clone.set_groups(source.groups())

    if set_active:
        _state.last_doc_id = clone_id
    _auto_checkpoint(clone_id, "clone_document", f"from {source_id}")
    _persist(clone_id)
    return clone

def get_document(document_id: str) -> DocumentNode:
    """Get a document by ID. Raises ValueError if not found."""
    doc = _state.docs.get(document_id)
    if doc is None:
        raise ValueError(
            f"Document '{document_id}' not found. "
            f"(In-memory — server restarts clear all documents) "
            f"Active: {list(_state.docs.keys())}"
        )
    return doc

def delete_document(document_id: str) -> bool:
    """Delete a document from memory and attached storage."""
    existed = document_id in _state.docs
    _state.docs.pop(document_id, None)

    deleted = _state.storage.delete(document_id) if _state.storage else False
    if _state.last_doc_id == document_id:
        _state.last_doc_id = next(iter(_state.docs), None)
    return existed or deleted

def has_document(document_id: str | None = None) -> bool:
    doc_id = document_id or _state.last_doc_id
    return doc_id in _state.docs if doc_id else False

def list_documents() -> list[dict[str, Any]]:
    """Return summary of all documents."""
    return [
        {
            "id": d.id,
            "name": d.name,
            "width": d.width,
            "height": d.height,
            "version": d.version,
            "element_count": d.element_count(),
            "created_at": d.created_at,
            "updated_at": d.updated_at,
        }
        for d in _state.docs.values()
    ]

# ── Element operations ───────────────────────────────────────────

def _elements_for(document_id: str) -> dict[str, ElementNode]:
    """Get the elements dict for a document."""
    return get_document(document_id).elements()

def create_element(
    outline: list[Point2D],
    document_id: str | None = None,
    element_id: str | None = None,
    layer: str = "default",
    z_index: int = 0,
    clip_to: str | None = None,
    constraints: CurveConstraints | None = None,
    style: Style | None = None,
    transform: Transform | None = None,
    metadata: dict[str, Any] | None = None,
) -> ElementNode:
    doc_id = _resolve_doc(document_id)
    doc = get_document(doc_id)
    rid = element_id or f"r_{uuid.uuid4().hex[:8]}"

    norm_outline = normalize_outline(outline)

    element = ElementNode(
        id=rid,
        layer=layer,
        z_index=z_index,
        clip_to=clip_to,
        outline=norm_outline,
        constraints=constraints or CurveConstraints(),
        style=style or Style(),
        transform=transform or Transform(),
        metadata=metadata or {},
    )
    doc.add_element(element)
    _auto_checkpoint(doc_id, "create_element", rid)
    _persist(doc_id)
    doc.version += 1
    return element

def get_element(element_id: str, document_id: str | None = None) -> ElementNode:
    return get_document(_resolve_doc(document_id)).get_element(element_id)

def has_element(element_id: str, document_id: str | None = None) -> bool:
    return get_document(_resolve_doc(document_id)).has_element(element_id)

def get_all_elements(document_id: str) -> list[ElementNode]:
    """Return elements in insertion order."""
    return get_document(document_id).list_elements()

def element_count(document_id: str | None = None) -> int:
    return get_document(_resolve_doc(document_id)).element_count()

# ── Element deletion ────────────────────────────────────────────────

def delete_element(document_id: str, element_id: str) -> bool:
    """Delete a element by ID. Returns True if deleted, False if not found."""
    if not get_document(document_id).delete_element(element_id):
        return False
    get_document(document_id).version += 1
    _auto_checkpoint(document_id, "delete_element", element_id)
    _persist(document_id)
    return True

def delete_elements(document_id: str, ids: list[str]) -> list[str]:
    """Delete multiple elements. Returns list of actually deleted IDs."""
    deleted: list[str] = []
    for element_id in ids:
        if delete_element(document_id, element_id):
            deleted.append(element_id)
    return deleted

# ── Tool usage tracking ────────────────────────────────────

def track_op(document_id: str | None, tool: str) -> None:
    """Record a tool call for the given document."""
    doc_id = _resolve_doc(document_id) if document_id else _state.last_doc_id
    if doc_id:
        get_document(doc_id).track_op(tool)

def get_doc_stats(document_id: str | None = None) -> dict:
    """Return tool call counts for a document."""
    doc_id = _resolve_doc(document_id)
    return get_document(doc_id).tool_stats_summary()

# ── Checkpoint / Restore ────────────────────────────────────────

def _auto_checkpoint(doc_id: str, action: str, detail: str = ""):
    """Auto-save checkpoint with metadata after every mutation."""
    if not _state.auto_enabled:
        return
    doc = _state.docs.get(doc_id)
    if doc is not None:
        doc.auto_checkpoint(action=action, detail=detail)

def checkpoint(document_id: str, name: str = "default") -> str:
    """Save a snapshot of document state."""
    doc_id = _resolve_doc(document_id)
    doc = get_document(doc_id)
    return doc.checkpoint(name)

def restore(document_id: str, name: str = "default") -> bool:
    """Restore document state from a named checkpoint."""
    doc = get_document(document_id)
    if not doc.restore_checkpoint(name):
        return False
    _persist(document_id)
    return True

def list_checkpoints(document_id: str | None = None) -> list[str]:
    """Return available checkpoint names for a document."""
    doc_id = _resolve_doc(document_id)
    return get_document(doc_id).list_checkpoints()

def checkpoint_entries(document_id: str, limit: int | None = None) -> list[dict[str, str]]:
    """Return checkpoint metadata entries for a document."""
    return get_document(document_id).checkpoint_entries(limit=limit)

def checkpoint_snapshot(document_id: str, name: str) -> tuple[DocumentNode | None, dict[str, ElementNode]]:
    """Return a deep-copied checkpoint snapshot."""
    return get_document(document_id).checkpoint_snapshot(name)
