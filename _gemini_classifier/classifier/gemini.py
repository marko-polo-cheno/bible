from __future__ import annotations

import json
import random
import re
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

from google import genai
from google.genai import types
from loguru import logger

from .config import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_CAP_SECONDS,
    CACHE_REFRESH_MARGIN_SECONDS,
    CACHE_TTL_SECONDS,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    MAX_OUTPUT_TOKENS_DEGRADED,
    MODEL,
    MODEL_CHAIN,
    RATE_LIMIT_COOLDOWN_MAX_SECONDS,
    RATE_LIMIT_COOLDOWN_MIN_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    THINKING_LEVEL,
    cache_state_path,
    resolve_api_key,
)
from .models import CacheState, DocClassification
from .prompt import build_system_prompt, prompt_sha256

_RETRY_STATUS = (408, 429, 500, 502, 503, 504)
_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s")
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


def _safety_settings() -> Optional[list]:
    """Never let a safety filter silently empty a response on doctrinal text."""
    try:
        return [
            types.SafetySetting(category=c, threshold=types.HarmBlockThreshold.BLOCK_NONE)
            for c in (
                types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            )
        ]
    except (AttributeError, TypeError, ValueError) as e:
        logger.error(f"Cannot build safety settings ({type(e).__name__}: {e}); using API defaults")
        return None


_SAFETY_SETTINGS = _safety_settings()


class ClassifierClient:
    """Gemini wrapper: explicit cache when the key allows it, implicit otherwise."""

    def __init__(self, model: str = MODEL, use_cache: bool = True) -> None:
        self.models = [model] + [m for m in MODEL_CHAIN if m != model]
        self.model = self.models[0]
        self.system_prompt = build_system_prompt()
        self.prompt_sha = prompt_sha256()
        self._client = genai.Client(api_key=resolve_api_key())
        self._cache_lock = threading.Lock()
        self._caches: Dict[str, CacheState] = {}
        self._model_lock = threading.Lock()
        self._cooldown_until: Dict[str, float] = {}
        self.explicit_cache_enabled = use_cache
        self.cache_unavailable_reason = ""

    # ------------------------------------------------------------- model pick
    def _pick_model(self, candidates: Optional[Sequence[str]] = None) -> str:
        """First model off cooldown; if all are limited, wait for the soonest."""
        models: List[str] = list(candidates) if candidates else self.models
        while True:
            now = time.time()
            with self._model_lock:
                for m in models:
                    if self._cooldown_until.get(m, 0.0) <= now:
                        return m
                soonest = min(models, key=lambda m: self._cooldown_until.get(m, 0.0))
                wait = self._cooldown_until[soonest] - now
            if wait <= 0:
                return soonest
            logger.warning(
                f"[model] all {len(models)} candidate model(s) rate-limited; "
                f"waiting {wait:.1f}s for {soonest}"
            )
            time.sleep(wait)

    def _mark_rate_limited(self, model: str, candidates: Sequence[str]) -> None:
        """Park a 429'd model for a random 30-70s so peers can absorb the load."""
        delay = random.uniform(RATE_LIMIT_COOLDOWN_MIN_SECONDS, RATE_LIMIT_COOLDOWN_MAX_SECONDS)
        until = time.time() + delay
        with self._model_lock:
            if until <= self._cooldown_until.get(model, 0.0):
                return
            self._cooldown_until[model] = until
            now = time.time()
            available = [m for m in candidates if self._cooldown_until.get(m, 0.0) <= now]
        logger.warning(
            f"[model] {model} rate-limited; cooling down {delay:.0f}s; "
            f"{'rotating to ' + available[0] if available else 'no alternate available'}"
        )

    # ------------------------------------------------------------------ cache
    def _load_cache_state(self, model: str) -> Optional[CacheState]:
        path = cache_state_path(model=model)
        if not path.exists():
            return None
        try:
            state = CacheState.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.error(f"Ignoring unreadable cache state {path}: {e}")
            return None
        if state.model != model or state.prompt_sha256 != self.prompt_sha:
            logger.info("Cached prompt no longer matches model/prompt; will recreate")
            return None
        if state.expires_at - time.time() < CACHE_REFRESH_MARGIN_SECONDS:
            return None
        try:
            self._client.caches.get(name=state.name)
        except Exception as e:
            logger.info(f"Cache {state.name} no longer retrievable ({type(e).__name__}); recreating")
            return None
        return state

    def _save_cache_state(self, state: CacheState) -> None:
        path = cache_state_path(model=state.model)
        try:
            path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to persist cache state {path}: {e}")

    def _create_cache(self, model: str) -> Optional[CacheState]:
        try:
            cache = self._client.caches.create(
                model=model,
                config=types.CreateCachedContentConfig(
                    system_instruction=self.system_prompt,
                    ttl=f"{CACHE_TTL_SECONDS}s",
                    display_name=f"tjc-taxonomy-{model}-{self.prompt_sha[:12]}",
                ),
            )
        except Exception as e:
            msg = str(e)
            if "CachedContentStorageTokens" in msg or "limit=0" in msg:
                self.explicit_cache_enabled = False
                self.cache_unavailable_reason = (
                    "explicit context caching is not available on this API tier "
                    "(TotalCachedContentStorageTokensPerModel limit=0); "
                    "falling back to implicit prefix caching"
                )
                logger.warning(f"[cache] {self.cache_unavailable_reason}")
            else:
                logger.error(f"[cache] creation failed ({type(e).__name__}): {msg[:300]}")
            return None

        token_count = 0
        if cache.usage_metadata is not None:
            token_count = cache.usage_metadata.total_token_count or 0
        state = CacheState(
            name=cache.name,
            model=model,
            prompt_sha256=self.prompt_sha,
            expires_at=time.time() + CACHE_TTL_SECONDS,
            token_count=token_count,
        )
        self._save_cache_state(state)
        logger.info(
            f"[cache] created {cache.name} for {model} "
            f"({token_count} tokens, ttl {CACHE_TTL_SECONDS}s)"
        )
        return state

    def ensure_cache(self, model: Optional[str] = None) -> Optional[str]:
        """Return an explicit cache name for a model, refreshing it near expiry."""
        if not self.explicit_cache_enabled:
            return None
        model = model or self.model
        with self._cache_lock:
            state = self._caches.get(model)
            if state is not None and state.expires_at - time.time() > CACHE_REFRESH_MARGIN_SECONDS:
                return state.name
            state = self._load_cache_state(model) or self._create_cache(model)
            if state is None:
                self._caches.pop(model, None)
                return None
            self._caches[model] = state
            return state.name

    def invalidate_cache(self, model: Optional[str] = None) -> None:
        model = model or self.model
        with self._cache_lock:
            self._caches.pop(model, None)
        path = cache_state_path(model=model)
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            logger.error(f"Failed to remove stale cache state {path}: {e}")

    # --------------------------------------------------------------- requests
    def _build_config(
        self, cache_name: Optional[str], degraded: bool = False
    ) -> types.GenerateContentConfig:
        """`degraded` drops schema-constrained decoding and buys more token headroom,
        for docs whose thinking pass keeps consuming the whole output budget."""
        kwargs = dict(
            response_mime_type="application/json",
            temperature=0.0,
            max_output_tokens=MAX_OUTPUT_TOKENS_DEGRADED if degraded else MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_SECONDS * 1000),
        )
        if not degraded:
            kwargs["response_schema"] = DocClassification
        if _SAFETY_SETTINGS is not None:
            kwargs["safety_settings"] = _SAFETY_SETTINGS
        if cache_name:
            kwargs["cached_content"] = cache_name
        else:
            kwargs["system_instruction"] = self.system_prompt
        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _status_code(err: Exception) -> Optional[int]:
        code = getattr(err, "code", None)
        if isinstance(code, int):
            return code
        match = re.match(r"^(\d{3}) ", str(err))
        return int(match.group(1)) if match else None

    @staticmethod
    def _suggested_delay(err: Exception) -> Optional[float]:
        match = _RETRY_DELAY_RE.search(str(err))
        return float(match.group(1)) if match else None

    @staticmethod
    def _backoff_delay(attempt: int, server_hint: Optional[float]) -> float:
        delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
        if server_hint is not None:
            delay = max(delay, server_hint)
        delay = min(delay, BACKOFF_CAP_SECONDS)
        return delay + random.uniform(0, delay * 0.25)

    @staticmethod
    def _is_stale_cache(err: Exception) -> bool:
        msg = str(err).lower()
        return "cached" in msg and ("not found" in msg or "expired" in msg or "invalid" in msg)

    def classify(
        self, text: str, models: Optional[Sequence[str]] = None
    ) -> Tuple[DocClassification, types.GenerateContentResponseUsageMetadata, str]:
        """One classification, rotating models on 429; raises on permanent failure.

        `models` pins the request (first try and every retry) to a specific chain.
        """
        candidates: List[str] = list(models) if models else self.models
        last_error: Optional[Exception] = None
        model = candidates[0]
        degraded = False

        for attempt in range(1, MAX_ATTEMPTS + 1):
            model = self._pick_model(candidates)
            cache_name = self.ensure_cache(model)
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=text,
                    config=self._build_config(cache_name, degraded=degraded),
                )
            except Exception as e:
                last_error = e
                if self._is_stale_cache(e):
                    logger.warning("[cache] request rejected stale cache; recreating")
                    self.invalidate_cache(model)
                    continue
                status = self._status_code(e)
                if status == 429:
                    self._mark_rate_limited(model, candidates)
                    if attempt < MAX_ATTEMPTS:
                        continue
                if status is not None and status not in _RETRY_STATUS:
                    logger.error(f"Non-retryable {status} from Gemini: {str(e)[:300]}")
                    raise
                if attempt == MAX_ATTEMPTS:
                    break
                delay = self._backoff_delay(attempt, self._suggested_delay(e))
                logger.warning(
                    f"Attempt {attempt}/{MAX_ATTEMPTS} failed ({type(e).__name__}"
                    f"{f' {status}' if status else ''}); retrying in {delay:.1f}s"
                )
                time.sleep(delay)
                continue

            parsed = self._parse(response)
            if parsed is None:
                why = self._diagnose(response)
                last_error = ValueError(f"model returned no parseable JSON ({why})")
                if attempt == MAX_ATTEMPTS:
                    break
                delay = self._backoff_delay(attempt, None)
                logger.warning(
                    f"Attempt {attempt}/{MAX_ATTEMPTS} on {model} unparseable [{why}]; "
                    f"retrying in {delay:.1f}s"
                    + (
                        ""
                        if degraded
                        else f" without response_schema, {MAX_OUTPUT_TOKENS_DEGRADED} token budget"
                    )
                )
                degraded = True
                time.sleep(delay)
                continue

            return parsed, response.usage_metadata, model

        logger.error(f"Giving up after {MAX_ATTEMPTS} attempts: {str(last_error)[:300]}")
        raise RuntimeError(f"classification failed after {MAX_ATTEMPTS} attempts: {last_error}")

    @staticmethod
    def _diagnose(response: types.GenerateContentResponse) -> str:
        """Why a 200 response yielded nothing usable — finish_reason, blocks, budget."""
        bits = []
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            bits.append("candidates=0")
        else:
            reason = getattr(candidates[0], "finish_reason", None)
            bits.append(f"finish_reason={getattr(reason, 'name', reason)}")
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) if content else None
            bits.append(f"parts={len(parts) if parts else 0}")
        feedback = getattr(response, "prompt_feedback", None)
        blocked = getattr(feedback, "block_reason", None) if feedback else None
        if blocked:
            bits.append(f"block_reason={getattr(blocked, 'name', blocked)}")
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            bits.append(f"thought_tokens={usage.thoughts_token_count or 0}")
            bits.append(f"output_tokens={usage.candidates_token_count or 0}")
        return " ".join(bits)

    @staticmethod
    def _parse(response: types.GenerateContentResponse) -> Optional[DocClassification]:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, DocClassification):
            return parsed
        raw = getattr(response, "text", None)
        if not raw:
            return None
        raw = _JSON_FENCE_RE.sub("", raw).strip()
        try:
            return DocClassification.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Cannot parse model output: {e}; raw={raw[:200]}")
            return None
