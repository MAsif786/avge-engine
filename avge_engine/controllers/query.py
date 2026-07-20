"""Query controller — find_objects, critique, list_layers, reorder_layer."""
from __future__ import annotations

import json as _json
from typing import Any, Literal

from avge_engine.services.engine import get_graph, resolve_doc
from avge_engine.services.selector_service import select_region_ids


def create_tools(mcp):
    """Register query/inspection tools on the given FastMCP instance."""

    @mcp.tool(
        name="find_objects",
        description="Query regions with the shared selector schema or legacy top-level filters. "
        "Lets you target e.g. 'all regions with fill #E8D4B0' for a "
        "palette-wide recolor without tracking every ID manually. "
        "Filters are AND-ed together; omit a filter to skip it. "
        "💡 Use tags filter to find regions by semantic label "
        "(e.g. tags={'part':'handle'} after creating with tags).",
    )
    def find_objects(
        document_id: str | None = None,
        selector: dict[str, Any] | None = None,
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
            selector: Shared selector. Keys: ids, group_name, layer, fill,
                tags, bounds, z_min, z_max, has_stroke.
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

        if selector is not None:
            target_ids = select_region_ids(scene, doc_id, selector)
            all_results = scene.find_objects(document_id=doc_id)
            target_set = set(target_ids)
            results = [r for r in all_results if r["id"] in target_set]
        else:
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
        name="critique",
        description="Run scene critique checks. mode='rules' runs mechanical design-rule checks "
        "for stroke hierarchy, palette size, depth shading, overlap, and off-canvas objects. "
        "mode='visual' runs preview-quality checks for too_flat, over_rounded, "
        "missing_contact_shadows, bad_perspective, and dominant_blob_shape. "
        "mode='both' returns both sections.",
    )
    def critique(
        document_id: str | None = None,
        mode: Literal["rules", "visual", "both"] = "both",
        min_confidence: float = 0.0,
        as_json: bool = False,
    ) -> str:
        """Critique a scene using rule-based checks, visual-quality checks, or both.

        Args:
            document_id: Document UUID (omit to use active document).
            mode: "rules", "visual", or "both".
            min_confidence: Hide visual findings below this confidence threshold.
            as_json: Return JSON for automated consumers.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        include_rules = mode in ("rules", "both")
        include_visual = mode in ("visual", "both")
        rule_findings = scene.critique_composition(document_id=doc_id) if include_rules else []
        visual_findings = [
            f for f in scene.critique_preview_quality(document_id=doc_id)
            if f.get("confidence", 0.0) >= min_confidence
        ] if include_visual else []

        if as_json:
            return _json.dumps({
                "mode": mode,
                "rules": {"findings": rule_findings, "count": len(rule_findings)},
                "visual": {"findings": visual_findings, "count": len(visual_findings)},
                "count": len(rule_findings) + len(visual_findings),
            }, indent=2)

        if not rule_findings and not visual_findings:
            return f"No {mode} critique issues found."

        lines = [f"Critique ({mode}, {len(rule_findings) + len(visual_findings)} finding(s)):"]
        if include_rules:
            lines.append(f"Rules ({len(rule_findings)} finding(s)):")
            if rule_findings:
                for i, f in enumerate(rule_findings, 1):
                    lines.append(f"  {i}. {f}")
            else:
                lines.append("  No rule-based issues found.")
        if include_visual:
            lines.append(f"Visual ({len(visual_findings)} finding(s)):")
            if visual_findings:
                for i, f in enumerate(visual_findings, 1):
                    ids = f.get("region_ids") or []
                    id_note = f" regions={', '.join(ids)}" if ids else ""
                    lines.append(
                        f"  {i}. [{f['severity']}] {f['code']} "
                        f"(confidence={f['confidence']:.2f}){id_note}"
                    )
                    lines.append(f"     {f['message']}")
                    lines.append(f"     Suggestion: {f['suggestion']}")
            else:
                lines.append("  No visual-quality issues found.")
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
