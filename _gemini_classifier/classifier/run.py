from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, List, Optional, Set, Tuple

from loguru import logger
from tqdm import tqdm

from .config import (
    CONCURRENCY,
    CORPUS_BY_LANG,
    DOC_TOKEN_BUDGET,
    LITE_LANGS,
    LITE_MAX_CHARS,
    LITE_MODEL,
    MAX_LABELS,
    MODEL,
    STATUS_FLUSH_EVERY,
    TAG,
    estimate_tokens,
)
from .gemini import ClassifierClient
from .models import CorpusDoc, LabelFlag, LabelRecord
from .prompt import build_system_prompt, repair_label
from .store import LabelStore, count_corpus, iter_corpus, load_failure_lines

_stop = threading.Event()


def _install_signal_handlers() -> None:
    def handler(signum, _frame):
        if _stop.is_set():
            logger.warning("Second interrupt; exiting immediately")
            sys.exit(130)
        logger.warning(f"Signal {signum} received; finishing in-flight work then stopping")
        _stop.set()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def _configure_logging(verbose: bool) -> None:
    logger.remove()
    logger.add(
        lambda msg: tqdm.write(msg, end=""),
        level="DEBUG" if verbose else "INFO",
        colorize=True,
    )


def build_doc_text(doc: CorpusDoc) -> Tuple[str, List[LabelFlag]]:
    flags: List[LabelFlag] = []
    body = doc.content
    if doc.transcript_content:
        body = f"{body}\n\n[Transcript]\n{doc.transcript_content}" if body else doc.transcript_content

    header_lines = [f"Title: {doc.filename or '(untitled)'}"]
    header_lines.append(f"Language: {'Chinese' if doc.lang == 'zh' else 'English'}")
    legacy = [c for c in doc.category if c and c != "Unknown"]
    if legacy:
        header_lines.append(f"Existing publication-format categories: {', '.join(legacy)}")
    header = "\n".join(header_lines)

    if not body.strip():
        flags.append(LabelFlag(node="input", reason="empty_content"))

    budget = DOC_TOKEN_BUDGET
    if estimate_tokens(body) > budget:
        head_budget = int(budget * 0.7)
        tail_budget = budget - head_budget
        ratio = len(body) / max(estimate_tokens(body), 1)
        head_chars = int(head_budget * ratio)
        tail_chars = int(tail_budget * ratio)
        body = f"{body[:head_chars]}\n\n[... middle omitted ...]\n\n{body[-tail_chars:]}"
        flags.append(LabelFlag(node="input", reason="truncated"))

    return f"{header}\n\n---\n\n{body}", flags


def normalize_labels(
    primary: str, labels: List[str]
) -> Tuple[str, List[str], List[LabelFlag]]:
    flags: List[LabelFlag] = []
    resolved: List[str] = []

    for raw in [primary] + list(labels):
        if not raw:
            continue
        fixed = repair_label(raw)
        if fixed is None:
            flags.append(LabelFlag(node=raw[:120], reason="unknown_label"))
            continue
        if fixed != raw:
            flags.append(LabelFlag(node=fixed, reason="repaired_label"))
        if fixed not in resolved:
            resolved.append(fixed)

    if len(resolved) > MAX_LABELS:
        flags.append(LabelFlag(node="labels", reason=f"trimmed_to_{MAX_LABELS}"))
        resolved = resolved[:MAX_LABELS]

    if not resolved:
        flags.append(LabelFlag(node="labels", reason="no_valid_labels"))
        return "", [], flags

    return resolved[0], resolved, flags


def _pending_docs(
    lang: str,
    done: Set[int],
    only_lines: Optional[Set[int]],
    limit: Optional[int],
    offset: int,
) -> Iterator[CorpusDoc]:
    yielded = 0
    for doc in iter_corpus(lang):
        if doc.line_no < offset:
            continue
        if doc.line_no in done:
            continue
        if only_lines is not None and doc.line_no not in only_lines:
            continue
        yield doc
        yielded += 1
        if limit is not None and yielded >= limit:
            return


def classify_language(
    client: ClassifierClient,
    lang: str,
    limit: Optional[int] = None,
    offset: int = 0,
    concurrency: int = CONCURRENCY,
    retry_failures: bool = False,
    tag: str = TAG,
    max_requests: Optional[int] = None,
) -> bool:
    """Classify a language's corpus. Returns False when stopped early."""
    store = LabelStore(lang, tag=tag)
    done = store.load_done()

    only_lines: Optional[Set[int]] = None
    if retry_failures:
        failures = set(load_failure_lines(lang, tag)) - done
        if not failures:
            logger.info(f"[{lang}] no recorded failures to retry")
            return True
        only_lines = failures
        logger.info(f"[{lang}] retrying {len(failures)} previously failed item(s)")

    total = count_corpus(lang)
    store.open()
    store.write_status(total, cache_name=client.ensure_cache() or "")

    if limit is not None:
        target = limit
    elif only_lines is not None:
        target = len(only_lines)
    else:
        target = max(total - len(done) - offset, 0)

    logger.info(
        f"[{lang}] {total} item(s) in corpus, {len(done)} already labelled, "
        f"{target} to process with concurrency {concurrency}"
    )

    completed = 0
    requests_made = 0
    counter_lock = threading.Lock()
    inflight = threading.Semaphore(concurrency * 2)
    bar = tqdm(total=target, desc=f"{lang} classify", unit="doc", smoothing=0.05)

    def budget_available() -> bool:
        if max_requests is None:
            return True
        with counter_lock:
            if requests_made >= max_requests:
                return False
        return True

    def work(doc: CorpusDoc) -> None:
        nonlocal completed, requests_made
        try:
            if _stop.is_set():
                return
            with counter_lock:
                if max_requests is not None and requests_made >= max_requests:
                    return
                requests_made += 1
            text, flags = build_doc_text(doc)
            models = [LITE_MODEL] if lang in LITE_LANGS and len(text) < LITE_MAX_CHARS else None
            try:
                result, usage, used_model = client.classify(text, models=models)
            except Exception as e:
                logger.error(f"[{lang}] line {doc.line_no} failed permanently: {str(e)[:200]}")
                store.record_failure(doc, str(e)[:400])
                return

            primary, labels, label_flags = normalize_labels(result.primary_label, result.labels)
            record = LabelRecord(
                item_id=doc.item_id,
                lang_id=doc.lang_id,
                filename=doc.filename,
                link=doc.link,
                category=doc.category,
                labels=labels,
                primary_label=primary,
                form_type=result.form_type,
                flags=flags + label_flags,
                model=used_model,
                prompt_tokens=(usage.prompt_token_count or 0) if usage else 0,
                cached_tokens=(usage.cached_content_token_count or 0) if usage else 0,
                output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            )
            store.append(doc.line_no, record)
            completed += 1
            if completed % STATUS_FLUSH_EVERY == 0:
                store.write_status(total, cache_name=client.ensure_cache() or "")
        finally:
            bar.update(1)
            inflight.release()

    try:
        pending = _pending_docs(lang, done, only_lines, limit, offset)

        if concurrency > 1:
            # Prime the implicit prefix cache with one lone request; parallel cold
            # starts otherwise all miss it and pay full price for the taxonomy.
            first = next(pending, None)
            if first is not None:
                inflight.acquire()
                work(first)

        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix=f"cls-{lang}") as pool:
            for doc in pending:
                if _stop.is_set() or not budget_available():
                    break
                inflight.acquire()
                pool.submit(work, doc)
    finally:
        bar.close()
        store.write_status(total, cache_name=client.ensure_cache() or "")
        store.close()

    cached = store.cached_tokens
    prompt = store.prompt_tokens
    hit_rate = (cached / prompt * 100) if prompt else 0.0
    logger.info(
        f"[{lang}] wrote {store.written}/{total} record(s), {store.failed} failure(s); "
        f"tokens in={prompt} cached={cached} ({hit_rate:.0f}% cache hit) out={store.output_tokens}"
    )
    return not _stop.is_set()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify eLibrary content (EN + ZH) into the sermon taxonomy with Gemini."
    )
    parser.add_argument("--lang", choices=["en", "zh", "both"], default="both")
    parser.add_argument("--limit", type=int, default=None, help="max items per language")
    parser.add_argument("--offset", type=int, default=0, help="skip corpus lines below this")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--tag", default=TAG, help="artifact tag, e.g. gemini37f")
    parser.add_argument(
        "--max-requests",
        type=int,
        default=None,
        help="stop after this many API calls per language (fit a daily quota)",
    )
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--no-explicit-cache", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _configure_logging(args.verbose)
    _install_signal_handlers()

    langs = ["en", "zh"] if args.lang == "both" else [args.lang]
    for lang in langs:
        path = CORPUS_BY_LANG[lang]
        if not path.exists():
            logger.error(f"Corpus missing: {path}")
            sys.exit(1)

    prompt = build_system_prompt()
    logger.info(
        f"model={MODEL} tag={args.tag} system_prompt={len(prompt)} chars "
        f"(~{estimate_tokens(prompt)} tokens)"
    )

    client = ClassifierClient(use_cache=not args.no_explicit_cache)
    logger.info(
        f"model rotation on 429: {' -> '.join(client.models)}; "
        f"{'/'.join(sorted(LITE_LANGS))} docs under {LITE_MAX_CHARS} chars pinned to {LITE_MODEL}"
    )
    cache_name = client.ensure_cache()
    if cache_name:
        logger.info(f"[cache] explicit cache active: {cache_name}")
    else:
        logger.info(
            "[cache] using implicit prefix caching"
            + (f" — {client.cache_unavailable_reason}" if client.cache_unavailable_reason else "")
        )

    started = time.time()
    for lang in langs:
        ok = classify_language(
            client,
            lang,
            limit=args.limit,
            offset=args.offset,
            concurrency=args.concurrency,
            retry_failures=args.retry_failures,
            tag=args.tag,
            max_requests=args.max_requests,
        )
        if not ok:
            logger.warning(f"[{lang}] stopped before finishing; rerun the same command to resume")
            break

    logger.info(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
