"""
Entry points for AVGE Engine M0b.

Usage:
    python -m avge_engine mcp          # MCP server (stdio)
    python -m avge_engine mcp-sse      # MCP server (SSE on :8001)
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

    elif mode == "api":
        import uvicorn
        uvicorn.run("avge_engine.api:app", host="0.0.0.0", port=8000, reload=False)

    elif mode == "dev":
        import uvicorn
        uvicorn.run("avge_engine.api:app", host="0.0.0.0", port=8000, reload=True)

    else:
        print(f"Unknown mode: {mode}")
        print(__doc__)


if __name__ == "__main__":
    main()
