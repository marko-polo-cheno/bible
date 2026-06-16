from pathlib import Path

import numpy as np
import soundfile as sf

from speaker_isolation.config import CROSSFADE_MS, SAMPLE_RATE
from speaker_isolation.models import TimeSpan


def _crossfade_len_samples() -> int:
    return max(1, int(SAMPLE_RATE * CROSSFADE_MS / 1000))


def stitch_a_only(
    master_wav: Path,
    a_spans: list[TimeSpan],
    output_path: Path,
) -> None:
    if not a_spans:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, np.zeros(0, dtype=np.float32), SAMPLE_RATE)
        return

    data, sr = sf.read(master_wav, dtype="float32", always_2d=False)
    if sr != SAMPLE_RATE:
        raise ValueError(f"expected sample rate {SAMPLE_RATE}, got {sr}")

    fade = _crossfade_len_samples()
    chunks: list[np.ndarray] = []

    for span in sorted(a_spans, key=lambda s: s.start_sec):
        start = int(span.start_sec * sr)
        end = int(span.end_sec * sr)
        start = max(0, min(start, len(data)))
        end = max(start, min(end, len(data)))
        piece = data[start:end]
        if piece.size == 0:
            continue
        chunks.append(piece)

    if not chunks:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, np.zeros(0, dtype=np.float32), SAMPLE_RATE)
        return

    out = chunks[0]
    for nxt in chunks[1:]:
        if fade >= len(out) or fade >= len(nxt):
            out = np.concatenate([out, nxt])
            continue
        fade_out = np.linspace(1.0, 0.0, fade, dtype=np.float32)
        fade_in = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        blended = out[-fade:] * fade_out + nxt[:fade] * fade_in
        out = np.concatenate([out[:-fade], blended, nxt[fade:]])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, out, SAMPLE_RATE)
