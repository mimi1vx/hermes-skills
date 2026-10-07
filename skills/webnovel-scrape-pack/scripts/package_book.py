#!/usr/bin/env python3
"""Package scraped chapter .md files into a combined txt and an epub.

Usage:  python3 package_book.py <book-dir> [title] [source-site]

Chapters are ordered NUMERICALLY (chapter-1, chapter-2, ... chapter-1076);
plain lexicographic sort puts chapter-1000 before chapter-100.

source-site goes on the title page and is REQUIRED in practice: the same
scripts are reused across nobadnovel / freewebnovel / novelrare, and a
hardcoded site name ships a false provenance line. Defaults to
$SCRAPE_SOURCE, then to "the web" rather than inventing a domain.
"""
import os
import re
import sys
import glob
import html as html_mod

DEFAULT_SOURCE = os.environ.get("SCRAPE_SOURCE") or "the web"


def chap_num(fname):
    # Accept both `chapter-12-slug.md` and zero-padded `chapter-0012.md`:
    # different scrapers name chapters differently, and a required trailing
    # dash made every file sort as 10**9 (and print CHAPTER 1000000000).
    m = re.search(r"chapter-(\d+)(?:-|\.|$)", fname)
    return int(m.group(1)) if m else 10 ** 9


def load(bookdir):
    files = sorted(glob.glob(os.path.join(bookdir, "out", "*.md")),
                   key=lambda f: chap_num(os.path.basename(f)))
    chapters = []
    for f in files:
        body = open(f, encoding="utf-8").read().strip()
        m = re.match(r"#\s*(.*?)\n", body)
        title = m.group(1).strip() if m else os.path.basename(f)
        text = body[m.end():].strip() if m else body
        chapters.append((chap_num(f), title, text))
    return chapters


def write_txt(chapters, path, title, source=DEFAULT_SOURCE):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{title}\n\nscraped from {source}\n")
        for num, ctitle, text in chapters:
            f.write(f"\n\n{'=' * 60}\nCHAPTER {num}\n{'=' * 60}\n\n{ctitle}\n\n{text}\n")
    print(f"[txt] {path} ({os.path.getsize(path) // 1024} KB, {len(chapters)} chapters)")


def write_epub(chapters, path, title):
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier(os.path.basename(path))
    book.set_title(title)
    book.set_language("en")
    book.add_author("Unknown")

    items, toc = [], []
    for num, ctitle, text in chapters:
        c = epub.EpubHtml(title=ctitle, file_name=f"ch{num:05d}.xhtml", lang="en")
        paras = [p for p in text.split("\n") if p.strip()]
        c.content = "<h1>" + html_mod.escape(ctitle) + "</h1>" + "".join(
            "<p>" + html_mod.escape(p) + "</p>" for p in paras)
        book.add_item(c)
        items.append(c)
        toc.append(c)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["ncx", "nav"] + items
    epub.write_epub(path, book, {"ignore_ncx": True})
    print(f"[epub] {path} ({os.path.getsize(path) // 1024} KB, {len(items)} chapters)")


def main():
    bookdir = sys.argv[1] if len(sys.argv) > 1 else "."
    title = sys.argv[2] if len(sys.argv) > 2 else "Web Novel"
    chapters = load(bookdir)
    words = sum(len(t.split()) for _, _, t in chapters)
    print(f"[package] {len(chapters)} chapters, {words:,} words")
    base = os.path.join(bookdir, "book")
    source = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SOURCE
    write_txt(chapters, base + ".txt", title, source)
    write_epub(chapters, base + ".epub", title)


if __name__ == "__main__":
    main()