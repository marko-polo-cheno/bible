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

JSONL_PATH_EN = Path(__file__).parent / "testimonies_en.jsonl"
JSONL_PATH_ZH = Path(__file__).parent / "testimonies_zh.jsonl"

SUFFIXES = ["s", "es", "ed", "d", "ing", "er", "ers", "ly", "tion", "sion", "ment", "ness", "ful", "less", "ous", "ive", "al", "ity"]

TESTIMONIES_URL_EN = (
    "https://github.com/marko-polo-cheno/bible/raw/main/backend/testimonies_en.jsonl"
)
TESTIMONIES_URL_ZH = (
    "https://github.com/marko-polo-cheno/bible/raw/main/backend/testimonies_zh.jsonl"
)

_file_ready_en = False
_file_ready_zh = False
_file_lock = threading.Lock()


def _download_file(url: str, path: Path):
    logger.info(f"Downloading {path.name} from GitHub...")
    resp = http_requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    size = 0
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            size += len(chunk)
    logger.info(f"Downloaded {path.name} ({size} bytes)")


def _is_lfs_pointer(path: Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            first_line = f.readline()
        return "git-lfs.github.com" in first_line
    except FileNotFoundError:
        return True


def _ensure_file(path: Path, url: str) -> int:
    if _is_lfs_pointer(path):
        logger.warning(f"{path.name} is missing or is a Git LFS pointer")
        try:
            _download_file(url, path)
        except Exception as e:
            logger.error(f"Failed to download {path.name}: {e}")
            return 0

    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        logger.info(f"{path.name} validated: {count} entries")
    except Exception as e:
        logger.error(f"Failed to validate {path.name}: {e}")
        return 0
    return count


def ensure_testimonies_file() -> int:
    global _file_ready_en, _file_ready_zh

    with _file_lock:
        total = 0
        if not _file_ready_en:
            count = _ensure_file(JSONL_PATH_EN, TESTIMONIES_URL_EN)
            if count > 0:
                _file_ready_en = True
                total += count

        if not _file_ready_zh:
            count = _ensure_file(JSONL_PATH_ZH, TESTIMONIES_URL_ZH)
            if count > 0:
                _file_ready_zh = True
                total += count

        return total if total > 0 else -1


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


def _get_jsonl_path(lang_id: int) -> Path:
    return JSONL_PATH_ZH if lang_id == 2 else JSONL_PATH_EN


def search_testimonies_content(
    search_terms: List[str],
    lang_id: int = 1,
    categories: List[str] | None = None,
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

    jsonl_path = _get_jsonl_path(lang_id)
    results = []
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    testimony = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Category filtering: prefix-based matching
                if categories:
                    entry_cats = testimony.get("category", [])
                    if not any(
                        ec == sc or ec.startswith(sc + "/")
                        for ec in entry_cats
                        for sc in categories
                    ):
                        continue

                raw = testimony.get("content", "").lower()
                content = (raw[:5000] + raw[-5000:]) if len(raw) > 10000 else raw
                hit_count = sum(content.count(term) for term in unique_terms)
                if hit_count > 0:
                    full_content = testimony.get("content", "")
                    preview = full_content[:180].rstrip() + ("..." if len(full_content) > 180 else "")
                    results.append({
                        "filename": testimony.get("filename", ""),
                        "link": testimony.get("link", ""),
                        "hitCount": hit_count,
                        "preview": preview,
                        "categories": testimony.get("category", []),
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
            model="gpt-5.4-mini-2026-03-17",
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
