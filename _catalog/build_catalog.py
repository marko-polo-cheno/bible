#!/usr/bin/env python3
"""Offline: CMS catalog CSVs -> the tiny file-type sidecar the API serves.

The four exports (~68 MB, 36-42 columns, inconsistent encodings) carry exactly
four fields the search app cares about. This collapses them to
``backend/catalog/{en,zh}.catalog.jsonl`` (~1.5 MB total) keyed by
``(lang_id, item_id)`` — the same key ``elibrary.parse_item_key`` already uses —
so the API never opens a CSV and never sniffs an encoding at runtime.

    python _catalog/build_catalog.py [--csv-dir ~/Downloads/CSV]

Re-run whenever the CMS re-exports. Nothing else in the pipeline changes.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Tuple

csv.field_size_limit(10 ** 9)

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "backend" / "catalog"

# (filename, encoding, lang_id, bucket). The encodings really do differ per
# file — two are UTF-16, two are UTF-8-with-BOM.
SOURCES = [
    ("Publication-EN.csv", "utf-8-sig", 1, "publication"),
    ("Publication-ZH.csv", "utf-16",    2, "publication"),
    ("Media-EN.csv",       "utf-16",    1, "media"),
    ("Media-ZH.csv",       "utf-8-sig", 2, "media"),
]

# The top level is the *medium* — one bucket per kind of thing, so every audio
# container is one Audio and every text format is one Document. Under it sits
# the granular type the CMS already records, so "Audio, but only sermons" or
# "Documents, but not lecture notes" are expressible. Emitted as a nested tree
# to file_types.json and served verbatim to the UI, never restated elsewhere.
OTHER = "Other"
MEDIA_ORDER = ["Audio", "Video", "Document", OTHER]
MEDIUM_LABELS = {"Audio": "Audio", "Video": "Video", "Document": "Document", OTHER: "Other"}

# Which column supplies the child level, per medium. Documents split by form
# (ItemSubType); audio and video split by occasion (ContentType), which is the
# same vocabulary for both.
CHILD_COLUMN = {"Document": "ItemSubType", "Audio": "ContentType", "Video": "ContentType"}

# Nicer names for the handful of child values that read badly raw.
CHILD_LABELS = {
    "Article": "Articles",
    "Chapter": "Book chapters",
    "LectureNote": "Lecture notes",
}

# ItemSubType -> medium. "Media" is genuinely ambiguous in the export and falls
# through to the file extension. TableOfContents is carried so the API can drop
# those items; it is never offered as a filter.
TOC = "TableOfContents"
SUBTYPE_TO_TYPE: Dict[str, Optional[str]] = {
    "Article": "Document",
    "Chapter": "Document",
    "LectureNote": "Document",
    "Audio": "Audio",
    "Video": "Video",
    "AudioVideo": "Video",   # an audio file that also has a video edition
    "Media": None,           # resolve by extension
    TOC: TOC,
}

# Containers collapse into their medium: mp3/m4a/wav/... are all one "Audio".
EXT_TO_TYPE = {
    "mp3": "Audio", "m4a": "Audio", "wav": "Audio", "wma": "Audio",
    "aac": "Audio", "ogg": "Audio", "flac": "Audio", "aiff": "Audio",
    "mp4": "Video", "wmv": "Video", "mov": "Video", "avi": "Video",
    "mkv": "Video", "webm": "Video", "mpg": "Video", "m4v": "Video",
    "htm": "Document", "html": "Document", "pdf": "Document", "txt": "Document",
    "doc": "Document", "docx": "Document", "rtf": "Document", "epub": "Document",
}
_EXT_RE = re.compile(r"\.([A-Za-z0-9]{2,4})(?:\?|$)")

# How you can actually consume an item. Orthogonal to the medium, and worth its
# own axis because it cuts across one: an /Audio item and an /Audio-plus-video
# item both ship an mp3, while a stream-only /Video item ships none.
FORMATS = [
    {"value": "pdf",   "label": "PDF"},
    {"value": "html",  "label": "Web page"},
    {"value": "mp3",   "label": "MP3 audio"},
    {"value": "video", "label": "Video file"},
]
# The CMS writes the literal string "NULL" for an absent URL, so emptiness is
# not the test — this is exactly what made PDF look universal at first glance.
_NULLISH = {"", "null", "n/a", "-", "none"}
_HTML_RE = re.compile(r"\.html?($|\?|\s)", re.I)
_AUDIO_EXT = {"mp3", "m4a", "wav", "wma", "aac", "ogg", "flac", "aiff"}
_VIDEO_EXT = {"mp4", "mov", "wmv", "avi", "mkv", "webm", "mpg", "m4v"}
# VideoSiteName is free text and carries junk in the malformed rows, so match
# known hosts rather than trusting whatever string is there.
_HOSTS = {"youtube": "youtube", "you tube": "youtube", "vimeo": "vimeo"}


def _real(row: Dict[str, str], *cols: str) -> bool:
    return any((row.get(c) or "").strip().lower() not in _NULLISH for c in cols)


def _formats(row: Dict[str, str]) -> list:
    out = []
    if _real(row, "PdfURL", "CompletePdfURL"):
        out.append("pdf")
    src = " ".join((row.get(c) or "") for c in ("URL", "PhysicalFilePath", "CompleteURL"))
    if _HTML_RE.search(src):
        out.append("html")

    # The item's own media file: mp3 and friends collapse to one "mp3".
    for col in ("PhysicalFilePath", "CompleteFilePath", "URL", "CompleteURL"):
        m = _EXT_RE.search((row.get(col) or "").strip())
        if not m:
            continue
        ext = m.group(1).lower()
        if ext in _AUDIO_EXT:
            out.append("mp3")
        elif ext in _VIDEO_EXT:
            out.append("video")
        break

    return list(dict.fromkeys(out))


def _video_host(row: Dict[str, str]) -> str:
    """Where a stream lives, when it is streamed at all.

    Deliberately *not* a format: YouTube is a host, and an item can be streamed
    from it while shipping no downloadable file of any kind. Kept per item so
    the UI can link or badge the stream; it is not a filter facet.
    """
    if not _real(row, "VideoID"):
        return ""
    host = (row.get("VideoSiteName") or "").strip().lower()
    return next((v for k, v in _HOSTS.items() if k in host), "other")


def _ext_type(row: Dict[str, str]) -> Optional[str]:
    """Medium from the item's own file.

    Never reads PdfURL/ImageURL: every publication row carries both, so they say
    nothing about what the item *is* — PdfURL is an alternate rendition of the
    same article and ImageURL is a thumbnail.
    """
    for col in ("PhysicalFilePath", "CompleteFilePath", "URL", "CompleteURL"):
        m = _EXT_RE.search((row.get(col) or "").strip())
        if m:
            hit = EXT_TO_TYPE.get(m.group(1).lower())
            if hit:
                return hit
    return None


def _resolve(row: Dict[str, str]) -> Optional[str]:
    """Medium for this row, or None if the row is unusable.

    Media-EN.csv contains rows whose unescaped commas shift every column (a file
    path lands in ItemSubType). Requiring a known ItemSubType rejects those
    rather than guessing an ItemID that may itself be shifted.

    Falls back to "Other" rather than dropping a catalogued item whose medium we
    cannot name — the item is real and must stay findable.
    """
    sub = (row.get("ItemSubType") or "").strip()
    if sub not in SUBTYPE_TO_TYPE:
        return None
    mapped = SUBTYPE_TO_TYPE[sub]
    if mapped is not None:
        return mapped
    return _ext_type(row) or OTHER


def _child(file_type: str, row: Dict[str, str]) -> str:
    """Granular type under the medium, or "" when the medium has no split."""
    col = CHILD_COLUMN.get(file_type)
    if not col:
        return ""
    # "/" is the path separator, so it can never appear inside a segment.
    return (row.get(col) or "").strip().replace("/", "-")


def _path(file_type: str, row: Dict[str, str]) -> str:
    if file_type == TOC:
        return f"/{TOC}"
    child = _child(file_type, row)
    return f"/{file_type}/{child}" if child else f"/{file_type}"


def _build_tree(rows) -> list:
    """Nested {name, value, children} from the paths actually present.

    Built from the data rather than hardcoded, so a new ContentType shows up on
    its own and a vocabulary that disappears stops being offered.
    """
    counts: Counter = Counter()
    for r in rows:
        counts[r["file_path"]] += 1

    tree = []
    for medium in MEDIA_ORDER:
        root = f"/{medium}"
        children = sorted(
            ((p, n) for p, n in counts.items() if p.startswith(root + "/")),
            key=lambda kv: -kv[1],
        )
        total = counts.get(root, 0) + sum(n for _, n in children)
        # /Other is always offered: it is filled by corpus items that have no
        # catalog row at all, so it never has rows here to count. The API prunes
        # any root that turns out to be empty against the real corpus.
        if not total and medium != OTHER:
            continue
        tree.append({
            "name": MEDIUM_LABELS.get(medium, medium),
            "value": root,
            "children": [
                {"name": CHILD_LABELS.get(p.rsplit("/", 1)[1], p.rsplit("/", 1)[1]),
                 "value": p, "children": []}
                for p, _ in children
            ],
        })
    return tree


def build(csv_dir: Path) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_lang: Dict[int, Dict[int, dict]] = {1: {}, 2: {}}
    stats: Counter = Counter()

    for name, enc, lang_id, bucket in SOURCES:
        path = csv_dir / name
        if not path.is_file():
            print(f"  ! missing {path}", file=sys.stderr)
            stats["missing_files"] += 1
            continue
        rows = kept = 0
        with path.open(encoding=enc, newline="", errors="replace") as f:
            for row in csv.DictReader(f):
                rows += 1
                try:
                    item_id = int((row.get("ItemID") or "").strip())
                except ValueError:
                    stats["bad_item_id"] += 1
                    continue
                file_type = _resolve(row)
                if file_type is None:
                    stats["unresolved_subtype"] += 1
                    continue
                if item_id in by_lang[lang_id]:
                    stats["duplicate_item_id"] += 1
                    continue
                by_lang[lang_id][item_id] = {
                    "item_id": item_id,
                    "lang_id": lang_id,
                    "file_type": file_type,          # medium, for the badge
                    "file_path": _path(file_type, row),  # medium[/granular type]
                    "formats": _formats(row),
                    "video_host": _video_host(row),
                    "sub_type": (row.get("ItemSubType") or "").strip(),
                    "content_type": (row.get("ContentType") or "").strip(),
                    "bucket": bucket,
                }
                kept += 1
        print(f"  {name:20s} {rows:6d} rows -> {kept:6d} kept")

    total = 0
    for lang_id, tag in ((1, "en"), (2, "zh")):
        out = OUT_DIR / f"{tag}.catalog.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for item_id in sorted(by_lang[lang_id]):
                f.write(json.dumps(by_lang[lang_id][item_id], ensure_ascii=False) + "\n")
        n = len(by_lang[lang_id])
        total += n
        print(f"  wrote {out.relative_to(REPO)}  {n:6d} rows  {out.stat().st_size/1e6:.2f} MB")

    all_rows = [r for d in by_lang.values() for r in d.values()
                if r["file_type"] != TOC]
    tree = _build_tree(all_rows)
    all_rows = [r for d in by_lang.values() for r in d.values() if r["file_type"] != TOC]
    seen = {f for r in all_rows for f in r["formats"]}
    fmt_out = OUT_DIR / "formats.json"
    fmt_out.write_text(json.dumps([f for f in FORMATS if f["value"] in seen],
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fc = Counter(f for r in all_rows for f in r["formats"])
    print(f"  wrote {fmt_out.relative_to(REPO)}  {dict(fc)}")

    types_out = OUT_DIR / "file_types.json"
    types_out.write_text(json.dumps(tree, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    leaves = sum(len(n["children"]) for n in tree)
    print(f"  wrote {types_out.relative_to(REPO)}  ({len(tree)} media, {leaves} granular types)")
    for n in tree:
        kids = ", ".join(c["name"] for c in n["children"]) or "-"
        print(f"     {n['value']:12s} {kids}")

    toc = sum(1 for d in by_lang.values() for r in d.values() if r["file_type"] == TOC)
    print(f"\n  {total} catalogued items, {toc} TableOfContents (excluded by the API)")
    if stats:
        print(f"  skipped: {dict(stats)}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv-dir", default=os.environ.get("CATALOG_CSV_DIR", "~/Downloads/CSV"),
                    help="directory holding the four CMS exports")
    args = ap.parse_args()
    csv_dir = Path(args.csv_dir).expanduser()
    print(f"Reading CMS exports from {csv_dir}")
    build(csv_dir)


if __name__ == "__main__":
    main()
