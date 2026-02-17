import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

from loguru import logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from bible_search import parse_passages
from testimony_search import (
    search_testimonies_content,
    suggest_terms,
    generate_derivatives,
    ensure_testimonies_file,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    port = os.environ.get("PORT", "not set")
    logger.info(f"[STARTUP] PORT env var = {port}")
    logger.info("[STARTUP] Ensuring testimonies file is ready...")
    try:
        count = ensure_testimonies_file()
        logger.info(f"[STARTUP] Testimonies file ready ({count} entries)")
    except Exception as e:
        logger.error(f"[STARTUP] Failed to prepare testimonies: {e}")
    logger.info("[STARTUP] Application ready to serve requests")
    yield
    logger.info("[SHUTDOWN] Application shutting down")


app = FastAPI(lifespan=lifespan)

# Simple in-memory analytics (in production, use a database)
request_count = 0
search_count = 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://marko-polo-cheno.github.io",
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


@app.get("/testimonies-suggest")
async def testimonies_suggest_endpoint(query: str = ""):
    """Get AI-suggested related search terms with pre-computed derivatives.

    Also returns derivatives for the user's own query terms so the frontend
    can toggle derivative visibility without any additional API calls.

    Returns:
        {
            "queryTerms": [{"term": str, "derivatives": [str, ...]}, ...],
            "suggestions": [{"term": str, "derivatives": [str, ...]}, ...]
        }
    queryTerms: the user's own input terms with their derivatives.
    suggestions: AI-suggested terms sorted alphabetically, each with derivatives.
    """
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    logger.info(f"TESTIMONIES SUGGEST REQUEST [{timestamp}]")
    logger.info(f"   Query: '{query}'")

    try:
        if not query:
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        # Compute derivatives for the user's own query terms
        user_terms = [t.strip() for t in query.split(",") if t.strip()]
        query_terms = [
            {"term": t, "derivatives": generate_derivatives(t)}
            for t in user_terms
        ]

        # Get AI suggestions (each already has derivatives, sorted alphabetically)
        suggestions = suggest_terms(query)

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


@app.get("/testimonies-search")
async def testimonies_search_endpoint(terms: str = ""):
    """Search testimonies with an explicit flat list of terms.

    The frontend assembles the final term list (user terms + selected AI terms
    + derivatives if the user toggled that on) and sends them comma-separated.
    No AI call happens here — just keyword matching.

    Args:
        terms: Comma-separated list of all search terms to match.
    """
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    logger.info(f"TESTIMONIES SEARCH REQUEST [{timestamp}]")
    logger.info(f"   Terms: '{terms}'")

    try:
        if not terms:
            return JSONResponse(content={"error": "Missing terms parameter"}, status_code=400)

        search_terms = [t.strip() for t in terms.split(",") if t.strip()]
        if not search_terms:
            return JSONResponse(content={"error": "No valid search terms"}, status_code=400)

        results = search_testimonies_content(search_terms)

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


def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"[MAIN] Starting uvicorn on 0.0.0.0:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
