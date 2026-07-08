"""
M0b test suite — FastAPI HTTP server integration tests.
"""

import pytest
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

    async def test_schemas(self, client):
        r = await client.get("/schemas")
        assert r.status_code == 200
        data = r.json()
        assert len(data["tools"]) >= 4


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

    async def test_style_objects(self, client, doc_id):
        await client.post("/tools/create_region", json={
            "outline": [[0, 0], [1, 0], [1, 1]],
            "region_id": "r1",
            "document_id": doc_id,
        })
        r = await client.post("/tools/style_objects", json={
            "ids": ["r1"],
            "document_id": doc_id,
            "fill": "#00FF00",
            "stroke_width": 0.02,
        })
        assert r.status_code == 200
        assert r.json()["data"]["count"] == 1


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
