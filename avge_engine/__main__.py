"""
Entry points for AVGE Engine M0b.

Usage:
    python -m avge_engine mcp          # MCP server (stdio)
    python -m avge_engine mcp-sse      # MCP server (SSE on :8001)
    python -m avge_engine mcp-http     # MCP server (Streamable HTTP on :8002 — Antigravity-compatible)
    python -m avge_engine api           # FastAPI HTTP server (:8000)
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    mode = sys.argv[1]

    if mode == "mcp":
        from avge_engine.server import run_stdio
        run_stdio()

    elif mode == "mcp-sse":
        from avge_engine.server import run_sse
        run_sse()

    elif mode == "mcp-http":
        from avge_engine.server import run_streamable_http
        run_streamable_http()

    elif mode == "api":
        import uvicorn
        uvicorn.run("avge_engine.api:app", host="0.0.0.0", port=8000, reload=False)

    elif mode == "dev":
        import uvicorn
        uvicorn.run("avge_engine.api:app", host="0.0.0.0", port=8000, reload=True)

    elif mode == "docs":
        """Generate markdown documentation for all registered MCP tools."""
        # Create a minimal MCP server to register all tools
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("avge-engine-docs")
        from avge_engine.controllers import register_all
        register_all(mcp)

        tools = mcp._tool_manager.list_tools()
        print(f"# AVGE Engine — Tool Reference ({len(tools)} tools)\n")
        print(f"_Generated from `{__name__}` — tool set: {__import__('avge_engine').__tool_set_version__}_\n")

        for t in sorted(tools, key=lambda x: x.name):
            print(f"## `{t.name}`\n")
            print(f"{t.description}\n")
            if hasattr(t, 'parameters') and t.parameters:
                props = t.parameters.get("properties", {})
                required = t.parameters.get("required", [])
                if props:
                    print("### Parameters\n")
                    print("| Name | Type | Required | Description |")
                    print("|------|------|----------|-------------|")
                    for pname, pdef in sorted(props.items()):
                        ptype = pdef.get("type", "any")
                        is_req = "✓" if pname in required else ""
                        pdesc = pdef.get("description", "")
                        # Clean up description
                        pdesc = pdesc.replace("\n", " ").strip()
                        print(f"| `{pname}` | `{ptype}` | {is_req} | {pdesc} |")
                print()
            print("---\n")

    else:
        print(f"Unknown mode: {mode}")
        print(__doc__)


if __name__ == "__main__":
    main()
