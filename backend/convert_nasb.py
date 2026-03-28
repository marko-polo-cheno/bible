#!/usr/bin/env python3
"""Convert NASB source (numbered books with Strong's tags) to hierarchical JSON matching NKJV.json format."""

import json
import re
import os

INPUT_PATH = os.path.expanduser("~/Downloads/nasb.txt")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "data", "NASB.json")

# Book number -> (testament, group, name)
BOOK_MAP = {
    # Old Testament - Pentateuch
    1: ("old", "Pentateuch", "Genesis"),
    2: ("old", "Pentateuch", "Exodus"),
    3: ("old", "Pentateuch", "Leviticus"),
    4: ("old", "Pentateuch", "Numbers"),
    5: ("old", "Pentateuch", "Deuteronomy"),
    # Old Testament - Historical Books
    6: ("old", "Historical Books", "Joshua"),
    7: ("old", "Historical Books", "Judges"),
    8: ("old", "Historical Books", "Ruth"),
    9: ("old", "Historical Books", "1 Samuel"),
    10: ("old", "Historical Books", "2 Samuel"),
    11: ("old", "Historical Books", "1 Kings"),
    12: ("old", "Historical Books", "2 Kings"),
    13: ("old", "Historical Books", "1 Chronicles"),
    14: ("old", "Historical Books", "2 Chronicles"),
    15: ("old", "Historical Books", "Ezra"),
    16: ("old", "Historical Books", "Nehemiah"),
    17: ("old", "Historical Books", "Esther"),
    # Old Testament - Wisdom Books
    18: ("old", "Wisdom Books", "Job"),
    19: ("old", "Wisdom Books", "Psalms"),
    20: ("old", "Wisdom Books", "Proverbs"),
    21: ("old", "Wisdom Books", "Ecclesiastes"),
    22: ("old", "Wisdom Books", "Song of Solomon"),
    # Old Testament - Major Prophets
    23: ("old", "Major Prophets", "Isaiah"),
    24: ("old", "Major Prophets", "Jeremiah"),
    25: ("old", "Major Prophets", "Lamentations"),
    26: ("old", "Major Prophets", "Ezekiel"),
    27: ("old", "Major Prophets", "Daniel"),
    # Old Testament - Minor Prophets
    28: ("old", "Minor Prophets", "Hosea"),
    29: ("old", "Minor Prophets", "Joel"),
    30: ("old", "Minor Prophets", "Amos"),
    31: ("old", "Minor Prophets", "Obadiah"),
    32: ("old", "Minor Prophets", "Jonah"),
    33: ("old", "Minor Prophets", "Micah"),
    34: ("old", "Minor Prophets", "Nahum"),
    35: ("old", "Minor Prophets", "Habakkuk"),
    36: ("old", "Minor Prophets", "Zephaniah"),
    37: ("old", "Minor Prophets", "Haggai"),
    38: ("old", "Minor Prophets", "Zechariah"),
    39: ("old", "Minor Prophets", "Malachi"),
    # New Testament - Gospels
    40: ("new", "Gospels", "Matthew"),
    41: ("new", "Gospels", "Mark"),
    42: ("new", "Gospels", "Luke"),
    43: ("new", "Gospels", "John"),
    # New Testament - History
    44: ("new", "History", "Acts"),
    # New Testament - Pauline Epistles
    45: ("new", "Pauline Epistles", "Romans"),
    46: ("new", "Pauline Epistles", "1 Corinthians"),
    47: ("new", "Pauline Epistles", "2 Corinthians"),
    48: ("new", "Pauline Epistles", "Galatians"),
    49: ("new", "Pauline Epistles", "Ephesians"),
    50: ("new", "Pauline Epistles", "Philippians"),
    51: ("new", "Pauline Epistles", "Colossians"),
    52: ("new", "Pauline Epistles", "1 Thessalonians"),
    53: ("new", "Pauline Epistles", "2 Thessalonians"),
    54: ("new", "Pauline Epistles", "1 Timothy"),
    55: ("new", "Pauline Epistles", "2 Timothy"),
    56: ("new", "Pauline Epistles", "Titus"),
    57: ("new", "Pauline Epistles", "Philemon"),
    # New Testament - General Epistles
    58: ("new", "General Epistles", "Hebrews"),
    59: ("new", "General Epistles", "James"),
    60: ("new", "General Epistles", "1 Peter"),
    61: ("new", "General Epistles", "2 Peter"),
    62: ("new", "General Epistles", "1 John"),
    63: ("new", "General Epistles", "2 John"),
    64: ("new", "General Epistles", "3 John"),
    65: ("new", "General Epistles", "Jude"),
    # New Testament - Prophecy
    66: ("new", "Prophecy", "Revelation"),
}


def strip_tags(text: str) -> str:
    """Remove Strong's numbers, SC tags, italic tags, PO tags, and clean up whitespace."""
    # Remove <SC>...</SC> tags but keep inner text
    text = re.sub(r"<SC>(.*?)</SC>", r"\1", text)
    # Remove <i>...</i> tags but keep inner text
    text = re.sub(r"<i>(.*?)</i>", r"\1", text)
    # Remove all remaining tags (Strong's numbers like <WH1234>, <WG5678>, <PO>, etc.)
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple spaces into one
    text = re.sub(r"  +", " ", text)
    return text.strip()


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    content = raw["content"]
    output: dict = {"old": {}, "new": {}}

    for book_num_str, chapters in content.items():
        book_num = int(book_num_str)
        if book_num not in BOOK_MAP:
            print(f"Warning: unknown book number {book_num}, skipping")
            continue

        testament, group, book_name = BOOK_MAP[book_num]

        if group not in output[testament]:
            output[testament][group] = {}

        book_data: dict = {}
        for chapter_num, verses in chapters.items():
            chapter_data: dict = {}
            for verse_num, text in verses.items():
                chapter_data[verse_num] = strip_tags(text)
            book_data[chapter_num] = chapter_data

        output[testament][group][book_name] = book_data

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    # Quick stats
    total_verses = sum(
        len(verses)
        for chapters in content.values()
        for verses in chapters.values()
    )
    print(f"Converted {len(content)} books, {total_verses} total verses")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
