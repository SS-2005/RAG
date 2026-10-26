import re
from typing import List, Dict, Any

class DocumentChunk:
    def __init__(self, chunk_id: int, text: str, section: str = "General", start_char: int = 0, end_char: int = 0):
        self.chunk_id = chunk_id
        self.text = text.strip()
        self.section = section
        self.start_char = start_char
        self.end_char = end_char
        self.word_count = len(self.text.split())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "section": self.section,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "word_count": self.word_count
        }

class DocumentChunker:
    """
    Splits document text into overlapping chunks using section-aware boundaries,
    paragraphs, and sliding windows.
    """

    def __init__(self, chunk_size: int = 1100, chunk_overlap: int = 250):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly smaller than chunk_size.")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_structured_blocks(self, structured_blocks: List[Dict[str, str]], full_text: str) -> List[DocumentChunk]:
        """
        Chunks structured blocks while attaching section context to each chunk.
        """
        if not structured_blocks and not full_text:
            return []

        if not structured_blocks:
            return self.chunk_text(full_text)

        chunks: List[DocumentChunk] = []
        current_chunk_blocks = []
        current_length = 0
        current_section = structured_blocks[0].get("section", "Document Overview")
        chunk_idx = 1
        global_char_offset = 0

        for block in structured_blocks:
            b_text = block["text"]
            b_len = len(b_text)
            b_section = block.get("section", current_section)

            # If adding this block exceeds chunk_size, create a chunk
            if current_length > 0 and (current_length + b_len > self.chunk_size or b_section != current_section):
                chunk_body = "\n\n".join(current_chunk_blocks)
                section_header = f"[Section: {current_section}]\n"
                full_chunk_text = section_header + chunk_body

                chunks.append(DocumentChunk(
                    chunk_id=chunk_idx,
                    text=full_chunk_text,
                    section=current_section,
                    start_char=global_char_offset,
                    end_char=global_char_offset + len(chunk_body)
                ))
                chunk_idx += 1
                global_char_offset += len(chunk_body)

                # Keep overlapping blocks if in the same section
                if b_section == current_section and len(current_chunk_blocks) > 1:
                    current_chunk_blocks = [current_chunk_blocks[-1]]
                    current_length = len(current_chunk_blocks[0])
                else:
                    current_chunk_blocks = []
                    current_length = 0

            current_section = b_section
            current_chunk_blocks.append(b_text)
            current_length += b_len

        # Flush remaining blocks
        if current_chunk_blocks:
            chunk_body = "\n\n".join(current_chunk_blocks)
            section_header = f"[Section: {current_section}]\n"
            full_chunk_text = section_header + chunk_body

            chunks.append(DocumentChunk(
                chunk_id=chunk_idx,
                text=full_chunk_text,
                section=current_section,
                start_char=global_char_offset,
                end_char=global_char_offset + len(chunk_body)
            ))

        return chunks

    def chunk_text(self, text: str) -> List[DocumentChunk]:
        """
        Splits plain text into chunks preserving semantic coherence.
        """
        text = text.strip()
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [DocumentChunk(chunk_id=1, text=text, section="Document", start_char=0, end_char=len(text))]

        chunks: List[DocumentChunk] = []
        start = 0
        chunk_idx = 1
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            if end < text_len:
                search_start = max(start + int(self.chunk_size * 0.70), start)
                break_point = text.rfind("\n\n", search_start, end)

                if break_point == -1:
                    sentence_matches = list(re.finditer(r'[\.\?!]\s+', text[search_start:end]))
                    if sentence_matches:
                        break_point = search_start + sentence_matches[-1].end()

                if break_point == -1:
                    break_point = text.rfind(" ", search_start, end)

                if break_point != -1 and break_point > start:
                    end = break_point

            chunk_content = text[start:end].strip()
            if chunk_content:
                chunks.append(DocumentChunk(
                    chunk_id=chunk_idx,
                    text=chunk_content,
                    section="Document",
                    start_char=start,
                    end_char=end
                ))
                chunk_idx += 1

            step = end - start - self.chunk_overlap
            if step <= 0:
                step = max(1, self.chunk_size - self.chunk_overlap)
            start += step

        return chunks
