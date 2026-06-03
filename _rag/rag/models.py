from pydantic import BaseModel, Field


class CorpusDoc(BaseModel):
    filename: str
    content: str
    link: str = ""
    category: list[str] = Field(default_factory=list)
    lang_id: int = 1
    item_id: int | None = None
    transcript_content: str = ""


class ChunkRecord(BaseModel):
    chunk_id: int
    filename: str
    link: str = ""
    category: list[str] = Field(default_factory=list)
    lang_id: int = 1
    item_id: int | None = None
    chunk_index: int = 0
    text: str = ""


class RetrieveHit(BaseModel):
    score: float
    filename: str
    link: str = ""
    lang_id: int = 1
    category: list[str] = Field(default_factory=list)
    snippet: str = ""
    chunk_index: int = 0


class RetrieveResult(BaseModel):
    query: str
    results: list[RetrieveHit] = Field(default_factory=list)
