#!/usr/bin/env python3
"""Render scraped chapter .md files to a single PDF with weasyprint.

Usage:  python3 make_pdf.py <book-dir> [title] [source-site] [--chunk=N]

A5 pages, justified text, page break before every chapter, cover page.
Verify the result with pypdf -- PDF 1.7 compresses object streams so grepping
the bytes for /Type /Page finds nothing in a valid file.

The source site is a positional argument, never a constant: one script serves
several novel sites and a hardcoded name puts a false domain on the cover.
Defaults to $SCRAPE_SOURCE, then to "the web".

Renders in CHUNKS and merges. weasyprint builds the whole document tree (and
the PDF) in memory, so a single-shot build of a 2,900k-word novel died at the
cgroup OOM killer holding ~2.9 GB. Per-chunk rendering keeps peak RSS flat at
the cost of one pypdf merge pass over the parts.
"""
import os
import re
import sys
import glob
import html as html_mod

DEFAULT_SOURCE = os.environ.get("SCRAPE_SOURCE") or "the web"
DEFAULT_CHUNK = 60

CSS = """
@page { size: A5; margin: 2.2cm 1.8cm; }
body { font-family: serif; font-size: 10pt; line-height: 1.5; }
.cover { page: cover; }
@page cover { margin: 0; }
.titlepage { text-align: center; font-size: 22pt; margin-top: 6cm; }
.chapter { page-break-before: always; }
.chapter:first-child { page-break-before: avoid; }
.chapter h2 { font-size: 13pt; margin-bottom: 1em; }
p { margin: 0 0 0.9em 0; text-align: justify; }
"""


def chap_num(fname):
    m = re.search(r"chapter-(\d+)-", fname)
    return int(m.group(1)) if m else 10 ** 9


def cover_html(title, source):
    return (f'<div class="cover"><h1 class="titlepage">'
            f'{html_mod.escape(title)}</h1>'
            f'<p style="text-align:center">scraped from '
            f'{html_mod.escape(source)}</p></div>')


def chapter_html(path):
    raw = open(path, encoding="utf-8").read().strip()
    m = re.match(r"#\s*(.*?)\n", raw)
    num = chap_num(os.path.basename(path))
    ctitle = html_mod.escape(m.group(1).strip()) if m else os.path.basename(path)
    text = raw[m.end():].strip() if m else raw
    paras = "".join("<p>" + html_mod.escape(p) + "</p>"
                    for p in text.split("\n") if p.strip())
    return f'<div class="chapter"><h2>Chapter {num} &middot; {ctitle}</h2>{paras}</div>'


def render(html_str, path, base_url):
    from weasyprint import HTML
    HTML(string=html_str, base_url=base_url).write_pdf(path)


def main():
    args = sys.argv[1:]
    chunk = DEFAULT_CHUNK
    args = [a for a in args if not a.startswith("--chunk")]
    for a in sys.argv[1:]:
        if a.startswith("--chunk="):
            chunk = int(a.split("=", 1)[1])
    if not args:
        sys.exit(__doc__)

    bookdir = args[0] if len(args) > 0 else "."
    title = args[1] if len(args) > 1 else "Web Novel"
    source = args[2] if len(args) > 2 else DEFAULT_SOURCE
    out = os.path.join(bookdir, "book.pdf")
    parts_dir = os.path.join(bookdir, ".pdfparts")
    os.makedirs(parts_dir, exist_ok=True)

    files = sorted(glob.glob(os.path.join(bookdir, "out", "*.md")),
                   key=lambda f: chap_num(os.path.basename(f)))
    print(f"[pdf] {len(files)} chapters, {chunk} per chunk", flush=True)

    doc_head = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
                + CSS + "</style></head><body>")
    nparts = 0
    for start in range(0, len(files), chunk):
        batch = files[start:start + chunk]
        pieces = [chapter_html(f) for f in batch]
        if start == 0:
            pieces.insert(0, cover_html(title, source))
        part = os.path.join(parts_dir, f"part-{nparts:05d}.pdf")
        render(doc_head + "".join(pieces) + "</body></html>", part, bookdir)
        nparts += 1
        print(f"  [pdf] {min(start + chunk, len(files))}/{len(files)} "
              f"-> part {nparts}", flush=True)

    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    pages = 0
    for i in range(nparts):
        with open(os.path.join(parts_dir, f"part-{i:05d}.pdf"), "rb") as f:
            r = PdfReader(f)
            pages += len(r.pages)
            for p in r.pages:
                w.add_page(p)
        print(f"  [merge] {i + 1}/{nparts}", flush=True)
    w.add_metadata({"/Title": title})
    with open(out, "wb") as f:
        w.write(f)
    for i in range(nparts):
        os.remove(os.path.join(parts_dir, f"part-{i:05d}.pdf"))
    os.rmdir(parts_dir)
    print(f"[pdf] wrote {out} ({os.path.getsize(out) // 1024} KB)")

    r = PdfReader(out)
    print(f"[verify] pages: {len(r.pages)} (merged parts said {pages})")
    print(f"[verify] last page: ...{r.pages[-1].extract_text()[-60:].strip()}")


if __name__ == "__main__":
    main()