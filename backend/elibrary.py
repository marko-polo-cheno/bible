"""Unified eLibrary item model: join map + dual category trees.

An *item* is the unit of search (one elibrary ContentDetail, keyed by
``(lang_id, item_id)`` parsed from its link). Each item carries metadata from
two taxonomies:

- **legacy tree** — the publication-format tree in ``categories.py`` (Media /
  Books / Magazines / ...), stored on each testimony's ``category`` field.
- **taxonomy tree** — the LLM-generated topical tree from
  ``classification/*.labels.jsonl`` (``/Bible and Truth/...``), multi-label.

The join map is metadata-only (no content), so it stays small enough to hold
in the slim API process. Content is streamed on demand by the keyword stage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from loguru import logger

from categories import get_category_tree  # legacy tree

BACKEND_DIR = Path(__file__).resolve().parent
CLASSIFICATION_DIR = BACKEND_DIR / "classification"
TAXONOMY_PATHS_FILE = BACKEND_DIR / "sermon_taxonomy_full_paths.txt"

# Which classification artifact (tag) to read labels from.
TAXONOMY_TAG = "gemma31b"

ItemKey = Tuple[int, int]  # (lang_id, item_id)


# --------------------------------------------------------------------------- #
# Taxonomy (new tree) parsing                                                  #
# --------------------------------------------------------------------------- #
def parse_taxonomy_tree(paths_file: Path = TAXONOMY_PATHS_FILE) -> List[Dict[str, Any]]:
    """Build a nested {name, value, children} tree from full-path lines.

    Each line is a leading-slash path like ``/Bible and Truth/Apologetics``.
    ``value`` is the full path (matching how labels are stored), so the same
    prefix-match logic used for the legacy tree applies unchanged.
    """
    roots: List[Dict[str, Any]] = []
    # full_path -> node, for O(1) parent lookup while building.
    by_path: Dict[str, Dict[str, Any]] = {}

    try:
        lines = paths_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        logger.warning(f"Taxonomy paths file not found: {paths_file}")
        return []

    for raw in lines:
        path = raw.strip()
        if not path:
            continue
        segments = [s for s in path.split("/") if s]
        # Build every ancestor so intermediate nodes exist even if a parent
        # path is not itself listed.
        cur_path = ""
        parent: Optional[Dict[str, Any]] = None
        for seg in segments:
            cur_path = f"{cur_path}/{seg}"
            node = by_path.get(cur_path)
            if node is None:
                node = {"name": seg, "value": cur_path, "children": []}
                by_path[cur_path] = node
                if parent is None:
                    roots.append(node)
                else:
                    parent["children"].append(node)
            parent = node

    return roots


def get_tree(tree: str, lang_id: int = 1) -> List[Dict[str, Any]]:
    """Return the requested tree. ``tree`` is 'legacy' or 'taxonomy'."""
    if tree == "taxonomy":
        return _TAXONOMY_TREE
    return get_category_tree(lang_id)


def matches_prefixes(values: List[str], prefixes: List[str]) -> bool:
    """Prefix match: keep if any value equals or is nested under any prefix."""
    if not prefixes:
        return True
    return any(
        v == p or v.startswith(p + "/")
        for v in values
        for p in prefixes
    )


# --------------------------------------------------------------------------- #
# Item join map                                                                #
# --------------------------------------------------------------------------- #
class Item:
    __slots__ = (
        "item_id",
        "lang_id",
        "title",
        "link",
        "legacy_categories",
        "taxonomy_labels",
        "form_type",
    )

    def __init__(self, item_id: int, lang_id: int, title: str, link: str):
        self.item_id = item_id
        self.lang_id = lang_id
        self.title = title
        self.link = link
        self.legacy_categories: List[str] = []
        self.taxonomy_labels: List[str] = []
        self.form_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "itemId": self.item_id,
            "langId": self.lang_id,
            "title": self.title,
            "link": self.link,
            "legacyCategories": self.legacy_categories,
            "taxonomyLabels": self.taxonomy_labels,
            "formType": self.form_type,
        }


def parse_item_key(link: str) -> Optional[ItemKey]:
    """Extract ``(lang_id, item_id)`` from an elibrary ContentDetail link."""
    try:
        q = parse_qs(urlparse(link).query)
        item_id = int(q["ItemID"][0])
        lang_id = int(q.get("LangID", ["1"])[0])
        return (lang_id, item_id)
    except (KeyError, ValueError, IndexError):
        return None


class JoinMap:
    """In-memory ``(lang_id, item_id) -> Item`` index across both trees."""

    def __init__(self) -> None:
        self.items: Dict[ItemKey, Item] = {}

    def values(self) -> List[Item]:
        return list(self.items.values())

    def get(self, key: ItemKey) -> Optional[Item]:
        return self.items.get(key)

    def candidate_keys(self, lang_ids: Optional[List[int]] = None) -> List[ItemKey]:
        if not lang_ids:
            return list(self.items.keys())
        wanted = set(lang_ids)
        return [k for k in self.items.keys() if k[0] in wanted]


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _load_legacy(jmap: JoinMap, path: Path, lang_id: int) -> int:
    if not path.exists():
        logger.warning(f"Testimonies file missing for join map: {path}")
        return 0
    count = 0
    for rec in _iter_jsonl(path):
        link = rec.get("link", "")
        key = parse_item_key(link)
        if key is None:
            continue
        item = jmap.items.get(key)
        if item is None:
            item = Item(item_id=key[1], lang_id=key[0], title=rec.get("filename", ""), link=link)
            jmap.items[key] = item
        cats = rec.get("category", [])
        if isinstance(cats, str):
            # Some rows store the list as a stringified literal.
            cats = _coerce_str_list(cats)
        item.legacy_categories = [c for c in cats if c and c != "Unknown"]
        count += 1
    return count


def _load_taxonomy(
    jmap: JoinMap,
    path: Path,
    lang_id: int,
    title_index: Dict[str, List[ItemKey]],
) -> int:
    """Attach taxonomy labels to items.

    The EN labels file carries ``item_id``/``link`` (join by key). The ZH labels
    file is leaner — only ``filename`` — so we fall back to a title match
    against the corpus.
    """
    if not path.exists():
        logger.warning(f"Classification labels missing: {path}")
        return 0
    count = 0
    unmatched = 0
    for rec in _iter_jsonl(path):
        labels = [l for l in (rec.get("labels", []) or []) if l]
        form_type = rec.get("form_type", "") or ""

        item_id = rec.get("item_id")
        if item_id is None and rec.get("link"):
            parsed = parse_item_key(rec["link"])
            if parsed is not None:
                item_id = parsed[1]

        targets: List[Item] = []
        if item_id is not None:
            item = jmap.items.get((lang_id, int(item_id)))
            if item is None:
                item = Item(item_id=int(item_id), lang_id=lang_id,
                            title=rec.get("filename", ""), link=rec.get("link", ""))
                jmap.items[(lang_id, int(item_id))] = item
            targets = [item]
        else:
            # Join by filename (ZH labels have no id/link).
            title = (rec.get("filename") or "").strip()
            for key in title_index.get(title, []):
                it = jmap.items.get(key)
                if it is not None:
                    targets.append(it)

        if not targets:
            unmatched += 1
            continue
        for it in targets:
            it.taxonomy_labels = labels
            it.form_type = form_type
            count += 1
    if unmatched:
        logger.info(f"[JOIN] {path.name}: {unmatched} label rows had no matching item")
    return count


def _coerce_str_list(value: str) -> List[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        try:
            import ast

            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except (ValueError, SyntaxError):
            pass
    return [value] if value else []


def build_join_map(
    en_path: Path,
    zh_path: Path,
) -> JoinMap:
    """Build the join map from testimonies (legacy) + classification (taxonomy)."""
    jmap = JoinMap()

    en = _load_legacy(jmap, en_path, lang_id=1)
    zh = _load_legacy(jmap, zh_path, lang_id=2)
    logger.info(f"[JOIN] Legacy loaded: en={en}, zh={zh}")

    # Title -> keys index for filename-based taxonomy joins (ZH labels).
    title_index: Dict[str, List[ItemKey]] = {}
    for key, item in jmap.items.items():
        title_index.setdefault(item.title.strip(), []).append(key)

    ten = _load_taxonomy(jmap, CLASSIFICATION_DIR / f"en.{TAXONOMY_TAG}.labels.jsonl",
                         lang_id=1, title_index=title_index)
    tzh = _load_taxonomy(jmap, CLASSIFICATION_DIR / f"zh.{TAXONOMY_TAG}.labels.jsonl",
                         lang_id=2, title_index=title_index)
    logger.info(f"[JOIN] Taxonomy labels attached: en={ten}, zh={tzh}")
    logger.info(f"[JOIN] Total items: {len(jmap.items)}")

    return jmap


# Parse the taxonomy tree once at import (static file).
_TAXONOMY_TREE: List[Dict[str, Any]] = parse_taxonomy_tree()
