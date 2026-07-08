"""
Production scene graph — multi-document in-memory store with versioning.

§4.6: Every node carries a monotonically increasing version. Mutations
produce a new version rather than mutating in place (immutable nodes).

M0b scope: in-memory only. Postgres-backed operation log comes in M1.

Multiple documents are stored keyed by document_id (UUID string).
All mutating/query tools accept an optional document_id parameter.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any

from avge_engine.geometry import (
    CurveConstraints,
    Point2D,
    Transform,
    compute_bounds,
    normalize_outline,
)
from avge_engine.effects import Style
from avge_engine.storage import StorageAdapter
from typing import TYPE_CHECKING


# ── Core data objects ──────────────────────────────────────────────

@dataclass
class RegionNode:
    """A region node in the scene graph."""

    id: str
    type: str = "region"
    layer: str = "default"
    z_index: int = 0
    outline: list[Point2D] = field(default_factory=list)
    constraints: CurveConstraints = field(default_factory=CurveConstraints)
    style: Style = field(default_factory=Style)
    transform: Transform = field(default_factory=Transform)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1


@dataclass
class DocumentNode:
    """Root document node."""

    id: str
    name: str = ""
    width: int = 1000
    height: int = 1000
    unit: str = "px"
    background: str = "#FFFFFF"
    version: int = 1


# ── Scene Graph ────────────────────────────────────────────────────

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

    def attach_storage(self, adapter: StorageAdapter) -> None:
        self._storage = adapter

    def _persist(self, doc_id: str) -> None:
        if not self._storage:
            return
        from dataclasses import asdict
        doc = self._docs.get(doc_id)
        regions = self._regions_by_doc.get(doc_id, {})
        self._storage.save(doc_id, {
            "document": asdict(doc) if doc else {},
            "regions": {k: asdict(v) for k, v in regions.items()},
            "metadata": {"updated": __import__("datetime").datetime.now().isoformat()},
        })

    def load_document(self, document_id: str) -> bool:
        if not self._storage:
            return False
        data = self._storage.load(document_id)
        if not data:
            return False
        from avge_engine.scene import DocumentNode, RegionNode, CurveConstraints, Style, Transform
        d = data.get("document", {})
        self._docs[document_id] = DocumentNode(**d)
        regions = {}
        for rid, r in data.get("regions", {}).items():
            if "constraints" in r and isinstance(r["constraints"], dict):
                r["constraints"] = CurveConstraints(**r["constraints"])
            if "style" in r and isinstance(r["style"], dict):
                r["style"] = Style(**r["style"])
            regions[rid] = RegionNode(**r)
        # Reconstruct regions dict from the loaded data
        regions_dict = {}
        for rid, rdict in data.get("regions", {}).items():
            from avge_engine.scene import RegionNode, CurveConstraints, Style
            if "constraints" in rdict and isinstance(rdict["constraints"], dict):
                rdict["constraints"] = CurveConstraints(**rdict["constraints"])
            if "style" in rdict and isinstance(rdict["style"], dict):
                rdict["style"] = Style(**rdict["style"])
            regions_dict[rid] = RegionNode(**rdict)
        self._regions_by_doc[document_id] = regions_dict
        self._last_doc_id = document_id
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
        doc = DocumentNode(
            id=doc_id,
            name=name,
            width=width,
            height=height,
            unit=unit,
            background=background,
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
        self._auto_checkpoint(doc_id, "delete_region", region_id)
        self._persist(doc_id)
        return True

    def delete_regions(self, document_id: str, ids: list[str]) -> list[str]:
        """Delete multiple regions. Returns list of actually deleted IDs."""
        deleted: list[str] = []
        for rid in ids:
            if self.delete_region(document_id, rid):
                deleted.append(rid)
        return deleted

    # ── Batch operations ────────────────────────────────────────────

    def batch(self, ops: list[dict], document_id: str | None = None) -> list[dict]:
        """Execute multiple operations in sequence within one document.

        Each op dict requires a "tool" key. Supported: create_region,
        edit_region, duplicate_region, delete_region, style_objects.

        Returns list of result dicts, one per op in order.
        """
        doc_id = self._resolve_doc(document_id)
        results: list[dict] = []
        for op in ops:
            tool = op.pop("tool", "")
            try:
                if tool == "create_region":
                    r = self.create_region(
                        outline=op.pop("outline"),
                        region_id=op.get("region_id"),
                        document_id=doc_id,
                        layer=op.get("layer", "default"),
                        z_index=op.get("z_index", 0),
                        constraints=CurveConstraints(
                            smoothness=op.get("smoothness", 0.5),
                            closed=op.get("closed", True),
                            tensions=tuple(op["tensions"]) if "tensions" in op else None,
                        ),
                        style=Style(
                            fill=op.get("fill"),
                            stroke=op.get("stroke"),
                            stroke_width=op.get("stroke_width", 0.005),
                            opacity=op.get("opacity", 1.0),
                        ),
                    )
                    results.append({"status": "ok", "region_id": r.id})
                elif tool == "edit_region":
                    self.edit_region(
                        region_id=op.pop("region_id"),
                        document_id=doc_id,
                        outline=op.get("outline"),
                        fill=op.get("fill"),
                        stroke=op.get("stroke"),
                        z_index=op.get("z_index"),
                        opacity=op.get("opacity"),
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
                    )
                    results.append({"status": "ok", "region_id": d.id})
                elif tool == "delete_region":
                    self.delete_region(region_id=op.pop("region_id"), document_id=doc_id)
                    results.append({"status": "ok"})
                elif tool == "style_objects":
                    affected = self.style_objects(
                        ids=op.pop("ids"),
                        document_id=doc_id,
                        fill=op.get("fill"),
                        stroke=op.get("stroke"),
                        stroke_width=op.get("stroke_width"),
                        opacity=op.get("opacity"),
                    )
                    results.append({"status": "ok", "affected": affected})
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
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        z_index: int | None = None,
        layer: str | None = None,
    ) -> bool:
        """Modify an existing region's properties. Only provided fields are changed."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        region = regions.get(region_id)
        if region is None:
            raise ValueError(f"Region '{region_id}' not found")
        if outline is not None:
            region.outline = normalize_outline(outline)
        if smoothness is not None or tensions is not None:
            old_c = region.constraints
            region.constraints = CurveConstraints(
                smoothness=smoothness if smoothness is not None else old_c.smoothness,
                closed=old_c.closed,
                corner_style=old_c.corner_style,
                tensions=tensions if tensions is not None else old_c.tensions,
            )
        if fill is not None or stroke is not None or stroke_width is not None or opacity is not None:
            old_s = region.style
            region.style = Style(
                fill=fill if fill is not None else old_s.fill,
                stroke=stroke if stroke is not None else old_s.stroke,
                stroke_width=stroke_width if stroke_width is not None else old_s.stroke_width,
                opacity=opacity if opacity is not None else old_s.opacity,
            )
        if z_index is not None:
            region.z_index = z_index
        if layer is not None:
            region.layer = layer
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
    ) -> RegionNode:
        """Duplicate a region with optional offset and overrides."""
        doc_id = self._resolve_doc(document_id)
        regions = self._regions_for(doc_id)
        original = regions.get(region_id)
        if original is None:
            raise ValueError(f"Region '{region_id}' not found")
        rid = new_region_id or f"{region_id}_copy"
        if rid in regions:
            raise ValueError(f"Region '{rid}' already exists")
        new_outline = [(x + offset_x, y + offset_y) for x, y in original.outline]
        new_fill = fill if fill is not None else original.style.fill
        dup = RegionNode(
            id=rid,
            layer=original.layer,
            z_index=z_index if z_index is not None else original.z_index + 1,
            outline=new_outline,
            constraints=original.constraints,
            style=Style(
                fill=new_fill,
                stroke=original.style.stroke,
                stroke_width=original.style.stroke_width,
                opacity=original.style.opacity,
            ),
            transform=original.transform,
        )
        regions[rid] = dup
        self.get_document(doc_id).version += 1
        self._auto_checkpoint(doc_id, "duplicate_region", f"{region_id}->{rid}")
        self._persist(doc_id)
        return dup

    # ── Style operations ────────────────────────────────────────────

    def style_objects(
        self,
        ids: list[str],
        document_id: str | None = None,
        *,
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
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
            new_style = Style(
                fill=fill if fill is not None else old.fill,
                stroke=stroke if stroke is not None else old.stroke,
                stroke_width=stroke_width if stroke_width is not None else old.stroke_width,
                opacity=opacity if opacity is not None else old.opacity,
            )
            region.style = new_style
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
                "outline_point_count": len(r.outline),
                "closed": r.constraints.closed,
                "smoothness": r.constraints.smoothness,
                "style": {
                    "fill": r.style.fill,
                    "stroke": r.style.stroke,
                    "stroke_width": r.style.stroke_width,
                    "opacity": r.style.opacity,
                },
                "bounds": compute_bounds(r.outline),
                "version": r.version,
            }
            if detail == "full":
                entry["outline"] = r.outline
            region_list.append(entry)

        warnings = self._compute_warnings(document_id)
        smoothness_notes = self._compute_smoothness_notes(document_id)

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
        return True

    def list_checkpoints(self, document_id: str | None = None) -> list[str]:
        """Return available checkpoint names for a document."""
        prefix = f"{document_id}::"
        return [k[len(prefix):] for k in self._checkpoints if k.startswith(prefix)]
