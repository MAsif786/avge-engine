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
        description="Execute multiple operations in a single call. "
        "**ALL** registered tools work in batch — not just the ones listed.\n"
        "  create_region: outline, fill, stroke, smoothness, closed, z_index, stroke_width\n"
        "  create_ellipse_band: cx, cy, rx, ry, thickness, start_angle, end_angle, perspective\n"
        "  create_primitive: shape (rect/ellipse/line/polyline/compound_path), fill, stroke, stroke_width\n"
        "  create_curve: points, stroke, stroke_width, smoothness\n"
        "  create_text: x, y, text, fill, font_size, font_family, text_anchor\n"
        "  insert_image: x, y, width, height, href\n"
        "  import_svg_path: path_data, fill, smoothness\n"
        "  edit_region: region_id, outline, fill, stroke, z_index, shape\n"
        "  duplicate: region_id, pattern, count, dx, dy, bounds, seed, columns, rows, spacing_falloff, scale_falloff\n"
        "  create_shadow: region_id, optional onto_region_id, direction, distance, softness, sy\n"
        "  apply_depth_haze: selector, haze_color, near_y, far_y, max_strength\n"
        "  restyle: selector, mode, fill, stroke, stroke_width, material\n"
        "  delete_region: ids\n"
        "  transform_objects: selector, mode, dx, dy, scale, rotate, alignment\n"
        "  project_quad: target_quad, source_region_id, fill, stroke, columns, rows\n"
        "  create_perspective_grid: vanishing_points, horizon_y, bounds\n"
        "  create_facade_grid: target_quad, rows, columns, lit_ratio\n"
        "  copy_element: region_id OR group, target_document_id, source_document_id, offset_x/y\n"
        "  create_line_pattern: pattern, points/bounds, stroke_width, width_profile, role\n"
        "  generate_shape: pattern, params\n"
        "💡 Inline shapes: create primitives directly — "
        '{"tool":"create_primitive","shape":{"type":"rect","x":0.1,"y":0.66,'
        '"width":0.09,"height":0.1},"fill":"#CCC"}\n'
        "💡 Batch text: multiple labels in one call — "
        '{"tool":"create_text","x":0.5,"y":0.5,"text":"Hello","font_size":0.06}',
    )
    def batch(ops: list[dict], document_id: str | None = None) -> str:
        """Execute multiple operations in one call.

        Uses the global TOOL_DISPATCH to dynamically route each op to the
        correct tool function — no hardcoded if/elif chain needed.
        ANY registered tool is automatically supported.

        Args:
            ops: List of operation dicts. Each must have a "tool" key.
            document_id: Document UUID (omit for active doc).
        """
        from avge_engine.controllers import TOOL_DISPATCH

        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"

        lines: list[str] = []
        ok = 0
        err = 0
        for i, op in enumerate(ops):
            tool_name = op.pop("tool", None)
            if not tool_name:
                err += 1
                lines.append(f"  ✗ [{i}] Missing 'tool' key in op")
                continue

            fn = TOOL_DISPATCH.get(tool_name)
            if fn is None:
                err += 1
                lines.append(
                    f"  ✗ [{i}] Unknown tool '{tool_name}'"
                )
                continue

            try:
                # Inject document_id so tools can find their document
                result = fn(**op, document_id=doc_id)
                # Tool functions return strings (MCP convention)
                ok += 1
                msg = str(result).split('\n')[0][:120]
                lines.append(f"  ✓ [{i}] {tool_name}: {msg}")
            except (ValueError, RuntimeError, TypeError, KeyError) as e:
                err += 1
                op_id = op.get("region_id", op.get("group_name", ""))
                ctx = f" ({op_id})" if op_id else ""
                lines.append(f"  ✗ [{i}] {tool_name}: {e}{ctx}")

        summary = f"Batch: {ok} ok, {err} errors"
        return "\n".join([summary] + lines)
