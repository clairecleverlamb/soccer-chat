import re

def _tokens(text):
    return set(re.findall(r"\w+", text.lower()))

def top_chunks(question, chunks, k=4):
    q = _tokens(question)
    scored = []
    for chunk in chunks.iterator():
        haystack = f"{chunk.title} {chunk.text}"
        score = len(q & _tokens(haystack))
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [(chunk, score) for score, chunk in scored[:k]]