from __future__ import annotations

from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import Settings


class ChromaStore:
    def __init__(self, settings: Settings) -> None:
        self.client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="resumes",
            metadata={"hnsw:space": "cosine"},
        )

    def add_texts(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        try:
            self.collection.upsert(
                ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                print(f"\n[!] Dimension mismatch detected ({e}). Resetting collection...")
                self.client.delete_collection(name="resumes")
                self.collection = self.client.get_or_create_collection(
                    name="resumes",
                    metadata={"hnsw:space": "cosine"},
                )
                # Retry once after reset
                self.collection.upsert(
                    ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas
                )
            else:
                raise e

    def query(
        self,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
