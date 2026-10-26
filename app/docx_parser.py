import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import docx

class DocxParsingError(Exception):
    """Custom exception raised when docx parsing fails."""
    pass

class DocxParser:
    """
    Extracts structured sections, headings, tables, and paragraphs from DOCX files
    with a reliable raw XML fallback.
    """

    @staticmethod
    def extract_text(file_bytes: bytes) -> Dict[str, Any]:
        """
        Parses a .docx file from bytes.
        Returns a dictionary with full_text, sections, paragraphs, tables, and stats.
        """
        if not file_bytes:
            raise DocxParsingError("Uploaded file is empty (0 bytes).")

        try:
            return DocxParser._parse_with_docx(file_bytes)
        except Exception as primary_err:
            try:
                return DocxParser._parse_with_xml(file_bytes)
            except Exception as fallback_err:
                raise DocxParsingError(
                    f"Failed to parse DOCX. Primary error: {primary_err}; Fallback error: {fallback_err}"
                )

    @staticmethod
    def _parse_with_docx(file_bytes: bytes) -> Dict[str, Any]:
        doc_stream = io.BytesIO(file_bytes)
        doc = docx.Document(doc_stream)

        structured_blocks: List[Dict[str, str]] = []
        current_section = "General / Front Matter"
        paragraphs_count = 0

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            paragraphs_count += 1
            style_name = getattr(p.style, 'name', '') or ''
            
            # Identify headings
            if 'Heading' in style_name or style_name in ['Title', 'Subtitle'] or (len(text) < 80 and text.isupper()):
                current_section = text
                structured_blocks.append({
                    "section": current_section,
                    "type": "heading",
                    "text": f"## {text}"
                })
            else:
                structured_blocks.append({
                    "section": current_section,
                    "type": "paragraph",
                    "text": text
                })

        # Extract tables
        tables_count = 0
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                # Avoid duplicate adjacent row cells if merged
                deduped = []
                for cell in row_cells:
                    if not deduped or cell != deduped[-1]:
                        deduped.append(cell)
                if any(deduped):
                    table_rows.append(" | ".join(deduped))
            if table_rows:
                tables_count += 1
                table_text = "\n".join(table_rows)
                structured_blocks.append({
                    "section": current_section,
                    "type": "table",
                    "text": f"[TABLE]\n{table_text}\n[/TABLE]"
                })

        # Build composite document text with section tags
        combined_text_parts = []
        for block in structured_blocks:
            combined_text_parts.append(block["text"])

        full_text = "\n\n".join(combined_text_parts)
        full_text = re.sub(r'\n{3,}', '\n\n', full_text).strip()

        if not full_text:
            raise DocxParsingError("The DOCX document does not contain any readable text.")

        return {
            "full_text": full_text,
            "structured_blocks": structured_blocks,
            "paragraph_count": paragraphs_count,
            "table_count": tables_count,
            "char_count": len(full_text),
            "word_count": len(full_text.split()),
            "parser_used": "python-docx"
        }

    @staticmethod
    def _parse_with_xml(file_bytes: bytes) -> Dict[str, Any]:
        """Fallback parser using raw document.xml extraction."""
        doc_stream = io.BytesIO(file_bytes)
        with zipfile.ZipFile(doc_stream) as zf:
            if "word/document.xml" not in zf.namelist():
                raise DocxParsingError("Invalid DOCX format: missing word/document.xml")
            xml_content = zf.read("word/document.xml")

        tree = ET.fromstring(xml_content)
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

        paragraphs: List[str] = []
        for p in tree.findall('.//w:p', namespaces):
            texts = [node.text for node in p.findall('.//w:t', namespaces) if node.text]
            p_text = "".join(texts).strip()
            if p_text:
                paragraphs.append(p_text)

        full_text = "\n\n".join(paragraphs).strip()
        if not full_text:
            raise DocxParsingError("The DOCX document does not contain any readable text.")

        structured_blocks = [{"section": "General", "type": "paragraph", "text": p} for p in paragraphs]

        return {
            "full_text": full_text,
            "structured_blocks": structured_blocks,
            "paragraph_count": len(paragraphs),
            "table_count": 0,
            "char_count": len(full_text),
            "word_count": len(full_text.split()),
            "parser_used": "xml-fallback"
        }
