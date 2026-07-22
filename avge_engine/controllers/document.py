"""Document controller — create_document, get_document, list_documents MCP tools."""
from __future__ import annotations

from typing import Any

from avge_engine.services.document_service import DocumentService
from avge_engine.services.engine import validate_input


def create_tools(mcp):
    """Register document tools on the given FastMCP instance."""

    @mcp.tool(
        name="create_document",
        description="Create a new canvas. Must be called first — call once per scene, "
        "then use create_region/restyle to edit the same document "
        "incrementally. Never rebuild from scratch.",
    )
    def create_document(
        width: int = 1000,
        height: int = 1000,
        unit: str = "px",
        background: str = "#FFFFFF",
        fill_gradient: Any | None = None,
        name: str = "",
    ) -> str:
        """Create a new vector document / canvas.

        Args:
            width: Canvas width in pixels (100–4000, default 1000).
            height: Canvas height in pixels (100–4000, default 1000).
            unit: Unit of measurement ("px", "in", "mm", "cm").
            background: Background hex color (default "#FFFFFF").
        """
        errs = validate_input("create_document", {
            "width": width, "height": height, "unit": unit, "background": background,
        })
        if errs:
            return f"Validation error: {'; '.join(errs)}"

        try:
            doc = DocumentService().create_document(
                width=width,
                height=height,
                unit=unit,
                background=background,
                fill_gradient=fill_gradient,
                name=name,
            )
            name_str = f" name='{doc.name}'" if doc.name else ""
            ts = f" created={doc.created_at[:19]}" if doc.created_at else ""
            return (
                f"Document created: id={doc.id}{name_str},{ts} "
                f"{doc.width}x{doc.height} {doc.unit}, "
                f"background={doc.background}\n\n"
                f"📌 Use this document_id=\"{doc.id}\" in subsequent tool calls.\n"
                f"💡 Tip: before styling, see resource avge://skill/design-guidelines "
                f"— flat single-tone fills on every region is a common miss. "
                f"For streets, interiors, and architecture, see "
                f"avge://skill/environment-guidelines."
            )
        except RuntimeError as e:
            return f"Error: {e}"
        except ValueError:
            return f"Error: invalid fill_gradient JSON"

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
        try:
            summary = DocumentService().get_document_summary(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."
        except ValueError as e:
            return f"Error: {e}"

        doc_info = summary.document
        lines = [
            f"Document: {doc_info['id']}",
            f"Name: {doc_info.get('name', '') or '(unnamed)'}",
            f"Canvas: {doc_info['width']}x{doc_info['height']}",
            f"Background: {doc_info['background']}",
            f"Regions: {summary.region_count}",
            f"Version: {doc_info['version']}",
            f"Preview: http://localhost:8000/preview/{doc_info['id']}.png",
        ]
        return "\n".join(lines)

    @mcp.tool(
        name="list_documents",
        description="List all saved documents on disk. Returns ID, name, version, "
        "and region count for each. Pass document_id directly to edit/view tools.",
    )
    def list_documents() -> str:
        """List all persisted documents."""
        stored = DocumentService().list_documents()
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
        name="clone_document",
        description="Clone an existing document into a new document ID, including canvas metadata, "
        "named gradients, regions, styles, layers, groups, and editable geometry. "
        "Omit source_document_id to clone the active document.",
    )
    def clone_document(
        source_document_id: str | None = None,
        name: str | None = None,
        set_active: bool = True,
    ) -> str:
        """Clone a document and optionally make the clone active.

        Args:
            source_document_id: Source document UUID. Omit to clone active document.
            name: Optional name for the cloned document.
            set_active: If True, make the clone the active document.
        """
        try:
            clone, source_id, region_count = DocumentService().clone_document(
                source_document_id=source_document_id,
                name=name,
                set_active=set_active,
            )
            return (
                f"Document cloned: source={source_id} clone={clone.id} "
                f"name='{clone.name}' {clone.width}x{clone.height} "
                f"regions={region_count}"
            )
        except RuntimeError:
            return "Error: No active document. Call create_document first."
        except ValueError as e:
            return f"Error: {e}"

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
        service = DocumentService()
        try:
            result = service.delete_documents(ids, confirm=confirm)
        except RuntimeError as e:
            return f"Error: {e}"
        if not result.found and not result.missing:
            return "No documents found or provided."

        if not confirm:
            lines = ["⚠️ **Preview — no documents deleted yet.**"]
            lines.append(f"  Call with confirm=True to delete {len(result.found)} document(s):")
            for d in result.found:
                doc_id = d["id"]
                name = d.get("name", "") or "(unnamed)"
                lines.append(f"    [{doc_id}] {name} | v{d['version']} | {d['region_count']} regions")
            if result.missing:
                lines.append(f"  Not found (skipped): {', '.join(result.missing)}")
            return "\n".join(lines)

        parts = [f"Deleted {len(result.deleted)} document(s): {', '.join(result.deleted)}"]
        if result.errors:
            parts.append(f"Errors: {'; '.join(result.errors)}")
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
        try:
            DocumentService().set_background(
                document_id=document_id,
                background=background,
                fill_gradient=fill_gradient,
            )
        except RuntimeError:
            return "Error: No active document"
        except ValueError as e:
            return f"Error: {e}"
        return f"Background updated"
