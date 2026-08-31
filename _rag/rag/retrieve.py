import logging
import os
from pathlib import Path

import faiss
import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel

from .index import MODEL_NAME, _normalize, load_index
from .models import RetrieveHit, RetrieveResult

logger = logging.getLogger(__name__)


def _category_matches(entry_cats: list[str], filter_cats: list[str]) -> bool:
    if not filter_cats:
        return True
    return any(
        ec == sc or ec.startswith(sc + "/")
        for ec in entry_cats
        for sc in filter_cats
    )


def retrieve(
    query: str,
    top_k: int = 10,
    lang_id: int | None = None,
    category_prefixes: list[str] | None = None,
    index_dir: Path | None = None,
    gpu_id: int = 0,
) -> RetrieveResult:
    try:
        index, chunks = load_index(index_dir)
        use_cuda = torch.cuda.is_available()
        if use_cuda:
            os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        model = BGEM3FlagModel(
            MODEL_NAME,
            use_fp16=use_cuda,
            device=f"cuda:{gpu_id}" if use_cuda else "cpu",
        )
        out = model.encode([query], batch_size=1, max_length=512)
        dense = out["dense_vecs"]
        if isinstance(dense, list):
            dense = np.array(dense, dtype=np.float32)
        qvec = _normalize(np.asarray(dense, dtype=np.float32))

        params = None
        if lang_id is not None:
            rows = [i for i, c in enumerate(chunks) if c.lang_id == lang_id]
            if not rows:
                logger.warning("No indexed chunks for lang_id=%s", lang_id)
                return RetrieveResult(query=query, results=[])
            params = faiss.SearchParameters()
            params.sel = faiss.IDSelectorBatch(np.asarray(rows, dtype=np.int64))
            search_k = min(len(rows), max(top_k * 5, top_k))
        else:
            search_k = min(len(chunks), max(top_k * 5, top_k))

        if params is not None:
            scores, indices = index.search(qvec, search_k, params=params)
        else:
            scores, indices = index.search(qvec, search_k)

        hits: list[RetrieveHit] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = chunks[int(idx)]
            if not _category_matches(chunk.category, category_prefixes or []):
                continue
            snippet = chunk.text[:500] + ("..." if len(chunk.text) > 500 else "")
            hits.append(
                RetrieveHit(
                    score=float(score),
                    filename=chunk.filename,
                    link=chunk.link,
                    lang_id=chunk.lang_id,
                    category=chunk.category,
                    snippet=snippet,
                    chunk_index=chunk.chunk_index,
                )
            )
            if len(hits) >= top_k:
                break

        return RetrieveResult(query=query, results=hits)
    except Exception as e:
        logger.error("Retrieval failed: %s", e)
        raise
