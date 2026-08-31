from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

from loguru import logger

from .config import MAX_LABELS, TAXONOMY_DEFINITIONS_FILE, TAXONOMY_PATHS_FILE

_SEP = "::"

_INSTRUCTIONS = """\
You are the cataloguing librarian for the True Jesus Church (TJC) eLibrary. You
read one library item at a time — it may be a magazine article, a doctrinal
book chapter, a sermon or lecture transcript, a personal testimony, a religious
education lesson, a Q&A column, a news report, a poem, or a mixture — and you
assign it topical labels from a fixed taxonomy.

The item may be written in English, Traditional Chinese, or Simplified Chinese.
Read whichever language it is in, but ALWAYS return taxonomy paths in the exact
English form given in the taxonomy below. Never translate, paraphrase, reorder
or re-punctuate a path.

## What to produce

1. `form_type` — exactly one of:
   - `TESTIMONY` — the substance is a first-person (or reported first-person)
     account of what God did in someone's life: healing, baptism, receiving the
     Holy Spirit, protection, conversion, answered prayer. Choose this even if
     the account also exhorts the reader.
   - `SERMON` — the item is or transcribes spoken delivery to a congregation or
     class: a sermon, sermon notes, a lecture, a seminar or convocation message.
     Signals include spoken register, direct address ("brothers and sisters",
     "弟兄姊妹"), opening and closing prayer, hymn numbers, and transcription
     artefacts.
   - `PUBLICATION` — everything else: written articles, book chapters, study
     guides, textbooks and workbooks, Q&A columns, news and reports, poems,
     reference material. This is the default when the item reads as prose
     written to be read rather than heard.

2. `primary_label` — the single taxonomy path that best captures what the item
   is *about*. This must be a topical path, not a `/Publications/...` path,
   unless the item has no discernible topic at all (a pure table of contents,
   an index, a bare announcement).

3. `labels` — from 1 to {max_labels} paths, ordered from most to least central.
   - `primary_label` MUST be the first element of `labels`.
   - Add further topical paths only for themes that are genuinely substantial in
     the item — a theme discussed at length or driving a section, not a passing
     mention or a single quoted verse.
   - Add a `/Publications/...` path when the item's form or series is
     identifiable (e.g. a Manna article, a Q&A column, a Junior 1 textbook
     lesson, a news report, a poem). `/Publications/...` paths describe *form*
     and normally accompany a topical label rather than replacing it.
   - Most items warrant 2 to 4 labels. Use 1 when the item is short and narrow.
     Do not pad the list to reach a count.

## How to choose a path

- **Go as deep as the evidence supports.** If the item studies Elijah at
  Carmel, use the Elijah node, not the Prophets parent. If it surveys several
  prophets without focusing on one, use the parent instead.
- **Never invent a path.** Copy a path character-for-character from the taxonomy
  below, including capitalisation, commas, apostrophes and em dashes. If nothing
  fits well, choose the closest parent node rather than inventing a child.
- **Narrative versus exposition.** A first-person account of being healed is
  `/Testimonies/Healing and Health`; a study of why God heals is
  `/Bible and Truth/Biblical Topics/Miracles and Divine Healing`. The same rule
  separates every `/Testimonies/...` node from its doctrinal counterpart.
- **Doctrine versus practice.** Arguing that the seventh day is the Sabbath is
  `/Articles of Faith/Sabbath Day`; advising how to keep it at work or school is
  `/Bible and Truth/Biblical Topics/Sabbath Observance`.
- **Scripture exposition.** When the item walks through a biblical book or
  passage, include the matching `/Bible and Truth/Textual Studies — Books of the
  Bible/...` node alongside the topical theme it draws out.
- **Biblical figures.** When a person's life carries the item, use the
  `/Bible and Truth/Character Studies/...` node for that person.
- **TJC framing.** This is a True Jesus Church library. Baptism means baptism in
  natural living water, face downward, in the name of Jesus Christ; the Holy
  Spirit is evidenced by speaking in tongues; the Sabbath is Saturday; the
  sacraments are baptism, footwashing and Holy Communion. Read the items with
  these convictions assumed rather than treating them as contested.
- **Religious education.** Grade-level textbook and workbook lessons should
  carry both the grade-level `/Publications/Book/Religious Education/...` node
  and the biblical or moral topic the lesson teaches.
- **Truncated or thin items.** If the text is very short, is a fragment, or is
  mostly boilerplate, classify what is actually present and keep the label list
  short rather than guessing.

## Output

Return JSON only, matching the required schema. No commentary, no markdown, no
explanation of your reasoning.

## Taxonomy

Each entry below is a full path, followed by `::` and a definition that states
what belongs there and, where useful, what does not. Choose only from these
paths.
"""


def _parse_definitions(path: Path) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        logger.error(f"Cannot read taxonomy definitions {path}: {e}")
        raise

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _SEP not in line:
            logger.error(f"{path.name}:{lineno} missing '{_SEP}' separator: {line[:80]}")
            raise ValueError(f"Malformed definition line {lineno} in {path.name}")
        node, definition = line.split(_SEP, 1)
        entries.append((node.strip(), definition.strip()))
    return entries


def _load_paths(path: Path) -> List[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        logger.error(f"Cannot read taxonomy paths {path}: {e}")
        raise
    return [ln.strip() for ln in lines if ln.strip()]


@lru_cache(maxsize=1)
def load_taxonomy() -> Tuple[Tuple[str, ...], Dict[str, str]]:
    """Return (ordered paths, path -> definition), asserting the two files agree."""
    paths = _load_paths(TAXONOMY_PATHS_FILE)
    entries = _parse_definitions(TAXONOMY_DEFINITIONS_FILE)

    defined = {node for node, _ in entries}
    declared = set(paths)

    missing = [p for p in paths if p not in defined]
    extra = [n for n, _ in entries if n not in declared]
    if missing or extra:
        for p in missing[:20]:
            logger.error(f"Taxonomy path has no definition: {p}")
        for p in extra[:20]:
            logger.error(f"Definition has no matching taxonomy path: {p}")
        raise ValueError(
            f"Taxonomy mismatch: {len(missing)} undefined path(s), {len(extra)} orphan definition(s)"
        )

    dupes = [n for n in defined if sum(1 for x, _ in entries if x == n) > 1]
    if dupes:
        logger.error(f"Duplicate definitions for: {sorted(dupes)[:20]}")
        raise ValueError(f"{len(dupes)} duplicate definition(s) in taxonomy definitions")

    by_path = {node: definition for node, definition in entries}
    return tuple(paths), by_path


@lru_cache(maxsize=1)
def build_system_prompt() -> str:
    paths, by_path = load_taxonomy()
    body = "\n".join(f"{p} {_SEP} {by_path[p]}" for p in paths)
    header = _INSTRUCTIONS.format(max_labels=MAX_LABELS)
    return f"{header}\n{body}\n"


@lru_cache(maxsize=1)
def valid_paths() -> frozenset[str]:
    paths, _ = load_taxonomy()
    return frozenset(paths)


@lru_cache(maxsize=1)
def _normalized_index() -> Dict[str, str]:
    paths, _ = load_taxonomy()
    return {_normalize(p): p for p in paths}


def _normalize(path: str) -> str:
    out = path.strip().replace("\u2014", "-").replace("\u2013", "-")
    out = out.replace("\u2019", "'").replace("\u2018", "'")
    out = " ".join(out.split())
    return out.strip("/").lower()


def repair_label(label: str) -> str | None:
    """Map a model-returned label onto a real taxonomy path, or None if hopeless."""
    if not label:
        return None
    if label in valid_paths():
        return label
    candidate = _normalized_index().get(_normalize(label))
    if candidate is not None:
        return candidate
    if not label.startswith("/"):
        return _normalized_index().get(_normalize("/" + label))
    return None


def prompt_sha256() -> str:
    return hashlib.sha256(build_system_prompt().encode("utf-8")).hexdigest()
