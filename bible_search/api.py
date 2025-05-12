from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from bible.bible_search.search import parse_passages


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://marko-polo-cheno.github.io"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/search")
def search(query: str = Query(...)):
    result = parse_passages(query)
    return {
        "passages": [p.model_dump_json() for p in result.passages],
        "secondary_passages": [p.model_dump_json() for p in result.secondary_passages],
    }
