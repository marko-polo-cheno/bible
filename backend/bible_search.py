from loguru import logger
from openai import OpenAI

from models import PassageQuery

client = OpenAI()

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


def parse_passages(user_text: str, result_count: str = "few", content_type: str = "verses", model_type: str = "fast") -> PassageQuery:
    """
    Send the user query text to the LLM and parse the response into a PassageQuery.
    """
    if model_type == "fast":
        model = "gpt-5-mini-2025-08-07"
    else:
        model = "gpt-5.2-2025-12-11"

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
