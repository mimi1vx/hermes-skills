#!/usr/bin/env python3
"""Scrape freewebnovel.com series into per-chapter markdown files.

Usage:  python3 scrape_fwn.py <series-slug> [outdir]

freewebnovel differs from nobadnovel in three ways that matter:

1. The series index lists only chapters 1..40 plus the final handful; the rest
   are reachable only by constructing /chapter-<n> directly. The pattern is
   uniform and every n in 1..max returns 200, so we enumerate instead of
   parsing. max is discovered by walking up from the last linked chapter until
   a probe 404s (or --max is given).
2. The story body is delimited by <div class="chapter-start"> ... <div
   class="chapter-end">. Scoped extraction to that span drops the ad slots,
   comment UI, and "Translator:" boilerplate cleanly.
3. <title> is unreliable (chapter-500's title says "Chapter 49"). The real
   heading is the first paragraph inside the body span, of the form
   "Chapter 500: ...". We prefer that and fall back to the title tag.

Resumable: chapters whose .md already exists are skipped.
"""
import html as html_mod
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

BASE = "https://freewebnovel.com"
UA = ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
SLEEP = 0.5
BODY_START = re.compile(r'<div class="chapter-start"[^>]*>', re.I)
BODY_END = re.compile(r'<div class="chapter-end"[^>]*>', re.I)
P = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
CHAPTER_HEAD = re.compile(r"^Chapter\s+(\d+)\s*[:.\-–]\s*(.+)$", re.I)
# Site boilerplate that lives inside the body span and must not be kept.
DROP = re.compile(
    r"^(translator|editor|proofreader|reviewer|typo|support us|if you enjoy this novel|"
    r"please visit|support the translator|chapter comments|comments|comment rules|"
    r"commenting suspended|report chapter|chapter discussion)", re.I)


def get(url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            last = e
        except Exception as e:  # noqa: BLE001 - transient network
            last = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def clean(text):
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"[ \t\r\f\v]+", " ", html_mod.unescape(text)).strip()


def body_span(page):
    """Story paragraphs only: the span between chapter-start and chapter-end."""
    m = BODY_START.search(page)
    if not m:
        return []
    rest = page[m.end():]
    e = BODY_END.search(rest)
    seg = rest[:e.start()] if e else rest
    return [clean(p) for p in P.findall(seg)]


def parse(page, num):
    paras = [p for p in body_span(page) if p and not DROP.match(p)]
    # The leading "Chapter N: Title" paragraph is the real heading.
    title = ""
    if paras:
        m = CHAPTER_HEAD.match(paras[0])
        if m and int(m.group(1)) == num:
            title = f"Chapter {num}: {m.group(2).strip()}"
            paras = paras[1:]
        else:
            title = f"Chapter {num}"
    else:
        title = f"Chapter {num}"
    return title, paras


def discover_max(slug, hint=None):
    """Walk up from the highest linked chapter until a probe returns nothing."""
    page = get(f"{BASE}/novel/{slug}")
    linked = sorted({int(n) for n in re.findall(rf"/novel/{re.escape(slug)}/chapter-(\d+)", page)})
    if not linked:
        raise SystemExit("no chapter links found on the index page")
    top = max(linked)
    print(f"[discover] index links {len(linked)}, highest {top}")
    if hint:
        return int(hint)
    n = top
    while n < top + 5000:
        probe = n + 1
        if not get(f"{BASE}/novel/{slug}/chapter-{probe}"):
            return n
        n = probe
        time.sleep(SLEEP)
    return n


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    slug = args[0]
    outdir = args[1] if len(args) > 1 else "out"
    hint = None
    for a in sys.argv[1:]:
        if a.startswith("--max="):
            hint = a.split("=", 1)[1]
    os.makedirs(outdir, exist_ok=True)

    total = discover_max(slug, hint)
    print(f"[toc] enumerating chapters 1..{total}")

    pending = [n for n in range(1, total + 1)
               if not any(re.fullmatch(rf"chapter-{n}-.*\.md", f) for f in os.listdir(outdir))]
    print(f"[scrape] {len(pending)} to fetch ({total - len(pending)} cached)")

    # Prove the URL pattern before a long run.
    probe = get(f"{BASE}/novel/{slug}/chapter-1")
    t, ps = parse(probe, 1)
    print(f"[probe] chapter 1 -> {len(ps)} paragraphs, title {t[:50]!r}")
    if len(ps) < 10:
        raise SystemExit(f"probe looks wrong ({len(ps)} paragraphs) — aborting")

    errs = os.path.join(outdir, ".errors.tsv")
    for i, n in enumerate(pending, 1):
        fname = os.path.join(outdir, f"chapter-{n}.md")
        try:
            page = get(f"{BASE}/novel/{slug}/chapter-{n}")
            title, paras = parse(page, n)
            if not paras:
                raise ValueError("no paragraphs extracted")
            # <chapter>-<slug>.md: package_book.py/make_pdf.py parse the number
            # with /chapter-(\d+)-/, so a bare chapter-N.md sorts to the end.
            slug_txt = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
            out_name = f"chapter-{n}-{slug_txt or 'chapter'}.md"
            with open(os.path.join(outdir, out_name), "w", encoding="utf-8") as fh:
                fh.write(f"# {title}\n\n")
                for p in paras:
                    fh.write(p + "\n\n")
        except Exception as e:  # noqa: BLE001 - record and continue
            with open(errs, "a", encoding="utf-8") as f:
                f.write(f"chapter-{n}\tERR {type(e).__name__}: {e}\n")
        if i % 25 == 0 or i == len(pending):
            print(f"  {i}/{len(pending)} ch{n}", end="\r", file=sys.stderr, flush=True)
        time.sleep(SLEEP)
    print()

    files = sorted(f for f in os.listdir(outdir) if re.fullmatch(r"chapter-\d+-.*\.md", f))
    words = junk = short = 0
    mathwm = 0
    for f in files:
        b = open(os.path.join(outdir, f), encoding="utf-8").read()
        w = len(b.split())
        words += w
        if re.search(r"Copyright|No Bad Novel", b, re.I):
            junk += 1
        # freewebnovel stamps its domain in MATH SCRIPT (𝒻𝒓𝒆𝒆𝒘𝒆𝒃𝓃𝒐𝒗𝒆𝓁.𝒸𝑜𝓂),
        # so a plain grep for "freewebnovel" cannot see it. NFKC it first.
        flat = "".join(unicodedata.normalize("NFKC", c) if len(unicodedata.normalize("NFKC", c)) == 1 else " "
                       for c in b)
        if re.search(r"webnovel\.(com|net|org)", flat, re.I):
            mathwm += 1
        if w < 50:
            short += 1
    nums = [int(re.search(r"chapter-(\d+)-", f).group(1)) for f in files]
    gaps = sorted(set(range(1, total + 1)) - set(nums))
    nerr = sum(1 for _ in open(errs, encoding="utf-8")) if os.path.exists(errs) else 0
    print("\n[verify]")
    print(f"  chapters   : {len(files)} / {total}")
    print(f"  gaps       : {len(gaps)} {gaps[:8]}")
    print(f"  errors     : {nerr}")
    print(f"  junk files : {junk}")
    print(f"  math-script watermark: {mathwm}")
    print(f"  too short  : {short}")
    print(f"  total words: {words:,}")
    print("[verify] OK" if not (gaps or junk or short or nerr) else "[verify] PROBLEMS (watermarks pending clean_chapters.py)")


if __name__ == "__main__":
    main()