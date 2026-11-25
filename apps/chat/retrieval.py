import re
import unicodedata

from django.db.models import QuerySet

from apps.knowledge.models import Chunk


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "does", "for",
    "from", "how", "in", "into", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "was", "what", "when", "where", "which", "who", "with",
}


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    )
    return {
        token
        for token in re.findall(r"\w+", ascii_text)
        if token not in _STOP_WORDS
    }


def top_chunks(
    question: str,
    chunks: QuerySet[Chunk],
    k: int = 4,
) -> list[tuple[Chunk, int]]:
    q = _tokens(question)
    scored = []
    for chunk in chunks.iterator():
        haystack = f"{chunk.title} {chunk.text}"
        score = len(q & _tokens(haystack))
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [(chunk, score) for score, chunk in scored[:k]]