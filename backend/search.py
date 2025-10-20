import argparse
import time
from loguru import logger
from typing import List, Union
from pydantic import BaseModel
from openai import OpenAI
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import json
from typing import List, Dict, Any

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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    global request_count
    from datetime import datetime
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    
    # Increment request counter
    request_count += 1
    
    # Extract detailed request information
    client_ip = request.client.host if request.client else 'unknown'
    user_agent = request.headers.get('user-agent', 'unknown')
    referer = request.headers.get('referer', 'direct')
    origin = request.headers.get('origin', 'unknown')
    x_forwarded_for = request.headers.get('x-forwarded-for', '')
    x_real_ip = request.headers.get('x-real-ip', '')
    
    # Determine actual client IP (considering proxies)
    real_ip = x_real_ip or (x_forwarded_for.split(',')[0].strip() if x_forwarded_for else client_ip)
    
    # Log incoming request with detailed tracking
    logger.info(f"📥 INCOMING REQUEST #{request_count} [{timestamp}]")
    logger.info(f"   Method: {request.method}")
    logger.info(f"   URL: {request.url}")
    logger.info(f"   Client IP: {real_ip} (original: {client_ip})")
    logger.info(f"   Origin: {origin}")
    logger.info(f"   Referer: {referer}")
    logger.info(f"   User-Agent: {user_agent}")
    logger.info(f"   X-Forwarded-For: {x_forwarded_for}")
    
    # Process request
    response = await call_next(request)
    
    # Log response with usage tracking
    process_time = time.time() - start_time
    logger.info(f"📤 RESPONSE #{request_count} [{timestamp}]")
    logger.info(f"   Status: {response.status_code}")
    logger.info(f"   Processing time: {process_time:.3f}s")
    logger.info(f"   Served to: {real_ip} from {origin}")
    
    return response

class Verse(BaseModel):
    """
    Single Bible verse.

    Attributes:
        book: Full name of the book (e.g., "Genesis", "John").
        chapter: Chapter number.
        verse: Verse number.
    """
    book: str
    chapter: int
    verse: int

class VerseRange(BaseModel):
    """
    Range of Bible verses.

    Attributes:
        book: Full name of the book.
        start_chapter: Starting chapter number.
        start_verse: Starting verse number.
        end_chapter: Ending chapter number.
        end_verse: Ending verse number.
    """
    book: str
    start_chapter: int
    start_verse: int
    end_chapter: int
    end_verse: int

class PassageQuery(BaseModel):
    """
    Container for a mix of single verses and verse ranges.

    Attributes:
        passages: List of Verse or VerseRange objects.
    """
    passages: List[Union[Verse, VerseRange]]
    secondary_passages: List[Union[Verse, VerseRange]]

class TestimoniesSearchQuery(BaseModel):
    terms: List[str]

SYSTEM_PROMPT = """\
You are a Bible scholar and passage searching expert. The Bible is a very large book making specific verses difficult to find.
Users will provide a prompt or question, and you will search for the relevant verses.


Return a PassageQuery object containing:
  - `passages`: the primary list of Verse or VerseRange items
  - `secondary_passages`: the secondary list of Verse or VerseRange items where other passages may be relevant or similar but not directly related to the user's query

<Steps>
1. Given the user's search query, understand the user's intent.
2. Consider which parts of the bible are relevant to efficiently find the specific verses the user is interested in.
3. Normalize book names to standard capitalization (e.g., "gen" -> "Genesis") such as Verse(book="Genesis", chapter=1, verse=1) or VerseRange(book="Genesis", start_chapter=1, start_verse=1, end_chapter=1, end_verse=2).
3. Provide the passages in a PassageQuery object.
</Steps>

<Example-1>
User input: "Show me the verses in Genesis that have the word H1254 בָּרָא"
passages=[
    Verse(book="Gen", chapter=1, verse=1),
    Verse(book="Gen", chapter=1, verse=21),
    Verse(book="Gen", chapter=1, verse=27),
    Verse(book="Gen", chapter=2, verse=3),
    Verse(book="Gen", chapter=2, verse=4),
    Verse(book="Gen", chapter=5, verse=1),
    Verse(book="Gen", chapter=5, verse=2),
    Verse(book="Gen", chapter=6, verse=7),
]
secondary_passages=[]
</Example-1>
<Example-2>
User input: "You shall not commit adultery, You shall not murder, You shall not steal, You shall not covet"
passages=[
    VerseRange(book="Exodus", start_chapter=20, start_verse=13, end_chapter=20, end_verse=17),
    VerseRange(book="Deuteronomy 5:17-21", start_chapter=5, start_verse=17, end_chapter=5, end_verse=21),
    Verse(book="Romans", chapter=13, verse=9),
]
secondary_passages=[
    VerseRange(book="Matthew", start_chapter=19, start_verse=18, end_chapter=19, end_verse=19),
    Verse(book="Mark", chapter=10, verse=19),
    Verse(book="Luke", chapter=18, verse=20),
]
</Example-2>
<Example-3>
User input: "where does esther become queen"
passages=[
    VerseRange(book="Esther", start_chapter=2, start_verse=1, end_chapter=2, end_verse=18),
]
secondary_passages=[]
</Example-3>
<Example-4>
User input: "where does jonah pray and preach at nineveh?"
passages=[
    VerseRange(book="Jonah", start_chapter=2, start_verse=1, end_chapter=3, end_verse=4),
]
secondary_passages=[]
</Example-4>
"""

client = OpenAI()

# Global cache for testimonies data
testimonies_data = None

def load_testimonies_data():
    """Load testimonies data from JSONL file with caching."""
    global testimonies_data
    if testimonies_data is None:
        try:
            testimonies_data = []
            with open('testimonies.jsonl', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        testimonies_data.append(json.loads(line))
            logger.info(f"Loaded {len(testimonies_data)} testimonies into memory cache")
        except Exception as e:
            logger.error(f"Failed to load testimonies data: {e}")
            testimonies_data = []
    return testimonies_data

def search_testimonies_content(search_terms: List[str]) -> List[Dict[str, Any]]:
    """Simple, efficient search through testimonies content."""
    testimonies = load_testimonies_data()
    if not testimonies:
        return []
    
    results = []
    search_terms_lower = [term.lower() for term in search_terms]
    
    for testimony in testimonies:
        content = testimony.get('content', '').lower()
        hit_count = sum(content.count(term) for term in search_terms_lower)
        
        if hit_count > 0:
            results.append({
                'filename': testimony.get('filename', ''),
                'link': testimony.get('link', ''),
                'hitCount': hit_count
            })
    
    # Sort by hit count (descending)
    results.sort(key=lambda x: x['hitCount'], reverse=True)
    return results

def parse_testimonies_search(user_text: str) -> TestimoniesSearchQuery:
    """
    Send the user query text to the LLM and parse the response into a TestimoniesSearchQuery.
    """
    system_prompt = """\
You are a Christian testimonies reading expert. When a user provides a search term, you should:
1. Take the user's input term.
2. Generate a list of three to five similar or related terms (strings) that would help find relevant testimonies.

For example:
- User input: "leukemia" → terms: ["blood cancer", "bone marrow", "leukemic"]
- User input: "argentena" → terms: ["argentina", "south america", "spanish"]
- User input: "car accident" → terms: ["crash", "accident", "vehicle", "car", "drive"]

Return a TestimoniesSearchQuery object with:
- terms: a list of three strings (the similar/related terms).
"""
    try:
        logger.info(f"Making API call for testimonies search with term: {user_text}")
        response = client.beta.chat.completions.parse(
            model="gpt-5-nano-2025-08-07",
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format=TestimoniesSearchQuery,
        )
        logger.info("Testimonies search API call completed successfully")
        return response.choices[0].message.parsed
    except Exception as e:
        logger.error(f"Testimonies search API call failed: {str(e)}")
        raise

def parse_passages(user_text: str, result_count: str = "few", content_type: str = "verses", model_type: str = "fast") -> PassageQuery:
    """
    Send the user query text to the LLM and parse the response into a PassageQuery.
    """
    if model_type == "fast":
        model = "gpt-5-nano-2025-08-07"
    else:
        model = "gpt-5-2025-08-07"
    
    system_prompt = SYSTEM_PROMPT
    if content_type == "verses":
        system_prompt += "\n\nFocus on finding individual verses rather than long passages."
    elif content_type == "passages":
        system_prompt += "\n\nFocus on finding complete sections or chapters rather than individual verses."

    if result_count == "one":
        user_text += "\n\nReturn only the most relevant single result in the passages list."
    elif result_count == "few":
        user_text += "\n\nReturn a small number (2-5) of the most relevant results in the passages list."
    elif result_count == "many":
        user_text += "\n\nReturn a comprehensive list of relevant results in the passages list."
    
    try:
        logger.info(f"Making API call to {model} with reasoning_effort={'high' if model_type == 'advanced' else 'low'}")
        response = client.beta.chat.completions.parse(
            model=model,
            reasoning_effort="high" if model_type == "advanced" else "low",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format=PassageQuery,
        )
        logger.info("API call completed successfully")
        return response.choices[0].message.parsed
    except Exception as e:
        logger.error(f"API call failed: {str(e)}")
        raise


@app.get("/")
async def health_check():
    from datetime import datetime
    timestamp = datetime.now().isoformat()
    logger.info(f"🏥 HEALTH CHECK [{timestamp}]")
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.get("/analytics")
async def get_analytics():
    """Simple analytics endpoint to track usage patterns"""
    from datetime import datetime, timedelta
    
    # This is a basic implementation - in production you'd use a database
    timestamp = datetime.now().isoformat()
    logger.info(f"📊 ANALYTICS REQUEST [{timestamp}]")
    
    return JSONResponse(content={
        "message": "Analytics endpoint - check logs for detailed usage tracking",
        "timestamp": timestamp,
        "usage_stats": {
            "total_requests": request_count,
            "search_requests": search_count,
            "uptime": "Check logs for detailed timing and origin data"
        },
        "note": "All requests are logged with IP, origin, user-agent, and timing data"
    }, status_code=200)

@app.get("/search")
async def search_endpoint(
    query: str = "", 
    result_count: str = "few", 
    content_type: str = "verses", 
    model_type: str = "fast"
):
    global search_count
    import time
    from datetime import datetime
    
    # Increment search counter
    search_count += 1
    
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    
    # Enhanced logging with request details
    logger.info(f"🔍 SEARCH REQUEST #{search_count} [{timestamp}]")
    logger.info(f"   Query: '{query}'")
    logger.info(f"   Params: result_count='{result_count}', content_type='{content_type}', model_type='{model_type}'")
    
    try:
        if not query:
            logger.warning("❌ Missing query parameter")
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        logger.info("🤖 Calling OpenAI API...")
        result = parse_passages(query, result_count, content_type, model_type)
        
        response = {
            "passages": [p.model_dump() for p in result.passages],
            "secondary_passages": [p.model_dump() for p in result.secondary_passages],
        }
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Enhanced success logging
        logger.info(f"✅ SEARCH SUCCESS [{timestamp}]")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Found {len(result.passages)} passages, {len(result.secondary_passages)} secondary")
        logger.info(f"   Passages: {[f'{p.book} {p.chapter}:{p.verse}' if hasattr(p, 'verse') else f'{p.book} {p.start_chapter}:{p.start_verse}-{p.end_verse}' for p in result.passages]}")
        
        return JSONResponse(content=response, status_code=200)
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ SEARCH ERROR [{timestamp}]")
        logger.error(f"   Processing time: {processing_time:.2f}s")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/testimonies-search")
async def testimonies_search_endpoint(query: str = ""):
    """Search through testimonies using AI-powered term expansion."""
    import time
    from datetime import datetime
    
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    
    # Enhanced logging with request details
    logger.info(f"🔍 TESTIMONIES SEARCH REQUEST [{timestamp}]")
    logger.info(f"   Query: '{query}'")
    
    try:
        if not query:
            logger.warning("❌ Missing query parameter")
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        logger.info("🤖 Calling OpenAI API for term expansion...")
        search_query = parse_testimonies_search(query)
        
        logger.info("🔍 Searching testimonies content...")
        search_terms = [query] + search_query.terms
        results = search_testimonies_content(search_terms)
        
        response = {
            "searchTerms": search_terms,
            "results": results
        }
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Enhanced success logging
        logger.info(f"✅ TESTIMONIES SEARCH SUCCESS [{timestamp}]")
        logger.info(f"   Processing time: {processing_time:.2f}s")
        logger.info(f"   Search terms: {search_terms}")
        logger.info(f"   Found {len(results)} testimonies")
        
        return JSONResponse(content=response, status_code=200)
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"❌ TESTIMONIES SEARCH ERROR [{timestamp}]")
        logger.error(f"   Processing time: {processing_time:.2f}s")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

def main():
    """Entry point for the application."""
    uvicorn.run("search:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
