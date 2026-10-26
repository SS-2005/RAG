import re
import numpy as np
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import httpx
from app.chunker import DocumentChunk

# Initialize Porter Stemmer
try:
    from nltk.stem import PorterStemmer
    _stemmer = PorterStemmer()
except Exception:
    class SimpleStemmer:
        def stem(self, w: str) -> str:
            w = w.lower()
            if w.endswith("ies") and len(w) > 4: return w[:-3] + "y"
            if w.endswith("es") and len(w) > 3: return w[:-2]
            if w.endswith("s") and not w.endswith("ss") and len(w) > 2: return w[:-1]
            if w.endswith("ing") and len(w) > 4: return w[:-3]
            if w.endswith("ed") and len(w) > 3: return w[:-2]
            return w
    _stemmer = SimpleStemmer()

# General-purpose query expansion dictionary for technical and academic documents
COMMON_SYNONYMS = {
    "vm": ["virtual", "machine", "virtualbox", "instance"],
    "vms": ["virtual", "machines", "virtualbox", "instances"],
    "virtual": ["vm", "vms", "machine"],
    "machine": ["vm", "vms"],
    "machines": ["vm", "vms"],
    "member": ["student", "author", "contributor", "submitted", "roll", "team"],
    "members": ["students", "authors", "contributors", "submitted", "roll", "team", "group"],
    "group": ["team", "members", "students", "authors", "submitted"],
    "team": ["members", "group", "students", "authors"],
    "guide": ["supervisor", "professor", "prof", "mentor", "internal"],
    "supervisor": ["guide", "professor", "prof", "internal"],
    "llm": ["large", "language", "model", "ollama", "agent"],
    "llms": ["large", "language", "models", "ollama", "agents"],
    "ui": ["interface", "frontend", "dashboard", "react", "browser"],
    "frontend": ["ui", "interface", "react", "browser"],
    "backend": ["fastapi", "server", "api", "orchestrator"],
    "database": ["sqlite", "db", "storage", "tables"],
    "db": ["database", "sqlite", "tables"],
    "evaluation": ["metrics", "scoring", "benchmark", "rate"],
    "metric": ["evaluation", "score", "rate", "count", "time"],
    "metrics": ["evaluation", "scores", "rates", "counts", "time"],
}

def tokenize_and_stem(text: str) -> List[str]:
    """Tokenizes and stems words for BM25 retrieval."""
    words = re.findall(r'\b[a-zA-Z0-9_\-]+\b', text.lower())
    return [_stemmer.stem(w) for w in words]

class LocalVectorStore:
    """
    Production-grade Hybrid Retriever:
    1. Stemmed BM25 Okapi for accurate term-frequency & document length normalized search.
    2. Subword Character N-gram TF-IDF for acronyms, abbreviations, and morphology matching.
    3. Query Expansion for technical synonyms.
    4. Reciprocal Rank Fusion (RRF) for robust multi-signal scoring.
    5. Dense Ollama embedding integration (optional).
    """

    def __init__(self, use_ollama_embeddings: bool = False, ollama_url: str = "http://127.0.0.1:11434", embedding_model: str = "nomic-embed-text"):
        self.chunks: List[DocumentChunk] = []
        self.use_ollama_embeddings = use_ollama_embeddings
        self.ollama_url = ollama_url.rstrip("/")
        self.embedding_model = embedding_model

        # BM25 Engine
        self.bm25: Optional[BM25Okapi] = None
        self.tokenized_corpus: List[List[str]] = []

        # Character N-gram TF-IDF Engine
        self.char_vectorizer: Optional[TfidfVectorizer] = None
        self.char_tfidf_matrix = None

        # Dense Embedding Engine (Ollama)
        self.dense_embeddings: Optional[np.ndarray] = None

    def build_index(self, chunks: List[DocumentChunk]) -> int:
        """
        Indexes the given list of document chunks.
        """
        self.chunks = chunks
        if not chunks:
            self.clear()
            return 0

        corpus = [c.text for c in chunks]

        # 1. Build Stemmed BM25
        self.tokenized_corpus = [tokenize_and_stem(doc) for doc in corpus]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

        # 2. Build Subword / Char N-gram TF-IDF
        self.char_vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(3, 5),
            sublinear_tf=True
        )
        self.char_tfidf_matrix = self.char_vectorizer.fit_transform(corpus)

        # 3. Dense embeddings (if Ollama embedding is enabled)
        if self.use_ollama_embeddings:
            try:
                embeddings = []
                for text in corpus:
                    emb = self._fetch_ollama_embedding(text)
                    if emb:
                        embeddings.append(emb)
                if len(embeddings) == len(corpus):
                    self.dense_embeddings = np.array(embeddings)
                else:
                    self.dense_embeddings = None
            except Exception:
                self.dense_embeddings = None

        return len(chunks)

    def _fetch_ollama_embedding(self, text: str) -> Optional[List[float]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.embedding_model, "prompt": text}
                )
                if res.status_code == 200:
                    return res.json().get("embedding")
        except Exception:
            pass
        return None

    def _expand_query(self, query: str) -> str:
        """Appends general technical synonyms to boost matching across abbreviations."""
        tokens = re.findall(r'\b[a-zA-Z0-9_\-]+\b', query.lower())
        expansions = []
        for t in tokens:
            if t in COMMON_SYNONYMS:
                expansions.extend(COMMON_SYNONYMS[t])
        if expansions:
            return query + " " + " ".join(set(expansions))
        return query

    def search(self, query: str, top_k: int = 6, min_score: float = 0.005) -> List[Dict[str, Any]]:
        """
        Performs Hybrid Search using RRF (Reciprocal Rank Fusion) across BM25 and Char N-Gram TF-IDF.
        """
        if not self.chunks or not query.strip():
            return []

        expanded_query = self._expand_query(query)
        stemmed_query_tokens = tokenize_and_stem(expanded_query)

        num_docs = len(self.chunks)
        rrf_scores = np.zeros(num_docs, dtype=float)
        RRF_K = 60

        # --- Signal 1: Stemmed BM25 ---
        if self.bm25 is not None and stemmed_query_tokens:
            bm25_scores = np.array(self.bm25.get_scores(stemmed_query_tokens))
            bm25_ranks = np.argsort(bm25_scores)[::-1]
            for rank, doc_idx in enumerate(bm25_ranks):
                if bm25_scores[doc_idx] > 0:
                    rrf_scores[doc_idx] += 1.0 / (RRF_K + rank + 1)

        # --- Signal 2: Subword / Char N-gram TF-IDF ---
        if self.char_vectorizer is not None and self.char_tfidf_matrix is not None:
            q_char_vec = self.char_vectorizer.transform([expanded_query])
            char_sims = cosine_similarity(q_char_vec, self.char_tfidf_matrix)[0]
            char_ranks = np.argsort(char_sims)[::-1]
            for rank, doc_idx in enumerate(char_ranks):
                if char_sims[doc_idx] > 0.01:
                    rrf_scores[doc_idx] += 0.8 / (RRF_K + rank + 1)

        # --- Signal 3: Dense Ollama Embeddings (Optional) ---
        if self.dense_embeddings is not None:
            q_emb = self._fetch_ollama_embedding(query)
            if q_emb is not None:
                q_vec = np.array(q_emb).reshape(1, -1)
                dense_sims = cosine_similarity(q_vec, self.dense_embeddings)[0]
                dense_ranks = np.argsort(dense_sims)[::-1]
                for rank, doc_idx in enumerate(dense_ranks):
                    if dense_sims[doc_idx] > 0.1:
                        rrf_scores[doc_idx] += 1.2 / (RRF_K + rank + 1)

        # Rank all documents by combined RRF score
        ranked_indices = np.argsort(rrf_scores)[::-1]
        results = []

        max_rrf = np.max(rrf_scores) if np.max(rrf_scores) > 0 else 1.0

        for idx in ranked_indices:
            score = float(rrf_scores[idx])
            normalized_score = round(score / max_rrf, 4) if max_rrf > 0 else 0.0

            if normalized_score < min_score and len(results) > 0:
                break

            chunk = self.chunks[idx]
            results.append({
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "section": chunk.section,
                "score": normalized_score,
                "word_count": chunk.word_count,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char
            })

            if len(results) >= top_k:
                break

        return results

    def clear(self):
        self.chunks = []
        self.bm25 = None
        self.tokenized_corpus = []
        self.char_vectorizer = None
        self.char_tfidf_matrix = None
        self.dense_embeddings = None
