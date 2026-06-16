import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from speaker_isolation.config import DEFAULT_SESSIONS_DIR, SAMPLE_RATE
from speaker_isolation.models import AnnotatedSpan, SpeakerLabel, TimeSpan
from speaker_isolation.segmenter import TurnSegmenter, segment_array
from speaker_isolation.stitch import stitch_a_only
from speaker_isolation.synth import synth_abab


def _print_turns(turns: list[AnnotatedSpan]) -> None:
    for i, t in enumerate(turns):
        print(
            f"  turn {i:2d}  {t.label.value}  "
            f"{t.start_sec:6.2f}s → {t.end_sec:6.2f}s  "
            f"({t.duration_sec():.2f}s)"
        )


def _a_spans(turns: list[AnnotatedSpan]) -> list[TimeSpan]:
    return [
        TimeSpan(start_sec=t.start_sec, end_sec=t.end_sec)
        for t in turns
        if t.label == SpeakerLabel.A
    ]


def cmd_selftest() -> int:
    """Synthesize ABAB audio, segment it, and check boundaries. No mic needed."""
    audio, truth = synth_abab()
    turns = segment_array(audio)

    print(f"ground truth: {len(truth)} turns")
    for s, e, lab in truth:
        print(f"  {lab}  {s:6.2f}s → {e:6.2f}s")
    print(f"detected:     {len(turns)} turns")
    _print_turns(turns)

    ok = len(turns) == len(truth)
    tol = 0.20  # 200 ms boundary tolerance
    if ok:
        for det, (s, e, lab) in zip(turns, truth):
            if det.label.value != lab:
                ok = False
                print(f"  FAIL label: got {det.label.value}, want {lab}")
            if abs(det.start_sec - s) > tol or abs(det.end_sec - e) > tol:
                ok = False
                print(
                    f"  FAIL boundary: got {det.start_sec:.2f}-{det.end_sec:.2f}, "
                    f"want {s:.2f}-{e:.2f}"
                )
    else:
        print(f"  FAIL count: detected {len(turns)}, expected {len(truth)}")

    print("\nSELFTEST PASS" if ok else "\nSELFTEST FAIL")
    return 0 if ok else 1


def cmd_segment(wav_path: Path, session_dir: Path) -> int:
    """Segment an existing WAV into turns, label ABAB, write A-only output."""
    audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != SAMPLE_RATE:
        print(
            f"warning: {wav_path} is {sr} Hz; config expects {SAMPLE_RATE} Hz. "
            "Boundary timings assume the configured rate.",
            file=sys.stderr,
        )

    turns = segment_array(audio, sample_rate=sr)
    print(f"{len(turns)} turns detected:")
    _print_turns(turns)

    session_dir.mkdir(parents=True, exist_ok=True)
    out = session_dir / "output_A_only.wav"
    # stitch reads from the source WAV directly using span timings
    stitch_a_only(wav_path, _a_spans(turns), out)
    print(f"\nwrote {out}")
    return 0


def cmd_record(session_dir: Path) -> int:
    """Live capture from the mic. Ctrl+C stops and writes the A-only output."""
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - depends on PortAudio
        print(f"sounddevice unavailable: {exc}", file=sys.stderr)
        return 2

    from speaker_isolation.capture import MasterWavWriter
    from speaker_isolation.config import FRAME_MS

    session_dir.mkdir(parents=True, exist_ok=True)
    master = session_dir / "master.wav"
    writer = MasterWavWriter(master)
    turns: list[AnnotatedSpan] = []

    def on_turn(t: AnnotatedSpan) -> None:
        turns.append(t)
        print(
            f"  [{t.label.value}] {t.start_sec:6.2f}s → {t.end_sec:6.2f}s "
            f"({t.duration_sec():.2f}s)",
            flush=True,
        )

    seg = TurnSegmenter(on_turn=on_turn)
    frame_len = max(1, round(SAMPLE_RATE * FRAME_MS / 1000))

    print(f"recording → {master}\nspeak in ABAB turns; Ctrl+C to stop.\n")
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=frame_len,
        ) as stream:
            while True:
                frames, _ = stream.read(frame_len)
                mono = frames[:, 0]
                writer.write_frames(mono)
                seg.push_frame(mono)
    except KeyboardInterrupt:
        print("\nstopping…")
    finally:
        seg.flush()
        writer.close()

    out = session_dir / "output_A_only.wav"
    stitch_a_only(master, _a_spans(turns), out)
    print(f"{len(turns)} turns; wrote {out}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Adaptive speaker-isolation recorder (see IMPLEMENTATION_PLAN.md)",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=DEFAULT_SESSIONS_DIR,
        help="Directory for master WAV, labels, and A-only outputs",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Session folder name (default: UTC timestamp)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("plan", help="Print path to IMPLEMENTATION_PLAN.md")
    sub.add_parser("selftest", help="Run synthetic ABAB segmentation check (no mic)")

    seg = sub.add_parser("segment", help="Segment a WAV file → A-only output")
    seg.add_argument("wav", type=Path, help="Input mono WAV")

    sub.add_parser("record", help="Live mic capture → A-only output on Ctrl+C")

    args = parser.parse_args()

    if args.command == "plan":
        plan = Path(__file__).resolve().parent.parent / "IMPLEMENTATION_PLAN.md"
        print(plan)
        return

    if args.command == "selftest":
        sys.exit(cmd_selftest())

    session_id = args.session_id or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    session_dir = args.sessions_dir / session_id

    if args.command == "segment":
        sys.exit(cmd_segment(args.wav, session_dir))
    if args.command == "record":
        sys.exit(cmd_record(session_dir))


if __name__ == "__main__":
    main()
