"""
Scene graph — multi-document in-memory store with versioning.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any, TYPE_CHECKING

from avge_engine.geometry import (
    CurveConstraints,
    Point2D,
    Transform,
    compute_bounds,
    fit_curves,
    normalize_outline,
    sample_curve,
)
from avge_engine.effects import Style, GradientDef
from avge_engine.storage import StorageAdapter
from avge_engine.scene.models import RegionNode, DocumentNode, ToolStats

class SceneGraph:
    """In-memory scene graph supporting multiple named documents."""

    def __init__(self) -> None:
        self._docs: dict[str, DocumentNode] = {}
        self._regions_by_doc: dict[str, dict[str, RegionNode]] = {}
        self._checkpoints: dict[str, dict[str, tuple[DocumentNode | None, dict[str, RegionNode]]]] = {}
        self._checkpoint_meta: dict[str, dict[str, str]] = {}
        self._auto_counter: int = 0
        self._auto_enabled: bool = True
        self._last_doc_id: str | None = None
        self._storage: StorageAdapter | None = None
        self.tool_stats: ToolStats = ToolStats()

    def attach_storage(self, adapter: StorageAdapter) -> None:
        self._storage = adapter

    def _persist(self, doc_id: str) -> None:
        if not self._storage:
            return
        doc = self._docs.get(doc_id)
        if doc:
            import datetime as _dt
            doc.updated_at = _dt.datetime.now().isoformat()
        regions = self._regions_by_doc.get(doc_id, {})
        groups_data = {}
        if hasattr(self, '_groups') and self._groups:
            prefix = f"{doc_id}::"
            for key, val in self._groups.items():
                if key.startswith(prefix):
                    groups_data[key[len(prefix):]] = val
        ts = __import__("datetime").datetime.now().isoformat()
        self._storage.save(doc_id, {
            "document": doc.model_dump() if doc else {},
            "regions": {k: v.model_dump() for k, v in regions.items()},
            "metadata": {
                "updated": ts,
                "tool_stats": self.tool_stats.to_metadata(),
            },
            "groups": groups_data,
        })

    def load_document(self, document_id: str) -> bool:
        if not self._storage:
            return False
        data = self._storage.load(document_id)
        if not data:
            return False
        from avge_engine.scene.models import DocumentNode, RegionNode
        d = data.get("document", {})
        self._docs[document_id] = DocumentNode(**d)
        regions = {}
        for rid, r in data.get("regions", {}).items():
            if "constraints" in r and isinstance(r["constraints"], dict):
                r["constraints"] = CurveConstraints(**r["constraints"])
            if "style" in r and isinstance(r["style"], dict):
                r["style"] = Style(**r["style"])
            if "transform" in r and isinstance(r["transform"], dict):
                r["transform"] = Transform(**r["transform"])
            regions[rid] = RegionNode(**r)
        self._regions_by_doc[document_id] = regions
        self._last_doc_id = document_id
        # Restore groups from storage
        groups_data = data.get("groups", {})
        if groups_data:
            if not hasattr(self, '_groups'):
                self._groups = {}
            prefix = f"{document_id}::"
            for name, ids in groups_data.items():
                self._groups[f"{prefix}{name}"] = list(ids)
        # Restore tool stats from metadata
        meta = data.get("metadata", {})
        if "tool_stats" in meta:
            self.tool_stats.from_metadata(meta["tool_stats"])
        return True

    def list_stored_documents(self) -> list[dict]:
        """List all documents in the attached storage."""
        if not self._storage:
            return []
        return self._storage.list_documents()

    def _resolve_doc(self, document_id: str | None = None) -> str:
        """Resolve document_id: use explicit value or fall back to last created."""
        if document_id:
            return document_id
        if self._last_doc_id is None:
            raise RuntimeError("No document exists. Call create_document first.")
        return self._last_doc_id

    # ── Document management ─────────────────────────────────────────

    def create_document(
        self,
        width: int = 1000,
        height: int = 1000,
        unit: str = "px",
        background: str = "#FFFFFF",
        name: str = "",
    ) -> DocumentNode:
        """Create a new document with a unique UUID.

        Args:
            width, height, unit, background: canvas properties.
            name: Optional human-readable name for identification.

        Returns:
            DocumentNode with auto-generated id (UUID).
        """
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        doc = DocumentNode(
            id=doc_id,
            name=name,
            width=width,
            height=height,
            unit=unit,
            background=background,
            created_at=now,
            updated_at=now,
        )
        self._docs[doc_id] = doc
        self._regions_by_doc[doc_id] = {}
        self._last_doc_id = doc_id
        self._auto_checkpoint(doc_id, "create_document", f"{width}x{height}")
        self._persist(doc_id)
        return doc

    def get_document(self, document_id: str) -> DocumentNode:
        """Get a document by ID. Raises ValueError if not found."""
        doc = self._docs.get(document_id)
        if doc is None:
            raise ValueError(
                f"Document '{document_id}' not found. "
                f"(In-memory — server restarts clear all documents) "
                f"Active: {list(self._docs.keys())}"
            )
        return doc

    def has_document(self, document_id: str | None = None) -> bool:
        doc_id = document_id or self._last_doc_id
        return doc_id in self._docs if doc_id else False

    def list_documents(self) -> list[dict[str, Any]]:
        """Return summary of all documents."""
        return [
            {
                "id": d.id,
                "name": d.name,
                "width": d.width,
                "height": d.height,
                "version": d.version,
                "region_count": len(self._regions_by_doc.get(d.id, {})),
                "created_at": d.created_at,
                "updated_at": d.updated_at,
            }
            for d in self._docs.values()
        ]

    # ── Region operations ───────────────────────────────────────────

    def _regions_for(self, document_id: str) -> dict[str, RegionNode]:
        """Get the regions dict for a document."""
        regions = self._regions_by_doc.get(document_id)
        if regions is None:
            raise ValueError(f"Document '{document_id}' not found")
        return regions

    def create_region(
        self,
        outline: list[Point2D],
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        clip_to: str | None = None,
        constraints: CurveConstraints | None = None,
        style: Style | None = None,
        transform: Transform | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegionNode:
        doc_id = self._resolve_doc(document_id)
        doc = self.get_document(doc_id)
        regions = self._regions_for(doc_id)
        rid = region_id or f"r_{uuid.uuid4().hex[:8]}"
        if rid in regions:
            raise ValueError(f"Region '{rid}' already exists in document '{document_id}'")

        norm_outline = normalize_outline(outline)

        region = RegionNode(
            id=rid,
            layer=layer,
            z_index=z_index,
            clip_to=clip_to,
            outline=norm_outline,
            constraints=constraints or CurveConstraints(),
            style=style or Style(),
            transform=transform or Transform(),
            metadata=metadata or {},
        )
        regions[rid] = region
        self._auto_checkpoint(doc_id, "create_region", rid)
        self._persist(doc_id)
        doc.version += 1
        return region

    def get_region(self, region_id: str, document_id: str | None = None) -> RegionNode:
        regions = self._regions_for(self._resolve_doc(document_id))
        region = regions.get(region_id)
        if region is None:
            raise ValueError(f"Region '{region_id}' not found in document '{document_id}'")
        return region

    def has_region(self, region_id: str, document_id: str | None = None) -> bool:
        return region_id in self._regions_for(self._resolve_doc(document_id))

    def get_all_regions(self, document_id: str) -> list[RegionNode]:
        """Return regions in insertion order."""
        return list(self._regions_for(document_id).values())

    def region_count(self, document_id: str | None = None) -> int:
        return len(self._regions_for(self._resolve_doc(document_id)))

    # ── Region deletion ────────────────────────────────────────────────

    def delete_region(self, document_id: str, region_id: str) -> bool:
        """Delete a region by ID. Returns True if deleted, False if not found."""
        regions = self._regions_for(document_id)
        if region_id not in regions:
            return False
        del regions[region_id]
        self.get_document(document_id).version += 1
        self._auto_checkpoint(document_id, "delete_region", region_id)
        self._persist(document_id)
        return True

    def delete_regions(self, document_id: str, ids: list[str]) -> list[str]:
        """Delete multiple regions. Returns list of actually deleted IDs."""
        deleted: list[str] = []
        for rid in ids:
            if self.delete_region(document_id, rid):
                deleted.append(rid)
        return deleted

    # ── Style presets ──────────────────────────────────────────────

    PRESETS: dict[str, dict] = {
        "warm_shaded": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":1,"y2":1,"stops":[{"offset":0,"color":"#F5E6D0"},{"offset":1,"color":"#D4B898"}]}', "opacity": 1.0},
        "cool_shaded": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":1,"y2":1,"stops":[{"offset":0,"color":"#D0E4F0"},{"offset":1,"color":"#8AB0C8"}]}', "opacity": 1.0},
        "metallic": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#E8E8E8"},{"offset":0.5,"color":"#C0C0C0"},{"offset":1,"color":"#888888"}]}', "opacity": 1.0},
        "glow": {"fill": "#FFE8A0", "opacity": 0.6, "blend_mode": "screen"},
        "shadow": {"fill": "#000000", "opacity": 0.2, "blend_mode": "multiply"},
        "wood": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#D4A868"},{"offset":1,"color":"#A07840"}]}', "opacity": 1.0},
        "car_paint": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#CC3333"},{"offset":0.15,"color":"#991111"},{"offset":0.5,"color":"#CC3333"},{"offset":1,"color":"#660000"}]}', "opacity": 1.0},
        "deep_shadow": {"fill_gradient": '{"type":"radial","cx":0.5,"cy":0.5,"r":0.5,"stops":[{"offset":0,"color":"#000000"},{"offset":0.7,"color":"#000000"},{"offset":1,"color":"#FFFFFF"}]}', "opacity": 0.35, "blend_mode": "multiply"},
        "chrome": {"fill_gradient": '{"type":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[{"offset":0,"color":"#FFFFFF"},{"offset":0.3,"color":"#CCCCCC"},{"offset":0.5,"color":"#888888"},{"offset":0.7,"color":"#CCCCCC"},{"offset":1,"color":"#AAAAAA"}]}', "opacity": 1.0},
        # ── Text presets ──
        "meme_title": {"fill": "#FFFFFF", "stroke": "#000000", "stroke_width": 0.003, "opacity": 1.0},
        "meme_caption": {"fill": "#FF0000", "opacity": 1.0},
        "label": {"fill": "#333333", "opacity": 1.0},
        "label_light": {"fill": "#888888", "opacity": 1.0},
        "title": {"fill": "#111111", "stroke": "#333333", "stroke_width": 0.001, "opacity": 1.0},
        "subtitle": {"fill": "#555555", "opacity": 0.85},
        "comic": {"fill": "#111111", "stroke": "#333333", "stroke_width": 0.001, "opacity": 1.0},
    }

    # ── Boolean operations (union/subtract/intersect/xor) ───────────

    def boolean_operation(
        self,
        operation: str,
        region_ids: list[str],
        new_region_id: str | None = None,
        document_id: str | None = None,
        *,
        keep_originals: bool = False,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
    ) -> RegionNode:
        """Perform boolean geometry on regions using shapely.

        Args:
            operation: "union", "subtract", "intersect", or "xor".
            region_ids: IDs of at least 2 regions to combine.
            new_region_id: ID for the result region.
            keep_originals: If True, keep input regions (default False).
            fill: Fill color for the result.
            stroke: Stroke color for the result.
            stroke_width: Stroke width for the result.
            opacity: Opacity for the result.

        Returns the new RegionNode.
        """
        import shapely
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        if len(region_ids) < 2:
            raise ValueError("Need at least 2 regions for boolean operation")

        # Sample each region's fitted curve to get boundary polygon
        polys: list[Polygon] = []
        for rid in region_ids:
            r = regions.get(rid)
            if r is None:
                raise ValueError(f"Region '{rid}' not found")
            segments = fit_curves(
                r.outline,
                closed=r.constraints.closed,
                smoothness=r.constraints.smoothness,
                tensions=list(r.constraints.tensions) if r.constraints.tensions else None,
                handle_in=list(r.constraints.handle_in) if r.constraints.handle_in else None,
                handle_out=list(r.constraints.handle_out) if r.constraints.handle_out else None,
            )
            pts = sample_curve(segments, samples_per_segment=64)
            if len(pts) < 3:
                raise ValueError(f"Region '{rid}' has too few boundary points ({len(pts)})")
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            polys.append(poly)

        # Perform operation
        try:
            if operation == "union":
                result = unary_union(polys)
                if hasattr(result, 'is_valid') and not result.is_valid:
                    result = result.buffer(0)
            elif operation == "intersect":
                result = polys[0]
                for p in polys[1:]:
                    result = result.intersection(p)
            elif operation == "subtract" or operation == "difference":
                result = polys[0]
                for p in polys[1:]:
                    result = result.difference(p)
            elif operation == "xor" or operation == "sym_diff":
                result = polys[0]
                for p in polys[1:]:
                    result = result.symmetric_difference(p)
            else:
                raise ValueError(f"Unknown operation: {operation}")
        except Exception as e:
            raise RuntimeError(f"Boolean {operation} failed: {e}")

        # Extract outline from result polygon
        if result.is_empty or result.area < 0.0001:
            raise RuntimeError(f"Boolean {operation} produced empty result")

        # Get exterior coordinates, simplify slightly
        coords = list(result.exterior.coords)
        # shapely includes closing point; remove it
        if len(coords) > 2 and coords[0] == coords[-1]:
            coords = coords[:-1]

        if len(coords) < 3:
            raise RuntimeError("Boolean result has too few points")

        rid = new_region_id or f"bool_{uuid.uuid4().hex[:6]}"
        result_fill = fill if fill is not None else "#CCCCCC"
        result_style = Style(
            fill=result_fill,
            stroke=stroke,
            stroke_width=max(0.001, min(0.1, stroke_width)) if stroke_width is not None else 0.005,
            opacity=max(0.0, min(1.0, opacity)) if opacity is not None else 1.0,
        )
        result_region = RegionNode(
            id=rid,
            outline=[(float(x), float(y)) for x, y in coords],
            constraints=CurveConstraints(smoothness=0.3, closed=True),
            style=result_style,
        )
        self._regions_for(doc_id)[rid] = result_region
        self.get_document(doc_id).version += 1

        if not keep_originals:
            for rid in region_ids:
                del regions[rid]

        self._auto_checkpoint(doc_id, f"boolean_{operation}", rid)
        self._persist(doc_id)
        return result_region

    # ── Group operations ───────────────────────────────────────────

    def group_regions(self, group_name: str, region_ids: list[str], document_id: str | None = None, *, replace: bool = False) -> list[str]:
        """Group regions under a name. Creates or appends to an existing group.
        When ``replace`` is True, replaces existing members instead of appending.
        """
        doc_id = self._resolve_doc(document_id)
        if not hasattr(self, '_groups'):
            self._groups: dict[str, list[str]] = {}
        key = f"{doc_id}::{group_name}"
        existing = [] if replace else self._groups.get(key, [])
        for rid in region_ids:
            if self.has_region(rid, doc_id) and rid not in existing:
                existing.append(rid)
        self._groups[key] = existing
        self._persist(doc_id)
        return existing

    def add_to_group(self, group_name: str, region_ids: list[str], document_id: str | None = None) -> list[str]:
        """Add regions to an existing group. Creates the group if it doesn't exist.
        Returns the updated member list.
        """
        doc_id = self._resolve_doc(document_id)
        if not hasattr(self, '_groups'):
            self._groups: dict[str, list[str]] = {}
        key = f"{doc_id}::{group_name}"
        members = self._groups.get(key, [])
        for rid in region_ids:
            if self.has_region(rid, doc_id) and rid not in members:
                members.append(rid)
        self._groups[key] = members
        self._persist(doc_id)
        return members

    def remove_from_group(self, group_name: str, region_ids: list[str], document_id: str | None = None) -> list[str]:
        """Remove specific regions from a group. Returns the updated member list.
        Raises ValueError if the group doesn't exist.
        """
        doc_id = self._resolve_doc(document_id)
        if not hasattr(self, '_groups'):
            raise ValueError(f"Group '{group_name}' not found (no groups exist)")
        key = f"{doc_id}::{group_name}"
        if key not in self._groups:
            raise ValueError(f"Group '{group_name}' not found")
        removed_ids = [rid for rid in region_ids if rid in self._groups[key]]
        self._groups[key] = [rid for rid in self._groups[key] if rid not in region_ids]
        self._persist(doc_id)
        return removed_ids

    def ungroup_regions(self, group_name: str | list[str], document_id: str | None = None) -> bool | list[str]:
        """Remove one or more groups. Returns True (single) or list of removed names."""
        doc_id = self._resolve_doc(document_id)
        if not hasattr(self, '_groups'):
            return False if isinstance(group_name, str) else []
        if isinstance(group_name, str):
            key = f"{doc_id}::{group_name}"
            return self._groups.pop(key, None) is not None
        removed = []
        for name in group_name:
            key = f"{doc_id}::{name}"
            if self._groups.pop(key, None) is not None:
                removed.append(name)
        return removed

    def get_group(self, group_name: str, document_id: str | None = None) -> list[dict]:
        """Get regions in a group with their IDs and bounds."""
        doc_id = self._resolve_doc(document_id)
        if not hasattr(self, '_groups'):
            return []
        key = f"{doc_id}::{group_name}"
        ids = self._groups.get(key, [])
        result = []
        for rid in ids:
            try:
                r = self.get_region(rid, doc_id)
                result.append({'id': rid, 'bounds': compute_bounds(r.outline)})
            except ValueError:
                pass
        return result

    def list_groups(self, document_id: str | None = None) -> list[dict]:
        """List all groups and their sizes."""
        doc_id = self._resolve_doc(document_id)
        if not hasattr(self, '_groups'):
            return []
        prefix = f"{doc_id}::"
        return [{'name': k[len(prefix):], 'count': len(v)}
                for k, v in self._groups.items() if k.startswith(prefix)]

    def duplicate_group(
        self,
        group_name: str,
        document_id: str | None = None,
        *,
        new_prefix: str | None = None,
        dx: float = 0.0,
        dy: float = 0.0,
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        rotate: float = 0.0,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> list[str]:
        """Duplicate all regions in a named group with transforms applied.

        Each region is copied, offset/scaled/rotated/mirrored, and added
        to a new group. The original group is unchanged.
        """
        import math
        doc_id = self._resolve_doc(document_id)
        members = self.get_group(group_name, doc_id)
        if not members:
            raise ValueError(f"Group '{group_name}' not found or empty")

        angle = math.radians(rotate)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        scale_x = sx if sx is not None else scale
        scale_y = sy if sy is not None else scale
        if mirror_x:
            scale_x = -abs(scale_x)
        if mirror_y:
            scale_y = -abs(scale_y)

        new_ids: list[str] = []
        for m in members:
            rid = m["id"]
            original = self._regions_for(doc_id).get(rid)
            if original is None:
                continue
            new_rid = f"{new_prefix or group_name + '_copy'}_{rid}"
            cx = sum(p[0] for p in original.outline) / len(original.outline)
            cy = sum(p[1] for p in original.outline) / len(original.outline)
            new_outline = []
            for x, y in original.outline:
                lx = (x - cx) * scale_x
                ly = (y - cy) * scale_y
                rx = lx * cos_a - ly * sin_a
                ry = lx * sin_a + ly * cos_a
                new_outline.append((rx + cx + dx, ry + cy + dy))
            from avge_engine.scene.models import RegionNode
            dup = RegionNode(
                id=new_rid, layer=original.layer, z_index=original.z_index,
                clip_to=original.clip_to, outline=new_outline,
                constraints=original.constraints, style=original.style,
                transform=original.transform,
                metadata=original.metadata.copy() if original.metadata else {},
            )
            self._regions_for(doc_id)[new_rid] = dup
            new_ids.append(new_rid)

        if new_ids:
            group_key = f"{doc_id}::{new_prefix or group_name + '_copy'}"
            if not hasattr(self, '_groups'):
                self._groups = {}
            self._groups[group_key] = new_ids
            self.get_document(doc_id).version += 1
            self._auto_checkpoint(doc_id, "duplicate_group", str(new_ids))
            self._persist(doc_id)
        return new_ids

    # ── Layer operations ───────────────────────────────────────────

    def list_layers(self, document_id: str | None = None) -> list[dict]:
        """List all unique layers and their region counts."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        layers: dict[str, int] = {}
        for r in regions.values():
            layers[r.layer] = layers.get(r.layer, 0) + 1
        return [{'layer': k, 'count': v} for k, v in sorted(layers.items())]

    def reorder_layer(self, layer: str, z_offset: int, document_id: str | None = None) -> int:
        """Shift all regions in a layer by z_offset. Returns count affected."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        count = 0
        for r in regions.values():
            if r.layer == layer:
                r.z_index += z_offset
                r.version += 1
                count += 1
        if count:
            self.get_document(doc_id).version += 1
        return count

    def move_to_front(self, region_id: str, document_id: str | None = None) -> bool:
        """Move a region to the highest z_index. Returns True if moved."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        region = regions.get(region_id)
        if region is None:
            return False
        max_z = max(r.z_index for r in regions.values())
        if region.z_index < max_z:
            region.z_index = max_z + 1
            region.version += 1
            self.get_document(doc_id).version += 1
            self._auto_checkpoint(doc_id, "move_to_front", region_id)
            self._persist(doc_id)
        return True

    def move_to_back(self, region_id: str, document_id: str | None = None) -> bool:
        """Move a region to the lowest z_index. Returns True if moved."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        region = regions.get(region_id)
        if region is None:
            return False
        min_z = min(r.z_index for r in regions.values())
        if region.z_index > min_z:
            region.z_index = min_z - 1
            region.version += 1
            self.get_document(doc_id).version += 1
            self._auto_checkpoint(doc_id, "move_to_back", region_id)
            self._persist(doc_id)
        return True

    # ── Critique composition (design skill Rule 7 auto-check) ──────

    def critique_composition(self, document_id: str | None = None) -> list[str]:
        """Auto-check the scene against design skill rules. Returns list of findings."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        findings: list[str] = []

        # Rule 1: Depth — count gradient-filled vs flat-filled regions
        flat_cnt = sum(1 for r in regions.values()
                      if isinstance(r.style.fill, str) and r.style.fill and r.style.opacity >= 0.95)
        grad_cnt = sum(1 for r in regions.values()
                      if isinstance(r.style.fill, dict))
        if flat_cnt > grad_cnt * 3 and flat_cnt > 5:
            findings.append(f"Rule 1 (depth): {flat_cnt} flat fills, only {grad_cnt} gradients — consider more depth shading")

        # Rule 2: Stroke hierarchy — check for uniform stroke widths
        widths = [r.style.stroke_width for r in regions.values() if r.style.stroke]
        if len(widths) > 3:
            unique = len(set(f'{w:.4f}' for w in widths))
            if unique <= 1:
                findings.append(f"Rule 2 (stroke hierarchy): all {len(widths)} stroked regions use the same width — vary by silhouette vs detail")

        # Rule 3: Palette size
        fills = [str(r.style.fill) for r in regions.values() if r.style.fill and isinstance(r.style.fill, str)]
        unique_fills = len(set(fills))
        if unique_fills > 8:
            findings.append(f"Rule 3 (palette): {unique_fills} unique fill colors — aim for 3-5 cohesive colors")
        if unique_fills <= 1 and len(fills) > 5:
            findings.append(f"Rule 3 (palette): only 1 fill color across {len(fills)} regions — add variation")

        # Rule 5: Overlapping / misaligned regions —
        # Detect when a region logically inside another extends beyond it.
        # Only flag when the inner region's center is within the outer bounds
        # (proving containment intent) but the inner region protrudes outside.
        sorted_regions = sorted(regions.values(), key=lambda r: r.z_index)
        for i, outer in enumerate(sorted_regions):
            if outer.z_index < 0:
                continue
            ob = compute_bounds(outer.outline)
            if not ob or ob["w"] < 0.05 or ob["h"] < 0.05:
                continue
            ox1, oy1 = ob["x"], ob["y"]
            ox2, oy2 = ob["x"] + ob["w"], ob["y"] + ob["h"]
            for inner in sorted_regions[i+1:]:
                if inner.z_index <= outer.z_index:
                    continue
                ib = compute_bounds(inner.outline)
                if not ib:
                    continue
                ix1, iy1 = ib["x"], ib["y"]
                ix2, iy2 = ib["x"] + ib["w"], ib["y"] + ib["h"]
                # Inner's center must be inside outer for containment relationship
                cx = (ix1 + ix2) / 2
                cy = (iy1 + iy2) / 2
                if cx < ox1 or cx > ox2 or cy < oy1 or cy > oy2:
                    continue
                # Skip narrow vertical elements (bookmarks, pendants)
                if ib["h"] > ob["h"] * 1.2 and ix1 >= ox1 and ix2 <= ox2:
                    continue
                # Check if inner extends significantly outside outer
                margin = 0.02
                if (ix1 < ox1 - margin or iy1 < oy1 - margin or
                    ix2 > ox2 + margin or iy2 > oy2 + margin):
                    findings.append(
                        f"Rule 5 (overlap): region '{inner.id}' (z={inner.z_index}) "
                        f"extends outside '{outer.id}' (z={outer.z_index}) — "
                        f"inner should stay inside outer bounds for correct layering"
                    )
                    break

        # Rule 6: Off-canvas — region extends fully outside the viewport
        for r in regions.values():
            b = compute_bounds(r.outline)
            if b and (b['x'] + b['w'] < 0 or b['x'] > 1 or b['y'] + b['h'] < 0 or b['y'] > 1):
                findings.append(f"Rule 6 (grounding): region '{r.id}' is off-canvas")

        # General: empty scene
        if not regions:
            findings.append("Scene is empty — nothing to critique")

        return findings

    # ── Transform operations ───────────────────────────────────────

    def transform_objects(
        self,
        ids: list[str],
        document_id: str | None = None,
        *,
        dx: float = 0.0,
        dy: float = 0.0,
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        rotate: float = 0.0,
        group_mode: bool = False,
        pivot_x: float | None = None,
        pivot_y: float | None = None,
        pivot_mode: str | None = None,
        z_index: int | None = None,
        group_name: str | None = None,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> list[str]:
        """Move, scale (optionally non-uniform), and/or rotate existing regions.

        When ``group_name`` is set, it resolves the group's members as IDs.
        When ``z_index`` is set, all affected regions get this z_index.
        When ``mirror_x`` or ``mirror_y`` is True, the outline is flipped
        around each region's center (or the group center in group_mode).
        """
        import math

        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        affected: list[str] = []

        # Resolve group_name to member IDs
        if group_name is not None:
            members = self.get_group(group_name, doc_id)
            if not members:
                raise ValueError(f"Group '{group_name}' not found")
            ids = [m["id"] for m in members]

        # Resolve scale factors
        scale_x = sx if sx is not None else scale
        scale_y = sy if sy is not None else scale
        # Apply mirror
        if mirror_x:
            scale_x = -abs(scale_x)
        if mirror_y:
            scale_y = -abs(scale_y)
        angle = math.radians(rotate)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Compute group center if group_mode
        gcx = gcy = 0.0
        if group_mode and ids:
            count = 0
            for rid in ids:
                r = regions.get(rid)
                if r is None:
                    continue
                for px, py in r.outline:
                    gcx += px
                    gcy += py
                    count += 1
            if count:
                gcx /= count
                gcy /= count

        # Pivot overrides both per-region and group center
        if pivot_x is not None and pivot_y is not None:
            gcx, gcy = pivot_x, pivot_y
        elif pivot_mode == "base":
            pass  # handled per-region

        for rid in ids:
            region = regions.get(rid)
            if region is None:
                continue
            # Center for scaling/rotation
            if pivot_mode == "base":
                from avge_engine.geometry import compute_bounds
                b = compute_bounds(region.outline)
                cx = b["x"] + b["w"] / 2
                cy = b["y"] + b["h"]
            elif pivot_mode == "center":
                from avge_engine.geometry import compute_bounds
                b = compute_bounds(region.outline)
                cx = b["x"] + b["w"] / 2
                cy = b["y"] + b["h"] / 2
            elif group_mode or (pivot_x is not None and pivot_y is not None):
                cx, cy = gcx, gcy
            else:
                cx = sum(p[0] for p in region.outline) / len(region.outline)
                cy = sum(p[1] for p in region.outline) / len(region.outline)

            new_outline = []
            for x, y in region.outline:
                # Scale around center
                lx = (x - cx) * scale_x
                ly = (y - cy) * scale_y
                # Rotate around center
                rx = lx * cos_a - ly * sin_a
                ry = lx * sin_a + ly * cos_a
                # Translate
                new_outline.append((rx + cx + dx, ry + cy + dy))

            region.outline = normalize_outline(new_outline)
            # If the region has a primitive dict, update its coordinates instead
            # of dropping it — this preserves clean SVG elements (ellipse, rect).
            if region.primitive:
                has_scale = (abs(scale_x - 1) > 0.001 or abs(scale_y - 1) > 0.001)
                has_rotate = abs(rotate) > 0.001
                ptype = region.primitive.get("type")

                if has_scale and not has_rotate and not mirror_x and not mirror_y:
                    # Scale-only: update primitive params in-place (preserves <ellipse>/<rect>)
                    p = region.primitive
                    if ptype == "ellipse":
                        p["cx"] = round((p["cx"] - cx) * scale_x + cx + dx, 6)
                        p["cy"] = round((p["cy"] - cy) * scale_y + cy + dy, 6)
                        p["rx"] = round(p["rx"] * scale_x, 6)
                        p["ry"] = round(p["ry"] * scale_y, 6)
                    elif ptype == "rect":
                        p["x"] = round((p["x"] - cx) * scale_x + cx + dx, 6)
                        p["y"] = round((p["y"] - cy) * scale_y + cy + dy, 6)
                        p["width"] = round(p["width"] * scale_x, 6)
                        p["height"] = round(p["height"] * scale_y, 6)
                    elif ptype == "line":
                        p["x1"] = round((p["x1"] - cx) * scale_x + cx + dx, 6)
                        p["y1"] = round((p["y1"] - cy) * scale_y + cy + dy, 6)
                        p["x2"] = round((p["x2"] - cx) * scale_x + cx + dx, 6)
                        p["y2"] = round((p["y2"] - cy) * scale_y + cy + dy, 6)
                    # Still update outline so bounds etc. are correct
                    new_outline = [(
                        ((x - cx) * scale_x * cos_a - (y - cy) * scale_y * sin_a) + cx + dx,
                        ((x - cx) * scale_x * sin_a + (y - cy) * scale_y * cos_a) + cy + dy,
                    ) for x, y in region.outline]
                    region.outline = normalize_outline(new_outline)

                elif has_rotate and not mirror_x and not mirror_y:
                    # Rotation only: set region.transform.rotate, keep primitive
                    rot_deg = rotate
                    object.__setattr__(region.transform, "rotate",
                                       region.transform.rotate + rot_deg)
                    new_outline = [(
                        ((x - cx) * math.cos(angle) - (y - cy) * math.sin(angle)) + cx + dx,
                        ((x - cx) * math.sin(angle) + (y - cy) * math.cos(angle)) + cy + dy,
                    ) for x, y in region.outline]
                    region.outline = normalize_outline(new_outline)

                elif abs(dx) > 0.001 or abs(dy) > 0.001:
                    # Pure translation: update primitive coords in-place
                    p = region.primitive
                    if p.get("type") == "ellipse":
                        p["cx"] += dx
                        p["cy"] += dy
                    elif p.get("type") == "rect":
                        p["x"] += dx
                        p["y"] += dy
                    elif p.get("type") == "line":
                        p["x1"] += dx
                        p["y1"] += dy
                        p["x2"] += dx
                        p["y2"] += dy
            region.version += 1
            affected.append(rid)

        # Apply z_index to all affected regions
        if z_index is not None:
            for rid in affected:
                region = regions.get(rid)
                if region is not None:
                    region.z_index = z_index

        if affected:
            self.get_document(doc_id).version += 1
            self._auto_checkpoint(doc_id, "transform_objects", str(affected))
            self._persist(doc_id)
        return affected

    # ── Find objects ────────────────────────────────────────────────

    def find_objects(
        self,
        document_id: str | None = None,
        *,
        fill: str | None = None,
        min_x: float | None = None, max_x: float | None = None,
        min_y: float | None = None, max_y: float | None = None,
        min_w: float | None = None, max_w: float | None = None,
        min_h: float | None = None, max_h: float | None = None,
        z_min: int | None = None, z_max: int | None = None,
        has_stroke: bool | None = None,
        layer: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> list[dict]:
        """Query regions by visual properties, bounds, z-index, and metadata tags.

        When ``tags`` is provided, all specified key/value pairs must match
        the region's metadata (AND logic) for the region to be included.
        """
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        results: list[dict] = []
        for r in regions.values():
            if fill is not None and r.style.fill != fill:
                continue
            if layer is not None and r.layer != layer:
                continue
            if has_stroke is not None:
                if has_stroke and r.style.stroke is None:
                    continue
                if not has_stroke and r.style.stroke is not None:
                    continue
            if tags is not None:
                if not all(r.metadata.get(k) == v for k, v in tags.items()):
                    continue
            if z_min is not None and r.z_index < z_min: continue
            if z_max is not None and r.z_index > z_max: continue
            b = compute_bounds(r.outline)
            if b is None:
                continue
            if min_x is not None and b["x"] < min_x: continue
            if max_x is not None and b["x"] > max_x: continue
            if min_y is not None and b["y"] < min_y: continue
            if max_y is not None and b["y"] > max_y: continue
            if min_w is not None and b["w"] < min_w: continue
            if max_w is not None and b["w"] > max_w: continue
            if min_h is not None and b["h"] < min_h: continue
            if max_h is not None and b["h"] > max_h: continue
            results.append({
                "id": r.id, "fill": r.style.fill, "stroke": r.style.stroke,
                "bounds": b, "layer": r.layer, "z_index": r.z_index,
                "clip_to": r.clip_to,
            })
        return results

    # ── Batch operations ────────────────────────────────────────────

    def batch(self, ops: list[dict], document_id: str | None = None) -> list[dict]:
        """Execute multiple operations in sequence within one document.

        Each op dict requires a "tool" key. Supported: create_region,
        create_shape, create_primitive, create_curve, edit_region,
        duplicate_region, delete_region, style_objects,
        transform_objects, move_to_front, move_to_back.

        Returns list of result dicts, one per op in order.
        """
        doc_id = self._resolve_doc(document_id)
        results: list[dict] = []
        for op in ops:
            tool = op.pop("tool", "")
            try:
                if tool == "create_region":
                    fill_for_style = op.get("fill_gradient") or op.get("fill")
                    r = self.create_region(
                        outline=op.pop("outline"),
                        region_id=op.get("region_id"),
                        document_id=doc_id,
                        layer=op.get("layer", "default"),
                        z_index=op.get("z_index", 0),
                        clip_to=op.get("clip_to"),
                        constraints=CurveConstraints(
                            smoothness=op.get("smoothness", 0.5),
                            closed=op.get("closed", True),
                            tensions=op.get("tensions") or op.get("smoothness_per_point"),
                        ),
                        style=Style(
                            fill=fill_for_style,
                            stroke=op.get("stroke"),
                            stroke_width=op.get("stroke_width", 0.005),
                            opacity=op.get("opacity", 1.0),
                            blend_mode=op.get("blend_mode"),
                            stroke_linecap=op.get("stroke_linecap"),
                        ),
                        metadata=op.get("metadata"),
                    )
                    results.append({"status": "ok", "region_id": r.id})
                elif tool == "create_shape":
                    shape = op.pop("shape", {})
                    stype = shape.get("type")
                    try:
                        if stype == "rect":
                            r = self.create_rect(
                                shape["x"], shape["y"], shape["width"], shape["height"],
                                rx=shape.get("rx", 0.0),
                                document_id=doc_id, region_id=op.get("region_id"),
                                layer=op.get("layer", "default"),
                                z_index=op.get("z_index", 0),
                                fill=op.get("fill", "#CCCCCC"),
                                stroke=op.get("stroke", "#333333"),
                                stroke_width=op.get("stroke_width", 0.005),
                                opacity=op.get("opacity", 1.0),
                                blend_mode=op.get("blend_mode"),
                                taper=shape.get("taper", 0.0),
                            )
                            results.append({"status": "ok", "region_id": r.id})
                        elif stype == "ellipse":
                            r = self.create_ellipse(
                                shape["cx"], shape["cy"], shape["rx"],
                                ry=shape.get("ry"),
                                document_id=doc_id, region_id=op.get("region_id"),
                                layer=op.get("layer", "default"),
                                z_index=op.get("z_index", 0),
                                fill=op.get("fill", "#CCCCCC"),
                                stroke=op.get("stroke", "#333333"),
                                stroke_width=op.get("stroke_width", 0.005),
                                opacity=op.get("opacity", 1.0),
                                blend_mode=op.get("blend_mode"),
                            )
                            results.append({"status": "ok", "region_id": r.id})
                        elif stype == "line":
                            pts = shape.get("points")
                            if pts is not None and len(pts) > 2:
                                r = self.create_line(
                                    points=pts,
                                    document_id=doc_id, region_id=op.get("region_id"),
                                    layer=op.get("layer", "default"),
                                    z_index=op.get("z_index", 0),
                                    stroke=op.get("stroke", "#333333"),
                                    stroke_width=op.get("stroke_width", 0.005),
                                    opacity=op.get("opacity", 1.0),
                                    blend_mode=op.get("blend_mode"),
                                    stroke_linecap=op.get("stroke_linecap"),
                                )
                            else:
                                r = self.create_line(
                                    shape.get("x1", 0.0), shape.get("y1", 0.0),
                                    shape.get("x2", 0.5), shape.get("y2", 0.5),
                                    document_id=doc_id, region_id=op.get("region_id"),
                                    layer=op.get("layer", "default"),
                                    z_index=op.get("z_index", 0),
                                    stroke=op.get("stroke", "#333333"),
                                    stroke_width=op.get("stroke_width", 0.005),
                                    opacity=op.get("opacity", 1.0),
                                    blend_mode=op.get("blend_mode"),
                                    stroke_linecap=op.get("stroke_linecap"),
                                )
                            results.append({"status": "ok", "region_id": r.id})
                        else:
                            results.append({"status": "error", "message": f"Unknown shape type: {stype}"})
                    except (ValueError, RuntimeError, KeyError) as e:
                        results.append({"status": "error", "message": str(e)})
                elif tool == "edit_region":
                    self.edit_region(
                        region_id=op.pop("region_id"),
                        document_id=doc_id,
                        outline=op.get("outline"),
                        fill=op.get("fill"),
                        stroke=op.get("stroke"),
                        stroke_width=op.get("stroke_width"),
                        opacity=op.get("opacity"),
                        z_index=op.get("z_index"),
                        blend_mode=op.get("blend_mode"),
                        clip_to=op.get("clip_to"),
                        layer=op.get("layer"),
                        metadata=op.get("metadata"),
                        shape=op.get("shape"),
                        stroke_linecap=op.get("stroke_linecap"),
                    )
                    results.append({"status": "ok"})
                elif tool == "duplicate_region":
                    d = self.duplicate_region(
                        region_id=op.pop("region_id"),
                        new_region_id=op.get("new_region_id"),
                        document_id=doc_id,
                        offset_x=op.get("offset_x", 0),
                        offset_y=op.get("offset_y", 0),
                        fill=op.get("fill"),
                        stroke=op.get("stroke"),
                        stroke_width=op.get("stroke_width"),
                        opacity=op.get("opacity"),
                        smoothness=op.get("smoothness"),
                        z_index=op.get("z_index"),
                        mirror_x=op.get("mirror_x", False),
                        mirror_y=op.get("mirror_y", False),
                        scale=op.get("scale", 1.0),
                        rotate=op.get("rotate", 0.0),
                    )
                    results.append({"status": "ok", "region_id": d.id})
                elif tool == "create_primitive":
                    # Alias — same logic as create_shape
                    shape = op.pop("shape", {})
                    stype = shape.get("type")
                    try:
                        if stype == "rect":
                            r = self.create_rect(
                                shape["x"], shape["y"], shape["width"], shape["height"],
                                rx=shape.get("rx", 0.0),
                                document_id=doc_id, region_id=op.get("region_id"),
                                layer=op.get("layer", "default"),
                                z_index=op.get("z_index", 0),
                                fill=op.get("fill", "#CCCCCC"),
                                stroke=op.get("stroke", "#333333"),
                                stroke_width=op.get("stroke_width", 0.005),
                                opacity=op.get("opacity", 1.0),
                                blend_mode=op.get("blend_mode"),
                                taper=shape.get("taper", 0.0),
                            )
                            results.append({"status": "ok", "region_id": r.id})
                        elif stype == "ellipse":
                            r = self.create_ellipse(
                                shape["cx"], shape["cy"], shape["rx"],
                                ry=shape.get("ry"),
                                document_id=doc_id, region_id=op.get("region_id"),
                                layer=op.get("layer", "default"),
                                z_index=op.get("z_index", 0),
                                fill=op.get("fill", "#CCCCCC"),
                                stroke=op.get("stroke", "#333333"),
                                stroke_width=op.get("stroke_width", 0.005),
                                opacity=op.get("opacity", 1.0),
                                blend_mode=op.get("blend_mode"),
                            )
                            results.append({"status": "ok", "region_id": r.id})
                        elif stype == "line":
                            pts = shape.get("points")
                            if pts is not None and len(pts) > 2:
                                r = self.create_line(
                                    points=pts,
                                    document_id=doc_id, region_id=op.get("region_id"),
                                    layer=op.get("layer", "default"),
                                    z_index=op.get("z_index", 0),
                                    stroke=op.get("stroke", "#333333"),
                                    stroke_width=op.get("stroke_width", 0.005),
                                    opacity=op.get("opacity", 1.0),
                                    blend_mode=op.get("blend_mode"),
                                    stroke_linecap=op.get("stroke_linecap"),
                                )
                            else:
                                r = self.create_line(
                                    shape.get("x1", 0.0), shape.get("y1", 0.0),
                                    shape.get("x2", 0.5), shape.get("y2", 0.5),
                                    document_id=doc_id, region_id=op.get("region_id"),
                                    layer=op.get("layer", "default"),
                                    z_index=op.get("z_index", 0),
                                    stroke=op.get("stroke", "#333333"),
                                    stroke_width=op.get("stroke_width", 0.005),
                                    opacity=op.get("opacity", 1.0),
                                    blend_mode=op.get("blend_mode"),
                                    stroke_linecap=op.get("stroke_linecap"),
                                )
                            results.append({"status": "ok", "region_id": r.id})
                        else:
                            results.append({"status": "error", "message": f"Unknown shape type: {stype}"})
                    except (ValueError, RuntimeError, KeyError) as e:
                        results.append({"status": "error", "message": str(e)})
                elif tool == "create_curve":
                    pts = op.pop("points", [])
                    if len(pts) < 2:
                        results.append({"status": "error", "message": "Need at least 2 points"})
                    else:
                        try:
                            r = self.create_line(
                                points=pts,
                                document_id=doc_id, region_id=op.get("region_id"),
                                layer=op.get("layer", "default"),
                                z_index=op.get("z_index", 0),
                                stroke=op.get("stroke", "#333333"),
                                stroke_width=op.get("stroke_width", 0.005),
                                opacity=op.get("opacity", 1.0),
                                blend_mode=op.get("blend_mode"),
                                stroke_linecap=op.get("stroke_linecap", "round"),
                                stroke_dasharray=op.get("stroke_dasharray"),
                                smoothness=op.get("smoothness", 0.5),
                            )
                            results.append({"status": "ok", "region_id": r.id})
                        except (ValueError, RuntimeError) as e:
                            results.append({"status": "error", "message": str(e)})
                elif tool == "delete_region":
                    self.delete_region(region_id=op.pop("region_id"), document_id=doc_id)
                    results.append({"status": "ok"})
                elif tool == "style_objects":
                    batch_ids = op.pop("ids", None)
                    batch_grp = op.get("group_name")
                    if batch_grp:
                        members = self.get_group(batch_grp, doc_id)
                        if members:
                            batch_ids = [m["id"] for m in members]
                    if batch_ids:
                        affected = self.style_objects(
                            ids=batch_ids,
                            document_id=doc_id,
                            fill=op.get("fill"),
                            stroke=op.get("stroke"),
                            stroke_width=op.get("stroke_width"),
                            opacity=op.get("opacity"),
                            fill_gradient=op.get("fill_gradient"),
                            blend_mode=op.get("blend_mode"),
                            clip_to=op.get("clip_to"),
                            stroke_linecap=op.get("stroke_linecap"),
                        )
                        results.append({"status": "ok", "affected": len(affected)})
                    else:
                        results.append({"status": "error", "message": "no ids or group resolved"})
                elif tool == "transform_objects":
                    affected = self.transform_objects(
                        ids=op.pop("ids"),
                        document_id=doc_id,
                        dx=op.get("dx", 0.0),
                        dy=op.get("dy", 0.0),
                        scale=op.get("scale", 1.0),
                        sx=op.get("sx"),
                        sy=op.get("sy"),
                        rotate=op.get("rotate", 0.0),
                        group_mode=op.get("group_mode", False),
                    )
                    results.append({"status": "ok", "affected": len(affected)})
                elif tool == "create_text":
                    try:
                        r = self.create_text(
                            x=op.pop("x", 0.5),
                            y=op.pop("y", 0.5),
                            text=op.pop("text", ""),
                            document_id=doc_id,
                            region_id=op.get("region_id"),
                            layer=op.get("layer", "default"),
                            z_index=op.get("z_index", 0),
                            fill=op.get("fill", "#333333"),
                            font_size=op.get("font_size", 0.04),
                            font_family=op.get("font_family", "sans-serif"),
                            text_anchor=op.get("text_anchor", "middle"),
                            font_weight=op.get("font_weight", "normal"),
                            rotate=op.get("rotate", 0.0),
                        )
                        results.append({"status": "ok", "region_id": r.id})
                    except (ValueError, RuntimeError) as e:
                        results.append({"status": "error", "message": str(e)})
                elif tool == "import_svg_path":
                    try:
                        from avge_engine.geometry.procedural import parse_svg_path
                        outline = parse_svg_path(
                            op.pop("path_data", ""),
                            samples_per_curve=op.get("samples_per_curve", 12),
                        )
                        if outline and len(outline) >= 2:
                            fill_for_style = op.get("fill_gradient") or op.get("fill", "#CCCCCC")
                            r = self.create_region(
                                outline=outline,
                                region_id=op.get("region_id"),
                                document_id=doc_id,
                                layer=op.get("layer", "default"),
                                z_index=op.get("z_index", 0),
                                constraints=CurveConstraints(
                                    smoothness=op.get("smoothness", 0.0),
                                    closed=op.get("closed", True),
                                ),
                                style=Style(
                                    fill=fill_for_style,
                                    stroke=op.get("stroke", "#333333"),
                                    stroke_width=op.get("stroke_width", 0.005),
                                ),
                            )
                            results.append({"status": "ok", "region_id": r.id})
                        else:
                            results.append({"status": "error", "message": "Could not parse SVG path data"})
                    except (ValueError, RuntimeError) as e:
                        results.append({"status": "error", "message": str(e)})
                elif tool == "insert_image":
                    try:
                        r = self.insert_image(
                            x=op.pop("x", 0.0), y=op.pop("y", 0.0),
                            width=op.pop("width", 0.5), height=op.pop("height", 0.5),
                            href=op.pop("href", ""),
                            document_id=doc_id,
                            region_id=op.get("region_id"),
                            layer=op.get("layer", "default"),
                            z_index=op.get("z_index", 0),
                            preserve_aspect_ratio=op.get("preserve_aspect_ratio", "xMidYMid meet"),
                            rotate=op.get("rotate", 0.0),
                        )
                        results.append({"status": "ok", "region_id": r.id})
                    except (ValueError, RuntimeError) as e:
                        results.append({"status": "error", "message": str(e)})
                elif tool == "generate_shape":
                    try:
                        from avge_engine.geometry import procedural as geo
                        pattern = op.pop("pattern", "")
                        params = op.pop("params", {})
                        if pattern == "offset_outline":
                            region_id_g = params.get("region_id")
                            if region_id_g and self.has_region(region_id_g, doc_id):
                                region = self.get_region(region_id_g, doc_id)
                                outline = geo.offset_outline(region.outline, distance=params.get("distance", 0.02))
                                if outline:
                                    r = self.create_region(
                                        outline=outline,
                                        document_id=doc_id,
                                        constraints=CurveConstraints(smoothness=region.constraints.smoothness, closed=True),
                                        style=Style(
                                            fill=params.get("fill", region.style.fill),
                                            stroke=params.get("stroke", region.style.stroke),
                                            stroke_width=params.get("stroke_width", region.style.stroke_width),
                                        ),
                                    )
                                    results.append({"status": "ok", "region_id": r.id})
                                else:
                                    results.append({"status": "error", "message": "offset produced degenerate outline"})
                            else:
                                results.append({"status": "error", "message": "region_id required for offset_outline"})
                        elif pattern == "distribute_linear":
                            pts = geo.distribute_linear(
                                start=params.get("start", (0, 0)),
                                end=params.get("end", (1, 1)),
                                count=params.get("count", 5),
                            )
                            results.append({"status": "ok", "points": pts})
                        elif pattern == "apex_from_edge":
                            region_id_g = params.get("region_id")
                            if region_id_g and self.has_region(region_id_g, doc_id):
                                region = self.get_region(region_id_g, doc_id)
                                triangle = geo.apex_from_edge(
                                    region.outline, edge=params.get("edge", "top"),
                                    apex_offset=params.get("apex_offset"),
                                    inset=params.get("inset", 0.0),
                                )
                                if triangle:
                                    r = self.create_region(
                                        outline=triangle,
                                        document_id=doc_id,
                                        constraints=CurveConstraints(smoothness=0.0, closed=True),
                                        style=Style(
                                            fill=params.get("fill", region.style.fill),
                                            stroke=params.get("stroke", region.style.stroke),
                                            stroke_width=params.get("stroke_width", region.style.stroke_width),
                                        ),
                                    )
                                    results.append({"status": "ok", "region_id": r.id})
                                else:
                                    results.append({"status": "error", "message": "apex produced degenerate triangle"})
                            else:
                                results.append({"status": "error", "message": "region_id required for apex_from_edge"})
                        else:
                            results.append({"status": "error", "message": f"Unsupported batch pattern: {pattern}"})
                    except (ValueError, RuntimeError, KeyError) as e:
                        results.append({"status": "error", "message": str(e)})
                else:
                    results.append({"status": "error", "message": f"Unknown tool: {tool}"})
            except (ValueError, RuntimeError) as e:
                results.append({"status": "error", "message": str(e)})
            finally:
                op["tool"] = tool  # restore
        return results

    # ── Edit region ────────────────────────────────────────────────

    def edit_region(
        self,
        region_id: str,
        document_id: str | None = None,
        *,
        outline: list[Point2D] | None = None,
        smoothness: float | None = None,
        tensions: tuple[float, ...] | None = None,
        handle_in: tuple[tuple[float, float], ...] | None = None,
        handle_out: tuple[tuple[float, float], ...] | None = None,
        fill: str | GradientDef | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        z_index: int | None = None,
        clip_to: str | None = None,
        blend_mode: str | None = None,
        layer: str | None = None,
        metadata: dict[str, Any] | None = None,
        shape: dict | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
    ) -> bool:
        """Modify an existing region's properties. Only provided fields are changed."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        region = regions.get(region_id)
        if region is None:
            raise ValueError(f"Region '{region_id}' not found")
        if shape is not None:
            # Update primitive shape and its surrogate outline
            stype = shape.get("type")
            if stype == "rect":
                x, y = shape["x"], shape["y"]
                w, h = shape["width"], shape["height"]
                rx = shape.get("rx", 0.0)
                max_rx = min(w, h) / 2
                region.primitive = {"type": "rect", "x": x, "y": y, "width": w, "height": h, "rx": max(0.0, min(rx, max_rx))}
                region.outline = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            elif stype == "ellipse":
                cx, cy = shape["cx"], shape["cy"]
                rx = shape["rx"]
                ry = shape.get("ry", rx)
                if rx <= 0 or ry <= 0:
                    raise ValueError("rx and ry must be positive")
                region.primitive = {"type": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry}
                region.outline = [(cx - rx, cy - ry), (cx + rx, cy + ry)]
            elif stype == "line":
                x1, y1 = shape["x1"], shape["y1"]
                x2, y2 = shape["x2"], shape["y2"]
                region.primitive = {"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2}
                region.outline = [(x1, y1), (x2, y2)]
            else:
                raise ValueError(f"Unknown shape type: {stype}")
        if outline is not None:
            region.outline = normalize_outline(outline)
        if smoothness is not None or tensions is not None or handle_in is not None or handle_out is not None:
            old_c = region.constraints
            region.constraints = CurveConstraints(
                smoothness=smoothness if smoothness is not None else old_c.smoothness,
                closed=old_c.closed,
                corner_style=old_c.corner_style,
                tensions=tensions if tensions is not None else old_c.tensions,
                handle_in=handle_in if handle_in is not None else old_c.handle_in,
                handle_out=handle_out if handle_out is not None else old_c.handle_out,
            )
        if fill is not None or stroke is not None or stroke_width is not None or opacity is not None or blend_mode is not None or stroke_linecap is not None or stroke_dasharray is not None:
            old_s = region.style
            region.style = Style(
                fill=fill if fill is not None else old_s.fill,
                stroke=stroke if stroke is not None else old_s.stroke,
                stroke_width=stroke_width if stroke_width is not None else old_s.stroke_width,
                opacity=opacity if opacity is not None else old_s.opacity,
                blend_mode=blend_mode if blend_mode is not None else old_s.blend_mode,
                stroke_linecap=stroke_linecap if stroke_linecap is not None else old_s.stroke_linecap,
                stroke_dasharray=stroke_dasharray if stroke_dasharray is not None else old_s.stroke_dasharray,
            )
        if z_index is not None:
            region.z_index = z_index
        if clip_to is not None:
            region.clip_to = clip_to
        if layer is not None:
            region.layer = layer
        if metadata is not None:
            region.metadata.update(metadata)
        region.version += 1
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "edit_region", region_id)
        self._persist(doc_id)
        return True

    # ── Duplicate region ──────────────────────────────────────────────

    def duplicate_region(
        self,
        region_id: str,
        new_region_id: str | None = None,
        document_id: str | None = None,
        *,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        z_index: int | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        smoothness: float | None = None,
        mirror_x: bool = False,
        mirror_y: bool = False,
        mirror_axis_x: float | None = None,
        blend_mode: str | None = None,
        layer: str | None = None,
        scale: float = 1.0,
        rotate: float = 0.0,
        shadow_mode: bool = False,
    ) -> RegionNode:
        """Duplicate a region with optional offset and overrides.

        When ``mirror_x`` or ``mirror_y`` is True, the outline is flipped
        around the original region's center before offset is applied.
        ``mirror_axis_x`` overrides the mirror axis to a fixed x position
        (e.g. 0.5 = canvas center) rather than the region's own center.
        ``scale`` and ``rotate`` apply uniform scale and rotation around
        the original region's center before offset.

        When ``shadow_mode`` is True (default False), the copy is
        automatically styled as a cel-shadow: fill is darkened via HSL,
        stroke is removed, and z_index is placed behind the original.
        Explicit ``fill``, ``stroke``, or ``z_index`` override auto values.
        """
        import math
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        original = regions.get(region_id)
        if original is None:
            raise ValueError(f"Region '{region_id}' not found")
        rid = new_region_id or f"{region_id}_copy"
        if rid in regions:
            raise ValueError(f"Region '{rid}' already exists")

        cx = sum(p[0] for p in original.outline) / len(original.outline)
        cy = sum(p[1] for p in original.outline) / len(original.outline)

        # When mirror_axis_x is set, mirror around that axis instead of own center
        if mirror_x and mirror_axis_x is not None:
            offset_x = offset_x + 2 * (mirror_axis_x - cx)

        angle = math.radians(rotate)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        new_outline = []
        for x, y in original.outline:
            # Mirror around center
            nx = (2 * cx - x) if mirror_x else x
            ny = (2 * cy - y) if mirror_y else y
            # Scale around center
            sx_val = (nx - cx) * scale + cx
            sy_val = (ny - cy) * scale + cy
            # Rotate around center
            rx = (sx_val - cx) * cos_a - (sy_val - cy) * sin_a + cx
            ry = (sx_val - cx) * sin_a + (sy_val - cy) * cos_a + cy
            # Translate
            new_outline.append((rx + offset_x, ry + offset_y))
        # Auto-compute shadow styling when shadow_mode is active
        if shadow_mode and fill is None:
            orig_fill = original.style.fill
            if isinstance(orig_fill, str) and orig_fill.startswith("#"):
                from avge_engine.effects.color import darken_hex
                new_fill = darken_hex(orig_fill)
            else:
                new_fill = orig_fill  # gradients pass through
        else:
            new_fill = fill if fill is not None else original.style.fill
        new_stroke = stroke
        if shadow_mode and stroke is None:
            new_stroke = None  # remove stroke on shadows
        elif stroke is not None:
            new_stroke = stroke
        else:
            new_stroke = original.style.stroke
        if shadow_mode and z_index is None:
            new_z = original.z_index - 1  # place behind original
        else:
            new_z = z_index if z_index is not None else original.z_index + 1
        new_constraints = original.constraints
        if smoothness is not None:
            new_constraints = CurveConstraints(
                smoothness=smoothness,
                closed=original.constraints.closed,
                corner_style=original.constraints.corner_style,
            )
        new_style_obj = Style(
            fill=new_fill,
            stroke=new_stroke,
            stroke_width=stroke_width if stroke_width is not None else original.style.stroke_width,
            opacity=opacity if opacity is not None else original.style.opacity,
            blend_mode=blend_mode if blend_mode is not None else original.style.blend_mode,
        )
        # Preserve primitive if possible (update coords for mirror/scale/rotate)
        new_primitive = None
        if original.primitive:
            p = original.primitive
            copy_p = dict(p)
            simple_transform = (abs(scale - 1) <= 0.001 and abs(rotate) <= 0.001)
            if simple_transform and (mirror_x or mirror_y):
                # Mirror ellipse/rect primitives by flipping their center point.
                # offset_x/y must be applied so the primitive matches the outline
                # after the offset that duplicate_region applies post-mirror.
                if copy_p.get("type") == "ellipse":
                    new_cx = copy_p["cx"]
                    new_cy = copy_p["cy"]
                    if mirror_x:
                        new_cx = 2 * cx - new_cx + offset_x
                    if mirror_y:
                        new_cy = 2 * cy - new_cy + offset_y
                    copy_p["cx"] = new_cx
                    copy_p["cy"] = new_cy
                    new_primitive = copy_p
                elif copy_p.get("type") in ("text", "image"):
                    if mirror_x:
                        copy_p["x"] = 2 * cx - copy_p["x"] + offset_x
                    if mirror_y:
                        copy_p["y"] = 2 * cy - copy_p["y"] + offset_y
                    if not mirror_x:
                        copy_p["x"] += offset_x
                    if not mirror_y:
                        copy_p["y"] += offset_y
                    new_primitive = copy_p
                elif copy_p.get("type") == "rect":
                    if mirror_x:
                        orig_right = copy_p["x"] + copy_p["width"]
                        copy_p["x"] = 2 * cx - orig_right + offset_x
                    if mirror_y:
                        orig_bottom = copy_p["y"] + copy_p["height"]
                        copy_p["y"] = 2 * cy - orig_bottom + offset_y
                    if not mirror_x:
                        copy_p["x"] += offset_x
                    if not mirror_y:
                        copy_p["y"] += offset_y
                    new_primitive = copy_p
            elif not mirror_x and not mirror_y and abs(scale - 1) <= 0.001 and abs(rotate) <= 0.001:
                # Pure translation — update coords
                if copy_p.get("type") == "ellipse":
                    copy_p["cx"] += offset_x
                    copy_p["cy"] += offset_y
                    new_primitive = copy_p
                elif copy_p.get("type") == "rect":
                    copy_p["x"] += offset_x
                    copy_p["y"] += offset_y
                    new_primitive = copy_p
                elif copy_p.get("type") == "line":
                    copy_p["x1"] += offset_x
                    copy_p["y1"] += offset_y
                    copy_p["x2"] += offset_x
                    copy_p["y2"] += offset_y
                    new_primitive = copy_p
                elif copy_p.get("type") in ("text", "image"):
                    copy_p["x"] += offset_x
                    copy_p["y"] += offset_y
                    new_primitive = copy_p

        dup = RegionNode(
            id=rid,
            layer=layer if layer is not None else original.layer,
            z_index=new_z,
            outline=new_outline,
            constraints=new_constraints,
            style=new_style_obj,
            transform=original.transform,
            primitive=new_primitive,
        )
        regions[rid] = dup
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "duplicate_region", f"{region_id}->{rid}")
        self._persist(doc_id)
        return dup

    # ── Primitive shape operations ──────────────────────────────────

    def create_rect(
        self,
        x: float, y: float,
        width: float, height: float,
        rx: float = 0.0,
        *,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | GradientDef | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        blend_mode: str | None = None,
        taper: float = 0.0,
        rotate: float = 0.0,
    ) -> RegionNode:
        """Create a rectangle (or rounded rect) region — renders as SVG <rect>.

        When ``taper`` is non-zero, the rect becomes a trapezoid (rendered as
        a path-based region rather than an SVG primitive). Positive taper =
        top narrower than base (e.g. finger shape). Negative taper = top wider.
        """
        import uuid, math
        doc_id = self._resolve_doc(document_id)
        rid = region_id or f"rect_{uuid.uuid4().hex[:6]}"
        max_rx = min(width, height) / 2
        rx_clamped = max(0.0, min(rx, max_rx))
        cx = x + width / 2
        top_w = width * (1.0 - max(-1.0, min(1.0, taper)))
        # ── Tapered path ──────────────────────────────────────────
        if abs(taper) > 0.001:
            # 6-point polygon for tapered pill shape
            top_x1 = cx - top_w / 2
            top_x2 = cx + top_w / 2
            bot_x1 = x
            bot_x2 = x + width
            surr = [
                (bot_x1, y + height),          # base-left
                (bot_x2, y + height),          # base-right
                (bot_x2, y),                   # top-right outer
                (top_x2, y),                   # top-right
                (cx, y - height * 0.08),        # top-center (slight dome)
                (top_x1, y),                   # top-left
            ]
            region = RegionNode(
                id=rid, layer=layer, z_index=z_index,
                outline=surr,
                constraints=CurveConstraints(smoothness=0.35, closed=True),
                style=Style(fill=fill, stroke=stroke, stroke_width=max(0.001, min(0.1, stroke_width)),
                            opacity=max(0.0, min(1.0, opacity)), blend_mode=blend_mode),
                primitive=None,
            )
        else:
            surr = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
            region = RegionNode(
                id=rid, layer=layer, z_index=z_index,
                outline=surr,
                constraints=CurveConstraints(smoothness=0.0, closed=True),
                style=Style(fill=fill, stroke=stroke, stroke_width=max(0.001, min(0.1, stroke_width)),
                            opacity=max(0.0, min(1.0, opacity)), blend_mode=blend_mode),
                primitive={"type": "rect", "x": x, "y": y, "width": width, "height": height, "rx": rx_clamped},
            )
        if abs(rotate) > 0.001:
            object.__setattr__(region.transform, "rotate", rotate)
        self._regions_for(doc_id)[rid] = region
        region.version += 1
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "create_rect", rid)
        self._persist(doc_id)
        return region

    def create_ellipse(
        self,
        cx: float, cy: float,
        rx: float, ry: float | None = None,
        *,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | GradientDef | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        blend_mode: str | None = None,
        rotate: float = 0.0,
    ) -> RegionNode:
        """Create an ellipse (or circle) region — renders as SVG <ellipse>."""
        import uuid
        doc_id = self._resolve_doc(document_id)
        rid = region_id or f"ellipse_{uuid.uuid4().hex[:6]}"
        ry_val = ry if ry is not None else rx
        if rx <= 0 or ry_val <= 0:
            raise ValueError("rx and ry must be positive")
        surr = [(cx - rx, cy - ry_val), (cx + rx, cy + ry_val)]
        region = RegionNode(
            id=rid, layer=layer, z_index=z_index,
            outline=surr,
            constraints=CurveConstraints(smoothness=0.0, closed=True),
            style=Style(fill=fill, stroke=stroke, stroke_width=max(0.001, min(0.1, stroke_width)),
                        opacity=max(0.0, min(1.0, opacity)), blend_mode=blend_mode),
            primitive={"type": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry_val},
        )
        self._regions_for(doc_id)[rid] = region
        region.version += 1
        if abs(rotate) > 0.001:
            object.__setattr__(region.transform, "rotate", rotate)
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "create_ellipse", rid)
        self._persist(doc_id)
        return region

    def create_line(
        self,
        x1: float = 0.0, y1: float = 0.0,
        x2: float = 1.0, y2: float = 1.0,
        *,
        document_id: str | None = None,
        points: list[list[float]] | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        blend_mode: str | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        smoothness: float | None = None,
        rotate: float = 0.0,
    ) -> RegionNode:
        """Create a line/stroke region — renders as SVG <line> or path-based polyline.

        Use ``points`` for multi-segment lines (3+ points) that curve through
        Catmull-Rom interpolation. When ``points`` has 2 entries, a simple
        SVG <line> primitive is used. When 3+, a path-based open curve is created.
        """
        import uuid
        doc_id = self._resolve_doc(document_id)
        rid = region_id or f"line_{uuid.uuid4().hex[:6]}"

        if points is not None and len(points) > 2:
            # Multi-point polyline — path-based with smoothness
            surr = [(float(p[0]), float(p[1])) for p in points]
            curve_smoothness = smoothness if smoothness is not None else 0.35
            region = RegionNode(
                id=rid, layer=layer, z_index=z_index,
                outline=surr,
                constraints=CurveConstraints(smoothness=curve_smoothness, closed=False),
                style=Style(fill=None, stroke=stroke, stroke_width=max(0.001, min(0.1, stroke_width)),
                            opacity=max(0.0, min(1.0, opacity)), blend_mode=blend_mode,
                            stroke_linecap=stroke_linecap, stroke_dasharray=stroke_dasharray),
                primitive=None,
            )
        else:
            surr = [(x1, y1), (x2, y2)]
            region = RegionNode(
                id=rid, layer=layer, z_index=z_index,
                outline=surr,
                constraints=CurveConstraints(smoothness=0.0, closed=False),
                style=Style(fill=None, stroke=stroke, stroke_width=max(0.001, min(0.1, stroke_width)),
                            opacity=max(0.0, min(1.0, opacity)), blend_mode=blend_mode,
                            stroke_linecap=stroke_linecap, stroke_dasharray=stroke_dasharray),
                primitive={"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2},
            )
        self._regions_for(doc_id)[rid] = region
        region.version += 1
        if abs(rotate) > 0.001:
            object.__setattr__(region.transform, "rotate", rotate)
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "create_line", rid)
        self._persist(doc_id)
        return region

    def create_text(
        self,
        x: float, y: float,
        text: str,
        *,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | GradientDef | None = "#333333",
        font_size: float = 0.04,
        font_family: str = "sans-serif",
        text_anchor: str = "middle",
        font_weight: str = "normal",
        font_style: str = "normal",
        rotate: float = 0.0,
        letter_spacing: float = 0.0,
        opacity: float = 1.0,
    ) -> RegionNode:
        """Create a text label — renders as SVG <text>.

        Coordinates are in normalized 0.0–1.0 space. ``y`` is the text
        *baseline* (not the center). ``text_anchor`` controls horizontal
        alignment. Font size is relative to canvas height (0.04 = 4% of height).
        """
        import uuid
        doc_id = self._resolve_doc(document_id)
        rid = region_id or f"text_{uuid.uuid4().hex[:6]}"

        region = RegionNode(
            id=rid, layer=layer, z_index=z_index,
            outline=[(x, y)],
            constraints=CurveConstraints(smoothness=0.0, closed=False),
            style=Style(fill=fill, stroke=None),
            primitive={
                "type": "text", "x": x, "y": y, "text": text,
                "font_size": font_size, "font_family": font_family,
                "text_anchor": text_anchor, "font_weight": font_weight, "font_style": font_style,
                "letter_spacing": letter_spacing if letter_spacing else None,
                "opacity": opacity if opacity < 1.0 else None,
            },
        )
        if abs(rotate) > 0.001:
            object.__setattr__(region.transform, "rotate", rotate)
        self._regions_for(doc_id)[rid] = region
        region.version += 1
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "create_text", rid)
        self._persist(doc_id)
        return region


    def insert_image(
        self,
        x: float, y: float,
        width: float, height: float,
        href: str,
        *,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        preserve_aspect_ratio: str = "xMidYMid meet",
        rotate: float = 0.0,
    ) -> RegionNode:
        """Create an image region — renders as SVG <image>.

        Args:
            x, y: Top-left corner in normalized space.
            width, height: Dimensions in normalized space.
            href: Image URL, data URI, or path.
            document_id: Document UUID.
            region_id: Optional unique ID.
            layer: Layer name.
            z_index: Paint order.
            preserve_aspect_ratio: SVG preserveAspectRatio value.
            rotate: Rotation in degrees around image center.
        """
        import uuid
        doc_id = self._resolve_doc(document_id)
        rid = region_id or f"img_{uuid.uuid4().hex[:6]}"

        region = RegionNode(
            id=rid, layer=layer, z_index=z_index,
            outline=[(x, y), (x + width, y), (x + width, y + height), (x, y + height)],
            constraints=CurveConstraints(smoothness=0.0, closed=True),
            style=Style(fill=None, stroke=None),
            primitive={
                "type": "image", "x": x, "y": y,
                "width": width, "height": height,
                "href": href,
                "preserve_aspect_ratio": preserve_aspect_ratio,
            },
        )
        if abs(rotate) > 0.001:
            object.__setattr__(region.transform, "rotate", rotate)
        self._regions_for(doc_id)[rid] = region
        region.version += 1
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "create_image", rid)
        self._persist(doc_id)
        return region

    # ── Style operations ────────────────────────────────────────────

    def style_objects(
        self,
        ids: list[str],
        document_id: str | None = None,
        *,
        fill: str | GradientDef | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        fill_gradient: str | dict | None = None,
        blend_mode: str | None = None,
        clip_to: str | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        fill_hsl_offset: dict | None = None,
        stroke_hsl_offset: dict | None = None,
    ) -> list[str]:
        """Update style on existing regions. Returns list of actually updated IDs."""
        doc_id = self._resolve_doc(document_id)
        doc = self.get_document(doc_id)
        regions = self._regions_for(doc_id)
        affected: list[str] = []
        for rid in ids:
            region = regions.get(rid)
            if region is None:
                continue
            old = region.style
            # Resolve fill — explicit fill/fill_gradient takes precedence over HSL
            resolved_fill = fill
            if fill_gradient is not None:
                if isinstance(fill_gradient, str):
                    import json
                    try:
                        resolved_fill = json.loads(fill_gradient)
                    except json.JSONDecodeError:
                        resolved_fill = fill_gradient
                else:
                    resolved_fill = fill_gradient
            elif fill is not None:
                resolved_fill = fill
            elif fill_hsl_offset is not None and isinstance(old.fill, str) and old.fill.startswith("#"):
                from avge_engine.effects.color import apply_hsl_offset
                resolved_fill = apply_hsl_offset(
                    old.fill,
                    h_offset=fill_hsl_offset.get("h", 0),
                    s_offset=fill_hsl_offset.get("s", 0),
                    l_offset=fill_hsl_offset.get("l", 0),
                )
            # Resolve stroke — explicit stroke takes precedence over HSL
            resolved_stroke = stroke
            if stroke is None and stroke_hsl_offset is not None and isinstance(old.stroke, str) and old.stroke.startswith("#"):
                from avge_engine.effects.color import apply_hsl_offset
                resolved_stroke = apply_hsl_offset(
                    old.stroke,
                    h_offset=stroke_hsl_offset.get("h", 0),
                    s_offset=stroke_hsl_offset.get("s", 0),
                    l_offset=stroke_hsl_offset.get("l", 0),
                )
            new_style = Style(
                fill=resolved_fill if resolved_fill is not None else old.fill,
                stroke=stroke if stroke is not None else old.stroke,
                stroke_width=stroke_width if stroke_width is not None else old.stroke_width,
                opacity=opacity if opacity is not None else old.opacity,
                blend_mode=blend_mode if blend_mode is not None else old.blend_mode,
                stroke_linecap=stroke_linecap if stroke_linecap is not None else old.stroke_linecap,
                stroke_dasharray=stroke_dasharray if stroke_dasharray is not None else old.stroke_dasharray,
            )
            region.style = new_style
            if clip_to is not None:
                region.clip_to = clip_to
            region.version += 1
            affected.append(rid)
        doc.version += 1
        self._auto_checkpoint(doc_id, "style_objects", str(affected))
        self._persist(doc_id)
        return affected

    # ── Scene description ───────────────────────────────────────────

    def describe_scene(
        self,
        document_id: str | None = None,
        detail: str = "summary",
        filter_layer: str | None = None,
    ) -> dict[str, Any]:
        doc_id = self._resolve_doc(document_id)
        doc = self.get_document(doc_id)
        regions = self._regions_for(doc_id)
        region_list: list[dict[str, Any]] = []

        for r in regions.values():
            if filter_layer and r.layer != filter_layer:
                continue
            entry: dict[str, Any] = {
                "id": r.id,
                "type": r.type,
                "layer": r.layer,
                "z_index": r.z_index,
                "clip_to": r.clip_to,
                "outline_point_count": len(r.outline),
                "closed": r.constraints.closed,
                "smoothness": r.constraints.smoothness,
                "style": {
                    "fill": r.style.fill,
                    "stroke": r.style.stroke,
                    "stroke_width": r.style.stroke_width,
                    "opacity": r.style.opacity,
                    "blend_mode": r.style.blend_mode,
                },
                "bounds": compute_bounds(r.outline),
                "version": r.version,
                "metadata": r.metadata if r.metadata else None,
            }
            if detail == "full":
                entry["outline"] = r.outline
            region_list.append(entry)

        warnings = self._compute_warnings(document_id)
        smoothness_notes = self._compute_smoothness_notes(document_id)

        # Collect color palette — unique fill and stroke hex values
        fills: set[str] = set()
        strokes: set[str] = set()
        for r in regions.values():
            if isinstance(r.style.fill, str) and r.style.fill.startswith("#"):
                fills.add(r.style.fill.upper())
            if isinstance(r.style.stroke, str) and r.style.stroke.startswith("#"):
                strokes.add(r.style.stroke.upper())

        return {
            "document": {
                "id": doc.id,
                "name": doc.name,
                "width": doc.width,
                "height": doc.height,
                "unit": doc.unit,
                "background": doc.background,
                "version": doc.version,
            },
            "regions": region_list,
            "region_count": len(region_list),
            "palette": {
                "fills": sorted(fills) if fills else [],
                "strokes": sorted(strokes) if strokes else [],
            },
            "warnings": warnings + smoothness_notes,
        }

    def _compute_warnings(self, document_id: str) -> list[str]:
        doc_id = self._resolve_doc(document_id)
        doc = self.get_document(doc_id)
        regions = self._regions_for(doc_id)
        warnings: list[str] = []
        for r in regions.values():
            b = compute_bounds(r.outline)
            if b and (b["x"] + b["w"] < 0 or b["x"] > 1.0 or b["y"] + b["h"] < 0 or b["y"] > 1.0):
                warnings.append(f"Region '{r.id}' is entirely off-canvas")
        return warnings

    def _compute_smoothness_notes(self, document_id: str | None = None) -> list[str]:
        regions = self._regions_for(self._resolve_doc(document_id))
        notes: list[str] = []
        for r in regions.values():
            n = len(r.outline)
            s = r.constraints.smoothness
            if n >= 20 and s <= 0.1:
                notes.append(
                    f"Region '{r.id}': {n} points with smoothness={s:.1f} "
                    f"(many points + sharp corners may produce jagged output; "
                    f"consider increasing smoothness or reducing point count)"
                )
        return notes

    # ── Tool usage tracking ────────────────────────────────────

    def track_op(self, document_id: str | None, tool: str) -> None:
        """Record a tool call for the given document."""
        doc_id = self._resolve_doc(document_id) if document_id else self._last_doc_id
        if doc_id:
            self.tool_stats.track_call(doc_id, tool)

    def get_doc_stats(self, document_id: str | None = None) -> dict:
        """Return tool call counts for a document."""
        doc_id = self._resolve_doc(document_id)
        calls = self.tool_stats.get_doc_calls(doc_id)
        return {
            "document_id": doc_id,
            "tool_calls": calls,
            "total_calls": sum(calls.values()),
        }

    # ── Reset (for tests) ───────────────────────────────────────────

    def reset(self) -> None:
        """Clear all state."""
        self._docs.clear()
        self._regions_by_doc.clear()
        self._checkpoints.clear()
        self._checkpoint_meta.clear()
        self._auto_counter = 0
        self._last_doc_id = None

    # ── Checkpoint / Restore ────────────────────────────────────────

    def _auto_checkpoint(self, doc_id: str, action: str, detail: str = ""):
        """Auto-save checkpoint with metadata after every mutation."""
        if not self._auto_enabled:
            return
        self._auto_counter += 1
        ts = __import__("datetime").datetime.now().strftime("%H:%M:%S")
        name = f"auto_{self._auto_counter:03d}"
        doc = self._docs.get(doc_id)
        regions = self._regions_by_doc.get(doc_id, {})
        snap_key = f"{doc_id}::{name}"
        self._checkpoints[snap_key] = (copy.deepcopy(doc), copy.deepcopy(regions))
        self._checkpoint_meta[snap_key] = {
            "name": name, "time": ts, "action": action,
            "detail": detail, "region_count": str(len(regions)),
        }

    def checkpoint(self, document_id: str, name: str = "default") -> str:
        """Save a snapshot of document state."""
        doc_id = self._resolve_doc(document_id)
        doc = self.get_document(doc_id)
        regions = self._regions_for(doc_id)
        snap_key = f"{document_id}::{name}"
        self._checkpoints[snap_key] = (copy.deepcopy(doc), copy.deepcopy(regions))
        return name

    def restore(self, document_id: str, name: str = "default") -> bool:
        """Restore document state from a named checkpoint."""
        snap_key = f"{document_id}::{name}"
        snap = self._checkpoints.get(snap_key)
        if snap is None:
            return False
        restored_doc, restored_regions = copy.deepcopy(snap)
        self._docs[document_id] = restored_doc
        self._regions_by_doc[document_id] = restored_regions
        self._persist(document_id)
        return True

    def list_checkpoints(self, document_id: str | None = None) -> list[str]:
        """Return available checkpoint names for a document."""
        prefix = f"{document_id}::"
        return [k[len(prefix):] for k in self._checkpoints if k.startswith(prefix)]

    # ── Extrude region outline ────────────────────────────────────

    def extrude_region_outline(
        self,
        region_id: str,
        document_id: str | None = None,
        *,
        segment_indices: list[int] | None = None,
        extrusion_length: float = 0.03,
        extrusion_width: float = 0.02,
        angle_offset: float = 0.0,
        direction: str = "outward",
        shape: str = "round",
    ) -> bool:
        """Add protrusions or notches at specified segments of a region's outline.

        Each segment index refers to the edge between ``outline[i]`` and
        ``outline[(i+1) % n]``. The extrusion adds points offset from the
        segment midpoint, controlled by direction and shape.

        Args:
            region_id: Region to modify.
            document_id: Document UUID.
            segment_indices: List of segment indices to extrude.
                If None, every segment gets a slight extrusion (rough edge).
            extrusion_length: How far the bump protrudes (normalized units).
            extrusion_width: How wide the bump base is (normalized units).
            angle_offset: Angular offset in degrees to skew the extrusion direction.
            direction: "outward" (bump) or "inward" (notch).
            shape: "round" (smooth bump via extra midpoint) or "sharp" (pointy vertex).
        """
        import math

        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        region = regions.get(region_id)
        if region is None:
            raise ValueError(f"Region '{region_id}' not found")

        pts = list(region.outline)
        n = len(pts)
        if n < 3:
            raise ValueError("Region must have at least 3 outline points")

        indices = segment_indices if segment_indices is not None else list(range(n))
        angle_rad = math.radians(angle_offset)
        dir_sign = -1.0 if direction == "inward" else 1.0

        # Process in reverse index order so insertions don't shift earlier indices
        for idx in sorted(indices, reverse=True):
            i = idx % n
            j = (i + 1) % n
            mx = (pts[i][0] + pts[j][0]) / 2
            my = (pts[i][1] + pts[j][1]) / 2
            # Outward normal (perpendicular to segment)
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            nx = -dy
            ny = dx
            seg_len = math.sqrt(nx * nx + ny * ny)
            if seg_len < 1e-10:
                continue
            nx /= seg_len
            ny /= seg_len
            # Apply angle offset + direction sign
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            ex = nx * cos_a - ny * sin_a
            ey = nx * sin_a + ny * cos_a
            ex *= dir_sign
            ey *= dir_sign

            if shape == "sharp":
                # Single pointy vertex
                ep = (mx + ex * extrusion_length, my + ey * extrusion_length)
                pts.insert(j, ep)
            else:
                # Round bump: three vertices for a symmetric rounded profile
                # Width is proportion of the segment length
                half_w = extrusion_width / 2
                t1 = max(0.0, 0.5 - half_w)
                t2 = min(1.0, 0.5 + half_w)
                p1x = pts[i][0] + (pts[j][0] - pts[i][0]) * t1
                p1y = pts[i][1] + (pts[j][1] - pts[i][1]) * t1
                p2x = pts[i][0] + (pts[j][0] - pts[i][0]) * t2
                p2y = pts[i][1] + (pts[j][1] - pts[i][1]) * t2
                # Peak is extruded from segment midpoint for symmetric placement
                peak = (mx + ex * extrusion_length, my + ey * extrusion_length)
                # Insert in reverse order: right bevel, peak, left bevel
                pts.insert(j, (p2x, p2y))  # right bevel
                pts.insert(j, peak)        # centered peak
                pts.insert(j, (p1x, p1y))  # left bevel

        region.outline = normalize_outline(pts)
        region.version += 1
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "extrude_region_outline", region_id)
        self._persist(doc_id)
        return True

    # ── Create composite region ───────────────────────────────────

    def create_composite_region(
        self,
        outline: list[Point2D],
        document_id: str | None = None,
        *,
        region_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        closed: bool = True,
        smoothness: float = 0.5,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        sub_parts: dict | None = None,
    ) -> dict[str, Any]:
        """Create a base region with patterned sub-part protrusions in one call.

        The ``sub_parts`` dict supports:
          count (int): Number of sub-parts (e.g. 5 fingers).
          pattern (str): "radial_fan" (fanning from one edge) or "radial_ring" (radial spikes).
          anchor (str): For radial_fan — "top_edge", "bottom_edge", "left_edge", "right_edge".
          length_range (list[float]): [min, max] length for each protrusion.
          width (float): Base width of each protrusion.
          angle_spread (float): Total angle spread in degrees across all protrusions.
          length_variance (bool): If True, vary lengths linearly across the fan.
          taper (float): Tip width ratio (0.0–1.0, default 0.5).

        Returns dict with ``base_id`` and ``sub_ids`` list.
        """
        import math
        import uuid

        doc_id = self._resolve_doc(document_id)

        # 1. Create base region
        rid = region_id or f"composite_{uuid.uuid4().hex[:6]}"
        base = self.create_region(
            outline=outline,
            document_id=doc_id,
            region_id=rid,
            layer=layer,
            z_index=z_index,
            constraints=CurveConstraints(smoothness=smoothness, closed=closed),
            style=Style(
                fill=fill,
                stroke=stroke,
                stroke_width=max(0.001, min(0.1, stroke_width)),
                opacity=max(0.0, min(1.0, opacity)),
            ),
        )

        sub_ids: list[str] = [base.id]

        if not sub_parts:
            return {"base_id": base.id, "sub_ids": sub_ids, "count": 1}

        count = sub_parts.get("count", 0)
        pattern = sub_parts.get("pattern", "radial_fan")
        anchor = sub_parts.get("anchor", "top_edge")
        length_range = sub_parts.get("length_range", [0.1, 0.15])
        part_width = sub_parts.get("width", 0.025)
        angle_spread = sub_parts.get("angle_spread", 30)
        length_var = sub_parts.get("length_variance", False)
        taper = sub_parts.get("taper", 0.5)

        if count < 1:
            return {"base_id": base.id, "sub_ids": sub_ids, "count": 1}

        # 2. Determine anchor edge from the base outline
        pts = list(base.outline)
        min_x_p = min(p[0] for p in pts)
        max_x_p = max(p[0] for p in pts)
        min_y_p = min(p[1] for p in pts)
        max_y_p = max(p[1] for p in pts)

        if anchor == "top_edge":
            edge_pts = sorted([p for p in pts if p[1] < min_y_p + (max_y_p - min_y_p) * 0.1], key=lambda p: p[0])
        elif anchor == "bottom_edge":
            edge_pts = sorted([p for p in pts if p[1] > max_y_p - (max_y_p - min_y_p) * 0.1], key=lambda p: p[0])
        elif anchor == "left_edge":
            edge_pts = sorted([p for p in pts if p[0] < min_x_p + (max_x_p - min_x_p) * 0.1], key=lambda p: p[1])
        elif anchor == "right_edge":
            edge_pts = sorted([p for p in pts if p[0] > max_x_p - (max_x_p - min_x_p) * 0.1], key=lambda p: p[1])
        else:
            edge_pts = sorted(pts, key=lambda p: p[0])

        if not edge_pts or len(edge_pts) < 2:
            edge_pts = pts[:2]

        # 3. Distribute origin points along the edge (span full width)
        origins: list[tuple[float, float]] = []
        edge_span = sub_parts.get("edge_span", 1.0)
        edge_pad = (1.0 - max(0.0, min(1.0, edge_span))) / 2
        for i in range(count):
            t = edge_pad + (i / (count - 1) if count > 1 else 0.5) * (1 - 2 * edge_pad)
            total_seg = len(edge_pts) - 1
            edge_pos = t * total_seg
            idx_a = min(int(edge_pos), total_seg - 1)
            idx_b = idx_a + 1
            frac = edge_pos - idx_a
            ox = edge_pts[idx_a][0] + (edge_pts[idx_b][0] - edge_pts[idx_a][0]) * frac
            oy = edge_pts[idx_a][1] + (edge_pts[idx_b][1] - edge_pts[idx_a][1]) * frac
            origins.append((ox, oy))

        # 4. Outward direction
        if anchor == "top_edge":
            outward = (0, -1)
        elif anchor == "bottom_edge":
            outward = (0, 1)
        elif anchor == "left_edge":
            outward = (-1, 0)
        elif anchor == "right_edge":
            outward = (1, 0)
        else:
            outward = (0, -1)

        half_spread = angle_spread / 2

        for i, (ox, oy) in enumerate(origins):
            t_fan = i / (count - 1) if count > 1 else 0.5
            if pattern == "radial_fan":
                fan_angle = math.radians(-half_spread + t_fan * angle_spread)
                dx = outward[0] * math.cos(fan_angle) - outward[1] * math.sin(fan_angle)
                dy = outward[0] * math.sin(fan_angle) + outward[1] * math.cos(fan_angle)
            else:
                cx = (min_x_p + max_x_p) / 2
                cy = (min_y_p + max_y_p) / 2
                rdx = ox - cx
                rdy = oy - cy
                dist = math.sqrt(rdx * rdx + rdy * rdy)
                if dist < 1e-10:
                    dx, dy = outward
                else:
                    dx = rdx / dist
                    dy = rdy / dist

            if length_var and count > 1:
                length_t = 1 - abs(t_fan - 0.5) * 2
                part_len = length_range[0] + length_t * (length_range[1] - length_range[0])
            else:
                part_len = (length_range[0] + length_range[1]) / 2

            self._create_protrusion(
                doc_id, part_len, part_width, taper, ox, oy, dx, dy,
                base.id, i, layer, z_index + 1, fill, stroke, stroke_width, opacity,
                sub_ids,
            )

        return {"base_id": base.id, "sub_ids": sub_ids, "count": len(sub_ids)}

    def _create_protrusion(
        self, doc_id, part_len, part_width, taper, ox, oy, dx, dy,
        base_id, index, layer, z_index, fill, stroke, stroke_width, opacity,
        sub_ids,
    ):
        """Helper: create one organic protrusion (finger, spike, petal) at origin.

        Uses a 6-point outline: base → mid-side → tip → mid-side → base,
        giving a tapered organic shape when smoothed by Catmull-Rom.
        """
        import math
        import uuid

        half_w = part_width / 2
        tip_w = half_w * taper
        px, py = dx * part_len, dy * part_len
        perp_x, perp_y = -dy, dx

        # Mid-point inset: narrows toward the tip for organic taper
        mid_frac = 0.35  # how far along the length the mid-points sit
        mid_w = half_w * (0.3 + 0.7 * taper)  # width at mid-point

        sub_rid = f"{base_id}_sub{index}"
        sub = RegionNode(
            id=sub_rid,
            layer=layer,
            z_index=z_index,
            outline=[
                # Base-left
                (ox - perp_x * half_w, oy - perp_y * half_w),
                # Mid-left (gently curved side)
                (ox + px * mid_frac - perp_x * mid_w, oy + py * mid_frac - perp_y * mid_w),
                # Tip-left
                (ox + px + perp_x * tip_w, oy + py + perp_y * tip_w),
                # Tip-right
                (ox + px - perp_x * tip_w, oy + py - perp_y * tip_w),
                # Mid-right
                (ox + px * mid_frac + perp_x * mid_w, oy + py * mid_frac + perp_y * mid_w),
                # Base-right
                (ox + perp_x * half_w, oy + perp_y * half_w),
            ],
            constraints=CurveConstraints(smoothness=0.5, closed=True),
            style=Style(
                fill=fill,
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
            ),
        )
        self._regions_for(doc_id)[sub_rid] = sub
        sub.version += 1
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "create_composite_region", sub_rid)
        self._persist(doc_id)
        sub_ids.append(sub_rid)
