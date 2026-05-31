# Operations & Deployment Guide

This guide provides comprehensive instructions for setting up, running, and interacting with the IT Resume RAG system.

## 🚀 Quick Access Links

- **Frontend (UI)**: [http://localhost:5173](http://localhost:5173)
- **Backend (API)**: [http://localhost:8000](http://localhost:8000)
- **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

## System Prerequisites

- **Python 3.10+**: Recommended for backend services.
- **Node.js 18+**: Required for the React frontend.
- **Ollama**: For local LLM inference (Qwen 2.5). [Download here](https://ollama.com/).
- **OCR Dependencies (Optional)**:
  - **Tesseract OCR**: Required for scanned PDF support.
  - **Poppler**: Required for PDF-to-image conversion.

## Initial Setup

### 1. Ollama Configuration
Ensure Ollama is running and the required model is pulled:
```bash
ollama serve
ollama pull qwen2.5:7b-instruct
```

### 2. Backend Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env if you need to adjust paths or model names
```

### 3. Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env
```

## Running the Application

### Start Backend (FastAPI)
From the project root:
```bash
uvicorn app.main:app --reload --app-dir backend
```
The API will be available at `http://127.0.0.1:8000`.

### Start Frontend (React)
From the `frontend` directory:
```bash
npm run dev
```
The UI will be available at `http://127.0.0.1:5173`.

## API Reference

### Ingestion Endpoints
- **POST `/api/ingest/dataset?limit=N`**: Starts background ingestion of the IT resume dataset.
- **POST `/api/ingest/upload`**: Upload one or more PDF files for immediate processing.
  - Body: `multipart/form-data` with `files` key.

### Query & Data Endpoints
- **POST `/api/query`**: Perform a RAG search.
  - Body: `{"query": "string", "top_k": integer}`
- **GET `/api/candidates/{resume_id}`**: Retrieve the full extracted JSON profile for a candidate.

### System Endpoints
- **GET `/api/health`**: Check system status.
- **Swagger Documentation**: `http://127.0.0.1:8000/docs`

## Evaluation & Monitoring

To generate a performance and coverage report:
```bash
python backend/scripts/evaluate.py --limit 20
```
This script checks:
1. **Extraction Coverage**: % of fields successfully extracted from PDFs.
2. **Retrieval Accuracy**: Boolean check if the top candidate matches predefined query constraints.
3. **Latency**: Average time taken for RAG queries.

## Troubleshooting

### LLM Connectivity
- **Error**: `ConnectionError` when calling LLM.
- **Solution**: Verify Ollama is running (`ollama serve`) and the model `qwen2.5:7b-instruct` is available. Check `OLLAMA_BASE_URL` in `.env`.

### OCR Issues
- **Error**: `TesseractNotFoundError` or `pdf2image` errors.
- **Solution**: Ensure Tesseract and Poppler are installed and their `bin` directories are added to your system's PATH. Restart your terminal after updating PATH.

### ChromaDB Persistence
- **Issue**: Data not persisting across restarts.
- **Solution**: Check `backend/data/chroma` permissions. Ensure the path in `.env` is correct.

### Frontend API Proxy
- **Issue**: Frontend cannot connect to backend.
- **Solution**: Verify `VITE_API_BASE_URL` in `frontend/.env` matches your FastAPI host/port.
