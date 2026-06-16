"""In-process semantic search over the prebuilt FAISS index.

Runs inside the single API service. The 2.3 GB BGE-M3 model and the FAISS
index load **once**, in a background thread at startup, so keyword/filter
search is available immediately and the semantic stage turns on when ready.

The index is built offline on a GPU (see ``_rag/README.md``); here we only
encode the single query vector (CPU is fine) and run FAISS search, optionally
restricted to a candidate subset of items via an ``IDSelector``.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from elibrary import ItemKey, parse_item_key

BACKEND_DIR = Path(__file__).resolve().parent
MODEL_NAME = os.environ.get("RAG_MODEL", "BAAI/bge-m3")

# Where the prebuilt artifacts live. Defaults to the sibling _rag/index for
# local dev; set RAG_INDEX_DIR on the deployed service.
INDEX_DIR = Path(os.environ.get("RAG_INDEX_DIR", str(BACKEND_DIR.parent / "_rag" / "index")))
FAISS_FILE = "faiss.index"
METADATA_FILE = "metadata.jsonl"

# Optional download URLs for the artifacts (too large to ship in the image).
FAISS_URL = os.environ.get("RAG_FAISS_URL", "")
METADATA_URL = os.environ.get("RAG_METADATA_URL", "")

_lock = threading.Lock()
_state: Dict[str, object] = {}
_status = {"loading": False, "ready": False, "error": ""}


def status() -> Dict[str, object]:
    return dict(_status)


def is_ready() -> bool:
    return bool(_status["ready"])


def _download(url: str, path: Path) -> None:
    import requests

    logger.info(f"[RAG] Downloading {path.name} from {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=600, stream=True) as resp:
        resp.raise_for_status()
        with path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    logger.info(f"[RAG] Downloaded {path.name} ({path.stat().st_size} bytes)")


def _ensure_artifacts() -> Tuple[Path, Path]:
    faiss_path = INDEX_DIR / FAISS_FILE
    meta_path = INDEX_DIR / METADATA_FILE
    if not faiss_path.exists() and FAISS_URL:
        _download(FAISS_URL, faiss_path)
    if not meta_path.exists() and METADATA_URL:
        _download(METADATA_URL, meta_path)
    if not faiss_path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"Missing RAG artifacts in {INDEX_DIR} (set RAG_FAISS_URL / RAG_METADATA_URL to fetch)"
        )
    return faiss_path, meta_path


def _load() -> None:
    """Heavy load: FAISS index + row metadata + BGE-M3. Called off the main thread."""
    import faiss

    faiss_path, meta_path = _ensure_artifacts()

    logger.info(f"[RAG] Reading FAISS index {faiss_path}")
    index = faiss.read_index(str(faiss_path))

    rows_key: List[Optional[ItemKey]] = []
    rows_text: List[str] = []
    item_to_rows: Dict[ItemKey, List[int]] = {}

    logger.info(f"[RAG] Reading metadata {meta_path}")
    with meta_path.open("r", encoding="utf-8") as f:
        for row_idx, line in enumerate(f):
            line = line.strip()
            if not line:
                rows_key.append(None)
                rows_text.append("")
                continue
            rec = json.loads(line)
            lang_id = int(rec.get("lang_id", 1))
            item_id = rec.get("item_id")
            if item_id is None:
                key = parse_item_key(rec.get("link", ""))
            else:
                key = (lang_id, int(item_id))
            rows_key.append(key)
            rows_text.append(rec.get("text", ""))
            if key is not None:
                item_to_rows.setdefault(key, []).append(row_idx)

    if index.ntotal != len(rows_key):
        logger.warning(
            f"[RAG] Index/metadata length mismatch: ntotal={index.ntotal} rows={len(rows_key)}"
        )

    logger.info(f"[RAG] Loading embedding model {MODEL_NAME} (CPU)")
    from FlagEmbedding import BGEM3FlagModel

    model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, devices=["cpu"])

    _state.update(
        index=index,
        rows_key=rows_key,
        rows_text=rows_text,
        item_to_rows=item_to_rows,
        model=model,
    )


def load_in_background() -> None:
    """Kick off the heavy load once; safe to call multiple times."""
    with _lock:
        if _status["loading"] or _status["ready"]:
            return
        _status["loading"] = True

    def _runner() -> None:
        try:
            _load()
            _status["ready"] = True
            logger.info("[RAG] Semantic search ready")
        except Exception as e:  # noqa: BLE001
            _status["error"] = str(e)
            logger.error(f"[RAG] Failed to load semantic index: {e}")
        finally:
            _status["loading"] = False

    threading.Thread(target=_runner, daemon=True).start()


def _embed_query(query: str):
    import numpy as np

    model = _state["model"]
    out = model.encode([query], return_dense=True, return_sparse=False,
                        return_colbert_vecs=False, max_length=512)
    vec = np.asarray(out["dense_vecs"], dtype=np.float32)
    norm = np.linalg.norm(vec, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    return vec / norm


def _snippet(text: str, n: int = 320) -> str:
    text = text.replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def semantic_search(
    query: str,
    candidate_keys: Optional[Set[ItemKey]] = None,
    lang_ids: Optional[List[int]] = None,
    top_k: int = 50,
) -> List[Tuple[ItemKey, float, str]]:
    """Return ``(item_key, score, snippet)`` best-chunk-per-item, top_k.

    When ``candidate_keys`` is given, search is restricted to those items'
    chunks via a FAISS ``IDSelector`` — this is the pipeline subset search
    (e.g. RAG within the keyword-matched pool).
    """
    if not is_ready():
        return []

    import faiss
    import numpy as np

    index = _state["index"]
    rows_key: List[Optional[ItemKey]] = _state["rows_key"]  # type: ignore[assignment]
    rows_text: List[str] = _state["rows_text"]  # type: ignore[assignment]
    item_to_rows: Dict[ItemKey, List[int]] = _state["item_to_rows"]  # type: ignore[assignment]

    qvec = _embed_query(query)

    params = None
    if candidate_keys is not None:
        chunk_rows: List[int] = []
        for key in candidate_keys:
            chunk_rows.extend(item_to_rows.get(key, []))
        if not chunk_rows:
            return []
        sel = faiss.IDSelectorBatch(np.asarray(chunk_rows, dtype=np.int64))
        params = faiss.SearchParameters()
        params.sel = sel
        search_k = min(len(chunk_rows), max(top_k * 4, top_k))
    else:
        search_k = min(index.ntotal, max(top_k * 6, top_k))

    if params is not None:
        scores, idxs = index.search(qvec, search_k, params=params)
    else:
        scores, idxs = index.search(qvec, search_k)

    lang_filter = set(lang_ids) if lang_ids else None
    best: Dict[ItemKey, Tuple[float, int]] = {}
    for score, row in zip(scores[0], idxs[0]):
        if row < 0:
            continue
        key = rows_key[int(row)]
        if key is None:
            continue
        if lang_filter and key[0] not in lang_filter:
            continue
        if candidate_keys is not None and key not in candidate_keys:
            continue
        cur = best.get(key)
        if cur is None or score > cur[0]:
            best[key] = (float(score), int(row))

    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:top_k]
    return [(key, sc, _snippet(rows_text[row])) for key, (sc, row) in ranked]
