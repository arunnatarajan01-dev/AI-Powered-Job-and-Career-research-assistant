"""Chunk a document and retrieve the passages that match a question."""

import re

_STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "what", "how", "does", "do", "from", "that", "this",
}


def chunk_document(text, size=900, overlap=120):
    """Split source text into overlapping passages."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]
    if not paragraphs:
        raw = " ".join((text or "").split())
        paragraphs = [raw[i:i + size] for i in range(0, len(raw), size)] if raw else []
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = (tail + " " + paragraph).strip()
        else:
            current = (current + "\n\n" + paragraph).strip() if current else paragraph
    if current:
        chunks.append(current)
    return chunks


def _tokens(text):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {word for word in words if word not in _STOP and len(word) > 2}


def retrieve(query, document, k=4):
    """Return the top passages for a question. Generation uses these, not the whole file."""
    chunks = chunk_document(document)
    if not chunks:
        return []
    query_terms = _tokens(query)
    scored = []
    for chunk in chunks:
        terms = _tokens(chunk)
        overlap = len(query_terms & terms)
        scored.append((overlap, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    chosen = [chunk for score, chunk in scored if score > 0][:k]
    if chosen:
        return chosen
    return [chunk for _, chunk in scored[:k]]
