# Gemini taxonomy classifier (EN + ZH)

Multi-label classification of every eLibrary item in
`backend/testimonies_{en,zh}.jsonl` into the 274-node sermon taxonomy, using
`gemini-3.7-flash` with a large cached system prompt.

Replaces the earlier local-vLLM `gemma31b` run, which covered 4,355 of 4,371 EN
items and only 7,817 of 20,506 ZH items, and whose ZH artifact carried no
`item_id` (forcing `elibrary.py` to join ZH labels by filename).

## What it produces

Artifacts land in `backend/classification/`, matching the shape `elibrary.py`
already reads (`labels`, `form_type`, `item_id`, `link`, `category`, `flags`):

- `{en,zh}.gemini37f.labels.jsonl` — one record per item, append-only
- `{en,zh}.gemini37f.status.json` — progress and token counters
- `{en,zh}.gemini37f.labels.failures.jsonl` — items that exhausted all retries

Each record adds `line_no` (the resume key), `primary_label`, and per-item token
counts. Unlike the ZH gemma artifact, **both** languages carry `item_id` and
`link`, so the join map can key ZH items properly instead of matching titles.

Completed run: **4,371 / 4,371 EN** and **20,506 / 20,506 ZH**, 0 outstanding
failures. 17 ZH records resolved to no valid taxonomy path and carry empty
`labels` with a `no_valid_labels` flag, so the join map attaches labels to
24,855 of 24,872 items.

To serve these labels, flip `TAXONOMY_TAG` in `backend/elibrary.py`:

```python
TAXONOMY_TAG = "gemini37f"
```

## The system prompt

`backend/sermon_taxonomy_definitions.md` gives every one of the 274 taxonomy
paths a definition with inclusion and exclusion cues. `classifier/prompt.py`
asserts on load that the definitions file and
`backend/sermon_taxonomy_full_paths.txt` describe exactly the same set of
paths — a typo in either file fails fast instead of silently degrading labels.

The assembled prompt is ~66 KB / **14,653 tokens** and covers the taxonomy plus
rules for form type, label count, specificity, narrative-vs-exposition,
doctrine-vs-practice, and TJC doctrinal framing. It is byte-identical on every
request, which is what makes caching work.

Model output is constrained to a Pydantic schema (`form_type`, `primary_label`,
`labels`). Returned paths are validated against the taxonomy and repaired when
they differ only in punctuation or case; anything unresolvable is dropped and
flagged rather than written.

## Caching

Two tiers, chosen automatically:

1. **Explicit cache** (`caches.create`, `ttl=3600s`, auto-refreshed 5 min before
   expiry, state persisted in `backend/classification/.gemini37f.cache.json`).
   This is the intended path and needs a **paid** API tier.
2. **Implicit prefix caching** — the fallback. The identical system-instruction
   prefix is sent inline and Gemini caches it automatically at the same 75%
   discount, with no TTL to manage.

On a free-tier key, explicit caching fails with
`TotalCachedContentStorageTokensPerModelFreeTier limit=0` and the client falls
back to implicit caching, logging the reason once. Measured implicit hit rate
once the prefix is warm: **12,057 of 14,653 prompt tokens (82%)**.

Because parallel cold starts all miss the implicit cache, each language
processes its first document alone to warm the prefix before the thread pool
starts.

## Resume and failure handling

- Writes are append-only, flushed per record and fsynced every 25 records.
- Resume reads `line_no` from the existing artifact; a truncated trailing record
  from a hard kill is detected and rewritten before appending.
- `SIGINT`/`SIGTERM` drain in-flight work and exit cleanly; a second signal
  exits immediately.
- Retries: **5 attempts**, exponential from **1s doubling to a 60s cap**, plus
  up to 25% jitter, on 408, 429, 500, 502, 503 and 504. When the API supplies
  its own `retryDelay` the longer of the two is used, still capped at 60s.
  `gemini-3.7-flash` returns 503 `UNAVAILABLE` fairly often, so this matters.
- An item that exhausts all 5 attempts is logged to
  `*.labels.failures.jsonl` and the run carries on. Sweep those up afterwards
  with `--retry-failures`.
- Documents over `CLASSIFY_DOC_TOKEN_BUDGET` (default 850k tokens) are cut to
  head 70% / tail 30% and flagged `truncated`. No document in the current corpus
  reaches this — the largest is ~893k chars (~250k tokens), so the run is
  effectively full-text.

## Rate limits observed on this key

| Limit reported by the API | Value |
|---|---|
| `GenerateRequestsPerDayPerProjectPerModel-FreeTier` (`gemini-3.7-flash`) | 20 |
| `TotalCachedContentStorageTokensPerModelFreeTier` | 0 (explicit caching unavailable) |

The 429 arrives with a misleadingly short `retryDelay` (27-33s), but the quota
does **not** refill on that timescale: after 20 successful calls the API kept
returning 429 instantly for the next 85 minutes. The cap is a genuine daily
ceiling of 20 requests for this model on this project.

The runner still treats 429 as retryable (5 attempts, 1s to 60s) rather than
aborting, so it degrades gracefully if the ceiling is ever raised. But at 20
calls/day a 24,877-document run is not reachable — it needs billing enabled on
the API project, which also switches explicit caching on.

Because a full pass takes hours, start it from your own terminal rather than a
tool-driven shell, which may kill the process group when the call returns:

```bash
cd _gemini_classifier
nohup poetry run python -m classifier.run --lang both --concurrency 20 > run.log 2>&1 &
tail -f run.log
```

## Usage

Run from this directory:

```bash
# Full run, both languages, resumable — 20 in flight
poetry run python -m classifier.run --lang both --concurrency 20

# Small slice under a throwaway tag
poetry run python -m classifier.run --lang en --limit 12 --tag smoke

# Cap the API calls for one session, then resume with the same command
poetry run python -m classifier.run --lang both --max-requests 500

# Re-attempt items that exhausted their 5 retries
poetry run python -m classifier.run --lang both --retry-failures
```

Progress is safe to interrupt at any point: rerun the same command and it picks
up from the last written record.

The API key is read from `GEMINI_API_KEY`, else `_rag/api_key.txt`.

Env overrides: `CLASSIFY_MODEL`, `CLASSIFY_TAG`, `CLASSIFY_CACHE_TTL`,
`CLASSIFY_CONCURRENCY`, `CLASSIFY_THINKING_LEVEL`, `CLASSIFY_MAX_ATTEMPTS`,
`CLASSIFY_DOC_TOKEN_BUDGET`.

## Corpus scale

| | Items | Chars | Avg | Max |
|---|---|---|---|---|
| EN | 4,371 | 93.1 M | 21.3 k | 893 k |
| ZH | 20,506 | 78.5 M | 3.8 k | 328 k |

Full-text classification is roughly 60-80 M input tokens before cache
discounts, plus ~14.6 k prompt tokens per request of which ~82% should be
cached once warm.
