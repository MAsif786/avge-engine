"""
M0b test suite — FastAPI HTTP server integration tests.
"""

import pytest
from uuid import uuid4
from httpx import ASGITransport, AsyncClient

from avge_engine.api import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/tools/reset")
        yield c


@pytest.fixture
async def doc_id(client):
    """Create a document and return its ID."""
    r = await client.post("/tools/create_document", json={})
    return r.json()["data"]["document_id"]


class TestHealth:
    async def test_health(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    async def test_viewer_html(self, client):
        r = await client.get("/viewer")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "AVGE Documents" in r.text
        assert "/viewer/documents" in r.text
        assert "docIdFromRoute" in r.text
        assert "history.pushState" in r.text
        assert "deleteSelectedDocument" in r.text
        assert "/tools/delete_document" in r.text
        assert "fetchSvgText" in r.text
        assert "fetchImageForRasterExport" in r.text
        assert "/viewer/image-proxy" in r.text
        assert "inlineSvgImagesInBrowser" in r.text
        assert "blobToDataUrl" in r.text
        assert "rasterizeSvg" in r.text
        assert "imageBlobToPdf" in r.text
        assert 'encoder.encode("%PDF-1.4' not in r.text
        assert "encoder.encode(`%PDF-1.4" in r.text

    async def test_viewer_document_route(self, client):
        r = await client.get("/viewer/doc_test_route")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "docIdFromRoute" in r.text

    async def test_schemas(self, client):
        r = await client.get("/schemas")
        assert r.status_code == 200
        data = r.json()
        assert len(data["tools"]) >= 4

    async def test_openapi_schema(self, client):
        r = await client.get("/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "/tools/copy_element" in data["paths"]


class TestDocument:
    async def test_create_document(self, client):
        r = await client.post("/tools/create_document", json={
            "width": 800, "height": 600, "background": "#F0F0F0",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "document_id" in data["data"]

    async def test_create_document_twice(self, client):
        """Multi-document: creating twice returns OK with different IDs."""
        r1 = await client.post("/tools/create_document", json={})
        assert r1.status_code == 200
        r2 = await client.post("/tools/create_document", json={})
        assert r2.status_code == 200

    async def test_create_document_invalid_width(self, client):
        r = await client.post("/tools/create_document", json={"width": 9999})
        assert r.status_code == 422  # validation error

    async def test_clone_document(self, client):
        created = await client.post("/tools/create_document", json={
            "width": 800,
            "height": 600,
            "name": "source",
        })
        source_id = created.json()["data"]["document_id"]
        region = await client.post("/tools/create_region", json={
            "document_id": source_id,
            "region_id": "panel",
            "outline": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
            "fill": "#336699",
        })
        assert region.status_code == 200

        cloned = await client.post("/tools/clone_document", json={
            "source_document_id": source_id,
            "name": "copy",
        })

        assert cloned.status_code == 200
        data = cloned.json()["data"]
        assert data["document_id"] != source_id
        assert data["name"] == "copy"
        assert data["width"] == 800
        assert data["region_count"] == 1

    async def test_viewer_documents_search_and_sort(self, client):
        unique_name = f"ViewerSearchUniqueApiDoc-{uuid4().hex}"
        await client.post("/tools/create_document", json={"name": unique_name})
        await client.post("/tools/create_document", json={"name": "Beta"})

        r = await client.get("/viewer/documents", params={
            "search": unique_name,
            "sort": "name",
            "order": "asc",
        })

        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["documents"][0]["name"] == unique_name

    async def test_download_svg(self, client):
        created = await client.post("/tools/create_document", json={"name": "Download Doc"})
        document_id = created.json()["data"]["document_id"]

        r = await client.get(f"/download/{document_id}.svg")

        assert r.status_code == 200
        assert "image/svg+xml" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]
        assert "<svg" in r.text

    async def test_download_png_is_browser_side_only(self, client):
        created = await client.post("/tools/create_document", json={"name": "Browser Raster Doc"})
        document_id = created.json()["data"]["document_id"]

        r = await client.get(f"/download/{document_id}.png")

        assert r.status_code == 400
        assert "browser-side PNG" in r.text

    async def test_viewer_image_proxy_rejects_unsupported_scheme(self, client):
        r = await client.get("/viewer/image-proxy", params={"url": "ftp://example.com/image.png"})

        assert r.status_code == 400
        assert "Unsupported image URL scheme" in r.text

    async def test_viewer_image_proxy_serves_local_image(self, client, tmp_path):
        image_path = tmp_path / "tiny.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

        r = await client.get("/viewer/image-proxy", params={"url": str(image_path)})

        assert r.status_code == 200
        assert "image/png" in r.headers["content-type"]
        assert r.content.startswith(b"\x89PNG")


class TestRegion:
    async def test_create_region_no_document(self, client):
        r = await client.post("/tools/create_region", json={
            "outline": [[0.1, 0.1], [0.5, 0.8], [0.9, 0.1]],
        })
        assert r.status_code == 400

    async def test_create_region(self, client, doc_id):
        r = await client.post("/tools/create_region", json={
            "outline": [[0.1, 0.1], [0.5, 0.8], [0.9, 0.1]],
            "region_id": "tri",
            "document_id": doc_id,
            "fill": "#FF0000",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["data"]["region_id"] == "tri"

    async def test_create_region_missing_outline(self, client, doc_id):
        r = await client.post("/tools/create_region", json={"document_id": doc_id})
        assert r.status_code == 422  # validation error


class TestDescribe:
    async def test_describe_scene(self, client, doc_id):
        await client.post("/tools/create_region", json={
            "outline": [[0, 0], [1, 0], [1, 1]],
            "region_id": "r1",
            "document_id": doc_id,
        })
        r = await client.post("/tools/describe_scene", json={"detail": "summary", "document_id": doc_id})
        assert r.status_code == 200
        data = r.json()
        assert data["region_count"] == 1
        assert data["regions"][0]["id"] == "r1"

    async def test_describe_scene_empty(self, client, doc_id):
        r = await client.post("/tools/describe_scene", json={"document_id": doc_id})
        assert r.status_code == 200
        assert r.json()["region_count"] == 0


class TestPreview:
    async def test_render_preview(self, client, doc_id):
        await client.post("/tools/create_region", json={
            "outline": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "fill": "#FF0000",
            "document_id": doc_id,
        })
        r = await client.post("/tools/render_preview", json={"scale": 0.5, "document_id": doc_id})
        assert r.status_code == 200
        data = r.json()
        assert "preview" in data["data"]
        assert data["data"]["preview"].startswith("data:image/png;base64,")

    async def test_render_preview_no_document(self, client):
        r = await client.post("/tools/render_preview", json={})
        assert r.status_code == 400
