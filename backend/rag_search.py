"""In-process semantic search over the prebuilt FAISS index.

Artifacts live on **disk**; weights live in **RAM only while people are using
the site**. The lifecycle is the whole point of this module:

* ``faiss.index`` / ``metadata.jsonl`` are fetched once into
  :data:`CACHE_INDEX_DIR` (or read from ``_rag/index``) and never re-downloaded.
  A ``rowmap.npz`` sidecar is built beside them the first time, so re-reading
  the 431 MB metadata file later costs a numpy load instead of a JSON parse.
* **Eager warm at boot**, so the first user after a deploy pays nothing.
* **Evict after a quiet period** (``RAG_IDLE_TTL``), so idle RAM drops back to
  the ~0.1 GB the keyword/filter paths need. Those paths never touch any of this.
* **Re-warm on the first sign of a user**, not on the semantic query itself.
  Opening the eLibrary page hits ``/elibrary/trees``; that marks activity and
  kicks the load off while the user is still picking filters and typing, so the
  semantic stage is usually resident by the time they reach it. A query that
  does arrive cold *waits* for the load (``RAG_WARM_TIMEOUT``) rather than
  silently degrading.

The index is built offline on a GPU (see ``_rag/README.md``); here we only
encode the single query vector (CPU is fine) and run FAISS search, optionally
restricted to a candidate subset of items via an ``IDSelector``.
"""
from __future__ import annotations

import ctypes
import gc
import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from elibrary import ItemKey, parse_item_key

BACKEND_DIR = Path(__file__).resolve().parent
MODEL_NAME = os.environ.get("RAG_MODEL", "BAAI/bge-m3")

FAISS_FILE = "faiss.index"
METADATA_FILE = "metadata.jsonl"
ROWMAP_FILE = "rowmap.npz"
BUNDLED_INDEX_DIR = BACKEND_DIR.parent / "_rag" / "index"
CACHE_INDEX_DIR = BACKEND_DIR / "rag_index"
_ARTIFACT_BASE = "https://github.com/marko-polo-cheno/bible/raw/main/_rag/index"
FAISS_URL = os.environ.get("RAG_FAISS_URL", f"{_ARTIFACT_BASE}/{FAISS_FILE}")
METADATA_URL = os.environ.get("RAG_METADATA_URL", f"{_ARTIFACT_BASE}/{METADATA_FILE}")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Load the whole stack at startup so a fresh deploy is already warm.
EAGER_WARM = os.environ.get("RAG_EAGER_WARM", "1") != "0"
# Drop it again after this many seconds with no user activity. 0 disables
# eviction (idle RAM stays at the full ~3.9 GB).
IDLE_TTL = _env_int("RAG_IDLE_TTL", 1800)
# How often the reaper checks.
IDLE_CHECK = _env_int("RAG_IDLE_CHECK", 60)
# How long a semantic query will block waiting for a cold load.
WARM_TIMEOUT = _env_int("RAG_WARM_TIMEOUT", 240)


class _Resident:
    """Everything that costs RAM. Swapped in/out as one immutable unit."""

    __slots__ = ("index", "rows_lang", "rows_item", "rows_off", "item_to_rows",
                 "lang_to_rows", "model", "meta_path", "loaded_at")


_lock = threading.Lock()
# Guards every transition below and wakes queries waiting on a cold load.
_cv = threading.Condition(_lock)
_resident: Optional[_Resident] = None
_loading = False
_error = ""
_artifacts_ready = False
_last_used = time.monotonic()
_loads = 0
_evictions = 0
_reaper_started = False


# --------------------------------------------------------------------------- #
# Status                                                                       #
# --------------------------------------------------------------------------- #
def status() -> Dict[str, object]:
    """``ready`` means *semantic search will answer* — not *it is in RAM now*."""
    return {
        "ready": is_ready(),
        "resident": _resident is not None,
        "loading": _loading,
        "error": _error,
        "idleSeconds": round(time.monotonic() - _last_used, 1),
        "idleTtl": IDLE_TTL,
        "loads": _loads,
        "evictions": _evictions,
    }


def is_ready() -> bool:
    """Servable: already resident, or artifacts are on disk and loadable."""
    return _resident is not None or (_artifacts_ready and not _error)


def is_resident() -> bool:
    return _resident is not None


# --------------------------------------------------------------------------- #
# Artifacts on disk                                                            #
# --------------------------------------------------------------------------- #
def _is_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as f:
            return "git-lfs.github.com" in f.readline()
    except (OSError, UnicodeDecodeError):
        return False


def _artifact_usable(path: Path, *, kind: str) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if kind == "faiss":
        if _is_lfs_pointer(path):
            return False
        with path.open("rb") as f:
            return f.read(4) == b"IxFI"
    if kind == "meta":
        try:
            with path.open("r", encoding="utf-8") as f:
                line = f.readline().strip()
            if not line or "git-lfs.github.com" in line:
                return False
            json.loads(line)
            return True
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False
    return False


def _resolve_index_dir() -> Path:
    explicit = os.environ.get("RAG_INDEX_DIR")
    if explicit:
        return Path(explicit)
    faiss_b = BUNDLED_INDEX_DIR / FAISS_FILE
    meta_b = BUNDLED_INDEX_DIR / METADATA_FILE
    if _artifact_usable(faiss_b, kind="faiss") and _artifact_usable(meta_b, kind="meta"):
        return BUNDLED_INDEX_DIR
    return CACHE_INDEX_DIR


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


def ensure_artifacts() -> Tuple[Path, Path]:
    """Get ``faiss.index`` + ``metadata.jsonl`` onto disk. Cheap in RAM.

    Called at startup so no user ever waits on a download, and again (as a
    no-op) at the head of every load.
    """
    global _artifacts_ready

    index_dir = _resolve_index_dir()
    faiss_path = index_dir / FAISS_FILE
    meta_path = index_dir / METADATA_FILE
    if not _artifact_usable(faiss_path, kind="faiss"):
        if faiss_path.exists():
            faiss_path.unlink()
        _download(FAISS_URL, faiss_path)
    if not _artifact_usable(meta_path, kind="meta"):
        if meta_path.exists():
            meta_path.unlink()
        _download(METADATA_URL, meta_path)
    if not _artifact_usable(faiss_path, kind="faiss") or not _artifact_usable(meta_path, kind="meta"):
        raise FileNotFoundError(f"Missing RAG artifacts in {index_dir}")
    _artifacts_ready = True
    return faiss_path, meta_path


# --------------------------------------------------------------------------- #
# Row map: row -> (lang, item) + byte offset into metadata.jsonl               #
# --------------------------------------------------------------------------- #
def _fingerprint(path: Path) -> str:
    st = path.stat()
    return f"{st.st_size}:{st.st_mtime_ns}"


def _rowmap_path(meta_path: Path) -> Path:
    """Beside the metadata when that directory is writable, else the cache dir."""
    if os.access(meta_path.parent, os.W_OK):
        return meta_path.parent / ROWMAP_FILE
    CACHE_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_INDEX_DIR / ROWMAP_FILE


def _scan_metadata(meta_path: Path):
    """One pass over metadata.jsonl recording keys and line offsets.

    Deliberately does *not* keep the chunk text: snippets are seeked out of the
    file for the handful of rows a query actually returns, which keeps ~0.5 GB
    of Python strings out of the resident set.
    """
    import numpy as np

    langs: List[int] = []
    items: List[int] = []
    offs: List[int] = []
    off = 0
    with meta_path.open("rb") as f:
        for raw in f:
            offs.append(off)
            off += len(raw)
            line = raw.strip()
            if not line:
                langs.append(-1)
                items.append(-1)
                continue
            rec = json.loads(line)
            lang_id = int(rec.get("lang_id", 1))
            item_id = rec.get("item_id")
            if item_id is None:
                key = parse_item_key(rec.get("link", "") or "")
                item_id = key[1] if key is not None else -1
            langs.append(lang_id)
            items.append(int(item_id))
    return (np.asarray(langs, dtype=np.int32),
            np.asarray(items, dtype=np.int64),
            np.asarray(offs, dtype=np.int64))


def _load_rowmap(meta_path: Path):
    """Cached row map, rebuilt only when metadata.jsonl changes."""
    import numpy as np

    cache = _rowmap_path(meta_path)
    fp = _fingerprint(meta_path)
    if cache.is_file():
        try:
            with np.load(cache) as z:
                if str(z["fp"][0]) == fp:
                    logger.info(f"[RAG] Row map from cache {cache.name}")
                    return z["lang"], z["item"], z["off"]
        except Exception as e:  # noqa: BLE001 - a bad cache is never fatal
            logger.warning(f"[RAG] Ignoring unreadable row map {cache}: {e}")

    logger.info(f"[RAG] Building row map from {meta_path}")
    langs, items, offs = _scan_metadata(meta_path)
    try:
        np.savez(cache, lang=langs, item=items, off=offs, fp=np.asarray([fp]))
        logger.info(f"[RAG] Row map cached to {cache}")
    except OSError as e:
        logger.warning(f"[RAG] Could not cache row map: {e}")
    return langs, items, offs


# --------------------------------------------------------------------------- #
# Load / evict                                                                 #
# --------------------------------------------------------------------------- #
def _load() -> _Resident:
    """Heavy load: FAISS index + row map + BGE-M3. Called off the main thread."""
    import faiss
    import numpy as np

    t0 = time.monotonic()
    faiss_path, meta_path = ensure_artifacts()

    logger.info(f"[RAG] Reading FAISS index {faiss_path}")
    index = faiss.read_index(str(faiss_path))

    rows_lang, rows_item, rows_off = _load_rowmap(meta_path)

    # tolist() once: per-element numpy indexing over 315k rows costs seconds.
    item_to_rows: Dict[ItemKey, List[int]] = {}
    lang_to_rows: Dict[int, object] = {}
    for row, (lang, item) in enumerate(zip(rows_lang.tolist(), rows_item.tolist())):
        if lang < 0 or item < 0:
            continue
        item_to_rows.setdefault((lang, item), []).append(row)
    for lang in np.unique(rows_lang):
        if int(lang) < 0:
            continue
        lang_to_rows[int(lang)] = np.flatnonzero(rows_lang == lang).astype(np.int64)

    if index.ntotal != len(rows_lang):
        logger.warning(
            f"[RAG] Index/metadata length mismatch: ntotal={index.ntotal} rows={len(rows_lang)}"
        )

    logger.info(
        "[RAG] chunks per lang_id: "
        + ", ".join(f"{lang}={len(rows)}" for lang, rows in sorted(lang_to_rows.items()))
    )

    logger.info(f"[RAG] Loading embedding model {MODEL_NAME} (CPU)")
    from FlagEmbedding import BGEM3FlagModel

    model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, devices=["cpu"])

    res = _Resident()
    res.index = index
    res.rows_lang = rows_lang
    res.rows_item = rows_item
    res.rows_off = rows_off
    res.item_to_rows = item_to_rows
    res.lang_to_rows = lang_to_rows
    res.model = model
    res.meta_path = meta_path
    res.loaded_at = time.monotonic()
    logger.info(f"[RAG] Loaded in {res.loaded_at - t0:.1f}s")
    return res


def _malloc_trim() -> None:
    """Hand freed arenas back to the OS so RSS actually drops (glibc/Linux)."""
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


def unload(reason: str = "idle") -> bool:
    """Drop the resident stack. Artifacts stay on disk; the next warm re-reads them."""
    global _resident, _evictions

    with _lock:
        if _resident is None or _loading:
            return False
        _resident = None
        _evictions += 1
    # Any search still running holds its own reference to the old _Resident and
    # finishes against it; this just stops new searches from pinning it.
    gc.collect()
    _malloc_trim()
    logger.info(f"[RAG] Evicted semantic index from RAM ({reason}); artifacts remain on disk")
    return True


def warm() -> None:
    """Kick off the heavy load once; safe to call from anywhere, repeatedly."""
    global _loading

    with _lock:
        if _loading or _resident is not None:
            return
        _loading = True

    def _runner() -> None:
        global _resident, _loading, _error, _loads
        res: Optional[_Resident] = None
        err = ""
        try:
            res = _load()
        except Exception as e:  # noqa: BLE001
            err = str(e)
            logger.error(f"[RAG] Failed to load semantic index: {e}")
        # One critical section, so a waiter never observes "not loading and not
        # resident" mid-handoff and unload() is never refused by a stale flag.
        with _cv:
            _loading = False
            _error = err
            if res is not None:
                _resident = res
                _loads += 1
            _cv.notify_all()
        if res is not None:
            logger.info("[RAG] Semantic search ready")

    threading.Thread(target=_runner, name="rag-warm", daemon=True).start()


def note_activity(warm_up: bool = True) -> None:
    """Mark that a real user is around.

    Called from the request middleware for user-facing endpoints (health checks
    excluded, or the reaper would never fire). This is what buys the "first user
    doesn't wait" property: the eLibrary page load starts the warm, so the load
    overlaps with the user picking filters and typing their query.
    """
    global _last_used

    _last_used = time.monotonic()
    if warm_up and _resident is None and not _loading:
        warm()


def ensure_resident(timeout: Optional[float] = None) -> Optional[_Resident]:
    """Return the resident stack, warming and waiting up to ``timeout`` seconds."""
    res = _resident
    if res is not None:
        return res
    warm()
    deadline = time.monotonic() + (WARM_TIMEOUT if timeout is None else timeout)
    with _cv:
        while _resident is None and _loading:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            _cv.wait(remaining)
        return _resident


def ensure_ready(timeout: Optional[float] = None) -> bool:
    return ensure_resident(timeout) is not None


def _reaper() -> None:
    while True:
        time.sleep(IDLE_CHECK)
        if _resident is None or _loading:
            continue
        idle = time.monotonic() - _last_used
        if idle >= IDLE_TTL:
            unload(f"idle {idle / 60:.0f}m")


def start(eager: Optional[bool] = None) -> None:
    """Startup hook: artifacts to disk, optional eager warm, idle reaper."""
    global _reaper_started

    eager = EAGER_WARM if eager is None else eager

    def _boot() -> None:
        global _error
        try:
            ensure_artifacts()
            logger.info("[RAG] Artifacts present on disk")
        except Exception as e:  # noqa: BLE001
            _error = str(e)
            logger.error(f"[RAG] Artifact fetch failed: {_error}")
            return
        if eager:
            warm()

    threading.Thread(target=_boot, name="rag-boot", daemon=True).start()

    with _lock:
        if IDLE_TTL > 0 and not _reaper_started:
            _reaper_started = True
            threading.Thread(target=_reaper, name="rag-reaper", daemon=True).start()
            logger.info(f"[RAG] Idle eviction on: unload after {IDLE_TTL}s quiet")


# --------------------------------------------------------------------------- #
# Query                                                                        #
# --------------------------------------------------------------------------- #
def _embed_query(res: _Resident, query: str):
    import numpy as np

    out = res.model.encode([query], return_dense=True, return_sparse=False,
                           return_colbert_vecs=False, max_length=512)
    vec = np.asarray(out["dense_vecs"], dtype=np.float32)
    norm = np.linalg.norm(vec, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    return vec / norm


def _snippet(text: str, n: int = 320) -> str:
    text = text.replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def _snippets_for(res: _Resident, rows: List[int], n: int = 320) -> Dict[int, str]:
    """Seek the chunk text for just the rows we are returning."""
    out: Dict[int, str] = {}
    try:
        with res.meta_path.open("rb") as f:
            for row in rows:
                f.seek(int(res.rows_off[row]))
                line = f.readline().strip()
                try:
                    out[row] = _snippet(json.loads(line).get("text", ""), n)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    out[row] = ""
    except OSError as e:
        logger.warning(f"[RAG] Could not read snippets: {e}")
    return out


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

    Warms the stack and waits if it was evicted; returns ``[]`` only if the load
    genuinely fails or exceeds ``RAG_WARM_TIMEOUT``.
    """
    res = ensure_resident()
    if res is None:
        return []
    note_activity(warm_up=False)

    import faiss
    import numpy as np

    qvec = _embed_query(res, query)

    lang_filter = set(lang_ids) if lang_ids else None

    chunk_rows = None
    if candidate_keys is not None:
        rows: List[int] = []
        for key in candidate_keys:
            if lang_filter and key[0] not in lang_filter:
                continue
            rows.extend(res.item_to_rows.get(key, []))
        chunk_rows = np.asarray(rows, dtype=np.int64)
    elif lang_filter:
        parts = [res.lang_to_rows[l] for l in lang_filter if l in res.lang_to_rows]
        chunk_rows = np.concatenate(parts) if parts else np.empty(0, dtype=np.int64)

    params = None
    if chunk_rows is not None:
        if chunk_rows.size == 0:
            return []
        sel = faiss.IDSelectorBatch(chunk_rows)
        params = faiss.SearchParameters()
        params.sel = sel
        search_k = min(int(chunk_rows.size), max(top_k * 4, top_k))
    else:
        search_k = min(res.index.ntotal, max(top_k * 6, top_k))

    if params is not None:
        scores, idxs = res.index.search(qvec, search_k, params=params)
    else:
        scores, idxs = res.index.search(qvec, search_k)

    best: Dict[ItemKey, Tuple[float, int]] = {}
    for score, row in zip(scores[0], idxs[0]):
        row = int(row)
        if row < 0:
            continue
        lang = int(res.rows_lang[row])
        item = int(res.rows_item[row])
        if lang < 0 or item < 0:
            continue
        key = (lang, item)
        if lang_filter and lang not in lang_filter:
            continue
        if candidate_keys is not None and key not in candidate_keys:
            continue
        cur = best.get(key)
        if cur is None or score > cur[0]:
            best[key] = (float(score), row)

    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:top_k]
    snippets = _snippets_for(res, [row for _, (_, row) in ranked])
    return [(key, sc, snippets.get(row, "")) for key, (sc, row) in ranked]
