import argparse
from typing import List, Union
from pydantic import BaseModel
from openai import OpenAI
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://marko-polo-cheno.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def parse_passages(user_text: str) -> PassageQuery:
    """
    Send the user query text to the LLM and parse the response into a PassageQuery.
    """
    response = client.beta.chat.completions.parse(
        model="o4-mini",
        reasoning_effort="high",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        response_format=PassageQuery,
    )
    return response.choices[0].message.parsed


@app.get("/")
async def search_endpoint(query: str = ""):
    try:
        if not query:
            return JSONResponse(content={"error": "Missing query parameter"}, status_code=400)

        result = parse_passages(query)
        response = {
            "passages": [p.model_dump() for p in result.passages],
            "secondary_passages": [p.model_dump() for p in result.secondary_passages],
        }
        return JSONResponse(content=response, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# def main():
#     parser = argparse.ArgumentParser(description="Bible Passage Search Query Parser")
#     parser.add_argument(
#         "query", type=str,
#         help="User input describing verses or ranges, e.g. 'John 3:16' or 'Gen 1:1-2'"
#     )
#     args = parser.parse_args()
#     query = parse_passages(args.query)
#     print("Parsed Passages:")
#     for p in query.passages:
#         print(p.model_dump_json())
#     print("Secondary Passages:")
#     for p in query.secondary_passages:
#         print(p.model_dump_json())

if __name__ == "__main__":
    uvicorn.run("search:app", host="0.0.0.0", port=8000, reload=True)
