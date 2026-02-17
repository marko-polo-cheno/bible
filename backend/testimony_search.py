import json
from typing import List, Dict, Any
from pathlib import Path

from loguru import logger
from openai import OpenAI

from models import TestimoniesSearchQuery

client = OpenAI()

# Global cache for testimonies data
testimonies_data = None

JSONL_PATH = Path(__file__).parent / "testimonies.jsonl"


def load_testimonies_data() -> list:
    """Load testimonies data from JSONL file with caching."""
    global testimonies_data
    if testimonies_data is None:
        try:
            testimonies_data = []
            with open(JSONL_PATH, "r", encoding="utf-8") as f:
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
        content = testimony.get("content", "").lower()
        hit_count = sum(content.count(term) for term in search_terms_lower)

        if hit_count > 0:
            results.append({
                "filename": testimony.get("filename", ""),
                "link": testimony.get("link", ""),
                "hitCount": hit_count,
            })

    results.sort(key=lambda x: x["hitCount"], reverse=True)
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
