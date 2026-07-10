"""Query controller — find_objects, critique_composition, list_layers, reorder_layer."""
from __future__ import annotations

import json as _json
from typing import Any

from avge_engine.services.engine import get_graph, resolve_doc


def create_tools(mcp):
    """Register query/inspection tools on the given FastMCP instance."""

    @mcp.tool(
        name="find_objects",
        description="Query regions by visual properties and bounds. "
        "Lets you target e.g. 'all regions with fill #E8D4B0' for a "
        "palette-wide recolor without tracking every ID manually. "
        "Filters are AND-ed together; omit a filter to skip it. "
        "💡 Use tags filter to find regions by semantic label "
        "(e.g. tags={'part':'handle'} after creating with tags).",
    )
    def find_objects(
        document_id: str | None = None,
        fill: str | None = None,
        min_x: float | None = None,
        max_x: float | None = None,
        min_y: float | None = None,
        max_y: float | None = None,
        min_w: float | None = None,
        max_w: float | None = None,
        min_h: float | None = None,
        max_h: float | None = None,
        has_stroke: bool | None = None,
        layer: str | None = None,
        tags: dict | None = None,
    ) -> str:
        """Query regions by visual properties, bounds, and metadata tags.

        Args:
            document_id: Document UUID (omit to use active document).
            fill: Filter by fill color (exact match).
            min_x: Minimum X bound.
            max_x: Maximum X bound.
            min_y: Minimum Y bound.
            max_y: Maximum Y bound.
            min_w: Minimum width.
            max_w: Maximum width.
            min_h: Minimum height.
            max_h: Maximum height.
            has_stroke: True = must have stroke, False = must NOT have stroke.
            layer: Filter by layer name.
            tags: JSON object of key/value tags to match (all must match, e.g. {"part":"handle"}).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        parsed_tags = dict(tags) if tags else None
        results = scene.find_objects(
            document_id=doc_id,
            fill=fill,
            min_x=min_x, max_x=max_x,
            min_y=min_y, max_y=max_y,
            min_w=min_w, max_w=max_w,
            min_h=min_h, max_h=max_h,
            has_stroke=has_stroke,
            layer=layer,
            tags=parsed_tags,
        )

        if not results:
            return "No matching regions found"

        lines = [f"Found {len(results)} region(s):"]
        for r in results:
            b = r["bounds"]
            lines.append(
                f"  [{r['id']}] fill={r['fill']} stroke={r['stroke']} "
                f"layer={r['layer']} z={r['z_index']} "
                f"bounds=({b['x']:.4f},{b['y']:.4f} "
                f"{b['w']:.4f}x{b['h']:.4f})"
            )
        # Add note about how to use results
        lines.append(
            ""
            "Tip: pass the IDs to style_objects(fill='#NEWCOLOR', stroke=...) "
            "for palette-wide recolor, or transform_objects(dx=..., dy=...) "
            "to reposition."
        )
        return "\n".join(lines)

    @mcp.tool(
        name="critique_composition",
        description="Auto-check the scene against design skill rules. "
        "Returns structured findings about stroke-width uniformity, "
        "palette size, depth shading, and off-canvas objects. "
        "The mechanical version of the Design Skill checklist. "
        "💡 Call after completing each major object, not only once "
        "before finishing — catches perspective/grounding mismatches "
        "while they're still cheap to fix.",
    )
    def critique_composition(document_id: str | None = None) -> str:
        """Auto-check scene composition against design skill rules.

        Args:
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        findings = scene.critique_composition(document_id=doc_id)

        if not findings:
            return "No issues found — scene looks good."

        lines = [f"Composition critique ({len(findings)} finding(s)):"]
        for i, f in enumerate(findings, 1):
            lines.append(f"  {i}. {f}")
        return "\n".join(lines)

    @mcp.tool(
        name="list_layers",
        description="List all unique layers and their region counts. "
        "Use reorder_layer to shift all regions in a layer up or down "
        "in the z-order.",
    )
    def list_layers(document_id: str | None = None) -> str:
        """List all layers and their region counts.

        Args:
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        layers = scene.list_layers(document_id=doc_id)

        if not layers:
            return "(no layers)"

        lines = [f"Layers ({len(layers)}):"]
        for lr in layers:
            lines.append(f"  {lr['layer']}: {lr['count']} region(s)")
        return "\n".join(lines)

    @mcp.tool(
        name="reorder_layer",
        description="Shift all regions in a layer by a z-offset. "
        "Positive offset moves them higher (top), negative moves lower (back). "
        "Use after list_layers to find which layer to adjust.",
    )
    def reorder_layer(
        layer: str,
        z_offset: int,
        document_id: str | None = None,
    ) -> str:
        """Shift all regions in a layer by z_offset.

        Args:
            layer: Layer name to reorder.
            z_offset: Positive = move up (on top), negative = move back.
            document_id: Document UUID (omit to use active document).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        count = scene.reorder_layer(
            layer=layer,
            z_offset=z_offset,
            document_id=doc_id,
        )
        if count == 0:
            return f"No regions found in layer '{layer}'"
        return (
            f"Reordered {count} region(s) in layer '{layer}' "
            f"(z_offset={z_offset:+d})"
        )

    @mcp.tool(
        name="get_document_stats",
        description="View tool usage stats and errors for a document. "
        "Shows call counts per tool, total operations, and recent errors.",
    )
    def get_document_stats(document_id: str | None = None) -> str:
        """Show tool call counts and errors for a document."""
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        stats = scene.get_doc_stats(doc_id)
        lines = [
            f"Stats for {stats['document_id']}:",
            f"  Total tool calls: {stats['total_calls']}",
            f"  Errors: {stats['error_count']}",
        ]
        if stats["tool_calls"]:
            lines.append("  Calls by tool:")
            for tool, count in sorted(stats["tool_calls"].items(),
                                       key=lambda x: -x[1]):
                lines.append(f"    {tool}: {count}")
        if stats["errors"]:
            lines.append("  Recent errors:")
            for e in stats["errors"]:
                lines.append(f"    [{e['tool']}] {e['error'][:120]}")
        return "\n".join(lines)
