# The Journey

> Walk the Bible chronologically — a game-like pilgrimage across a living map, where every
> story is pinned to its place, time, and connected scriptures.

## Idea

A guided, chronological traversal of the Bible presented as a journey rather than a book.
The player moves along a timeline-road — Creation → Patriarchs → Exodus → Kingdom → Exile →
Gospels → Acts → Letters → Revelation. Each stop is a scene: the passage(s) in reading order,
its location glowing on a live map, the people involved, and a glossary of unfamiliar terms.
Cross-references (our existing verse-similarity graph, `nn.json`) appear as "threads" you can
pull to see how a moment echoes across the whole canon — how Isaiah 53 threads into the
crucifixion narrative, how the Passover threads into the Last Supper.

## Why

People don't struggle with the Bible because it's long; they struggle because it's
non-linear — books overlap in time, epistles interleave with Acts, prophets speak into
specific kingdoms. A map + timeline + glossary turns background confusion into orientation.
The game framing (progress, streaks, unlockable side-paths) gives momentum that reading
plans lack.

## Experience

- **The Road**: a scrollable path with milestones. Your avatar (a little olive branch 🌿)
  stands where you left off. Progress is visible and satisfying.
- **Scenes**: each milestone opens a split view — passage on one side, map/timeline on the
  other. Locations animate (Abraham's route from Ur, the Exodus wanderings, Paul's journeys).
- **Threads**: pull a highlighted verse to see its connected verses across the canon,
  rendered as literal threads across the timeline. This reuses the Connected Verses engine
  already shipped in the Bible app.
- **Glossary**: every scene contributes terms (Pharisee, ephod, covenant, Sanhedrin) to a
  personal glossary that grows as you travel — your own study companion by the end.
- **Side quests**: optional deep-dives (genealogies, feasts, temple layout) for completionists.

## Plan

- **Phase 1 — data**: chronological ordering table (scene → passages → date range → location
  coordinates → people → terms). This is content work; store as JSON in `public/data/journey/`.
- **Phase 2 — the Road UI**: milestone scroller + scene reader reusing the Bible reader
  component; progress saved locally, later per-account.
- **Phase 3 — the Map**: SVG/vector map of the ancient Near East & Mediterranean with
  animated routes per scene (no heavy map dependency; stylized like the rest of the site).
- **Phase 4 — Threads & Glossary**: integrate `nn.json` threads and per-scene term packs.
- **Phase 5 — game feel**: streaks, chapter "stamps" in a pilgrim's passport, shareable
  progress cards.

## Strategy

- Content-first: even Phase 1 shipped as a plain "chronological reading order with maps"
  page is already differentiated. Game mechanics layer on top; they are polish, not core.
- Reuse aggressively: the reader, connected verses, and theming all exist. The Journey is
  primarily a *navigation and data* project, not a new engine.
- Long-term: The Journey becomes the on-ramp for new believers on the site — "Start here."

## Open questions

- One canonical chronology vs. selectable scholarly orderings?
- How much extra-biblical dating do we show (and how do we caveat it)?
- Mobile map interactions — pan/zoom or fixed vignettes per scene?
