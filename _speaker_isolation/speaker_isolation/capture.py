from pathlib import Path

import numpy as np
import soundfile as sf

from speaker_isolation.config import CHANNELS, SAMPLE_RATE


class MasterWavWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = sf.SoundFile(
            path,
            mode="w",
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            subtype="PCM_16",
        )

    def write_frames(self, frames: np.ndarray) -> None:
        self._file.write(frames)

    def close(self) -> None:
        self._file.close()
