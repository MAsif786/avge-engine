"""Scene view controller — describe_scene, render_preview, export_svg."""
from __future__ import annotations

from typing import Literal

from avge_engine.services.engine import resolve_doc
from avge_engine.services.element_service import ElementService
from avge_engine.services.history_service import HistoryService
from avge_engine.services.inspection_service import InspectionService
from avge_engine.services.rendering_service import RenderingService


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
        try:
            desc = InspectionService().describe_scene(
                detail=detail,
                filter_layer=filter_layer,
                document_id=document_id,
            )
        except RuntimeError:
            return "Error: No active document — call create_document first"

        lines: list[str] = []
        d = desc["document"]
        lines.append(f"Document: {d['id']}  |  Version: {d['version']}")
        lines.append(f"Canvas: {d['width']}x{d['height']} {d['unit']}, bg={d['background']}")
        lines.append(f"Elements: {desc['element_count']}")
        lines.append("")

        if not desc["elements"]:
            lines.append("(No elements on canvas)")
        else:
            for r in desc["elements"]:
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
        name="get_element",
        description="Get a element's full outline coordinates, style, and primitive "
        "data. Use this when you need exact point positions for editing — "
        "e.g. adding a border to an isometric box face requires knowing its "
        "actual parallelogram vertices, not just bounding boxes.",
    )
    def get_element(
        element_id: str,
        document_id: str | None = None,
        decimals: int = 4,
    ) -> str:
        """Get a element's outline coordinates and properties.

        Args:
            element_id: ID of the element to inspect.
            document_id: Document UUID (omit for active doc).
            decimals: Rounding for coordinate output (default 4).
        """
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        try:
            r = ElementService().get_element(doc_id, element_id)
        except ValueError:
            return f"Error: Element '{element_id}' not found"

        lines = [f"Element: {element_id}"]
        lines.append(f"  Layer: {r.layer}  |  Z: {r.z_index}")

        # Style
        s = r.style
        lines.append(f"  Fill: {s.fill}  |  Stroke: {s.stroke}  |  "
                      f"Stroke width: {s.stroke_width}  |  Opacity: {s.opacity}")

        # Primitive
        if r.primitive:
            lines.append(f"  Primitive: {r.primitive}")

        # Outline
        pts = r.outline
        lines.append(f"  Outline: {len(pts)} point(s)")
        for i, (px, py) in enumerate(pts):
            lines.append(f"    [{i}] ({px:.{decimals}f}, {py:.{decimals}f})")

        # Metadata
        if r.metadata:
            lines.append(f"  Metadata: {r.metadata}")

        return "\n".join(lines)

    @mcp.tool(
        name="render_preview",
        description="Get a visual PNG preview URL for the current canvas. "
        "💡 Pass element_id to render just one element for inspection.\n"
        "Also: /preview/{doc_id}.png (PNG) and /preview/{doc_id}.svg (SVG).",
    )
    def render_preview(
        scale: float = 1.0,
        document_id: str | None = None,
        element_id: str | None = None,
        bbox: dict | None = None,
    ) -> str:
        """Get a visual PNG preview URL for the current canvas.

        The preview is served by the API server on port 8000.
        Open the returned URL in a browser or fetch it.

        Args:
            scale: Render scale factor (0.25–2.0, default 1.0).
            document_id: Document UUID (omit to use active document).
            element_id: Optional — crop preview to this element's bounding box.
            bbox: Optional — explicit crop area {x, y, w, h} in normalized coords.
                💡 Combine with scale=4 for a detail zoom on a face or hand.
        """
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        if element_id or bbox:
            try:
                b64 = RenderingService().cropped_preview_base64(
                    document_id=doc_id,
                    scale=scale,
                    element_id=element_id,
                    bbox=bbox,
                )
            except ValueError as e:
                return f"Error: {e}"
            return f"data:image/png;base64,{b64[:60]}... ({len(b64)} chars)"

        return f"http://localhost:8000/preview/{doc_id}.png"

    @mcp.tool(
        name="export_svg",
        description="Export the current canvas to an SVG file on disk. "
        "Returns the file path and SVG character count.",
    )
    def export_svg(
        filepath: str = "output/scene.svg",
        document_id: str | None = None,
        exclude_layers: list[str] | None = None,
        exclude_element_ids: list[str] | None = None,
        exclude_prefixes: list[str] | None = None,
    ) -> str:
        """Export the current canvas as an SVG file on disk.

        Args:
            filepath: Path to save the SVG file (default "output/scene.svg").
                Relative paths are resolved from the project root.
            document_id: Document UUID (omit to use active document).
            exclude_layers: Optional layer names to omit from final export.
                Use ["guides"] to keep construction guides out of final art.
            exclude_element_ids: Optional exact element IDs to omit.
            exclude_prefixes: Optional ID prefixes to omit, e.g. ["guide_"].
        """
        try:
            result = RenderingService().export_svg(
                filepath=filepath,
                document_id=document_id,
                exclude_layers=exclude_layers,
                exclude_element_ids=exclude_element_ids,
                exclude_prefixes=exclude_prefixes,
            )
        except RuntimeError:
            return "Error: No document — call create_document first"

        return f"SVG saved: {result['filepath']} ({result['chars']} chars)"

    @mcp.tool(
        name="checkpoint_diff",
        description="Compare the current scene against a named checkpoint. "
        "Shows which elements were added, removed, or changed since the checkpoint. "
        "💡 Use checkpoint before a risky edit, then checkpoint_diff to review "
        "what actually changed.",
    )
    def checkpoint_diff(
        name: str = "default",
        document_id: str | None = None,
    ) -> str:
        """Compare the current scene against a named checkpoint.

        Args:
            name: Checkpoint name (default "default").
            document_id: Document UUID (omit to use active document).
        """
        try:
            return HistoryService().checkpoint_diff(name=name, document_id=document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

    @mcp.tool(
        name="render_diff",
        description="Render a visual diff PNG comparing current state against "
        "a named checkpoint. Shows added (green), removed (red), and modified "
        "(yellow) elements. 💡 Use after checkpoint/restore to verify changes "
        "visually. Returns a data URI that can be opened in a browser.",
    )
    def render_diff(
        name: str = "default",
        document_id: str | None = None,
        scale: float = 1.0,
    ) -> str:
        """Render a visual diff PNG showing changes since a checkpoint.

        Args:
            name: Checkpoint name to compare against (default "default").
            document_id: Document UUID (omit to use active document).
            scale: Render scale (0.25–2.0).
        """
        try:
            return HistoryService().render_diff(name=name, document_id=document_id, scale=scale)
        except RuntimeError:
            return "Error: No active document — call create_document first"
