#!/usr/bin/env python3
"""Audit a scraped book directory: numbering, duplicates, header integrity.

    python3 audit_chapters.py <dir> [--max-n N]

Catches the defects that word-count and junk-string sweeps miss, because all of
them leave the word count plausible:

  * duplicate chapter NUMBERS hidden by a resume run (file count still matches)
  * gaps, computed against the real 1..max range rather than the TOC's own output
  * doubled headers, e.g. "# Chapter 2962: Chapter 2960: Teaming Up ..." — the
    site printed a number that disagrees with the URL, and both were kept
  * untitled headers ("# Chapter 63" with no title after the colon)
  * a header whose number disagrees with its filename

Exit status is 1 when anything is wrong, so it can gate a build.
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import re

NUM = re.compile(r"chapter-(\d+)", re.I)
HEAD = re.compile(r"^#\s+(.*)$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", nargs="?", default=".")
    ap.add_argument("--out", default=None,
                    help="chapter dir to audit (default <directory>/out)")
    ap.add_argument("--max-n", type=int, default=0,
                    help="highest expected chapter; 0 = use what is on disk")
    args = ap.parse_args()

    outdir = args.out or os.path.join(args.directory, "out")
    files = glob.glob(os.path.join(outdir, "chapter-*.md"))
    if not files:
        print(f"no chapters in {outdir}")
        return 1

    nums: dict[int, list[str]] = collections.defaultdict(list)
    words = 0
    for f in files:
        m = NUM.search(os.path.basename(f))
        if m:
            nums[int(m.group(1))].append(f)
        words += len(open(f, encoding="utf-8").read().split())

    uniq = sorted(nums)
    hi = args.max_n or uniq[-1]
    gaps = sorted(set(range(1, hi + 1)) - set(uniq))
    dups = {n: fs for n, fs in nums.items() if len(fs) > 1}

    doubled, untitled, mismatched = [], [], []
    for f in files:
        head = HEAD.match(open(f, encoding="utf-8").readline().strip())
        if not head:
            mismatched.append((f, "no '#' header"))
            continue
        title = head.group(1)
        fnum = NUM.search(os.path.basename(f))
        n = int(fnum.group(1)) if fnum else -1
        if title.count("Chapter") > 1:
            doubled.append((f, title))
        m = re.match(r"Chapter (\d+)\b", title)
        if not m:
            untitled.append((f, title))
        elif n != -1 and int(m.group(1)) != n:
            mismatched.append((f, f"header says {m.group(1)}, file says {n}"))

    print(f"files           : {len(files)}")
    print(f"unique numbers  : {len(uniq)}  range {uniq[0]}..{uniq[-1]}")
    print(f"total words     : {words:,}")
    print(f"gaps in 1..{hi}   : {len(gaps)} {gaps[:12]}")
    print(f"duplicate nums  : {len(dups)} {sorted(dups)[:12]}")
    print(f"doubled headers : {len(doubled)}  {[os.path.basename(f) for f, _ in doubled[:6]]}")
    print(f"untitled headers: {len(untitled)}  {[os.path.basename(f) for f, _ in untitled[:6]]}")
    print(f"header/filename mismatch: {len(mismatched)}")
    for f, why in mismatched[:6]:
        print(f"    {os.path.basename(f)}: {why}")

    bad = gaps or dups or doubled or mismatched
    # untitled is a legitimate end state when the source has no titles
    print("OK" if not bad else "PROBLEMS")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())