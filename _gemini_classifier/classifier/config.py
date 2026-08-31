from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
BIBLE_ROOT = PROJECT_ROOT.parent
BACKEND_DIR = BIBLE_ROOT / "backend"
CLASSIFICATION_DIR = BACKEND_DIR / "classification"

TAXONOMY_PATHS_FILE = BACKEND_DIR / "sermon_taxonomy_full_paths.txt"
TAXONOMY_DEFINITIONS_FILE = BACKEND_DIR / "sermon_taxonomy_definitions.md"

CORPUS_BY_LANG = {
    "en": BACKEND_DIR / "testimonies_en.jsonl",
    "zh": BACKEND_DIR / "testimonies_zh.jsonl",
}
LANG_ID_BY_LANG = {"en": 1, "zh": 2}

API_KEY_FILE = BIBLE_ROOT / "_rag" / "api_key.txt"

MODEL_CHAIN = [
    m.strip()
    for m in os.environ.get(
        "CLASSIFY_MODEL_CHAIN",
        "gemini-3.7-flash,gemini-3.5-flash",
    ).split(",")
    if m.strip()
]
MODEL = os.environ.get("CLASSIFY_MODEL", MODEL_CHAIN[0])
TAG = os.environ.get("CLASSIFY_TAG", "gemini37f")

LITE_MODEL = os.environ.get("CLASSIFY_LITE_MODEL", "gemini-3.5-flash-lite")
LITE_LANGS = {"zh"}
LITE_MAX_CHARS = int(os.environ.get("CLASSIFY_LITE_MAX_CHARS", "1000"))

CACHE_TTL_SECONDS = int(os.environ.get("CLASSIFY_CACHE_TTL", "1600"))
CACHE_REFRESH_MARGIN_SECONDS = 300

THINKING_LEVEL = os.environ.get("CLASSIFY_THINKING_LEVEL", "low")
# Thinking tokens are billed against max_output_tokens; the JSON verdict itself is
# ~20 tokens, so this ceiling exists purely to give thinking room to finish.
MAX_OUTPUT_TOKENS = int(os.environ.get("CLASSIFY_MAX_OUTPUT_TOKENS", "8192"))
# Kept at 16384 because several flash models cap output at 8192-65536; going higher
# risks a non-retryable 400 on the retry path that is supposed to rescue the doc.
MAX_OUTPUT_TOKENS_DEGRADED = int(os.environ.get("CLASSIFY_MAX_OUTPUT_TOKENS_DEGRADED", "16384"))
CONCURRENCY = int(os.environ.get("CLASSIFY_CONCURRENCY", "20"))
MAX_ATTEMPTS = int(os.environ.get("CLASSIFY_MAX_ATTEMPTS", "8"))
RATE_LIMIT_COOLDOWN_MIN_SECONDS = float(os.environ.get("CLASSIFY_RATE_LIMIT_COOLDOWN_MIN", "30"))
RATE_LIMIT_COOLDOWN_MAX_SECONDS = float(os.environ.get("CLASSIFY_RATE_LIMIT_COOLDOWN_MAX", "70"))
BACKOFF_BASE_SECONDS = float(os.environ.get("CLASSIFY_BACKOFF_BASE", "1.0"))
BACKOFF_CAP_SECONDS = float(os.environ.get("CLASSIFY_BACKOFF_CAP", "60"))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("CLASSIFY_REQUEST_TIMEOUT", "180"))

MODEL_INPUT_TOKEN_LIMIT = int(os.environ.get("CLASSIFY_INPUT_TOKEN_LIMIT", "1048576"))
DOC_TOKEN_BUDGET = int(os.environ.get("CLASSIFY_DOC_TOKEN_BUDGET", "850000"))

MAX_LABELS = 6
STATUS_FLUSH_EVERY = 25


def resolve_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    try:
        return API_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.error(f"No API key in GEMINI_API_KEY and cannot read {API_KEY_FILE}: {e}")
        raise


def labels_path(lang: str, tag: str = TAG) -> Path:
    return CLASSIFICATION_DIR / f"{lang}.{tag}.labels.jsonl"


def status_path(lang: str, tag: str = TAG) -> Path:
    return CLASSIFICATION_DIR / f"{lang}.{tag}.status.json"


def cache_state_path(tag: str = TAG, model: str = MODEL) -> Path:
    suffix = "" if model == MODEL else f".{model}"
    return CLASSIFICATION_DIR / f".{tag}{suffix}.cache.json"


def estimate_tokens(text: str) -> int:
    """Cheap local token estimate: CJK counts ~1 token/char, latin ~1/3.5."""
    cjk = 0
    other = 0
    for ch in text:
        if "\u3400" <= ch <= "\u9fff" or "\uf900" <= ch <= "\ufaff" or "\u3040" <= ch <= "\u30ff":
            cjk += 1
        else:
            other += 1
    return int(cjk + other / 3.5) + 1
