import pytest
from app.chunker import DocumentChunk
from app.vector_store import LocalVectorStore

def test_vector_store_indexing_and_search():
    store = LocalVectorStore()

    chunks = [
        DocumentChunk(chunk_id=1, text="Apples and bananas are nutritious fruits rich in vitamins.", start_char=0, end_char=58),
        DocumentChunk(chunk_id=2, text="Quantum computers use qubits to solve complex cryptographic algorithms.", start_char=59, end_char=130),
        DocumentChunk(chunk_id=3, text="Airplanes generate lift through aerodynamic wings and jet thrust.", start_char=131, end_char=196)
    ]

    indexed_count = store.build_index(chunks)
    assert indexed_count == 3

    # Query matching chunk 2
    results = store.search(query="qubits cryptography quantum", top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == 2
    assert results[0]["score"] > 0.1

    # Query matching chunk 1
    results = store.search(query="nutritious fruit vitamins", top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == 1

def test_vector_store_clear():
    store = LocalVectorStore()
    chunks = [DocumentChunk(chunk_id=1, text="Test", start_char=0, end_char=4)]
    store.build_index(chunks)
    assert len(store.chunks) == 1
    store.clear()
    assert len(store.chunks) == 0
    assert store.search("Test") == []
