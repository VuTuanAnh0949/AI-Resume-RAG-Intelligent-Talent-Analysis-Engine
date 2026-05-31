from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def project_root(self) -> Path:
        # Resolve absolute path to the project root (3 levels up from this file)
        return Path(__file__).resolve().parents[3]

    @property
    def data_dir(self) -> Path: 
        return self.project_root / "data"
    
    @property
    def uploads_dir(self) -> Path: 
        return self.data_dir / "uploads"
    
    @property
    def profiles_dir(self) -> Path: 
        return self.data_dir / "profiles"
    
    @property
    def text_dir(self) -> Path: 
        return self.data_dir / "text"
    
    @property
    def chroma_dir(self) -> Path: 
        return self.data_dir / "chroma"
    
    @property
    def dataset_dir(self) -> Path: 
        # SMART PATH DISCOVERY
        # 1. Check if user provided an override that actually exists
        if self.dataset_dir_override:
            p = Path(self.dataset_dir_override)
            if not p.is_absolute():
                p = self.project_root / p
            if p.exists(): return p.resolve()
            
        # 2. Check standard location 1: Technical test ITL/Resume_Dataset/data/INFORMATION-TECHNOLOGY
        path1 = self.project_root / "Resume_Dataset" / "data" / "INFORMATION-TECHNOLOGY"
        if path1.exists(): return path1.resolve()

        # 3. Check standard location 2: Technical test ITL/Resume_Dataset/data/data/INFORMATION-TECHNOLOGY (nested data)
        path2 = self.project_root / "Resume_Dataset" / "data" / "data" / "INFORMATION-TECHNOLOGY"
        if path2.exists(): return path2.resolve()

        # 4. Fallback: Search for any INFORMATION-TECHNOLOGY folder inside Resume_Dataset
        dataset_base = self.project_root / "Resume_Dataset"
        if dataset_base.exists():
            for root, dirs, _ in os.walk(dataset_base):
                if "INFORMATION-TECHNOLOGY" in dirs:
                    return Path(root) / "INFORMATION-TECHNOLOGY"

        # Final fallback to root
        return path1

    # Field for .env override (DATASET_DIR)
    dataset_dir_override: str | None = Field(default=None, alias="DATASET_DIR")

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    gemini_api_key: str | None = None
    embeddings_model: str = "text-embedding-004"

    max_chunk_size: int = 900
    chunk_overlap: int = 150

    ocr_enabled: bool = True
    ocr_language: str = "eng"
    min_text_chars: int = 200

    allow_origins: str = "http://localhost:5173"


def parse_origins(origins: str) -> list[str]:
    return [item.strip() for item in origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Check if dataset actually exists and log it clearly
    final_path = s.dataset_dir
    if final_path.exists():
        print(f"\n[OK] Dataset found at: {final_path}")
    else:
        print(f"\n[CRITICAL] Dataset NOT FOUND. Checked root: {s.project_root}")
    return s


def ensure_dirs(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.profiles_dir.mkdir(parents=True, exist_ok=True)
    settings.text_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
