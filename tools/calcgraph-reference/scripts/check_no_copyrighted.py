"""Copyright guard: block committing anything derived from the copyrighted permit set (a private
drawing set + calc package used during development, never part of this repo).

The repo is public. That set carries copyright notices, so no PDF, page render, extracted text,
derived JSON or screenshot of it may enter git. The guard scans the WHOLE repository (repo root
from git: the Vite app in src/ and public/, packages/, tools/, docs, CI config - every path).
Rules (config in tools/calcgraph-reference/scripts/copyright_guard.json):
  1. any *.pdf, or any file with a PDF header (the PDF magic plus a n.n version) at the start of a
     line in its first 1 KB - readers accept junk before it
  2. any NON-TEXT blob not on the blob allowlist, which pins each allowed file by path AND blob
     sha (a re-used path with new bytes fails). A file is classified by its CONTENT as well as its
     name: image magic bytes (PNG, JPEG, GIF, WebP, TIFF, BMP, ICO, PSD, JPEG 2000 / XL, HEIC /
     HEIF / AVIF), archives and office files (zip - which is also docx / xlsx / pptx / odt - OLE
     doc / xls, gzip, bzip2, xz, zstd, 7z, rar, tar), SVG (by name or by an <svg> root element),
     and any other blob holding NUL bytes that does not decode as UTF-16 / UTF-32 text. An image
     name (png, heic, ...) on a file whose bytes are not an image is still treated as an image.
  3. any text file carrying an embedded base64 data: URI payload of 200+ characters (a raster or
     archive smuggled inside SVG / HTML / CSS / JSON / Markdown) unless the file is pinned on the
     blob allowlist
  4. anything under tools/calcgraph-reference/data/sets/ or tools/calcgraph-reference/data/labels/
     (anywhere in the path)
  5. any text file containing a protected term (a distinctive string from the set: firm names,
     project name, job / package / permit numbers), unless the file's path is on the term
     allowlist for that term id. Text is UTF-8 / 8-bit, or UTF-16 / UTF-32 (BOM, or BOM-less
     ASCII-heavy); it is decoded before the scan.

Protected terms are never stored in plaintext - not in the config, not in this script, not in
its self-test. The config holds a random salt, one salted SHA-256 per term, the term's canonical
length (`len`, see below) and `max_n`:
  tokens(text)      = maximal runs of ASCII letters / digits, a decimal number (digits '.' digits)
                      kept as one token, lowercased; everything else (whitespace, punctuation,
                      dashes) separates tokens
  canonical(term)   = its tokens concatenated with no separator, so "Ab-Cd", "ab cd" and "AbCd"
                      are one canonical form
  hash              = sha256(salt + "\\0" + canonical)
A text file is matched in three tiers; a hit is reported as file, line, column and tier plus the
term's opaque id - never the term:
  token tier   every n-gram of 1..max_n consecutive tokens, concatenated
  unit tier    every n-gram of 1..max_n+3 consecutive UNITS, where each token is further split at
               letter <-> digit and camelCase boundaries and a decimal loses its dots; catches
               `PRJ<term>Rev2`, `get<Term>Value`, and `12345.6` for a stored `12345-6`
  glued tier   every substring of the separator-free stream (the file's letters and digits only,
               lowercased) whose length is the canonical length of a stored term of >= GLUE_MIN_LEN
               (8) characters; a hit may not start or end inside a longer digit run (so a term is
               not found inside a decimal or a longer number). Catches a term glued into a longer
               token with no case or digit boundary (`xx<term>yy`, `PRJ<TERM>REV`).
Why 8: below 8 characters a substring of the separator-free stream collides with ordinary words
and identifiers (a 5-letter name inside longer words, a 6-digit number inside the digit runs of
IFC coordinates), so the guard would block legitimate files. At 8+ characters a hit needs the
exact, distinctive term string, and digit runs must match whole.
RESIDUAL (mitigation, not a fix): a term shorter than 8 canonical characters glued to letters or
digits of the same case with no letter/digit or camelCase boundary (all-lowercase `xx<term>yy`,
all-caps `PRJ<TERM>REV`), or a digit-only term merged with adjacent digits, is NOT detected.
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
  python scripts/check_no_copyrighted.py --range A..B        # every (path, blob) introduced in A..B, merges included (CI)
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
UNIT = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+(?:\.[0-9]+)*")
ALNUM = re.compile(r"[0-9A-Za-z]+")
PDF_HEADER = re.compile(rb"(?:^|[\r\n])%PDF-\d\.\d")
DATA_URI = re.compile(r"data:[\w.+-]*/?[\w.+-]*(?:;[\w.+=-]+)*;base64,([A-Za-z0-9+/=\s\\]{200,})")
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
def classify(path: str, data: bytes) -> tuple[str, str]:
    """(kind, label): kind is pdf | image | archive | binary | text. Content first, then name."""
    low = path.lower()
    if low.endswith(".pdf") or PDF_HEADER.search(data[:1024]):
        return "pdf", "PDF file"
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
    """(unit, start offset): each token split at letter<->digit and camelCase boundaries, decimals without dots."""
    out = []
    for t in TOKEN.finditer(text):
        for m in UNIT.finditer(t.group(0)):
            out.append((m.group(0).replace(".", "").lower(), t.start() + m.start()))
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


def _glued_hits(text: str, cfg: dict, out: dict) -> None:
    lens = cfg["_glue_lens"]
    if not lens:
        return
    runs = [(m.start(), m.group(0)) for m in ALNUM.finditer(text)]
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
            # a hit may not start or end inside a longer digit run
            if 48 <= s[i] <= 57 and i > 0 and 48 <= s[i - 1] <= 57:
                continue
            j = i + L - 1
            if 48 <= s[j] <= 57 and j + 1 < n and 48 <= s[j + 1] <= 57:
                continue
            k = bisect.bisect_right(run_pos, i) - 1
            out.setdefault((tid, runs[k][0] + (i - run_pos[k])), "glued")


def term_hits(text: str, cfg: dict) -> list[tuple[str, int, int, str]]:
    """(term id, line, column, tier) for every protected-term hit in text, all three tiers."""
    if not cfg["_hashes"]:
        return []
    salt, hashes, max_n = cfg["salt"], cfg["_hashes"], int(cfg["max_n"])
    found: dict[tuple[str, int], str] = {}
    _ngram_hits(tokens(text), max_n, salt, hashes, "token", found)
    _ngram_hits(units(text), max_n + UNIT_EXTRA_N, salt, hashes, "unit", found)
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


def check_blob(path: str, data: bytes, sha: str | None, cfg: dict) -> list[str]:
    """Findings for one file (path relative to the repo root)."""
    found = []
    sha = sha or blob_sha(data)
    if any(f"/{d}" in "/" + path for d in FORBIDDEN_DIRS):
        found.append("path under tools/calcgraph-reference/data/sets/ or tools/calcgraph-reference/data/labels/ (derived from the drawing set)")
    kind, label = classify(path, data)
    if kind == "pdf":
        found.append("PDF file")
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
    tid, nid, did, sid = add_terms([f"{w1} {w2}", num, f"{n5}-{d1}", w3], cfg)
    ok = True

    def expect(label: str, got: list[str], want: str | None) -> None:
        nonlocal ok
        hit = any(want in g for g in got) if want else not got
        print(f"{'PASS' if hit else 'FAIL'}  {label}: {got}")
        ok &= hit

    png = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"
    expect("PDF by name", check_blob("x/report.pdf", b"anything", None, cfg), "PDF file")
    expect("PDF by bytes", check_blob("x/notes.txt", b"%PDF-1.7 ...", None, cfg), "PDF file")
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
    expect("12345.6 for a stored 12345-6 (unit tier)", check_blob("x/j.json", f'{{"job": {n5}.{d1}}}'.encode(), None, cfg),
           f"protected term {did}")
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
    g.add_argument("--paths", nargs="+")
    g.add_argument("--allow-blob", "--allow-image", dest="allow_blob", metavar="PATH")
    g.add_argument("--add-term", action="store_true", help="read term(s) from stdin, one per line; store only hashes")
    g.add_argument("--self-test", action="store_true")
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
    if a.history or a.range:
        spec = a.history or a.range
        n = len(git("rev-list", spec, cwd=root).split())
        sys.exit(report(scan_range(root, cfg, spec), f"{n} commits in {spec}, merges included", cfg))
    sys.exit(report(scan_paths(root, cfg, a.paths), f"{len(a.paths)} path(s)", cfg))


if __name__ == "__main__":
    main()
