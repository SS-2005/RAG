from pydantic import BaseModel

class AppConfig(BaseModel):
    # LLM Settings
    default_provider: str = "ollama"  # "ollama", "openai_compatible", or "offline"
    ollama_base_url: str = "http://127.0.0.1:11434"
    openai_base_url: str = "http://127.0.0.1:1234/v1"
    default_model: str = "llama3"
    temperature: float = 0.1
    max_tokens: int = 512          # Fast, concise token generation
    num_ctx: int = 2048            # Compact context window to minimize prompt evaluation prefill time

    # RAG & Chunking Settings
    chunk_size: int = 1000         # Optimal balance between context and fast prefill
    chunk_overlap: int = 200
    top_k: int = 4                 # 4 chunks provide all necessary facts with minimal prefill latency
    min_similarity_score: float = 0.005

    # File Constraints
    max_file_size_mb: int = 25     # Maximum DOCX upload size in MB
    allowed_extensions: list[str] = [".docx"]

config = AppConfig()
