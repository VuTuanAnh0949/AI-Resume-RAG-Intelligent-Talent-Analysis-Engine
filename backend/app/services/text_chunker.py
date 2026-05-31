from __future__ import annotations


def chunk_text(text: str, max_size: int, overlap: int) -> list[str]:
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    overlap_words = max(1, overlap // 6)
    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = start
        length = 0
        while end < len(words) and length + len(words[end]) + 1 <= max_size:
            length += len(words[end]) + 1
            end += 1

        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break
        start = max(0, end - overlap_words)

    return chunks
