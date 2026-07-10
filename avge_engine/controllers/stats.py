"""Stats controller — get_tool_stats, reset_tool_stats MCP tools."""
from avge_engine.services.engine import get_tool_stats, reset_tool_stats


def create_tools(mcp):
    """Register stats tools on the given FastMCP instance."""

    @mcp.tool(
        name="get_tool_stats",
        description="Show tool usage stats — call counts and error counts "
        "per tool since the server started. Useful for debugging "
        "and understanding which tools the agent relies on most.",
    )
    def get_tool_stats_mcp() -> str:
        """Return tool usage statistics."""
        stats = get_tool_stats()
        if not stats:
            return "(no tool calls recorded yet)"

        lines = ["Tool usage stats:"]
        total_calls = 0
        total_errors = 0
        for name in sorted(stats.keys()):
            c = stats[name]
            calls = c.get("calls", 0)
            errors = c.get("errors", 0)
            total_calls += calls
            total_errors += errors
            status = "  ✓" if errors == 0 else "  ⚠"
            lines.append(f"{status} {name}: {calls} calls, {errors} errors")
        lines.append(f"  Total: {total_calls} calls, {total_errors} errors")
        return "\n".join(lines)

    @mcp.tool(
        name="reset_tool_stats",
        description="Reset all tool usage counters to zero. Use when starting "
        "a fresh session to get clean stats.",
    )
    def reset_tool_stats_mcp() -> str:
        """Reset tool usage statistics."""
        reset_tool_stats()
        return "Tool stats reset"
