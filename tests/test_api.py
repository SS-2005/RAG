import os
import pytest
import httpx
from app.main import app, rag_engine

SAMPLE_DOC_PATH = "sample_data/ai_architecture_brief.docx"

@pytest.mark.asyncio
async def test_api_health_and_index():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200

@pytest.mark.asyncio
async def test_api_upload_docx():
    rag_engine.reset()
    assert os.path.exists(SAMPLE_DOC_PATH)

    with open(SAMPLE_DOC_PATH, "rb") as f:
        file_bytes = f.read()

    files = {"file": ("test_doc.docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "document" in data
    assert data["document"]["chunk_count"] > 0

@pytest.mark.asyncio
async def test_api_query_grounded():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/query",
            json={
                "query": "What are the hardware requirements and VRAM target?",
                "provider": "offline",
                "top_k": 3
            }
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "sources" in data
    assert len(data["sources"]) > 0

@pytest.mark.asyncio
async def test_api_stream_query():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/query/stream",
            json={
                "query": "What are the hardware requirements?",
                "provider": "offline",
                "top_k": 3
            }
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    content = response.text
    assert "sources" in content
    assert "done" in content

@pytest.mark.asyncio
async def test_api_chunks_inspection():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/chunks")
    assert response.status_code == 200
    data = response.json()
    assert "chunks" in data
    assert len(data["chunks"]) > 0

@pytest.mark.asyncio
async def test_api_reset():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/reset")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # After reset, query should fail with 400
        query_res = await client.post(
            "/api/query",
            json={"query": "test query", "provider": "offline"}
        )
        assert query_res.status_code == 400
