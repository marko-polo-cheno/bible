"""Byte-offset index over ``testimonies_{en,zh}.jsonl`` for targeted reads.

The keyword stage used to stream all 314 MB and ``json.loads`` every line —
~315k full parses — just to keep the handful of items still in the candidate
pool. Since each line is one item, the file position of each item's line is all
we need: given a pool, seek to those lines only.

Three things fall out of that:

* items filtered away earlier (category filter, language, and in particular
  **TableOfContents**) are never read or parsed at all;
* offsets are visited in ascending order, so the read stays sequential;
* the index is cached beside the corpus as ``.offsets.npz`` and rebuilt only
  when the file changes, so a restart costs a numpy load rather than a rescan.

The index itself is ~24k int64 pairs per language — a few MB, unrelated to the
RAG stack's memory lifecycle.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Tuple

from loguru import logger

from elibrary import parse_item_key

ItemKey = Tuple[int, int]

# path -> (fingerprint, {item_id: offset})
_CACHE: Dict[Path, Tuple[str, Dict[int, int]]] = {}


def _fingerprint(path: Path) -> str:
    st = path.stat()
    return f"{st.st_size}:{st.st_mtime_ns}"


def _scan(path: Path, lang_id: int):
    """One pass recording each item's line offset. Only the link is parsed."""
    import numpy as np

    ids: list[int] = []
    offs: list[int] = []
    off = 0
    with path.open("rb") as f:
        for raw in f:
            start = off
            off += len(raw)
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = parse_item_key(rec.get("link", "") or "")
            if key is None or key[0] != lang_id:
                continue
            ids.append(key[1])
            offs.append(start)
    return np.asarray(ids, dtype=np.int64), np.asarray(offs, dtype=np.int64)


def _load(path: Path, lang_id: int) -> Dict[int, int]:
    """``item_id -> byte offset``, from the sidecar when it is still valid."""
    import numpy as np

    fp = _fingerprint(path)
    cached = _CACHE.get(path)
    if cached is not None and cached[0] == fp:
        return cached[1]

    sidecar = path.with_suffix(path.suffix + ".offsets.npz")
    ids = offs = None
    if sidecar.is_file():
        try:
            with np.load(sidecar) as z:
                if str(z["fp"][0]) == fp:
                    ids, offs = z["ids"], z["offs"]
                    logger.info(f"[CORPUS] Offsets from cache {sidecar.name} ({len(ids)} items)")
        except Exception as e:  # noqa: BLE001 - a bad cache is never fatal
            logger.warning(f"[CORPUS] Ignoring unreadable {sidecar}: {e}")

    if ids is None:
        logger.info(f"[CORPUS] Building offset index for {path.name}")
        ids, offs = _scan(path, lang_id)
        try:
            np.savez(sidecar, ids=ids, offs=offs, fp=np.asarray([fp]))
            logger.info(f"[CORPUS] Cached {sidecar.name} ({len(ids)} items)")
        except OSError as e:
            logger.warning(f"[CORPUS] Could not cache offsets: {e}")

    index = dict(zip(ids.tolist(), offs.tolist()))
    _CACHE[path] = (fp, index)
    return index


def iter_records(path: Path, lang_id: int, item_ids: Iterable[int]) -> Iterator[Tuple[int, dict]]:
    """Yield ``(item_id, record)`` for ``item_ids``, reading only their lines.

    Offsets are sorted so the seeks walk the file forwards. Items with no line
    in this corpus file are simply absent from the output.
    """
    if not path.exists():
        logger.warning(f"[CORPUS] Missing corpus file {path}")
        return
    index = _load(path, lang_id)
    wanted = [(index[i], i) for i in item_ids if i in index]
    if not wanted:
        return
    wanted.sort()
    with path.open("rb") as f:
        for off, item_id in wanted:
            f.seek(off)
            line = f.readline().strip()
            if not line:
                continue
            try:
                yield item_id, json.loads(line)
            except json.JSONDecodeError:
                continue


def prewarm(paths: Dict[int, Path]) -> None:
    """Build/load every offset index up front so no search pays for the scan."""
    for lang_id, path in paths.items():
        if path.exists():
            try:
                _load(path, lang_id)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[CORPUS] Offset index failed for {path.name}: {e}")
