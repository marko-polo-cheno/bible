import threading

from speaker_isolation.models import AnnotatedSpan, SpeakerLabel, TimeSpan


class LabelStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._human_a_spans: list[TimeSpan] = []
        self._annotated: list[AnnotatedSpan] = []

    def add_human_a_span(self, span: TimeSpan) -> None:
        with self._lock:
            self._human_a_spans.append(span)

    def human_a_spans(self) -> list[TimeSpan]:
        with self._lock:
            return list(self._human_a_spans)

    def add_annotated(self, item: AnnotatedSpan) -> None:
        with self._lock:
            self._annotated.append(item)

    def annotated(self) -> list[AnnotatedSpan]:
        with self._lock:
            return list(self._annotated)

    def enough_per_class(self, k: int) -> bool:
        with self._lock:
            a_count = sum(1 for x in self._annotated if x.label == SpeakerLabel.A)
            b_count = sum(1 for x in self._annotated if x.label == SpeakerLabel.B)
            return a_count >= k and b_count >= k
