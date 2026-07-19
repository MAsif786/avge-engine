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
        z_min: int | None = None,
        z_max: int | None = None,
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
            z_min: Minimum z_index.
            z_max: Maximum z_index.
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
            z_min=z_min, z_max=z_max,
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
            "Tip: pass the IDs to restyle(selector={'ids': ids}, fill='#NEWCOLOR') "
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
        name="critique_preview",
        description="Preview-quality visual critique. Flags likely visual issues "
        "such as too_flat, over_rounded, missing_contact_shadows, "
        "bad_perspective, and dominant_blob_shape. Returns actionable "
        "suggestions with affected region IDs.",
    )
    def critique_preview(
        document_id: str | None = None,
        min_confidence: float = 0.0,
        as_json: bool = False,
    ) -> str:
        """Critique preview-quality issues using scene geometry/style signals.

        Args:
            document_id: Document UUID (omit to use active document).
            min_confidence: Hide findings below this confidence threshold.
            as_json: Return JSON for automated consumers.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        findings = [
            f for f in scene.critique_preview_quality(document_id=doc_id)
            if f.get("confidence", 0.0) >= min_confidence
        ]

        if as_json:
            return _json.dumps({"findings": findings, "count": len(findings)}, indent=2)

        if not findings:
            return "No preview-quality issues found."

        lines = [f"Preview critique ({len(findings)} finding(s)):"]
        for i, f in enumerate(findings, 1):
            ids = f.get("region_ids") or []
            id_note = f" regions={', '.join(ids)}" if ids else ""
            lines.append(
                f"  {i}. [{f['severity']}] {f['code']} "
                f"(confidence={f['confidence']:.2f}){id_note}"
            )
            lines.append(f"     {f['message']}")
            lines.append(f"     Suggestion: {f['suggestion']}")
        return "\n".join(lines)

    @mcp.tool(
        name="list_layers",
        description="List all unique layers and their region counts. "
        "Use shift_layer_z to shift all regions in a layer up or down "
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
        name="shift_layer_z",
        description="Shift all regions in a layer by a z-offset. "
        "Positive offset moves them higher (top), negative moves lower (back). "
        "Use after list_layers to find which layer to adjust.",
    )
    def shift_layer_z(
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
