"""
FastAPI HTTP server — the underlying API layer beneath the MCP interface.

§12: The engine maintains a plain HTTP/FastAPI surface for non-MCP clients
(debug tooling, direct API access, integration tests), though MCP is the
primary LLM-facing interface.

M0b scope: single-process, no auth, in-memory scene graph.
Mirrors the MCP tool set at avge_engine/controllers/ — keep in sync.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from avge_engine import __version__, __tool_set_version__
from avge_engine.scene import CurveConstraints, Style
from avge_engine.services.engine import get_graph, reset_graph
from avge_engine.schema_registry import validate_input, list_tool_names
from avge_engine.renderer import svg_serialize, render_preview_base64, render_preview_png
from avge_engine.geometry import compute_bounds


# ── Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AVGE Engine",
    version=__version__,
    description="AI-Native Vector Graphics Engine — M0b Production Build",
    lifespan=lifespan,
)


# ── Shared Literal types ───────────────────────────────────────────

BLEND_MODES = Literal[
    "normal", "multiply", "screen", "overlay", "darken", "lighten",
    "color-dodge", "color-burn", "soft-light", "hard-light",
]

BOOLEAN_OPS = Literal["union", "intersect", "subtract", "xor"]
DETAIL_LEVEL = Literal["summary", "full"]
GROUP_ACTION = Literal["create", "add", "remove", "delete"]
PRESET_NAMES = Literal["warm_shaded", "cool_shaded", "metallic", "glow", "shadow", "wood"]
PIVOT_MODES = Literal["center", "base", "fixed"]


# ── Request / Response Models ──────────────────────────────────────

class ToolResponse(BaseModel):
    status: str = "ok"
    data: Any = None
    warnings: list[str] = []
    version: int | None = None


# ── Document ───────────────────────────────────────────────────────

class CreateDocumentRequest(BaseModel):
    width: int = Field(default=1000, ge=100, le=4000)
    height: int = Field(default=1000, ge=100, le=4000)
    unit: str = Field(default="px", pattern=r"^(px|in|mm|cm)$")
    background: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    name: str = ""


class DeleteDocumentRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    confirm: bool = False


# ── Region ─────────────────────────────────────────────────────────

class CreateRegionRequest(BaseModel):
    outline: list[list[float]] = Field(min_length=2, max_length=200)
    document_id: str
    region_id: str | None = None
    layer: str = "default"
    closed: bool = True
    smoothness: float = Field(default=0.5, ge=0.0, le=1.0)
    fill: str | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float = Field(default=0.005, ge=0.0, le=0.1)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    fill_gradient: Any = None
    smoothness_per_point: list[float] | None = None
    z_index: int = 0
    clip_to: str | None = None
    blend_mode: BLEND_MODES | None = None
    tags: dict | None = None


class EditRegionRequest(BaseModel):
    region_id: str
    document_id: str
    outline: list[list[float]] | None = None
    smoothness: float | None = Field(default=None, ge=0.0, le=1.0)
    smoothness_per_point: list[float] | None = None
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=0.1)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    z_index: int | None = None
    blend_mode: BLEND_MODES | None = None
    clip_to: str | None = None
    layer: str | None = None
    tags: dict | None = None


class DeleteRegionRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    document_id: str
    confirm: bool = False


class DuplicateRegionRequest(BaseModel):
    region_id: str
    new_region_id: str | None = None
    document_id: str
    offset_x: float = 0.0
    offset_y: float = 0.0
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=0.1)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    smoothness: float | None = Field(default=None, ge=0.0, le=1.0)
    z_index: int | None = None
    mirror_x: bool = False
    mirror_y: bool = False
    blend_mode: BLEND_MODES | None = None
    layer: str | None = None


# ── Style ──────────────────────────────────────────────────────────

class StyleObjectsRequest(BaseModel):
    ids: list[str] | None = None
    document_id: str
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=0.1)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    fill_gradient: Any = None
    blend_mode: BLEND_MODES | None = None
    clip_to: str | None = None
    group_name: str | None = None


class ApplyStylePresetRequest(BaseModel):
    preset: PRESET_NAMES
    ids: list[str] = Field(min_length=1)
    document_id: str


# ── Scene ops ──────────────────────────────────────────────────────

class BooleanOpRequest(BaseModel):
    operation: BOOLEAN_OPS = "union"
    region_ids: list[str] = Field(min_length=2)
    new_region_id: str | None = None
    document_id: str
    keep_originals: bool = False
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = None
    opacity: float | None = None


class TransformObjectsRequest(BaseModel):
    ids: list[str] | None = None
    document_id: str
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    sx: float | None = None
    sy: float | None = None
    rotate: float = 0.0
    group_mode: bool = False
    pivot_x: float | None = None
    pivot_y: float | None = None
    pivot_mode: PIVOT_MODES | None = None
    z_index: int | None = None
    group_name: str | None = None
    mirror_x: bool = False
    mirror_y: bool = False


class ManageGroupRequest(BaseModel):
    action: GROUP_ACTION = "create"
    group_name: str
    region_ids: list[str] | None = None
    document_id: str


class DuplicateGroupRequest(BaseModel):
    group_name: str
    document_id: str
    new_prefix: str | None = None
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    sx: float | None = None
    sy: float | None = None
    rotate: float = 0.0
    mirror_x: bool = False
    mirror_y: bool = False


class SubPartsDef(BaseModel):
    """Structured definition for create_composite_region sub-parts."""
    pattern: str = Field(description="Pattern type: radial_fan or radial_ring")
    count: int = Field(default=5, ge=1, le=50)
    anchor: str | None = Field(default=None, description="Edge anchor for radial_fan")
    length_range: list[float] | None = Field(default=None, min_length=2, max_length=2)
    width: float = Field(default=0.02, ge=0.001, le=0.2)
    angle_spread: float = Field(default=35, ge=0, le=180)
    length_variance: bool = False
    taper: float = Field(default=0.5, ge=0.0, le=1.0)
    edge_span: float = Field(default=1.0, ge=0.0, le=1.0, description="Fraction of edge to distribute across")


class CreateCompositeRegionRequest(BaseModel):
    outline: list[list[float]] = Field(min_length=2)
    document_id: str
    region_id: str | None = None
    layer: str = "default"
    closed: bool = True
    smoothness: float = Field(default=0.5, ge=0.0, le=1.0)
    fill: str | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float = 0.005
    opacity: float = 1.0
    z_index: int = 0
    sub_parts: SubPartsDef | None = None


class ExtrudeOutlineRequest(BaseModel):
    region_id: str
    document_id: str
    segment_indices: list[int] | None = None
    extrusion_length: float = 0.03
    extrusion_width: float = 0.02
    angle_offset: float = 0.0
    direction: Literal["outward", "inward"] = "outward"
    shape: Literal["round", "sharp"] = "round"


# ── Query / View ───────────────────────────────────────────────────

class DescribeSceneRequest(BaseModel):
    detail: DETAIL_LEVEL = "summary"
    filter_layer: str | None = None
    document_id: str


class FindObjectsRequest(BaseModel):
    document_id: str
    fill: str | None = None
    min_x: float | None = None
    max_x: float | None = None
    min_y: float | None = None
    max_y: float | None = None
    min_w: float | None = None
    max_w: float | None = None
    min_h: float | None = None
    max_h: float | None = None
    has_stroke: bool | None = None
    layer: str | None = None
    tags: dict | None = None


class PreviewRequest(BaseModel):
    scale: float = Field(default=1.0, ge=0.25, le=2.0)
    document_id: str


class ExportSvgRequest(BaseModel):
    filepath: str = "output/scene.svg"
    document_id: str


class ReorderLayerRequest(BaseModel):
    layer: str
    z_offset: int
    document_id: str


# ── History ────────────────────────────────────────────────────────

class CheckpointRequest(BaseModel):
    name: str = "default"
    document_id: str | None = None


class BatchRequest(BaseModel):
    ops: list[dict] = Field(min_length=1, max_length=200)
    document_id: str


# ── Health ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__, "tool_set": __tool_set_version__}


# ── Document Endpoints ─────────────────────────────────────────────

@app.post("/tools/create_document", response_model=ToolResponse)
async def create_document(req: CreateDocumentRequest):
    graph = get_graph()
    try:
        doc = graph.create_document(
            width=req.width, height=req.height,
            unit=req.unit, background=req.background,
            name=req.name,
        )
        return ToolResponse(data={
            "document_id": doc.id,
            "width": doc.width, "height": doc.height,
            "unit": doc.unit, "background": doc.background,
            "name": doc.name or "",
        })
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/tools/delete_document", response_model=ToolResponse)
async def delete_document(req: DeleteDocumentRequest):
    scene = get_graph()
    if not scene._storage:
        raise HTTPException(status_code=400, detail="Storage not available")

    from avge_engine.services.engine import list_stored_documents
    stored = {d["id"]: d for d in list_stored_documents()}
    found = [i for i in req.ids if i in stored]
    missing = [i for i in req.ids if i not in stored]

    if not found:
        raise HTTPException(status_code=404, detail=f"No matching documents found. Not found: {missing}")

    if not req.confirm:
        return ToolResponse(data={
            "preview": True,
            "found": [{"id": i, "name": stored[i].get("name", "") or "(unnamed)"} for i in found],
            "message": f"Call with confirm=True to delete {len(found)} document(s)",
            "not_found": missing,
        })

    deleted = []
    errors = []
    for doc_id in found:
        try:
            if doc_id in scene._docs:
                del scene._docs[doc_id]
            if doc_id in scene._regions_by_doc:
                del scene._regions_by_doc[doc_id]
            scene._storage.delete(doc_id)
            deleted.append(doc_id)
        except Exception as e:
            errors.append(f"{doc_id}: {e}")

    result = {"deleted": deleted}
    if errors:
        result["errors"] = errors
    return ToolResponse(data=result)


@app.post("/tools/load_document", response_model=ToolResponse)
async def load_document(document_id: str):
    from avge_engine.services.engine import load_stored_document
    if load_stored_document(document_id):
        scene = get_graph()
        desc = scene.describe_scene(document_id)
        return ToolResponse(data={
            "document_id": document_id,
            "region_count": desc["region_count"],
            "version": desc["document"]["version"],
        })
    raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


@app.get("/documents")
async def list_documents_api():
    """List all persisted documents."""
    from avge_engine.services.engine import list_stored_documents
    stored = list_stored_documents()
    return ToolResponse(data={"documents": stored, "count": len(stored)})


@app.get("/documents/{document_id}")
async def get_document_info(document_id: str):
    """Get document metadata + preview link."""
    graph = get_graph()
    if not graph.has_document(document_id) and not graph.load_document(document_id):
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    desc = graph.describe_scene(document_id)
    return {
        "document": desc["document"],
        "regions": desc["regions"],
        "region_count": desc["region_count"],
        "preview_url": f"/preview/{document_id}.png",
    }


# ── Region Endpoints ───────────────────────────────────────────────

@app.post("/tools/create_region", response_model=ToolResponse)
async def create_region(req: CreateRegionRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found")
    doc_id = req.document_id

    import json as _json
    resolved_fill = req.fill
    if req.fill_gradient is not None:
        if isinstance(req.fill_gradient, str):
            try:
                resolved_fill = _json.loads(req.fill_gradient)
            except _json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="invalid fill_gradient JSON")
        else:
            resolved_fill = req.fill_gradient

    try:
        constraints = CurveConstraints(
            smoothness=max(0.0, min(1.0, req.smoothness)),
            closed=req.closed,
            tensions=req.smoothness_per_point,
        )
        style = Style(
            fill=None if resolved_fill is None or resolved_fill == "none" else resolved_fill,
            stroke=req.stroke,
            stroke_width=max(0.001, min(0.1, req.stroke_width)),
            opacity=max(0.0, min(1.0, req.opacity)),
            blend_mode=req.blend_mode,
        )
        metadata = {}
        if req.tags:
            try:
                metadata = dict(req.tags)
            except (_json.JSONDecodeError, TypeError):
                raise HTTPException(status_code=400, detail="tags must be a valid JSON object")

        region = graph.create_region(
            outline=[(float(p[0]), float(p[1])) for p in req.outline],
            region_id=req.region_id, document_id=doc_id,
            layer=req.layer, z_index=req.z_index,
            clip_to=req.clip_to,
            constraints=constraints, style=style,
            metadata=metadata,
        )
        bounds = compute_bounds(region.outline)
        warnings = []
        if len(req.outline) > 30:
            warnings.append(f"Advisory: {len(req.outline)} points is high")
        return ToolResponse(data={
            "region_id": region.id, "bounds": bounds,
            "outline_point_count": len(req.outline),
        }, warnings=warnings)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/edit_region", response_model=ToolResponse)
async def edit_region(req: EditRegionRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        metadata = None
        if req.tags:
            import json as _json
            metadata = dict(req.tags)

        graph.edit_region(
            region_id=req.region_id, document_id=req.document_id,
            outline=req.outline, smoothness=req.smoothness,
            tensions=req.smoothness_per_point,
            fill=req.fill, stroke=req.stroke,
            stroke_width=req.stroke_width, opacity=req.opacity,
            z_index=req.z_index, blend_mode=req.blend_mode,
            clip_to=req.clip_to, layer=req.layer,
            metadata=metadata,
        )
        return ToolResponse(data={"region_id": req.region_id})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/delete_region", response_model=ToolResponse)
async def delete_region(req: DeleteRegionRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    deleted = graph.delete_regions(req.document_id, req.ids)
    return ToolResponse(data={"affected": deleted, "count": len(deleted)})


@app.post("/tools/duplicate_region", response_model=ToolResponse)
async def duplicate_region(req: DuplicateRegionRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=400, detail="No document")
    try:
        dup = graph.duplicate_region(
            region_id=req.region_id, new_region_id=req.new_region_id,
            document_id=req.document_id,
            offset_x=req.offset_x, offset_y=req.offset_y,
            fill=req.fill, stroke=req.stroke,
            stroke_width=req.stroke_width, opacity=req.opacity,
            smoothness=req.smoothness, z_index=req.z_index,
            mirror_x=req.mirror_x, mirror_y=req.mirror_y,
            blend_mode=req.blend_mode, layer=req.layer,
        )
        return ToolResponse(data={"region_id": dup.id, "source": req.region_id})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Primitive Endpoints ────────────────────────────────────────────

class CreateRectRequest(BaseModel):
    x: float
    y: float
    width: float
    height: float
    rx: float = 0.0
    document_id: str
    region_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    fill: str | None = "#E8C8A0"
    stroke: str | None = "#5A4A3A"
    stroke_width: float = 0.006
    opacity: float = 1.0
    blend_mode: str | None = None


class CreateEllipseRequest(BaseModel):
    cx: float
    cy: float
    rx: float
    ry: float | None = None
    document_id: str
    region_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    fill: str | None = "#E8C8A0"
    stroke: str | None = "#5A4A3A"
    stroke_width: float = 0.006
    opacity: float = 1.0
    blend_mode: str | None = None


class CreateLineRequest(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    document_id: str
    region_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    stroke: str | None = "#5A4A3A"
    stroke_width: float = 0.005
    opacity: float = 1.0
    blend_mode: str | None = None


@app.post("/tools/create_rect", response_model=ToolResponse)
async def create_rect(req: CreateRectRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        r = graph.create_rect(
            req.x, req.y, req.width, req.height, rx=req.rx,
            document_id=req.document_id, region_id=req.region_id,
            layer=req.layer, z_index=req.z_index,
            fill=req.fill, stroke=req.stroke,
            stroke_width=req.stroke_width, opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"region_id": r.id})
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/create_ellipse", response_model=ToolResponse)
async def create_ellipse(req: CreateEllipseRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        e = graph.create_ellipse(
            req.cx, req.cy, req.rx, ry=req.ry,
            document_id=req.document_id, region_id=req.region_id,
            layer=req.layer, z_index=req.z_index,
            fill=req.fill, stroke=req.stroke,
            stroke_width=req.stroke_width, opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"region_id": e.id})
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/create_line", response_model=ToolResponse)
async def create_line(req: CreateLineRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        lr = graph.create_line(
            req.x1, req.y1, req.x2, req.y2,
            document_id=req.document_id, region_id=req.region_id,
            layer=req.layer, z_index=req.z_index,
            stroke=req.stroke, stroke_width=req.stroke_width,
            opacity=req.opacity, blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"region_id": lr.id})
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Style Endpoints ────────────────────────────────────────────────

@app.post("/tools/style_objects", response_model=ToolResponse)
async def style_objects(req: StyleObjectsRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc_id = req.document_id

    # Resolve group_name
    ids = req.ids
    if req.group_name is not None:
        members = graph.get_group(req.group_name, doc_id)
        if not members:
            raise HTTPException(status_code=404, detail=f"Group '{req.group_name}' not found")
        ids = [m["id"] for m in members]
    elif not ids:
        raise HTTPException(status_code=400, detail="No region IDs provided")

    # Resolve fill from gradient
    import json as _json
    resolved_fill = None
    if req.fill_gradient is not None:
        if isinstance(req.fill_gradient, str):
            resolved_fill = _json.loads(req.fill_gradient)
        else:
            resolved_fill = req.fill_gradient
    elif req.fill is not None and req.fill != "none":
        resolved_fill = req.fill

    resolved_stroke = None if req.stroke is None or req.stroke == "none" else req.stroke
    resolved_sw = max(0.001, min(0.1, req.stroke_width)) if req.stroke_width is not None else None
    resolved_op = max(0.0, min(1.0, req.opacity)) if req.opacity is not None else None

    # Route through edit_region if blend_mode or clip_to
    if req.blend_mode is not None or req.clip_to is not None:
        affected = []
        for rid in ids:
            try:
                graph.edit_region(
                    region_id=rid, document_id=doc_id,
                    fill=resolved_fill, stroke=resolved_stroke,
                    stroke_width=resolved_sw, opacity=resolved_op,
                    blend_mode=req.blend_mode, clip_to=req.clip_to,
                )
                affected.append(rid)
            except (ValueError, RuntimeError) as e:
                raise HTTPException(status_code=400, detail=f"Error updating '{rid}': {e}")
        return ToolResponse(data={"affected": affected, "count": len(affected)})

    affected = graph.style_objects(
        ids=ids, document_id=doc_id,
        fill=resolved_fill, stroke=resolved_stroke,
        stroke_width=resolved_sw, opacity=resolved_op,
    )
    return ToolResponse(data={"affected": affected, "count": len(affected)})


@app.post("/tools/apply_style_preset", response_model=ToolResponse)
async def apply_style_preset(req: ApplyStylePresetRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc_id = req.document_id

    presets = getattr(graph, "PRESETS", None)
    if presets is None or req.preset not in presets:
        raise HTTPException(status_code=400, detail=f"Unknown preset '{req.preset}'")

    preset_config = presets[req.preset].copy()
    fill_gradient = preset_config.pop("fill_gradient", None)
    blend_mode = preset_config.pop("blend_mode", None)

    import json as _json
    affected = []
    for rid in req.ids:
        try:
            fill = None
            if fill_gradient:
                fill = _json.loads(fill_gradient) if isinstance(fill_gradient, str) else fill_gradient
            graph.edit_region(
                region_id=rid, document_id=doc_id,
                fill=fill or preset_config.get("fill"),
                opacity=preset_config.get("opacity"),
                blend_mode=blend_mode,
            )
            affected.append(rid)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=400, detail=str(e))
    return ToolResponse(data={"affected": affected, "count": len(affected)})


# ── Scene Ops Endpoints ────────────────────────────────────────────

@app.post("/tools/boolean_operation", response_model=ToolResponse)
async def boolean_operation(req: BooleanOpRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = graph.boolean_operation(
            operation=req.operation, region_ids=req.region_ids,
            new_region_id=req.new_region_id, document_id=req.document_id,
            keep_originals=req.keep_originals, fill=req.fill,
            stroke=req.stroke, stroke_width=req.stroke_width,
            opacity=req.opacity,
        )
        return ToolResponse(data={"region_id": result.id, "outline_points": len(result.outline)})
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/transform_objects", response_model=ToolResponse)
async def transform_objects(req: TransformObjectsRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc_id = req.document_id

    ids = req.ids
    if req.group_name is not None:
        members = graph.get_group(req.group_name, doc_id)
        if not members:
            raise HTTPException(status_code=404, detail=f"Group '{req.group_name}' not found")
        ids = [m["id"] for m in members]
    elif not ids:
        raise HTTPException(status_code=400, detail="No region IDs provided")

    try:
        affected = graph.transform_objects(
            ids=ids, document_id=doc_id,
            dx=req.dx, dy=req.dy, scale=req.scale,
            sx=req.sx, sy=req.sy, rotate=req.rotate,
            group_mode=req.group_mode,
            pivot_x=req.pivot_x, pivot_y=req.pivot_y,
            pivot_mode=req.pivot_mode, z_index=req.z_index,
            mirror_x=req.mirror_x, mirror_y=req.mirror_y,
        )
        return ToolResponse(data={"affected": affected, "count": len(affected)})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/manage_group", response_model=ToolResponse)
async def manage_group(req: ManageGroupRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    doc_id = req.document_id

    if req.action == "delete":
        result = graph.ungroup_regions(req.group_name, doc_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Group '{req.group_name}' not found")
        return ToolResponse(data={"group": req.group_name, "deleted": True})

    if not req.region_ids:
        raise HTTPException(status_code=400, detail="No region IDs provided")

    try:
        if req.action == "create":
            members = graph.group_regions(req.group_name, req.region_ids, doc_id, replace=True)
        elif req.action == "add":
            members = graph.add_to_group(req.group_name, req.region_ids, doc_id)
        elif req.action == "remove":
            removed = graph.remove_from_group(req.group_name, req.region_ids, doc_id)
            return ToolResponse(data={"group": req.group_name, "removed": removed})
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
        return ToolResponse(data={"group": req.group_name, "members": members, "count": len(members)})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/list_groups", response_model=ToolResponse)
async def list_groups(document_id: str):
    graph = get_graph()
    if not graph.has_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    groups = graph.list_groups(document_id)
    return ToolResponse(data={"groups": groups, "count": len(groups)})


@app.post("/tools/duplicate_group", response_model=ToolResponse)
async def duplicate_group(req: DuplicateGroupRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        new_ids = graph.duplicate_group(
            group_name=req.group_name, document_id=req.document_id,
            new_prefix=req.new_prefix,
            dx=req.dx, dy=req.dy, scale=req.scale,
            sx=req.sx, sy=req.sy, rotate=req.rotate,
            mirror_x=req.mirror_x, mirror_y=req.mirror_y,
        )
        return ToolResponse(data={
            "source_group": req.group_name,
            "new_ids": new_ids, "count": len(new_ids),
        })
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/create_composite_region", response_model=ToolResponse)
async def create_composite_region(req: CreateCompositeRegionRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        result = graph.create_composite_region(
            outline=req.outline, document_id=req.document_id,
            region_id=req.region_id, layer=req.layer,
            z_index=req.z_index, closed=req.closed,
            smoothness=req.smoothness,
            fill=req.fill, stroke=req.stroke,
            stroke_width=req.stroke_width, opacity=req.opacity,
            sub_parts=req.sub_parts,
        )
        return ToolResponse(data=result)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/extrude_region_outline", response_model=ToolResponse)
async def extrude_region_outline(req: ExtrudeOutlineRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        graph.extrude_region_outline(
            region_id=req.region_id, document_id=req.document_id,
            segment_indices=req.segment_indices,
            extrusion_length=req.extrusion_length,
            extrusion_width=req.extrusion_width,
            angle_offset=req.angle_offset,
            direction=req.direction,
            shape=req.shape,
        )
        return ToolResponse(data={"region_id": req.region_id})
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Query / View Endpoints ─────────────────────────────────────────

@app.post("/tools/describe_scene", response_model=ToolResponse)
async def describe_scene(req: DescribeSceneRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    desc = graph.describe_scene(detail=req.detail, filter_layer=req.filter_layer, document_id=req.document_id)
    return ToolResponse(data={
        "document": desc["document"],
        "regions": desc["regions"],
        "region_count": desc["region_count"],
        "warnings": desc.get("warnings", []),
    })


@app.post("/tools/find_objects", response_model=ToolResponse)
async def find_objects(req: FindObjectsRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    parsed_tags = dict(req.tags) if req.tags else None
    results = graph.find_objects(
        document_id=req.document_id, fill=req.fill,
        min_x=req.min_x, max_x=req.max_x,
        min_y=req.min_y, max_y=req.max_y,
        min_w=req.min_w, max_w=req.max_w,
        min_h=req.min_h, max_h=req.max_h,
        layer=req.layer, has_stroke=req.has_stroke,
        tags=parsed_tags,
    )
    return ToolResponse(data={"results": results, "count": len(results)})


@app.post("/tools/critique_composition", response_model=ToolResponse)
async def critique_composition(document_id: str):
    graph = get_graph()
    if not graph.has_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    findings = graph.critique_composition(document_id)
    return ToolResponse(data={"findings": findings, "count": len(findings)})


@app.post("/tools/list_layers", response_model=ToolResponse)
async def list_layers(document_id: str):
    graph = get_graph()
    if not graph.has_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    layers = graph.list_layers(document_id)
    return ToolResponse(data={"layers": layers})


@app.post("/tools/reorder_layer", response_model=ToolResponse)
async def reorder_layer(req: ReorderLayerRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    count = graph.reorder_layer(req.layer, req.z_offset, req.document_id)
    return ToolResponse(data={"layer": req.layer, "z_offset": req.z_offset, "count": count})


@app.post("/tools/render_preview", response_model=ToolResponse)
async def render_preview(req: PreviewRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    svg = svg_serialize(graph, req.document_id)
    from avge_engine.renderer import render_preview_base64
    try:
        b64 = render_preview_base64(svg, scale=max(0.25, min(2.0, req.scale)))
        return ToolResponse(data={"preview": b64})
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/export_svg", response_model=ToolResponse)
async def export_svg(req: ExportSvgRequest):
    from pathlib import Path
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    svg = svg_serialize(graph, req.document_id)
    path = Path(req.filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg)
    return ToolResponse(data={"filepath": str(path.resolve()), "chars": len(svg)})


# ── Preview (direct PNG) ───────────────────────────────────────────

@app.get("/preview/{document_id}.png")
async def preview_doc_png(document_id: str):
    """Render a PNG preview of a specific document by ID."""
    graph = get_graph()
    # Reload from disk on every render to pick up MCP-side edits
    if not graph.load_document(document_id):
        return Response(f"Document '{document_id}' not found", status_code=404)
    try:
        svg = svg_serialize(graph, document_id)
        png = render_preview_png(svg, scale=1.0)
        return Response(content=png, media_type="image/png")
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


# ── History Endpoints ──────────────────────────────────────────────

@app.post("/tools/checkpoint", response_model=ToolResponse)
async def checkpoint(req: CheckpointRequest):
    graph = get_graph()
    try:
        from avge_engine.services.engine import resolve_doc
        doc_id = resolve_doc(req.document_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No document")
    graph.checkpoint(doc_id, req.name)
    return ToolResponse(data={
        "checkpoint": req.name,
        "region_count": graph.region_count(doc_id),
        "version": graph.get_document(doc_id).version,
    })


@app.post("/tools/restore", response_model=ToolResponse)
async def restore(req: CheckpointRequest):
    graph = get_graph()
    try:
        from avge_engine.services.engine import resolve_doc
        doc_id = resolve_doc(req.document_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No document")
    if not graph.restore(doc_id, req.name):
        raise HTTPException(status_code=404, detail=f"Checkpoint '{req.name}' not found")
    return ToolResponse(data={
        "checkpoint": req.name,
        "region_count": graph.region_count(doc_id),
        "version": graph.get_document(doc_id).version,
    })


@app.post("/tools/get_history", response_model=ToolResponse)
async def get_history(document_id: str | None = None, limit: int = 20):
    graph = get_graph()
    try:
        from avge_engine.services.engine import resolve_doc
        doc_id = resolve_doc(document_id)
    except RuntimeError:
        raise HTTPException(status_code=400, detail="No active document")
    history = graph.list_checkpoints(doc_id)
    meta_store = getattr(graph, "_checkpoint_meta", {})
    entries = []
    for name in history[:limit]:
        entry = meta_store.get(f"{doc_id}::{name}", {})
        entries.append({
            "name": name,
            "time": entry.get("time", "?"),
            "action": entry.get("action", "?"),
            "detail": entry.get("detail", ""),
            "region_count": entry.get("region_count", "?"),
        })
    return ToolResponse(data={"history": entries, "count": len(entries)})


@app.post("/tools/batch", response_model=ToolResponse)
async def batch(req: BatchRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=400, detail="No document")
    results = graph.batch(req.ops, req.document_id)
    return ToolResponse(data={"results": results})



@app.post("/tools/reset")
async def reset():
    """Reset the scene graph (test/debug endpoint)."""
    reset_graph()
    return ToolResponse(data={"message": "Scene graph reset"})


# ── Schema Discovery ───────────────────────────────────────────────

@app.get("/schemas")
async def list_schemas():
    return {"tools": list_tool_names()}
