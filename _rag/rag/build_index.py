"""CLI: stream testimony JSONLs → chunk → embed → persist FAISS index."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Iterator, List, Optional

import orjson
from loguru import logger
from tqdm import tqdm

from .chunk import chunk_tokens, prefix_with_title
from .config import (
    CHUNK_OVERLAP,
    CHUNK_TOKENS,
    DEFAULT_EN_PATH,
    DEFAULT_INDEX_DIR,
    DEFAULT_ZH_PATH,
    EMBED_DIM,
    MODEL_NAME,
    ensure_hf_home,
)
from .embedder import Embedder
from .index import MANIFEST_FILE, RagIndex


def iter_docs(path: Path, lang: str, limit: Optional[int] = None) -> Iterator[dict]:
    with open(path, "rb") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            d = orjson.loads(line)
            d["__lang"] = lang
            d["__doc_id"] = f"{lang}:{i}"
            yield d


def make_chunk_records(doc: dict, tokenizer, max_tokens: int, overlap: int) -> List[dict]:
    title = doc.get("filename") or ""
    content = doc.get("content") or ""
    full = prefix_with_title(content, title)
    recs: List[dict] = []
    for ch in chunk_tokens(full, tokenizer, max_tokens=max_tokens, overlap=overlap):
        recs.append({
            "chunk_id": f"{doc['__doc_id']}#{ch.chunk_idx}",
            "doc_id": doc["__doc_id"],
            "lang": doc["__lang"],
            "filename": title,
            "link": doc.get("link", ""),
            "category": doc.get("category", []) or [],
            "chunk_idx": ch.chunk_idx,
            "text": ch.text,
        })
    return recs


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build(
    en_path: Path,
    zh_path: Path,
    out_dir: Path,
    batch_size: int = 64,
    limit: Optional[int] = None,
) -> None:
    ensure_hf_home()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    embedder = Embedder(batch_size=batch_size)
    tok = embedder.tokenizer
    rag = RagIndex(dim=EMBED_DIM)

    flush_threshold = batch_size * 4
    buf_texts: List[str] = []
    buf_recs: List[dict] = []

    def flush():
        if not buf_texts:
            return
        vecs = embedder.embed(buf_texts, batch_size=batch_size)
        rag.add(vecs, buf_recs)
        buf_texts.clear()
        buf_recs.clear()

    total_docs = 0
    sources = [("en", Path(en_path)), ("zh", Path(zh_path))]
    for lang, path in sources:
        if not path.exists():
            logger.warning(f"Missing source for lang={lang}: {path}")
            continue
        logger.info(f"Indexing {lang} from {path}")
        for doc in tqdm(iter_docs(path, lang, limit=limit), desc=f"{lang} docs", unit="doc"):
            total_docs += 1
            for rec in make_chunk_records(doc, tok, CHUNK_TOKENS, CHUNK_OVERLAP):
                buf_texts.append(rec["text"])
                buf_recs.append(rec)
                if len(buf_texts) >= flush_threshold:
                    flush()
    flush()

    rag.save(out_dir)

    full_corpus = limit is None
    manifest = {
        "model": MODEL_NAME,
        "dim": EMBED_DIM,
        "chunk_tokens": CHUNK_TOKENS,
        "chunk_overlap": CHUNK_OVERLAP,
        "num_docs": total_docs,
        "num_chunks": rag.index.ntotal,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "limit": limit,
        "sources": {
            "en": {
                "path": str(en_path),
                "sha256": sha256_file(en_path) if full_corpus and Path(en_path).exists() else None,
            },
            "zh": {
                "path": str(zh_path),
                "sha256": sha256_file(zh_path) if full_corpus and Path(zh_path).exists() else None,
            },
        },
    }
    with open(out_dir / MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"Done. Indexed {rag.index.ntotal} chunks from {total_docs} docs into {out_dir}")


def main() -> None:
    p = argparse.ArgumentParser(description="Build the testimony RAG index.")
    p.add_argument("--en-path", type=Path, default=DEFAULT_EN_PATH)
    p.add_argument("--zh-path", type=Path, default=DEFAULT_ZH_PATH)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_INDEX_DIR)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--limit", type=int, default=None,
                   help="smoke-test: only read the first N lines from each JSONL")
    args = p.parse_args()
    build(args.en_path, args.zh_path, args.out_dir, args.batch_size, args.limit)


if __name__ == "__main__":
    main()
