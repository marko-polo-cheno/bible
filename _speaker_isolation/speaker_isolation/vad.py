"""Energy-based voice-activity detection (numpy only, streaming).

Deliberately dependency-free: no webrtcvad/torch. Good enough to find the
silence gaps between strict ABAB turns, which is all turn segmentation needs.
Swap in silero/webrtcvad later behind the same `is_speech` interface.
"""

from __future__ import annotations

import numpy as np

from speaker_isolation.config import (
    VAD_ABS_FLOOR,
    VAD_NOISE_ALPHA,
    VAD_SPEECH_FACTOR,
)


def frame_rms(frame: np.ndarray) -> float:
    if frame.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))


class EnergyVad:
    """Per-frame speech/silence decision with an online noise-floor estimate.

    The noise floor only adapts on frames judged non-speech, so sustained
    speech can't drag the threshold up and silence it.
    """

    def __init__(
        self,
        speech_factor: float = VAD_SPEECH_FACTOR,
        abs_floor: float = VAD_ABS_FLOOR,
        noise_alpha: float = VAD_NOISE_ALPHA,
    ) -> None:
        self.speech_factor = speech_factor
        self.abs_floor = abs_floor
        self.noise_alpha = noise_alpha
        self._noise: float | None = None

    @property
    def noise_floor(self) -> float:
        return self._noise if self._noise is not None else self.abs_floor

    def is_speech(self, frame: np.ndarray) -> bool:
        rms = frame_rms(frame)
        if self._noise is None:
            # Seed the floor from the first frame (assume it's roughly ambient).
            self._noise = max(rms, self.abs_floor)
            return rms > max(self.abs_floor, self._noise * self.speech_factor)

        threshold = max(self.abs_floor, self._noise * self.speech_factor)
        speech = rms > threshold
        if not speech:
            self._noise = (
                1 - self.noise_alpha
            ) * self._noise + self.noise_alpha * rms
        return speech
