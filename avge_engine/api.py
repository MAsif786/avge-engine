"""
FastAPI HTTP server — the underlying API layer beneath the MCP interface.

§12: The engine maintains a plain HTTP/FastAPI surface for non-MCP clients
(debug tooling, direct API access, integration tests), though MCP is the
primary LLM-facing interface.

M0b scope: single-process, no auth, in-memory scene graph.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from avge_engine import __version__, __tool_set_version__
from avge_engine.scene import SceneGraph, CurveConstraints, Style, Transform
from avge_engine.schema_registry import validate_input, list_tool_names
from avge_engine.renderer import svg_serialize, render_preview_base64, render_preview_png


# ── Global scene graph (single-process, M0b) ───────────────────────
_graph: SceneGraph | None = None


def _get_graph() -> SceneGraph:
    global _graph
    if _graph is None:
        _graph = SceneGraph()
    return _graph


def _reset_graph() -> None:
    """Reset the scene graph (used for tests and between benchmarks)."""
    global _graph
    _graph = None


# ── Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to init beyond lazy globals
    yield
    # Shutdown: no cleanup needed (in-memory only)


app = FastAPI(
    title="AVGE Engine",
    version=__version__,
    description="AI-Native Vector Graphics Engine — M0b",
    lifespan=lifespan,
)


# ── Models ──────────────────────────────────────────────────────────

class DocumentRequest(BaseModel):
    width: int = Field(default=1000, ge=100, le=4000)
    height: int = Field(default=1000, ge=100, le=4000)
    unit: str = Field(default="px")
    background: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    name: str = ""


class RegionRequest(BaseModel):
    outline: list[tuple[float, float]]
    document_id: str | None = None
    region_id: str | None = None
    layer: str = "default"
    z_index: int = 0
    closed: bool = True
    smoothness: float = Field(default=0.5, ge=0.0, le=1.0)
    fill: str | None = "#CCCCCC"
    stroke: str | None = "#333333"
    stroke_width: float = Field(default=0.005, ge=0.0, le=0.1)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class StyleRequest(BaseModel):
    ids: list[str]
    document_id: str | None = None
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=0.1)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)


class DescribeRequest(BaseModel):
    detail: str = "summary"
    filter_layer: str | None = None
    document_id: str | None = None


class PreviewRequest(BaseModel):
    scale: float = Field(default=1.0, ge=0.25, le=2.0)
    document_id: str | None = None


class DeleteRequest(BaseModel):
    ids: list[str]
    document_id: str | None = None


class EditRequest(BaseModel):
    region_id: str
    document_id: str | None = None
    outline: list[list[float]] | None = None
    smoothness: float | None = Field(default=None, ge=0.0, le=1.0)
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=0.1)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    z_index: int | None = None
    layer: str | None = None


class DuplicateRequest(BaseModel):
    region_id: str
    new_region_id: str | None = None
    document_id: str | None = None
    offset_x: float = 0.0
    offset_y: float = 0.0
    fill: str | None = None
    z_index: int | None = None


class EditRequest(BaseModel):
    region_id: str
    document_id: str | None = None
    outline: list[list[float]] | None = None
    smoothness: float | None = Field(default=None, ge=0.0, le=1.0)
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(default=None, ge=0.0, le=0.1)
    opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    z_index: int | None = None
    layer: str | None = None


class DuplicateRequest(BaseModel):
    region_id: str
    new_region_id: str | None = None
    document_id: str | None = None
    offset_x: float = 0.0
    offset_y: float = 0.0
    fill: str | None = None
    z_index: int | None = None


class ToolResponse(BaseModel):
    status: str = "ok"
    data: Any = None
    warnings: list[str] = []
    version: int | None = None


class ToolError(BaseModel):
    status: str = "error"
    error_code: str = ""
    message: str = ""


# ── Endpoints ──────────────────────────────────────────────────────

@app.post("/tools/reset")
async def reset():
    """Reset the scene graph (test/debug endpoint)."""
    _reset_graph()
    return ToolResponse(data={"message": "Scene graph reset"})


from fastapi.responses import Response


class BatchRequest(BaseModel):
    ops: list[dict] = Field(min_length=1)
    document_id: str | None = None
    atomic: bool = False


class CheckpointRequest(BaseModel):
    name: str = "default"


@app.get("/documents")
@app.post("/tools/list_documents")
async def list_documents():
    """List all documents (in-memory + stored)."""
    graph = _get_graph()
    docs = []
    for did in list(graph._docs.keys()):
        try:
            desc = graph.describe_scene(did)
            docs.append(desc["document"] | {"region_count": desc["region_count"]})
        except Exception:
            pass
    if hasattr(graph, 'list_stored_documents'):
        docs.extend(graph.list_stored_documents())
    return ToolResponse(data={"documents": docs})


@app.get("/preview/active.png")
@app.get("/preview/active")
async def preview_active():
    """Render a PNG preview of the active document directly."""
    from fastapi.responses import Response
    graph = _get_graph()
    if not graph._last_doc_id:
        return Response("No active document", status_code=404)
    try:
        svg = svg_serialize(graph)
        png = render_preview_png(svg, scale=1.0)
        return Response(content=png, media_type="image/png")
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


@app.post("/tools/batch", response_model=ToolResponse)
async def batch(req: BatchRequest):
    graph = _get_graph()
    doc_id = req.document_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No document")
    results = graph.batch(req.ops, doc_id)
    return ToolResponse(data={"results": results})


@app.get("/tools/checkpoint", response_model=ToolResponse)
async def checkpoint(req: CheckpointRequest):
    graph = _get_graph()
    if not graph.has_document():
        raise HTTPException(status_code=400, detail="No document")
    graph.checkpoint(req.name)
    return ToolResponse(data={
        "checkpoint": req.name,
        "region_count": graph.region_count(),
        "version": graph.get_document(doc_id).version,
    })


@app.post("/tools/restore", response_model=ToolResponse)
async def restore(req: CheckpointRequest):
    graph = _get_graph()
    if not graph.has_document():
        raise HTTPException(status_code=400, detail="No document")
    if not graph.restore(req.name):
        raise HTTPException(status_code=404, detail=f"Checkpoint '{req.name}' not found")
    return ToolResponse(data={
        "checkpoint": req.name,
        "region_count": graph.region_count(),
        "version": graph.get_document(doc_id).version,
    })


@app.get("/preview/{document_id}.png")
async def preview_doc_png(document_id: str):
    """Render a PNG preview of a specific document by ID."""
    from fastapi.responses import Response
    graph = _get_graph()
    if not graph.has_document(document_id):
        return Response(f"Document '{document_id}' not found", status_code=404)
    try:
        svg = svg_serialize(graph)
        png = render_preview_png(svg, scale=1.0)
        return Response(content=png, media_type="image/png")
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


@app.get("/documents/{document_id}")
async def get_document_rest(document_id: str):
    """RESTful: get document info + regions + preview link."""
    graph = _get_graph()
    if not graph.has_document(document_id):
        return Response(f"Document '{document_id}' not found", status_code=404)
    desc = graph.describe_scene(document_id)
    doc_info = desc["document"]
    return {
        "document": doc_info,
        "regions": desc["regions"],
        "region_count": desc["region_count"],
        "preview_url": f"/preview/{document_id}.png",
    }


@app.get("/tools/document/{document_id}", response_model=ToolResponse)
@app.post("/tools/document", response_model=ToolResponse)
async def get_document(document_id: str | None = None):
    """Get document metadata and render preview."""
    graph = _get_graph()
    if document_id and not graph.has_document(document_id):
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    doc_id = document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No document available")
    desc = graph.describe_scene(doc_id)
    svg = svg_serialize(graph)
    try:
        preview = render_preview_base64(svg, scale=0.5)
    except Exception as e:
        preview = f"error: {e}"
    return ToolResponse(data={
        "document": desc["document"],
        "region_count": desc["region_count"],
        "preview": preview,
    })


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__, "tool_set": __tool_set_version__}


@app.get("/schemas")
async def list_schemas():
    return {"tools": list_tool_names()}


@app.post("/tools/create_document", response_model=ToolResponse)
async def create_document(req: DocumentRequest):
    graph = _get_graph()
    try:
        doc = graph.create_document(
            width=req.width,
            height=req.height,
            unit=req.unit,
            background=req.background,
            name=req.name,
        )
        return ToolResponse(data={"document_id": doc.id, **req.model_dump()})
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/tools/create_region", response_model=ToolResponse)
async def create_region(req: RegionRequest):
    graph = _get_graph()
    if not req.document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found")
    doc_id = req.document_id

    try:
        constraints = CurveConstraints(
            smoothness=req.smoothness,
            closed=req.closed,
        )
        style = Style(
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
        )
        region = graph.create_region(
            outline=req.outline,
            region_id=req.region_id,
            layer=req.layer,
            z_index=req.z_index,
            constraints=constraints,
            style=style,
        )
        from avge_engine.geometry import compute_bounds
        bounds = compute_bounds(region.outline)
        warnings = []
        if len(req.outline) > 30:
            warnings.append(
                f"Advisory: outline has {len(req.outline)} points; "
                f"use fewer points + smoothness constraints for better curve quality"
            )
        return ToolResponse(
            data={
                "region_id": region.id,
                "bounds": bounds,
                "outline_point_count": len(req.outline),
            },
            warnings=warnings,
            version=region.version,
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/delete_region", response_model=ToolResponse)
async def delete_region(req: DeleteRequest):
    graph = _get_graph()
    if not req.document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found")
    doc_id = req.document_id
    deleted = graph.delete_regions(req.ids)
    return ToolResponse(data={"affected": deleted, "count": len(deleted)})


@app.post("/tools/edit_region", response_model=ToolResponse)
async def edit_region(req: EditRequest):
    graph = _get_graph()
    doc_id = req.document_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No document")
    try:
        graph.edit_region(
            region_id=req.region_id, document_id=doc_id,
            outline=req.outline, smoothness=req.smoothness,
            fill=req.fill, stroke=req.stroke,
            stroke_width=req.stroke_width, opacity=req.opacity,
            z_index=req.z_index, layer=req.layer,
        )
        return ToolResponse(data={"region_id": req.region_id, "updated": True})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/duplicate_region", response_model=ToolResponse)
async def duplicate_region(req: DuplicateRequest):
    graph = _get_graph()
    doc_id = req.document_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No document")
    try:
        dup = graph.duplicate_region(
            region_id=req.region_id, new_region_id=req.new_region_id,
            document_id=doc_id,
            offset_x=req.offset_x, offset_y=req.offset_y,
            fill=req.fill, z_index=req.z_index,
        )
        return ToolResponse(data={"region_id": dup.id, "source": req.region_id})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/style_objects", response_model=ToolResponse)
async def style_objects(req: StyleRequest):
    graph = _get_graph()
    if not req.document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found")
    doc_id = req.document_id

    affected = graph.style_objects(
        ids=req.ids,
        fill=req.fill,
        stroke=req.stroke,
        stroke_width=req.stroke_width,
        opacity=req.opacity,
    )
    return ToolResponse(data={"affected": affected, "count": len(affected)})


@app.post("/tools/describe_scene")
async def describe_scene(req: DescribeRequest):
    graph = _get_graph()
    if not req.document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found")
    doc_id = req.document_id
    desc = graph.describe_scene(detail=req.detail, filter_layer=req.filter_layer, document_id=doc_id)
    return desc


@app.post("/tools/render_preview", response_model=ToolResponse)
async def render_preview(req: PreviewRequest):
    graph = _get_graph()
    if not req.document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found")
    doc_id = req.document_id
    svg = svg_serialize(graph)
    try:
        b64 = render_preview_base64(svg, scale=req.scale)
        return ToolResponse(data={"preview": b64})
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
