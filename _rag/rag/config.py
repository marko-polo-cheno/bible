"""Paths, model id, and chunk parameters (env-overridable)."""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent           # bible/_rag/
BIBLE_ROOT = PROJECT_ROOT.parent             # bible/

BACKEND_DIR = BIBLE_ROOT / "backend"
DEFAULT_EN_PATH = BACKEND_DIR / "testimonies_en.jsonl"
DEFAULT_ZH_PATH = BACKEND_DIR / "testimonies_zh.jsonl"

DEFAULT_INDEX_DIR = PROJECT_ROOT / "index"
DEFAULT_HF_HOME = PROJECT_ROOT / "hf_home"

MODEL_NAME = os.environ.get("RAG_MODEL", "BAAI/bge-m3")
EMBED_DIM = 1024

CHUNK_TOKENS = int(os.environ.get("RAG_CHUNK_TOKENS", "512"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "64"))

EN_CHUNK_WORDS = int(os.environ.get("RAG_EN_CHUNK_WORDS", "300"))
EN_CHUNK_WORD_OVERLAP = int(os.environ.get("RAG_EN_CHUNK_WORD_OVERLAP", "40"))
ZH_CHUNK_CHARS = int(os.environ.get("RAG_ZH_CHUNK_CHARS", "200"))
ZH_CHUNK_CHAR_OVERLAP = int(os.environ.get("RAG_ZH_CHUNK_CHAR_OVERLAP", "27"))
ZH_LANG_ID = 2


def ensure_hf_home() -> Path:
    """Point HF cache at the project-local dir unless the caller already set HF_HOME."""
    hf_home = Path(os.environ.get("HF_HOME", str(DEFAULT_HF_HOME)))
    hf_home.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(hf_home)
    return hf_home


def resolve_index_dir() -> Path:
    return Path(os.environ.get("RAG_INDEX_DIR", str(DEFAULT_INDEX_DIR)))
