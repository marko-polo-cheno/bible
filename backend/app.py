import os

# Prevent segfault from duplicate OpenMP runtimes (FAISS + PyTorch/FlagEmbedding
# both ship their own libomp; on macOS/Anaconda they collide at model-load time).
# Must run before faiss/torch are imported anywhere downstream.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import time
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from bible_search import parse_passages
from testimony_search import (
    search_testimonies_content,
    suggest_terms,
    analyze_query,
    generate_derivatives,
    ensure_testimonies_file,
)
from categories import get_category_tree
import elibrary
import rag_search
from pipeline import run_pipeline

BACKEND_DIR = Path(__file__).resolve().parent

# Shared eLibrary join map, built once at startup.
JMAP: Optional[elibrary.JoinMap] = None


def _bg_prepare_testimonies():
    global JMAP
    try:
        count = ensure_testimonies_file()
        logger.info(f"[BG] Testimonies file ready ({count} entries)")
    except Exception as e:
        logger.error(f"[BG] Failed to prepare testimonies: {e}")

    try:
        JMAP = elibrary.build_join_map(
            BACKEND_DIR / "testimonies_en.jsonl",
            BACKEND_DIR / "testimonies_zh.jsonl",
        )
        logger.info(f"[BG] eLibrary join map ready ({len(JMAP.items)} items)")
    except Exception as e:
        logger.error(f"[BG] Failed to build join map: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    port = os.environ.get("PORT", "not set")
    logger.info(f"[STARTUP] PORT env var = {port}")
    threading.Thread(target=_bg_prepare_testimonies, daemon=True).start()
    # Load the FAISS index + BGE-M3 model in the background; semantic search
    # turns on when ready while keyword/filter work immediately.
    rag_search.load_in_background()
    logger.info("[STARTUP] Application ready (corpus + semantic index loading in background)")
    yield
    logger.info("[SHUTDOWN] Application shutting down")


class ElibrarySearchRequest(BaseModel):
    stages: List[Dict[str, Any]]
    langIds: Optional[List[int]] = None
    page: int = 0
    size: int = 20


app = FastAPI(lifespan=lifespan)

# Simple in-memory analytics (in production, use a database)
request_count = 0
search_count = 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://marko-polo-cheno.github.io",
        "https://almondsandolives.ca",
        "https://www.almondsandolives.ca",
        "https://bible.almondsandolives.ca",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    global request_count
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    request_count += 1

    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    referer = request.headers.get("referer", "direct")
    origin = request.headers.get("origin", "unknown")
    x_forwarded_for = request.headers.get("x-forwarded-for", "")
    x_real_ip = request.headers.get("x-real-ip", "")

    real_ip = x_real_ip or (x_forwarded_for.split(",")[0].strip() if x_forwarded_for else client_ip)

    logger.info(f"INCOMING REQUEST #{request_count} [{timestamp}]")
    logger.info(f"   Method: {request.method}")
    logger.info(f"   URL: {request.url}")
    logger.info(f"   Client IP: {real_ip} (original: {client_ip})")
    logger.info(f"   Origin: {origin}")
    logger.info(f"   Referer: {referer}")
    logger.info(f"   User-Agent: {user_agent}")
    logger.info(f"   X-Forwarded-For: {x_forwarded_for}")

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(f"RESPONSE #{request_count} [{timestamp}]")
    logger.info(f"   Status: {response.status_code}")
    logger.info(f"   Processing time: {process_time:.3f}s")
    logger.info(f"   Served to: {real_ip} from {origin}")

    return response


@app.get("/")
async def health_check():
    timestamp = datetime.now().isoformat()
    logger.info(f"HEALTH CHECK [{timestamp}]")
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.get("/analytics")
async def get_analytics():
    """Simple analytics endpoint to track usage patterns."""
    timestamp = datetime.now().isoformat()
    logger.info(f"ANALYTICS REQUEST [{timestamp}]")

    return JSONResponse(content={
        "message": "Analytics endpoint - check logs for detailed usage tracking",
        "timestamp": timestamp,
        "usage_stats": {
            "total_requests": request_count,
            "search_requests": search_count,
            "uptime": "Check logs for detailed timing and origin data",
        },
        "note": "All requests are logged with IP, origin, user-agent, and timing data",
    }, status_code=200)


@app.get("/search")
async def search_endpoint(
    query: str = "",
    result_count: str = "few",
    content_type: str = "verses",
    model_type: str = "fast",
):
    global search_count

    search_count += 1
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    logger.info(f"SEARCH REQUEST #{search_count} [{timestamp}]")
    logger.info(f"   Query: '{query}'")
    logger.info(f"   Params: result_count='{result_count}', content_type='{content_type}', model_type='{model_type}'")

    try:
        if not query:
            logger.warning("Missing query parameter")
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        logger.info("Calling OpenAI API...")
        result = parse_passages(query, result_count, content_type, model_type)

        response = {
            "passages": [p.model_dump() for p in result.passages],
            "secondary_passages": [p.model_dump() for p in result.secondary_passages],
        }

        processing_time = time.time() - start_time

        logger.info(f"SEARCH SUCCESS [{timestamp}]")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Found {len(result.passages)} passages, {len(result.secondary_passages)} secondary")
        logger.info(f"   Passages: {[f'{p.book} {p.chapter}:{p.verse}' if hasattr(p, 'verse') else f'{p.book} {p.start_chapter}:{p.start_verse}-{p.end_verse}' for p in result.passages]}")

        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"SEARCH ERROR [{timestamp}]")
        logger.error(f"   Processing time: {processing_time:.2f}s")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/testimonies-categories")
async def testimonies_categories_endpoint(lang_id: int = 1):
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    logger.info(f"TESTIMONIES CATEGORIES REQUEST [{timestamp}] lang_id={lang_id}")

    try:
        tree = get_category_tree(lang_id)
        processing_time = time.time() - start_time
        logger.info(f"TESTIMONIES CATEGORIES SUCCESS [{timestamp}] {len(tree)} top-level categories in {processing_time:.2f}s")
        return JSONResponse(content={"categories": tree}, status_code=200)
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"TESTIMONIES CATEGORIES ERROR [{timestamp}] {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/testimonies-suggest")
async def testimonies_suggest_endpoint(query: str = "", lang: str = "en"):
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    is_chinese = lang == "zh"

    logger.info(f"TESTIMONIES SUGGEST REQUEST [{timestamp}]")
    logger.info(f"   Query: '{query}', lang: '{lang}'")

    try:
        if not query:
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        user_terms = [t.strip() for t in query.split(",") if t.strip()]
        query_terms = [
            {"term": t, "derivatives": [] if is_chinese else generate_derivatives(t)}
            for t in user_terms
        ]

        suggestions = suggest_terms(query, lang=lang)

        processing_time = time.time() - start_time
        logger.info(f"TESTIMONIES SUGGEST SUCCESS [{timestamp}]")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Query terms: {[q['term'] for q in query_terms]}")
        logger.info(f"   Suggested: {[s['term'] for s in suggestions]}")

        return JSONResponse(content={
            "queryTerms": query_terms,
            "suggestions": suggestions,
        }, status_code=200)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"TESTIMONIES SUGGEST ERROR [{timestamp}]")
        logger.error(f"   Error: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/testimonies-analyze")
async def testimonies_analyze_endpoint(query: str = ""):
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    logger.info(f"TESTIMONIES ANALYZE REQUEST [{timestamp}]")
    logger.info(f"   Query: '{query}'")

    try:
        if not query:
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        result = analyze_query(query)

        processing_time = time.time() - start_time
        logger.info(f"TESTIMONIES ANALYZE SUCCESS [{timestamp}]")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Lang IDs: {result['langIds']}")
        logger.info(f"   EN terms: {[t['term'] for t in result['termsEn']]}")
        logger.info(f"   ZH terms: {[t['term'] for t in result['termsZh']]}")

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"TESTIMONIES ANALYZE ERROR [{timestamp}]")
        logger.error(f"   Error: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/testimonies-search")
async def testimonies_search_endpoint(
    terms: str = "",
    lang_id: int = 1,
    categories: str | None = None,
    snippets: bool = False,
):
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    logger.info(f"TESTIMONIES SEARCH REQUEST [{timestamp}]")
    logger.info(f"   Terms: '{terms}', lang_id: {lang_id}, categories: '{categories}'")

    try:
        if not terms:
            return JSONResponse(content={"error": "Missing terms parameter"}, status_code=400)

        search_terms = [t.strip() for t in terms.split(",") if t.strip()]
        if not search_terms:
            return JSONResponse(content={"error": "No valid search terms"}, status_code=400)

        cat_list = [c.strip() for c in categories.split("|") if c.strip()] if categories else None
        results = search_testimonies_content(
            search_terms,
            lang_id=lang_id,
            categories=cat_list,
            generate_snippets=snippets,
        )

        response = {
            "searchTerms": search_terms,
            "results": results,
        }

        processing_time = time.time() - start_time

        logger.info(f"TESTIMONIES SEARCH SUCCESS [{timestamp}]")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Search terms ({len(search_terms)}): {search_terms[:10]}{'...' if len(search_terms) > 10 else ''}")
        logger.info(f"   Found {len(results)} testimonies")

        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"TESTIMONIES SEARCH ERROR [{timestamp}]")
        logger.error(f"   Error: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/elibrary/trees")
async def elibrary_trees_endpoint(lang_id: int = 1):
    """Both category trees for the filter UI: legacy (publication-format) and
    taxonomy (LLM topical)."""
    try:
        return JSONResponse(content={
            "legacy": elibrary.get_tree("legacy", lang_id),
            "taxonomy": elibrary.get_tree("taxonomy", lang_id),
        }, status_code=200)
    except Exception as e:
        logger.error(f"ELIBRARY TREES ERROR: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/elibrary/status")
async def elibrary_status_endpoint():
    return JSONResponse(content={
        "joinMapReady": JMAP is not None,
        "itemCount": len(JMAP.items) if JMAP is not None else 0,
        "semantic": rag_search.status(),
    }, status_code=200)


@app.post("/elibrary/search")
async def elibrary_search_endpoint(req: ElibrarySearchRequest):
    """Run a staged search pipeline. Each stage narrows the previous pool.

    Example body:
        {"stages": [
            {"type": "filter", "tree": "taxonomy", "prefixes": ["/Bible and Truth"]},
            {"type": "keyword", "terms": ["healing"], "includeDerivatives": true},
            {"type": "semantic", "query": "I lost my faith", "topK": 20}
        ], "page": 0, "size": 20}
    """
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    logger.info(f"ELIBRARY SEARCH REQUEST [{timestamp}] stages={[s.get('type') for s in req.stages]}")

    if JMAP is None:
        return JSONResponse(content={"error": "Index still building, try again shortly"}, status_code=503)

    try:
        result = run_pipeline(
            JMAP,
            req.stages,
            lang_ids=req.langIds,
            page=req.page,
            size=req.size,
        )
        result["semanticReady"] = rag_search.is_ready()
        processing_time = time.time() - start_time
        funnel = " -> ".join(f"{s['inCount']}→{s['outCount']}" for s in result["stages"])
        logger.info(f"ELIBRARY SEARCH SUCCESS [{timestamp}] {processing_time:.2f}s funnel: {funnel}")
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error(f"ELIBRARY SEARCH ERROR [{timestamp}] {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"[MAIN] Starting uvicorn on 0.0.0.0:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
