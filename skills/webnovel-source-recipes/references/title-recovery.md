# Title recovery and clean-up ordering

Companion notes to the parent SKILL.md (which owns the class-level rules).
This file collects the ordering rules that decide *which* fixer runs when,
and the evidence order that decides whether an untitled chapter is
recoverable at all.

## The evidence order for a missing title

When a chapter is bare `# Chapter N`, check the sources in THIS order before
concluding the title does not exist:

1. **The chapter page** — `<h1>`, `<title>`, or a meta tag (freewebnovel's
   `og:novel:chapter_name`).
2. **The series index anchor text** — akknovel and nobadnovel only have
   titles here; see the parent SKILL.md's site entries for the marker shapes.
3. **The chapter's own first body paragraph** — many sites put the title card
   in-line (novelfull `Episode 1 – ...`, wuxiaworld `Chapter N: Title`).

Only after all three fail is a bare `# Chapter N` the correct, honest output.
On a 5-untitled-chapter book, 3 were recoverable from step 3 and 1 from step 1;
only 2 genuinely had no upstream title at all. Promoting a body title card
means: take the line verbatim, use the site's own header style on the other
files, drop the promoted line from the body so it is not duplicated, assert it
is short (<120 chars), and make the pass idempotent (a second run must report
0 changes).

A body line that reduces to only the chapter marker after stripping
(`Chapter 63:`) is proof the source has no title — strip the residue line and
keep the bare header. Never invent a title, and never leave the residue as a
lone body paragraph.

## Clean-up ordering: targeted fixer is never last

A one-off fixer (translator credits, a header mangling, a title promotion)
sees only the defect class it was written for. The shared
`clean_chapters.py` holds the site-furniture rules — separators, MTL notes,
author notes, watermarks — that nobody re-derives by hand, and they are spread
across the book rather than clustered.

Fixed order after any targeted fix:

1. Targeted fixer in dry run (it must print its change list).
2. Same fixer `--apply`; re-run dry to confirm 0 changes (idempotence).
3. `clean_chapters.py <book> --apply` — catches everything the fixer
   could not see.
4. `find out -name '*.bak' -delete`.
5. `package_book.py` → txt + epub, then `make_pdf.py`.
6. Verify the packaged artefacts, not just the chapter files (a repack can
   resurrect junk from a stale intermediate).

Measured on the library's longest book: the one-off cleared the 23 targeted
credit paragraphs, and the shared pass then caught 20 more stray lines
(16 separators, 7 ps-notes, 1 author-note) across 700 chapters.

## Quality complaints audit the whole shelf

A user reading a finished book finds defects no verifier caught — a verifier
checks counts and patterns, a reader finds repeated furniture and missing
names. When a quality complaint arrives:

- Sweep the named defect across **every** book on the shelf, not just the one
  named. A credit block that survived 3,165 chapters of a popular series exists
  in its siblings.
- Grep the credit domain as its own string — the scrape-host grep is exactly
  the check that misses a translator's own domain.
- Judge hits in context before deleting: text about copyright disputes,
  web-novel rankings, or monthly passes can be story content, not furniture.

