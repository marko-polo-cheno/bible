#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export HF_HOME="${HF_HOME:-${PROJECT_DIR}/hf_home}"
export RAG_INDEX_DIR="${RAG_INDEX_DIR:-${PROJECT_DIR}/index}"
# Pin API to a single GPU; override RAG_DEVICES for multi-GPU serving.
export RAG_DEVICES="${RAG_DEVICES:-cuda:0}"
cd "${PROJECT_DIR}"
exec poetry run uvicorn rag.api:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8801}"
