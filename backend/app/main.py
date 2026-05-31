import os
import sys

# CRITICAL: Disable ChromaDB telemetry before ANY other imports
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_NO_ANONYMOUS"] = "True"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import ensure_dirs, get_settings, parse_origins

settings = get_settings()
ensure_dirs(settings)

app = FastAPI(title="IT Resume RAG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(settings.allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
