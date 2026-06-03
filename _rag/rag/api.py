"""FastAPI endpoint over the built RAG index."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import List, Literal

from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from .config import ensure_hf_home, resolve_index_dir
from .embedder import Embedder
from .index import MANIFEST_FILE, RagIndex


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(10, ge=1, le=100)
    lang: Literal["en", "zh", "both"] = "both"


class ResultItem(BaseModel):
    score: float
    doc_id: str
    lang: str
    filename: str
    link: str
    category: List[str] = Field(default_factory=list)
    chunk_idx: int
    snippet: str
    text: str


class QueryResponse(BaseModel):
    query: str
    k: int
    lang: str
    results: List[ResultItem]


STATE: dict = {}


def _snippet(text: str, n: int = 240) -> str:
    text = text.replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_hf_home()
    index_dir = resolve_index_dir()
    logger.info(f"Loading index from {index_dir}")
    rag = RagIndex.load(index_dir)
    embedder = Embedder()
    manifest_path = index_dir / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    STATE.update({"rag": rag, "embedder": embedder, "manifest": manifest})
    yield
    STATE.clear()


app = FastAPI(title="Testimonies RAG", lifespan=lifespan)


@app.get("/health")
def health():
    rag = STATE.get("rag")
    if rag is None:
        raise HTTPException(503, "index not loaded")
    return {
        "ok": True,
        "num_chunks": rag.index.ntotal,
        "manifest": STATE.get("manifest", {}),
    }


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    rag: RagIndex | None = STATE.get("rag")
    embedder: Embedder | None = STATE.get("embedder")
    if rag is None or embedder is None:
        raise HTTPException(503, "index not loaded")
    qvec = embedder.embed([req.query])
    hits = rag.search(qvec, k=req.k, lang=req.lang)
    return QueryResponse(
        query=req.query,
        k=req.k,
        lang=req.lang,
        results=[
            ResultItem(
                score=h.score,
                doc_id=h.doc_id,
                lang=h.lang,
                filename=h.filename,
                link=h.link,
                category=list(h.category) if h.category else [],
                chunk_idx=h.chunk_idx,
                snippet=_snippet(h.text),
                text=h.text,
            )
            for h in hits
        ],
    )
