from pathlib import Path

import pdfplumber

from app.services.ocr import ocr_pdf_to_text


def extract_text_from_pdf(
    pdf_path: Path,
    ocr_enabled: bool,
    min_text_chars: int,
    ocr_language: str,
) -> str:
    text_parts: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(layout=True) or ""
                text_parts.append(page_text)
    except Exception as e:
        print(f"pdfplumber error for {pdf_path}: {e}")
        text_parts = []

    text = _clean_text("\n".join(text_parts))

    # Fallback to OCR when the PDF text is too short or likely garbage.
    if (len(text) < min_text_chars or _is_mostly_garbage(text)) and ocr_enabled:
        ocr_text = ocr_pdf_to_text(pdf_path, ocr_language)
        if ocr_text:
            text = _clean_text(ocr_text)

    return text


def _clean_text(text: str) -> str:
    # Preserve some structure but clean up multiple spaces and excessive newlines
    lines = []
    for line in text.splitlines():
        cleaned_line = " ".join(line.split())
        if cleaned_line:
            lines.append(cleaned_line)
    return "\n\n".join(lines)


def _is_mostly_garbage(text: str) -> bool:
    if not text:
        return True
    # If a large portion of the text is non-alphanumeric, it's likely garbage encoding
    alnum_chars = sum(1 for c in text if c.isalnum())
    if alnum_chars / len(text) < 0.3:
        return True
    return False
