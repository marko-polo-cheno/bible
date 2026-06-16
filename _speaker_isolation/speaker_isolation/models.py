from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class RecorderPhase(str, Enum):
    ENROLL = "ENROLL"
    COLD_START = "COLD_START"
    SEMI_SUPERVISED = "SEMI_SUPERVISED"
    LIVE = "LIVE"
    FALLBACK_LEARN = "FALLBACK_LEARN"
    FINALIZE = "FINALIZE"


class TimeSpan(BaseModel):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)

    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


class SpeakerLabel(str, Enum):
    A = "A"
    B = "B"


class LabelSource(str, Enum):
    HUMAN = "human"
    LID = "lid"
    VOICE = "voice"
    PRIOR = "prior"


class AnnotatedSpan(TimeSpan):
    label: SpeakerLabel
    source: LabelSource = LabelSource.HUMAN
    confidence: float | None = None


class SnippetRecord(BaseModel):
    start_sec: float
    end_sec: float
    provisional_label: SpeakerLabel
    confidence: float
    source: LabelSource
    human_override: SpeakerLabel | None = None
