import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from app.config import config
from app.rag_engine import RAGEngine
from app.llm_client import LLMClient
from app.docx_parser import DocxParsingError

app = FastAPI(
    title="Local LLM DOCX RAG Assistant",
    description="Ask questions on DOCX documents using Local LLMs (Ollama / LM Studio) with real-time streaming RAG.",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_engine = RAGEngine()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "DOCX Local RAG API is running. UI not found at /static/index.html"}

@app.post("/api/upload")
async def upload_docx(file: UploadFile = File(...)):
    """Uploads and indexes a .docx document."""
    filename = file.filename or "uploaded.docx"
    ext = os.path.splitext(filename)[1].lower()
    if ext != ".docx":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Only '.docx' files are supported."
        )

    contents = await file.read()
    max_bytes = config.max_file_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size limit of {config.max_file_size_mb} MB."
        )

    try:
        doc_info = rag_engine.ingest_docx(filename=filename, file_bytes=contents)
        return {
            "success": True,
            "message": f"Successfully ingested and indexed '{filename}'.",
            "document": doc_info
        }
    except DocxParsingError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected parsing error: {str(e)}")

class QueryRequest(BaseModel):
    query: str = Field(..., description="User question about the document")
    provider: str = Field("ollama", description="'ollama', 'openai_compatible', or 'offline'")
    base_url: Optional[str] = Field(None, description="Local server base URL")
    model: Optional[str] = Field("llama3", description="Model identifier")
    top_k: int = Field(4, ge=1, le=10, description="Number of context chunks to retrieve")
    temperature: float = Field(0.1, ge=0.0, le=1.0)

@app.post("/api/query/stream")
async def stream_query_document(req: QueryRequest):
    """Streams RAG generation live using Server-Sent Events for near real-time response."""
    if not rag_engine.has_document():
        raise HTTPException(
            status_code=400,
            detail="No document loaded. Please upload a .docx file first."
        )

    return StreamingResponse(
        rag_engine.stream_query(
            query=req.query,
            provider=req.provider,
            base_url=req.base_url,
            model=req.model,
            top_k=req.top_k,
            temperature=req.temperature
        ),
        media_type="text/event-stream"
    )

@app.post("/api/query")
async def query_document(req: QueryRequest):
    """Processes user question non-streaming (fallback/testing)."""
    if not rag_engine.has_document():
        raise HTTPException(
            status_code=400,
            detail="No document loaded. Please upload a .docx file first."
        )

    result = await rag_engine.answer_query(
        query=req.query,
        provider=req.provider,
        base_url=req.base_url,
        model=req.model,
        top_k=req.top_k,
        temperature=req.temperature
    )

    if not result.get("success", False) and "error" in result:
        return JSONResponse(status_code=502, content=result)

    return result

@app.get("/api/document")
async def get_current_document():
    """Returns active document information."""
    info = rag_engine.get_document_info()
    return {"loaded": info is not None, "document": info}

@app.get("/api/chunks")
async def get_document_chunks():
    """Returns all chunks generated for the uploaded document."""
    if not rag_engine.has_document():
        return {"chunks": []}
    return {"chunks": rag_engine.get_all_chunks()}

@app.post("/api/reset")
async def reset_document():
    """Clears the uploaded document and resets index."""
    rag_engine.reset()
    return {"success": True, "message": "Document index cleared."}

@app.get("/api/models")
async def get_available_models(provider: str = "ollama", base_url: Optional[str] = None):
    """Detects installed models on the local LLM runner."""
    url = base_url or (config.ollama_base_url if provider == "ollama" else config.openai_base_url)
    models = await LLMClient.list_models(provider=provider, base_url=url)
    health = await LLMClient.check_health(provider=provider, base_url=url)
    return {
        "provider": provider,
        "base_url": url,
        "online": health.get("reachable", False),
        "status_message": health.get("message", ""),
        "models": models
    }
