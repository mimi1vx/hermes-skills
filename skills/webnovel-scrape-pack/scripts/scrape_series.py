#!/usr/bin/env python3
"""Scrape a nobadnovel.com series into per-chapter markdown files.

Usage:  python3 scrape_series.py <series-slug> [outdir] [--refresh]

  <series-slug>   e.g. the-villain-my-system-is-not-so-serious
  [outdir]        default: out
  --refresh       re-fetch chapters even if their .md already exists
                  (needed after changing the extraction rules)

Resumable: chapters whose .md already exists are skipped, so re-running after
an interruption only fetches what's missing.
"""
import os
import re
import sys
import time
import html as html_mod
import urllib.request

BASE = "https://www.nobadnovel.com"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
SLEEP = 0.5

# Story paragraphs only. The page also contains related-novel teasers
# (class="... line-clamp-2") and a footer copyright (class="astro-*");
# matching every <p> pulls in ~30% junk. Verify these classes still hold:
#   grep -o '<p class="[^"]*"' page.html | sort | uniq -c
STORY_P = re.compile(r'<p class="mb-4 para"[^>]*>(.*?)</p>', re.I | re.S)
ANY_P = re.compile(r"<p[^>]*>(.*?)</p>", re.I | re.S)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
JUNK_PREFIX = ("Copyright",)


def get(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def clean(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_chapter(page):
    m = H1.search(page)
    title = clean(m.group(1)) if m else ""
    paras = STORY_P.findall(page)
    if not paras:
        paras = ANY_P.findall(page)          # fallback if the class is renamed
    lines = [t for t in (clean(p) for p in paras) if t]
    lines = [t for t in lines if not t.startswith(JUNK_PREFIX)]
    return title, lines


def chapter_urls(series):
    page = get(f"{BASE}/series/{series}")
    urls = re.findall(rf'{BASE}/series/{re.escape(series)}/chapter-[^"\']*', page)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def chap_num(fname):
    m = re.search(r"chapter-(\d+)-", fname)
    return int(m.group(1)) if m else 10 ** 9


def verify(outdir, expected):
    files = sorted(
        (f for f in os.listdir(outdir) if f.endswith(".md")),
        key=chap_num,
    )
    errs = os.path.join(outdir, ".errors.tsv")
    nerr = sum(1 for _ in open(errs, encoding="utf-8")) if os.path.exists(errs) else 0
    junk, short = [], []
    words = 0
    for f in files:
        body = open(os.path.join(outdir, f), encoding="utf-8").read()
        w = len(body.split())
        words += w
        if "Copyright" in body or "No Bad Novel" in body:
            junk.append(f)
        if w < 50:
            short.append(f)
    nums = [chap_num(f) for f in files]
    gaps = len(set(range(min(nums), max(nums) + 1)) - set(nums))
    print("\n[verify]")
    print(f"  chapters   : {len(files)} / {expected}")
    print(f"  numbering  : {min(nums)}..{max(nums)}  gaps={gaps}")
    print(f"  errors     : {nerr}")
    print(f"  junk files : {len(junk)}")
    print(f"  too short  : {len(short)}")
    print(f"  total words: {words:,}")
    if junk:
        print(f"  !! junk in e.g. {junk[0]} -- re-run with --refresh")
    if short:
        print(f"  !! short chapters e.g. {short[:3]}")
    return not (junk or short or nerr)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    series = args[0]
    outdir = args[1] if len(args) > 1 else "out"
    refresh = "--refresh" in sys.argv
    os.makedirs(outdir, exist_ok=True)

    urls = chapter_urls(series)
    print(f"[toc] {len(urls)} chapters found")
    with open(os.path.join(outdir, "chapter_urls.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(urls) + "\n")

    # sanity: prove the first URL actually resolves before a long run
    probe = get(urls[0])
    print(f"[probe] {urls[0][:90]}... -> {len(probe)} bytes")

    pending = [u for u in urls
               if refresh or not os.path.exists(
                   os.path.join(outdir, u.rsplit("/", 1)[-1] + ".md"))]
    print(f"[scrape] {len(pending)} to fetch ({len(urls) - len(pending)} cached)")

    errs_path = os.path.join(outdir, ".errors.tsv")
    title = ""
    for i, url in enumerate(pending):
        fname = os.path.join(outdir, url.rsplit("/", 1)[-1] + ".md")
        try:
            title, lines = parse_chapter(get(url))
            with open(fname, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                for p in lines:
                    f.write(p + "\n\n")
        except Exception as e:
            with open(errs_path, "a", encoding="utf-8") as f:
                f.write(f"{url}\tERR {type(e).__name__}: {e}\n")
        if i % 25 == 0 or i == len(pending) - 1:
            print(f"  {i + 1}/{len(pending)} {title[:45]}", end="\r", file=sys.stderr)
        time.sleep(SLEEP)
    print()

    ok = verify(outdir, len(urls))
    last = max((f for f in os.listdir(outdir) if f.endswith(".md")),
               key=lambda f: chap_num(f))
    tail = open(os.path.join(outdir, last), encoding="utf-8").read().strip()[-90:]
    print(f"\n[last chapter] {last}\n  ...{tail}")
    print("[verify] OK" if ok else "[verify] PROBLEMS FOUND (see above)")


if __name__ == "__main__":
    main()