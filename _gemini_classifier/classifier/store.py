from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set
from urllib.parse import parse_qs, urlparse

import orjson
from loguru import logger

from .config import (
    CORPUS_BY_LANG,
    LANG_ID_BY_LANG,
    MODEL,
    STATUS_FLUSH_EVERY,
    TAG,
    labels_path,
    status_path,
)
from .models import CorpusDoc, LabelRecord, RunStatus


def _parse_link(link: str) -> tuple[Optional[int], Optional[int]]:
    try:
        q = parse_qs(urlparse(link).query)
        item_id = int(q["ItemID"][0]) if q.get("ItemID") else None
        lang_id = int(q["LangID"][0]) if q.get("LangID") else None
        return lang_id, item_id
    except (ValueError, IndexError, KeyError):
        return None, None


def iter_corpus(lang: str) -> Iterator[CorpusDoc]:
    path = CORPUS_BY_LANG[lang]
    default_lang_id = LANG_ID_BY_LANG[lang]
    try:
        with path.open("rb") as f:
            for line_no, raw in enumerate(f):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = orjson.loads(raw)
                except orjson.JSONDecodeError as e:
                    logger.error(f"{path.name}:{line_no} invalid JSON, skipping: {e}")
                    continue
                link = row.get("link") or ""
                link_lang, item_id = _parse_link(link)
                cats = row.get("category") or []
                if isinstance(cats, str):
                    cats = [cats]
                yield CorpusDoc(
                    lang=lang,
                    lang_id=link_lang or default_lang_id,
                    line_no=line_no,
                    item_id=item_id,
                    filename=row.get("filename") or "",
                    link=link,
                    category=[c for c in cats if c],
                    content=row.get("content") or "",
                    transcript_content=row.get("transcript_content") or "",
                )
    except OSError as e:
        logger.error(f"Cannot read corpus {path}: {e}")
        raise


def count_corpus(lang: str) -> int:
    path = CORPUS_BY_LANG[lang]
    try:
        with path.open("rb") as f:
            return sum(1 for line in f if line.strip())
    except OSError as e:
        logger.error(f"Cannot count corpus {path}: {e}")
        raise


class LabelStore:
    """Append-only, crash-resumable artifact writer for one language."""

    def __init__(self, lang: str, tag: str = TAG) -> None:
        self.lang = lang
        self.tag = tag
        self.labels_file = labels_path(lang, tag)
        self.status_file = status_path(lang, tag)
        self.failures_file = self.labels_file.with_suffix(".failures.jsonl")
        self.labels_file.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._handle = None
        self._since_sync = 0
        self.done_lines: Set[int] = set()
        self.written = 0
        self.failed = 0
        self.prompt_tokens = 0
        self.cached_tokens = 0
        self.output_tokens = 0

    def load_done(self) -> Set[int]:
        """Line numbers already classified, recovered from a previous run."""
        if not self.labels_file.exists():
            return set()
        done: Set[int] = set()
        salvageable = True
        try:
            with self.labels_file.open("rb") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        rec = orjson.loads(raw)
                    except orjson.JSONDecodeError:
                        logger.warning(
                            f"{self.labels_file.name}: trailing partial record ignored on resume"
                        )
                        salvageable = False
                        continue
                    line_no = rec.get("line_no")
                    if isinstance(line_no, int):
                        done.add(line_no)
        except OSError as e:
            logger.error(f"Cannot read existing artifact {self.labels_file}: {e}")
            raise
        if not salvageable:
            self._rewrite_clean()
        self.done_lines = done
        self.written = len(done)
        logger.info(f"[{self.lang}] resuming with {len(done)} record(s) already written")
        return done

    def _rewrite_clean(self) -> None:
        """Drop a truncated final line so appends stay valid JSONL."""
        tmp = self.labels_file.with_suffix(".jsonl.clean")
        try:
            with self.labels_file.open("rb") as src, tmp.open("wb") as dst:
                for raw in src:
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    try:
                        orjson.loads(stripped)
                    except orjson.JSONDecodeError:
                        continue
                    dst.write(stripped + b"\n")
            tmp.replace(self.labels_file)
            logger.info(f"[{self.lang}] rewrote {self.labels_file.name} without partial records")
        except OSError as e:
            logger.error(f"Failed to clean {self.labels_file}: {e}")
            raise

    def open(self) -> None:
        try:
            self._handle = self.labels_file.open("ab")
        except OSError as e:
            logger.error(f"Cannot open {self.labels_file} for append: {e}")
            raise

    def close(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.flush()
            os.fsync(self._handle.fileno())
            self._handle.close()
        except OSError as e:
            logger.error(f"Failed to close {self.labels_file}: {e}")
        finally:
            self._handle = None

    def append(self, line_no: int, record: LabelRecord) -> None:
        payload = record.model_dump()
        payload["line_no"] = line_no
        blob = orjson.dumps(payload) + b"\n"
        with self._lock:
            if self._handle is None:
                self.open()
            try:
                self._handle.write(blob)
                self._handle.flush()
                self._since_sync += 1
                if self._since_sync >= STATUS_FLUSH_EVERY:
                    os.fsync(self._handle.fileno())
                    self._since_sync = 0
            except OSError as e:
                logger.error(f"Failed to append record for line {line_no}: {e}")
                raise
            self.done_lines.add(line_no)
            self.written += 1
            self.prompt_tokens += record.prompt_tokens
            self.cached_tokens += record.cached_tokens
            self.output_tokens += record.output_tokens

    def record_failure(self, doc: CorpusDoc, reason: str) -> None:
        entry = {
            "line_no": doc.line_no,
            "item_id": doc.item_id,
            "filename": doc.filename,
            "link": doc.link,
            "reason": reason,
        }
        with self._lock:
            self.failed += 1
            try:
                with self.failures_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f.flush()
            except OSError as e:
                logger.error(f"Failed to write failure entry for line {doc.line_no}: {e}")

    def write_status(self, total: int, cache_name: str = "") -> None:
        status = RunStatus(
            lang=self.lang,
            tag=self.tag,
            model=MODEL,
            input_path=str(CORPUS_BY_LANG[self.lang]),
            artifact_path=str(self.labels_file),
            total=total,
            completed=self.written,
            pending=max(total - self.written, 0),
            failed=self.failed,
            prompt_tokens=self.prompt_tokens,
            cached_tokens=self.cached_tokens,
            output_tokens=self.output_tokens,
            cache_name=cache_name,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        tmp = self.status_file.with_suffix(".json.tmp")
        try:
            tmp.write_text(status.model_dump_json(indent=2), encoding="utf-8")
            tmp.replace(self.status_file)
        except OSError as e:
            logger.error(f"Failed to write status {self.status_file}: {e}")


def load_failure_lines(lang: str, tag: str = TAG) -> List[int]:
    path = labels_path(lang, tag).with_suffix(".failures.jsonl")
    if not path.exists():
        return []
    lines: List[int] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec.get("line_no"), int):
                    lines.append(rec["line_no"])
        return lines
    except OSError as e:
        logger.error(f"Cannot read failures file {path}: {e}")
        return []


def summarize_labels(lang: str, tag: str = TAG) -> Dict[str, int]:
    path = labels_path(lang, tag)
    counts: Dict[str, int] = {}
    if not path.exists():
        return counts
    try:
        with path.open("rb") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = orjson.loads(raw)
                except orjson.JSONDecodeError:
                    continue
                for label in rec.get("labels") or []:
                    counts[label] = counts.get(label, 0) + 1
    except OSError as e:
        logger.error(f"Cannot summarize {path}: {e}")
    return counts
