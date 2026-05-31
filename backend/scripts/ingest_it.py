from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.services.ingestion import IngestionService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest INFORMATION-TECHNOLOGY resumes"
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of PDFs")
    parser.add_argument(
        "--dataset", type=str, default=None, help="Override dataset dir"
    )
    args = parser.parse_args()

    settings = get_settings()
    dataset_dir = Path(args.dataset) if args.dataset else Path(settings.dataset_dir)

    service = IngestionService(settings)
    count = service.ingest_dataset_dir(dataset_dir, args.limit)
    print(f"Ingested {count} resumes.")


if __name__ == "__main__":
    main()
