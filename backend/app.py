import time
from datetime import datetime

from loguru import logger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from bible_search import parse_passages
from testimony_search import (
    search_testimonies_content,
    parse_testimonies_search,
)

app = FastAPI()

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


@app.get("/testimonies-search")
async def testimonies_search_endpoint(query: str = ""):
    """Search through testimonies using AI-powered term expansion."""
    start_time = time.time()
    timestamp = datetime.now().isoformat()

    logger.info(f"TESTIMONIES SEARCH REQUEST [{timestamp}]")
    logger.info(f"   Query: '{query}'")

    try:
        if not query:
            logger.warning("Missing query parameter")
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        logger.info("Calling OpenAI API for term expansion...")
        search_query = parse_testimonies_search(query)

        logger.info("Searching testimonies content...")
        search_terms = [query] + search_query.terms
        results = search_testimonies_content(search_terms)

        response = {
            "searchTerms": search_terms,
            "results": results,
        }

        processing_time = time.time() - start_time

        logger.info(f"TESTIMONIES SEARCH SUCCESS [{timestamp}]")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Search terms: {search_terms}")
        logger.info(f"   Found {len(results)} testimonies")

        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"TESTIMONIES SEARCH ERROR [{timestamp}]")
        logger.error(f"   Processing time: {processing_time:.2f}s")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


def main():
    """Entry point for the application."""
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
