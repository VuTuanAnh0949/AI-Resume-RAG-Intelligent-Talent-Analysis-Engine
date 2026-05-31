from functools import lru_cache

from app.core.config import get_settings
from app.services.ingestion import IngestionService
from app.services.rag import RAGService


@lru_cache
def get_ingestion_service() -> IngestionService:
    settings = get_settings()
    return IngestionService(settings)


@lru_cache
def get_rag_service() -> RAGService:
    settings = get_settings()
    return RAGService(settings)
