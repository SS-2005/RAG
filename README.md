# DOCX Local RAG Assistant (Dark UI)

A private, on-premise Document Q&A application powered by **Local LLMs** (Ollama, LM Studio, vLLM, or any OpenAI-compatible runner) and an in-memory **Retrieval-Augmented Generation (RAG)** pipeline with a **Modern Dark UI**.

---

## 1. System Constraints & Logic Definition

### 1.1 Document Ingestion Constraints
1. **File Format**: Exclusively supports `.docx` files (Microsoft Word OpenXML).
2. **File Size Limit**: Capped at 25 MB per upload to safeguard local host RAM.
3. **Extraction Integrity**:
   - Parses document paragraphs and tables using `python-docx`.
   - Includes a native XML fallback parser (`word/document.xml`) to extract text even if custom styles or formatting artifacts are present.
   - Rejects empty documents (0 bytes or whitespace-only files).

### 1.2 Chunking & Vectorization Logic
1. **Sliding Semantic Window**:
   - Chunk size: **600 characters** (~90–120 words).
   - Overlap: **100 characters** between consecutive chunks to preserve contextual coherence across paragraph and sentence boundaries.
   - Splits prioritize natural paragraph boundaries (`\n\n`), then sentence boundaries (`. `, `? `, `! `), then word spaces (` `).
2. **Vector Space Indexing**:
   - In-memory vectorizer using **Sublinear TF-IDF + Bi-grams** combined with Cosine Similarity.
   - Sub-millisecond similarity retrieval with zero cloud dependencies or external vector database requirements.
   - Optional local dense embedding support via Ollama (`nomic-embed-text`, etc.).
3. **Retrieval**:
   - Retrieves top-$k$ chunks (default: 4 chunks, adjustable between 1–8).
   - Minimum relevance score threshold (0.01) filters out irrelevant noise.

### 1.3 Grounding & Anti-Hallucination Constraints
1. **Strict Context Adherence**:
   - The LLM is instructed via system prompt that it must answer **ONLY** using the provided context chunks.
2. **Absence Disclosure**:
   - If the answer to the user's question cannot be found or directly deduced from the document, the model MUST explicitly respond:
     > *"I cannot find the answer in the uploaded document."*
3. **Citation & Source Attribution**:
   - Responses cite source chunks (e.g., `[Chunk 1]`, `[Chunk 2]`).
   - The Dark UI renders an interactive "Retrieved Sources" drawer displaying similarity scores and exact text snippets for transparency.

---

## 2. Project Architecture

```
NLP/
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration & hyperparameters
│   ├── docx_parser.py         # DOCX parser with table extraction & XML fallback
│   ├── chunker.py             # Sliding window semantic text chunker
│   ├── vector_store.py        # Local vector index (TF-IDF + Cosine similarity)
│   ├── llm_client.py          # Unified client for Ollama, LM Studio, and Offline Mode
│   ├── rag_engine.py          # Core RAG pipeline & strict grounding prompts
│   └── main.py                # FastAPI server & REST API
├── static/
│   ├── index.html             # Clean, responsive Dark UI
│   ├── style.css              # Obsidian Dark CSS theme & glassmorphic accents
│   └── app.js                 # Drag-and-drop upload, model detection, & chat
├── tests/
│   ├── __init__.py
│   ├── test_docx_parser.py    # Unit tests for DOCX parsing
│   ├── test_chunker.py        # Unit tests for semantic chunking & overlap
│   ├── test_vector_store.py   # Unit tests for vector search & similarity
│   ├── test_rag_engine.py     # Unit tests for RAG pipeline & grounding rules
│   └── test_api.py            # API integration tests
├── sample_data/
│   ├── ai_architecture_brief.docx  # Pre-generated sample DOCX
│   └── create_sample_doc.py        # Generator script for test documents
├── requirements.txt           # Python dependencies
├── run.bat                    # 1-click Windows launcher
├── run.sh                     # 1-click Linux/macOS launcher
└── README.md                  # Documentation & setup guide
```

---

## 3. Quick Start Guide

### Step 1: Install Requirements
Ensure Python 3.10+ is installed on your system. Run:
```bash
pip install -r requirements.txt
```

### Step 2: Choose Your Local LLM Backend

#### Option A: Ollama (Recommended)
1. Ensure Ollama is installed and running (`ollama serve` or Ollama desktop app).
2. Pull any model of your choice:
   ```bash
   ollama pull llama3
   # Or: ollama pull mistral, deepseek-r1, phi3, etc.
   ```
3. Default URL: `http://127.0.0.1:11434`.

#### Option B: LM Studio / Jan / LocalAI / vLLM (OpenAI-compatible)
1. Start local inference server inside LM Studio or vLLM.
2. Default URL: `http://127.0.0.1:1234/v1`.

#### Option C: Offline / Grounded Mode
If you want to test without running an external LLM server, choose **"Offline / Demo Mode"** in the sidebar. It uses an extractive grounded synthesizer over retrieved chunks.

---

### Step 3: Run the Application

#### On Windows:
Double-click `run.bat` or run:
```cmd
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### On Linux / macOS:
```bash
chmod +x run.sh
./run.sh
```

---

### Step 4: Open the Dark UI
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

1. **Upload**: Drag and drop any `.docx` file (or use `sample_data/ai_architecture_brief.docx`).
2. **Detect Model**: Click **"Detect"** in the sidebar to auto-populate installed local models from Ollama or LM Studio.
3. **Ask Questions**: Ask questions in the chat box!
4. **Inspect Sources**: Expand the **"Retrieved Context Chunks"** dropdown under any response to see exact chunk relevance scores and snippets.
5. **Inspect Chunks**: Click **"Inspect Chunks"** in the sidebar to view all indexed segments.

---

## 4. Running Automated Tests

Run the full test suite with `pytest`:
```bash
python -m pytest tests/ -v
```
All 15 unit and integration tests will execute, validating parser extraction, chunking, vector scoring, RAG grounding, and API endpoints.
