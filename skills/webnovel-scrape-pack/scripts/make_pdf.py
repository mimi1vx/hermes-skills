#!/usr/bin/env python3
"""Render scraped chapter .md files to a single PDF with weasyprint.

Usage:  python3 make_pdf.py <book-dir> [title] [source-site]

A5 pages, justified text, page break before every chapter, cover page.
Verify the result with pypdf -- PDF 1.7 compresses object streams so grepping
the bytes for /Type /Page finds nothing in a valid file.

The source site is a positional argument, never a constant: one script serves
several novel sites and a hardcoded name puts a false domain on the cover.
Defaults to $SCRAPE_SOURCE, then to "the web".
"""
import os
import re
import sys
import glob
import html as html_mod

DEFAULT_SOURCE = os.environ.get("SCRAPE_SOURCE") or "the web"

CSS = """
@page { size: A5; margin: 2.2cm 1.8cm; }
body { font-family: serif; font-size: 10pt; line-height: 1.5; }
.cover { page: cover; }
@page cover { margin: 0; }
.titlepage { text-align: center; font-size: 22pt; margin-top: 6cm; }
.chapter { page-break-before: always; }
.chapter h2 { font-size: 13pt; margin-bottom: 1em; }
p { margin: 0 0 0.9em 0; text-align: justify; }
"""


def chap_num(fname):
    m = re.search(r"chapter-(\d+)-", fname)
    return int(m.group(1)) if m else 10 ** 9


def main():
    bookdir = sys.argv[1] if len(sys.argv) > 1 else "."
    title = sys.argv[2] if len(sys.argv) > 2 else "Web Novel"
    source = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SOURCE

    files = sorted(glob.glob(os.path.join(bookdir, "out", "*.md")),
                   key=lambda f: chap_num(os.path.basename(f)))
    print(f"[pdf] {len(files)} chapters")

    body = [f'<div class="cover"><h1 class="titlepage">{html_mod.escape(title)}</h1>'
            f'<p style="text-align:center">scraped from '
            f'{html_mod.escape(source)}</p></div>']
    for f in files:
        raw = open(f, encoding="utf-8").read().strip()
        m = re.match(r"#\s*(.*?)\n", raw)
        num = chap_num(os.path.basename(f))
        ctitle = html_mod.escape(m.group(1).strip()) if m else os.path.basename(f)
        text = raw[m.end():].strip() if m else raw
        paras = "".join("<p>" + html_mod.escape(p) + "</p>"
                        for p in text.split("\n") if p.strip())
        body.append(f'<div class="chapter"><h2>Chapter {num} &middot; {ctitle}</h2>{paras}</div>')

    doc = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
           + CSS + "</style></head><body>" + "".join(body) + "</body></html>")
    out = os.path.join(bookdir, "book.pdf")
    from weasyprint import HTML
    HTML(string=doc, base_url=bookdir).write_pdf(out)
    print(f"[pdf] wrote {out} ({os.path.getsize(out) // 1024} KB)")

    from pypdf import PdfReader
    r = PdfReader(out)
    print(f"[verify] pages: {len(r.pages)}")
    print(f"[verify] last page: ...{r.pages[-1].extract_text()[-60:].strip()}")


if __name__ == "__main__":
    main()