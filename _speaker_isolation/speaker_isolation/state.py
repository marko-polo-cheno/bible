import threading

from speaker_isolation.models import RecorderPhase


class RecorderState:
    def __init__(self, phase: RecorderPhase = RecorderPhase.COLD_START) -> None:
        self._lock = threading.Lock()
        self._phase = phase
        self._recording = False

    @property
    def phase(self) -> RecorderPhase:
        with self._lock:
            return self._phase

    def set_phase(self, phase: RecorderPhase) -> None:
        with self._lock:
            self._phase = phase

    @property
    def recording(self) -> bool:
        with self._lock:
            return self._recording

    def set_recording(self, value: bool) -> None:
        with self._lock:
            self._recording = value
