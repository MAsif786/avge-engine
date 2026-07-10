"""History controller — checkpoint, restore, get_history, batch."""
from __future__ import annotations

from avge_engine.services.engine import get_graph, resolve_doc


def create_tools(mcp):
    """Register history tools on the given FastMCP instance."""

    @mcp.tool(
        name="checkpoint",
        description="Save a snapshot of the current document state. "
        "Use restore() to revert back to this point.",
    )
    def checkpoint(name: str = "default", document_id: str | None = None) -> str:
        """Save a checkpoint of the current document.

        Args:
            name: Checkpoint name (default "default"). Use distinct names
                for multiple snapshots.
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No document — create one first"

        scene.checkpoint(doc_id, name)
        regions = scene.region_count(doc_id)
        doc = scene.get_document(doc_id)
        return f"Checkpoint '{name}' saved ({regions} regions at version {doc.version})"

    @mcp.tool(
        name="restore",
        description="Restore document state from a named checkpoint. "
        "All changes made after the checkpoint are discarded.",
    )
    def restore(name: str = "default", document_id: str | None = None) -> str:
        """Restore document state from a checkpoint.

        Args:
            name: Checkpoint name to restore from (default "default").
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No document"

        if not scene.restore(doc_id, name):
            available = scene.list_checkpoints(doc_id)
            return (
                f"Error: Checkpoint '{name}' not found. "
                f"Available: {available}"
            )
        regions = scene.region_count(doc_id)
        doc = scene.get_document(doc_id)
        return (
            f"Restored from checkpoint '{name}' "
            f"({regions} regions at version {doc.version})"
        )

    @mcp.tool(
        name="get_history",
        description="Show mutation history for a document. Requires document_id "
        "(get from create_document or list_documents). Returns auto-saved "
        "checkpoints with timestamps and actions. Use restore() "
        "to revert to any point.",
    )
    def get_history(
        document_id: str | None = None,
        limit: int = 20,
    ) -> str:
        """Show mutation history for a document.

        Args:
            document_id: Document UUID (omit for active doc).
            limit: Max entries to show (default 20).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        history = scene.list_checkpoints(doc_id)
        if not history:
            return "(no history)"

        lines = [f"History for {doc_id} ({len(history)} entries):"]
        # list_checkpoints returns checkpoint names; _checkpoint_meta has timestamps
        meta_store = getattr(scene, "_checkpoint_meta", {})
        for name in history[:limit]:
            entry = meta_store.get(f"{doc_id}::{name}", {})
            ts = entry.get("time", "?")
            action = entry.get("action", "?")
            detail = entry.get("detail", "")
            rc = entry.get("region_count", "?")
            lines.append(
                f"  {name} [{ts}] {action} {detail}  ({rc} regions)"
            )
        if lines:
            lines.append(
                f'Use restore(name="{history[0]}") to go back.'
            )
        return "\n".join(lines)

    @mcp.tool(
        name="batch",
        description="Execute multiple operations in a single call. Each op is a dict "
        "with a 'tool' key. Supported: create_region, create_shape, "
        "edit_region, duplicate_region, delete_region, style_objects.",
    )
    def batch(ops: list[dict], document_id: str | None = None) -> str:
        """Execute multiple operations in one call.

        Args:
            ops: List of operation dicts. Each must have a "tool" key.
            document_id: Document UUID (omit for active doc).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        results = scene.batch(ops, doc_id)
        ok = sum(1 for r in results if r["status"] == "ok")
        err = sum(1 for r in results if r["status"] == "error")
        lines = [f"Batch: {ok} ok, {err} errors"]
        for i, r in enumerate(results):
            status = chr(10003) if r["status"] == "ok" else chr(10007)
            msg = r.get("message", r.get("region_id", ""))
            lines.append(f"  {status} [{i}] {msg}")
        return "\n".join(lines)
