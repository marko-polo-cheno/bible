# Sabbath Notes

> One Bible, many sticky notes — the congregation fills the margins together, one Sabbath
> at a time.

## Idea

A collaborative layer over the Bible: after service, members post what they learned — a
takeaway, a testimony, a question — attached directly to a verse or a small set of verses.
Over months, the congregation's shared Bible fills with sticky notes: John 3:16 carries
Auntie Chen's testimony from last spring; Romans 8 holds twelve different Sabbath takeaways.
Reading scripture becomes reading scripture *with your church*.

## Why

- Sermon insights evaporate by Tuesday. Anchoring them to verses gives them a durable home
  and makes them discoverable exactly when someone next reads that passage.
- Testimonies are the most under-archived treasure in the church. Attaching them to the
  verses that carried someone through builds a living commentary of lived faith.
- It's social in the right direction: contribution over consumption, encouragement over
  engagement metrics. No feeds, no likes-chasing — the Bible itself is the timeline.

## Experience

- **In the reader**: verses with notes show a soft blossom-pink dot in the margin. Tap a
  verse → alongside Connected Verses, a "Notes from us" panel shows the congregation's notes.
- **Posting**: Sabbath afternoon, the app asks one gentle question: *"What did you take away
  today?"* Write 1–3 sentences, attach to verse(s) (search or pick from today's sermon
  passages), choose a type: 💡 takeaway · 🙏 testimony · ❓ question.
- **The Wall**: a browsable view — "this week's notes," "most-annotated chapters," a
  heatmap Bible showing where the congregation has been feeding.
- **Identity**: real names within a congregation (small-group trust), anonymous option for
  sensitive testimonies. Elders/moderators can gently hide off-topic notes.

## Plan

- **Phase 1 — MVP**: single congregation, simple auth (invite code), notes on verses,
  panel in the reader, weekly prompt. Backend: one `notes` table on the existing Railway
  service (`verse_key`, `author`, `type`, `text`, `created_at`).
- **Phase 2 — the Wall & digest**: browse views + an automatic Sabbath-evening email/WhatsApp
  digest of the week's notes.
- **Phase 3 — multi-congregation**: rooms with their own walls; optional cross-congregation
  sharing of anonymized testimonies.
- **Phase 4 — search integration**: notes become a corpus in eLibrary search ("what has our
  church said about perseverance?").

## Strategy

- Seed content matters: launch with a "notes drive" — collect 50 takeaways from one Sabbath
  so the Bible never looks empty on day one.
- Moderation-light by design: small trusted groups, post-hoc moderation, no public internet
  exposure by default.
- This is the feature that turns the site from a tool into a *community* — prioritize right
  after the Bible reader is polished.

## Open questions

- Verse-ranges vs. single verses as anchors (probably both, capped at ~5 verses)?
- Should questions (❓) ping someone — a "deacons' inbox" — or stay ambient?
- Retention policy for testimonies if someone leaves the congregation.
