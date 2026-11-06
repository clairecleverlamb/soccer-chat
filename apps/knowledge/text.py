"""Pure text helpers for the knowledge dataset.

These functions do not touch the database. Loading and publishing call them
so the same document always chunks and hashes the same way.
"""

import hashlib
import json


def document_hash(title: str, body: str, metadata: dict) -> str:
    """Fingerprint the fields that change what a document means."""
    payload = json.dumps(
        {"title": title, "body": body, "metadata": metadata},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping pieces that retrieval can return.

    Breaks on a space when one falls inside the window, so a chunk tends to
    end on a word. Each step moves forward, so overlap cannot stall the loop.
    """
    if size <= 0:
        raise ValueError("Chunk size must be positive.")
    if overlap < 0 or overlap >= size:
        raise ValueError("Chunk overlap must be zero or smaller than the chunk size.")

    normalized = " ".join(text.split())
    if not normalized:
        return []
    if len(normalized) <= size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        if end < len(normalized):
            split_at = normalized.rfind(" ", start + overlap, end)
            if split_at > start:
                end = split_at
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(normalized):
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks
