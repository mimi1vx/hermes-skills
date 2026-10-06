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
- **The junk check must exempt the title page.** `grep -ci Copyright\|<site>`
  hits line 3 — the provenance line you just wrote. Require the count to be
  exactly 1 for the site name, and inspect every other hit before calling it
  contamination.

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