# Memory Garden

> Hide the Word in your heart and watch an orchard grow — scripture memorization with
> spaced repetition, visualized as almond and olive trees.

## Idea

A verse-memorization trainer where progress is a garden. Each verse (or passage) you're
memorizing is a sapling; every successful recall waters it. Spaced-repetition scheduling
(SM-2 style) decides when a tree "needs water" again. Fully-grown trees blossom — almonds
for Old Testament verses, olives for New Testament. Your garden *is* your review deck:
a glance shows what's thriving and what's wilting.

## Why

- Memorization apps exist, but none are connected to where you actually *read*. Ours is one
  tap away: any verse in the reader gets a "Plant this verse" action.
- The almond/olive brand practically begs for this metaphor (Jeremiah 1:11–12 — the almond
  branch as the sign that God watches over His word to perform it).
- Spaced repetition is the single most evidence-backed learning technique; wrapping it in a
  garden removes the flash-card grind.

## Experience

- **Planting**: in the Bible reader, long-press/expand a verse → "Plant in Memory Garden."
  Choose translation(s) — memorize in English, Chinese, or both (pinyin support built in).
- **Watering (review)**: progressive recall modes — read → first-letters → blanks → type/say
  from memory. Grading feeds the scheduler.
- **The Garden**: an isometric orchard in the site's illustration style. Trees cluster by
  book. Wilting trees drift toward the gate so the day's reviews are always visible.
- **Seasons**: weekly recap — what bloomed, what needs care, streaks as "rainfall."
- **Group plots** (later): a family or Bible-study group tends a shared plot — everyone's
  memorization of the month's passage waters the same communal tree.

## Plan

- **Phase 1 — engine**: verse decks + SM-2 scheduler + the four recall modes; data in
  localStorage first (no account needed), export/import JSON.
- **Phase 2 — the garden**: SVG orchard renderer (reuses splash/branch art language),
  tree growth states, review-queue-as-wilting.
- **Phase 3 — accounts & sync**: piggyback on whatever auth Sabbath Notes introduces.
- **Phase 4 — group plots + audio recall** (speech-to-text checking for recitation).

## Strategy

- Ship Phase 1 embedded in the Bible app (a leaf icon in the header) rather than as a
  separate page — adoption comes from proximity to reading.
- The garden visual is the shareable artifact: "my year in the garden" cards spread the site
  organically.

## Open questions

- Word-perfect vs. meaning-tolerant grading (especially across EN/ZH)?
- Passage-level memorization (whole Psalm) — one big tree or a grove?
- Kids mode with simpler verses and faster-growing trees?
