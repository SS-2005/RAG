import pytest
import os
from app.rag_engine import RAGEngine

SAMPLE_DOC_PATH = "sample_data/ai_architecture_brief.docx"

@pytest.mark.asyncio
async def test_rag_ingest_and_grounded_answer():
    engine = RAGEngine()
    assert not engine.has_document()

    with open(SAMPLE_DOC_PATH, "rb") as f:
        doc_bytes = f.read()

    doc_info = engine.ingest_docx("test_report.docx", doc_bytes)
    assert engine.has_document()
    assert doc_info["chunk_count"] > 0

    # Query using offline grounded mode
    res = await engine.answer_query(
        query="What is the RAM limit ceiling specified for Project Titan?",
        provider="offline"
    )

    assert res["success"] is True
    assert len(res["sources"]) > 0
    # Must retrieve chunk mentioning 16 GB unified RAM
    assert any("16 GB" in s["text"] for s in res["sources"])

@pytest.mark.asyncio
async def test_rag_unrelated_query_grounding():
    engine = RAGEngine()
    with open(SAMPLE_DOC_PATH, "rb") as f:
        engine.ingest_docx("test_report.docx", f.read())

    # Completely unrelated question with no keyword match
    res = await engine.answer_query(
        query="xyzjkldfs unique meaningless nonsense query that does not exist",
        provider="offline"
    )

    assert res["success"] is True
    assert "I cannot find the answer in the uploaded document" in res["answer"]
