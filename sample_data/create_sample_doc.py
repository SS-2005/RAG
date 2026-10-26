import os
import docx
from docx.shared import Inches, Pt, RGBColor

def create_sample_docx(output_path: str = "sample_data/ai_architecture_brief.docx"):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = docx.Document()

    # Title
    title = doc.add_heading("Autonomous Systems & Local AI Architecture Report", level=0)
    title.runs[0].font.color.rgb = RGBColor(99, 102, 241)

    # Section 1
    doc.add_heading("1. Executive Summary", level=1)
    doc.add_paragraph(
        "Project Titan is an open-source initiative dedicated to private, on-premise artificial intelligence deployment. "
        "The primary goal is to run high-throughput LLM workloads directly on consumer hardware without exposing proprietary data "
        "to third-party cloud providers. The project specifies a strict memory footprint ceiling of 16 GB unified RAM."
    )

    # Section 2
    doc.add_heading("2. Retrieval-Augmented Generation (RAG) Specifications", level=1)
    doc.add_paragraph(
        "Under Project Titan, documents are ingested in .docx and .pdf formats. The text chunker enforces a maximum segment size "
        "of 600 characters with a 100-character overlapping sliding window. The retrieval pipeline implements an in-memory vector "
        "space model using TF-IDF with sublinear term-frequency scaling and cosine similarity metrics."
    )
    doc.add_paragraph(
        "When a query arrives, the system retrieves the top 4 most relevant chunks. The grounding constraint requires that if "
        "the document does not contain the answer, the LLM must explicitly reply: 'I cannot find the answer in the uploaded document.' "
        "Hallucinated citations or unverified assertions are prohibited."
    )

    # Section 3: Table
    doc.add_heading("3. Hardware Requirements and Model Matrix", level=1)
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Model Tier'
    hdr_cells[1].text = 'Parameter Count'
    hdr_cells[2].text = 'VRAM Target'
    hdr_cells[3].text = 'Quantization'

    data = [
        ('Edge Lightweight', '3.8 Billion', '4 GB VRAM', 'Q4_K_M'),
        ('Standard Desktop', '8.0 Billion', '8 GB VRAM', 'Q5_K_M'),
        ('Workstation Heavy', '14.0 Billion', '16 GB VRAM', 'Q8_0'),
        ('Enterprise Flagship', '70.0 Billion', '48 GB VRAM', 'Q4_K_S')
    ]

    for tier, params, vram, quant in data:
        row_cells = table.add_row().cells
        row_cells[0].text = tier
        row_cells[1].text = params
        row_cells[2].text = vram
        row_cells[3].text = quant

    # Section 4
    doc.add_heading("4. Security Protocols and Air-Gapped Operation", level=1)
    doc.add_paragraph(
        "Titan nodes operate in strictly air-gapped server racks. All outbound TCP/UDP traffic on ports 80 and 443 is blocked "
        "by default iptables policies. Encryption at rest utilizes AES-256-GCM, and vector indices are volatile, purged upon application termination."
    )

    doc.save(output_path)
    print(f"Sample DOCX created at: {output_path}")

if __name__ == "__main__":
    create_sample_docx()
