#!/usr/bin/env python3
"""Strip non-story boilerplate from scraped chapter .md files.

Usage:  clean_chapters.py <book-dir> [--apply]

Dry run by default: prints every planned edit. --apply rewrites files in place.

Three classes are removed, each an explicit list rather than a loose regex:
  1. site furniture      '————' separator paragraphs (387 across the book)
  2. MTL translator notes 'ps: it takes twenty minutes to check for typos.'
                         (168, including 2 never translated from Chinese)
  3. author end-of-chapter notes  monthly-pass begging, 'thank you!!!',
                         'the next chapter shall...' (93)

A fourth class is REPAIRED, not deleted: anti-piracy watermarks where a site
injected raw Chinese into the middle of an English sentence. Deleting the
paragraph would break the sentence; the CJK run plus its stray gloss is removed
in place.

Deliberately KEPT:
  - ch1977 '"&...%￥#"' -- the story is about a distorted space that garbles
    speech; the gibberish is the point, not a watermark.
  - every other non-ASCII char: curly quotes and em dashes are the translation's.
"""
import os
import re
import shutil
import sys
import unicodedata

SEP = re.compile(r"^[—\-–=_\s*·•]{4,}$")
PS_NOTE = re.compile(r"^\s*(ps|p\.s\.)\s*[:：]\s*.+", re.I)

# Anti-piracy watermarks: the site stamps its domain into the story text using
# Unicode MATHEMATICAL ALPHANUMERIC SYMBOLS (𝒻𝒓𝒆𝒆𝒘𝒆𝒃𝓃𝒐𝒗𝒆𝓁.𝒸𝑜𝓂) in MIXED
# font styles, so a plain grep for "freewebnovel" never sees it. ~1,100
# paragraphs carry it. The stamp is appended to the end of a paragraph, after
# the final sentence.
#
# Approach: map each character to its NFKC form ONE AT A TIME and keep a 1:1
# index back to the original string. Whole-string NFKC is NOT safe here --
# 1,120 paragraphs change length under it (ligatures, compatibility forms), so
# offsets into the original cannot be recovered from offsets into the
# normalised text. Per-character NFKC never changes length for these.
#
# The guard matters: a run is removed only if the reassembled letters spell a
# known domain. Real math in a xianxia novel (x, y, z, π, ∑) does not spell a
# domain and survives untouched.
MATH_CHAR = re.compile(
    r"["
    r"̀-ͯ"          # combining diacriticals
    r"∀-⋿"               # math operators
    r"℀-⅏"               # letterlike symbols (incl. SCRIPT SMALL E/O, U+0212F/U+02134)
    r"Ⰰ-⿯"               # CJK radicals
    r"、-퟿"               # CJK, hangul, CJK compat
    r"豈-﫿"               # CJK compat forms
    r"𝛀-𝟿"               # mathematical alphanumeric symbols
    r"\U0001D400-\U0001D7FF"  # bold/italic/script/fraktur/double-struck/mono
    r"\U0001F100-\U0001F1FF"  # enclosed alphanumeric supplement
    r"\U00020000-\U0002FFFF]"  # CJK ext planes
)
# The whole domain must be reconstructable from mapped characters only: if any
# codepoint inside it is NOT in MATH_CHAR, the span cannot be located and is
# silently missed. U+0212F (SCRIPT SMALL E) and U+02134 (SCRIPT SMALL O) were
# exactly that -- outside the class, and 254 chapters kept their watermark.
WATERMARK_RE = re.compile(r"(?:no)?(?:free)?webnovel\.(?:com|net|org)"
                         r"|freewenol\.(?:com|net|org)", re.I)
WATERMARK_DOMAINS = ("freewebnovel", "freewenol", "webnovel", "nobadnovel",
                     "novelread", "novelrare", "novellunar", "novelbuddy",
                     "lightnovel")


def strip_watermark(text):
    """Remove math-script domain stamps, plus the stray rule before them.

    Returns (cleaned_text, count).
    """
    if not MATH_CHAR.search(text):
        return text, 0

    # 1:1 char map: original index -> normalised char. An unmappable char
    # becomes U+FFFD, which cannot match inside a domain -- so a watermark
    # containing one is missed rather than mis-removed.
    norm_chars, orig_index = [], []
    for i, ch in enumerate(text):
        if MATH_CHAR.match(ch):
            n = unicodedata.normalize("NFKC", ch)
            norm_chars.append(n if len(n) == 1 else "�")
        else:
            norm_chars.append(ch)
        orig_index.append(i)
    flat = "".join(norm_chars).lower()

    spans = list(WATERMARK_RE.finditer(flat))
    drop = set()
    for m in spans:
        lo, hi = orig_index[m.start()], orig_index[m.end() - 1] + 1
        # swallow trailing whitespace only -- NOT the left side, or a stamp
        # after real prose joins the words ("Text<stamp>and more" -> "Textand")
        while hi < len(text) and text[hi] in " \t":
            hi += 1
        drop.update(range(lo, hi))

    out = "".join(ch for i, ch in enumerate(text) if i not in drop)
    if not spans and out == text:
        # No full domain matched. A leftover fragment can sit at the end of ANY
        # paragraph, not just the last one, so check per paragraph -- anchoring
        # on the end of the whole text removed 1 of 74 fragments.
        paras = out.split("\n\n")
        changed = 0
        for i, p in enumerate(paras):
            # allow leading punctuation: the site sometimes leaves a closing
            # curly quote attached to the fragment, as in '...said. "𝒻𝒓𝒆ℯ'
            m = re.search(r"([^\x00-\x7f]+)[ \t]*$", p)
            if not m:
                continue
            frag = unicodedata.normalize("NFKC", m.group(1)).lower()
            if frag in ("free", "ree", "webnovel", "vel", "wenol"):
                paras[i] = p[:m.start()].rstrip()
                changed += 1
            elif frag.lstrip("”’\"'") in ("free", "ree", "webnovel", "vel", "wenol"):
                lead = len(frag) - len(frag.lstrip("”’\"'"))
                keep = m.start() + lead
                paras[i] = p[:keep].rstrip()
                changed += 1
        if changed:
            return "\n\n".join(paras), changed

    # an inline rule left beside a stamp is site furniture too
    out = re.sub(r"[ \t]*[—–-]{4,}[ \t]*", " ", out)
    out = re.sub(r"[ \t]{2,}", " ", out).strip()

    return out, len(spans)

# author notes: monthly-pass begging, thank-yous, next-chapter teasers
AUTHOR_NOTE = re.compile(
    r"^(?:"
    r"(?:please\s+|pls\s+)?(?:kindly\s+)?"
    r"(?:support|donate|vote|request(?:ing)?|seek(?:ing)?|beg(?:ging)?|ask(?:ing)?|"
    r"seeking|urgently\s+request(?:ing)?|humbly\s+ask(?:ing)?)\b"
    r".{0,120}\b(?:monthly\s+(?:pass|vote|ticket)\w*|passes)\b"
    r"|"
    r"(?:also,?\s*)?(?:i\s+)?(?:would\s+like\s+to\s+|will\s+|want\s+to\s+)?"
    r"ask(?:ing)?\s+for\s+(?:a\s+|the\s+|your\s+|baseline\s+)?"
    r"monthly\s+(?:pass|vote|ticket)\w*"
    r"|"
    r"(?:the\s+)?(?:start|beginning|end)\s+of\s+the\s+month"
    r"|"
    r".{0,140}\bmonthly\s+(?:pass|vote|ticket)\w*\b.{0,140}"
    r"|"
    r"do\s+you\s+(?:still\s+)?have\s+any\s+monthly\s+pass"
    r"|"
    r"(?:thank\s+you|thanks)(?:\s+all|\s+you)?[!.\s]*"
    r"|"
    r"the\s+next\s+chapter\s+shall"
    r"|"
    r"bows?\s+(?:of|to)\s+thanks"
    r")\s*$",
    re.I)

# watermark repair: exact CJK run -> corrected English
WATERMARK_FIXES = [
    ("looked at the小木屋草草地创可贴 (small wooden hut ss makeshift bolster)",
     "looked at the small wooden hut (a makeshift bolster)"),
    ("Let’s see, repair the sky裂.",
     "Let’s see, repair the sky."),
    ("Let’s see, repair the sky裂.\"",
     "Let’s see, repair the sky.\""),
]

# Everything after this marker in a chapter is author commentary, not story:
# ch2138 ends "(End of the book)" and everything below it is a farewell note.
END_OF_STORY = re.compile(r"^\(end of (?:the )?(?:book|novel|story)\)$", re.I)

# Author sign-off lines. These are matched ONLY as a contiguous run ending the
# chapter (see trim_tail), never mid-chapter: "Thanks!" and "Happy New Year!"
# occur as ordinary dialogue, so a global regex would eat story text.
#
# Each alternative is PREFIX-matched, not whole-line: the real sign-off blocks
# trail extra prose ("Farewell for now; if things go smoothly, next book will be
# around May or June"). Whole-line anchoring silently matched almost nothing --
# only 2 of ~90 lines dropped on the first run.
SIGN_OFF = re.compile(
    r"(?:"
    r"nothing much to write\b"
    r"|that[’']?s all for it\b"
    r"|additionally[.…]*"
    r"|happy new year[!.]*"
    r"|the alliance hierarch hasn[’']?t updated"
    r"|thank you for supporting[!.]*"
    r"|farewell for now\b"
    r"|see you if fate allows\b"
    r"|thanks to all .{0,40}support"
    r"|bow of thanks[!.]*"
    r"|thanks[!.]*"
    r"|thank you all for your continued support"
    r")",
    re.I)


def chap_num(fname):
    m = re.search(r"chapter-(\d+)(?:-|\.|$)", fname)
    return int(m.group(1)) if m else 10 ** 9


def classify(s, body_idx, body_len):
    if SEP.match(s):
        return "separator"
    if PS_NOTE.match(s):
        return "ps-note"
    if AUTHOR_NOTE.match(s) and len(s) < 200:
        return "author-note"
    return None


def trim_tail(paras):
    """Drop trailing author sign-off lines, contiguous from the chapter end.

    Returns (kept, dropped_text). Two independent triggers, because the
    closing block differs per book:
      - a marker line like "(End of the book)" — everything below is notes
      - a run of >=2 sign-off lines at the tail (ch2139 has no marker)
    A single trailing line is never enough on its own: "Thanks!" and
    "Happy New Year!" also occur as plain dialogue mid-chapter.
    """
    n = len(paras)
    cut = n
    while cut > 0 and SIGN_OFF.match(paras[cut - 1].strip()):
        cut -= 1
    if n - cut >= 2:
        return paras[:cut], [p.strip() for p in paras[cut:]]
    # marker form
    for j, p in enumerate(paras):
        if END_OF_STORY.match(p.strip()) and j + 1 < n:
            return paras[:j + 1], [q.strip() for q in paras[j + 1:]]
    return paras, []


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    bookdir = args[0] if args else "."
    outdir = os.path.join(bookdir, "out")

    files = sorted((f for f in os.listdir(outdir)
                    if re.fullmatch(r"chapter-\d+.*\.md", f)), key=chap_num)

    removed = {"separator": 0, "ps-note": 0, "author-note": 0, "sign-off": 0,
               "math-watermark": 0}
    affected = set()
    repaired = []
    shown = 0

    for f in files:
        path = os.path.join(outdir, f)
        raw = open(path, encoding="utf-8").read()
        head, _, rest = raw.partition("\n")
        paras = [p for p in rest.strip().split("\n\n") if p.strip()]

        fixed_text = "\n\n".join(paras)
        for old, new in WATERMARK_FIXES:
            if old in fixed_text:
                fixed_text = fixed_text.replace(old, new)
                repaired.append((chap_num(f), old[:55]))

        fixed_text, nw = strip_watermark(fixed_text)
        if nw:
            removed["math-watermark"] += nw
            affected.add(chap_num(f))

        kept = []
        for p in fixed_text.split("\n\n"):
            if not p.strip():
                continue
            # a paragraph that was only a watermark is now empty
            kind = classify(p.strip(), 0, 0)
            if kind:
                removed[kind] += 1
                affected.add(chap_num(f))
                if shown < 30:
                    print(f"  DROP {kind:13s} ch{chap_num(f):<5d} {p.strip()[:88]!r}")
                    shown += 1
                continue
            kept.append(re.sub(r"[ \t]+", " ", p.strip()).strip())

        kept, tail = trim_tail(kept)
        if tail:
            removed["sign-off"] += len(tail)
            affected.add(chap_num(f))
            for t in tail:
                print(f"  TAIL-END          ch{chap_num(f):<5d} {t[:88]!r}")

        new_raw = head + "\n\n" + "\n\n".join(kept) + "\n"
        if new_raw != raw:
            if apply:
                shutil.copy2(path, path + ".bak")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new_raw)

    mode = "APPLIED" if apply else "DRY RUN (no files written)"
    print(f"\n=== {mode} ===")
    for k, v in removed.items():
        print(f"  {k:13s}: {v}")
    print(f"  chapters touched: {len(affected)} of {len(files)}"
          + (f"  ({affected and min(affected)}..{max(affected)})" if affected else ""))
    print(f"  watermark repairs: {len(repaired)}")
    for n, frag in repaired:
        print(f"    ch{n}: {frag!r}")
    if not apply:
        print("\nre-run with --apply to write changes (each file gets a .bak)")


if __name__ == "__main__":
    main()