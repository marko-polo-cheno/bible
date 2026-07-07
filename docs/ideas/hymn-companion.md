# Hymn Companion

> Every hymn, its scriptures, and its story — sing with understanding.

## Idea

A hymn explorer built on the lyrics corpus already in this repo
(`frontend/public/hymn_lyrics.csv`). Each hymn page shows the lyrics (EN/ZH side by side
where available), the scriptures it springs from (auto-linked into the Bible app), and the
scriptures link back: reading Psalm 23 shows "Hymns that sing this psalm." Add search by
theme, line fragment ("I once was lost…"), or verse.

## Why

- The data is already sitting in the repo — this is the cheapest new app we can ship.
- Hymns are the congregation's shared memory; connecting them to scripture deepens both.
  "It Is Well" hits differently next to 2 Kings 4 and Psalm 46.
- Worship leaders constantly ask "what hymn fits this sermon passage?" — verse→hymn lookup
  answers that in one search.

## Experience

- **Hymn page**: number, title, lyrics with verse/chorus structure, linked scripture chips,
  "sung on" history (if Sabbath Notes exists, services can log their hymn picks).
- **In the Bible reader**: a small music note in the margin when the chapter has associated
  hymns — tap to see them, same pattern as Connected Verses.
- **Search**: by number (fastest path for service use), title, lyric fragment, theme, or
  scripture reference.
- **Presentation mode**: full-screen lyrics for projection — large serif type on the paper
  background, keyboard/tap to advance stanzas. A poor-man's ProPresenter for small halls.

## Plan

- **Phase 1 — browse & search**: parse `hymn_lyrics.csv`, hymn pages, fuzzy lyric search
  (client-side; the corpus is small).
- **Phase 2 — scripture linking**: LLM pass to map each hymn to its source/allusion verses;
  store as a static JSON; hand-review the top 100 hymns.
- **Phase 3 — reader integration**: margin indicator + "Hymns for this chapter" panel.
- **Phase 4 — presentation mode** and service planning (pick Sabbath's hymns, share a link).

## Strategy

- This is the ideal "second live tile" after Bible — small, data-complete, and it makes the
  home menu feel like a real suite. Ship Phase 1–2 quickly for momentum between the bigger
  bets (Translator, Journey).
- The scripture-linking JSON becomes another edge in the site's knowledge graph: verses ↔
  verses (nn.json), verses ↔ notes (Sabbath Notes), verses ↔ hymns. The graph is the product.

## Open questions

- Copyright check per hymnal — public domain vs. licensed lyrics (may constrain which hymns
  display full text vs. first lines + number).
- Audio: embed recordings/MIDI, or stay text-only?
- Pinyin rendering for Chinese hymn lyrics (reuse the Bible's pinyin approach)?
