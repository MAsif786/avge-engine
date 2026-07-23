"""
FastAPI HTTP server — the underlying API layer beneath the MCP interface.

§12: The engine maintains a plain HTTP/FastAPI surface for non-MCP clients
(debug tooling, direct API access, integration tests), though MCP is the
primary LLM-facing interface.

M0b scope: single-process, no auth, in-memory documents.
Mirrors the MCP tool set at avge_engine/controllers/ — keep in sync.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from avge_engine import __version__, __tool_set_version__
from avge_engine.api_viewer import viewer_html
from avge_engine.services.engine import reset_documents
from avge_engine.services.creation_service import CreationService
from avge_engine.services.document_service import DocumentService
from avge_engine.services.document_structure_service import DocumentStructureService
from avge_engine.services.inspection_service import InspectionService
from avge_engine.services.rendering_service import RenderingService
from avge_engine.services.transform_service import TransformService
from avge_engine.services.history_service import HistoryService
from avge_engine.services.element_service import ElementService
from avge_engine.services.tool_execution_service import ToolExecutionService
from avge_engine.schema_registry import list_tool_names
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
    CreateElementRequest,
    CritiqueRequest,
    DeleteDocumentRequest,
    DeleteElementRequest,
    DescribeSceneRequest,
    DocIdBody,
    DocIdLimitBody,
    DuplicateGroupRequest,
    EditElementRequest,
    ExportSvgRequest,
    ExtrudeOutlineRequest,
    FindObjectsRequest,
    ManageGroupRequest,
    PreviewRequest,
    ReorderLayerRequest,
    ToolResponse,
    TransformObjectsRequest,
)

MAX_VIEWER_IMAGE_PROXY_BYTES = 20_000_000


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
    elif sort in {"elements", "element_count"}:
        key = lambda d: int(d.get("element_count") or 0)
    elif sort == "version":
        key = lambda d: int(d.get("version") or 0)
    else:
        key = lambda d: d.get("updated") or ""

    named_docs = [d for d in docs if (d.get("name") or "").strip()]
    unnamed_docs = [d for d in docs if not (d.get("name") or "").strip()]
    docs = (
        sorted(named_docs, key=key, reverse=reverse)
        + sorted(unnamed_docs, key=key, reverse=reverse)
    )
    return {"documents": docs, "count": len(docs)}


@app.get("/viewer/image-proxy")
async def viewer_image_proxy(url: str):
    """Fetch an image URL for browser-side raster export when CORS blocks direct fetch."""
    try:
        raw, mime = _read_viewer_image_url(url)
    except ValueError as e:
        return Response(str(e), status_code=400)
    except Exception as e:
        return Response(f"Image proxy error: {e}", status_code=502)

    if not mime.startswith("image/"):
        return Response(f"URL did not return an image content type: {mime}", status_code=400)

    return Response(
        content=raw,
        media_type=mime,
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


@app.get("/viewer/{document_id}/versions")
async def list_document_versions_viewer(document_id: str):
    try:
        versions = HistoryService().versions(document_id=document_id)
    except ValueError:
        return Response(f"Document '{document_id}' not found", status_code=404)
    return {"document_id": document_id, "versions": versions, "count": len(versions)}


@app.get("/viewer/{document_id}")
async def viewer_document(document_id: str):
    return Response(
        content=viewer_html(),
        media_type="text/html",
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


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
        doc, source_id, element_count = DocumentService().clone_document(
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
            "element_count": element_count,
        })
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
        "elements": summary.elements,
        "element_count": summary.element_count,
        "preview_url": f"/preview/{document_id}.png",
    }


# ── Element Endpoints ───────────────────────────────────────────────

@app.post("/tools/create_element", response_model=ToolResponse)
async def create_element(req: CreateElementRequest):
    try:
        result = CreationService().create_element(
            outline=req.outline,
            document_id=req.document_id,
            element_id=req.element_id,
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
                "element_id": result.element_id,
                "bounds": result.bounds,
                "outline_point_count": result.outline_point_count,
            },
            warnings=result.warnings,
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/edit_element", response_model=ToolResponse)
async def edit_element(req: EditElementRequest):
    try:
        ElementService().edit_element(
            element_id=req.element_id,
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
        return ToolResponse(data={"element_id": req.element_id})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/delete_element", response_model=ToolResponse)
async def delete_element(req: DeleteElementRequest):
    try:
        deleted = ElementService().delete_elements(document_id=req.document_id, ids=req.ids)
    except RuntimeError:
        raise HTTPException(status_code=404, detail="No active document")
    return ToolResponse(data={"affected": deleted, "count": len(deleted)})



@app.post("/tools/copy_element", response_model=ToolResponse, tags=["copy_element"])
async def copy_element(req: CopyElementRequest):
    try:
        result = ElementService().copy_element(
            source_document_id=req.source_document_id,
            target_document_id=req.target_document_id,
            element_id=req.element_id,
            group_name=req.group,
            new_element_id=req.new_element_id,
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
    return ToolResponse(data={"element_id": result.copied_ids[0] if result.copied_ids else None, "source": req.element_id})


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
            element_id=req.element_id,
            layer=req.layer,
            z_index=req.z_index,
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"element_id": result.element_id})
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
            element_id=req.element_id,
            layer=req.layer,
            z_index=req.z_index,
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"element_id": result.element_id})
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
            element_id=req.element_id,
            layer=req.layer,
            z_index=req.z_index,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
            blend_mode=req.blend_mode,
        )
        return ToolResponse(data={"element_id": result.element_id})
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
            element_id=req.element_id,
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
            "element_id": result.element_id,
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
            element_ids=req.element_ids,
            new_element_id=req.new_element_id,
            document_id=req.document_id,
            keep_originals=req.keep_originals,
            fill=req.fill,
            stroke=req.stroke,
            stroke_width=req.stroke_width,
            opacity=req.opacity,
        )
        return ToolResponse(data={"element_id": result.element_id, "outline_points": result.outline_points})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/transform_objects", response_model=ToolResponse)
async def transform_objects(req: TransformObjectsRequest):
    try:
        result = TransformService().transform_objects(
            ids=req.ids,
            document_id=req.document_id,
            dx=req.dx,
            dy=req.dy,
            scale=req.scale,
            sx=req.sx,
            sy=req.sy,
            rotate=req.rotate,
            group_mode=req.group_mode,
            pivot_x=req.pivot_x,
            pivot_y=req.pivot_y,
            pivot_mode=req.pivot_mode,
            z_index=req.z_index,
            group_name=req.group_name,
            mirror_x=req.mirror_x,
            mirror_y=req.mirror_y,
        )
        return ToolResponse(data={"affected": result["affected"], "count": result["count"]})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/edit_group", response_model=ToolResponse)
async def edit_group(req: ManageGroupRequest):
    try:
        result = DocumentStructureService().edit_group(
            action=req.action,
            group_name=req.group_name,
            element_ids=req.element_ids,
            document_id=req.document_id,
        )
        if req.action == "delete" and not result["deleted"]:
            raise HTTPException(status_code=404, detail=f"Group '{req.group_name}' not found")
        return ToolResponse(data=result)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/list_groups", response_model=ToolResponse)
async def list_groups(req: DocIdBody):
    try:
        groups = DocumentStructureService().list_groups(document_id=req.document_id)
        return ToolResponse(data={"groups": groups, "count": len(groups)})
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/duplicate_group", response_model=ToolResponse)
async def duplicate_group(req: DuplicateGroupRequest):
    try:
        return ToolResponse(data=DocumentStructureService().duplicate_group(
            group_name=req.group_name,
            document_id=req.document_id,
            new_prefix=req.new_prefix,
            dx=req.dx, dy=req.dy, scale=req.scale,
            sx=req.sx, sy=req.sy, rotate=req.rotate,
            mirror_x=req.mirror_x, mirror_y=req.mirror_y,
        ))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/add_bumps", response_model=ToolResponse)
async def add_bumps(req: ExtrudeOutlineRequest):
    try:
        return ToolResponse(data=ElementService().add_bumps(
            element_id=req.element_id,
            document_id=req.document_id,
            segment_indices=req.segment_indices,
            extrusion_length=req.extrusion_length,
            extrusion_width=req.extrusion_width,
            angle_offset=req.angle_offset,
            direction=req.direction,
            shape=req.shape,
        ))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Query / View Endpoints ─────────────────────────────────────────

@app.post("/tools/describe_scene")
async def describe_scene(req: DescribeSceneRequest):
    try:
        desc = InspectionService().describe_scene(
            document_id=req.document_id,
            detail=req.detail,
            filter_layer=req.filter_layer,
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "document": desc["document"],
        "elements": desc["elements"],
        "element_count": desc["element_count"],
        "warnings": desc.get("warnings", []),
    }


@app.post("/tools/find_objects", response_model=ToolResponse)
async def find_objects(req: FindObjectsRequest):
    try:
        results = InspectionService().find_objects(
            document_id=req.document_id,
            fill=req.fill,
            min_x=req.min_x, max_x=req.max_x,
            min_y=req.min_y, max_y=req.max_y,
            min_w=req.min_w, max_w=req.max_w,
            min_h=req.min_h, max_h=req.max_h,
            layer=req.layer,
            has_stroke=req.has_stroke,
            tags=req.tags,
        )
        return ToolResponse(data={"results": results, "count": len(results)})
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/critique", response_model=ToolResponse)
async def critique(req: CritiqueRequest):
    try:
        return ToolResponse(data=InspectionService().critique(
            document_id=req.document_id,
            mode=req.mode,
            min_confidence=req.min_confidence,
        ))
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/list_layers", response_model=ToolResponse)
async def list_layers(req: DocIdBody):
    try:
        layers = DocumentStructureService().list_layers(document_id=req.document_id)
        return ToolResponse(data={"layers": layers})
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/shift_layer_z", response_model=ToolResponse)
async def reorder_layer(req: ReorderLayerRequest):
    try:
        count = DocumentStructureService().shift_layer_z(
            layer=req.layer,
            z_offset=req.z_offset,
            document_id=req.document_id,
        )
        return ToolResponse(data={"layer": req.layer, "z_offset": req.z_offset, "count": count})
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools/render_preview", response_model=ToolResponse)
async def render_preview(req: PreviewRequest):
    try:
        b64 = RenderingService().preview_base64(
            document_id=req.document_id,
            scale=req.scale,
            exclude_layers=req.exclude_layers,
            exclude_element_ids=req.exclude_element_ids,
            exclude_prefixes=req.exclude_prefixes,
        )
        return ToolResponse(data={"preview": b64})
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tools/export_svg", response_model=ToolResponse)
async def export_svg(req: ExportSvgRequest):
    try:
        return ToolResponse(data=RenderingService().export_svg(
            filepath=req.filepath,
            document_id=req.document_id,
            exclude_layers=req.exclude_layers,
            exclude_element_ids=req.exclude_element_ids,
            exclude_prefixes=req.exclude_prefixes,
        ))
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Preview (direct PNG) ───────────────────────────────────────────

@app.get("/preview/{document_id}.png")
async def preview_doc_png(document_id: str | None = None):
    """Render a PNG preview of a specific document by ID."""
    try:
        png = RenderingService().preview_png(document_id=document_id, scale=1.0)
    except ValueError:
        return Response(f"Document '{document_id}' not found", status_code=404)
    try:
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
    try:
        svg = RenderingService().svg(document_id=document_id, load_from_storage=True)
    except ValueError:
        return Response(f"Document '{document_id}' not found", status_code=404)
    try:
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


@app.get("/preview/{document_id}/versions/{checkpoint_name}.svg")
async def preview_doc_version_svg(document_id: str, checkpoint_name: str):
    """Render an SVG preview of a checkpoint without restoring it."""
    try:
        doc, elements = HistoryService().snapshot_document(
            document_id=document_id,
            checkpoint_name=checkpoint_name,
        )
        from avge_engine.renderer import svg_serialize_document
        svg = svg_serialize_document(doc, elements)
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )
    except KeyError:
        return Response(
            f"Checkpoint '{checkpoint_name}' not found for document '{document_id}'",
            status_code=404,
        )
    except ValueError:
        return Response(f"Document '{document_id}' not found", status_code=404)
    except Exception as e:
        return Response(f"Error: {e}", status_code=500)


@app.get("/download/{document_id}.{fmt}")
async def download_document(document_id: str, fmt: str):
    """Download a document as SVG.

    The browser viewer rasterizes PNG/JPG/PDF client-side from SVG so it does
    not depend on the server PNG renderer.
    """
    try:
        safe_name, content = RenderingService().download_svg(document_id=document_id)
    except ValueError:
        return Response(f"Document '{document_id}' not found", status_code=404)

    fmt = fmt.lower()

    try:
        if fmt != "svg":
            return Response(
                "Unsupported server download format. Use /viewer for browser-side PNG, JPG, and PDF export.",
                status_code=400,
            )
        media_type = "image/svg+xml"
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


def _read_viewer_image_url(url: str) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        req = Request(url, headers={"User-Agent": "AVGE/0.5"})
        with urlopen(req, timeout=20) as response:
            mime = response.headers.get_content_type() or "application/octet-stream"
            raw = response.read(MAX_VIEWER_IMAGE_PROXY_BYTES + 1)
    elif parsed.scheme == "file":
        path = Path(parsed.path).expanduser()
        raw = path.read_bytes()
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    elif parsed.scheme:
        raise ValueError(f"Unsupported image URL scheme: {parsed.scheme}")
    else:
        path = Path(url).expanduser()
        raw = path.read_bytes()
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    if len(raw) > MAX_VIEWER_IMAGE_PROXY_BYTES:
        raise ValueError(f"Image too large for browser raster export proxy (max {MAX_VIEWER_IMAGE_PROXY_BYTES} bytes)")
    return raw, mime


# ── History Endpoints ──────────────────────────────────────────────

@app.post("/tools/checkpoint", response_model=ToolResponse)
async def checkpoint(req: CheckpointRequest):
    try:
        data = HistoryService().checkpoint(name=req.name, document_id=req.document_id)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ToolResponse(data=data)


@app.post("/tools/restore", response_model=ToolResponse)
async def restore(req: CheckpointRequest):
    try:
        data = HistoryService().restore(name=req.name, document_id=req.document_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError:
        raise HTTPException(status_code=404, detail=f"Checkpoint '{req.name}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ToolResponse(data=data)


@app.post("/tools/get_history", response_model=ToolResponse)
async def get_history(req: DocIdLimitBody):
    try:
        entries = HistoryService().entries(document_id=req.document_id, limit=req.limit)
    except ValueError:
        raise HTTPException(status_code=400, detail="Document not found")
    return ToolResponse(data={
        "history": [entry.model_dump() for entry in entries],
        "count": len(entries),
    })


@app.post("/tools/batch", response_model=ToolResponse)
async def batch(req: BatchRequest):
    try:
        results = ToolExecutionService().execute_batch(req.ops, document_id=req.document_id)
    except RuntimeError:
        raise HTTPException(status_code=400, detail="No document")
    return ToolResponse(data={"results": [result.as_api_dict() for result in results]})


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
    """Reset in-memory documents (test/debug endpoint)."""
    reset_documents()
    return ToolResponse(data={"message": "Documents reset"})


# ── Generic Tool Dispatch ───────────────────────────────────────────
# All MCP tools are also accessible via REST using a unified endpoint.
# The tool name maps to the document/tool method name.

@app.post("/tools/{tool_name}")
async def tool_dispatch(tool_name: str, body: dict):
    """Generic dispatch — route any tool call to the document/tool method.

    The ``tool_name`` path segment matches the MCP tool name. Parameters
    are passed as a JSON body dict. This avoids maintaining individual
    endpoints for every tool.
    """
    params = dict(body)
    doc_id = params.pop("document_id", None)
    result = ToolExecutionService().execute_tool(tool_name, params, document_id=doc_id)
    if result.status == "error" and result.message.startswith("Unknown tool:"):
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return ToolResponse(data=result.as_api_dict())


# ── Schema Discovery ───────────────────────────────────────────────

@app.get("/schemas")
async def list_schemas():
    return {"tools": list_tool_names()}
