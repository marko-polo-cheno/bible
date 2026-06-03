import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .models import CorpusDoc

logger = logging.getLogger(__name__)


def _extract_link_params(link: str) -> tuple[int | None, int | None]:
    try:
        qs = parse_qs(urlparse(link).query)
        lang_id = None
        item_id = None
        for key in ("LangID", "langid", "langID"):
            vals = qs.get(key)
            if vals:
                lang_id = int(vals[0])
                break
        for key in ("ItemID", "itemid", "itemID"):
            vals = qs.get(key)
            if vals:
                item_id = int(vals[0])
                break
        return lang_id, item_id
    except (ValueError, IndexError):
        return None, None


def load_corpus(paths: list[Path], max_docs: int | None = None) -> list[CorpusDoc]:
    docs: list[CorpusDoc] = []
    for path in paths:
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    if max_docs is not None and len(docs) >= max_docs:
                        return docs
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    link = row.get("link", "")
                    lang_id, item_id = _extract_link_params(link)
                    if lang_id is None:
                        lang_id = 1 if path.name.endswith("_en.jsonl") else 2
                    docs.append(
                        CorpusDoc(
                            filename=row.get("filename", ""),
                            content=row.get("content", ""),
                            link=link,
                            category=row.get("category", []),
                            lang_id=lang_id,
                            item_id=item_id,
                            transcript_content=row.get("transcript_content", ""),
                        )
                    )
        except Exception as e:
            logger.error("Failed to load corpus from %s: %s", path, e)
            raise
    return docs


def doc_embed_text(doc: CorpusDoc) -> str:
    parts = [doc.filename, doc.content]
    if doc.transcript_content:
        parts.append(doc.transcript_content)
    return "\n\n".join(p for p in parts if p)
