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
  catches junk-contamination immediately.
- **Verify PDFs by parsing them** (`pypdf`), not by grepping the bytes — PDF
  1.7 compresses object streams, so `/Type /Page` regex finds nothing in a
  perfectly valid file.
- **Can't verify from a guessed slug** — a hand-typed chapter URL returns
  404/empty and looks like broken extraction. Read the real slug from
  `chapter_urls.txt`.

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

- `scripts/scrape_series.py <series-slug>` — TOC fetch, chapter scrape
  (scoped, resumable), verification summary.
- `scripts/package_book.py <dir>` — combined txt + epub, numeric order.
- `scripts/make_pdf.py <dir>` — weasyprint PDF, A5, page break per chapter.

Dependencies (not in system python; make a uv venv):

    uv venv epubenv && uv pip install -p epubenv/bin/python ebooklib weasyprint pypdf

## Notes

- Respect the site's terms and rate: this pipeline sleeps 0.5s per request
  (~9 chapters/sec), which is polite for a full-series fetch.
- Word-count delta is the best junk detector: contaminated run 2.0M words,
  clean run 1.31M for the same 1076 chapters (~25-33% per chapter removed).
- Deliverables convention: `$HOME/books/<series-slug>/` with `book.pdf`,
  `book.epub`, `book.txt`, `out/` and the three scripts.