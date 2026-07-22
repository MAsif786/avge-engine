"""History controller — checkpoint, restore, get_history, batch."""
from __future__ import annotations

from avge_engine.services.history_service import HistoryService
from avge_engine.services.tool_execution_service import ToolExecutionService


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
        try:
            data = HistoryService().checkpoint(name=name, document_id=document_id)
        except (RuntimeError, ValueError):
            return "Error: No document — create one first"
        return (
            f"Checkpoint '{name}' saved "
            f"({data['element_count']} elements at version {data['version']})"
        )

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
        try:
            data = HistoryService().restore(name=name, document_id=document_id)
        except RuntimeError:
            return "Error: No document"
        except LookupError:
            return f"Error: Checkpoint '{name}' not found."
        except ValueError as e:
            return f"Error: {e}"
        return (
            f"Restored from checkpoint '{name}' "
            f"({data['element_count']} elements at version {data['version']})"
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
        try:
            entries = HistoryService().entries(document_id=document_id, limit=limit)
        except RuntimeError:
            return "Error: No active document"
        except ValueError as e:
            return f"Error: {e}"

        if not entries:
            return "(no history)"

        label = document_id or "active document"
        lines = [f"History for {label} ({len(entries)} entries):"]
        for entry in entries:
            lines.append(
                f"  {entry.name} [{entry.time}] {entry.action} "
                f"{entry.detail}  ({entry.element_count} elements)"
            )
        if lines:
            lines.append(
                f'Use restore(name="{entries[0].name}") to go back.'
            )
        return "\n".join(lines)

    @mcp.tool(
        name="batch",
        description="Execute multiple operations in a single call. "
        "**ALL** registered tools work in batch — not just the ones listed.\n"
        "  create_element: outline, fill, stroke, smoothness, closed, z_index, stroke_width\n"
        "  create_ellipse_band: cx, cy, rx, ry, thickness, start_angle, end_angle, perspective\n"
        "  create_primitive: shape (rect/ellipse/line/polyline/compound_path), fill, stroke, stroke_width\n"
        "  create_curve: points, stroke, stroke_width, smoothness\n"
        "  create_text: x, y, text, fill, font_size, font_family, text_anchor\n"
        "  insert_image: x, y, width, height, href, import_mode (image/embed/svg_paths), clip_to\n"
        "  import_svg_path: path_data, fill, smoothness\n"
        "  edit_element: element_id, outline, fill, stroke, z_index, shape\n"
        "  duplicate: element_id, pattern, count, dx, dy, bounds, seed, columns, rows, spacing_falloff, scale_falloff\n"
        "  create_shadow: element_id, optional onto_element_id, direction, distance, softness, sy\n"
        "  apply_depth_haze: selector, haze_color, near_y, far_y, max_strength\n"
        "  restyle: selector, mode, fill, stroke, stroke_width, material\n"
        "  mix_element_colors: source_element_id, target_element_id, mix_ratio, output\n"
        "  apply_fx: type, bounds/selector, center, direction, count, length\n"
        "  delete_element: ids\n"
        "  transform_objects: selector, mode, dx, dy, scale, rotate, alignment\n"
        "  warp_element: element_id, mode, strength, axis, center, handles, falloff\n"
        "  project_quad: target_quad, source_element_id, fill, stroke, columns, rows\n"
        "  create_perspective_grid: vanishing_points, horizon_y, bounds\n"
        "  create_facade_grid: target_quad, rows, columns, lit_ratio\n"
        "  generate_background_asset: mode, bounds, count, density, seed\n"
        "  create_comic_panel_layout: layout, rows, columns, bounds, gutter_x/y, reading_direction\n"
        "  copy_element: element_id OR group, target_document_id, source_document_id, offset_x/y\n"
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
        try:
            results = ToolExecutionService().execute_batch(ops, document_id=document_id)
        except RuntimeError:
            return "Error: No active document"
        return ToolExecutionService().format_mcp_batch(results)
