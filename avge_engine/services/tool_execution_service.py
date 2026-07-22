"""Shared tool dispatch service for REST and MCP batch execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from avge_engine.services.engine import get_graph, resolve_doc


@dataclass
class ToolExecutionResult:
    """Result of one tool execution."""

    status: str
    tool: str
    result: Any = None
    message: str = ""

    def as_api_dict(self) -> dict[str, Any]:
        data = {"status": self.status, "tool": self.tool}
        if self.message:
            data["message"] = self.message
        if self.result is not None:
            if hasattr(self.result, "model_dump"):
                data["data"] = self.result.model_dump()
            else:
                data["result"] = str(self.result)[:500]
        return data


class ToolExecutionService:
    """Execute registered controller tools through one dispatch path."""

    def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
        *,
        document_id: str | None = None,
    ) -> ToolExecutionResult:
        dispatch = self._tool_dispatch()
        fn = dispatch.get(tool_name)
        if fn is None:
            return ToolExecutionResult(
                status="error",
                tool=tool_name,
                message=f"Unknown tool: {tool_name}",
            )

        call_params = dict(params or {})
        doc_id = call_params.get("document_id") or document_id
        if doc_id:
            call_params["document_id"] = doc_id

        try:
            result = fn(**call_params)
            if doc_id:
                get_graph().track_op(doc_id, tool_name)
            return ToolExecutionResult(status="ok", tool=tool_name, result=result)
        except (ValueError, RuntimeError, TypeError, KeyError) as e:
            return ToolExecutionResult(status="error", tool=tool_name, message=str(e))

    def execute_batch(
        self,
        ops: list[dict[str, Any]],
        *,
        document_id: str | None = None,
    ) -> list[ToolExecutionResult]:
        doc_id = resolve_doc(document_id)
        results: list[ToolExecutionResult] = []
        for op in ops:
            params = dict(op)
            tool_name = params.pop("tool", None)
            if not tool_name:
                results.append(ToolExecutionResult(
                    status="error",
                    tool="",
                    message="Missing 'tool' key",
                ))
                continue
            results.append(self.execute_tool(tool_name, params, document_id=doc_id))
        return results

    def format_mcp_batch(self, results: list[ToolExecutionResult]) -> str:
        ok = 0
        err = 0
        lines: list[str] = []
        for i, result in enumerate(results):
            if result.status == "ok":
                ok += 1
                msg = str(result.result).split("\n")[0][:120]
                lines.append(f"  ✓ [{i}] {result.tool}: {msg}")
            else:
                err += 1
                lines.append(f"  ✗ [{i}] {result.tool or 'unknown'}: {result.message}")
        return "\n".join([f"Batch: {ok} ok, {err} errors"] + lines)

    @staticmethod
    def _tool_dispatch():
        from avge_engine.controllers import TOOL_DISPATCH

        if TOOL_DISPATCH:
            return TOOL_DISPATCH

        from mcp.server.fastmcp import FastMCP
        from avge_engine.controllers import register_all

        mcp = FastMCP("avge-engine-dispatch")
        register_all(mcp)
        return TOOL_DISPATCH
