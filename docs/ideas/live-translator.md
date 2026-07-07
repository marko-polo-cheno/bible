# Live Translator

> Real-time sermon and service translation — hear the Word in your own language, as it's spoken.

## Idea

A phone-first web app that listens to a live sermon (Mandarin ⇄ English first) and streams
a translated transcript — and optionally synthesized audio — to every listener's own device.
Members open `almondsandolives.ca`, tap **Live Translator**, join the room for their church,
and read along in their language. No apps to install, no AV equipment beyond the speaker's mic.

## Why this, why us

- Bilingual congregations (TJC especially) constantly juggle consecutive interpretation,
  which doubles service length and halves flow. Live translation gives the interpreter a
  safety net and gives latecomers/visitors instant access.
- We already have domain vocabulary assets: the Pinyin/Chinese/NKJV parallel Bible and the
  eLibrary corpus. Sermon translation quality jumps when the model can ground Bible quotes
  to canonical translations instead of re-translating them ("John 3:16" should render as the
  actual 和合本 text, not a paraphrase).

## Signature feature: verse-lock

When the speaker quotes scripture, we detect the reference or the quoted text (fuzzy match
against our verse index) and render the *canonical* verse in the listener's translation,
styled as a verse card — tappable to open in the Bible app. This is the moat: generic
translators garble scripture; ours snaps to it.

## Experience

1. **Speaker side**: one phone/laptop on the pulpit. Big "Go Live" button, room code, mic meter.
2. **Listener side**: join by code or QR on the bulletin. Choose language + text size.
   Transcript streams like subtitles; verse cards snap in; optional TTS audio via earbuds.
3. **Afterwards**: transcript is saved to the room (opt-in), searchable, and can be published
   as sermon notes with all quoted verses linked.

## Plan

- **Phase 1 — transcript relay (MVP)**: browser mic → streaming STT → translation →
  WebSocket fan-out to listeners. Text only. One room. Mandarin→English and English→Mandarin.
- **Phase 2 — verse-lock**: reference detection (regex + fuzzy match on the verse corpus)
  and canonical rendering; tap-through to the Bible app.
- **Phase 3 — audio**: low-latency TTS stream per language; latency budget ≤ 4s end-to-end.
- **Phase 4 — rooms & archive**: multiple congregations, saved transcripts feeding into
  eLibrary search.

## Strategy & tech notes

- Frontend lives in this repo as a new route (`/translate`); reuse the olive/almond design system.
- Backend: extend the existing Railway service with a WebSocket endpoint; STT/translation via
  a streaming API (e.g. Gemini/Whisper-class streaming models); keep per-minute cost visible
  in the speaker UI.
- The `_speaker_isolation` work in this repo is a natural input — speaker diarization keeps
  the transcript clean when multiple people speak.
- Privacy: rooms are unlisted by default; recordings only stored with an explicit toggle.

## Open questions

- Consecutive-interpretation mode (interpreter reads the draft aloud) vs. pure simultaneous?
- On-device vs. server STT for cost at scale (a 2-hour service every week per congregation).
- Which languages after EN/ZH? (Pinyin subtitle mode for language learners is nearly free.)
