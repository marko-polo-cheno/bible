import json
import threading
from typing import List, Dict, Any
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests as http_requests
from loguru import logger
from openai import OpenAI

from models import TestimoniesSearchQuery, TestimoniesUnifiedQuery

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


def generate_kwic_preview(
    content: str,
    terms: List[str],
    max_snippets: int = 3,
    context_chars: int = 80,
) -> List[Dict[str, Any]]:
    """Generate keyword-in-context preview snippets with highlight positions."""
    if not content or not terms:
        return []

    content_lower = content.lower()
    # Find all match positions: (start, end, term_index)
    matches = []
    for i, term in enumerate(terms):
        term_lower = term.lower()
        pos = 0
        while True:
            idx = content_lower.find(term_lower, pos)
            if idx == -1:
                break
            matches.append((idx, idx + len(term_lower), i))
            pos = idx + 1

    if not matches:
        return []

    matches.sort(key=lambda m: m[0])

    # Build windows around each match
    windows = []
    for start, end, term_idx in matches:
        win_start = max(0, start - context_chars)
        win_end = min(len(content), end + context_chars)
        windows.append((win_start, win_end, {term_idx}))

    # Merge overlapping windows
    merged = [windows[0]]
    for win_start, win_end, term_set in windows[1:]:
        prev_start, prev_end, prev_terms = merged[-1]
        if win_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, win_end), prev_terms | term_set)
        else:
            merged.append((win_start, win_end, term_set))

    # Score by number of distinct terms covered
    merged.sort(key=lambda w: len(w[2]), reverse=True)

    snippets = []
    for win_start, win_end, _ in merged[:max_snippets]:
        text = content[win_start:win_end]
        # Find highlights within this window
        highlights = []
        text_lower = text.lower()
        for term in terms:
            term_lower = term.lower()
            pos = 0
            while True:
                idx = text_lower.find(term_lower, pos)
                if idx == -1:
                    break
                highlights.append([idx, idx + len(term_lower)])
                pos = idx + 1

        # Sort and merge overlapping highlights
        highlights.sort()
        if highlights:
            merged_hl = [highlights[0]]
            for hl in highlights[1:]:
                if hl[0] <= merged_hl[-1][1]:
                    merged_hl[-1][1] = max(merged_hl[-1][1], hl[1])
                else:
                    merged_hl.append(hl)
            highlights = merged_hl

        prefix = "..." if win_start > 0 else ""
        suffix = "..." if win_end < len(content) else ""
        snippets.append({
            "text": prefix + text + suffix,
            "highlights": [[h[0] + len(prefix), h[1] + len(prefix)] for h in highlights],
        })

    return snippets


def search_testimonies_content(
    search_terms: List[str],
    lang_id: int = 1,
    categories: List[str] | None = None,
    generate_snippets: bool = False,
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
                    entry = {
                        "filename": testimony.get("filename", ""),
                        "link": testimony.get("link", ""),
                        "hitCount": hit_count,
                        "preview": preview,
                        "categories": testimony.get("category", []),
                    }
                    if generate_snippets:
                        entry["snippets"] = generate_kwic_preview(full_content, unique_terms)
                    results.append(entry)
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

Note that you must return terms in a plain list without any formatting or delimiters.

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

注意：你必須以純列表形式回傳詞彙，不得使用任何額外格式或分隔符。

回傳一個 TestimoniesSearchQuery 物件：
- terms: 大約 4-6 個相關詞彙的列表。
"""


_SYSTEM_PROMPT_UNIFIED = """\
You are a search assistant for a True Jesus Church religious article archive containing ~21,000 testimonies and publications in English and Chinese.

Given a user's search query (which may be in English, Chinese, or mixed), analyze it and return structured search parameters.

## Language Detection
- If the query contains primarily English/Latin characters, set lang_ids to [1] (English).
- If the query contains primarily CJK characters, set lang_ids to [2] (Chinese).
- If the query is mixed or the topic would benefit from searching both corpora, set lang_ids to [1, 2].

## Category Selection
Select the most relevant category path prefixes. Use parent paths for broad matches (e.g. "Media" matches everything under Media), leaf paths for precision. If the query is general, return empty lists to search all categories.

English categories:
- Media/Sermon, Media/Lecture, Media/Testimony
- Books/Book/Basic Beliefs (sub: Outreach Series, Gospel Series, Inquiry Series, Doctrinal Series, Testimony Series)
- Books/Book/Christian Living/Discipleship Series
- Books/Book/Biblical References (sub: Bible Study Guides, Bible Curriculum, Topical Studies)
- Books/Book/Religious Education (sub: Textbooks, Student Workbooks, Student Spiritual Convocation, Manuals)
- Magazines/Magazine/Manna Magazine, Magazines/Magazine/Living Water, Magazines/Magazine/Showers of Blessing, Magazines/Magazine/Heavenly Sunlight
- Training Materials/Lecture Notes
- Unknown

Chinese categories:
- 影音/講道, 影音/講習會, 影音/見證
- 書籍/書籍/釋義類, 書籍/書籍/研經類, 書籍/書籍/查經類, 書籍/書籍/福音類
- 雜誌/雜誌/聖靈月刊 (sub: 蒙恩見證, 真理, 福音, 靈修, 信徒園地, 專題報導, etc.)
- 雜誌/雜誌/青年團契, 雜誌/雜誌/宗教教育, 雜誌/雜誌/聖靈報
- 教材/教材/幼年班, 教材/教材/高級班, 教材/教材/神學院
- 未分類

For personal testimony queries, prefer: Media/Testimony, Books/Book/Basic Beliefs/Testimony Series, Magazines/Magazine/Manna Magazine (EN) or 影音/見證, 雜誌/雜誌/聖靈月刊/蒙恩見證 (ZH).

## Term Generation
Generate 6-10 search keywords per applicable language. Include:
- The user's explicit terms (decomposed into individual keywords)
- Synonyms and related concepts
- True Jesus Church specific terminology
- Keep terms in root/base form (no plurals or conjugations)
- For Chinese, include both traditional and simplified variants where applicable

## Derivatives
Set include_derivatives to true for English queries where matching word forms (plurals, past tense, gerunds) would improve recall. Set to false for very specific or proper-noun queries.

Return a TestimoniesUnifiedQuery object.
"""


def analyze_query(user_text: str) -> Dict[str, Any]:
    """Unified LLM call that auto-detects language, categories, and search terms."""
    try:
        logger.info(f"Making unified analyze call for: {user_text}")
        response = client.beta.chat.completions.parse(
            model="gpt-5.4-mini-2026-03-17",
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT_UNIFIED},
                {"role": "user", "content": user_text},
            ],
            response_format=TestimoniesUnifiedQuery,
        )
        logger.info("Unified analyze call completed successfully")
        parsed = response.choices[0].message.parsed

        # Enrich English terms with derivatives
        terms_en_enriched = sorted(
            [{"term": t, "derivatives": generate_derivatives(t)} for t in parsed.terms_en],
            key=lambda x: x["term"].lower(),
        )
        terms_zh_enriched = sorted(
            [{"term": t, "derivatives": []} for t in parsed.terms_zh],
            key=lambda x: x["term"],
        )

        return {
            "langIds": parsed.lang_ids,
            "categoriesEn": parsed.categories_en,
            "categoriesZh": parsed.categories_zh,
            "termsEn": terms_en_enriched,
            "termsZh": terms_zh_enriched,
            "includeDerivatives": parsed.include_derivatives,
        }
    except Exception as e:
        logger.error(f"Unified analyze call failed: {str(e)}")
        raise


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
