"""
Data processing pipeline:
1. Build CSV category mapping (NodeText -> ItemIDs) and best-match to HTML category tree
2. Split testimonies.jsonl by language + update categories
3. Ingest SRT transcripts into language JSONL files
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Add parent dir to path so we can import categories
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from categories import LEAF_INDEX_EN, LEAF_INDEX_ZH

BACKEND_DIR = Path(__file__).resolve().parent.parent
RESEARCH_DIR = BACKEND_DIR.parent.parent / "research"
CSV_PATH = RESEARCH_DIR / "PublicationCategory - Sheet1.csv"
TRANSCRIPTS_DIR = RESEARCH_DIR / "trascripts"
JSONL_PATH = BACKEND_DIR / "testimonies.jsonl"
JSONL_EN_PATH = BACKEND_DIR / "testimonies_en.jsonl"
JSONL_ZH_PATH = BACKEND_DIR / "testimonies_zh.jsonl"


def extract_link_params(link: str) -> tuple[int | None, int | None]:
    """Extract LangID and ItemID from a testimony link URL."""
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


# ─── Step 1: CSV category mapping ────────────────────────────────────────────

def map_csv_path_to_tree(csv_path: str, leaf_index: dict[str, list[str]]) -> str | None:
    """Map a single CSV category path to an HTML tree value path.

    Strategy:
    1. Extract leaf name (last segment)
    2. If unique match in index -> use it
    3. If ambiguous -> use parent segments from CSV to disambiguate
    4. If no match -> return None
    """
    segments = [s.strip() for s in csv_path.split("/")]
    leaf = segments[-1]

    # Strip any trailing counts like " (0)"
    leaf = re.sub(r'\s*\(\d+\)$', '', leaf).strip()

    matches = leaf_index.get(leaf, [])
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    # Ambiguous: use CSV parent segments to disambiguate
    # For each candidate, check if any CSV ancestor appears in the candidate path
    csv_ancestors = [re.sub(r'\s*\(\d+\)$', '', s).strip() for s in segments[:-1]]

    best_match = None
    best_score = -1
    for candidate in matches:
        candidate_parts = candidate.split("/")
        score = 0
        for ancestor in csv_ancestors:
            if ancestor in candidate_parts:
                score += 1
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match


def build_item_category_mapping() -> dict[int, list[str]]:
    """Parse CSV and build {ItemID -> [HTML tree category paths]} mapping."""
    print(f"Reading CSV: {CSV_PATH}")

    # First pass: collect all unique individual paths and determine their language
    all_node_texts = defaultdict(list)
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_id = int(row["ItemID"])
            node_text = row["NodeText"].strip()
            all_node_texts[node_text].append(item_id)

    print(f"  {len(all_node_texts)} unique NodeText values")

    # Build mapping: NodeText -> list of matched HTML tree paths
    node_text_to_tree_paths: dict[str, list[str]] = {}
    unmapped_paths: set[str] = set()

    for node_text in all_node_texts:
        # Split NodeText into individual paths (comma-separated)
        individual_paths = [p.strip() for p in node_text.split(", ")]

        # Determine language: if any path starts with CJK chars, it's Chinese
        is_chinese = any(ord(p[0]) > 0x2E7F for p in individual_paths if p)
        leaf_index = LEAF_INDEX_ZH if is_chinese else LEAF_INDEX_EN

        matched = []
        for csv_path in individual_paths:
            tree_path = map_csv_path_to_tree(csv_path, leaf_index)
            if tree_path:
                if tree_path not in matched:
                    matched.append(tree_path)
            else:
                unmapped_paths.add(csv_path)

        node_text_to_tree_paths[node_text] = matched

    print(f"  {len(unmapped_paths)} unmapped CSV paths (By Type/All Articles/etc)")
    if unmapped_paths:
        samples = sorted(unmapped_paths)[:10]
        for s in samples:
            print(f"    - {s}")
        if len(unmapped_paths) > 10:
            print(f"    ... and {len(unmapped_paths) - 10} more")

    # Build final ItemID -> categories mapping
    item_categories: dict[int, list[str]] = {}
    for node_text, item_ids in all_node_texts.items():
        tree_paths = node_text_to_tree_paths[node_text]
        for item_id in item_ids:
            if item_id not in item_categories:
                item_categories[item_id] = []
            for tp in tree_paths:
                if tp not in item_categories[item_id]:
                    item_categories[item_id].append(tp)

    # Stats
    mapped_count = sum(1 for cats in item_categories.values() if cats)
    empty_count = sum(1 for cats in item_categories.values() if not cats)
    print(f"  {len(item_categories)} total ItemIDs in CSV")
    print(f"  {mapped_count} with at least one mapped category")
    print(f"  {empty_count} with no mapped categories (will use Unknown/未分類)")

    return item_categories


# ─── Step 2: Split JSONL by language + update categories ─────────────────────

def split_and_update_jsonl(item_categories: dict[int, list[str]]):
    """Split testimonies.jsonl into en/zh files with updated categories."""
    print(f"\nReading {JSONL_PATH}")

    en_entries = []
    zh_entries = []
    skipped = 0

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                print(f"  WARNING: invalid JSON at line {line_num}, skipping")
                skipped += 1
                continue

            lang_id, item_id = extract_link_params(entry.get("link", ""))

            if lang_id not in (1, 2):
                skipped += 1
                continue

            # Update categories from CSV mapping
            if item_id and item_id in item_categories:
                cats = item_categories[item_id]
                if cats:
                    entry["category"] = cats
                else:
                    entry["category"] = ["Unknown"] if lang_id == 1 else ["未分類"]
            else:
                entry["category"] = ["Unknown"] if lang_id == 1 else ["未分類"]

            if lang_id == 1:
                en_entries.append(entry)
            else:
                zh_entries.append(entry)

    print(f"  EN entries: {len(en_entries)}")
    print(f"  ZH entries: {len(zh_entries)}")
    print(f"  Skipped (no/invalid LangID): {skipped}")

    # Write out
    print(f"Writing {JSONL_EN_PATH}")
    with open(JSONL_EN_PATH, "w", encoding="utf-8") as f:
        for entry in en_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Writing {JSONL_ZH_PATH}")
    with open(JSONL_ZH_PATH, "w", encoding="utf-8") as f:
        for entry in zh_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return en_entries, zh_entries


# ─── Step 3: Ingest SRT transcripts ─────────────────────────────────────────

def parse_srt(filepath: Path) -> str:
    """Parse SRT file, strip timestamps and sequence numbers, return plain text."""
    lines = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines, sequence numbers (pure digits), timestamp lines
            if not line or line.isdigit() or "-->" in line:
                continue
            lines.append(line)
    return " ".join(lines)


def find_srt_files(base_dir: Path) -> list[tuple[int, Path]]:
    """Find all SRT files and extract ItemID from filename."""
    results = []
    for srt_path in sorted(base_dir.rglob("*.srt")):
        stem = srt_path.stem
        try:
            item_id = int(stem)
            results.append((item_id, srt_path))
        except ValueError:
            print(f"  WARNING: non-numeric SRT filename: {srt_path.name}, skipping")
    return results


def ingest_srt_transcripts(
    en_entries: list[dict],
    zh_entries: list[dict],
    item_categories: dict[int, list[str]],
):
    """Ingest SRT files into the language JSONL entries."""
    print("\nIngesting SRT transcripts...")

    # Build ItemID -> entry index for existing entries
    en_by_id: dict[int, dict] = {}
    for entry in en_entries:
        _, item_id = extract_link_params(entry.get("link", ""))
        if item_id:
            en_by_id[item_id] = entry

    zh_by_id: dict[int, dict] = {}
    for entry in zh_entries:
        _, item_id = extract_link_params(entry.get("link", ""))
        if item_id:
            zh_by_id[item_id] = entry

    # Process English SRTs
    en_srt_dir = TRANSCRIPTS_DIR / "en"
    en_srts = find_srt_files(en_srt_dir)
    print(f"  Found {len(en_srts)} English SRT files")

    en_new = 0
    en_updated = 0
    en_skipped = 0
    for item_id, srt_path in en_srts:
        transcript = parse_srt(srt_path)
        if not transcript.strip():
            continue

        if item_id in en_by_id:
            existing = en_by_id[item_id]
            if existing.get("content", "").strip() == transcript.strip():
                en_skipped += 1
            else:
                existing["transcript_content"] = transcript
                en_updated += 1
        else:
            cats = item_categories.get(item_id, [])
            if not cats:
                cats = ["Unknown"]
            entry = {
                "filename": str(item_id),
                "content": transcript,
                "link": f"https://ia.tjc.org/elibrary/ContentDetail.aspx?ItemID={item_id}&LangID=1",
                "category": cats,
            }
            en_entries.append(entry)
            en_by_id[item_id] = entry
            en_new += 1

    print(f"    New: {en_new}, Updated (transcript_content added): {en_updated}, Skipped (identical): {en_skipped}")

    # Process Chinese SRTs
    zh_srt_dir = TRANSCRIPTS_DIR / "zh"
    zh_srts = find_srt_files(zh_srt_dir)
    print(f"  Found {len(zh_srts)} Chinese SRT files")

    zh_new = 0
    zh_updated = 0
    zh_skipped = 0
    for item_id, srt_path in zh_srts:
        transcript = parse_srt(srt_path)
        if not transcript.strip():
            continue

        if item_id in zh_by_id:
            existing = zh_by_id[item_id]
            if existing.get("content", "").strip() == transcript.strip():
                zh_skipped += 1
            else:
                existing["transcript_content"] = transcript
                zh_updated += 1
        else:
            cats = item_categories.get(item_id, [])
            if not cats:
                cats = ["未分類"]
            entry = {
                "filename": str(item_id),
                "content": transcript,
                "link": f"https://ia.tjc.org/elibrary/ContentDetail.aspx?ItemID={item_id}&LangID=2",
                "category": cats,
            }
            zh_entries.append(entry)
            zh_by_id[item_id] = entry
            zh_new += 1

    print(f"    New: {zh_new}, Updated (transcript_content added): {zh_updated}, Skipped (identical): {zh_skipped}")

    # Rewrite JSONL files with SRT data included
    print(f"\nRewriting {JSONL_EN_PATH} ({len(en_entries)} entries)")
    with open(JSONL_EN_PATH, "w", encoding="utf-8") as f:
        for entry in en_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Rewriting {JSONL_ZH_PATH} ({len(zh_entries)} entries)")
    with open(JSONL_ZH_PATH, "w", encoding="utf-8") as f:
        for entry in zh_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Step 1: Building CSV category mapping")
    print("=" * 60)
    item_categories = build_item_category_mapping()

    print("\n" + "=" * 60)
    print("Step 2: Splitting JSONL by language + updating categories")
    print("=" * 60)
    en_entries, zh_entries = split_and_update_jsonl(item_categories)

    print("\n" + "=" * 60)
    print("Step 3: Ingesting SRT transcripts")
    print("=" * 60)
    ingest_srt_transcripts(en_entries, zh_entries, item_categories)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
