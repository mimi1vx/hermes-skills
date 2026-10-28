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
  that is only digits/dots after recovery and keep the bare header — unless
  stripping leaves nothing: a dots-only source title (`......`, no number)
  stays verbatim, since an empty header says less than the source's own
  placeholder; report the
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
  - The same guard covers the OTHER obfuscation families: parens/spaces/
    homoglyph variants (`freew(e)bnovel.(c)om`, `freewe bnovel.com`,
    `direction. freewebnovel.cσ๓`, `freeweɓnøvel.com`) and per-chapter UNIQUE
    tokens (one book stamped ~400 chapters each with a different RANOBES
    spelling — `℞âŊoBЕS`, `ṙÄNȰβΕs`, `ꞦáNÓВΕṥ` — so no keyword list ever
    completes). De-obfuscate each paragraph (homoglyph map + NFD diacritic
    strip + drop parens/whitespace, keeping an index map back to the
    original), then remove only spans whose reassembled text spells the known
    signature. Whole-line template stamps (`Follow current novels on X`,
    `This chapter is updated by X`, ...) drop as paragraphs; inline appends
    keep the story and lose the token. Re-scan until the count is zero — the
    palette keeps growing (Greek/Cyrillic/Runic/Gothic lookalikes, macron
    vowels, enclosed alphanumerics), so a partial pass looks identical to a
    clean book. Anchor the search LOOSELY (any paragraph-final token) and
    guard STRICTLY (exact signature match after normalization) — the guard,
    not the anchor, is what keeps story text safe.
  - The palette now includes non-letter scripts: Gujarati digits for `o`
    (`freewebn૦νeƖ.com`, `ƒreewebn૦vel.com` — U+0AE6 is a digit, so NFKC
    never touches it and MATH_CHAR never matches it), the domain with the
    dot dropped (`freewebnoѵeƖ com`), and doubled domains
    (`NovelFull.cominnread.com`). Extend the homoglyph map per find
    (ƒ→f, ૦→o, ν/ѵ→v, Ɩ→l) and match the signature dot-optional. These hide
    from every cleaner built before them: one run's `clean_chapters.py`
    reported all-zeros while 185 hits shipped into all three formats —
    only a normalizing re-scan of the CHAPTER files caught it. Translators'
    real-life asides (`Hopping on a plane in 12 hours! ... 🙂`) ride in the
    same paragraphs as story text on some uploads; they drop as exact-match
    furniture like any promo line.

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

**Verify what the series actually IS before you assert anything about it.**
Search snippets for a fan sequel read exactly like canon: same author name, a
book number, a "series" name, even a plausible chapter count. One run spent a
full search cycle asserting "book 3 of X, by Author Y, official mirror is Z"
— all three invented from snippets, and the "official mirror" turned out to be a
parked domain for sale. Before writing that sentence or opening a scraper:

- Check an authority that knows the canon — publisher page (webnovel.com),
  Wikipedia, or a novel database — and see whether the series is even listed.
  If it isn't, treat the request as unverified rather than guessing.
- Confirm the number of books from the source, not from a mirror's title slug.
  A slug like `lord-of-mysteries-3-city-of-horror` is a mirror's guess, and the
  rest of the family may not exist there at all (404 on the real index).
- Fanfic, derivative, and copy titles are the common case for popular series.
  Say "this looks like fan work, unverified" and ask for a URL instead of
  inventing an author, a book number, and a host.
- "Domain returns 200" is not "site is alive" — read the <title>; a parked or
  for-sale page returns 200 forever.

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

## Sites seen in the wild (as of 2026-10-21)

| host | status | notes |
|------|--------|-------|
| freewebnovel.com | scrapeable | chapter-start scoping works |
| nobadnovel.com | scrapeable | scope to `<p class="mb-4 para">`; no-space `Ch.N` markers |
| akknovel.com | scrapeable | same parser family; censors profanity as `f***ing` |
| readnovelfull.com | scrapeable | clean prose, no scoping hooks — scope by paragraph index |
| novelfull.com | scrapeable | category pages paginate; watch for split-chapter subparts |
| novelcool.com | scrapeable | shares novelfull's chapter numbering and translation — the fallback source for novelfull gaps; exact chapter URLs live in the chapter-page picker's dropdown/nav, which lists chapters the series index omits |
| dhibooks.com | rate-limited | hard 429s for hours at a time; titles are MTL-variants of the same numbering, but chapter slots can serve wrong content and the translation is a different, cruder MTL pipeline — verify slot integrity and translation family before trusting anything from here |
| lite.wuxiaworld.com | scrapeable | **preferred fallback when novellive.app is walled**: serves clean pages over curl, scope to `<div class="chapter-body" id="chapter-body">` with `<p data-uid>`; TOC lists only the first 100 chapters, so walk next-links from ch1 |
| novellive.app | Cloudflare-walled | curl and headless browser both get the JS challenge; the same novels are usually on lite.wuxiaworld.com |
| konkon.ink | scrapeable | Nuxt SSR: story HTML is inside the `__NUXT_DATA__` JSON payload (devalue index refs — resolve ints via the array), not in `<p>` markup; TOC hrefs are `/read/chapter/<id>/chapter-N-slug`, ch1-10 slugs carry no title (use the content's own subtitle lines); scraper `scrape_konkon.py` kept next to the books. Number by the slug, never by URL id or TOC position — chapters upload out of order (slug `6` on a late id, slug `26` on an early one) and id-ordering silently scrambles the book. When the content opens with its own `Chapter N: Title` line, capture the embedded title and drop the line — concatenating it with the file number doubles every header. A guessed short series slug can 404 (`Novel not found`) while every chapter URL stays live — resolve the true slug from any chapter page's `__NUXT_DATA__` payload (`novel.slug`), never by trimming the title |
| hostednovel.com | scrapeable | server-rendered; story in `<div id="chapter-content">` (close by nesting count), title in `#chapter-title`; chapter URLs `/novel/<slug>/chapter-N` (no slug); TOC paginates `?page=N` at 100/page, but pages are CUMULATIVE (page 2 shows 1–200, not 201–300) — walk until a page yields no new numbers and union them. TOC links can be dead: probe every linked number with a cheap status check first (one book had live 550 beside dead 540/555/559), then scrape only the live set and record the real gaps; chapter URLs that 404 are removed uploads, not a broken URL builder. Liveness probes flap under rapid requests — a no-delay sweep reports live chapters as dead, so probe with a delay between requests and retry 404s with backoff before trusting a dead list. Long chapters split as dot-suffixed parts (`chapter-610.1`, `.2`, sometimes `.3`) with no bare page, or bare + `.2` where the bare page's title ends `(1)` — enumerate every href shape from the TOC, never bare integers alone. Where a bare page coexists with suffixed parts, the bare page is Part 1: header `Chapter N (Part 1)` / `(Part 2)`, and strip the site's own `(1)`/`(2)` title markers, or every header doubles its numbering |
| 18.foxaholic.com | scrapeable (WordPress Madara + Cloudflare) | CF auto-clears in Safari (may need a Turnstile click); TOC renders via AJAX (wait for 150+ links); story in `.reading-content` innerText, which also holds the translator's spin-off promo as its first paragraph — strip it (verified identical first paragraph in every chapter); titles from `document.title` (`Chapter N: Title - Foxaholic 18`); verify a hand-built URL list by hash against the live TOC |
| shanghaifantasy.com | scrapeable | WordPress: series page carries almost no chapter links — read the TOC from the REST API `fiction/v1/chapters?category=<id>&order=asc` (the id is the series page's `data-cat` on `#chapterList`; page with `per_page`, totals in `X-WP-Total`/`X-WP-TotalPages`). Story in `div.contenta` (plain `<p>`, no hooks) with template furniture *inside* the container: a rating plea first, the real title second (`Chapter N: Title` — the only title source, keep it), then story, then donation plea + ko-fi line + `Next`/nav bleed + translator sign-off last; strip positionally, keep `^Translated by` line-anchored sweeps. Split finales share one number (`chapter-500-1`, `chapter-500-2`) — write one file per part, never let the second overwrite the first; per-book scraper `scrape_shf.py` kept next to the book |
| wuxiaworld.site | scrapeable (Madara clone, AJAX-only chapter list) | the chapter list never reaches the HTML — walk next-links from ch1 (the walk IS the TOC, keep `.url` sidecars); untitled chapters get bare `# Chapter N`; readnovelfull mirrors the same translations (full TOC via `/ajax/chapter-archive?novelId=`) |
| novellunar.com | scrapeable (Next.js + Cloudflare) | curl 403s; clear Turnstile in Safari (click Verify-you-are-human), then in-page fetch batches off the cleared session — story is `article` innerText, titles from `<title>` in `Chapter N: Title` / `Chapter N Title:` shapes, html-unescape bodies |
| brightnovels.com | scrapeable (Inertia.js SPA) | series page is a shell — TOC is JSON at `/series/<slug>/chapters/free` (`total` + `chapters` array with bare-number slugs; check `is_premium` flags, a free-listed chapter can still be teaser-locked); chapter page `/series/<slug>/<chapterSlug>` carries the story in the `data-page` JSON attr (`props.chapter.content` HTML, first `<p>` echoes the title — drop it, keep `props.chapter.title`); per-book scraper `scrape_bright.py` kept next to the book. Some uploads wrap paragraphs in `<span>` blocks separated by blank lines instead of `<p>` (7 chapters of one book) — fall back to `<span[^>]*>` then to tag-strip + blank-line split, or those chapters report 'no paragraphs extracted' forever. Rate-limits aggressively at 0.5s pace (dozens of HTTP 429s across a full run, roughly every 15th request) — keep the scraper's sleep env-overridable and re-run resume-style at 2-3s to fill the 429 gaps. Empty-page misses on the same run are usually 429-challenge pages, not locks — verify `is_premium` before treating them as locked |

`novellive.app`-hosted titles that were successfully re-sourced from wuxiaworld lite:
The Novel's Extra, A Villain's Will to Survive. Walker + renamer script:
`scrape_ww.py` in the per-book fixer directory (the books tree — see the
`webnovel-library` catalog page for its location).

`discover_max` must probe past the highest linked chapter (3205 here; 3206 404s),
and the series is often still ongoing, so "completed" in a search snippet is not
a chapter count.

## API-backed sites: read the JS bundle before writing a scraper

Some series sites are SPA shells — the series page returns 200 with no chapter
links, and every `<p class=...>` on it is nav furniture. Before concluding
"blocked/unscrapable", check whether the story is already embedded in the
page itself: Inertia/Livewire shells carry full page props in a `data-page`
JSON attribute (inner quotes are HTML-escaped, so scan to the next raw `"`,
then unescape and parse — chapter text usually sits at
`props.chapter.content`), Nuxt in `__NUXT_DATA__`. Only when the payload is
not in the page, fetch the page's `<script type="module">` bundle and grep
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
recover. Fan out `delegate_task` with one agent per ~10 chapters — unless the
user asked for no delegation/dispatch, in which case generate the titles
directly in-session in small batches instead of fanning out: a fan-out against
an explicit no-dispatch request wastes the session and produces nothing usable.
Each agent
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

**Chapters must end up titled — bare `# Chapter N` is a defect, not an
acceptable output.** Recover from every source first (index, headings,
`<title>`, single-word lead lines like `Prologue`), generate for the rest,
hand-name whatever the generator fails after retries, and leave bare only
chapters whose generated title duplicates an earlier one.

**Local-LLM generation (no delegation):** drive a local OpenAI-compatible
endpoint (LM Studio) sequentially or at most 2-way parallel — 6 concurrent
requests stampeded the server into mass failures, and thinking models burn
~1 min of reasoning per 3-word title, so budget ~1 title/min. Shrink excerpts
(~350 head + 100 tail words) to cut thinking time and empty responses; retry
empties with higher temperature before giving up on a chapter. Validate every
response (non-empty, ≤8 words, not numeric, not echoing `Chapter N`) and
append to the TSV immediately with fsync — a stalled pool must never take
finished titles with it.

**Generator and applier must share ONE canonical key function.** A `file_key`
that returns `N` for slugged names but the full basename for bare ones writes
TSV keys the applier never matches — one run applied 50 of 916 titles with
zero errors. Normalize both sides to the same key space (or match on a
candidate set) and assert applied-count equals loaded-count minus rejects
before calling the pass done.

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
             Pages may REPEAT only-known numbers while later pages still hold
             new ones (a 372-chapter block hid behind one all-known page),
             and pagination can CYCLE (pages 39-60 repeat pages 1-21), so stop
             only on an empty page or several consecutive stale pages, never
             on the first no-new page. The index can also simply OMIT upload
             ranges (169 chapters missing from every page) while prev/next
             nav chains through them -- when a solid block is absent from all
             pages, walk prev_chap links backward from a live chapter above
             the hole; the walk IS the TOC (keep `.url` sidecars).
             Never stop at the first page that yields no NEW numbers: one book
             hid a 372-chapter block behind a single all-known page, and another
             cycles old ranges back in (pages 39+ repeat pages 1+). Tolerate a
             few stale pages (3) and stop only on an empty page or repeated
             staleness.
    URL    : three shapes, all real:
               chapter-63.html                         (no slug)   x67
               chapter-1-mt-yellows-true-monarch.html  (dash+slug) x3097
               chapter-71tearing-down-a-building.html  (NO dash)   x1
             Use `chapter-(\d+)-?[^"]+\.html` and keep the FULL href. Requiring
             the dash loses 67; rebuilding the path from a dash/space-swapped
             display title 404s. `－`? see below — the shapes above are exact.
             A fourth shape is decimal splits with the dot dropped:
             `chapter-2041.html` serves "Chapter 204.1" (35 such groups on
             one book, up to 3 parts). The served `<title>` keeps the dot,
             so it -- not the URL -- decodes (N, P); file as `chapter-N-P`
             so the numeric sort orders parts, header `Chapter N (Part P)`
             with the heading's own "(part P)" suffix peeled.

**Numbering drifts from the URL.** From ~ch2962 the site's own numbering is
offset by two (URL `chapter-2962` serves "Chapter 2960") and the offset grows.
The body keeps the site's title, so combining it with the TOC slug produces a
doubled header: `# Chapter 2962: Chapter 2960: Teaming Up with Top Tycoons`.
The file number and the printed number are both legitimate — trust the URL for
ordering, the body for the title, and never concatenate both. 206 chapters were
affected; a `h.count('Chapter') > 1` check finds every one.

**A TOC gap is a never-uploaded chapter only with three signals.** The TOC
skipping a number plus a 404 on its bare URL is not enough — confirm with the
site's own prev/next navigation (fetch the live neighbors: ch541's Next links
straight to ch543) and a seam read (tail of N-1 into head of N+1, past any
watermark lines sitting at the tail). One book had 7 such gaps (542, 545, 548,
586, 852, 887, 955); all three signals agreed on every one, so they were
recorded as real gaps, not grafted. But a bare-URL 404 alone proves nothing on
hosts where even live chapters 404 bare — one book's whole 2062..2230 range
404'd bare including chapters that existed under titled slugs, so gate the
404 signal on a live control (a known-present chapter must 200 on the same
URL shape) before trusting it.

**When the index itself is incomplete, the prev/next chain is the true TOC.**
One book's index omitted a contiguous 169-chapter block that all existed:
the last chapter's Prev link named a page the index never listed, and walking
`prev_chap` backward from there recovered every URL in order. So treat a big
apparent hole as suspect until the chain is walked — fetch the highest live
chapter, follow `prev_chap` down into known territory, and scrape the walked
URLs (they often carry titled slugs the index lacks). Conversely, neighbors
linking straight to each other across a number (1109's Next -> 1111 and
1111's Prev -> 1109) confirms a true never-uploaded gap even when the bare
URL 404s everywhere by default on that host.

**Same chapter under two URL shapes: keep the titled slug.** Bare
`chapter-925.html` and slugged `chapter-925-the-origins-of-the-dao-tree.html`
can serve the same chapter (142 such pairs on one book); the slugged variant
carries the real heading and cleaner typography. Dedupe by body diff (expect
~0.99+), keep the longer header, and check the low-ratio pairs by hand — one
0.01 pair was two genuinely different chapters sharing the number `1100`,
resolved by the site's own prev/next links (the true 1100 sits between 1099
and 1101; the orphan keeps its content under a marked `(Duplicate Numbering)`
header, never silently dropped).

**Real gaps are still recoverable from same-numbering mirrors — verify the
graft four ways before inserting.** novelcool shares novelfull's chapter
numbering, so a gap there may exist here: 5 of 7 above were recovered this way. Read the exact chapter URLs off a chapter page's picker dropdown/nav — the series index omits the very chapters being hunted, the dropdown lists them.
For each candidate chapter: (1) prove the same translation — diff a chapter
both sites carry and require identical wording down to quirks (`Its`/`Weve`
without apostrophes); a different translation grafted in reads as a forgery.
(2) prove slot integrity — diff the candidate against both neighbors, because
a mirror's slot can be a mislabeled duplicate of the next chapter (98.8%
identical text); (3) seam-read both sides, tail of N-1 into candidate head and
candidate tail into head of N+1; (4) after grafting, assert zero shared
10-grams with either neighbor as the anti-duplication proof. Append the
mirror URLs to `chapter_urls.txt` so resume skips them and the provenance is
auditable, then repackage all three formats. (5) confirm the slot actually
serves the expected chapter — one mirror's `chapter-852` URL served chapter
849's text under an 849 title, so a live URL and a matching number prove
nothing until the body is diffed against the neighbors. Check the served
page's `<title>` AND its og:url/canonical AND the body against each other:
all three must agree, and the body must match neither neighbor.

**Align mirrors by content, not by number.** A mirror's numbering can be
shifted relative to yours, so a title mismatch on the same number does not by
itself prove a scrambled slot. When the candidate's title disagrees with your
numbering, diff its body against your N-3..N+3 neighbors: a content match at
an offset means a shifted mirror (map by content from there); a match with
nothing nearby means a corrupt slot, reject it.

**A cross-translation graft is a placeholder, not a fill.** When the only
source is a different MTL pipeline (systematic tells like `Lingmo` vs
`Ling Mo` name spacing, cruder voice), normalize names mechanically
longest-first, cut promo tails, and record the provenance caveat in the
catalog entry so a future same-translation source replaces it. A same-family
gap stays open; a cross-family graft closes it provisionally — never silently.

**A gap sometimes needs no graft because the content merged into a neighbor.**
Suspect this when the seam reads continuous mid-explanation. Verify against
another edition of the same novel (even another language): if the foreign
chapter spanning the gap opens and closes on exactly the lines your two
neighbors open and close on, the number was skipped with content intact —
record a numbering skip, do not graft. Back off aggregators that 429 — one
gentle fetch per several minutes, not a retry loop.

**Judge junk hits in context.** This book produced: "copyright" (a skill in the
story), "reply to" (dialogue), a wikipedia URL in a `[TL: ...]` translator note,
"monthly pass"/"subscribe" (characters discussing web novels ON PAGE — the author
is writing about novel site rankings), and fullwidth `＊＊＊＊＊` scene dividers.
All legitimate. Only the ad iframes were real.

**Translator credits also come in sentence form.** Besides `Translator: X`
labels, uploads open the chapter with `Translated by X` as the first body
paragraph — a `^Translator` line-start filter never fires on it, so it ships
in every chapter. Sweep `^Translated by\b` paragraph-starts before packaging;
keep the match line-anchored, since only paragraph-initial position marks it
as furniture rather than prose. Same sweep: a lone `#` paragraph sitting just
before the copyright line is an ad-slot placeholder, never story — drop it.

**Strip translator end-markers that echo the chapter's own title.** Some uploads
close chapters with `< {title} > Fin.`, repeating that chapter's title inside
angle brackets — template furniture, not an epigraph. Drop a trailing paragraph
matching `^<.+>\s*(Fin\.)?$` when its inner text echoes the chapter title.
But a bare `Fin.` with no brackets on the genuine final chapter is the real
ending marker — judge it in context and keep it.

## Pitfalls that cost real time

- **Chapter URLs need the series prefix.** The series page links are
  `https://site.com/series/<series-slug>/chapter-N-title`, but a naive regex
  reduced them to `m/chapter-N-...` and every request 404'd. Always print the
  first constructed URL and `curl -o /dev/null -w "%{http_code}"` it before a
  long run. A 404-everything scrape looks like "blocked site" — it's a broken
  URL builder.
- **A run logging systematic 404s on one URL shape is enumerating wrong, not fetching wrong.** Every miss burns full retry backoff, so a few hundred part-only numbers turn a minutes-long run into an hours-long one. Kill it, confirm liveness per URL with cheap status checks (delay + retries), and re-drive the scraper off the confirmed-live URL list — resume skips what is already on disk, so nothing fetched is lost.
- **A reboot mid-run loses everything** unless the scraper resumes. Skip
  chapters whose `.md` already exists; then re-running after any interruption
  is safe and cheap.
- **Anti-piracy watermarks also come as plain-English promo paragraphs.**
  A dozen fixed sentences (`We are "NovelFull.com", find us on google.`,
  `Theft is never good, try looking at NovelFull.com.`, ...) plus the bare
  domain glued to story paragraph ends (`...for me.NovelFull.com`, sometimes
  doubled as `NovelFull.cominnread.com`). Strip trailing tokens keeping the
  story's own punctuation, drop whole paragraphs whose remainder is only
  promo shell, and guard translator footnote URLs (rebirth.online refs,
  wikipedia) that must survive. Always re-sweep the CHAPTER files for the
  domain after cleaning -- one sweep silently missed 185 hits and they
  shipped into all three formats.
- **Key the resume guard on URL identity, not filename prefix.** A check like
  `chapter-118(-|\.|$)` also matches the split-part file `chapter-118-1-...`,
  so the whole chapter 118 is skipped forever once its part exists — 6 chapters
  silently never fetched on one run. Log every successfully fetched URL to
  `out/.fetched.txt` and resume off that set; use filename matching only as a
  backstop for runs predating the log, and then on exact `(N, P)` keys, never
  prefixes.
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
- **The cleaner's file-selection glob must accept the same shapes as the
  filename regex.** Fixing `chap_num` while leaving a slugged-names-only glob
  makes the clean pass silently skip every bare and part-suffixed file — a run
  reporting `touched 7 of 421` on an 897-file directory reads as a clean book
  while most of it was never examined. The glob is `chapter-\d+(?:-.*)?\.md`;
  after any filename-convention change, re-run the cleaner and check its `of N`
  denominator against the directory file count. Bare `chapter-51.html.md`
  (no slug) is the shape that exposes this — the slugged-names-only glob
  skips it while the number regex parses it fine.
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
- **A batch header/content repair must prove the bodies survived.** A
  `re.match(r'(# ...)(.*)', full_text)` without DOTALL captures only the first
  line, so writing back `group(1) + group(2)` keeps every header perfect while
  deleting every body — 196 chapters gutted with a clean-looking diff. After
  any batch repair, assert total word count across `out/` is unchanged (within
  the edit's tolerance) before calling it done; operate line-wise or with
  DOTALL, and spot-read one repaired file top to bottom.
- **A repair script must be idempotent.** After one applied run, re-running
  reported "0 changed" while a stale header from the earlier buggy run was
  still wrong, because the guard only matched *bare* headers. Match the defect
  (any embedded `Ch.N` marker), not just the first-run symptom, and re-run until
  it reports no changes.
- **Order a transliteration table longest-first.** `pdf_sanitize` maps run in
  sequence, so a single-character entry (`人` -> `ren`) fires inside longer
  entries containing it and breaks their exact match — the longer fragments
  then sail through unmapped and the PDF still warns. Put multi-character
  terms before any of their substrings.
- **Detect obfuscation with NFD + diacritic-strip, not NFKC.** NFKC keeps
  precomposed letters (`ē` stays `ē`), so a homoglyph scan built on it misses
  every macron-vowel variant. Normalize with NFD, drop `Mn`/`Me`, then map —
  and run table lookup AFTER casefold (or carry both cases): casefold turns an
  unmapped capital (`Ꞩ`) into a mapped small (`ꞩ`) only if lookup already ran,
  the capital sails through.
- **Delete `.bak` files before any glob-based step.** `glob('out/chapter-*.md')`
  does NOT match `chapter-16-x.md.bak`, but a looser `glob('out/chapter-*')`
  does — and then every chapter is processed twice, showing duplicate headers
  and double-counting every metric. Symptom: chapter count reported higher than
  the unique chapter numbers, with two files claiming the same number.
- **A lone `***` line is a scene divider, not leftover markdown.** It survives
  the `**`-emphasis sweep by design and shows up as a "literal **" hit in the
  final check. Do not chase it.
- **Probe the mirror's series page before hunting gaps on it.** A 404 or
  placeholder title on the series URL means that host does not carry the
  series at all, so per-chapter probing there is wasted requests — gate each
  mirror on series existence first and spend chapter-level probes only on
  hosts that list the book.
- **Know when a gap hunt is over.** If no same-translation mirror carries the
  series, the translation is marked complete by its own translator, every seam
  reads continuous, and the finale is present, the numbers are skipped uploads,
  not missing content — record them and stop hunting. Do not machine-translate
  the raw to fill the hole: an MTL graft in a different voice reads as a
  forgery next to a human translation, and the seam continuity already proves
  nothing is absent.
- **Run chapter headers through the same `pdf_sanitize` as body paragraphs.**
  Headers render on a separate code path (bold font), so CJK there warns
  even after the body pass is fully mapped — verify with the sanitize
  function itself over every line including headers, and drive its unmapped
  set to zero rather than eyeballing the build log.
- **CJK kaomoji are story content — transliterate, don't strip.** Emoticons
  built from CJK presentation forms (`o(一︿一+)o`, `(⊙﹏⊙)`, `(︶︹︺)`)
  arrive as character dialogue, and DejaVu has no glyphs for them, so the PDF
  renders blanks with missing-glyph warnings. Map them to ASCII lookalikes
  in the PDF render path only, so txt/epub keep the originals — same doctrine
  as `pdf_sanitize`. They are content, not watermarks: never let a CJK sweep
  delete them.
- **A same-slug catalog row from another site is a different book until the
  bodies are diffed.** Before rewriting or deleting a catalog row as stale,
  check the books directory for the actual artifacts and diff chapter text:
  identical titles and chapter-1 header styling coincide across translations
  while full-text difflib scores near zero. Never drop a row whose book is
  complete on disk.
- **Verify a user-supplied HTML save before trusting its filename.** A 429 page
  and a wrong-chapter save both arrived wearing the right filename. Check the
  `<title>` tag, the og:url/canonical URL, and diff the body text against the
  neighboring chapters — a same-numbered chapter from another mirror can also
  be a wholly different translation (full-text difflib ratio near zero,
  telltale name-segmentation differences like `Lingmo` vs `Ling Mo`), which
  reads as a forgery grafted into the book. Reject on mismatch.
- **Count URLs in the epub against known xmlns declarations.** A sweep for
  `https?://` reports ~3 hits per chapter file, all of them
  `http://www.w3.org/1999/xhtml` and the EPUB vocab URIs in the boilerplate
  head. Verify against the epub source before calling it contamination.
- **Recompute library index totals from the table after every row change.**
  The header line (series count, chapter sum, word sum) drifts within a
  session or two of hand edits — recompute all three from the rows and assert
  the row count equals the book-directory count before calling the catalog
  done. A stale total beside a correct row is the next session's false
  confident.
- **Inserting a catalog row by string-replacing the last row deletes it.**
  Anchor the edit on the existing final row and include that row unchanged in
  BOTH the old and new strings, then assert the row count grew by exactly
  one — a patch whose new string holds only the added row silently eats its
  anchor, and re-adding the lost row from memory risks stale numbers.

## Pipeline

0. **Check for an existing completed run first.** Before fetching anything,
   list `$HOME/books/<series-slug>/`: if `book.txt`/`book.epub`/`book.pdf`
   plus a full `out/` already exist, verify them (step 6 checks) instead of
   re-scraping — a repeat request for the same series is usually a re-ask,
   not a new scrape, and a full re-run burns thousands of requests for
   nothing.
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
   page count + last-page text in pdf. Recompute word counts and byte sizes
   from the final artifacts in this same pass — numbers carried forward from
   mid-run outputs go stale across repair/repackage cycles.
7. **Move out of scratch** — scratch is pruned after 24h idle. Keep deliverables
   plus the scripts somewhere durable so a re-run can pick up new chapters.

## Scripts

- `scripts/make_pdf.py <dir> [title] [source-site] [--chunk=N]` — chunked
  weasyprint render + pypdf merge.
- `scripts/make_pdf_fpdf2.py <dir> [title]` — fpdf2 + DejaVu fallback for
  boxes without libpangoft2 (weasyprint cannot load). Produces the same
  book.pdf; sanitize is render-path only, txt/epub keep originals.
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

**PDF backend selection.** weasyprint needs libpangoft2, which is absent on this
box (and on the user's Box). When `import weasyprint` fails with
`cannot load library 'libpangoft2-1.0-0'`, do NOT install pango or fight the
system package manager — run `make_pdf_fpdf2.py` (fpdf2 + DejaVu) instead. It
reads the same `out/chapter-*.md` layout and emits the same `book.pdf`; its
`pdf_sanitize` transliterates only in the render path, so txt/epub keep the
originals. Both scripts run under the epubenv python, not system python.

## Notes

- Respect the site's terms and rate: this pipeline sleeps 0.5s per request
  (~9 chapters/sec), which is polite for a full-series fetch.
- Word-count delta is the best junk detector: contaminated run 2.0M words,
  clean run 1.31M for the same 1076 chapters (~25-33% per chapter removed).
- Deliverables convention: `$HOME/books/<series-slug>/` with `book.pdf`,
  `book.epub`, `book.txt`, `out/` and the three scripts.