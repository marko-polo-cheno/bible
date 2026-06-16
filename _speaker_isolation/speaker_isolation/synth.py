"""Synthesize ABAB test audio with known turn boundaries.

Used by the `selftest` command so the segmenter can be verified end-to-end
without a microphone or real recordings.
"""

from __future__ import annotations

import numpy as np

from speaker_isolation.config import SAMPLE_RATE


def _tone(freq: float, dur_sec: float, sr: int, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(dur_sec * sr)) / sr
    # Add a tiny bit of vibrato so it reads as voice-like, not a pure sine.
    sig = np.sin(2 * np.pi * freq * t + 0.5 * np.sin(2 * np.pi * 5 * t))
    return (amp * sig).astype(np.float32)


def _silence(dur_sec: float, sr: int, noise: float = 1e-4) -> np.ndarray:
    n = int(dur_sec * sr)
    return (noise * np.random.randn(n)).astype(np.float32)


def synth_abab(
    sr: int = SAMPLE_RATE,
    seed: int = 0,
) -> tuple[np.ndarray, list[tuple[float, float, str]]]:
    """Return (audio, ground_truth_turns).

    Each turn is (start_sec, end_sec, label). A speaks ~male F0, B ~female,
    with a short intra-turn pause inside one turn to prove it doesn't split,
    and longer hand-off gaps between turns that should split.
    """
    rng = np.random.default_rng(seed)
    np.random.seed(seed)

    # (speaker, freq, [sub-durations within the turn], gap_after)
    plan = [
        ("A", 120.0, [1.2], 0.8),
        ("B", 220.0, [1.0], 0.8),
        # A turn with an internal short pause (0.3s) — must stay ONE turn.
        ("A", 120.0, [0.7, 0.6], 0.8),
        ("B", 220.0, [1.1], 0.8),
        ("A", 120.0, [0.9], 0.0),
    ]
    intra_pause = 0.3

    parts: list[np.ndarray] = []
    truth: list[tuple[float, float, str]] = []
    clock = 0.0
    # Lead-in silence so the noise floor seeds on ambient, not speech.
    lead = _silence(0.5, sr)
    parts.append(lead)
    clock += len(lead) / sr

    for speaker, freq, durs, gap_after in plan:
        turn_start = clock
        for i, d in enumerate(durs):
            tone = _tone(freq + rng.normal(0, 3), d, sr)
            parts.append(tone)
            clock += len(tone) / sr
            if i < len(durs) - 1:
                pause = _silence(intra_pause, sr)
                parts.append(pause)
                clock += len(pause) / sr
        truth.append((turn_start, clock, speaker))
        if gap_after > 0:
            gap = _silence(gap_after, sr)
            parts.append(gap)
            clock += len(gap) / sr

    audio = np.concatenate(parts)
    return audio, truth
