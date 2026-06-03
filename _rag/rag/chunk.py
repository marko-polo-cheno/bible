import re

from .config import (
    EN_CHUNK_WORD_OVERLAP,
    EN_CHUNK_WORDS,
    ZH_CHUNK_CHAR_OVERLAP,
    ZH_CHUNK_CHARS,
    ZH_LANG_ID,
)
from .corpus import CorpusDoc, doc_embed_text
from .models import ChunkRecord

_WORD_RE = re.compile(r"\S+")


def _chunk_by_words(text: str, size: int, overlap: int) -> list[str]:
    words = _WORD_RE.findall(text)
    if not words:
        return []
    if len(words) <= size:
        return [text.strip()]
    stride = max(1, size - overlap)
    chunks: list[str] = []
    for start in range(0, len(words), stride):
        part = words[start : start + size]
        if not part:
            break
        chunks.append(" ".join(part))
        if start + size >= len(words):
            break
    return chunks


def _chunk_by_chars(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    stride = max(1, size - overlap)
    chunks: list[str] = []
    for start in range(0, len(text), stride):
        part = text[start : start + size]
        if not part:
            break
        chunks.append(part)
        if start + size >= len(text):
            break
    return chunks


def _chunk_texts(doc: CorpusDoc, text: str) -> list[str]:
    if doc.lang_id == ZH_LANG_ID:
        return _chunk_by_chars(text, ZH_CHUNK_CHARS, ZH_CHUNK_CHAR_OVERLAP)
    return _chunk_by_words(text, EN_CHUNK_WORDS, EN_CHUNK_WORD_OVERLAP)


def chunk_document(doc: CorpusDoc, start_id: int) -> tuple[list[ChunkRecord], int]:
    text = doc_embed_text(doc)
    if not text.strip():
        return [], start_id

    texts = _chunk_texts(doc, text)
    if not texts:
        return [], start_id

    chunks: list[ChunkRecord] = []
    next_id = start_id
    for chunk_index, chunk_text in enumerate(texts):
        chunks.append(
            ChunkRecord(
                chunk_id=next_id,
                filename=doc.filename,
                link=doc.link,
                category=doc.category,
                lang_id=doc.lang_id,
                item_id=doc.item_id,
                chunk_index=chunk_index,
                text=chunk_text,
            )
        )
        next_id += 1
    return chunks, next_id


def chunk_corpus(docs: list[CorpusDoc]) -> list[ChunkRecord]:
    all_chunks: list[ChunkRecord] = []
    next_id = 0
    for doc in docs:
        doc_chunks, next_id = chunk_document(doc, next_id)
        all_chunks.extend(doc_chunks)
    return all_chunks
