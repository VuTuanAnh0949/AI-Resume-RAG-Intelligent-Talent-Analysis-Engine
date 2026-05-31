# Project Plan: IT Resume RAG System

This document outlines the architecture, implementation steps, and verification process for the IT Resume RAG (Retrieval-Augmented Generation) system.

## Project Goal
Build a high-performance system to process, index, and query INFORMATION-TECHNOLOGY resumes. The system uses a RAG architecture to provide precise candidate recommendations with evidence snippets based on natural language queries.

## Architecture Overview

### Backend (Python FastAPI)
- **API Layer**: REST endpoints for ingestion, upload, and querying.
- **Ingestion Engine**: Processes PDF files using `pdfplumber` with an OCR fallback (`pytesseract` + `pdf2image`) for scanned documents.
- **Extraction Service**: Dual-strategy extraction:
  - **Heuristic**: Regex-based extraction for high-reliability fields (email, phone, basic skills).
  - **LLM-Augmented**: Uses **Qwen 2.5 (7B)** via Ollama to extract structured JSON (name, experience, education, roles, total years).
- **Vector Database**: **ChromaDB** for efficient similarity search of resume chunks.
- **Embeddings**: Local **BAAI/bge-small-en** model for high-quality text representation.
- **RAG Logic**: Combines semantic search with metadata filtering (e.g., years of experience) and LLM-based answer generation.

### Frontend (React + Vite)
- **Upload Dashboard**: Multi-file upload for new resumes.
- **Query Interface**: Natural language search with configurable results count.
- **Candidate View**: Detailed visualization of extracted JSON profiles and similarity scores.

## Implementation Roadmap

### Phase 1: Data Ingestion & Extraction (Completed)
- [x] PDF text extraction with OCR fallback.
- [x] Structured JSON profile extraction using LLM (Qwen).
- [x] Heuristic fallback for essential contact information.
- [x] Normalization of skills and domain filtering (IT focus).

### Phase 2: Indexing & Retrieval (Completed)
- [x] Text chunking strategy for resumes.
- [x] ChromaDB integration for vector storage.
- [x] Metadata indexing (resume_id, skills, years_experience).
- [x] Semantic search implementation.

### Phase 3: RAG & API (Completed)
- [x] Prompt engineering for candidate selection and answer generation.
- [x] FastAPI endpoints for `/query`, `/ingest`, and `/candidates`.
- [x] Background task management for batch ingestion.

### Phase 4: UI & Evaluation (Completed)
- [x] React-based dashboard for search and upload.
- [x] Automated evaluation script for coverage and retrieval quality.
- [x] Documentation and runbook.

## Technical Decisions
- **Qwen 2.5 7B**: Chosen for its excellent balance of performance and efficiency in local inference, particularly strong at following JSON schemas.
- **BAAI/bge-small-en**: High-performance embedding model that fits well in memory while providing state-of-the-art retrieval accuracy.
- **ChromaDB**: Native Python support and simplicity for local persistence.
- **FastAPI**: Asynchronous support for long-running ingestion and LLM tasks.

## Verification Strategy
1. **Extraction Accuracy**: Run `backend/scripts/evaluate.py` to check field coverage.
2. **Retrieval Precision**: Verify top candidates against standard queries (e.g., "Python + ML").
3. **End-to-End Flow**: Upload a new resume through the UI and ensure it appears in subsequent search results.
4. **OCR Check**: Test with a scanned PDF to confirm fallback to Tesseract works as expected.
