#!/usr/bin/env bash
echo "========================================================"
echo "       DOCX Local RAG Assistant (Dark UI)"
echo "========================================================"
echo ""
echo "Starting Local DOCX RAG Assistant Server on http://127.0.0.1:8000 ..."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
