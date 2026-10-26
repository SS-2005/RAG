import pytest
import os
from app.docx_parser import DocxParser, DocxParsingError

SAMPLE_DOC_PATH = "sample_data/ai_architecture_brief.docx"

def test_parse_valid_docx():
    assert os.path.exists(SAMPLE_DOC_PATH)
    with open(SAMPLE_DOC_PATH, "rb") as f:
        file_bytes = f.read()

    result = DocxParser.extract_text(file_bytes)
    assert "full_text" in result
    assert result["paragraph_count"] > 0
    assert result["char_count"] > 100
    assert "Project Titan" in result["full_text"]
    assert "Hardware Requirements" in result["full_text"]
    # Check that table content was parsed
    assert "Edge Lightweight" in result["full_text"]

def test_parse_empty_bytes():
    with pytest.raises(DocxParsingError):
        DocxParser.extract_text(b"")

def test_parse_corrupted_bytes():
    with pytest.raises(DocxParsingError):
        DocxParser.extract_text(b"not a real docx file")
