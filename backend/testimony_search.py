import json
import threading
from typing import List, Dict, Any
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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


def _extract_lang_id(link: str) -> int | None:
    try:
        qs = parse_qs(urlparse(link).query)
        vals = qs.get("LangID") or qs.get("langid") or qs.get("langID")
        if vals:
            return int(vals[0])
    except (ValueError, IndexError):
        pass
    return None


def get_categories(lang_id: int) -> List[str]:
    ensure_testimonies_file()
    cats: set[str] = set()
    try:
        with open(JSONL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _extract_lang_id(entry.get("link", "")) != lang_id:
                    continue
                for c in entry.get("category", []):
                    if c:
                        cats.add(c)
    except Exception as e:
        logger.error(f"Error reading categories: {e}")
        return []
    return sorted(cats)


def search_testimonies_content(
    search_terms: List[str],
    lang_id: int | None = None,
    category: str | None = None,
) -> List[Dict[str, Any]]:
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

                if lang_id is not None:
                    if _extract_lang_id(testimony.get("link", "")) != lang_id:
                        continue

                if category is not None:
                    if category not in testimony.get("category", []):
                        continue

                raw = testimony.get("content", "").lower()
                content = (raw[:5000] + raw[-5000:]) if len(raw) > 10000 else raw
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


_SYSTEM_PROMPT_EN = """\
You are a keyword brainstorming assistant for a religious article archive (True Jesus Church).
Given a user's search term, generate approximately 4-6 related words or terms that someone might use when describing the same topic in a personal testimony or article.

Think broadly: include synonyms, related concepts, common collocations, and terms from adjacent topics.

Examples:
- "exam" → ["test", "school", "study", "grade", "midterm", "finals", "stress", "report card", "student", "academic"]
- "leukemia" → ["blood cancer", "bone marrow", "chemotherapy", "cancer", "hospital", "diagnosis", "healing", "remission", "white blood cells", "treatment"]
- "car accident" → ["crash", "collision", "vehicle", "traffic", "hospital", "injury", "driving", "road", "emergency", "insurance"]

Use True Jesus Church terminology so if the user's search term is "Holy Spirit", do not suggest "Holy Ghost" or "Holy Ghosts", or "Baptism of Holy Spirit" as it is a substring, but "Fruit of the spirit" and "Speaking in tongue" are great suggestions.
Always keep the terms in root format, so "speaking in tongues" should be "speaking in tongue".

Return a TestimoniesSearchQuery object with:
- terms: a list of approximately 4-6 related terms, ideally single words/concepts that are directly related to the user's search term.
"""

_SYSTEM_PROMPT_ZH = """\
你是一個真耶穌教會宗教文章庫的關鍵字聯想助手。
根據使用者的搜尋詞，產生大約 4-6 個相關的中文詞彙或短語，這些詞彙是人們在個人見證或文章中描述同一主題時可能會使用的。

廣泛思考：包含同義詞、相關概念、常見搭配和相鄰主題的詞彙。包含繁體和簡體中文的變體。

範例：
- "洗禮" → ["受洗", "浸禮", "大水", "赦罪", "悔改", "歸入基督", "重生"]
- "聖靈" → ["方言禱告", "靈言", "寶惠師", "感動", "充滿", "恩賜"]
- "安息日" → ["守安息", "十誡", "第七日", "聖日", "敬拜"]

使用真耶穌教會的術語。所有建議的詞彙都必須是中文。

回傳一個 TestimoniesSearchQuery 物件：
- terms: 大約 4-6 個相關詞彙的列表。
"""


def suggest_terms(user_text: str, lang: str = "en") -> List[Dict[str, Any]]:
    system_prompt = _SYSTEM_PROMPT_ZH if lang == "zh" else _SYSTEM_PROMPT_EN
    is_chinese = lang == "zh"

    try:
        logger.info(f"Making AI suggestion call for: {user_text} (lang={lang})")
        response = client.beta.chat.completions.parse(
            model="gpt-5.2-2025-12-11",
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"I'm searching for: {user_text}"},
            ],
            response_format=TestimoniesSearchQuery,
        )
        logger.info("AI suggestion call completed successfully")
        raw_terms = response.choices[0].message.parsed.terms

        enriched = sorted(
            [
                {"term": t, "derivatives": [] if is_chinese else generate_derivatives(t)}
                for t in raw_terms
            ],
            key=lambda x: x["term"].lower(),
        )
        return enriched
    except Exception as e:
        logger.error(f"AI suggestion call failed: {str(e)}")
        raise
