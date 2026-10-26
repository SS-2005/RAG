import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from app.config import config
from app.docx_parser import DocxParser
from app.chunker import DocumentChunker, DocumentChunk
from app.vector_store import LocalVectorStore
from app.llm_client import LLMClient

STRICT_RAG_SYSTEM_PROMPT = """You are an accurate, intelligent document assistant. Your task is to answer user questions factually and thoroughly based on the provided Document Context.

GUIDELINES:
1. Base your answer strictly on the facts present in the provided Document Context.
2. Understand synonymous and related concepts naturally:
   - Terms like "members", "team", "group", "students", or "authors" refer to the individuals who submitted or authored the project.
   - Technical abbreviations (e.g. "VM" / "VMs" refer to Virtual Machines; "LLM" refers to Large Language Models; "UI" refers to User Interface).
   - Project roles (e.g. "guide", "supervisor", "mentor" refer to faculty advisors).
3. If the provided context genuinely does not contain enough information to answer the question, state: "The uploaded document does not contain information to answer this question."
4. Support your statements by citing the relevant chunk numbers (e.g. [Chunk 1], [Chunk 2]).
5. Be concise, direct, and helpful.
"""

class RAGEngine:
    def __init__(self):
        self.vector_store = LocalVectorStore(
            use_ollama_embeddings=False,
            ollama_url=config.ollama_base_url
        )
        self.chunker = DocumentChunker(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        self.current_document: Optional[Dict[str, Any]] = None
        self.indexed_chunks: List[DocumentChunk] = []

    def ingest_docx(self, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Parses DOCX, chunks text preserving sections, and indexes in vector store."""
        parse_result = DocxParser.extract_text(file_bytes)
        full_text = parse_result["full_text"]
        structured_blocks = parse_result.get("structured_blocks", [])

        chunks = self.chunker.chunk_structured_blocks(structured_blocks, full_text)
        self.indexed_chunks = chunks

        indexed_count = self.vector_store.build_index(chunks)

        self.current_document = {
            "filename": filename,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "paragraph_count": parse_result["paragraph_count"],
            "table_count": parse_result["table_count"],
            "char_count": parse_result["char_count"],
            "word_count": parse_result["word_count"],
            "chunk_count": indexed_count,
            "parser_used": parse_result["parser_used"]
        }

        return self.current_document

    def get_document_info(self) -> Optional[Dict[str, Any]]:
        return self.current_document

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.indexed_chunks]

    def has_document(self) -> bool:
        return self.current_document is not None and len(self.indexed_chunks) > 0

    async def stream_query(
        self,
        query: str,
        provider: str = "ollama",
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        top_k: int = 4,
        temperature: float = 0.1
    ) -> AsyncGenerator[str, None]:
        """
        Streams RAG response via Server-Sent Events (SSE).
        Yields sources immediately (< 20ms) then streams tokens as they are generated.
        """
        if not self.has_document():
            yield f"data: {json.dumps({'type': 'error', 'message': 'No document loaded. Please upload a .docx file first.'})}\n\n"
            return

        query = query.strip()
        if not query:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Query cannot be empty.'})}\n\n"
            return

        # 1. Fast sub-millisecond retrieval
        matched_chunks = self.vector_store.search(
            query=query,
            top_k=top_k or config.top_k,
            min_score=config.min_similarity_score
        )

        # Send retrieved sources immediately to UI
        yield f"data: {json.dumps({'type': 'sources', 'sources': matched_chunks})}\n\n"

        if not matched_chunks:
            yield f"data: {json.dumps({'type': 'token', 'token': 'The uploaded document does not contain information to answer this question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 2. Build Context String
        context_blocks = []
        for c in matched_chunks:
            sec_info = f" [Section: {c.get('section', 'General')}]" if c.get('section') else ""
            context_blocks.append(f"--- [Chunk {c['chunk_id']}]{sec_info} ---\n{c['text']}")

        context_str = "\n\n".join(context_blocks)

        user_augmented_prompt = f"""DOCUMENT CONTEXT:
{context_str}

USER QUESTION:
{query}

ANSWER (grounded strictly in the above context, citing chunk numbers):"""

        if not base_url:
            base_url = config.ollama_base_url if provider == "ollama" else config.openai_base_url
        if not model:
            model = config.default_model

        # 3. Stream tokens live
        async for token in LLMClient.generate_stream(
            provider=provider,
            base_url=base_url,
            model=model,
            system_prompt=STRICT_RAG_SYSTEM_PROMPT,
            user_prompt=user_augmented_prompt,
            temperature=temperature,
            max_tokens=config.max_tokens,
            num_ctx=config.num_ctx,
            retrieved_chunks=matched_chunks
        ):
            yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    async def answer_query(
        self,
        query: str,
        provider: str = "ollama",
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        top_k: int = 4,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Non-streaming query response for direct API or tests."""
        if not self.has_document():
            return {
                "success": False,
                "error": "No document has been uploaded yet. Please upload a .docx document first.",
                "answer": "",
                "sources": []
            }

        query = query.strip()
        if not query:
            return {"success": False, "error": "Query cannot be empty.", "answer": "", "sources": []}

        matched_chunks = self.vector_store.search(
            query=query,
            top_k=top_k or config.top_k,
            min_score=config.min_similarity_score
        )

        if not matched_chunks:
            return {
                "success": True,
                "answer": "The uploaded document does not contain information to answer this question.",
                "sources": [],
                "model": model or config.default_model,
                "provider": provider
            }

        context_blocks = []
        for c in matched_chunks:
            sec_info = f" [Section: {c.get('section', 'General')}]" if c.get('section') else ""
            context_blocks.append(f"--- [Chunk {c['chunk_id']}]{sec_info} ---\n{c['text']}")

        context_str = "\n\n".join(context_blocks)
        user_augmented_prompt = f"""DOCUMENT CONTEXT:
{context_str}

USER QUESTION:
{query}

ANSWER (grounded strictly in the above context, citing chunk numbers):"""

        if not base_url:
            base_url = config.ollama_base_url if provider == "ollama" else config.openai_base_url
        if not model:
            model = config.default_model

        llm_res = await LLMClient.generate_response(
            provider=provider,
            base_url=base_url,
            model=model,
            system_prompt=STRICT_RAG_SYSTEM_PROMPT,
            user_prompt=user_augmented_prompt,
            temperature=temperature,
            max_tokens=config.max_tokens,
            retrieved_chunks=matched_chunks
        )

        llm_res["sources"] = matched_chunks
        llm_res["query"] = query
        return llm_res

    def reset(self):
        self.vector_store.clear()
        self.current_document = None
        self.indexed_chunks = []
