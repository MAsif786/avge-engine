"""Document controller — create_document, get_document, list_documents, load_document MCP tools."""
from __future__ import annotations

from typing import Any

from avge_engine.services.engine import (
    get_graph, resolve_doc, set_active_doc, validate_input,
    list_stored_documents, load_stored_document, get_storage_dir,
)


def create_tools(mcp):
    """Register document tools on the given FastMCP instance."""

    @mcp.tool(
        name="create_document",
        description="Create a new canvas. Must be called first — call once per scene, "
        "then use create_region/style_objects to edit the same document "
        "incrementally. Never rebuild from scratch.",
    )
    def create_document(
        width: int = 1000,
        height: int = 1000,
        unit: str = "px",
        background: str = "#FFFFFF",
        name: str = "",
    ) -> str:
        """Create a new vector document / canvas.

        Args:
            width: Canvas width in pixels (100–4000, default 1000).
            height: Canvas height in pixels (100–4000, default 1000).
            unit: Unit of measurement ("px", "in", "mm", "cm").
            background: Background hex color (default "#FFFFFF").
            name: Optional human-readable name for identification.
        """
        errs = validate_input("create_document", {
            "width": width, "height": height, "unit": unit, "background": background,
        })
        if errs:
            return f"Validation error: {'; '.join(errs)}"

        scene = get_graph()
        try:
            doc = scene.create_document(
                width=max(100, min(width, 4000)),
                height=max(100, min(height, 4000)),
                unit=unit,
                background=background,
                name=name,
            )
            set_active_doc(doc.id)
            name_str = f" name='{doc.name}'" if doc.name else ""
            ts = f" created={doc.created_at[:19]}" if doc.created_at else ""
            return (
                f"Document created: id={doc.id}{name_str},{ts} "
                f"{doc.width}x{doc.height} {doc.unit}, "
                f"background={doc.background}\n\n"
                f"📌 Use this document_id=\"{doc.id}\" in subsequent tool calls.\n"
                f"💡 Tip: before styling, see resource avge://skill/design-guidelines "
                f"— flat single-tone fills on every region is a common miss."
            )
        except RuntimeError as e:
            return f"Error: {e}"

    @mcp.tool(
        name="get_document",
        description="Get metadata for a document. "
        "Returns document ID, name, canvas size, region count, version, "
        "and a preview URL (open in browser to view). "
        "Omit document_id to use the active document.",
    )
    def get_document(document_id: str | None = None) -> str:
        """Get document metadata and preview URL.

        Args:
            document_id: Document UUID (omit to use the active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        try:
            desc = scene.describe_scene(doc_id)
        except ValueError as e:
            return f"Error: {e}"

        doc_info = desc["document"]
        lines = [
            f"Document: {doc_info['id']}",
            f"Name: {doc_info.get('name', '') or '(unnamed)'}",
            f"Canvas: {doc_info['width']}x{doc_info['height']}",
            f"Background: {doc_info['background']}",
            f"Regions: {desc['region_count']}",
            f"Version: {doc_info['version']}",
            f"Preview: http://localhost:8000/preview/{doc_id}.png",
        ]
        return "\n".join(lines)

    @mcp.tool(
        name="list_documents",
        description="List all saved documents on disk. Returns ID, name, version, "
        "and region count for each. Use load_document to restore one.",
    )
    def list_documents() -> str:
        """List all persisted documents."""
        stored = list_stored_documents()
        if not stored:
            return "No saved documents found."

        lines = [f"Saved documents ({len(stored)}):"]
        for d in stored:
            name = d.get("name", "") or "(unnamed)"
            created = d.get("created_at", "")[:16] if d.get("created_at") else "?"
            updated = d.get("updated_at", "")[:16] if d.get("updated_at") else "?"
            lines.append(
                f"  [{d['id']}] {name} | v{d['version']} | "
                f"{d['region_count']} regions | created {created} | updated {updated}"
            )
        return "\n".join(lines)

    @mcp.tool(
        name="load_document",
        description="Load a previously saved document from disk into the editor. "
        "Use list_documents to see available documents.",
    )
    def load_document(document_id: str) -> str:
        """Load a stored document back into the scene graph.

        Args:
            document_id: Document UUID to load.
        """
        if load_stored_document(document_id):
            scene = get_graph()
            desc = scene.describe_scene(document_id)
            return (
                f"Document '{document_id}' loaded "
                f"({desc['region_count']} regions, version {desc['document']['version']}). "
                f"Ready for editing."
            )
        return f"Error: Document '{document_id}' not found on disk."

    @mcp.tool(
        name="delete_document",
        description="Delete one or more saved documents from disk. "
        "Call with confirm=False first to preview what will be deleted, "
        "then call with confirm=True to execute. "
        "Use list_documents to see available documents. "
        "⚠️ This permanently removes the document and all its regions.",
    )
    def delete_document(
        ids: list[str],
        confirm: bool = False,
    ) -> str:
        """Delete saved documents from disk.

        Args:
            ids: List of document UUIDs to delete.
            confirm: Set to True to actually delete. False (default)
                just shows what would be deleted.
        """
        stored = {d["id"]: d for d in list_stored_documents()}
        found = []
        missing = []
        for doc_id in ids:
            if doc_id in stored:
                found.append(doc_id)
            else:
                missing.append(doc_id)

        if not found and not missing:
            return "No documents found or provided."

        if not confirm:
            lines = ["⚠️ **Preview — no documents deleted yet.**"]
            lines.append(f"  Call with confirm=True to delete {len(found)} document(s):")
            for doc_id in found:
                d = stored[doc_id]
                name = d.get("name", "") or "(unnamed)"
                lines.append(f"    [{doc_id}] {name} | v{d['version']} | {d['region_count']} regions")
            if missing:
                lines.append(f"  Not found (skipped): {', '.join(missing)}")
            return "\n".join(lines)

        scene = get_graph()
        if not scene._storage:
            return "Error: Storage not available"
        deleted = []
        errors = []
        for doc_id in found:
            try:
                if doc_id in scene._docs:
                    del scene._docs[doc_id]
                if doc_id in scene._regions_by_doc:
                    del scene._regions_by_doc[doc_id]
                scene._storage.delete(doc_id)
                deleted.append(doc_id)
            except Exception as e:
                errors.append(f"{doc_id}: {e}")

        parts = [f"Deleted {len(deleted)} document(s): {', '.join(deleted)}"]
        if errors:
            parts.append(f"Errors: {'; '.join(errors)}")
        return "\n".join(parts)

    @mcp.tool(
        name="set_background",
        description="Change the canvas background color of an existing document. "
        "💡 Use instead of recreating the document when you need a different background.",
    )
    def set_background(
        background: str | None = "#FFFFFF",
        fill_gradient: Any | None = None,
        document_id: str | None = None,
    ) -> str:
        """Change the canvas background color, image, or gradient.

        Args:
            background: Hex color (e.g. "#1A1A2E"), image URL, or "none".
                URLs starting with ``http``/``https``/``data:`` set an image.
                Default "#FFFFFF".
            fill_gradient: Gradient definition (dict or JSON string) for a
                smooth gradient background. Takes precedence over ``background``.
                Linear: {"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,
                "stops":[{"offset":0,"color":"#FFF"},{"offset":1,"color":"#000"}]}
                Radial: {"type":"radial","cx":0.5,"cy":0.5,"r":0.5,
                "stops":[{"offset":0,"color":"#FFF"},{"offset":1,"color":"#000"}]}
            document_id: Document UUID (omit for active doc).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        if not scene.has_document(doc_id):
            return f"Error: Document '{doc_id}' not found"

        import json as _json
        resolved = background
        if fill_gradient is not None:
            if isinstance(fill_gradient, str):
                try:
                    resolved = _json.loads(fill_gradient)
                except _json.JSONDecodeError:
                    return f"Error: invalid fill_gradient JSON"
            elif isinstance(fill_gradient, dict):
                resolved = fill_gradient
        elif background is not None:
            is_url = background.startswith(("http://", "https://", "data:"))
            if not is_url and background != "none" and not (background.startswith("#") and len(background) in (4, 7, 9)):
                return f"Error: Invalid background '{background}'"

        doc = scene.get_document(doc_id)
        old_bg = str(doc.background)[:60]
        from avge_engine.scene import DocumentNode
        object.__setattr__(doc, "background", resolved)
        doc.version += 1
        scene._persist(doc_id)
        return f"Background updated"
