---
name: webnovel-scrape-pack
description: Scrape a full web novel series into epub, pdf and txt.
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [webnovel, scraping, epub, pdf, packaging]
    related_skills: [grounded-citations]
---

# Scraping a full web serial into a book

## When to Use

- The user asks to scrape, download, or "get" a whole web novel / web serial
  (or one series from a chapter-index site) as a readable file.
- The deliverable should be a book: epub, pdf, or one combined text file.
- Not for a single page fetch, and not for sites behind a paywall or login.

Goal: get every chapter of a serial as clean per-chapter markdown, then package
to txt + epub + pdf. ~1100 chapters takes ~10 min.

## The lesson that matters

**Scope extraction to the story container, never to "all `<p>` tags".**
On nobadnovel.com the page contains the story, 2-4 "related novels" teaser
blocks (gray previews), a footer copyright, and nav — all inside or near the
same content div. Grepping every `<p>` yields ~30% junk: the final chapter of
a book reads as ad copy for another series.

Fix: match the story paragraph class only — `<p class="mb-4 para">`. Inspect
the raw HTML first and confirm the classes are cleanly separated:

    grep -o '<p class="[^"]*"' page.html | sort | uniq -c
    # 79  <p class="mb-4 para">                           <- story
    #  4  <p class="text-sm text-gray-500 line-clamp-2">  <- teasers
    #  1  <p class="astro-DF3T5UYH">                      <- footer copyright

Keep a fallback to all `<p>` if the class is ever renamed, but verify the
fallback isn't firing (count of matched paragraphs should be non-zero and the
per-chapter word count should look stable across chapters).

## Verification that actually catches contamination

A count check (`grep -ci Copyright <site>`) proves nothing about the body text.
The word-count and junk-string checks also pass while real markup leaks through.
Sweep these classes explicitly, over the built epub/txt as well as the chapter
files:

- **Site-injected pseudo-HTML tags.** akknovel wraps proper nouns in
  `<glossary_translation>Chloe</glossary_translation>` to drive a hover
  glossary — 61 pairs in one chapter of 334. Markup, not text, and it renders
  as literal tags in every output format. A generic tag census
  (`grep -o '<[a-zA-Z_][\w:.-]*' | sort | uniq -c`) finds them; no keyword list
  would.
- **The site's own emphasis markup.** `[** ... **]` around bracketed
  livestream barrage lines (8 in one chapter). Only the `**` reveals it — the
  brackets around it are legitimate story formatting.
- **Censored profanity is NOT emphasis markup.** akknovel censors swears as
  `f***ing` and `Bull****` — runs of asterisks with word characters around
  them. Any markup stripper must mask these FIRST: `**...**` with content
  between the delimiters cannot match an all-asterisk run, but a naive
  `replace('**', '')` turns `Bull****` into `Bull` and silently uncensors the
  book with no visible error. Unit-test the stripper on `Bull****`,
  `f***ing`, `**bold**`, `**[thought]**`, `**「dialogue」**` before trusting it,
  and report censored-word counts before AND after as proof they survived.
- **`**` counts must exclude censored words** or a clean book looks dirty: 2
  residual hits on a fully-cleaned book were exactly the two censored swears.
**Titles that exist only in the TOC.** The chapter page `<h1>`/`<title>` is
just "Book Name Chapter N" — no title at all — but the SERIES INDEX renders
`<span class="inline-block mr-3">Ch.53</span>Two Armies at War`. All 334
headers came out bare `# Chapter N`. Parse titles off the index page, and
expect its anchor text to vary per row: the last chapter is wrapped in the
site's own `Last chapter: &nbsp; Ch.334&nbsp; Final Chapter`, so the `Ch.N`
marker must be stripped at any position or the header reads `Chapter 334 Last
chapter: Ch.334 Final Chapter`. Print the raw inner HTML per row before
trusting a strip-tags parser.

- **A numeric "title" is a placeholder, not a title.** Some uploads leave the TOC
  title field empty, so the index renders the chapter number as the title —
  `Ch.24` -> `Three-in-One` but `Ch.2` -> `02`, `Ch.95` -> `95`. On one book 94 of
  104 chapters came back numeric-only. Writing those into headers produces
  `# Chapter 2 02`, which is worse than a bare `# Chapter 2`. Strip any title
  that is only digits/dots after recovery and keep the bare header; report the
  count so a genuinely untitled book is visible rather than silently mangled.
  Check this before assuming a title-recovery step failed — dump the parsed
  titles and see whether the SOURCE has them.

Run `scripts/clean_chapters.py` in dry-run mode and a pattern sweep over the
chapter files before shipping; then re-check the packaged formats.

Findings that only a pattern sweep surfaces, all from real runs:

- **Site furniture**: `————` separator paragraphs (388 in one book), plus
  ASCII `------` variants. Check both dash styles.
- **MTL translator notes**: `ps: it takes twenty minutes to check for typos.`
  (168). Two were never translated from Chinese — scan for CJK residue too.
- **Author end-of-chapter notes**: monthly-pass begging (84), plus a closing
  sign-off block that may carry no marker at all — ch2139's farewell ran from
  its 85th paragraph to the end. Prefer a `(End of the book)` marker or a run
  of >=2 sign-off lines at the TAIL; `Thanks!` and `Happy New Year!` also occur
  as ordinary dialogue, so a global regex eats story text.
- **Anti-piracy watermarks hidden in Unicode math script**: the site appends
  `𝒻𝒓𝒆𝒆𝒘𝒆𝒃𝓃𝒐𝒗𝒆𝓁.𝒸𝑜𝓂` to the END of ~1,100 paragraphs in MIXED font styles. A
  grep for `freewebnovel` never sees it and the whole-domain string never
  appears as a contiguous run. Two consequences:
  - Normalise per character (NFKC) and keep a 1:1 index back to the original.
    Whole-string NFKC is unsafe: 1,120 paragraphs change length under it, so
    offsets into the normalised text don't address the original.
  - Every codepoint inside a watermark must be in the mapping class. U+0212F
    (SCRIPT SMALL E) and U+02134 (SCRIPT SMALL O) sit in LETTERLIKE SYMBOLS,
    not the Mathematical Alphanumeric block — omitting them silently left 254
    chapters stamped. Guard the pattern and re-run the scan until the count is
    zero; a partial pass looks identical to a clean book.
  - Guard removal on "the reassembled letters spell a known domain", so real
    math in a xianxia novel survives. Test against paragraphs harvested from
    the book that contain math but no watermark: 0/75 collateral on the last run.

**Keep deliberate oddities.** ch1977's `"&...%￥#"` is garbled speech inside a
distorted space — it is the story, not a watermark. Likewise ch1947's "The next
Chapter shall begin anew" follows "The Chapter of three eras has nearly
ended": cultivation-world verse about an era closing. Judge each hit in
context; a blanket delete removes real text.

**CJK BRACKETS ARE STORY, NOT SITE FURNITURE.** `【...】` (U+3010/3011) marks
internal monologue, system/skill panels and stat readouts — 124 in one book.
Never strip them; they are the convention that makes those passages readable
as thoughts rather than dialogue.

They are also a live trap for the watermark code: `MATH_CHAR` spans
U+3001-U+D7FF, which **contains** U+3010/3011, and both are NFKC-stable. So
they map to themselves harmlessly and `strip_watermark` leaves them alone —
verified: `【System: skill activated】` comes back byte-identical. The removal
stays safe because it is guarded on the reassembled letters spelling a known
domain, not on the character class. Do not "fix" this by narrowing MATH_CHAR
without re-running the full watermark scan: the guard, not the class, is what
keeps real math in a xianxia novel safe.

## Pick the source by testing, not by search results

Search engines return five or six mirrors of the same serial; most are worse than
the one you want. Fetch chapter 1 from EVERY candidate and compare paragraph
counts and the first/last line of the extracted text before committing to a
3,000-chapter run. Measured on Shadow Slave (2026-10-06), same novel, four
sites:

    freewebnovel.com   57 paras, chapter-start scoping works -> USE
    novgo.net          65 paras, nav header/footer bleeds in
    freewebnovel.net   65 paras, same bleed, and a duplicate chapter listing
    readnovelfull.com  clean prose but no scoping hooks at all
    wuxiadreams.com    100-chapter cap; 91 of 100 <p> are JS/CSS

A site's index page loading 200 is not evidence it is scrapable, and a
"cloudflare" grep is not a reliable block detector — challenge-platform script
tags appear on pages that serve content fine. Judge by extracted paragraphs.

`discover_max` must probe past the highest linked chapter (3205 here; 3206 404s),
and the series is often still ongoing, so "completed" in a search snippet is not
a chapter count.

## API-backed sites: read the JS bundle before writing a scraper

Some series sites are SPA shells — the series page returns 200 with no chapter
links, and every `<p class=...>` on it is nav furniture. Before concluding
"blocked/unscrapable", fetch the page's `<script type="module">` bundle and grep
for the API paths. On botitranslation.com that took five minutes and replaced
the whole scrape with two clean REST calls.

    curl -s "$URL" | grep -o 'src="/assets/[^"]*\.js"'      # entry bundles
    # then grep the bundles for base URL and endpoints:
    grep -o 'baseURL[^,;}]\{0,80\}' bundle.js
    grep -o '`[^`]\{3,80\}`' bundle.js | grep -iE 'api|book|chapter'

Observed there: base `https://api.mystorywave.com/story-wave-backend/api/`,
paths `v1/content/books/{id}`, `v1/content/books/{id}/firstChapter`,
`v1/content/chapters/page?bookId=&pageNumber=&pageSize=&sortDirection=`,
`v1/content/chapters/{id}` (full text). Two non-obvious required headers:
`site-domain: <hostname>` and `lang: en`. The chapter payload has a separate
`authorNote` field — author notes are NOT inline in `content`, so they need no
cleanup pass.

**A `paywallStatus: free` chapter can still be locked.** The TOC listing
carries a `tier` field; 66 of 501 chapters had `free` + `tier > 0` and returned
only a ~1000-char teaser. Check `tier`, not just `paywallStatus`, or a
"complete" scrape silently drops the last fifth of the book. Those chapters
need purchase — fetch them yourself, then point the packaging scripts at the
local files.

## Generating chapter titles the source doesn't have

Some uploads leave the TOC title field empty, so no title exists anywhere to
recover. Fan out `delegate_task` with one agent per ~10 chapters: each agent
`read_file`s every one of its chapters IN FULL (10 chapters x 2-5k words fits
comfortably) and writes a TSV `<number>\t<title>`. Batches of 10 ran 95 chapters
in ~2 minutes wall clock.

**Give the agents the book's real titles as a style reference** in the prompt —
the four or five the uploader did fill in. Agents working in parallel have no
shared context, so without reference titles the batches drift into different
registers and the TOC reads like three different books.

Verify the merged output before applying. Three defects showed up in one run:

- **Literal `\t` instead of a tab.** One batch wrote `92\tSilver Frost` as
  literal backslash-t characters. `line.split('\t')` then yields one field and
  the titles silently vanish. Count parsed titles vs expected — a shortfall of
  exactly the last batch's size points here. Normalise with
  `raw.replace('\\t', '\t')`.
- **Missing trailing newline** merges the last line of one file into the next
  when you `cat` them, producing a two-field line that parses as garbage.
  Rewrite each file as `'\n'.join(non_empty_lines) + '\n'`.
- **`wc -l` undercounts by one** per file without a trailing newline; 89 lines
  for 95 titles looked like missing data until parsed properly.

Then apply through `apply_titles.py`, which refuses to overwrite a real
source title, rejects numeric placeholders, and rejects duplicate titles across
batches (an agent that loops would otherwise stamp one line 10 times and the
count still reads 10).

## Madara-theme sites (hiraethtranslation and its many clones)

Mangareader.to / Madara clones serve ~545 KB per chapter page of which ~5 KB is
the novel: ads, sidebar widgets, related-reading carousels, a login modal and a
wpdiscuz comment thread.

    CONTENT = <div class="reading-content"> … <div class="text-left"> STORY
      … <div class="entry-header footer">  <- chapter nav pager = CUT HERE
    ads live in: <div class="code-block"> and bare <ins class="adsbygoogle">

Anchor on `<div class="text-left">` and cut at `entry-header footer`. Three
traps, all of which produce a plausible-looking but wrong result:

- `class="reading-content"` also prefixes `reading-content-wrap` and
  `related-reading-content` (4 ad carousels at the page bottom). A greedy
  capture runs into the comment thread and picks up `Reply`, usernames and
  `1 year ago` as story paragraphs.
- `grep 'chapter-1'` matches `chapter-199`. Match `chapter-\d+/` and sort -V.
- The series index (750 KB) has NO `<option>` rows. The chapter picker with
  all 1,023 titles lives on a CHAPTER page, in
  `<option … chapter-N>Chapter N - Title</option>` — note no `value="chapter-N"`,
  the URL is in `data-redirect`. Fetch chapter 1 once and take every title from
  there; the picker is duplicated across several selects, so dedupe.

The `<h1 id="chapter-heading">` is only "Book Title - Chapter N" — no title.
Reject that form (ends with `Chapter N` after the book name) and fall back to
the TOC. After a title-recovery fix on an already-scraped book, the resume
guard only re-fetches BARE `# Chapter N` headers, so files still carrying the
book-prefixed H1 look finished forever — re-head them from the TOC instead of
re-downloading the book.

## novelfull.com: paginated TOC, three URL shapes, drifting numbering

    body   : div#chapter-content.chapter-c — find the closing tag by NESTING
             COUNT, not by the next `<hr class="chapter-end">` or sibling div.
             Three ad iframes (`//ad.a-ads.com/...`) live INSIDE the container,
             so any "cut at the next marker" heuristic truncates the story.
    TOC    : /<slug>.html?page=N, 64 pages x ~50 for a 3k-chapter book. Page 1
             yields 55 links and looks complete; the highest chapter NUMBER on
             it (3165) is the only tell. Walk until a page errors or is empty —
             and CATCH that error: page 65 is a 404, and an uncaught HTTPError
             in the TOC walk aborts the run with an empty output directory.
    URL    : three shapes, all real:
               chapter-63.html                         (no slug)   x67
               chapter-1-mt-yellows-true-monarch.html  (dash+slug) x3097
               chapter-71tearing-down-a-building.html  (NO dash)   x1
             Use `chapter-(\d+)-?[^"]+\.html` and keep the FULL href. Requiring
             the dash loses 67; rebuilding the path from a dash/space-swapped
             display title 404s. `－`? see below — the shapes above are exact.

**Numbering drifts from the URL.** From ~ch2962 the site's own numbering is
offset by two (URL `chapter-2962` serves "Chapter 2960") and the offset grows.
The body keeps the site's title, so combining it with the TOC slug produces a
doubled header: `# Chapter 2962: Chapter 2960: Teaming Up with Top Tycoons`.
The file number and the printed number are both legitimate — trust the URL for
ordering, the body for the title, and never concatenate both. 206 chapters were
affected; a `h.count('Chapter') > 1` check finds every one.

**Judge junk hits in context.** This book produced: "copyright" (a skill in the
story), "reply to" (dialogue), a wikipedia URL in a `[TL: ...]` translator note,
"monthly pass"/"subscribe" (characters discussing web novels ON PAGE — the author
is writing about novel site rankings), and fullwidth `＊＊＊＊＊` scene dividers.
All legitimate. Only the ad iframes were real.

## Pitfalls that cost real time

- **Chapter URLs need the series prefix.** The series page links are
  `https://site.com/series/<series-slug>/chapter-N-title`, but a naive regex
  reduced them to `m/chapter-N-...` and every request 404'd. Always print the
  first constructed URL and `curl -o /dev/null -w "%{http_code}"` it before a
  long run. A 404-everything scrape looks like "blocked site" — it's a broken
  URL builder.
- **A reboot mid-run loses everything** unless the scraper resumes. Skip
  chapters whose `.md` already exists; then re-running after any interruption
  is safe and cheap.
- **Decode HTML entities with `html.unescape`**, not a four-entry replace dict
  for `&amp; &quot; &lt; &gt;` — the site's text is full of `&#39;` (curly
  apostrophes) which the manual version leaves in as literal `&#39;`.
- **Send a browser User-Agent.** Without it every request is 403.
- **Sort chapters numerically**, not lexicographically — `sort` gives
  chapter-1, chapter-10, chapter-100, chapter-1000. Parse the integer out of
  the filename.
- **The cover image CDN blocks hotlinking** (403 AccessDenied on direct
  download). Don't spend time on it; build the epub without a cover.
- **Sanity-check the last chapter's tail.** It should end with the real final
  line (often `(The End)`), not a teaser or copyright line. That single check
  catches junk-contamination immediately. Same for the FIRST chapter: Shadow
  Slave's ch1 ends on `[Aspirant! Welcome to the Nightmare Spell...]`, a system
  line that is genuinely part of the story, not boilerplate to strip.
- **A `ps:`-shaped regex matches ordinary words.** `^ps\s*:` is safe, but a
  loose `ps:` substring hits `lips:` and `maps:` — seven false hits in one epub
  prompted a pointless detour. Anchor line-start patterns.
- **The cleanup step is one watermark CLASS per pass.** Removing full domains
  leaves bare `free`/`ree` fragments that need a second, differently-anchored
  rule. Always re-run `clean_chapters.py` until it reports 0 touched, then
  confirm with an NFKC scan for any remaining math-script run. Two classes over
  3,205 chapters: 1,608 + 29.
- **Chunk size must shrink as the book grows.** 50 chapters of xianxia (~2.9k
  words each) peaked near the memory ceiling for a 3.2M-word book; Shadow Slave's
  ~1.2k-word chapters ran the same 50 fine at 3.9M words. Start at 50 and lower
  it if a build is OOM-killed.
- **Verify PDFs by parsing them** (`pypdf`), not by grepping the bytes — PDF
  1.7 compresses object streams, so `/Type /Page` regex finds nothing in a
  perfectly valid file.
- **Can't verify from a guessed slug** — a hand-typed chapter URL returns
  404/empty and looks like broken extraction. Read the real slug from
  `chapter_urls.txt`.
- **Never hardcode the source domain in the packaging scripts.** These scripts
  get reused across sites, and a constant like `scraped from nobadnovel.com`
  stamps a false provenance on the title page of a book actually scraped from
  freewebnovel.com. Take the site as a positional arg (or `$SCRAPE_SOURCE`).
  Same rule for the SCRAPER's base URL — `scrape_series.py` now takes `--base`
  (or `$SCRAPE_BASE`) instead of carrying `nobadnovel.com` as a constant, so one
  scraper serves akknovel / nobadnovel / freewebnovel unchanged.
- **Chapter filenames are not consistent across scrapers.** `chapter-12-slug.md`
  (nobadnovel, akknovel) vs zero-padded `chapter-0012.md` (API scrapers). A
  `chap_num` regex requiring a trailing dash silently sorts EVERY file as
  10**9 and prints `CHAPTER 1000000000` in the txt — and `clean_chapters.py`'s
  `chapter-\d+-.*\.md` glob matches nothing at all. All three scripts now use
  `r"chapter-(\d+)(?:-|\.|$)"`. Check this before blaming the packager.
- **Zero clean hits is a finding, not a bug.** `clean_chapters.py` reporting
  all-zeros across 334 chapters means the site emits no separator/MTL/author
  furniture — akknovel was clean out of the box. Do not go hunting for
  watermarks that were never there.
- **The junk check must exempt the title page.** `grep -ci Copyright\|<site>`
  hits line 3 — the provenance line you just wrote. Require the count to be
  exactly 1 for the site name, and inspect every other hit before calling it
  contamination.
- **Never let a repair script `os.replace` a chapter without writing it back.**
  `os.replace(f, f + ".bak")` renames the file out of the scrape output, then
  nothing writes the repaired text — every `.md` vanishes, the run looks like
  catastrophic data loss, and recovery is a manual copy-back. Use
  `shutil.copy2(f, f + ".bak")` then `open(f, "w").write(new)`.
- **Build a chapter's new content in one pass, in the right order.** Rebuilding
  `new` from the ORIGINAL `raw` after already mutating it silently discards
  every repair: the title fix ran, the body-strip step overwrote it with
  untagged text, and the run reported success while leaving the tags in place.
  Compose once — title into `head`, repairs into `body`, then
  `new = head + sep + body` — and verify the OUTPUT, not the intent.
- **A repair script must be idempotent.** After one applied run, re-running
  reported "0 changed" while a stale header from the earlier buggy run was
  still wrong, because the guard only matched *bare* headers. Match the defect
  (any embedded `Ch.N` marker), not just the first-run symptom, and re-run until
  it reports no changes.
- **Delete `.bak` files before any glob-based step.** `glob('out/chapter-*.md')`
  does NOT match `chapter-16-x.md.bak`, but a looser `glob('out/chapter-*')`
  does — and then every chapter is processed twice, showing duplicate headers
  and double-counting every metric. Symptom: chapter count reported higher than
  the unique chapter numbers, with two files claiming the same number.
- **A lone `***` line is a scene divider, not leftover markdown.** It survives
  the `**`-emphasis sweep by design and shows up as a "literal **" hit in the
  final check. Do not chase it.
- **Count URLs in the epub against known xmlns declarations.** A sweep for
  `https?://` reports ~3 hits per chapter file, all of them
  `http://www.w3.org/1999/xhtml` and the EPUB vocab URIs in the boilerplate
  head. Verify against the epub source before calling it contamination.

## Pipeline

1. **Fetch the series page**, save HTML.
2. **Extract chapter URLs**: `grep -o 'https://site.com/series/<slug>/chapter-[^"]*' | sort -u`.
   Check the count and that chapter numbers are contiguous (strip the number
   with a regex, `sort -n`, inspect the max).
3. **Scrape chapters** → `out/chapter-N-slug.md`, one `# Title` header then
   paragraphs. Resume-aware, errors to `out/.errors.tsv`.
4. **Verify**: file count matches URL count, `.errors.tsv` absent/empty, no
   junk strings (`Copyright`, site name) anywhere, no chapter under ~50 words.
5. **Package** (see scripts/) → txt + epub (ebooklib) + pdf (weasyprint).
6. **Verify outputs**: chapter count and ordering in txt; zip entries in epub;
   page count + last-page text in pdf.
7. **Move out of scratch** — scratch is pruned after 24h idle. Keep deliverables
   plus the scripts somewhere durable so a re-run can pick up new chapters.

## Scripts

- `scripts/make_pdf.py <dir> [title] [source-site] [--chunk=N]` — chunked
  weasyprint render + pypdf merge.
- `scripts/clean_chapters.py <dir> [--apply]` — dry run by default; strips
  separators, MTL notes, author notes, and math-script watermarks.
- `scripts/scrape_series.py <series-slug>` — TOC fetch, chapter scrape
  (scoped, resumable), verification summary.
- `scripts/package_book.py <dir> [title] [source-site]` — combined txt + epub.
- `scripts/make_pdf.py <dir>` — weasyprint PDF, A5, page break per chapter.

Dependencies (not in system python; make a uv venv):

    uv venv epubenv && uv pip install -p epubenv/bin/python ebooklib weasyprint pypdf

Memory ceiling: `make_pdf.py` renders in chunks (default 50 chapters, `--chunk=N`)
and merges with pypdf. A single-shot weasyprint build of a 2,900k-word novel was
OOM-killed by the cgroup limit at ~2.9 GB RSS, because it holds the whole
document tree in memory. Chunked rendering keeps peak RSS flat.

## Notes

- Respect the site's terms and rate: this pipeline sleeps 0.5s per request
  (~9 chapters/sec), which is polite for a full-series fetch.
- Word-count delta is the best junk detector: contaminated run 2.0M words,
  clean run 1.31M for the same 1076 chapters (~25-33% per chapter removed).
- Deliverables convention: `$HOME/books/<series-slug>/` with `book.pdf`,
  `book.epub`, `book.txt`, `out/` and the three scripts.