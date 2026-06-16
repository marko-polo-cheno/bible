"""Gap-based turn segmentation.

Feeds fixed-size frames through an energy VAD and emits a *closed turn* once a
speaker hand-off gap is observed. A turn closes ``TURN_GAP_MS`` after the
speaker actually stops, so the just-finished sentence is sectioned "within a
second or two" of the switch. Short intra-turn pauses do not split a turn.

Labeling is pure ABAB alternation anchored by ``FIRST_SPEAKER`` — given strict
turn-taking, no acoustic model is needed to tell A from B.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from speaker_isolation.config import (
    FIRST_SPEAKER,
    FRAME_MS,
    MIN_SPEECH_MS,
    SAMPLE_RATE,
    TURN_GAP_MS,
)
from speaker_isolation.models import AnnotatedSpan, LabelSource, SpeakerLabel
from speaker_isolation.vad import EnergyVad

TurnCallback = Callable[[AnnotatedSpan], None]


class TurnSegmenter:
    def __init__(
        self,
        on_turn: TurnCallback,
        vad: EnergyVad | None = None,
        frame_ms: int = FRAME_MS,
        min_speech_ms: int = MIN_SPEECH_MS,
        turn_gap_ms: int = TURN_GAP_MS,
        first_speaker: str = FIRST_SPEAKER,
    ) -> None:
        self._on_turn = on_turn
        self._vad = vad or EnergyVad()
        self._frame_sec = frame_ms / 1000.0
        self._min_speech_frames = max(1, round(min_speech_ms / frame_ms))
        self._gap_frames = max(1, round(turn_gap_ms / frame_ms))

        self._frame_idx = 0  # frames seen so far → drives the clock
        self._in_speech = False
        self._speech_start_frame: int | None = None
        self._speech_end_frame: int | None = None  # last speech frame + 1
        self._speech_frame_count = 0
        self._trailing_silence = 0

        self._turn_index = 0
        self._first_is_a = first_speaker.upper() == "A"

    def _label_for(self, turn_index: int) -> SpeakerLabel:
        is_a = (turn_index % 2 == 0) == self._first_is_a
        return SpeakerLabel.A if is_a else SpeakerLabel.B

    def push_frame(self, frame: np.ndarray) -> None:
        speech = self._vad.is_speech(frame)
        idx = self._frame_idx
        self._frame_idx += 1

        if speech:
            if not self._in_speech:
                self._in_speech = True
                self._speech_start_frame = idx
                self._speech_frame_count = 0
            self._speech_frame_count += 1
            self._speech_end_frame = idx + 1
            self._trailing_silence = 0
            return

        # silence frame
        if not self._in_speech:
            return
        self._trailing_silence += 1
        if self._trailing_silence >= self._gap_frames:
            self._close_turn()

    def _close_turn(self) -> None:
        start = self._speech_start_frame
        end = self._speech_end_frame
        long_enough = self._speech_frame_count >= self._min_speech_frames
        # Reset speech state regardless; only emit real turns.
        self._in_speech = False
        self._speech_start_frame = None
        self._speech_end_frame = None
        self._speech_frame_count = 0
        self._trailing_silence = 0

        if not long_enough or start is None or end is None:
            return

        span = AnnotatedSpan(
            start_sec=start * self._frame_sec,
            end_sec=end * self._frame_sec,
            label=self._label_for(self._turn_index),
            source=LabelSource.PRIOR,
            confidence=1.0,
        )
        self._turn_index += 1
        self._on_turn(span)

    def flush(self) -> None:
        """Close any open turn at end of stream (no trailing gap needed)."""
        if self._in_speech:
            self._close_turn()


def segment_array(
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    frame_ms: int = FRAME_MS,
    **kwargs,
) -> list[AnnotatedSpan]:
    """Run the segmenter over a whole mono array. Convenience for files/tests."""
    turns: list[AnnotatedSpan] = []
    seg = TurnSegmenter(on_turn=turns.append, frame_ms=frame_ms, **kwargs)
    frame_len = max(1, round(sample_rate * frame_ms / 1000))
    for start in range(0, len(audio), frame_len):
        seg.push_frame(audio[start : start + frame_len])
    seg.flush()
    return turns
