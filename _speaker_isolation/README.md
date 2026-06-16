# Adaptive Speaker-Isolation Recorder

Live capture for strict turn-taking, two-speaker sessions (A = main, B = translator/echo): human highlight while streaming, optional auto A/B labeling, and an A-only output after stop.

Full design: [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).

## Milestones

| # | Scope |
|---|--------|
| 1 | Record → master WAV → hold-to-mark A spans → stitch `output_A_only.wav` (no ML) |
| 2 | VAD / utterance segmentation |
| 3 | LID (two enrolled languages) |
| 4 | Enrollment + persisted profiles |
| 5 | Voice tiebreakers (F0 + embeddings) |
| 6 | Turn/gap detection + ABAB pairing |
| 7 | Global correction pass + sidecar JSON |
| 8 | Drift / IoU fallback + UI polish |

## Layout

```
_speaker_isolation/
  IMPLEMENTATION_PLAN.md
  speaker_isolation/          # Python package
    __main__.py               # CLI entry (milestones land here)
    config.py                 # sample rate, paths, thresholds
    models.py                 # Pydantic types (spans, snippets, profiles)
    state.py                  # Recorder state machine
    capture.py                # sounddevice callback + master WAV
    labels.py                 # human + model label store
    stitch.py                 # crossfade A-only assembly
```

Later modules (not scaffolded yet): `segmentation.py`, `enrollment.py`, `classify.py`, `finalize.py`, `iou.py`.

## Install (milestone 1 deps)

```bash
cd _speaker_isolation
poetry install
```

## Run

```bash
poetry run speaker-isolation --help
```

Artifacts default under `_speaker_isolation/sessions/` (gitignored): master WAV, labels, profiles, outputs.
