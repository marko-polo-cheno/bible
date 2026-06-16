from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSIONS_DIR = PACKAGE_ROOT / "sessions"

SAMPLE_RATE = 16_000
CHANNELS = 1
FRAME_MS = 25
CROSSFADE_MS = 8

# --- Turn segmentation (energy VAD + gap-based boundary detection) ---
# A frame counts as speech when its RMS exceeds the tracked noise floor by this
# factor (and clears a small absolute floor so dead silence never trips).
VAD_SPEECH_FACTOR = 3.0
VAD_ABS_FLOOR = 1e-4
# How fast the noise-floor estimate adapts on non-speech frames (EMA alpha).
VAD_NOISE_ALPHA = 0.05

# Minimum speech to count as a real turn (drops coughs/clicks).
MIN_SPEECH_MS = 250
# Silence shorter than this is an intra-turn pause and does NOT split a turn.
# Silence reaching this length is a speaker hand-off: the turn closes and is
# emitted this many ms after the speaker actually stopped. This is the
# "section the sentence within a second or two" knob.
TURN_GAP_MS = 700

# Which speaker takes the first turn. ABAB strict alternation labels the rest.
FIRST_SPEAKER = "A"
