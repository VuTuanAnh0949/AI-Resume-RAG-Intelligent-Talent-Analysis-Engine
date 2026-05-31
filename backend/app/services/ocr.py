from __future__ import annotations

from pathlib import Path

import pytesseract
from pdf2image import convert_from_path


def ocr_pdf_to_text(pdf_path: Path, language: str) -> str:
    try:
        images = convert_from_path(str(pdf_path))
    except Exception:
        return ""

    chunks: list[str] = []
    for image in images:
        chunks.append(pytesseract.image_to_string(image, lang=language))
    return "\n".join(chunks)
