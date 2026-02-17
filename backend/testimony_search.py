import json
import threading
from typing import List, Dict, Any
from pathlib import Path

import requests as http_requests
from loguru import logger
from openai import OpenAI

from models import TestimoniesSearchQuery

client = OpenAI()

JSONL_PATH = Path(__file__).parent / "testimonies.jsonl"

SUFFIXES = ["s", "es", "ed", "d", "ing", "er", "ers", "ly", "tion", "sion", "ment", "ness", "ful", "less", "ous", "ive", "al", "ity"]

TESTIMONIES_URL = (
    "https://github.com/marko-polo-cheno/bible/raw/main/backend/testimonies.jsonl"
)

_file_ready = False
_file_lock = threading.Lock()


def _download_testimonies():
    logger.info("Downloading testimonies.jsonl from GitHub...")
    resp = http_requests.get(TESTIMONIES_URL, timeout=120, stream=True)
    resp.raise_for_status()
    size = 0
    with open(JSONL_PATH, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            size += len(chunk)
    logger.info(f"Downloaded testimonies.jsonl ({size} bytes)")


def _is_lfs_pointer() -> bool:
    try:
        with open(JSONL_PATH, "r", encoding="utf-8") as f:
            first_line = f.readline()
        return "git-lfs.github.com" in first_line
    except FileNotFoundError:
        return True


def ensure_testimonies_file() -> int:
    global _file_ready
    if _file_ready:
        return -1

    with _file_lock:
        if _file_ready:
            return -1

        if _is_lfs_pointer():
            logger.warning("testimonies.jsonl is missing or is a Git LFS pointer")
            try:
                _download_testimonies()
            except Exception as e:
                logger.error(f"Failed to download testimonies.jsonl: {e}")
                return 0

        count = 0
        try:
            with open(JSONL_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
            logger.info(f"testimonies.jsonl validated: {count} entries")
        except Exception as e:
            logger.error(f"Failed to validate testimonies.jsonl: {e}")
            return 0

        _file_ready = True
        return count


def generate_derivatives(word: str) -> List[str]:
    """Generate common English derivatives of a word (plural, past tense, gerund, etc.)."""
    word = word.strip().lower()
    if not word or len(word) < 2:
        return []

    derivatives = set()
    for suffix in SUFFIXES:
        derivatives.add(word + suffix)

    # Handle words ending in 'e' (e.g., "hope" -> "hoping", "hoped")
    if word.endswith("e"):
        derivatives.add(word[:-1] + "ing")
        derivatives.add(word + "d")
        derivatives.add(word[:-1] + "ation")

    # Handle words ending in 'y' (e.g., "pray" -> "prays", "prayed", "praying", "prayer")
    if word.endswith("y"):
        derivatives.add(word[:-1] + "ies")
        derivatives.add(word[:-1] + "ied")
        derivatives.add(word[:-1] + "ier")

    # Handle consonant doubling (e.g., "sin" -> "sinning", "sinned")
    if len(word) >= 3 and word[-1] not in "aeiouwy" and word[-2] in "aeiou" and word[-3] not in "aeiou":
        derivatives.add(word + word[-1] + "ing")
        derivatives.add(word + word[-1] + "ed")
        derivatives.add(word + word[-1] + "er")

    # Remove the original word if it snuck in
    derivatives.discard(word)
    return sorted(derivatives)


def search_testimonies_content(search_terms: List[str]) -> List[Dict[str, Any]]:
    ensure_testimonies_file()

    seen = set()
    unique_terms = []
    for t in search_terms:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            unique_terms.append(t_lower)

    if not unique_terms:
        return []

    results = []
    try:
        with open(JSONL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    testimony = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = testimony.get("content", "").lower()
                hit_count = sum(content.count(term) for term in unique_terms)
                if hit_count > 0:
                    results.append({
                        "filename": testimony.get("filename", ""),
                        "link": testimony.get("link", ""),
                        "hitCount": hit_count,
                    })
    except Exception as e:
        logger.error(f"Error searching testimonies: {e}")
        return []

    results.sort(key=lambda x: x["hitCount"], reverse=True)
    return results


def suggest_terms(user_text: str) -> List[Dict[str, Any]]:
    """
    Use AI to suggest ~10 related search terms, then attach pre-computed
    derivatives to each so the frontend never needs a second LLM call.

    Returns a list of {"term": str, "derivatives": [str, ...]} dicts,
    sorted alphabetically by term.
    """
    system_prompt = """\
You are a keyword brainstorming assistant for a religious testimony archive (True Jesus Church).
Given a user's search term, generate approximately 10 related words or short phrases that someone might use when describing the same topic in a personal testimony or sermon.

Think broadly: include synonyms, related concepts, common collocations, and terms from adjacent topics. For terms in Chinese, include both simplified and traditional variants where they differ.

Examples:
- "exam" → ["test", "school", "study", "grade", "midterm", "finals", "stress", "report card", "student", "academic"]
- "leukemia" → ["blood cancer", "bone marrow", "chemotherapy", "cancer", "hospital", "diagnosis", "healing", "remission", "white blood cells", "treatment"]
- "car accident" → ["crash", "collision", "vehicle", "traffic", "hospital", "injury", "driving", "road", "emergency", "insurance"]
- "洗禮" → ["受洗", "浸禮", "洗禮", "大水", "赦罪", "baptism", "悔改", "歸入基督", "重生", "水"]

Return a TestimoniesSearchQuery object with:
- terms: a list of approximately 10 related terms.
"""
    try:
        logger.info(f"Making AI suggestion call for: {user_text}")
        response = client.beta.chat.completions.parse(
            model="gpt-5-mini-2025-08-07",
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format=TestimoniesSearchQuery,
        )
        logger.info("AI suggestion call completed successfully")
        raw_terms = response.choices[0].message.parsed.terms

        # Attach derivatives to each term and sort alphabetically
        enriched = sorted(
            [{"term": t, "derivatives": generate_derivatives(t)} for t in raw_terms],
            key=lambda x: x["term"].lower(),
        )
        return enriched
    except Exception as e:
        logger.error(f"AI suggestion call failed: {str(e)}")
        raise
