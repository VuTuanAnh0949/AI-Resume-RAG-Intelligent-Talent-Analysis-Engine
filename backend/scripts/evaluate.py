from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.services.ingestion import IngestionService
from app.services.rag import RAGService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a lightweight evaluation report"
    )
    parser.add_argument("--limit", type=int, default=20, help="Max resumes to ingest")
    parser.add_argument(
        "--dataset", type=str, default=None, help="Dataset folder override"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output markdown report (default: docs/evaluation_report.md)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingestion if the index already exists",
    )
    args = parser.parse_args()

    settings = get_settings()
    dataset_dir = Path(args.dataset) if args.dataset else Path(settings.dataset_dir)
    report_path = (
        Path(args.out)
        if args.out
        else settings.root_dir / "docs" / "evaluation_report.md"
    )

    if not dataset_dir.exists():
        raise SystemExit(f"Dataset directory not found: {dataset_dir}")

    pdf_files = sorted(dataset_dir.glob("*.pdf"))
    if args.limit is not None:
        pdf_files = pdf_files[: args.limit]

    resume_ids = [path.stem for path in pdf_files]
    ingestion = IngestionService(settings)

    ingest_seconds = 0.0
    if not args.skip_ingest:
        start_ingest = time.perf_counter()
        ingestion.ingest_dataset_dir(dataset_dir, args.limit)
        ingest_seconds = time.perf_counter() - start_ingest

    profiles = _load_profiles(settings.profiles_dir, resume_ids)
    coverage = _field_coverage(profiles)

    rag = RAGService(settings)
    query_results = []
    latencies = []
    for item in _evaluation_queries():
        start = time.perf_counter()
        answer, candidates = rag.query(item["query"], top_k=5)
        latency = time.perf_counter() - start
        latencies.append(latency)
        match = _candidate_matches(candidates, item)
        query_results.append(
            {
                "query": item["label"],
                "latency": latency,
                "match": match,
                "answer": answer,
                "top_candidate": candidates[0].resume_id if candidates else "N/A",
            }
        )

    report = _build_report(
        dataset_dir=dataset_dir,
        sample_size=len(resume_ids),
        ingest_seconds=ingest_seconds,
        coverage=coverage,
        query_results=query_results,
        latency_avg=statistics.mean(latencies) if latencies else 0.0,
    )

    report_path.write_text(report, encoding="utf-8")
    print(f"Report written to {report_path}")


def _load_profiles(profiles_dir: Path, resume_ids: list[str]) -> list[dict]:
    profiles = []
    for resume_id in resume_ids:
        path = profiles_dir / f"{resume_id}.json"
        if not path.exists():
            continue
        profiles.append(json.loads(path.read_text(encoding="utf-8")))
    return profiles


def _field_coverage(profiles: list[dict]) -> dict[str, float]:
    fields = [
        "name",
        "email",
        "phone",
        "skills",
        "education",
        "experience",
        "current_role",
        "years_experience",
    ]
    if not profiles:
        return {field: 0.0 for field in fields}

    totals = {field: 0 for field in fields}
    for profile in profiles:
        for field in fields:
            value = profile.get(field)
            if isinstance(value, list):
                filled = len(value) > 0
            else:
                filled = value not in (None, "")
            totals[field] += 1 if filled else 0

    return {field: totals[field] / len(profiles) for field in fields}


def _evaluation_queries() -> list[dict]:
    return [
        {
            "label": "Python + ML",
            "query": "Find candidates with Python and Machine Learning experience.",
            "skills": ["python", "machine learning"],
            "min_years": None,
            "role_contains": None,
        },
        {
            "label": "Risk management",
            "query": "Show INFORMATION-TECHNOLOGY candidates with risk management experience.",
            "skills": ["risk management"],
            "min_years": None,
            "role_contains": None,
        },
        {
            "label": "5+ years",
            "query": "Which candidates have more than 5 years of experience?",
            "skills": [],
            "min_years": 5,
            "role_contains": None,
        },
        {
            "label": "Data Engineer",
            "query": "Recommend candidates suitable for a Data Engineer position.",
            "skills": ["data engineer", "data engineering"],
            "min_years": None,
            "role_contains": "data engineer",
        },
    ]


def _candidate_matches(candidates: list, query: dict) -> bool:
    if not candidates:
        return False

    top = candidates[0]
    skills = {skill.lower() for skill in (top.skills or [])}

    for required in query["skills"]:
        if required not in skills:
            return False

    if query["min_years"] is not None:
        if (top.years_experience or 0) < query["min_years"]:
            return False

    if query["role_contains"]:
        role = (top.current_role or "").lower()
        if query["role_contains"] not in role and query["role_contains"] not in skills:
            return False

    return True


def _build_report(
    dataset_dir: Path,
    sample_size: int,
    ingest_seconds: float,
    coverage: dict[str, float],
    query_results: list[dict],
    latency_avg: float,
) -> str:
    lines = [
        "# Evaluation Report",
        "",
        "This report is generated by backend/scripts/evaluate.py.",
        "",
        "## Scope",
        f"- Dataset: {dataset_dir}",
        f"- Sample size: {sample_size}",
        f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Extraction Coverage",
        "Field coverage rate (non-empty values):",
        "",
    ]

    for field, rate in coverage.items():
        lines.append(f"- {field}: {rate:.2f}")

    lines.extend(
        [
            "",
            "## Retrieval Quality (Heuristic)",
            "Top candidate meets the query constraint:",
            "",
        ]
    )

    for result in query_results:
        status = "PASS" if result["match"] else "FAIL"
        lines.append(
            f"- {result['query']}: {status} | latency {result['latency']:.2f}s | top {result['top_candidate']}"
        )

    lines.extend(
        [
            "",
            "## Response Latency",
            f"- Average query latency: {latency_avg:.2f}s",
        ]
    )

    if ingest_seconds > 0 and sample_size > 0:
        lines.append(
            f"- Ingestion time per resume: {ingest_seconds / sample_size:.2f}s"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    main()
