#!/usr/bin/env python3
"""Reconcile a scraped book against its live TOC — the independent gate.

The pack verifier computes every number against the parser's own output, so a
book that lost most of its content to a number-keyed dedupe still prints
`gaps=0, errors=0, OK`. This script counts from two INDEPENDENT sides and
prints the disagreement:

  1. files on disk, keyed by chapter number AND by full slug
  2. the live TOC, walked with the optional-slug pattern, counted raw and
     deduped by number

Exit code 0 when the disk set covers the TOC set, 1 otherwise — so a pre-pack
check fails loudly instead of shipping a truncated book.

Usage:
    python3 reconcile_book.py <book-dir> --toc-url "https://host/series/slug.html"
    python3 reconcile_book.py <book-dir>            # disk-side audit only
    python3 reconcile_book.py <book-dir> --urls-file out/chapter_urls.txt

For next-link-walk sites (wuxiaworld lite) there is no paginated TOC to walk;
pass the saved chapter_urls.txt instead.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
CHAPTER_RE = re.compile(r"chapter-(\d+)\.html\.md$")
# optional slug AFTER the number: bare, dash+slug, dot-suffix, or a part marker
CHAP_LINK = re.compile(r'href="[^"]*?chapter-(\d+)(?:-[^"\s/]+)?\.html"')
SLUG_RE = re.compile(r"chapter-(\d+(?:-[^.\s"/]+)?)\.html$", re.I)


def scan_disk(outdir: str) -> tuple[set[str], set[str], dict[str, set[str]]]:
    """Return (numbers, full-slugs, number->suffix-map)."""
    numbers: set[str] = set()
    slugs: set[str] = set()
    suffixes: dict[str, set[str]] = {}
    for f in os.listdir(outdir):
        m = CHAPTER_RE.search(f)
        if not m:
            continue
        s = SLUG_RE.search(f)
        slug = s.group(1) if s else m.group(1)
        numbers.add(m.group(1))
        slugs.add(slug)
        suffixes.setdefault(m.group(1), set()).add(slug[len(m.group(1)) :] or "(bare)")
    return numbers, slugs, suffixes


def walk_toc(url: str, page_param: str, max_pages: int) -> tuple[int, set[str]]:
    """Walk the paginated TOC. Return (raw href count, unique numbers)."""
    raw = 0
    nums: set[str] = set()
    page_no = 1
    while page_no <= max_pages:
        target = url if page_no == 1 else "%s?%s=%d" % (url, page_param, page_no)
        try:
            req = urllib.request.Request(target, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                page = r.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError):
            break
        links = CHAP_LINK.findall(page)
        if not links:
            break
        raw += len(links)
        nums.update(n for n in links)
        page_no += 1
    return raw, nums


def load_urls_file(path: str) -> tuple[int, set[str]]:
    links: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            links.extend(CHAP_LINK.findall(line))
    return len(links), set(links)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("book_dir")
    ap.add_argument("--toc-url", default=None)
    ap.add_argument("--urls-file", default=None)
    ap.add_argument("--page-param", default="page")
    ap.add_argument("--max-pages", type=int, default=200)
    args = ap.parse_args()

    outdir = os.path.join(args.book_dir, "out")
    if not os.path.isdir(outdir):
        print("no out/ directory under %s" % args.book_dir)
        return 2

    nums, slugs, suffixes = scan_disk(outdir)
    split = {n: sorted(s) for n, s in suffixes.items() if len(s) > 1}
    print("[disk] files=%d  unique numbers=%d  numbers with >1 variant=%d"
          % (len(slugs), len(nums), len(split)))
    if split and len(split) <= 20:
        for n in sorted(split)[:20]:
            print("        %-8s %s" % (n, split[n]))

    if not (args.toc_url or args.urls_file):
        print("[note] no TOC source given; disk-side audit only")
        return 0

    raw, tnums = (load_urls_file(args.urls_file) if args.urls_file
                  else walk_toc(args.toc_url, args.page_param, args.max_pages))
    print("[toc ] raw hrefs=%d  unique numbers=%d" % (raw, len(tnums)))
    missing = tnums - nums
    extra = nums - tnums
    print("[chk ] toc numbers not on disk: %d %s"
          % (len(missing), sorted(missing)[:12]))
    if extra:
        print("[chk ] disk numbers not in toc: %d %s"
              % (len(extra), sorted(extra)[:12]))
    collapsed = raw - len(tnums)
    print("[chk ] raw-vs-unique delta: %d" % collapsed)

    if missing:
        print("RESULT: MISMATCH — reconcile before packaging.")
        return 1
    if collapsed > len(tnums) // 2 and collapsed > 10:
        print("RESULT: SUSPECT — most TOC hrefs collapsed onto one number; "
              "check for a part-split site.")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

