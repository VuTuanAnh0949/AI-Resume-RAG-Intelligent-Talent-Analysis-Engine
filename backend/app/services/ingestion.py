from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from app.core.config import Settings
from app.models.schemas import CandidateProfile
from app.services.chroma_store import ChromaStore
from app.services.embeddings import EmbeddingService
from app.services.extraction import extract_profile
from app.services.llm import LLMClient
from app.services.pdf_extractor import extract_text_from_pdf
from app.services.text_chunker import chunk_text


from typing import Any, Dict

class IngestionService:
    # Global state to prevent parallel ingestion across requests
    _is_processing = False
    _status = {"current": 0, "total": 0, "last_file": "", "errors": 0}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = LLMClient(settings)
        self.embedder = EmbeddingService(settings)
        self.store = ChromaStore(settings)

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "is_processing": cls._is_processing,
            **cls._status
        }

    def ingest_dataset_dir(
        self, 
        dataset_dir: Path, 
        limit: int | None = None, 
        offset: int = 0,
        skip_existing: bool = True,
        include_original: bool = True,
        include_synthetic: bool = True
    ) -> int:
        if IngestionService._is_processing:
            print(">>> [REJECTED] Ingestion already in progress.")
            return 0
            
        try:
            IngestionService._is_processing = True
            print(f"\n>>> DEBUG: Scanning directory: {dataset_dir}")
            # Use rglob to find PDFs in subdirectories as well (e.g., AST_Data)
            all_pdfs = sorted(dataset_dir.rglob("*.pdf"))
            print(f">>> DEBUG: Found {len(all_pdfs)} total PDFs")
            
            # Filter based on type
            pdf_files = []
            for p in all_pdfs:
                is_ast = p.name.startswith("AST_")
                if is_ast and include_synthetic:
                    pdf_files.append(p)
                elif not is_ast and include_original:
                    pdf_files.append(p)

            total_available = len(pdf_files)
            
            # Apply offset and limit
            start_idx = offset
            end_idx = (offset + limit) if limit is not None else total_available
            pdf_files = pdf_files[start_idx:end_idx]

            IngestionService._status = {
                "current": 0,
                "total": len(pdf_files),
                "last_file": "",
                "errors": 0
            }

            print(f"\n>>> Starting ingestion. Include Original: {include_original}, Synthetic: {include_synthetic}")
            print(f">>> Processing: {len(pdf_files)} files")
            
            count = 0
            skipped = 0
            for idx, pdf_path in enumerate(pdf_files):
                try:
                    resume_id = pdf_path.stem
                    IngestionService._status["last_file"] = resume_id
                    IngestionService._status["current"] = idx + 1
                    
                    # Check if already exists to skip redundant LLM calls
                    profile_path = self.settings.profiles_dir / f"{resume_id}.json"
                    if skip_existing and profile_path.exists():
                        skipped += 1
                        continue
                    
                    print(f"\n--- Processing [{idx+1}/{len(pdf_files)}]: {resume_id} ---")
                    self.ingest_pdf(pdf_path, resume_id, source="dataset")
                    count += 1
                    # Small sleep to prevent hitting rate limits too fast
                    time.sleep(1)
                except Exception as e:
                    print(f"!!! Error processing {pdf_path.name}: {e}")
                    IngestionService._status["errors"] += 1
            
            print(f"\n>>> Ingestion complete. Processed: {count}, Skipped: {skipped}")
            return count
        finally:
            IngestionService._is_processing = False

    def ingest_pdf(
        self, pdf_path: Path, resume_id: str, source: str
    ) -> CandidateProfile:
        overall_start = time.perf_counter()

        # 0. Sync to Uploads (Centralize files for easy management/viewing)
        target_upload = self.settings.uploads_dir / f"{resume_id}.pdf"
        if pdf_path.resolve() != target_upload.resolve():
            try:
                target_upload.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf_path, target_upload)
                print(f"   [0/4] PDF copied to: {target_upload}")
            except Exception as e:
                print(f"   [!] Could not copy PDF to uploads: {e}")

        # 1. PDF Extraction
        start = time.perf_counter()
        text = extract_text_from_pdf(
            pdf_path,
            ocr_enabled=self.settings.ocr_enabled,
            min_text_chars=self.settings.min_text_chars,
            ocr_language=self.settings.ocr_language,
        )
        pdf_time = time.perf_counter() - start
        print(f"   [1/4] PDF Extracted: {len(text)} chars in {pdf_time:.2f}s")

        if not text or len(text.strip()) < 50:
            print(f"   [!] WARNING: Very little text extracted for {resume_id}")
            if not text: raise ValueError("No text extracted from PDF.")

        # 2. LLM Extraction
        start = time.perf_counter()
        profile = extract_profile(text, resume_id, self.llm, source=source)
        llm_time = time.perf_counter() - start
        
        # Check completeness
        fields_filled = sum(1 for v in [profile.name, profile.current_role, profile.years_experience] if v)
        print(f"   [2/4] LLM Extraction: Done in {llm_time:.2f}s (Basic Info Quality: {fields_filled}/3)")

        # 3. Persistence
        start = time.perf_counter()
        self._save_text(resume_id, text)
        self._save_profile(profile)
        save_time = time.perf_counter() - start

        # 4. Vector Indexing
        start = time.perf_counter()
        try:
            chunks = chunk_text(
                text, self.settings.max_chunk_size, self.settings.chunk_overlap
            )
            
            # This is where Gemini API is called
            embeddings = self.embedder.embed_texts(chunks)
            if not embeddings or len(embeddings) == 0:
                print(f"   [!] Skipping indexing for {resume_id} due to empty embeddings.")
                return profile

            embed_time = time.perf_counter() - start
            
            start = time.perf_counter()
            metadata = {
                "resume_id": resume_id,
                "name": profile.name or "",
                "current_role": profile.current_role or "",
                "years_experience": profile.years_experience or 0.0,
                "skills": ", ".join(profile.skills),
                "domain": profile.domain or "INFORMATION-TECHNOLOGY",
                "source": source,
            }
            metadatas = [metadata for _ in chunks]
            ids = [f"{resume_id}-{idx}" for idx in range(len(chunks))]

            self.store.add_texts(
                ids=ids, texts=chunks, embeddings=embeddings, metadatas=metadatas
            )
            db_time = time.perf_counter() - start
            
            total_time = time.perf_counter() - overall_start
            print(f"   [3/4] Saved to disk: {save_time:.3f}s")
            print(f"   [4/4] Indexed (Gemini API + Chroma): {embed_time:.2f}s + {db_time:.3f}s")
            print(f"   >>> Total time: {total_time:.2f}s")
        except Exception as e:
            print(f"   [!] Indexing error for {resume_id}: {e}")
        
        return profile

    def update_metadata_only(self, profile: CandidateProfile) -> None:
        text_path = self.settings.text_dir / f"{profile.resume_id}.txt"
        if not text_path.exists():
            return
            
        text = text_path.read_text(encoding="utf-8")
        chunks = chunk_text(
            text, self.settings.max_chunk_size, self.settings.chunk_overlap
        )
        
        metadata = {
            "resume_id": profile.resume_id,
            "name": profile.name or "",
            "current_role": profile.current_role or "",
            "years_experience": profile.years_experience or 0.0,
            "skills": ", ".join(profile.skills),
            "domain": profile.domain or "INFORMATION-TECHNOLOGY",
            "source": profile.source or "unknown",
        }
        
        for idx in range(len(chunks)):
            chunk_id = f"{profile.resume_id}-{idx}"
            self.store.collection.update(
                ids=[chunk_id],
                metadatas=[metadata]
            )

    def _save_text(self, resume_id: str, text: str) -> None:
        target = self.settings.text_dir / f"{resume_id}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def _save_profile(self, profile: CandidateProfile) -> None:
        target = self.settings.profiles_dir / f"{profile.resume_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)
        target.write_text(payload, encoding="utf-8")
