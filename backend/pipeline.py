"""Staged search pipeline over eLibrary items.

A search is an ordered list of stages. Each stage receives the candidate pool
produced by the previous stage and narrows it further:

    filter (taxonomy) -> keyword ("healing") -> semantic ("lost my faith")

- ``filter``   keep items whose legacy/taxonomy paths match prefixes (no score)
- ``keyword``  keep items whose content contains terms; score = hit count
- ``semantic`` keep items whose chunks rank highest for the query; score = cosine

The first stage starts from the whole corpus (optionally narrowed by language).
Final ordering uses the most recent *scoring* stage. Each stage reports its
in/out counts so the UI can show the tiered funnel.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

from elibrary import Item, ItemKey, JoinMap, matches_prefixes, parse_item_key
from testimony_search import generate_derivatives, generate_kwic_preview

BACKEND_DIR = Path(__file__).resolve().parent
JSONL_BY_LANG = {
    1: BACKEND_DIR / "testimonies_en.jsonl",
    2: BACKEND_DIR / "testimonies_zh.jsonl",
}


class StageStat:
    def __init__(self, stage_type: str, label: str, in_count: int, out_count: int, scored: bool, available: bool = True):
        self.stage_type = stage_type
        self.label = label
        self.in_count = in_count
        self.out_count = out_count
        self.scored = scored
        self.available = available

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.stage_type,
            "label": self.label,
            "inCount": self.in_count,
            "outCount": self.out_count,
            "scored": self.scored,
            "available": self.available,
        }


class PipelineState:
    """Mutable candidate pool threaded through the stages."""

    def __init__(self, pool: Set[ItemKey]):
        self.pool: Set[ItemKey] = pool
        self.scores: Dict[ItemKey, float] = {}
        self.hit_counts: Dict[ItemKey, int] = {}
        self.snippets: Dict[ItemKey, List[Dict[str, Any]]] = {}
        self.order_kind: Optional[str] = None  # "keyword" | "semantic"


def _expand_terms(terms: List[str], include_derivatives: bool, lang_ids: List[int]) -> List[str]:
    seen: Set[str] = set()
    flat: List[str] = []
    only_zh = lang_ids == [2]
    for t in terms:
        t = t.strip()
        if not t:
            continue
        low = t.lower()
        if low not in seen:
            seen.add(low)
            flat.append(t)
        if include_derivatives and not only_zh:
            for d in generate_derivatives(t):
                if d.lower() not in seen:
                    seen.add(d.lower())
                    flat.append(d)
    return flat


def _langs_in_pool(pool: Set[ItemKey]) -> List[int]:
    return sorted({k[0] for k in pool})


# --------------------------------------------------------------------------- #
# Stage runners                                                                #
# --------------------------------------------------------------------------- #
def _run_filter(state: PipelineState, jmap: JoinMap, params: Dict[str, Any]) -> StageStat:
    tree = params.get("tree", "legacy")
    prefixes = [p for p in (params.get("prefixes") or []) if p]
    in_count = len(state.pool)
    if not prefixes:
        return StageStat("filter", "filter (none)", in_count, in_count, scored=False)

    kept: Set[ItemKey] = set()
    for key in state.pool:
        item = jmap.get(key)
        if item is None:
            continue
        values = item.taxonomy_labels if tree == "taxonomy" else item.legacy_categories
        if matches_prefixes(values, prefixes):
            kept.add(key)
    state.pool = kept
    label = f"filter · {tree} · {len(prefixes)} path(s)"
    return StageStat("filter", label, in_count, len(kept), scored=False)


def _run_keyword(state: PipelineState, jmap: JoinMap, params: Dict[str, Any]) -> StageStat:
    raw_terms = params.get("terms") or []
    include_derivatives = bool(params.get("includeDerivatives", False))
    in_count = len(state.pool)
    lang_ids = _langs_in_pool(state.pool) or [1, 2]
    terms = _expand_terms(raw_terms, include_derivatives, lang_ids)
    if not terms:
        return StageStat("keyword", "keyword (no terms)", in_count, in_count, scored=False)

    lowered = [t.lower() for t in terms]
    want_snippets = bool(params.get("snippets", True))

    # Restrict the scan to languages present in the pool.
    by_lang_pool: Dict[int, Set[int]] = {}
    for (lid, iid) in state.pool:
        by_lang_pool.setdefault(lid, set()).add(iid)

    kept: Set[ItemKey] = set()
    for lid, item_ids in by_lang_pool.items():
        path = JSONL_BY_LANG.get(lid)
        if not path or not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = parse_item_key(rec.get("link", ""))
                if key is None or key[1] not in item_ids or key[0] != lid:
                    continue
                full = rec.get("content", "")
                raw = full.lower()
                scan = (raw[:5000] + raw[-5000:]) if len(raw) > 10000 else raw
                hits = sum(scan.count(t) for t in lowered)
                if hits > 0:
                    kept.add(key)
                    state.hit_counts[key] = hits
                    state.scores[key] = float(hits)
                    if want_snippets:
                        state.snippets[key] = generate_kwic_preview(full, lowered)

    state.pool = kept
    state.order_kind = "keyword"
    label = f"keyword · {len(terms)} term(s)"
    return StageStat("keyword", label, in_count, len(kept), scored=True)


def _run_semantic(state: PipelineState, jmap: JoinMap, params: Dict[str, Any]) -> StageStat:
    query = (params.get("query") or "").strip()
    top_k = int(params.get("topK", 50))
    in_count = len(state.pool)
    if not query:
        return StageStat("semantic", "semantic (no query)", in_count, in_count, scored=False)

    import rag_search

    if not rag_search.is_ready():
        logger.warning("[PIPELINE] Semantic stage requested but RAG index not ready")
        return StageStat("semantic", "semantic (warming up)", in_count, in_count,
                         scored=False, available=False)

    lang_ids = _langs_in_pool(state.pool) or None
    hits = rag_search.semantic_search(
        query,
        candidate_keys=state.pool,
        lang_ids=lang_ids,
        top_k=top_k,
    )
    kept: Set[ItemKey] = set()
    for key, score, snippet in hits:
        if key not in state.pool:
            continue
        kept.add(key)
        state.scores[key] = float(score)
        state.snippets[key] = [{"text": snippet, "highlights": []}]
    state.pool = kept
    state.order_kind = "semantic"
    label = f"semantic · “{query[:40]}”"
    return StageStat("semantic", label, in_count, len(kept), scored=True)


_RUNNERS = {
    "filter": _run_filter,
    "keyword": _run_keyword,
    "semantic": _run_semantic,
}


def run_pipeline(
    jmap: JoinMap,
    stages: List[Dict[str, Any]],
    lang_ids: Optional[List[int]] = None,
    page: int = 0,
    size: int = 20,
) -> Dict[str, Any]:
    """Execute ``stages`` in order and return ranked, paginated results."""
    pool = set(jmap.candidate_keys(lang_ids))
    state = PipelineState(pool)
    stats: List[StageStat] = []

    for stage in stages:
        stype = stage.get("type")
        runner = _RUNNERS.get(stype)
        if runner is None:
            logger.warning(f"[PIPELINE] Unknown stage type: {stype}")
            continue
        stat = runner(state, jmap, stage)
        stats.append(stat)
        if not state.pool:
            break

    keys = list(state.pool)
    if state.order_kind in ("keyword", "semantic"):
        keys.sort(key=lambda k: state.scores.get(k, 0.0), reverse=True)
    else:
        keys.sort(key=lambda k: (jmap.get(k).title if jmap.get(k) else "").lower())

    total = len(keys)
    start = page * size
    page_keys = keys[start:start + size]

    results: List[Dict[str, Any]] = []
    for key in page_keys:
        item = jmap.get(key)
        if item is None:
            continue
        d = item.to_dict()
        d["score"] = state.scores.get(key)
        d["hitCount"] = state.hit_counts.get(key, 0)
        d["snippets"] = state.snippets.get(key, [])
        results.append(d)

    return {
        "stages": [s.to_dict() for s in stats],
        "total": total,
        "page": page,
        "size": size,
        "results": results,
    }
