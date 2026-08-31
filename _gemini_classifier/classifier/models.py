from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

FormType = Literal["PUBLICATION", "TESTIMONY", "SERMON"]


class DocClassification(BaseModel):
    """Schema the model is constrained to return."""

    form_type: FormType
    primary_label: str
    labels: List[str] = Field(default_factory=list)


class CorpusDoc(BaseModel):
    lang: str
    lang_id: int
    line_no: int
    item_id: Optional[int] = None
    filename: str = ""
    link: str = ""
    category: List[str] = Field(default_factory=list)
    content: str = ""
    transcript_content: str = ""


class LabelFlag(BaseModel):
    node: str
    reason: str


class LabelRecord(BaseModel):
    item_id: Optional[int] = None
    lang_id: int
    filename: str = ""
    link: str = ""
    category: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    primary_label: str = ""
    form_type: str = ""
    flags: List[LabelFlag] = Field(default_factory=list)
    model: str = ""
    prompt_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0


class RunStatus(BaseModel):
    lang: str
    tag: str
    model: str
    input_path: str
    artifact_path: str
    total: int = 0
    completed: int = 0
    pending: int = 0
    failed: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cache_name: str = ""
    updated_at: str = ""


class CacheState(BaseModel):
    name: str
    model: str
    prompt_sha256: str
    expires_at: float
    token_count: int = 0
