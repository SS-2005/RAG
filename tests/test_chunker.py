import pytest
from app.chunker import DocumentChunker

def test_chunker_small_text():
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    text = "Short paragraph of text."
    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == 1
    assert chunks[0].text == text

def test_chunker_empty_text():
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    chunks = chunker.chunk_text("")
    assert chunks == []

def test_chunker_overlapping():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    long_text = "Word " * 60  # 300 characters
    chunks = chunker.chunk_text(long_text)
    assert len(chunks) > 1
    # Ensure sequential IDs
    ids = [c.chunk_id for c in chunks]
    assert ids == list(range(1, len(chunks) + 1))
    # Each chunk should have text length within reasonable bounds
    for c in chunks:
        assert len(c.text) > 0
