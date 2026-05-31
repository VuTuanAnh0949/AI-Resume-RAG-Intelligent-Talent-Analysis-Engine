from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import Settings
from app.models.schemas import CandidateSummary
from app.services.chroma_store import ChromaStore
from app.services.embeddings import EmbeddingService
from app.services.extraction import SKILL_KEYWORDS
from app.services.llm import LLMClient


class RAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ChromaStore(settings)
        self.embedder = EmbeddingService(settings)
        self.llm = LLMClient(settings)

    def query(self, query: str, top_k: int) -> tuple[str, list[CandidateSummary]]:
        candidates = self.retrieve(query, top_k)
        answer = _build_answer(query, candidates, self.llm)
        return answer, candidates

    def query_stream(self, query: str, top_k: int):
        candidates = self.retrieve(query, top_k)
        # Enrich candidates from disk if they have a JSON profile
        enriched = []
        for c in candidates:
            profile_path = self.settings.profiles_dir / f"{c.resume_id}.json"
            if profile_path.exists():
                try:
                    with open(profile_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        c.name = data.get("name") or c.name
                        c.current_role = data.get("current_role") or c.current_role
                        c.skills = data.get("skills") or c.skills
                        c.years_experience = data.get("years_experience") or c.years_experience
                except Exception:
                    pass
            enriched.append(c)
            
        yield {"candidates": [c.model_dump() for c in enriched]}
        
        # Then stream the answer
        for token in _build_answer_stream(query, enriched, self.llm):
            yield token

    def retrieve(self, query: str, top_k: int) -> list[CandidateSummary]:
        query_embedding = self.embedder.embed_texts([query])[0]
        where = _build_filters(query)
        requested_skills = _extract_query_skills(query)
        
        # Increase search depth to find more candidates before filtering
        search_k = max(25, top_k * 5)
        results = self.store.query(query_embedding, top_k=search_k, where=where)
        
        all_candidates = _build_candidates(results)
        
        # If we have requested skills, prioritize candidates with those skills
        if requested_skills:
            filtered = _filter_by_skills(all_candidates, requested_skills)
            if filtered:
                seen_ids = {c.resume_id for c in filtered}
                others = [c for c in all_candidates if c.resume_id not in seen_ids]
                return (filtered + others)[:top_k]
                
        return all_candidates[:top_k]


def _build_filters(query: str) -> dict[str, Any] | None:
    query_lower = query.lower()
    filters: dict[str, Any] = {}

    if (
        "information-technology" in query_lower
        or "information technology" in query_lower
    ):
        filters["domain"] = "INFORMATION-TECHNOLOGY"

    # Precise year extraction: only filter if user says "more than X years"
    years_match = re.search(r"(\d+)\s*(?:\+)?\s*years?", query_lower)
    if years_match:
        try:
            years = float(years_match.group(1))
            filters["years_experience"] = {"$gte": years}
        except ValueError:
            pass

    return filters or None


def _extract_query_skills(query: str) -> list[str]:
    lower = query.lower()
    skills = [skill for skill in SKILL_KEYWORDS if skill in lower]
    for alias, canonical in _QUERY_SKILL_ALIASES.items():
        if _contains_word(lower, alias) and canonical not in skills:
            skills.append(canonical)
    return skills


def _build_candidates(results: dict[str, Any]) -> list[CandidateSummary]:
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    grouped: dict[str, CandidateSummary] = {}
    for doc, meta, distance in zip(docs, metas, distances):
        resume_id = meta.get("resume_id")
        if not resume_id:
            continue
        similarity = round(1 - float(distance), 4)
        existing = grouped.get(resume_id)
        if existing and existing.score is not None and similarity <= existing.score:
            continue

        skills = _split_skills(meta.get("skills", ""))
        grouped[resume_id] = CandidateSummary(
            resume_id=resume_id,
            name=meta.get("name") or None,
            current_role=meta.get("current_role") or None,
            years_experience=float(meta.get("years_experience", 0.0)),
            skills=skills,
            score=similarity,
            evidence=_shorten(doc),
        )

    candidates = sorted(
        grouped.values(), key=lambda item: item.score or 0.0, reverse=True
    )
    return candidates


def _filter_by_skills(
    candidates: list[CandidateSummary],
    required_skills: list[str],
) -> list[CandidateSummary]:
    if not required_skills:
        return candidates

    required = {skill.lower() for skill in required_skills}
    filtered: list[CandidateSummary] = []
    for candidate in candidates:
        skills = {skill.lower() for skill in candidate.skills}
        # Flexible matching: if ANY of requested skills found
        if any(req in skills for req in required):
            filtered.append(candidate)
    return filtered


def _build_answer(
    query: str, candidates: list[CandidateSummary], llm: LLMClient
) -> str:
    if not candidates:
        return "No matching candidates found."

    best = candidates[0]
    if not llm.is_available():
        return _fallback_answer(query, best)

    context = []
    for candidate in candidates[:3]:
        context.append(
            f"ID: {candidate.resume_id}\n"
            f"Name: {candidate.name}\n"
            f"Role: {candidate.current_role}\n"
            f"Years: {candidate.years_experience}\n"
            f"Skills: {', '.join(candidate.skills)}\n"
            f"Evidence: {candidate.evidence}\n"
        )

    prompt = (
        "Based on the context, who is the best candidate? "
        "Answer in ONE short sentence starting with 'Best candidate is...'\n\n"
        f"Query: {query}\n\n"
        "Candidates:\n" + "\n".join(context)
    )

    try:
        return llm.generate(prompt)
    except Exception:
        return _fallback_answer(query, best)


def _build_answer_stream(
    query: str, candidates: list[CandidateSummary], llm: LLMClient
):
    if not candidates:
        yield "No matching candidates found."
        return

    best = candidates[0]
    if not llm.is_available():
        yield _fallback_answer(query, best)
        return

    context = []
    # Provide info on up to 5 candidates for more context
    for candidate in candidates[:5]:
        context.append(
            f"ID: {candidate.resume_id}\n"
            f"Name: {candidate.name}\n"
            f"Role: {candidate.current_role}\n"
            f"Years: {candidate.years_experience}\n"
            f"Skills: {', '.join(candidate.skills)}\n"
            f"Evidence: {candidate.evidence}\n"
        )

    prompt = (
        "You are an HR Assistant. Based on the candidates below, answer the user's request. "
        "Summarize why the top choices are suitable. Start with 'Based on your search, here are the best matches...'\n"
        "IMPORTANT RULE: Whenever you mention a candidate's name, you MUST include their ID in parentheses immediately after it, like this: 'John Doe (ID: 12345678)'. Do not just say their name.\n\n"
        f"Query: {query}\n\n"
        "Candidates Data:\n" + "\n".join(context)
    )

    try:
        for token in llm.stream(prompt):
            yield token
    except Exception:
        yield _fallback_answer(query, best)


def _fallback_answer(query: str, best: CandidateSummary) -> str:
    return (
        f"Best candidate for '{query}': {best.name or 'Unknown'} "
        f"(ID {best.resume_id}). Role: {best.current_role or 'N/A'}."
    )


def _split_skills(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _shorten(text: str, limit: int = 240) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _contains_word(text: str, word: str) -> bool:
    pattern = rf"\b{re.escape(word)}\b"
    return re.search(pattern, text) is not None


_QUERY_SKILL_ALIASES = {
    "ml": "machine learning",
    "ai": "machine learning",
}
