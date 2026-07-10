"""Scene view controller — describe_scene, render_preview, export_svg."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from avge_engine.services.engine import get_graph, resolve_doc
from avge_engine.renderer import svg_serialize


def create_tools(mcp):
    """Register scene view tools on the given FastMCP instance."""

    @mcp.tool(
        name="describe_scene",
        description="Get a text description of the current canvas — object list, "
        "bounds, styles, and warnings. Use this for structural feedback.",
    )
    def describe_scene(
        detail: Literal["summary", "full"] = "summary",
        filter_layer: str | None = None,
        document_id: str | None = None,
    ) -> str:
        """Get a text description of the current canvas.

        Args:
            detail: "summary" (default) or "full" (includes outline coordinates).
            filter_layer: Optional — only describe objects in this layer.
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        desc = scene.describe_scene(
            detail=detail,
            filter_layer=filter_layer,
            document_id=doc_id,
        )

        lines: list[str] = []
        d = desc["document"]
        lines.append(f"Document: {d['id']}  |  Version: {d['version']}")
        lines.append(f"Canvas: {d['width']}x{d['height']} {d['unit']}, bg={d['background']}")
        lines.append(f"Regions: {desc['region_count']}")
        lines.append("")

        if not desc["regions"]:
            lines.append("(No regions on canvas)")
        else:
            for r in desc["regions"]:
                b = r.get("bounds")
                bs = (
                    f"x={b['x']:.4f} y={b['y']:.4f} w={b['w']:.4f} h={b['h']:.4f}"
                    if b else "no bounds"
                )
                lines.append(f"  [{r['id']}] type={r['type']} layer={r['layer']}")
                lines.append(f"    Bounds: {bs}")
                lines.append(
                    f"    Points: {r['outline_point_count']} | "
                    f"{'closed' if r['closed'] else 'open'} | "
                    f"smoothness={r['smoothness']}"
                )
                lines.append(
                    f"    Style: fill={r['style']['fill']} "
                    f"stroke={r['style']['stroke']} "
                    f"width={r['style']['stroke_width']}"
                )
                if r.get("metadata"):
                    lines.append(f"    Tags: {r['metadata']}")
                lines.append("")

        if desc.get("warnings"):
            lines.append("Warnings:")
            for w in desc["warnings"]:
                lines.append(f"  ⚠ {w}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool(
        name="render_preview",
        description="Get a visual PNG preview URL for the current canvas. "
        "Returns a URL to the API's preview endpoint — open it to view "
        "the rendered image. Use this to visually inspect your work.",
    )
    def render_preview(scale: float = 1.0, document_id: str | None = None) -> str:
        """Get a visual PNG preview URL for the current canvas.

        The preview is served by the API server on port 8000.
        Open the returned URL in a browser or fetch it.

        Args:
            scale: Render scale factor (0.25–2.0, default 1.0).
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        return f"http://localhost:8000/preview/{doc_id}.png"

    @mcp.tool(
        name="export_svg",
        description="Export the current canvas to an SVG file on disk. "
        "Returns the file path and SVG character count.",
    )
    def export_svg(
        filepath: str = "output/scene.svg",
        document_id: str | None = None,
    ) -> str:
        """Export the current canvas as an SVG file on disk.

        Args:
            filepath: Path to save the SVG file (default "output/scene.svg").
                Relative paths are resolved from the project root.
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No document — call create_document first"

        svg = svg_serialize(scene, doc_id)

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg)

        return f"SVG saved: {path.resolve()} ({len(svg)} chars)"
