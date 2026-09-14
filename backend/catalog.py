"""CMS catalog sidecar: grouped file type per item.

A third metadata axis alongside the two category trees — not topical, just
*what kind of thing this is*. Two levels: the medium (Audio / Video / Document /
Other) and, under it, the granular type the CMS already records — occasion for
media (Sermon, Lecture, Convocation, …), form for documents (Articles, Book
chapters, Lecture notes). Built offline by ``_catalog/build_catalog.py`` from
the CMS exports, so nothing here opens a 68 MB CSV or guesses an encoding at
request time.

Keyed by ``(lang_id, item_id)``, the same key the rest of the app joins on.
Rows are annotations only: a catalogued item the corpus does not have is
ignored, never created.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from loguru import logger

BACKEND_DIR = Path(__file__).resolve().parent
CATALOG_DIR = BACKEND_DIR / "catalog"

ItemKey = Tuple[int, int]

TOC_TYPE = "TableOfContents"
# Items the CMS has no row for land here, alongside catalogued items whose
# medium could not be named. Roughly half the ZH corpus has no catalog row, so
# "Other" is a real bucket users can select — never a silent drop.
UNKNOWN_TYPE = "Other"


class Catalog:
    """``(lang_id, item_id) -> file_type`` plus the raw sub/content types."""

    __slots__ = ("file_type", "file_path", "formats", "video_host",
                 "sub_type", "content_type", "toc_keys")

    def __init__(self) -> None:
        self.file_type: Dict[ItemKey, str] = {}
        self.file_path: Dict[ItemKey, str] = {}
        self.formats: Dict[ItemKey, List[str]] = {}
        self.video_host: Dict[ItemKey, str] = {}
        self.sub_type: Dict[ItemKey, str] = {}
        self.content_type: Dict[ItemKey, str] = {}
        self.toc_keys: set[ItemKey] = set()


def load_catalog() -> Catalog:
    cat = Catalog()
    for tag in ("en", "zh"):
        path = CATALOG_DIR / f"{tag}.catalog.jsonl"
        if not path.is_file():
            logger.warning(f"[CATALOG] Missing {path} — file-type filter will be empty")
            continue
        n = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = (int(rec["lang_id"]), int(rec["item_id"]))
                ftype = rec.get("file_type") or UNKNOWN_TYPE
                if ftype == TOC_TYPE:
                    cat.toc_keys.add(key)
                    continue
                cat.file_type[key] = ftype
                cat.file_path[key] = rec.get("file_path") or f"/{ftype}"
                cat.formats[key] = rec.get("formats") or []
                cat.video_host[key] = rec.get("video_host") or ""
                cat.sub_type[key] = rec.get("sub_type", "")
                cat.content_type[key] = rec.get("content_type", "")
                n += 1
        logger.info(f"[CATALOG] {path.name}: {n} items")
    logger.info(f"[CATALOG] {len(cat.toc_keys)} TableOfContents items flagged for exclusion")
    return cat


def load_formats() -> List[Dict[str, str]]:
    """Formats an item is available in, in display order.

    Orthogonal to the medium — a Document can be both PDF and web page, and an
    mp3 exists under two mediums — so this is its own scope rather than a branch
    of the file-type tree. Streaming *hosts* are not here: YouTube is not a
    format, and lives on the item as ``videoHost``.
    """
    path = CATALOG_DIR / "formats.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"[CATALOG] Could not read {path}: {e}")
        return []


def load_file_types() -> List[Dict[str, Any]]:
    """The facet *tree* for the UI, in display order, straight from the converter.

    Same ``{name, value, children}`` shape as the two category trees, so the UI
    renders it with the component it already has and the API matches it with the
    prefix logic it already has.
    """
    path = CATALOG_DIR / "file_types.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"[CATALOG] Could not read {path}: {e}")
        return [{"name": "Other", "value": f"/{UNKNOWN_TYPE}", "children": []}]
