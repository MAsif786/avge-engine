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
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from avge_engine import __version__, __tool_set_version__
from avge_engine.api_viewer import viewer_html
from avge_engine.services.engine import get_graph, reset_graph
from avge_engine.services.creation_service import CreationService
from avge_engine.services.document_service import DocumentService
from avge_engine.services.region_service import RegionService
from avge_engine.schema_registry import list_tool_names
from avge_engine.renderer import (
    svg_serialize,
    render_preview_base64,
    render_preview_jpeg,
    render_preview_pdf,
    render_preview_png,
)
from avge_engine.schemas import (
    BatchRequest,
    BooleanOpRequest,
    CheckpointRequest,
    CloneDocumentRequest,
    CopyElementRequest,
    CreateCurveRequest,
    CreateDocumentRequest,
    CreateEllipseRequest,
    CreateLineRequest,
    CreateRectRequest,
    CreateRegionRequest,
    CritiqueRequest,
    DeleteDocumentRequest,
    DeleteRegionRequest,
    DescribeSceneRequest,
    DocIdBody,
    DocIdLimitBody,
    DuplicateGroupRequest,
    EditRegionRequest,
    ExportSvgRequest,
    ExtrudeOutlineRequest,
    FindObjectsRequest,
    ManageGroupRequest,
    PreviewRequest,
    ReorderLayerRequest,
    ToolResponse,
    TransformObjectsRequest,
)


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


# ── Health ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__, "tool_set": __tool_set_version__}


# ── Browser Viewer ─────────────────────────────────────────────────

@app.get("/")
async def viewer_root():
    return Response(
        content=viewer_html(),
        media_type="text/html",
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@app.get("/viewer")
async def viewer():
    return Response(
        content=viewer_html(),
        media_type="text/html",
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@app.get("/viewer/documents")
async def list_documents_viewer(search: str = "", sort: str = "updated", order: str = "desc"):
    docs = DocumentService().list_documents()
    q = search.strip().lower()
    if q:
        docs = [
            d for d in docs
            if q in f"{d.get('name', '')} {d.get('id', '')}".lower()
        ]

    reverse = order.lower() != "asc"
    if sort == "name":
        key = lambda d: (d.get("name") or "").lower()
    elif sort in {"regions", "region_count"}:
        key = lambda d: int(d.get("region_count") or 0)
    elif sort == "version":
        key = lambda d: int(d.get("version") or 0)
    else:
        key = lambda d: d.get("updated") or ""

    docs = sorted(docs, key=key, reverse=reverse)
    return {"documents": docs, "count": len(docs)}


# ── Document Endpoints ─────────────────────────────────────────────

@app.post("/tools/create_document", response_model=ToolResponse)
async def create_document(req: CreateDocumentRequest):
    try:
        doc = DocumentService().create_document(
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
    service = DocumentService()
    try:
        result = service.delete_documents(req.ids, confirm=req.confirm)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result.found:
        raise HTTPException(status_code=404, detail=f"No matching documents found. Not found: {result.missing}")

    if not req.confirm:
        return ToolResponse(data={
            "preview": True,
            "found": [{"id": d["id"], "name": d.get("name", "") or "(unnamed)"} for d in result.found],
            "message": f"Call with confirm=True to delete {len(result.found)} document(s)",
            "not_found": result.missing,
        })

    data = {"deleted": result.deleted}
    if result.errors:
        data["errors"] = result.errors
    return ToolResponse(data=data)


@app.post("/tools/clone_document", response_model=ToolResponse)
async def clone_document(req: CloneDocumentRequest):
    try:
        doc, source_id, region_count = DocumentService().clone_document(
            source_document_id=req.source_document_id,
            name=req.name,
            set_active=req.set_active,
        )
        return ToolResponse(data={
            "source_document_id": source_id,
            "document_id": doc.id,
            "name": doc.name or "",
            "width": doc.width,
            "height": doc.height,
            "region_count": region_count,
        })
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/load_document", response_model=ToolResponse)
async def load_document(req: DocIdBody):
    summary = DocumentService().load_document(req.document_id)
    if summary is not None:
        return ToolResponse(data={
            "document_id": req.document_id,
            "region_count": summary.region_count,
            "version": summary.document["version"],
        })
    raise HTTPException(status_code=404, detail=f"Document '{req.document_id}' not found")


@app.get("/documents")
async def list_documents_api():
    """List all persisted documents."""
    stored = DocumentService().list_documents()
    return ToolResponse(data={"documents": stored, "count": len(stored)})


@app.get("/documents/{document_id}")
async def get_document_info(document_id: str | None = None):
    """Get document metadata + preview link."""
    try:
        summary = DocumentService().ensure_loaded_summary(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return {
        "document": summary.document,
        "regions": summary.regions,
        "region_count": summary.region_count,
        "preview_url": f"/preview/{document_id}.png",
    }


# ── Region Endpoints ───────────────────────────────────────────────

@app.post("/tools/create_region", response_model=ToolResponse)
async def create_region(req: CreateRegionRequest):
    try:
        result = CreationService().create_region(
            outline=req.outline,
            document_id=req.document_id,
            region_id=req.region_id,
            layer=req.layer,
            closed=req.closed,
            smoothness=req.smoothness,
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            fill_gradient=req.fill_gradient,
            smoothness_per_point=req.smoothness_per_point,
            z_index=req.z_index,
            clip_to=req.clip_to,
            blend_mode=req.blend_mode,
            tags=req.tags,
            blur=req.blur,
        )
        return ToolResponse(
            data={
                "region_id": result.region_id,
                "bounds": result.bounds,
                "outline_point_count": result.outline_point_count,
            },
            warnings=result.warnings,
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/edit_region", response_model=ToolResponse)
async def edit_region(req: EditRegionRequest):
    try:
        RegionService().edit_region(
            region_id=req.region_id,
            document_id=req.document_id,
            outline=req.outline,
            smoothness=req.smoothness,
            smoothness_per_point=req.smoothness_per_point,
            fill=req.fill, stroke=req.stroke,
            stroke_width=req.stroke_width, opacity=req.opacity,
            z_index=req.z_index, blend_mode=req.blend_mode,
            clip_to=req.clip_to, layer=req.layer,
            tags=req.tags,
            blur=req.blur,
        )
        return ToolResponse(data={"region_id": req.region_id})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/delete_region", response_model=ToolResponse)
async def delete_region(req: DeleteRegionRequest):
    try:
        deleted = RegionService().delete_regions(document_id=req.document_id, ids=req.ids)
    except RuntimeError:
        raise HTTPException(status_code=404, detail="No active document")
    return ToolResponse(data={"affected": deleted, "count": len(deleted)})



@app.post("/tools/copy_element", response_model=ToolResponse, tags=["copy_element"])
async def copy_element(req: CopyElementRequest):
    try:
        result = RegionService().copy_element(
            source_document_id=req.source_document_id,
            target_document_id=req.target_document_id,
            region_id=req.region_id,
            group_name=req.group,
            new_region_id=req.new_region_id,
            offset_x=req.offset_x,
            offset_y=req.offset_y,
            skip_existing=True,
        )
    except RuntimeError:
        raise HTTPException(status_code=400, detail="No active source document")
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, RuntimeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result.group_name:
        return ToolResponse(data={"copied": result.copied_ids, "count": len(result.copied_ids)})
    return ToolResponse(data={"region_id": result.copied_ids[0] if result.copied_ids else None, "source": req.region_id})


@app.post("/tools/create_rect", response_model=ToolResponse)
async def create_rect(req: CreateRectRequest):
    try:
        result = CreationService().create_rect(
            x=req.x,
            y=req.y,
            width=req.width,
            height=req.height,
            rx=req.rx,
            document_id=req.document_id,
            region_id=req.region_id,
            layer=req.layer,
            z_index=req.z_index,
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"region_id": result.region_id})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/create_ellipse", response_model=ToolResponse)
async def create_ellipse(req: CreateEllipseRequest):
    try:
        result = CreationService().create_ellipse(
            cx=req.cx,
            cy=req.cy,
            rx=req.rx,
            ry=req.ry,
            document_id=req.document_id,
            region_id=req.region_id,
            layer=req.layer,
            z_index=req.z_index,
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"region_id": result.region_id})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/create_line", response_model=ToolResponse)
async def create_line(req: CreateLineRequest):
    try:
        result = CreationService().create_line(
            x1=req.x1,
            y1=req.y1,
            x2=req.x2,
            y2=req.y2,
            document_id=req.document_id,
            region_id=req.region_id,
            layer=req.layer,
            z_index=req.z_index,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"region_id": result.region_id})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Creation Operation Endpoints ───────────────────────────────────

@app.post("/tools/create_curve", response_model=ToolResponse)
async def create_curve(req: CreateCurveRequest):
    try:
        result = CreationService().create_curve(
            points=req.points,
            document_id=req.document_id,
            region_id=req.region_id,
            layer=req.layer,
            z_index=req.z_index,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            smoothness=req.smoothness,
            blend_mode=req.blend_mode,
            stroke_linecap=req.stroke_linecap,
        )
        return ToolResponse(data={
            "region_id": result.region_id,
            "points": result.points,
            "smoothness": result.smoothness,
        })
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/boolean_operation", response_model=ToolResponse)
async def boolean_operation(req: BooleanOpRequest):
    try:
        result = CreationService().boolean_operation(
            operation=req.operation,
            region_ids=req.region_ids,
            new_region_id=req.new_region_id,
            document_id=req.document_id,
            keep_originals=req.keep_originals,
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
        )
        return ToolResponse(data={"region_id": result.region_id, "outline_points": result.outline_points})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/transform_objects", response_model=ToolResponse)
async def transform_objects(req: TransformObjectsRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
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


@app.post("/tools/edit_group", response_model=ToolResponse)
async def edit_group(req: ManageGroupRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
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
async def list_groups(req: DocIdBody):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    groups = graph.list_groups(req.document_id)
    return ToolResponse(data={"groups": groups, "count": len(groups)})


@app.post("/tools/duplicate_group", response_model=ToolResponse)
async def duplicate_group(req: DuplicateGroupRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
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


@app.post("/tools/add_bumps", response_model=ToolResponse)
async def add_bumps(req: ExtrudeOutlineRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
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

@app.post("/tools/describe_scene")
async def describe_scene(req: DescribeSceneRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
    desc = graph.describe_scene(detail=req.detail, filter_layer=req.filter_layer, document_id=req.document_id)
    return {
        "document": desc["document"],
        "regions": desc["regions"],
        "region_count": desc["region_count"],
        "warnings": desc.get("warnings", []),
    }


@app.post("/tools/find_objects", response_model=ToolResponse)
async def find_objects(req: FindObjectsRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
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


@app.post("/tools/critique", response_model=ToolResponse)
async def critique(req: CritiqueRequest):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    rules = graph.critique_composition(req.document_id) if req.mode in ("rules", "both") else []
    visual = [
        f for f in graph.critique_preview_quality(req.document_id)
        if f.get("confidence", 0.0) >= req.min_confidence
    ] if req.mode in ("visual", "both") else []
    return ToolResponse(data={
        "mode": req.mode,
        "rules": {"findings": rules, "count": len(rules)},
        "visual": {"findings": visual, "count": len(visual)},
        "count": len(rules) + len(visual),
    })


@app.post("/tools/list_layers", response_model=ToolResponse)
async def list_layers(req: DocIdBody):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    layers = graph.list_layers(req.document_id)
    return ToolResponse(data={"layers": layers})


@app.post("/tools/shift_layer_z", response_model=ToolResponse)
async def reorder_layer(req: ReorderLayerRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
    count = graph.reorder_layer(req.layer, req.z_offset, req.document_id)
    return ToolResponse(data={"layer": req.layer, "z_offset": req.z_offset, "count": count})


@app.post("/tools/render_preview", response_model=ToolResponse)
async def render_preview(req: PreviewRequest):
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No active document")
    svg = svg_serialize(
        graph,
        req.document_id,
        exclude_layers=req.exclude_layers,
        exclude_region_ids=req.exclude_region_ids,
        exclude_prefixes=req.exclude_prefixes,
    )
    try:
        b64 = render_preview_base64(svg, scale=max(0.25, min(2.0, req.scale)))
        return ToolResponse(data={"preview": b64})
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/export_svg", response_model=ToolResponse)
async def export_svg(req: ExportSvgRequest):
    from pathlib import Path
    graph = get_graph()
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=404, detail="No active document")
    svg = svg_serialize(
        graph,
        req.document_id,
        exclude_layers=req.exclude_layers,
        exclude_region_ids=req.exclude_region_ids,
        exclude_prefixes=req.exclude_prefixes,
    )
    path = Path(req.filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg)
    return ToolResponse(data={"filepath": str(path.resolve()), "chars": len(svg)})


# ── Preview (direct PNG) ───────────────────────────────────────────

@app.get("/preview/{document_id}.png")
async def preview_doc_png(document_id: str | None = None):
    """Render a PNG preview of a specific document by ID."""
    graph = get_graph()
    # Reload from disk on every render to pick up MCP-side edits
    if not graph.load_document(document_id):
        return Response(f"Document '{document_id}' not found", status_code=404)
    try:
        svg = svg_serialize(graph, document_id)
        png = render_preview_png(svg, scale=1.0)
        return Response(
            content=png,
            media_type="image/png",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


@app.get("/preview/{document_id}.svg")
async def preview_doc_svg(document_id: str | None = None):
    """Render an SVG preview of a specific document by ID."""
    graph = get_graph()
    if not graph.load_document(document_id):
        return Response(f"Document '{document_id}' not found", status_code=404)
    try:
        svg = svg_serialize(graph, document_id)
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


@app.get("/download/{document_id}.{fmt}")
async def download_document(document_id: str, fmt: str):
    """Download a document as SVG, PNG, JPG, or PDF."""
    graph = get_graph()
    if not graph.load_document(document_id):
        return Response(f"Document '{document_id}' not found", status_code=404)

    doc = graph.get_document(document_id)
    safe_name = _download_name(doc.name or document_id)
    fmt = fmt.lower()

    try:
        svg = svg_serialize(graph, document_id)
        if fmt == "svg":
            content = svg.encode("utf-8")
            media_type = "image/svg+xml"
        elif fmt == "png":
            content = render_preview_png(svg, scale=1.0)
            media_type = "image/png"
        elif fmt in {"jpg", "jpeg"}:
            fmt = "jpg"
            content = render_preview_jpeg(svg, scale=1.0)
            media_type = "image/jpeg"
        elif fmt == "pdf":
            content = render_preview_pdf(svg)
            media_type = "application/pdf"
        else:
            return Response("Unsupported format. Use svg, png, jpg, or pdf.", status_code=400)
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store, must-revalidate",
            "Content-Disposition": f'attachment; filename="{safe_name}.{fmt}"',
        },
    )


def _download_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip(".-")
    return safe[:80] or "avge-document"


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
async def get_history(req: DocIdLimitBody):
    graph = get_graph()
    if not graph.has_document(req.document_id):
        raise HTTPException(status_code=400, detail="Document not found")
    doc_id = req.document_id
    history = graph.list_checkpoints(doc_id)
    meta_store = getattr(graph, "_checkpoint_meta", {})
    entries = []
    for name in history[:req.limit]:
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
    doc_id = req.document_id or graph._last_doc_id
    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No document")

    # Dynamic dispatch: route each op to graph.<tool_name>(**params)
    results: list[dict] = []
    for op in req.ops:
        tool_name = op.pop("tool", None)
        if not tool_name:
            results.append({"status": "error", "message": "Missing 'tool' key"})
            continue

        method = getattr(graph, tool_name, None)
        if method is None:
            results.append({"status": "error", "message": f"Unknown tool: {tool_name}"})
            continue

        try:
            result = method(**op, document_id=req.document_id)
            if isinstance(result, str):
                results.append({"status": "ok", "message": result[:120]})
            else:
                rid = getattr(result, "id", None)
                results.append({"status": "ok", "region_id": rid or str(result)})
        except (ValueError, RuntimeError, TypeError, KeyError) as e:
            results.append({"status": "error", "message": str(e)})

    return ToolResponse(data={"results": results})


@app.get("/tools/docs")
async def tool_docs():
    """Generate markdown documentation for all registered MCP tools."""
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("avge-engine-docs")
    from avge_engine.controllers import register_all
    register_all(mcp)
    tools = mcp._tool_manager.list_tools()
    from avge_engine import __tool_set_version__ as tsv
    lines = [f"# AVGE Engine — Tool Reference ({len(tools)} tools)\n"]
    lines.append(f"_Tool set: {tsv}_\n")

    for t in sorted(tools, key=lambda x: x.name):
        lines.append(f"## `{t.name}`\n")
        lines.append(f"{t.description}\n")
        if hasattr(t, 'parameters') and t.parameters:
            props = t.parameters.get("properties", {})
            required = t.parameters.get("required", [])
            if props:
                lines.append("### Parameters\n")
                lines.append("| Name | Type | Required | Description |")
                lines.append("|------|------|----------|-------------|")
                for pname, pdef in sorted(props.items()):
                    ptype = pdef.get("type", "any")
                    is_req = "✓" if pname in required else ""
                    pdesc = pdef.get("description", "").replace("\n", " ").strip()
                    lines.append(f"| `{pname}` | `{ptype}` | {is_req} | {pdesc} |")
                lines.append("")
        lines.append("---\n")

    return Response(content="\n".join(lines), media_type="text/markdown")


@app.post("/tools/reset")
async def reset():
    """Reset the scene graph (test/debug endpoint)."""
    reset_graph()
    return ToolResponse(data={"message": "Scene graph reset"})


# ── Generic Tool Dispatch ───────────────────────────────────────────
# All MCP tools are also accessible via REST using a unified endpoint.
# The tool name maps to the scene graph method name.

@app.post("/tools/{tool_name}")
async def tool_dispatch(tool_name: str, body: dict):
    """Generic dispatch — route any tool call to the scene graph method.

    The ``tool_name`` path segment matches the MCP tool name. Parameters
    are passed as a JSON body dict. This avoids maintaining individual
    endpoints for every tool.
    """
    graph = get_graph()
    doc_id = body.pop("document_id", None) or graph._last_doc_id

    if not doc_id or not graph.has_document(doc_id):
        raise HTTPException(status_code=400, detail="No active document")

    method = getattr(graph, tool_name, None)
    if method is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    try:
        result = method(**body, document_id=doc_id)
        if hasattr(result, "model_dump"):
            return ToolResponse(data=result.model_dump())
        rid = getattr(result, "id", None)
        return ToolResponse(data={"region_id": rid} if rid else {"result": str(result)[:200]})
    except (ValueError, RuntimeError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Schema Discovery ───────────────────────────────────────────────

@app.get("/schemas")
async def list_schemas():
    return {"tools": list_tool_names()}
