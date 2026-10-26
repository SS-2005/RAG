import pytest
import os
from app.rag_engine import RAGEngine

USER_DOC_PATH = "sample_data/cyber_arena_synopsis.docx"

@pytest.mark.asyncio
async def test_vm_count_query():
    assert os.path.exists(USER_DOC_PATH)
    engine = RAGEngine()
    with open(USER_DOC_PATH, "rb") as f:
        engine.ingest_docx("cyber_arena_synopsis.docx", f.read())

    res = await engine.answer_query("how many vms are being used in this ?", provider="offline")
    assert res["success"] is True
    assert len(res["sources"]) > 0

    # Ensure retrieved chunks include the section discussing VMs
    found_vm_reference = any("virtual machine" in s["text"].lower() or "vm" in s["text"].lower() for s in res["sources"])
    assert found_vm_reference, "Failed to retrieve VM context chunks!"
    # Ensure answer reflects 2 virtual machines
    assert "two" in res["answer"].lower() or "2" in res["answer"], f"Expected 'two' or '2' in answer: {res['answer']}"

@pytest.mark.asyncio
async def test_members_query():
    assert os.path.exists(USER_DOC_PATH)
    engine = RAGEngine()
    with open(USER_DOC_PATH, "rb") as f:
        engine.ingest_docx("cyber_arena_synopsis.docx", f.read())

    res = await engine.answer_query("who are the members of the group", provider="offline")
    assert res["success"] is True
    assert len(res["sources"]) > 0

    # Ensure student names appear in retrieved sources
    found_student = any("pranav" in s["text"].lower() or "shivam" in s["text"].lower() for s in res["sources"])
    assert found_student, "Failed to retrieve student member chunks!"
    assert "pranav" in res["answer"].lower() or "shivam" in res["answer"].lower()

@pytest.mark.asyncio
async def test_guide_query():
    engine = RAGEngine()
    with open(USER_DOC_PATH, "rb") as f:
        engine.ingest_docx("cyber_arena_synopsis.docx", f.read())

    res = await engine.answer_query("who is the project guide", provider="offline")
    assert res["success"] is True
    assert any("anuja" in s["text"].lower() for s in res["sources"])
