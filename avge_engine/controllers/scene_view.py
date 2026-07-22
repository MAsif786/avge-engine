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
        name="get_region",
        description="Get a region's full outline coordinates, style, and primitive "
        "data. Use this when you need exact point positions for editing — "
        "e.g. adding a border to an isometric box face requires knowing its "
        "actual parallelogram vertices, not just bounding boxes.",
    )
    def get_region(
        region_id: str,
        document_id: str | None = None,
        decimals: int = 4,
    ) -> str:
        """Get a region's outline coordinates and properties.

        Args:
            region_id: ID of the region to inspect.
            document_id: Document UUID (omit for active doc).
            decimals: Rounding for coordinate output (default 4).
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document"
        r = scene.get_region(region_id, doc_id)
        if r is None:
            return f"Error: Region '{region_id}' not found"

        lines = [f"Region: {region_id}"]
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
        "💡 Pass region_id to render just one region for inspection.\n"
        "Also: /preview/{doc_id}.png (PNG) and /preview/{doc_id}.svg (SVG).",
    )
    def render_preview(
        scale: float = 1.0,
        document_id: str | None = None,
        region_id: str | None = None,
        bbox: dict | None = None,
    ) -> str:
        """Get a visual PNG preview URL for the current canvas.

        The preview is served by the API server on port 8000.
        Open the returned URL in a browser or fetch it.

        Args:
            scale: Render scale factor (0.25–2.0, default 1.0).
            document_id: Document UUID (omit to use active document).
            region_id: Optional — crop preview to this region's bounding box.
            bbox: Optional — explicit crop area {x, y, w, h} in normalized coords.
                💡 Combine with scale=4 for a detail zoom on a face or hand.
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        # If cropping requested, render SVG inline with modified viewBox
        if region_id or bbox:
            from avge_engine.renderer.svg import svg_serialize
            from avge_engine.renderer.raster import render_preview_base64
            svg = svg_serialize(scene, doc_id)
            import re
            if region_id:
                r = scene.get_region(region_id, doc_id)
                if not r:
                    return f"Error: Region '{region_id}' not found"
                from avge_engine.geometry import compute_bounds
                b = compute_bounds(r.outline)
                margin = 0.05
                crop = {"x": b["x"] - margin, "y": b["y"] - margin,
                        "w": b["w"] + margin * 2, "h": b["h"] + margin * 2}
            elif bbox:
                crop = bbox

            # Modify viewBox to crop area
            doc = scene.get_document(doc_id)
            cw, ch = doc.width, doc.height
            vx = crop["x"] * cw
            vy = crop["y"] * ch
            vw = crop["w"] * cw
            vh = crop["h"] * ch
            svg = re.sub(
                r'viewBox="[^"]*"',
                f'viewBox="{vx:.0f} {vy:.0f} {vw:.0f} {vh:.0f}"',
                svg
            )
            b64 = render_preview_base64(svg, scale=scale)
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
        exclude_region_ids: list[str] | None = None,
        exclude_prefixes: list[str] | None = None,
    ) -> str:
        """Export the current canvas as an SVG file on disk.

        Args:
            filepath: Path to save the SVG file (default "output/scene.svg").
                Relative paths are resolved from the project root.
            document_id: Document UUID (omit to use active document).
            exclude_layers: Optional layer names to omit from final export.
                Use ["guides"] to keep construction guides out of final art.
            exclude_region_ids: Optional exact region IDs to omit.
            exclude_prefixes: Optional ID prefixes to omit, e.g. ["guide_"].
        """
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No document — call create_document first"

        svg = svg_serialize(
            scene,
            doc_id,
            exclude_layers=exclude_layers,
            exclude_region_ids=exclude_region_ids,
            exclude_prefixes=exclude_prefixes,
        )

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg)

        return f"SVG saved: {path.resolve()} ({len(svg)} chars)"

    @mcp.tool(
        name="checkpoint_diff",
        description="Compare the current scene against a named checkpoint. "
        "Shows which regions were added, removed, or changed since the checkpoint. "
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
        import json
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        # Get list of checkpoint names for the document
        cps = scene.list_checkpoints(doc_id)
        if not cps:
            return f"No checkpoints found for document '{doc_id}'"

        # Get current region IDs
        current_ids = set()
        current_regions = {}
        for r in scene.get_all_regions(doc_id):
            current_ids.add(r.id)
            current_regions[r.id] = {
                "fill": r.style.fill, "stroke": r.style.stroke,
                "stroke_width": r.style.stroke_width,
                "z_index": r.z_index, "layer": r.layer, "version": r.version,
                "outline_len": len(r.outline),
                "primitive_type": r.primitive.get("type") if r.primitive else None,
            }

        try:
            _doc_snap, regions_snap = scene.checkpoint_snapshot(doc_id, name)
        except KeyError:
            return f"Checkpoint '{name}' not found (available: {cps})"

        checkpoint_ids = set(regions_snap.keys())
        checkpoint_regions = {}
        for rid, r in regions_snap.items():
            checkpoint_regions[rid] = {
                "fill": r.style.fill, "stroke": r.style.stroke,
                "stroke_width": r.style.stroke_width,
                "z_index": r.z_index, "layer": r.layer, "version": r.version,
                "outline_len": len(r.outline),
                "primitive_type": r.primitive.get("type") if r.primitive else None,
            }

        # Compute diff
        added_ids = current_ids - checkpoint_ids
        removed_ids = checkpoint_ids - current_ids
        common_ids = current_ids & checkpoint_ids

        modified = []
        for rid in sorted(common_ids):
            cur = current_regions[rid]
            chk = checkpoint_regions[rid]
            changes = []
            if cur["fill"] != chk["fill"]:
                changes.append(f"fill: {chk['fill']} → {cur['fill']}")
            if cur["stroke"] != chk["stroke"]:
                changes.append(f"stroke: {chk['stroke']} → {cur['stroke']}")
            if cur["stroke_width"] != chk["stroke_width"]:
                changes.append(f"stroke_width: {chk['stroke_width']} → {cur['stroke_width']}")
            if cur["z_index"] != chk["z_index"]:
                changes.append(f"z_index: {chk['z_index']} → {cur['z_index']}")
            if cur["layer"] != chk["layer"]:
                changes.append(f"layer: {chk['layer']} → {cur['layer']}")
            if cur["outline_len"] != chk["outline_len"]:
                changes.append(f"points: {chk['outline_len']} → {cur['outline_len']}")
            if cur["primitive_type"] != chk["primitive_type"]:
                changes.append(f"type: {chk['primitive_type']} → {cur['primitive_type']}")
            if changes:
                modified.append({"id": rid, "changes": changes})

        lines = [
            f"Checkpoint: '{name}'",
            f"Added: {sorted(added_ids)}" if added_ids else "Added: (none)",
            f"Removed: {sorted(removed_ids)}" if removed_ids else "Removed: (none)",
            f"Modified: {len(modified)} region(s)",
        ]
        if not added_ids and not removed_ids and not modified:
            lines.append("  (no changes since checkpoint)")
        for m in modified:
            lines.append(f"  {m['id']}: {'; '.join(m['changes'])}")

        return "\n".join(lines)

    @mcp.tool(
        name="render_diff",
        description="Render a visual diff PNG comparing current state against "
        "a named checkpoint. Shows added (green), removed (red), and modified "
        "(yellow) regions. 💡 Use after checkpoint/restore to verify changes "
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
        scene = get_graph()
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document — call create_document first"

        cps = scene.list_checkpoints(doc_id)
        if not cps:
            return f"No checkpoints found for '{doc_id}'"

        try:
            _doc_snap, checkpoint_regions = scene.checkpoint_snapshot(doc_id, name)
        except KeyError:
            return f"Checkpoint '{name}' not found"

        # Get current regions
        current_regions = {r.id: r for r in scene.get_all_regions(doc_id)}
        doc = scene.get_document(doc_id)

        # Build diff SVG overlay
        w, h = doc.width, doc.height
        svg_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            f'  <rect width="{w}" height="{h}" fill="#1a1a2e"/>',
            '  <text x="10" y="20" font-size="14" font-family="monospace" fill="#888">',
            f'    Diff vs checkpoint "{name}" — green=added, red=removed, yellow=modified</text>',
        ]

        cp_ids = set(checkpoint_regions.keys())
        cur_ids = set(current_regions.keys())

        added = cur_ids - cp_ids
        removed = cp_ids - cur_ids
        common = cur_ids & cp_ids

        # Checkpoint state (gray ghosts)
        for rid in sorted(cp_ids):
            r = checkpoint_regions[rid]
            if not r.outline:
                continue
            pts = " ".join(f"{p[0]*w:.1f},{p[1]*h:.1f}" for p in r.outline)
            if r.constraints.closed:
                svg_lines.append(f'  <polygon points="{pts}" fill="#666" fill-opacity="0.12" stroke="#666" stroke-opacity="0.25" stroke-width="1"/>')
            else:
                svg_lines.append(f'  <polyline points="{pts}" fill="none" stroke="#666" stroke-opacity="0.25" stroke-width="1"/>')

        # Current state (color overlay on top)
        for rid in sorted(cur_ids):
            r = current_regions[rid]
            if not r.outline:
                continue
            if rid in added:
                color, label = "#33ff33", "added"
            elif rid in removed:
                continue  # already shown in red above
            else:
                # Check if modified
                chk = checkpoint_regions.get(rid)
                if chk:
                    cur_fill = str(r.style.fill)
                    chk_fill = str(chk.style.fill)
                    if cur_fill == chk_fill and len(r.outline) == len(chk.outline):
                        continue  # unchanged — skip for clarity
                color, label = "#ffdd33", "modified"

            pts = " ".join(f"{p[0]*w:.1f},{p[1]*h:.1f}" for p in r.outline)
            svg_lines.append(f'  <polygon points="{pts}" fill="{color}" fill-opacity="0.35" stroke="{color}" stroke-width="2"/>')

        # Special handling for removed — red X marks
        for rid in sorted(removed):
            r = checkpoint_regions[rid]
            if not r.outline:
                continue
            pts = " ".join(f"{p[0]*w:.1f},{p[1]*h:.1f}" for p in r.outline)
            svg_lines.append(f'  <polygon points="{pts}" fill="#ff3333" fill-opacity="0.25" stroke="#ff3333" stroke-width="2"/>')
            cx = sum(p[0] for p in r.outline) / len(r.outline) * w
            cy = sum(p[1] for p in r.outline) / len(r.outline) * h
            s = 6
            svg_lines.append(f'  <line x1="{cx-s}" y1="{cy-s}" x2="{cx+s}" y2="{cy+s}" stroke="#ff3333" stroke-width="2"/>')
            svg_lines.append(f'  <line x1="{cx-s}" y1="{cy+s}" x2="{cx+s}" y2="{cy-s}" stroke="#ff3333" stroke-width="2"/>')

        svg_lines.append("</svg>")
        diff_svg = "\n".join(svg_lines)

        try:
            from avge_engine.renderer.raster import render_preview_base64
            b64 = render_preview_base64(diff_svg, scale=scale)
            return f"Diff rendered: data:image/png;base64,{b64[:50]}... ({len(b64)} chars)"
        except Exception as e:
            return f"Diff SVG generated but PNG render failed: {e}"
