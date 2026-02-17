from typing import List, Union
from pydantic import BaseModel


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
        secondary_passages: List of Verse or VerseRange objects.
    """
    passages: List[Union[Verse, VerseRange]]
    secondary_passages: List[Union[Verse, VerseRange]]


class TestimoniesSearchQuery(BaseModel):
    terms: List[str]
