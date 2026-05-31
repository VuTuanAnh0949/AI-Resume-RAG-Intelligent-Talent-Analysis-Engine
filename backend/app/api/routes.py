from pathlib import Path
import json

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.models.schemas import (
    CandidateProfile,
    IngestResponse,
    QueryRequest,
    UploadResponse,
)
from app.services import get_ingestion_service, get_rag_service

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@router.post("/ingest/dataset", response_model=IngestResponse)
def ingest_dataset(
    background_tasks: BackgroundTasks, 
    limit: int | None = None,
    offset: int = 0,
    skip_existing: bool = True,
    include_original: bool = True,
    include_synthetic: bool = True
) -> IngestResponse:
    settings = get_settings()
    dataset_dir = Path(settings.dataset_dir).resolve()
    if not dataset_dir.exists():
        print(f"\n[ERROR] Dataset directory not found at: {dataset_dir}")
        raise HTTPException(status_code=400, detail=f"Dataset directory not found: {dataset_dir}")

    service = get_ingestion_service()
    background_tasks.add_task(
        service.ingest_dataset_dir, 
        dataset_dir, 
        limit, 
        offset, 
        skip_existing,
        include_original,
        include_synthetic
    )
    msg = f"Ingestion started. Limit: {limit}, Skip: {skip_existing}, Org: {include_original}, AST: {include_synthetic}"
    return IngestResponse(status="started", count=None, message=msg)


@router.post("/ingest/upload", response_model=UploadResponse)
async def ingest_upload(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)) -> UploadResponse:
    settings = get_settings()
    
    saved_files = []
    uploads_dir = Path(settings.uploads_dir).resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            continue
        
        target = uploads_dir / upload.filename
        print(f"\n>>> Saving uploaded file to: {target}")
        content = await upload.read()
        target.write_bytes(content)
        saved_files.append(target)

    # Process sequentially in background to avoid overwhelming the LLM/Embedding APIs
    def process_uploads():
        service = get_ingestion_service()
        for pdf_path in saved_files:
            try:
                print(f"\n>>> Background processing uploaded file: {pdf_path.name}")
                service.ingest_pdf(pdf_path, pdf_path.stem, source="upload")
            except Exception as e:
                print(f"!!! Error processing uploaded file {pdf_path.name}: {e}")

    background_tasks.add_task(process_uploads)
    return UploadResponse(status="ok", count=len(saved_files))


@router.post("/query")
def query_candidates(payload: QueryRequest):
    service = get_rag_service()
    
    def event_generator():
        try:
            for chunk in service.query_stream(payload.query, payload.top_k):
                if isinstance(chunk, dict):
                    # Send metadata (candidates) as first chunk
                    yield f"METADATA:{json.dumps(chunk)}\nEND_METADATA\n"
                else:
                    # Send text tokens
                    yield chunk
        except Exception as e:
            yield f"Error during query: {str(e)}"

    return StreamingResponse(event_generator(), media_type="text/plain")


@router.get("/ingest/status")
def get_ingest_status():
    service = get_ingestion_service()
    return service.get_status()

import time
from app.services import get_ingestion_service, get_rag_service

# ... (rest of imports)

@router.get("/evaluation")
def get_evaluation_metrics():
    settings = get_settings()
    profiles_dir = Path(settings.profiles_dir)
    text_dir = Path(settings.text_dir)
    
    profiles = []
    if profiles_dir.exists():
        for path in profiles_dir.glob("*.json"):
            try:
                profiles.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass

    total = len(profiles)
    
    # 1. Calculate Faithfulness (Anti-Hallucination)
    # Checks if AI-extracted skills actually exist in source text
    total_skills_extracted = 0
    faithful_skills = 0
    
    for p in profiles:
        resume_id = p.get("resume_id")
        skills = p.get("skills", [])
        if not resume_id or not skills: continue
        
        raw_text_path = text_dir / f"{resume_id}.txt"
        if raw_text_path.exists():
            raw_text = raw_text_path.read_text(encoding="utf-8").lower()
            total_skills_extracted += len(skills)
            for skill in skills:
                if skill.lower() in raw_text:
                    faithful_skills += 1
                elif " " in skill and any(part in raw_text for part in skill.lower().split()):
                    faithful_skills += 1
                    
    faithfulness_score = round((faithful_skills / total_skills_extracted) * 100, 1) if total_skills_extracted > 0 else 0.0

    # 2. RAG Performance (Retrieval & Latency)
    rag = get_rag_service()
    test_queries = [
        {"q": "Find candidates with Python and Machine Learning experience.", "skills": ["python", "machine learning"]},
        {"q": "Recommend candidates suitable for a Data Engineer position.", "skills": ["data", "sql"]}
    ]
    
    latencies = []
    precision_scores = []
    
    for test in test_queries:
        start_time = time.perf_counter()
        try:
            candidates = rag.retrieve(test["q"], top_k=5)
            latency = time.perf_counter() - start_time
            latencies.append(latency)
            
            relevant_count = 0
            for c in candidates:
                skills_str = " ".join(c.skills).lower()
                req_skills = test.get("skills", [])
                if any(rs in skills_str for rs in req_skills):
                    relevant_count += 1
            
            query_precision = relevant_count / len(candidates) if candidates else 0.0
            precision_scores.append(query_precision)
        except Exception:
            pass

    avg_latency = round(sum(latencies) / len(latencies), 3) if latencies else 0.0
    overall_precision = round((sum(precision_scores) / len(precision_scores)) * 100, 1) if precision_scores else 0.0

    return {
        "sample_size": total,
        "rag_metrics": {
            "average_latency_sec": avg_latency,
            "retrieval_precision_at_5": overall_precision,
            "extraction_faithfulness": faithfulness_score,
            "system_health": "Degraded (Check Embeddings)" if overall_precision < 10 else "Optimal"
        }
    }

from fastapi.responses import FileResponse, StreamingResponse

@router.get("/candidates/{resume_id}/pdf")
def get_candidate_pdf(resume_id: str):
    settings = get_settings()
    
    # Resolve absolute paths to be safe
    uploads_dir = Path(settings.uploads_dir).resolve()
    dataset_dir = Path(settings.dataset_dir).resolve()
    
    # Check both potential locations
    paths = [
        uploads_dir / f"{resume_id}.pdf",
        dataset_dir / f"{resume_id}.pdf"
    ]
    
    for pdf_path in paths:
        if pdf_path.exists():
            return FileResponse(
                str(pdf_path), 
                media_type="application/pdf",
                content_disposition_type="inline"
            )
    
    # Debug print if not found
    print(f"\n[ERROR] PDF not found for ID: {resume_id}")
    print(f"Checked in: \n 1. {uploads_dir}\n 2. {dataset_dir}")
            
    raise HTTPException(status_code=404, detail=f"PDF file not found for ID: {resume_id}")


@router.get("/candidates/{resume_id}", response_model=CandidateProfile)
def get_candidate(resume_id: str, force_refresh: bool = False) -> CandidateProfile:
    settings = get_settings()
    profile_path = settings.profiles_dir / f"{resume_id}.json"
    
    existing_profile = None
    if profile_path.exists():
        try:
            existing_profile = CandidateProfile.model_validate_json(
                profile_path.read_text(encoding="utf-8")
            )
        except Exception:
            pass

    # If we have a profile, check if it's "incomplete" (no education AND no experience)
    is_incomplete = existing_profile and not existing_profile.education and not existing_profile.experience
    
    if existing_profile and not force_refresh and not is_incomplete:
        return existing_profile

    # Fallback/Refresh logic: Re-extract from Text or PDF
    text_path = settings.text_dir / f"{resume_id}.txt"
    pdf_path = None
    for p in [settings.dataset_dir / f"{resume_id}.pdf", settings.uploads_dir / f"{resume_id}.pdf"]:
        if p.exists():
            pdf_path = p
            break

    if text_path.exists() or pdf_path:
        from app.services import get_ingestion_service
        from app.services.extraction import extract_profile
        from app.services.llm import LLMClient
        
        # Use existing text if available for speed, otherwise full ingest
        if text_path.exists():
            text = text_path.read_text(encoding="utf-8")
            llm = LLMClient(settings)
            profile = extract_profile(text, resume_id, llm)
            # Save JSON
            payload = json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)
            profile_path.write_text(payload, encoding="utf-8")
            # Sync to Chroma
            service = get_ingestion_service()
            service.update_metadata_only(profile)
            return profile
        elif pdf_path:
            service = get_ingestion_service()
            return service.ingest_pdf(pdf_path, resume_id, source="refresh")
    
    if existing_profile:
        return existing_profile
        
    raise HTTPException(
        status_code=404, 
        detail=f"Candidate {resume_id} data not found."
    )
