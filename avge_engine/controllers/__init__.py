"""Controller registry — each module registers its tools with the MCP server.

Usage:
    from avge_engine.controllers import register_all, TOOL_DISPATCH
    register_all(mcp)
    # TOOL_DISPATCH maps tool name → callable for dynamic batch dispatch
"""
from __future__ import annotations

from typing import Any, Callable

from . import document, element, scene_view, style, history, scene_ops, query, procedural

TOOL_DISPATCH: dict[str, Callable[..., Any]] = {}
"""Global dispatch dict: tool name → callable. Populated by register_all().
Used by the batch tool to dynamically route ops to any registered tool."""


def register_all(mcp):
    """Register all tool controllers with the given FastMCP instance."""
    document.create_tools(mcp)
    element.create_tools(mcp)
    scene_view.create_tools(mcp)
    style.create_tools(mcp)
    history.create_tools(mcp)
    scene_ops.create_tools(mcp)
    query.create_tools(mcp)
    procedural.create_tools(mcp)

    # Build the dispatch dict from registered MCP tools
    for tool in mcp._tool_manager.list_tools():
        original_fn = tool.fn
        TOOL_DISPATCH[tool.name] = original_fn

        def _make_tracked(name, fn):
            def tracked(*args, **kwargs):
                # Extract document_id if present, otherwise use active doc
                from avge_engine.services.engine import resolve_doc
                from avge_engine.services.document_tool_service import DocumentToolService
                try:
                    doc_id = kwargs.get("document_id") or resolve_doc(None)
                    DocumentToolService().track_op(doc_id, name)
                except Exception:
                    pass  # tracking is best-effort
                return fn(*args, **kwargs)
            return tracked

        tool.fn = _make_tracked(tool.name, original_fn)
