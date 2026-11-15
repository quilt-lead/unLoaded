"""Copyright guard: block committing anything derived from the copyrighted permit set (a private
drawing set + calc package used during development, never part of this repo).

The repo is public. That set carries copyright notices, so no PDF, page render, extracted text,
derived JSON or screenshot of it may enter git. The guard scans the WHOLE repository (repo root
from git: the Vite app in src/ and public/, packages/, tools/, docs, CI config - every path).
Rules (config in tools/calcgraph-reference/scripts/copyright_guard.json):
  1. any *.pdf (never allowed); any other file with a PDF header (the PDF magic plus a n.n
     version) at the start of a line in its first 1 KB - readers accept junk before it - unless
     pinned on the blob allowlist (a text file that quotes a header can be pinned)
  2. any NON-TEXT blob not on the blob allowlist, which pins each allowed file by path AND blob
     sha (a re-used path with new bytes fails). A file is classified by its CONTENT as well as its
     name: image magic bytes (PNG, JPEG, GIF, WebP, TIFF, BMP, ICO, PSD, JPEG 2000 / XL, HEIC /
     HEIF / AVIF), archives and office files (zip - which is also docx / xlsx / pptx / odt - OLE
     doc / xls, gzip, bzip2, xz, zstd, 7z, rar, tar), SVG (by name or by an <svg> root element),
     and any other blob holding NUL bytes that does not decode as UTF-16 / UTF-32 text. Magic bytes
     count only in a binary context (a NUL, a control byte or invalid UTF-8 in the first 8 KB), so
     plain text that happens to start `8BPS` or hold `ustar` at 257 is text. An image name (png,
     heic, ...) on a file whose bytes are not an image is still treated as an image.
  3. any text file carrying a base64 payload - an embedded data: URI of 200+ characters, or raw
     base64 (standard or URL-safe) with no prefix: an unbroken run of 256+ characters, or 4+
     consecutive wrapped lines of 60..100, mixing upper case, lower case and digits and not pure hex
     (so hex hashes and lockfile integrity values pass) - unless the file is pinned on the blob
     allowlist. RESIDUAL: base64 shorter than that, or broken up by other characters, is not seen.
  4. anything under tools/calcgraph-reference/data/sets/ or tools/calcgraph-reference/data/labels/
     (anywhere in the path)
  5. any text file containing a protected term (a distinctive string from the set: firm names,
     project name, job / package / permit numbers), unless the file's path is on the term
     allowlist for that term id. Text is UTF-8 / 8-bit, or UTF-16 / UTF-32 (BOM, or BOM-less
     ASCII-heavy); it is decoded before the scan.

Protected terms are never stored in plaintext - not in the config, not in this script, not in
its self-test. The config holds a random salt, one salted SHA-256 per term, the term's canonical
length (`len`, see below) and `max_n`:
  tokens(text)      = maximal runs of ASCII letters / digits, with each following '.' digits
                      group kept in the token (a decimal is ONE number), lowercased; everything
                      else (whitespace, punctuation, dashes) separates tokens
  canonical(term)   = its tokens concatenated with no separator, so "Ab-Cd", "ab cd" and "AbCd"
                      are one canonical form. All three tiers below scan in this same form, so a
                      term matches exactly as stored: `1234.56` is never `123456`, and a term
                      stored with a dot keeps it and is found with it.
  hash              = sha256(salt + "\\0" + canonical)
A text file is matched in three tiers; a hit is reported as file, line, column and tier plus the
term's opaque id - never the term:
  token tier   every n-gram of 1..max_n consecutive tokens, concatenated
  unit tier    every n-gram of 1..max_n+3 consecutive UNITS, where each token is further split at
               letter <-> digit and camelCase boundaries (a decimal stays one unit, dot included;
               the units of a token concatenate back to the token); catches `PRJ<term>Rev2`,
               `get<Term>Value`
  glued tier   every substring of the canonical stream (the file's tokens concatenated, lowercased)
               whose length is the canonical length of a stored term of >= GLUE_MIN_LEN (8)
               characters; a hit may not start or end inside a longer number of the ORIGINAL text
               (an adjacent digit, or a decimal point and digit), so a term is not found inside a
               decimal or a longer number, while a separator ends a number (`Sheet 3 <term>`).
               Catches a term glued into a longer token with no case or digit boundary
               (`xx<term>yy`, `PRJ<TERM>REV`).
Why 8: below 8 characters a substring of the separator-free stream collides with ordinary words
and identifiers (a 5-letter name inside longer words, a 6-digit number inside the digit runs of
IFC coordinates), so the guard would block legitimate files. At 8+ characters a hit needs the
exact, distinctive term string, and digit runs must match whole.
RESIDUAL (mitigation, not a fix): a term shorter than 8 canonical characters glued to letters or
digits of the same case with no letter/digit or camelCase boundary (all-lowercase `xx<term>yy`,
all-caps `PRJ<TERM>REV`), or a digit-only term merged with adjacent digits, is NOT detected.
Nor is a number term written as a decimal (`12345.6` for a stored `12345-6`): a decimal is one
number, and matching across its point would find 6-digit terms in IFC coordinates.
A term stored before `len` was recorded (no `len` in the config) is scanned in the glued tier at
every length 8..GLUE_LEGACY_MAX_LEN (32), which is slower and misses such a term if it is longer
than 32; re-entering the term with --add-term records its length (nothing else changes).

Add a term without it ever touching a file, argv or shell history:
  tools/calcgraph-reference/scripts/check_no_copyrighted.py --add-term   (reads stdin, one term
per line; type it, then Ctrl-D). Re-entering a stored term backfills its `len`.

The salt only defeats precomputed tables: a short term can still be brute-forced from its hash
(and its stored length), so a hash list is obscurity for short strings, not secrecy. It keeps the
identity out of plaintext search, diffs and indexes, which is what this public repo needs.

  (paths below are from tools/calcgraph-reference/; the script may be run from any directory in the repo)
  python scripts/check_no_copyrighted.py --staged            # pre-commit hook (index contents)
  python scripts/check_no_copyrighted.py --tracked           # every file in HEAD
  python scripts/check_no_copyrighted.py --history [REV]     # every (path, blob) ever introduced on REV's history
                                                             # (fails on prod: its history predates the guard -
                                                             # screenshots, .DS_Store - and is not rewritten)
  python scripts/check_no_copyrighted.py --range A..B        # every (path, blob) introduced in A..B, merges included (CI)
  python scripts/check_no_copyrighted.py --push BEFORE AFTER [--base origin/prod] [--ref BRANCH]
                                                             # CI push: what the push introduces (push_spec);
                                                             # tree + ::warning:: when that cannot be determined
  python scripts/check_no_copyrighted.py --paths F [F ...]   # files on disk (working tree)
  python scripts/check_no_copyrighted.py --allow-blob PATH   # pin a synthetic image / binary (prints the entry)
  python scripts/check_no_copyrighted.py --add-term          # append term hash(es) read from stdin
  python scripts/check_no_copyrighted.py --self-test         # prove each rule fires

Exit 1 on any finding.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "copyright_guard.json")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".bmp", ".heic", ".heif", ".avif",
             ".ico", ".jxl", ".jp2", ".psd", ".svg")
ARCHIVE_EXT = (".zip", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".doc", ".xls", ".ppt", ".gz", ".tgz",
               ".bz2", ".xz", ".zst", ".7z", ".rar", ".tar")
FORBIDDEN_DIRS = ("tools/calcgraph-reference/data/sets/", "tools/calcgraph-reference/data/labels/")
TOKEN = re.compile(r"[0-9A-Za-z]+(?:\.[0-9]+)*")
# a unit's dot-digits run keeps its dot, so the units of a token concatenate back to the token itself
# (one canonical form for all three tiers; a decimal stays one number, `1234.56` never becomes `123456`)
UNIT = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\.?[0-9]+(?:\.[0-9]+)*")
PDF_HEADER = re.compile(rb"(?:^|[\r\n])%PDF-\d\.\d")
DATA_URI = re.compile(r"data:[\w.+-]*/?[\w.+-]*(?:;[\w.+=-]+)*;base64,([A-Za-z0-9+/=\s\\]{200,})")
# raw base64 (standard or URL-safe) with no data: prefix: one unbroken run of RAW_B64_MIN+ characters,
# or RAW_B64_LINES+ consecutive wrapped lines of 60..100. A run must mix upper case, lower case and
# digits and not be pure hex, so hex hashes, lockfile integrity values (sha512 = 88 chars) and long
# identifiers do not trip it.
RAW_B64_MIN = 256
RAW_B64_LINES = 4
RAW_B64 = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{%d,}={0,2}|(?:^[ \t]*[A-Za-z0-9+/]{60,100}={0,2}\r?\n){%d,}"
                     % (RAW_B64_MIN, RAW_B64_LINES), re.M)
BINARY_CTRL = re.compile(rb"[\x00-\x08\x0b\x0e-\x1a\x1c-\x1f\x7f]")
GLUE_MIN_LEN = 8           # glued-tier threshold, justified in the docstring
GLUE_LEGACY_MAX_LEN = 32   # glued-tier window for a term stored without `len`
UNIT_EXTRA_N = 3           # unit tier: a token can split into several units

# (offset, magic, label, kind) - kind "image" or "archive"
MAGIC = (
    (0, b"\x89PNG\r\n\x1a\n", "PNG image", "image"), (0, b"\xff\xd8\xff", "JPEG image", "image"),
    (0, b"GIF87a", "GIF image", "image"), (0, b"GIF89a", "GIF image", "image"),
    (0, b"II*\x00", "TIFF image", "image"), (0, b"MM\x00*", "TIFF image", "image"),
    (0, b"\x00\x00\x01\x00", "ICO image", "image"), (0, b"8BPS", "PSD image", "image"),
    (0, b"\x00\x00\x00\x0cjP  ", "JPEG 2000 image", "image"), (0, b"\xff\x4f\xff\x51", "JPEG 2000 image", "image"),
    (0, b"\x00\x00\x00\x0cJXL ", "JPEG XL image", "image"), (0, b"\xff\x0a", "JPEG XL image", "image"),
    (0, b"PK\x03\x04", "zip archive (or docx / xlsx / pptx / odt)", "archive"),
    (0, b"PK\x05\x06", "zip archive", "archive"), (0, b"PK\x07\x08", "zip archive", "archive"),
    (0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "OLE compound file (doc / xls / ppt / msg)", "archive"),
    (0, b"\x1f\x8b", "gzip archive", "archive"), (0, b"\xfd7zXZ\x00", "xz archive", "archive"),
    (0, b"\x28\xb5\x2f\xfd", "zstd archive", "archive"), (0, b"7z\xbc\xaf\x27\x1c", "7z archive", "archive"),
    (0, b"Rar!\x1a\x07", "rar archive", "archive"), (257, b"ustar", "tar archive", "archive"),
)
BMFF_IMAGE_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1",
                     b"avif", b"avis", b"mif2"}


def git(*args: str, cwd: str | None = None, binary: bool = False, stdin: bytes | None = None):
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True, input=stdin).stdout
    return out if binary else out.decode()


def repo_root() -> str:
    return git("rev-parse", "--show-toplevel", cwd=HERE).strip()


# ---------------------------------------------------------------- content classification
def binary_context(data: bytes) -> bool:
    """True when the first 8 KB are not plain text: a NUL, a control byte (other than tab, newline,
    form feed, carriage return, escape) or invalid UTF-8 (a multibyte character cut at the 8 KB edge
    does not count). Magic bytes only classify a file that has this - `8BPS`, `ustar` at 257 or
    `ftyp` at 4 in an ordinary text file are just text."""
    head = data[:8192]
    if BINARY_CTRL.search(head):
        return True
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as e:
        if len(data) <= 8192 or e.start < len(head) - 3:
            return True
    return False


def classify(path: str, data: bytes) -> tuple[str, str]:
    """(kind, label): kind is pdf | image | archive | binary | text. Content first, then name.
    A PDF found by its header rather than its name is labelled "PDF content" (it can be pinned)."""
    low = path.lower()
    if low.endswith(".pdf"):
        return "pdf", "PDF file"
    if PDF_HEADER.search(data[:1024]):
        return "pdf", "PDF content (a PDF header at a line start in the first 1 KB)"
    if binary_context(data):
        for off, magic, label, kind in MAGIC:
            if data[off:off + len(magic)] == magic:
                return kind, label
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image", "WebP image"
        if data[4:8] == b"ftyp":
            brand = data[8:12]
            return ("image", f"HEIF / AVIF image ({brand.decode('latin-1')})") if brand in BMFF_IMAGE_BRANDS \
                else ("binary", "ISO media file")
        if data[:2] == b"BM" and len(data) >= 26 and data[6:10] == b"\0\0\0\0":
            return "image", "BMP image"
        if data[:3] == b"BZh" and data[4:10] == b"1AY&SY":
            return "archive", "bzip2 archive"
    if low.endswith(".svg"):
        return "image", "SVG image"
    if low.endswith(IMAGE_EXT):
        return "image", f"image ({os.path.splitext(low)[1]}) whose bytes are not a known image format"
    if low.endswith(ARCHIVE_EXT):
        return "archive", f"archive / office file ({os.path.splitext(low)[1]})"
    text = decode_text(data)
    if text is None:
        return "binary", "binary file (not text)"
    head = re.sub(r"^\s*(<\?xml[^>]*\?>\s*)?(<!--.*?-->\s*)*(<!DOCTYPE[^>]*>\s*)?", "", text[:4096], flags=re.S)
    if head[:4].lower() == "<svg":
        return "image", "SVG image (by content)"
    return "text", ""


BOMS = ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe\x00\x00", "utf-32-le"), (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"))


def _texty(s: str) -> bool:
    """ASCII-heavy and free of control characters - real text, not binary decoded by luck."""
    if not s or "\0" in s:
        return False
    sample = s[:20000]
    ascii_ok = sum(1 for ch in sample if " " <= ch <= "~" or ch in "\t\r\n")
    return ascii_ok >= 0.6 * len(sample)


def decode_text(data: bytes) -> str | None:
    """The file as text, or None when it is binary. UTF-16 / UTF-32 (with or without a BOM) are
    decoded; anything else without NUL bytes is read as UTF-8 (8-bit encodings keep ASCII)."""
    for bom, enc in BOMS:
        if data.startswith(bom):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                return None
    if b"\0" not in data:
        return data.decode("utf-8", "replace")
    for enc, unit in (("utf-32-le", 4), ("utf-32-be", 4), ("utf-16-le", 2), ("utf-16-be", 2)):
        try:
            s = data[: len(data) - len(data) % unit].decode(enc)
        except UnicodeDecodeError:
            continue
        if _texty(s):
            return s
    return None


# ---------------------------------------------------------------- term hashing (one definition)
def tokens(text: str) -> list[tuple[str, int]]:
    """(lowercased token, start offset) for every token of text - the normalisation for terms AND files."""
    return [(m.group(0).lower(), m.start()) for m in TOKEN.finditer(text)]


def units(text: str) -> list[tuple[str, int]]:
    """(unit, start offset): each token split at letter<->digit and camelCase boundaries. A decimal
    stays ONE unit with its dot (`1234.56`, never `1234` + `56` or `123456`), and a dot-digits run after
    letters keeps its dot (`rev` + `.2`), so "".join(units(t)) == canonical_of(t) for every term t."""
    out = []
    for t in TOKEN.finditer(text):
        for m in UNIT.finditer(t.group(0)):
            out.append((m.group(0).lower(), t.start() + m.start()))
    return out


def term_hash(salt: str, canonical: str) -> str:
    return hashlib.sha256(f"{salt}\0{canonical}".encode()).hexdigest()


def canonical_of(term: str) -> str:
    toks = [t for t, _ in tokens(term)]
    if not toks:
        raise ValueError("term has no letters or digits")
    return "".join(toks)


def hash_term(salt: str, term: str) -> tuple[str, int]:
    """(hash, token count) of a term; raises on a term with no tokens."""
    return term_hash(salt, canonical_of(term)), len(tokens(term))


def index_config(cfg: dict) -> dict:
    """Derived lookup tables (keys starting with '_' are never saved)."""
    cfg["_hashes"] = {t["sha256"]: t["id"] for t in cfg["terms"]}
    cfg["_hashes_b"] = {bytes.fromhex(t["sha256"]): t["id"] for t in cfg["terms"]}
    lens = {int(t["len"]) for t in cfg["terms"] if int(t.get("len", 0)) >= GLUE_MIN_LEN}
    cfg["_legacy"] = [t["id"] for t in cfg["terms"] if "len" not in t]
    if cfg["_legacy"]:
        lens |= set(range(GLUE_MIN_LEN, GLUE_LEGACY_MAX_LEN + 1))
    cfg["_glue_lens"] = sorted(lens)
    cfg["_hit_cache"] = {}
    return cfg


def load_config(path: str = CONFIG) -> dict:
    cfg = json.load(open(path))
    # one allowlist for every non-text blob; the older image-only key is read too
    cfg["blob_allowlist"] = {**cfg.pop("image_allowlist", {}), **cfg.get("blob_allowlist", {})}
    return index_config(cfg)


def save_config(cfg: dict, path: str = CONFIG) -> None:
    out = {k: v for k, v in cfg.items() if not k.startswith("_")}
    with open(path, "w") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")


def _ngram_hits(seq: list[tuple[str, int]], max_n: int, salt: str, hashes: dict, tier: str, out: dict) -> None:
    for i in range(len(seq)):
        canon = ""
        for n in range(1, max_n + 1):
            if i + n > len(seq):
                break
            canon += seq[i + n - 1][0]
            tid = hashes.get(term_hash(salt, canon))
            if tid:
                out.setdefault((tid, seq[i][1]), tier)


def _inside_number(text: str, o: int, step: int) -> bool:
    """True when the digit at text[o] continues a number on side `step` (-1 before, +1 after): an
    adjacent digit, or a decimal point with a digit beyond it. Checked on the ORIGINAL text, so a
    separator (space, dash, comma) ends a number."""
    d = "0123456789"
    if not (0 <= o < len(text)) or text[o] not in d:
        return False
    n1, n2 = o + step, o + 2 * step
    if not 0 <= n1 < len(text):
        return False
    return text[n1] in d or (text[n1] == "." and 0 <= n2 < len(text) and text[n2] in d)


def _glued_hits(text: str, cfg: dict, out: dict) -> None:
    """The stream is canonical(text): every token concatenated, the same normalisation as a stored
    term (letters / digits lowercased, a decimal keeps its dot), so a term matches exactly as stored."""
    lens = cfg["_glue_lens"]
    if not lens:
        return
    runs = [(m.start(), m.group(0)) for m in TOKEN.finditer(text)]
    if not runs:
        return
    run_pos, acc = [], 0  # stream offset where each run starts
    for _, r in runs:
        run_pos.append(acc)
        acc += len(r)
    s = "".join(r for _, r in runs).lower().encode("ascii")
    hashes = cfg["_hashes_b"]
    base = hashlib.sha256(f"{cfg['salt']}\0".encode())
    lo, hi, want = lens[0], lens[-1], set(lens)
    n = len(s)
    for i in range(n - lo + 1):
        h = base.copy()
        h.update(s[i:i + lo - 1])
        for L in range(lo, min(hi, n - i) + 1):
            h.update(s[i + L - 1:i + L])
            if L not in want:
                continue
            tid = hashes.get(h.copy().digest())
            if not tid:
                continue
            # a hit may not start or end inside a longer number of the ORIGINAL text
            k = bisect.bisect_right(run_pos, i) - 1
            start = runs[k][0] + (i - run_pos[k])
            j = i + L - 1
            kj = bisect.bisect_right(run_pos, j) - 1
            end = runs[kj][0] + (j - run_pos[kj])
            if _inside_number(text, start, -1) or _inside_number(text, end, +1):
                continue
            out.setdefault((tid, start), "glued")


TIERS = ("token", "unit", "glued")


def term_hits(text: str, cfg: dict, tiers: tuple[str, ...] = TIERS) -> list[tuple[str, int, int, str]]:
    """(term id, line, column, tier) for every protected-term hit in text. Every scan uses all three
    tiers; `tiers` exists so a test can prove one tier on its own."""
    if not cfg["_hashes"]:
        return []
    salt, hashes, max_n = cfg["salt"], cfg["_hashes"], int(cfg["max_n"])
    found: dict[tuple[str, int], str] = {}
    if "token" in tiers:
        _ngram_hits(tokens(text), max_n, salt, hashes, "token", found)
    if "unit" in tiers:
        _ngram_hits(units(text), max_n + UNIT_EXTRA_N, salt, hashes, "unit", found)
    if "glued" in tiers:
        _glued_hits(text, cfg, found)
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    out = []
    for (tid, off), tier in sorted(found.items(), key=lambda kv: kv[0][1]):
        ln = bisect.bisect_right(line_starts, off)
        out.append((tid, ln, off - line_starts[ln - 1] + 1, tier))
    return out


# ---------------------------------------------------------------- rules
def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _pinned(path: str, sha: str, cfg: dict) -> str | None:
    """None when path is pinned at this sha; otherwise why not."""
    pinned = cfg["blob_allowlist"].get(path)
    if pinned is None:
        return "not on the pinned blob allowlist"
    if pinned != sha:
        return f"on the blob allowlist but its content changed (blob {sha[:10]} != pinned {pinned[:10]})"
    return None


def raw_base64(text: str) -> int:
    """Length of the first base64-looking run (see RAW_B64), or 0."""
    for m in RAW_B64.finditer(text):
        run = re.sub(r"\s", "", m.group(0))
        if re.search(r"[A-Z]", run) and re.search(r"[a-z]", run) and re.search(r"[0-9]", run) \
                and not re.fullmatch(r"[0-9A-Fa-f]+", run.rstrip("=")):
            return len(run)
    return 0


def check_blob(path: str, data: bytes, sha: str | None, cfg: dict) -> list[str]:
    """Findings for one file (path relative to the repo root)."""
    found = []
    sha = sha or blob_sha(data)
    if any(f"/{d}" in "/" + path for d in FORBIDDEN_DIRS):
        found.append("path under tools/calcgraph-reference/data/sets/ or tools/calcgraph-reference/data/labels/ (derived from the drawing set)")
    kind, label = classify(path, data)
    if kind == "pdf":
        # a .pdf is never allowed; a file holding a PDF header (e.g. a text file quoting one at a line
        # start) is blocked unless pinned by path + sha, like any other non-text blob
        if label == "PDF file":
            found.append("PDF file")
        elif why := _pinned(path, sha, cfg):
            found.append(f"{label} {why}")
        return found
    if kind != "text":  # image / archive / office / SVG / unknown binary: pinned or blocked
        why = _pinned(path, sha, cfg)
        if why:
            found.append(f"{label} {why}")
        if kind != "image" or not label.startswith("SVG"):
            return found  # bytes are not text: path/type rules only
    text = decode_text(data) or ""
    if (m := DATA_URI.search(text)) and _pinned(path, sha, cfg):
        found.append(f"embedded base64 data: URI ({len(m.group(1))} chars) {_pinned(path, sha, cfg)}")
    elif (b64 := raw_base64(text)) and _pinned(path, sha, cfg):
        found.append(f"raw base64 payload ({b64} chars, no data: prefix) {_pinned(path, sha, cfg)}")
    cache = cfg.setdefault("_hit_cache", {})
    if sha not in cache:
        cache[sha] = term_hits(text, cfg)
    allowed = set(cfg["term_allowlist"].get(path, []))
    for tid, ln, col, tier in cache[sha]:
        if tid not in allowed:
            found.append(f"contains protected term {tid} (line {ln}, col {col}, {tier} tier)")
    return found


def scan_staged(root: str, cfg: dict) -> dict[str, list[str]]:
    out = {}
    # every staged path that still exists: added, copied, modified, renamed AND type-changed
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z", cwd=root).split("\0")
    for p in filter(None, names):
        mode = git("ls-files", "-s", "-z", "--", p, cwd=root).split(" ", 1)[0]
        if mode == "160000":  # submodule gitlink: no blob
            continue
        data = git("show", f":{p}", cwd=root, binary=True)
        f = check_blob(p, data, blob_sha(data), cfg)
        if f:
            out[p] = f
    return out


def scan_tree(root: str, cfg: dict, rev: str = "HEAD") -> dict[str, list[str]]:
    out = {}
    for line in git("ls-tree", "-r", "-z", rev, cwd=root).split("\0"):
        if not line:
            continue
        meta, p = line.split("\t", 1)
        _, kind, sha = meta.split()
        if kind != "blob":
            continue
        f = check_blob(p, git("cat-file", "blob", sha, cwd=root, binary=True), sha, cfg)
        if f:
            out[p] = f
    return out


def introduced_blobs(root: str, spec: str) -> list[tuple[str, str, str]]:
    """(commit, path, blob sha) for every blob a commit in spec introduces at a path. Merge commits
    are diffed against EACH parent (-m), so content written in a merge resolution is included; type
    changes count. Every blob object reachable in spec but not seen that way (rev-list --objects) is
    added too, under the path rev-list names."""
    revs = git("rev-list", spec, cwd=root).split()
    out, seen = [], set()
    for c in revs:
        raw = git("diff-tree", "--root", "-m", "--no-commit-id", "-r", "-z", "--diff-filter=ACMRT", c, cwd=root)
        parts = raw.split("\0")
        i = 0
        while i < len(parts) - 1:
            meta = parts[i]
            if not meta.startswith(":"):
                i += 1
                continue
            f = meta.split()
            status, mode, sha = f[4], f[1], f[3]
            if status[:1] in "RC":
                p, i = parts[i + 2], i + 3
            else:
                p, i = parts[i + 1], i + 2
            if mode == "160000" or (p, sha) in seen:
                continue
            seen.add((p, sha))
            out.append((c, p, sha))
    seen_sha = {s for _, s in seen}
    objs = [ln.split(" ", 1) for ln in git("rev-list", "--objects", spec, cwd=root).splitlines()]
    named = {o[0]: (o[1] if len(o) > 1 else "") for o in objs}
    if named:
        types = git("cat-file", "--batch-check=%(objectname) %(objecttype)", cwd=root,
                    stdin="\n".join(named).encode() + b"\n").split("\n")
        for ln in filter(None, types):
            sha, typ = ln.split()
            if typ == "blob" and sha not in seen_sha:
                out.append(("objects", named[sha], sha))
    return out


def scan_range(root: str, cfg: dict, spec: str) -> dict[str, list[str]]:
    out = {}
    for c, p, sha in introduced_blobs(root, spec):
        f = check_blob(p, git("cat-file", "blob", sha, cwd=root, binary=True), sha, cfg)
        if f:
            out[f"{c[:10]} {p}"] = f
    return out


def _has_commit(root: str, rev: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{rev}^{{commit}}"], cwd=root, capture_output=True).returncode == 0


def push_spec(root: str, before: str, after: str, base: str = "origin/prod", ref: str = "",
              remote: str = "origin") -> tuple[str | None, str]:
    """(range spec, why) for what a push INTRODUCES relative to what the repo already accepted, or
    (None, why) when that cannot be determined.
      - an update (before is a commit): before..after; a force-push's old head that is not in the
        clone is fetched from `remote` by sha first
      - a new branch (before all zeros): base..after, the commits not reachable from the default
        branch - unless the new branch IS the base (nothing to compare it with)
    Never the full history: the default branch's history predates the guard (it holds unpinned
    screenshots and .DS_Store versions) and is already public, so a history scan could only fail."""
    if before and before.strip("0"):
        if not _has_commit(root, before):
            subprocess.run(["git", "fetch", "--no-tags", "--quiet", remote, before], cwd=root, capture_output=True)
        if _has_commit(root, before):
            return f"{before}..{after}", f"push update {before[:10]}..{after[:10]}"
        return None, f"the pushed-over head {before[:10]} is not in the clone and could not be fetched from {remote}"
    base_branch = base.split("/", 1)[1] if base.startswith(f"{remote}/") else base
    if ref and ref == base_branch:
        return None, f"the push created the base branch {base_branch} itself"
    if not _has_commit(root, base):
        return None, f"the base {base} is not in the clone"
    return f"{base}..{after}", f"new branch: commits not on {base}"


def scan_push(root: str, cfg: dict, before: str, after: str, base: str, ref: str) -> int:
    spec, why = push_spec(root, before, after, base, ref)
    if spec:
        n = len(git("rev-list", spec, cwd=root).split())
        return report(scan_range(root, cfg, spec), f"{n} commits in {spec} ({why}), merges included", cfg)
    # GitHub Actions annotation: shows on the run and the commit, so an unscanned history is never silent
    print(f"::warning title=copyright guard::history of this push was NOT scanned ({why}); "
          f"only the tree of {after[:10]} was")
    return report(scan_tree(root, cfg, after), f"files in {after[:10]} (push history not scanned: {why})", cfg)


def scan_paths(root: str, cfg: dict, paths: list[str]) -> dict[str, list[str]]:
    out = {}
    for fp in paths:
        ap = os.path.abspath(fp)
        if not os.path.isfile(ap):
            continue
        rel = os.path.relpath(ap, root)
        data = open(ap, "rb").read()
        f = check_blob(rel, data, blob_sha(data), cfg)
        if f:
            out[rel] = f
    return out


def report(found: dict[str, list[str]], what: str, cfg: dict | None = None) -> int:
    if cfg and cfg.get("_legacy"):
        print(f"copyright guard: note - {len(cfg['_legacy'])} term(s) stored without `len` are glue-scanned at every "
              f"length {GLUE_MIN_LEN}..{GLUE_LEGACY_MAX_LEN} (slower); re-enter them with --add-term to record it")
    if not found:
        print(f"copyright guard: clean ({what})")
        return 0
    print(f"copyright guard: {len(found)} file(s) blocked ({what}):")
    for p, fs in sorted(found.items()):
        for f in fs:
            print(f"  {p}: {f}")
    print("Derived data belongs in a gitignored dir (tools/calcgraph-reference/data/sets/, tools/calcgraph-reference/data/labels/). If a file must "
          "carry a protected term, add its path and the term id to term_allowlist in "
          "tools/calcgraph-reference/scripts/copyright_guard.json; pin a synthetic image or binary with --allow-blob. Never commit the PDFs "
          "or anything rendered or extracted from them.")
    return 1


# ---------------------------------------------------------------- adding terms
def add_terms(lines: list[str], cfg: dict) -> list[str]:
    """Append the hash (and canonical length) of each non-blank line to cfg; a term already stored
    gets its length backfilled. Returns the ids (no term is ever echoed)."""
    ids = []
    used = {t["id"] for t in cfg["terms"]}
    nxt = 1 + max([int(i[1:]) for i in used if i[1:].isdigit()] or [0])
    by_hash = {t["sha256"]: t for t in cfg["terms"]}
    for line in lines:
        if not line.strip():
            continue
        canon = canonical_of(line)
        h, n = term_hash(cfg["salt"], canon), len(tokens(line))
        if h in by_hash:
            t = by_hash[h]
            note = " (already present)" if "len" in t else " (already present; length recorded)"
            t["len"] = len(canon)
            ids.append(t["id"] + note)
            continue
        tid = f"t{nxt}"
        nxt += 1
        t = {"id": tid, "sha256": h, "len": len(canon)}
        cfg["terms"].append(t)
        by_hash[h] = t
        cfg["max_n"] = max(int(cfg.get("max_n", 1)), n)
        ids.append(tid)
    index_config(cfg)
    return ids


# ---------------------------------------------------------------- self-test
def _rand_word(k: int = 7) -> str:
    return "".join(secrets.choice("bcdfghjklmnpqrstvwxz") for _ in range(k))


def throwaway_config() -> dict:
    """The real salt and allowlists, no real term: for tests that plant runtime-generated terms."""
    real = load_config()
    return index_config({**real, "terms": [], "max_n": 1, "term_allowlist": {}})


def self_test() -> int:
    real = load_config()
    cfg = throwaway_config()
    w1, w2, w3 = _rand_word().capitalize(), _rand_word(), _rand_word(6)
    num = str(secrets.randbelow(9_000_000) + 1_000_000)
    n5, d1 = str(secrets.randbelow(90_000) + 10_000), str(secrets.randbelow(9) + 1)
    tid, nid, did, sid, pid = add_terms([f"{w1} {w2}", num, f"{n5}-{d1}", w3, f"{n5}.{d1}{d1}"], cfg)
    ok = True

    def expect(label: str, got: list[str], want: str | None) -> None:
        nonlocal ok
        hit = any(want in g for g in got) if want else not got
        print(f"{'PASS' if hit else 'FAIL'}  {label}: {got}")
        ok &= hit

    png = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"
    expect("PDF by name", check_blob("x/report.pdf", b"anything", None, cfg), "PDF file")
    expect("PDF by bytes", check_blob("x/notes.txt", b"%PDF-1.7 ...", None, cfg), "PDF content")
    expect("PDF content can be pinned", check_blob("x/notes.txt", b"%PDF-1.7 ...", None,
                                                    {**cfg, "blob_allowlist": {"x/notes.txt": blob_sha(b"%PDF-1.7 ...")}}), None)
    expect("text starting 8BPS is text", check_blob("x/n.txt", b"8BPS is a magic, in prose\n", None, cfg), None)
    expect("text with ustar at 257 is text", check_blob("x/n.txt", b"a" * 257 + b"ustar\n", None, cfg), None)
    expect("unpinned image", check_blob("x/shot.png", png, None, cfg), "not on the pinned blob allowlist")
    expect("unpinned image in public/", check_blob("public/thumb.png", png, None, cfg), "PNG image not on")
    expect("PNG renamed .bin", check_blob("x/page.bin", png, None, cfg), "PNG image not on")
    expect("PNG with no extension", check_blob("x/page", png, None, cfg), "PNG image not on")
    expect("HEIC by content", check_blob("x/a.dat", b"\0\0\0\x18ftypheic\0\0\0\0mif1heic", None, cfg), "HEIF / AVIF")
    expect("AVIF by name", check_blob("x/a.avif", b"whatever", None, cfg), "image (.avif)")
    expect("docx / zip by content", check_blob("x/notes.txt", b"PK\x03\x04\x14\0\0\0\x08\0", None, cfg), "zip archive")
    expect("SVG by name", check_blob("x/plan.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", None, cfg), "SVG image")
    expect("SVG by content", check_blob("x/plan.xml", b"<?xml version='1.0'?>\n<svg></svg>", None, cfg), "SVG image (by content)")
    expect("base64 raster in a text file", check_blob("x/page.html", b"<img src='data:image/png;base64," + b"iVBORw0K" * 40 + b"'>", None, cfg),
           "embedded base64")
    expect("unknown binary", check_blob("x/blob.dat", bytes(range(256)) * 4, None, cfg), "binary file (not text)")
    utf16 = f"prepared by {w1} {w2}\n".encode("utf-16")
    expect("UTF-16 text (BOM) is decoded and scanned", check_blob("x/export.txt", utf16, None, cfg), f"protected term {tid}")
    expect("UTF-16 text (no BOM) is decoded and scanned",
           check_blob("x/export.txt", f"by {w1} {w2}".encode("utf-16-le"), None, cfg), f"protected term {tid}")
    expect("data/sets path", check_blob("tools/calcgraph-reference/data/sets/s/graph.json", b"{}", None, cfg), "data/sets")
    expect("data/labels path", check_blob("tools/calcgraph-reference/data/labels/s/tags.json", b"{}", None, cfg), "data/labels")
    expect("nested data/sets path", check_blob("src/fixtures/tools/calcgraph-reference/data/sets/s/x.json", b"{}", None, cfg), "data/sets")
    planted = f"line one\nprepared by {w1.upper()}-{w2.upper()}, see sheet\n".encode()
    expect("planted term, other case + punctuation, line 2", check_blob("x/a.py", planted, None, cfg),
           f"protected term {tid} (line 2, col 13")
    expect("planted term with separators removed", check_blob("x/b.md", f"x {w1}{w2} y".encode(), None, cfg),
           f"protected term {tid}")
    expect("term glued into a lowercase token (glued tier)", check_blob("x/g.py", f"prj{w1.lower()}{w2}rev2".encode(), None, cfg),
           f"protected term {tid}")
    expect("term in camelCase (unit tier)", check_blob("x/h.ts", f"get{w1}{w2.capitalize()}Value".encode(), None, cfg),
           f"protected term {tid}")
    expect("number glued between letters (unit tier)", check_blob("x/i.ts", f"PRJ{num}Rev2".encode(), None, cfg),
           f"protected term {nid}")
    expect("a decimal is one number: 12345.6 is not a stored 12345-6 (documented)",
           check_blob("x/j.json", f'{{"job": {n5}.{d1}}}'.encode(), None, cfg), None)
    expect("a term stored with a dot is found glued to letters (unit tier)",
           check_blob("x/j.ts", f"Job{n5}.{d1}{d1}".encode(), None, cfg), f"protected term {pid}")
    expect("raw base64 with no data: prefix", check_blob("x/d.json", b'{"img": "' + b"iVBORw0KGgo9" * 30 + b'"}', None, cfg),
           "raw base64")
    expect("planted number", check_blob("x/c.json", f'{{"job": "{num}"}}'.encode(), None, cfg), f"protected term {nid}")
    expect("number inside a decimal is not a hit", check_blob("x/d.ifc", f"(0.{num},1.5)".encode(), None, cfg), None)
    expect("half a term is not a hit", check_blob("x/e.py", f"{w1} other".encode(), None, cfg), None)
    expect(f"RESIDUAL: a term under {GLUE_MIN_LEN} chars glued in one case is not found (documented)",
           check_blob("x/k.py", f"xx{w3}yy".encode(), None, cfg), None)
    expect("clean file passes", check_blob("x/clean.py", b"print('synthetic office, fictional firm')\n", None, cfg), None)
    cfg["term_allowlist"] = {"x/a.py": [tid]}
    expect("term allowlist by path suppresses it", check_blob("x/a.py", planted, None, cfg), None)
    expect("allowlist is per path", check_blob("x/other.py", planted, None, cfg), f"protected term {tid}")
    cfg["term_allowlist"] = {}
    report_txt = " ".join(check_blob("x/a.py", planted, None, cfg))
    expect("report never echoes the term", [] if w2 not in report_txt.lower() else [report_txt], None)
    legacy = index_config({**cfg, "terms": [{k: v for k, v in t.items() if k != "len"} for t in cfg["terms"]]})
    expect("legacy term (no len) is still glue-matched", check_blob("x/g.py", f"prj{w1.lower()}{w2}rev2".encode(), None, legacy),
           f"protected term {tid}")
    pin = {**cfg, "blob_allowlist": {"x/ok.png": blob_sha(png)}}
    expect("pinned blob passes", check_blob("x/ok.png", png, None, pin), None)
    expect("pinned path with new bytes fails", check_blob("x/ok.png", png + b"changed", None, pin), "content changed")
    with tempfile.TemporaryDirectory() as tmp:  # the staged and range paths end to end, in a throwaway repo
        g = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp, check=True,
                                      capture_output=True)
        g("init", "-q", "-b", "main")
        open(os.path.join(tmp, "leak.txt"), "wb").write(planted)
        g("add", "leak.txt")
        expect("staged scan blocks a staged leak", scan_staged(tmp, cfg).get("leak.txt", []), f"protected term {tid}")
        g("rm", "-q", "--cached", "leak.txt")
        os.remove(os.path.join(tmp, "leak.txt"))
        open(os.path.join(tmp, "f.txt"), "w").write("base\n")
        g("add", "f.txt"), g("commit", "-q", "-m", "base")
        g("checkout", "-q", "-b", "side"), open(os.path.join(tmp, "f.txt"), "w").write("side\n")
        g("commit", "-q", "-am", "side")
        g("checkout", "-q", "main"), open(os.path.join(tmp, "f.txt"), "w").write("main\n")
        g("commit", "-q", "-am", "main")
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "side"], cwd=tmp,
                       capture_output=True)  # conflicts
        open(os.path.join(tmp, "f.txt"), "wb").write(planted)  # the leak is in the resolution only
        g("add", "f.txt"), g("commit", "-q", "-m", "merge")
        parents = subprocess.run(["git", "rev-list", "--parents", "-n1", "HEAD"], cwd=tmp, capture_output=True,
                                 text=True).stdout.split()
        got = [f for v in scan_range(tmp, cfg, "HEAD~2..HEAD").values() for f in v] if len(parents) == 3 else []
        expect("range scan sees content written in a merge resolution", got, f"protected term {tid}")
    good = bool(real.get("salt")) and int(real.get("max_n", 0)) >= 1 and all(
        re.fullmatch(r"[0-9a-f]{64}", t["sha256"]) for t in real["terms"]) and real["terms"]
    print(f"{'PASS' if good else 'FAIL'}  real config: salt, max_n and {len(real['terms'])} well-formed term hashes")
    ok &= bool(good)
    print("ALL PASS" if ok else "SELF-TEST FAILED")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", action="store_true")
    g.add_argument("--tracked", action="store_true")
    g.add_argument("--history", nargs="?", const="HEAD", metavar="REV")
    g.add_argument("--range", metavar="A..B")
    g.add_argument("--push", nargs=2, metavar=("BEFORE", "AFTER"),
                   help="CI push event: scan what the push introduces (see push_spec)")
    g.add_argument("--paths", nargs="+")
    g.add_argument("--allow-blob", "--allow-image", dest="allow_blob", metavar="PATH")
    g.add_argument("--add-term", action="store_true", help="read term(s) from stdin, one per line; store only hashes")
    g.add_argument("--self-test", action="store_true")
    ap.add_argument("--base", default="origin/prod", help="--push: the default branch a new branch is compared with")
    ap.add_argument("--ref", default="", help="--push: the pushed branch name (GITHUB_REF_NAME)")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    cfg = load_config()
    if a.add_term:
        if sys.stdin.isatty():
            print("type each term on its own line, then Ctrl-D (input is not echoed back or stored as text)",
                  file=sys.stderr)
        ids = add_terms(sys.stdin.read().splitlines(), cfg)
        save_config(cfg)
        print(f"added {', '.join(ids) or 'nothing'}; max_n = {cfg['max_n']}")
        return
    root = repo_root()
    if a.allow_blob:
        rel = os.path.relpath(os.path.abspath(a.allow_blob), root)
        print(json.dumps({rel: blob_sha(open(a.allow_blob, "rb").read())}))
        print("add this entry to blob_allowlist in tools/calcgraph-reference/scripts/copyright_guard.json - only for a "
              "SYNTHETIC image or binary you have looked at")
        return
    if a.staged:
        sys.exit(report(scan_staged(root, cfg), "staged changes", cfg))
    if a.tracked:
        sys.exit(report(scan_tree(root, cfg), "files in HEAD", cfg))
    if a.push:
        sys.exit(scan_push(root, cfg, a.push[0], a.push[1], a.base, a.ref))
    if a.history or a.range:
        spec = a.history or a.range
        n = len(git("rev-list", spec, cwd=root).split())
        sys.exit(report(scan_range(root, cfg, spec), f"{n} commits in {spec}, merges included", cfg))
    sys.exit(report(scan_paths(root, cfg, a.paths), f"{len(a.paths)} path(s)", cfg))


if __name__ == "__main__":
    main()
