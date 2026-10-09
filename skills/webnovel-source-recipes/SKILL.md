---
name: webnovel-source-recipes
description: "Use when scraping a webnovel from a known serial site."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [webnovel, scraping, selectors, toc, pagination]
    related_skills: [webnovel-scrape-pack]
---

# Per-site extraction recipes

Companion to `webnovel-scrape-pack`, which owns the class-level rules
(contamination sweeps, packaging, watermark handling). This skill is the site
schema table — what you look up when a series URL arrives and you need to know
where the story lives, where the ads live, and how to enumerate chapters.

## When to Use

- A series URL on novelfull, hiraethtranslation (or any Madara/mangareader.to
  clone), akknovel, botitranslation, nobadnovel or freewebnovel arrives and you
  need the story selector, the ad selectors, and the TOC/pagination scheme
  before writing a scraper.
- A scrape of one of those sites produced plausible-but-wrong output — prose
  that turns into "Reply / 1 year ago", or a chapter count lower than the
  highest chapter number implies. Look up that site's entry for its trap.
- A TOC regex you just edited silently matches fewer links than before, and you
  need to know whether the book is actually short or the parser regressed. The
  verification rules below answer that without re-scraping.
- Not for deciding WHETHER to scrape, and not for packaging — see
  `webnovel-scrape-pack` for both.

## Always: inspect before writing a scraper

    python3 scripts/audit_chapters.py <book-dir>   # numbering, dupes, headers

Do this after the scrape and again after any header repair.

```bash
curl -sL -A "Mozilla/5.0 … Chrome/120.0" "$URL" -o page.html
grep -o '<p class="[^"]*"' page.html | sort | uniq -c   # paragraph census
grep -o 'chapter-[0-9]*' page.html | sort -u -V | tail  # chapter range
```

Two tells that a TOC is incomplete, both of which look fine at a glance:

- **Page 1 shows far fewer links than the highest chapter number implies.**
  (novelfull: 55 links, max chapter 3165.)
- **The series page has zero chapter links but returns 200.** The site is an
  SPA shell over an API — read the JS bundle for endpoints instead of hunting
  for markup that will never appear.

## Verify the TOC before trusting a resume-aware run

A resume-aware scraper skips chapters already on disk, so a broken TOC parser is
invisible: the files exist from earlier runs, and the summary still prints
`3165 / 3165, gaps=0`. Two independent checks, before and after:

1. **Print the TOC's own count and gap count before scraping** — gaps computed
   against the parser's own output are circular and prove nothing.
2. **Count unique chapter NUMBERS on disk** (not file count) and diff the two
   sets. Duplicate numbers and file-count-vs-unique-count disagreement are both
   real bugs; a matching file count alone hides them.

The nastiest variant of this is a regex that loses 65 links and a run that
reports success anyway. Check the parser against the live TOC before concluding
the book is complete, and re-check after every regex edit — a `gaps=0` line from
a resume run is not evidence the current code can find those chapters.

**A numbered TOC page with zero chapter links is not an error.** Mid-book pages
can serve full nav furniture while the chapter list has not flashed in. Treat a
zero-link page as "walk continues" only when that page's own pagination still
points past it, and as "end of TOC" when it does not. A 403 or 404 IS a stop;
a 200 with no links is ambiguous — resolve it from the `?page=` anchors on the
same page, not from the status code.
- **The series page has zero chapter links but returns 200.** The site is an
  SPA shell over an API — read the JS bundle for endpoints instead of hunting
  for markup that will never appear.

---

## novelfull.com

    TOC:    /<slug>.html?page=N     (N=1..64 on a 3k-chapter book; page 65 → 404)
    STORY:  <div id="chapter-content" class="chapter-c">
    ADS:    <iframe src="//ad.a-ads.com/…">  nested INSIDE the content div

**Close the content div by NESTING COUNT**, not by searching for the next
marker. The ad iframes are real `<div>` descendants, so a "cut at the next
`<hr>` / sibling div" approach either truncates the story or runs into the site
footer:

```python
i = page.find('<div id="chapter-content"'); j = page.find('>', i) + 1
depth, k = 1, j
while depth and k < len(page):
    nd, cd = page.find('<div', k), page.find('</div>', k)
    if cd == -1: break
    if nd != -1 and nd < cd: depth += 1; k = nd + 4
    else:        depth -= 1; k = cd + 6
seg = page[j:k - 6]                 # then drop <iframe>…</iframe>
```

**The TOC contains FOUR href shapes** in the same listing, and the boundary
between the number and the slug is unreliable in both directions:

    /<slug>/chapter-63.html                          bare, no slug        x66
    /<slug>/chapter-1-mt-yellows-true-monarch.html   dash + slug      x3097
    /<slug>/chapter-71tearing-down-a-building.html   NO dash + slug      x1
    /<slug>/chapter-2865(no-dash).html               dash + slug w/ parens

Make the whole slug segment optional AND capture the full href verbatim:

```python
CHAP_LINK = re.compile(rf'href="(/{re.escape(SLUG)}/chapter-(\d+)(?:-?[^"]+)?\.html)"')
```

Each half of that is load-bearing, and getting either wrong reads as a site gap
rather than a parser bug:

- a **mandatory** slug group drops all 66 bare `chapter-N.html` links — and note
  `(?:-?[^"]+)?` where the `-?` sits INSIDE an optional group is not the same
  thing as an optional slug, so re-test after any edit;
- requiring a dash before the slug drops the no-dash shapes;
- **never rebuild the path** from a dash/space-swapped display title. The
  slugs contain parens and doubled dashes, so the reconstruction 404s even
  though every component came from the TOC. Store the href and use it as-is.

Test the pattern against several pages, not page 1: the malformed links cluster
mid-book (ch63-66, ch641+), so page 1 shows no difference while the full walk
loses them. Diff old vs new link counts on pages 1, 2, 13 and 58.

**Translate credits glued INTO the heading on the same line.** Statement blocks
are sometimes stripped inside the same `<p>` that carries the title:
`Chapter 444: ConfessionTranslator: Atlas Studios Editor: Atlas Studios`.
The STAFF line-anchor guard misses it (it only matches lines STARTING with
'Translator:'), so glue leaks into the title field. Scrub with
`re.sub(r"(translator|editor)\s*:.*$", "", title, flags=re.I).strip()` on the
recovered title, and strip it from the paragraph text too.

**A heading repeated as the first paragraph is furniture, not prose.** Bonus
and epilogue pages often open the body with `Chapter 1432 Bonus Chapter: That
Corner (2)`, duplicating the H1 you just recovered. After title recovery, drop
any leading paragraph equal to (or a suffix of) the title. The check is
`paras[0].strip().lower() == title.strip().lower()`, repeated until it stops
matching.

**Some pages list credits BEFORE the heading.** Strip furniture paragraphs
before the heading match, then apply the title regex — otherwise the
`Chapter N: Title` paragraph is never first and the parse falls to a bare
`Chapter N` header.

**The TOC walk must stop on empty links, not status codes.** The end page
sometimes answers 403 rather than 404 (novelfull), and mid-book pages can
serve a full nav while returning zero chapter links. `if not links: break`
plus a `TOC_PAGES` hard cap is the robust walk; a status-code-only check
aborts the TOC or runs past the end.

**A TOC with one missing number is a SITE GAP, not a scraper bug.** Confirm it
before reporting the book incomplete:

    for u in chapter-N.html chapter-N-guess-slug.html; do
      curl -o /dev/null -w "$u %{http_code}\n" -A "$UA" "$BASE/$SLUG/$u"
    done

403/404 on every shape proves the chapter was never uploaded, not that your
parser dropped a link. Report the gap and source the chapter from a mirror
rather than re-running the scrape.

**A missing chapter leaves the book incomplete until it is filled from a
mirror.** Seed the recovered file with the same `<number>-<slug>.md` convention
the scraper emits (`chapter-1303-coming-to-life.html.md`) so packaging picks it
up without touching the scripts, and verify continuity at BOTH seams: the last
paragraph of chN must flow into the first of chN+1 (continued dialogue, a
completed thought). Two-sided confirmation is the proof you sourced the right
chapter and placed it correctly — a match at one seam only means the
neighbouring chapter is right.

**Headings can change shape between books in the same family.** A sequel on the
same host may drop the `Chapter N:` prefix entirely and use a bare
`N Title` (`1 Foreigners`, `500 “Nonexistent” City`) where the first book used
`Chapter 1: Crimson`. A title regex anchored on the word `Chapter` then fails on
the whole book: the title falls through to `<title>` (worse text) and the raw
heading line survives as the first body paragraph. Handle both shapes, and guard
the bare-number form so a sentence beginning with a year is not swallowed as a
title:

    CHAPTER_HEAD = re.compile(r"^\s*Chapter\s+(\d+)\s*[:.\-–]?\s*(.*)$", re.I)
    NUM_HEAD     = re.compile(r"^(\d{1,4})\s+(\S.*)$")   # "500 “Nonexistent” City"

Check the heading shape on 3-4 chapters spread across the book BEFORE the long
run, not just chapter 1 — a mid-book format change reads as one corrupt
paragraph rather than a parser bug.

**A duplicate-listing TOC can report success with all links present.**
Truly-broken TOC pages (JS chapter lists not yet flashed in) can serve a
similar page shape but enumerate only the FIRST 20 chapters. Print the per-
page chapter-number range (`ch[0]..ch[-1]`) during the walk and verify the last
page tops out at your max — a walk that ends at 1302 on a 1,432-chapter series
regressed silently.

**The printed chapter number drifts from the URL number.** From ~ch2962 the
site's own numbering is offset (URL `chapter-2962` serves "Chapter 2960") and
the drift grows. The body keeps the site's title and the TOC slug carries the
same one, so concatenating them produced `# Chapter 2962: Chapter 2960: Teaming
Up with Top Tycoons` across 206 chapters — invisible to word-count and
junk-string checks. Trust the URL for ordering, the body for the title, never
both; find every instance with `header.count('Chapter') > 1`.

**The page that ends the TOC walk does not exist.** Wrap it, or one uncaught
`HTTPError` aborts the run before a single chapter is written.

**Resume-aware scraping hides a broken TOC parser.** Chapters already on disk are
skipped, so a run whose regex now matches 65 fewer links still reports
`3165 / 3165, gaps=0` — the files came from earlier runs. Count unique chapter
numbers on disk separately, and print the TOC's own count and gaps BEFORE
scraping. Gaps computed against the parser's own output are circular.

**Give the scraper a `configure(slug)` that sets the module globals.** With
`SLUG`/`BASE` assigned inside `main()`, the module cannot be imported for a dry
TOC check (`NameError` on first use), so a verification script ends up
re-typing the regex — and a second copy of the pattern is exactly what drifts
from the first. Split the globals out and let the probe call the real `toc()`.

**Junk hits on this site are almost all legitimate.** Measured false positives:
"copyright" (a skill named in the story), "reply to" (dialogue), a wikipedia URL
inside a `[TL: …]` translator note, and "monthly pass"/"subscribe" — characters
discussing web novels ON PAGE, because the author writes about novel-site
rankings. Also fullwidth `＊＊＊＊＊` scene dividers, and a skill name in literal
angle brackets which is not markup. Only the ad iframes were real
contamination.

---

## hiraethtranslation.com — Madara / mangareader.to clones

~545 KB per chapter page, ~5 KB of it novel: ads, widgets, related-reading
carousels, a login modal, a wpdiscuz comment thread.

    STORY:  <div class="reading-content"> … <div class="text-left"> …
            <div class="entry-header footer">    <- chapter nav pager = CUT HERE
    ADS:    <div class="code-block">, bare <ins class="adsbygoogle">

- `class="reading-content"` also prefixes `reading-content-wrap` and
  `related-reading-content` (4 ad carousels at page bottom). A greedy capture
  runs into the comment thread and ingests `Reply`, usernames, `1 year ago`.
- `grep 'chapter-1'` matches `chapter-199`. Match `chapter-\d+/`, sort `-V`.
- The series index (750 KB) has **no** `<option>` rows. The picker with all
  titles lives on a CHAPTER page:
  `<option … chapter-N>Chapter N - Title</option>` — no `value="chapter-N"`,
  the URL is in `data-redirect`. Fetch chapter 1 once, dedupe with `setdefault`
  (it repeats across several selects).
- `<h1 id="chapter-heading">` is only "Book Title - Chapter N" — no title.
  Reject that shape (ends `Chapter N` after the book name), use the TOC.
- After adding title recovery to an already-scraped book, the resume guard only
  re-fetches BARE `# Chapter N` headers, so files still carrying the
  book-prefixed H1 look finished forever. Re-head them from the TOC rather than
  re-downloading the book.

---

## akknovel.com

    STORY:  <p class="mb-4 para">   (same class family as nobadnovel)

- The chapter page `<h1>`/`<title>` carries **no** title ("Book Name Chapter N").
  Titles exist only in the series index:
  `<span class="inline-block mr-3">Ch.53</span>Two Armies at War`.
  Print the raw inner HTML per row before trusting a strip-tags parser — the
  last chapter is wrapped in `Last chapter: &nbsp; Ch.334&nbsp; Final Chapter`,
  so the `Ch.N` marker must be stripped at any position or the header reads
  `Chapter 334 Last chapter: Ch.334 Final Chapter`.
- Site markup in the body: `<glossary_translation>` pseudo-tags around proper
  nouns, plus `**…**` / `[**…**]` emphasis. Read the censored-profanity rule in
  `webnovel-scrape-pack` before writing a stripper — `Bull****` must survive.
- Empty TOC title field → the index renders the chapter NUMBER as the title
  (`Ch.2` → `02`). Strip digits-only titles; `# Chapter 2 02` is worse than a
  bare `# Chapter 2`.

---

## Next.js SPA sites — read the FLIGHT PAYLOAD, not the JS bundle

NovelShelf and similar Next.js reader sites return 200 with the chapter list
and full text already in the HTML, but triple-escaped inside `self.__next_f`
flight chunks. Do NOT hunt for a REST API: the story is in the page.

```python
s = open(page, encoding="utf-8").read()
# Flight payloads are escaped up to 3x: \\\" , \\u003c , \\n
# strip in that order, then take the content-inner div
t = s.replace('\\\\u003c', '<').replace('\\u003c', '<')
# fix paragraphs and headings
t = t.replace('\\\\u003e', '>').replace('\\u003e', '>')
t = t.replace('\\\\\\\\\"', '"').replace('\\\"', '"')  # quotes last
i = t.find('content-inner')
end = t.find('INFOLINKS_OFF')  # infolinks marker, page-specific
# or locate the second flight chunk 'N:[...' or '</div>' followed by 'N:'
seg = t[i:end]
```

- **Search the FLIGHT PAGE for the embedded title metadata** before trusting
  a scraped one: the chunk `"chapter":{"id":N,"order":N+1,"title":"C.N+1 -
  Title"}` confirms both the title and the order in one grep on the raw page.
- **`order` may lag `id` by one** — chapter list entries are `order:1302,
  title:C.1303`, so the URL id is NOT the chapter number on this site.
  Derive chapter numbering from `order`, not the URL.
- **Verify continuity at the seam** before writing the file: the last
  paragraph of chN must flow into the first of chN+1 (dialogue that continues,
  a thought that completes). This is the proof the page is the right chapter
  and belongs at that position — a mismatch means you grabbed the wrong
  chapter, not that the text is corrupted.
- **Paragraph-separating `<br>` tags carry content.** The body is
  `<p>...</p><br><p>...</p>`, not a single `<p>`-less div. Split on `</p>` and
  discard `<br>` blocks.
- **The heading line repeats as the first paragraph** on this site
  (`Chapter 1303 Coming to Life` precedes the story). Drop it before writing.

---

## botitranslation.com — SPA over a public REST API

The series page is a JS shell. Find the endpoints from the bundle:

```bash
curl -s "$URL" | grep -o 'src="/assets/[^"]*\.js"'      # entry bundles
grep -o 'baseURL[^,;}]\{0,80\}' bundle.js
grep -o '`[^`]\{3,80\}`' bundle.js | grep -iE 'api|book|chapter'
```

    base  https://api.mystorywave.com/story-wave-backend/api/
    GET   v1/content/books/{id}
    GET   v1/content/books/{id}/firstChapter
    GET   v1/content/chapters/page?bookId=&pageNumber=&pageSize=&sortDirection=
    GET   v1/content/chapters/{id}            -> full text
    headers: site-domain: <hostname>, lang: en   (both required)

`authorNote` is a **separate** field — author notes are not inline in `content`,
so no cleanup pass is needed. Check the TOC's `tier` field, not just
`paywallStatus`: a chapter can read `free` and still be locked.

---

## nobadnovel.com / freewebnovel.com — reference schema

    STORY:  <p class="mb-4 para">

Confirm the classes are still separated:

```bash
grep -o '<p class="[^"]*"' page.html | sort | uniq -c
```

Chapter URLs need the `series/<series-slug>/` prefix; a regex that reduces them
to `/m/chapter-N-…` 404s every request, which reads as a blocked site rather
than a broken URL builder. Filenames carry a slug: `chapter-12-slug.md`.

### nobadnovel.com: titles only in the index anchor text

The index at `/series/<slug>` links every chapter as `/series/<slug>/chapter-N-slug`,
and the DISPLAY text of each `<a>` is the only place a title exists:
`C1. Old Qin, Do you want your apprentice`. The chapter page `<h1>`/`<title>` is
just `Book Title c1 - Snippet` — useless. So freewebnovel's
`og:novel:chapter_name` trick does NOT apply here; parse the index once and
re-head from it with a small script kept alongside the book.

The marker regex is the load-bearing part — the marker is
`<optional letters><digits><optional period>` with the letters sitting DIRECTLY
against the digits:

    LEAD = re.compile(r'^\s*(?:[A-Za-z]*\d+)(?:\.\s*)?', re.I)

Requiring whitespace between letter and digits, or requiring `ch`/`chapter`,
leaves every header reading `# C1. Old Qin...` — plausible-looking, and it
ships. Verify with a census after the pass:
`grep -lE '^# [A-Za-z]*[0-9]+[. ]' out/*.md | wc -l` must be 0.

Ch1's anchor wraps the cover `<img>` and a "Start Reading" button, so after
tag-stripping the recovered text is `Start Reading`, not a title. Skip known UI
labels (`start reading`, `read`, `continue`, `next chapter`) and keep the bare
`# Chapter 1` header — a bare header beats a button label. On a re-run, files
already canonical report as "kept" (509/521 on one book): that count is the
idempotence check, not a failure.

### freewebnovel.com: no slugged TOC, titles only in a per-chapter meta tag

This site breaks the pattern every other entry here relies on. The series index
exposes no slugged chapter list (only `og:novel:lastest_chapter_name`) and the
chapter URL carries no slug at all — `/novel/<slug>/chapter-1`. So a title
cannot be learned from the URL the way akknovel/noMadara/novelfull books do, and
a naive scrape leaves every file with a bare `# Chapter N`.

The title lives in one meta tag on the chapter page:

```bash
curl -sL -A "Mozilla/5.0 … Chrome/120.0" "$URL" \
  | grep -o '<meta property="og:novel:chapter_name" content="[^"]*"'
```

Its content drifts badly and must be normalised before it goes in a header:

    "Chapter 1: Nightmare Begins"
    "Chapter 3205 Three Heroes Faced a Dreadful Worm"   (no separator)
    "Chapter 1501 - 1305: Did you say…"                 (stale old number)
    "The 1309th Chapter: Calculating that…"            (ordinal word)
    "Special Chapter 1313: The Demoness: …"            (chapter-type word)
    "1307 Chapter The Demoness Feels Strange_2"        (reversed + _2 marker)

Peel any leading chapter label only when it is the WHOLE leading label and real
text follows (a `1305:` inside a title is content), strip a trailing `_2`/`-2`
(the site's duplicate marker), and let the SITE's title win over the URL number
— its numbering drifted from the URL numbering, so concatenating both yields
`# Chapter 2962: Chapter 2960: …` across hundreds of chapters. A title that is
only digits after normalisation carries no information: keep the bare header.

Two rules that keep the normaliser honest:

- **`clean()` must return the canonical string for an already-canonical header,
  not `None`.** A doubled header such as `# Chapter 1501: Chapter 1305: Title`
  *has* a recoverable title in it and must normalise to the de-doubled form;
  returning `None` for both cases silently leaves the doubling in place forever.
- **A header that already carries the site's title needs no re-fetch.** Use it
  as the fallback when the meta tag disagrees, and skip the request.

**This is a 3,000-request job — thread it at 2 workers, not 10.** A sequential run with a polite
`time.sleep(0.4)` between chapters takes over an hour for a 3.2k-chapter book; a
2-worker pool runs all 3,205 clean; ten parallel fetchers tripped the site's rate limit after ~1,200 requests (HTTP 403 on everything after). Keep the normaliser in ONE module and have
the parallel driver import it (a copy per script is how the two drift apart).

**Never let the fetcher report a transport error as 'no title'.** Return None ONLY when the page loaded fine but carries no meta tag; raise on HTTPError/429/5xx with backoff instead. A fetcher that swallows transport errors into None makes rate-limited chapters look untitled — one dry run reported 814 'missing' titles when every one of them existed on the site. Report fetch-failed and no-title-on-page as two separate counts, and treat any nonzero fetch-failed as a retry signal, not a result.

**A run without `--apply` is invisible on disk.** Fetching, normalising and the
progress counter all happen; zero bytes are written. File mtimes stay at the
scrape time and every header is still bare, so a finished dry run is
indistinguishable from a failed one. Judge it by stdout (`…250/3205`) and a
header census, and budget a SECOND full-length run for the `--apply` pass — it
re-fetches everything, there is no cache. `.bak` count 0 afterwards is the
expected end state of a successful apply (delete the backups after verifying),
not evidence that nothing ran.

## Deliverables convention

`$HOME/books/<series-slug>/` holding `book.pdf`, `book.epub`, `book.txt`,
`out/` (per-chapter markdown) and the scraper used, so a re-run can pick up new
chapters. Scratch is pruned after 24h idle — never leave the only copy there.

**Two traps when auditing a book directory for completeness:**

- **Naming drifts between packaging runs.** Earlier runs emitted
  `book_<series-slug>.txt` instead of `book.txt`. A glob for `book.txt` alone
  finds nothing and reads as "scraped but not packaged" — the book is sitting
  there at 8 MB with 1,076 chapters. Check both patterns before declaring a
  book unpackaged, and rename to the short form so one glob covers all books.
- **Packaging runs can drop stub artifacts inside `out/`.** An `out/book.txt`
  of a few paragraphs and an `out/book.epub` with an empty shelf are run
  residue, not the book. Only the top-level `book.*` files count; delete the
  out/ stubs so a chapter census doesn't inflate.

A finished-book check is: all three of `book.{txt,epub,pdf}` exist and are
non-empty, epub opens as a zip containing `mimetype`, pdf starts `%PDF-` and
ends `%%EOF`, and unique chapter numbers in `out/` are gapless against the max.

**Packaging needs a venv, and one is usually already on the box.** Look for
an existing packaging venv (ebooklib, weasyprint, pypdf installed) before
creating a new venv; a fresh `uv venv epubenv` under the book directory works
too, but reusing the existing one avoids a multi-hundred-MB reinstall per book.