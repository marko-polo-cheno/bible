# Testimonies RAG (EN + ZH)

Cross-lingual semantic retrieval over `bible/backend/testimonies_{en,zh}.jsonl`, using **BAAI/bge-m3** for a shared multilingual embedding space and FAISS for top-k search.

A Chinese query can surface relevant English testimonies and vice versa — both languages live in the same vector space.

## GPU vs CPU

| Phase | Hardware | When |
|-------|----------|------|
| **Index build** (`rag index`) | GPU (recommended) | One-time setup: chunk corpus + embed all chunks |
| **Query / hosting** (`rag retrieve`, app) | **CPU only** | Production; no GPU required after the index exists |

Use GPUs only while building embeddings. The running app loads the pre-built FAISS index and encodes each user query on CPU — fast enough at this corpus size (~130k vectors, sub-10ms FAISS search).

## Install

```bash
cd bible/_rag
poetry install
```

For index builds on NVIDIA GPUs, install a CUDA torch wheel in the Poetry env (not needed on CPU-only hosts):

```bash
poetry run pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu124
```

Model weights (~2.3 GB) are cached under `_rag/hf_home/` (gitignored). Set `HF_HOME` to override.

## Build the index (GPU)

Reads both JSONL corpora, chunks per language, embeds with BGE-M3, writes FAISS + metadata.

```bash
cd bible/_rag

# Full corpus (~25k docs → ~130k chunks). Uses both GPUs by default:
poetry run rag index --gpus 0,1 --batch-size 32

# Single GPU:
poetry run rag index --gpus 0 --batch-size 32
```

On a machine with two RTX 3090s, `--gpus 0,1` splits the embedding workload across both cards. Without CUDA, the same command falls back to CPU (much slower).

Custom corpora or output dir:

```bash
poetry run rag index \
  --corpus ../backend/testimonies_en.jsonl ../backend/testimonies_zh.jsonl \
  --index-dir ./index
```

### Chunk sizes (per language)

Chunking is language-aware so chunks stay within BGE-M3’s 512-token encode limit:

- **English:** word windows (default 300 words, 40-word overlap)
- **Chinese:** character windows (default 200 chars, 27-char overlap)

Override via env before `rag index`:

```bash
export RAG_EN_CHUNK_WORDS=300
export RAG_EN_CHUNK_WORD_OVERLAP=40
export RAG_ZH_CHUNK_CHARS=200
export RAG_ZH_CHUNK_CHAR_OVERLAP=27
```

Other env: `RAG_MODEL`, `RAG_INDEX_DIR`, `HF_HOME`.

### Artifacts

Written to `_rag/index/` (or `RAG_INDEX_DIR`):

- `faiss.index` — FAISS `IndexFlatIP`, 1024-dim, L2-normalized vectors (cosine via inner product)
- `metadata.jsonl` — row-aligned chunk records (`chunk_id`, `filename`, `link`, `category`, `lang_id`, `item_id`, `chunk_index`, `text`)

While `rag index` is running, partial state is kept as `embeddings.partial.f32` and `embed_checkpoint.json`. If the job stops, rerun the same command to resume; use `--fresh` to discard partial embeddings and start over.

Rebuild the index after changing chunk parameters or updating the corpus.

## Query / hosting (CPU)

Force CPU so a visible GPU is never used (recommended for production):

```bash
CUDA_VISIBLE_DEVICES="" poetry run rag retrieve "What does the Bible say about prayer?" --top-k 10

CUDA_VISIBLE_DEVICES="" poetry run rag retrieve "關於禱告與禁食聖經怎麼說？" --top-k 8
```

Optional filters:

```bash
# English only (lang_id 1) or Chinese only (lang_id 2)
CUDA_VISIBLE_DEVICES="" poetry run rag retrieve "prayer" --lang-id 1 --top-k 5

# Category prefix filter (comma-separated)
CUDA_VISIBLE_DEVICES="" poetry run rag retrieve "fasting" --category "Sermons"
```

FAISS search is CPU-only; only the query embedding step touches the model. With `CUDA_VISIBLE_DEVICES=""`, BGE-M3 runs on CPU for that single-vector encode.

## HTTP API (CPU, optional)

`scripts/serve_api.sh` is intended for CPU-only hosting (`CUDA_VISIBLE_DEVICES=""`). It is not yet wired to the `faiss.index` / `metadata.jsonl` artifacts from `rag index` — use `rag retrieve` above for production queries until the FastAPI layer is updated.

When available, the server will listen on `0.0.0.0:8801` (`HOST` / `PORT` overrides). Do not set `RAG_DEVICES` to CUDA in production.

## Notes

- **Retrieval-only (v1).** No generation step yet. Ranked chunks are returned; a separate LLM can consume them for grounded answers.
- The FAISS index is exact (`IndexFlatIP`). At ~130k vectors, queries are sub-10ms on CPU. If the corpus grows past ~1M vectors, consider HNSW or IVFPQ.
- **Two-phase ops:** run `rag index` on a GPU machine (e.g. dual 3090), copy `_rag/index/` + `hf_home/` if needed, serve queries on CPU-only app servers.
