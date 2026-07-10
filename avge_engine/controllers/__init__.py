"""Controller registry — each module registers its tools with the MCP server.

Usage:
    from avge_engine.controllers import register_all
    register_all(mcp)
"""
from __future__ import annotations

from . import document, region, scene_view, style, history, scene_ops, query, stats


def register_all(mcp):
    """Register all tool controllers with the given FastMCP instance."""
    document.create_tools(mcp)
    region.create_tools(mcp)
    scene_view.create_tools(mcp)
    style.create_tools(mcp)
    history.create_tools(mcp)
    scene_ops.create_tools(mcp)
    query.create_tools(mcp)
    stats.create_tools(mcp)

    # Wire up tool usage tracking for all registered tools
    from avge_engine.services.engine import track_tool_call, track_tool_error

    for tool in mcp._tool_manager.list_tools():
        original_fn = tool.fn

        def _make_tracked(name, fn):
            def tracked(*args, **kwargs):
                track_tool_call(name)
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    track_tool_error(name)
                    raise
            return tracked

        tool.fn = _make_tracked(tool.name, original_fn)
