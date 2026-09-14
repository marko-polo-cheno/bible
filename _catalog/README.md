# _catalog — CMS exports → file-type sidecar

Turns the four CMS catalog exports into the small artifact the API serves.

```bash
python _catalog/build_catalog.py --csv-dir ~/Downloads/CSV
```

Writes `backend/catalog/{en,zh}.catalog.jsonl` and `backend/catalog/file_types.json`.
Re-run whenever the CMS re-exports; nothing else in the pipeline changes.

## Why a sidecar

| | size |
| --- | --- |
| `backend/testimonies_{en,zh}.jsonl` | 314 MB — article text, streamed per keyword search |
| the four CSVs | 68 MB, 36–42 columns, **mixed encodings** (two UTF-16, two UTF-8-BOM) |
| what this emits | 8 MB — five fields keyed by `(lang_id, item_id)` |

Merging into the corpus would rewrite 314 MB to carry a few MB of metadata that
the keyword stage re-reads on every query and never looks at. Reading the CSVs
at request time would put encoding sniffing in the hot path. So: convert once,
offline, and join on the key the app already uses (`elibrary.parse_item_key`).

## Grouping

The facet is the **medium**, not the publication form — one bucket per kind of
thing, so every audio container (mp3/m4a/wav/wma/…) is one **Audio** and every
text format (htm/html/pdf/doc/…) is one **Document**:

Two levels. The **medium** at the top, the granular type the CMS already records
beneath it, as a `{name, value, children}` tree with `/`-paths — the same shape
as the two category trees, so the UI renders it with the component it already
has and the API matches it with the prefix logic it already has.

| medium | from | children (`ContentType` / `ItemSubType`) | items |
| --- | --- | --- | --- |
| `/Audio` | `ItemSubType=Audio`, or an audio extension | Sermon 225 · Testimony 50 · Lecture 89 · Convocation 64 · Evangelical Service 33 · Prayer 15 · Sacrament 9 | 485 |
| `/Video` | `Video`, `AudioVideo`, or a video extension | Sermon 1,503 · Outreach 448 · Lecture 437 · Evangelical Service 44 · Prayer 39 · Convocation 28 · Testimony 21 · Sacrament 1 · Other 2 | 2,523 |
| `/Document` | `Article`, `Chapter`, `LectureNote`, or a text extension | Articles 8,592 · Book chapters 2,212 · Lecture notes 165 | 10,969 |
| `/Other` | no catalog row — see below | — | 10,576 |

Selecting `/Audio` takes everything under it; `/Audio/Sermon` takes just the one.
Paths use the raw CMS value (`/Document/Article`); the display name is separate
(`Articles`). The tree is **built from the data**, so a new `ContentType` appears
on its own, and the API prunes any branch with no items in the corpus — the CMS
vocabulary is much wider than the searchable set (`/Audio/Choir` and
`/Video/Choir` exist upstream but have no text, so they are never offered).

`FILE_TYPES` in `build_catalog.py` is the single source of truth; it is emitted
to `file_types.json` and served verbatim to the UI, so the list is never
duplicated in the backend or the frontend. `ItemSubType` and `ContentType` are
still carried per item, so a finer facet later needs no re-export.

**Only the item's own file decides the medium.** `_ext_type` reads
`PhysicalFilePath` / `CompleteFilePath` / `URL` / `CompleteURL` and deliberately
never `PdfURL` or `ImageURL` — every publication row carries both, so they say
nothing about what the item *is*: `PdfURL` is an alternate rendition of the same
article and `ImageURL` is a thumbnail.

That is also why **HTML vs PDF cannot be a sub-facet**: every Document is both.
`ItemSubType` and `ContentType` are the splits that do partition items, and both
are already stored per item — see "Nesting" below.

`TableOfContents` is carried through the sidecar but never offered as a filter —
`elibrary.build_join_map` uses it to drop those items before they become
searchable at all.

## Things the data does, that the code has to handle

- **No `TableOfContents` is lost to broken rows.** Both publication exports parse
  100% cleanly (5,010/5,010 and 18,365/18,365 rows carry a valid `ItemSubType`).
  The malformed rows are confined to `Media-EN.csv`, which has no TOC concept at
  all — so the 2 rows dropped there cost nothing on this axis.
- **A length heuristic cannot substitute for the flag.** Containers are long
  (median 107,223 chars vs 7,235 for an ordinary Document), but so are plenty of
  real articles. Scored against the catalogued set where the answer is known:

  | threshold | TOC caught | recall | real Documents wrongly hidden | precision |
  | --- | --- | --- | --- | --- |
  | 26,308 | 240 | 75% | 343 | 41% |
  | 40,000 | 230 | 72% | 107 | 68% |
  | 60,000 | 221 | 69% | 72 | 75% |

  At any usable recall it hides hundreds of legitimate articles, so the catalog
  flag stays the only signal. The ~45 estimated undetected containers among the
  uncatalogued items need a fresh export, not a guess.
- **`Other` is a stale export, not a category.** Every one of the 10,576 `Other`
  items is uncatalogued — zero are catalogued-but-unnamed. The exports stop at
  `ItemID` 55064; the corpus runs to 66090, and 10,570 of the 10,576 have an ID
  above that ceiling. They are simply articles published after the May 2025
  snapshot was taken. By `form_type` they are 8,702 PUBLICATION / 1,432
  TESTIMONY / 442 SERMON, i.e. overwhelmingly text.

  **A fresh CMS export is the fix**; it should move ~95% of `Other` into
  `Document`. Until then `Other` stays a real, selectable facet so filtering
  never silently hides them.
- **`Media-EN.csv` has malformed rows** — unescaped commas shift every column, so
  a file path lands in `ItemSubType`. Rows whose `ItemSubType` is not a known
  value are rejected rather than guessed at (2 rows today).
- **`(lang_id, item_id)` is safe.** Publication and Media share no `ItemID`
  within a language, so the two catalogs can be merged into one keyspace.
- `Person.csv`, `tPlace.csv`, `tPersonVerseIndex.csv` and the `.srt` transcripts
  are not used here — they are Bible reference data and media subtitles, not
  eLibrary catalog metadata.

## Format — a second, orthogonal axis

How you can actually consume the item. *Not* a branch of the file-type tree — a
Document can be both a web page and a PDF, and an mp3 exists under two different
mediums — so it is its own scope (`formats.json`, `formats` on the request),
intersected with the rest.

Extracted per item: `pdf`, `html`, `mp3` (any audio container), `video` (any
video container). Multi-select is a union — picking **PDF** means "available as
a PDF", including items also published as a web page.

A streaming **host** is not a format — YouTube is a place, not a file, and an
item can stream from it while shipping nothing downloadable. It lives on the
item as `video_host` (`youtube` 2,522 · `vimeo` 1 in the corpus) for badging and
deep links, and is never a filter facet.

### Only some of them earn a chip

`JoinMap.prune_format_facets` drops a rendition that says nothing the medium
already says. Against the corpus today:

| format | items | verdict |
| --- | --- | --- |
| `pdf` | 2,768 | **kept** — 25% of `/Document`, a real split |
| `mp3` | 2,659 | **kept** — spans `/Audio` (485) *and* `/Video` (2,174), so it cuts across the medium and splits `/Video` into 2,174 downloadable vs 349 stream-only |
| `html` | 10,966 | dropped — restates `/Document` (10,966 of 10,969; the chip would remove 3 items) |
| `video` | 0 | dropped — no items in the corpus |

The rule is data-driven, not a hand-picked list: a format is offered unless it
has fewer than 10 items, or it sits inside one medium and covers ≥95% of it. The
values stay on every item either way, so the UI can still badge or link them.

`formats.json` is the *vocabulary*, not the served list — the converter only
knows the CSVs, and whether a format earns a control depends on the corpus,
which only the API can see. Expect entries in that file that `/elibrary/trees`
does not return.

> **Careful with `PdfURL`.** The CMS writes the literal string `"NULL"` for an
> absent URL, so a non-empty test says every publication has a PDF. It does not —
> only ~14% do. `_formats()` treats `NULL`/`N/A`/`-`/`none` as absent.
