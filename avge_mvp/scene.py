"""
In-memory scene graph for the AVGE MVP.

Normalized coordinate system: 0.0–1.0 on both axes, (0,0) = top-left.
Stored normalized, resolved to canvas pixels only at render/export time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


# ── Geometric types ───────────────────────────────────────────────────

type Point2D = tuple[float, float]


@dataclass
class CurveConstraints:
    """Geometric constraints for curve fitting (PRD §16, MVP §3.1)."""

    smoothness: float = 0.5        # 0.0 = sharp corners, 1.0 = very smooth
    closed: bool = True             # Whether the outline forms a closed loop
    corner_style: str = "round"     # "round" | "sharp" | "bevel"


@dataclass
class Style:
    """Fill and stroke style."""

    fill: str | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float = 0.005
    opacity: float = 1.0


@dataclass
class Transform:
    """Local transform relative to parent."""

    translate: tuple[float, float] = (0.0, 0.0)
    rotate: float = 0.0
    scale: tuple[float, float] = (1.0, 1.0)


@dataclass
class Region:
    """A vector region — the core primitive under test."""

    id: str
    layer: str = "default"
    outline: list[Point2D] = field(default_factory=list)
    constraints: CurveConstraints = field(default_factory=CurveConstraints)
    style: Style = field(default_factory=Style)
    transform: Transform = field(default_factory=Transform)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1


@dataclass
class Document:
    """A vector document / canvas."""

    id: str
    width: int = 1000
    height: int = 1000
    unit: str = "px"
    background: str = "#FFFFFF"
    regions: dict[str, Region] = field(default_factory=dict)
    version: int = 1


# ── Scene Graph Store ────────────────────────────────────────────────

class SceneGraph:
    """In-memory single-process scene graph (MVP — no persistence)."""

    def __init__(self) -> None:
        self._doc: Document | None = None

    # ── Document ──────────────────────────────────────────────────────

    def create_document(
        self,
        width: int = 1000,
        height: int = 1000,
        unit: str = "px",
        background: str = "#FFFFFF",
    ) -> Document:
        if self._doc is not None:
            raise RuntimeError("Document already exists (MVP: single-document only)")
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        self._doc = Document(
            id=doc_id, width=width, height=height, unit=unit, background=background
        )
        return self._doc

    @property
    def document(self) -> Document:
        if self._doc is None:
            raise RuntimeError("No document — call create_document first")
        return self._doc

    # ── Regions ───────────────────────────────────────────────────────

    def create_region(
        self,
        region_id: str | None = None,
        layer: str = "default",
        outline: list[Point2D] | None = None,
        constraints: CurveConstraints | None = None,
        style: Style | None = None,
        transform: Transform | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Region:
        doc = self.document
        rid = region_id or f"r_{uuid.uuid4().hex[:8]}"
        if rid in doc.regions:
            raise ValueError(f"Region '{rid}' already exists")
        region = Region(
            id=rid,
            layer=layer,
            outline=outline or [],
            constraints=constraints or CurveConstraints(),
            style=style or Style(),
            transform=transform or Transform(),
            metadata=metadata or {},
        )
        doc.regions[rid] = region
        doc.version += 1
        return region

    def get_region(self, region_id: str) -> Region:
        doc = self.document
        if region_id not in doc.regions:
            raise ValueError(f"Region '{region_id}' not found")
        return doc.regions[region_id]

    def style_objects(
        self,
        ids: list[str],
        fill: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
    ) -> list[str]:
        doc = self.document
        affected: list[str] = []
        for rid in ids:
            if rid not in doc.regions:
                continue
            reg = doc.regions[rid]
            if fill is not None:
                reg.style.fill = fill
            if stroke is not None:
                reg.style.stroke = stroke
            if stroke_width is not None:
                reg.style.stroke_width = stroke_width
            if opacity is not None:
                reg.style.opacity = opacity
            reg.version += 1
            affected.append(rid)
        doc.version += 1
        return affected

    # ── Scene Description (LLM feedback) ──────────────────────────────

    def describe_scene(self, detail: str = "summary") -> dict[str, Any]:
        doc = self.document
        regions = []
        for r in doc.regions.values():
            entry: dict[str, Any] = {
                "id": r.id,
                "layer": r.layer,
                "outline_point_count": len(r.outline),
                "closed": r.constraints.closed,
                "smoothness": r.constraints.smoothness,
                "style": {
                    "fill": r.style.fill,
                    "stroke": r.style.stroke,
                    "stroke_width": r.style.stroke_width,
                    "opacity": r.style.opacity,
                },
                "bounds": self._compute_bounds(r),
                "version": r.version,
            }
            if detail == "full":
                entry["outline"] = r.outline
            regions.append(entry)

        return {
            "document": {
                "id": doc.id,
                "width": doc.width,
                "height": doc.height,
                "unit": doc.unit,
                "background": doc.background,
                "version": doc.version,
            },
            "regions": regions,
            "region_count": len(regions),
            "warnings": self._compute_warnings(regions),
        }

    def _compute_bounds(self, r: Region) -> dict[str, float] | None:
        if not r.outline:
            return None
        xs = [p[0] for p in r.outline]
        ys = [p[1] for p in r.outline]
        return {"x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}

    def _compute_warnings(self, regions: list[dict]) -> list[str]:
        warnings: list[str] = []
        # Off-canvas check
        doc = self.document
        for r in regions:
            b = r.get("bounds")
            if b and (
                b["x"] + b["w"] < 0 or b["x"] > 1.0 or b["y"] + b["h"] < 0 or b["y"] > 1.0
            ):
                warnings.append(f"Region '{r['id']}' is entirely off-canvas")
        return warnings

    # ── SVG generation hook for renderer ─────────────────────────────

    def get_all_regions_sorted(self) -> list[Region]:
        """Return regions in insertion order (stable)."""
        doc = self.document
        # dict preserves insertion order in Python 3.7+
        return list(doc.regions.values())
