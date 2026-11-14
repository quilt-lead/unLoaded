"""Copyright guard: block committing anything derived from the copyrighted permit set (a private
drawing set + calc package used during development, never part of this repo).

The repo is public. That set carries copyright notices, so no PDF, page render, extracted text,
derived JSON or screenshot of it may enter git. The guard scans the WHOLE repository (repo root
from git: the Vite app in src/ and public/, backend/, docs, CI config - every path).
Rules (config in backend/scripts/copyright_guard.json):
  1. any *.pdf, or any file whose bytes start with %PDF
  2. any image (png/jpg/jpeg/gif/webp/tif/tiff/bmp) not on the image allowlist, which pins
     each allowed synthetic image by path AND blob sha (a re-used path with new pixels fails)
  3. anything under backend/data/sets/ or backend/data/labels/ (anywhere in the path)
  4. any text file containing a protected term (a distinctive string from the set: firm names,
     project name, job / package / permit numbers), unless the file's path is on the term
     allowlist for that term id

Protected terms are never stored in plaintext - not in the config, not in this script, not in
its self-test. The config holds a random salt, one salted SHA-256 per term and `max_n`:
  normalise(text) = its tokens: maximal runs of ASCII letters / digits, a decimal number
                    (digits '.' digits) kept as one token, lowercased; everything else
                    (whitespace, punctuation, dashes) separates tokens
  canonical(n-gram) = the n tokens concatenated with no separator, so "Ab-Cd", "ab cd" and
                    "AbCd" are one canonical form (the same collapse as the matcher's loose
                    "ignoring punctuation" tier)
  hash = sha256(salt + "\\0" + canonical)
At scan time every n-gram of 1..max_n consecutive tokens of each text file is hashed; a hit is
reported as file, line, column and token position plus the term's opaque id - never the term.
`max_n` is the largest token count of any stored term. Add a term without it ever touching a
file, argv or shell history:  backend/scripts/check_no_copyrighted.py --add-term   (reads
stdin, one term per line; type it, then Ctrl-D).

The salt only defeats precomputed tables: a short term can still be brute-forced from its hash,
so a hash list is obscurity for short strings, not secrecy. It keeps the identity out of
plaintext search, diffs and indexes, which is what this public repo needs.

  (paths below are from backend/; the script may be run from any directory in the repo)
  python scripts/check_no_copyrighted.py --staged            # pre-commit hook (index contents)
  python scripts/check_no_copyrighted.py --tracked           # every file in HEAD
  python scripts/check_no_copyrighted.py --history [REV]     # every blob ever added on REV's history
  python scripts/check_no_copyrighted.py --range A..B        # blobs added by the commits in A..B (CI)
  python scripts/check_no_copyrighted.py --paths F [F ...]   # files on disk (working tree)
  python scripts/check_no_copyrighted.py --allow-image PATH  # pin a synthetic image (prints the entry)
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
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".bmp")
FORBIDDEN_DIRS = ("backend/data/sets/", "backend/data/labels/")
TOKEN = re.compile(r"[0-9A-Za-z]+(?:\.[0-9]+)*")


def git(*args: str, cwd: str | None = None, binary: bool = False):
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout
    return out if binary else out.decode()


def repo_root() -> str:
    return git("rev-parse", "--show-toplevel", cwd=HERE).strip()


# ---------------------------------------------------------------- term hashing (one definition)
def tokens(text: str) -> list[tuple[str, int]]:
    """(lowercased token, start offset) for every token of text - the normalisation for terms AND files."""
    return [(m.group(0).lower(), m.start()) for m in TOKEN.finditer(text)]


def term_hash(salt: str, canonical: str) -> str:
    return hashlib.sha256(f"{salt}\0{canonical}".encode()).hexdigest()


def hash_term(salt: str, term: str) -> tuple[str, int]:
    """(hash, token count) of a term; raises on a term with no tokens."""
    toks = [t for t, _ in tokens(term)]
    if not toks:
        raise ValueError("term has no letters or digits")
    return term_hash(salt, "".join(toks)), len(toks)


def load_config(path: str = CONFIG) -> dict:
    cfg = json.load(open(path))
    cfg["_hashes"] = {t["sha256"]: t["id"] for t in cfg["terms"]}
    return cfg


def save_config(cfg: dict, path: str = CONFIG) -> None:
    out = {k: v for k, v in cfg.items() if not k.startswith("_")}
    with open(path, "w") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")


def term_hits(text: str, cfg: dict) -> list[tuple[str, int, int, int, int]]:
    """(term id, line, column, first token index, n) for every n-gram (n <= max_n) whose
    canonical hash is a stored term."""
    toks = tokens(text)
    if not toks or not cfg["_hashes"]:
        return []
    salt, hashes, max_n = cfg["salt"], cfg["_hashes"], int(cfg["max_n"])
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    out = []
    for i in range(len(toks)):
        canon = ""
        for n in range(1, max_n + 1):
            if i + n > len(toks):
                break
            canon += toks[i + n - 1][0]
            tid = hashes.get(term_hash(salt, canon))
            if tid:
                off = toks[i][1]
                ln = bisect.bisect_right(line_starts, off)
                out.append((tid, ln, off - line_starts[ln - 1] + 1, i, n))
    return out


# ---------------------------------------------------------------- rules
def check_blob(path: str, data: bytes, sha: str | None, cfg: dict) -> list[str]:
    """Findings for one file (path relative to the repo root)."""
    found = []
    low = path.lower()
    norm = "/" + path
    if any(f"/{d}" in norm for d in FORBIDDEN_DIRS):
        found.append("path under backend/data/sets/ or backend/data/labels/ (derived from the drawing set)")
    if low.endswith(".pdf") or data[:5] == b"%PDF-":
        found.append("PDF file")
    if low.endswith(IMAGE_EXT):
        pinned = cfg["image_allowlist"].get(path)
        if pinned is None:
            found.append("image not on the synthetic-image allowlist")
        elif sha is not None and pinned != sha:
            found.append(f"image on the allowlist but its content changed (blob {sha[:10]} != pinned {pinned[:10]})")
    if b"\0" in data[:8192]:
        return found  # binary: path/type rules only
    allowed = set(cfg["term_allowlist"].get(path, []))
    for tid, ln, col, ti, n in term_hits(data.decode("utf-8", "replace"), cfg):
        if tid in allowed:
            continue
        found.append(f"contains protected term {tid} (line {ln}, col {col}, tokens {ti}..{ti + n - 1})")
    return found


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def scan_staged(root: str, cfg: dict) -> dict[str, list[str]]:
    out = {}
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", cwd=root).split("\0")
    for p in filter(None, names):
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


def scan_commits(root: str, cfg: dict, revs: list[str]) -> dict[str, list[str]]:
    """Every (path, blob) added or modified by the given commits; keyed 'commit path'."""
    out = {}
    seen = set()
    for c in revs:
        raw = git("diff-tree", "--root", "--no-commit-id", "-r", "-z", "--diff-filter=ACMR", c, cwd=root)
        parts = raw.split("\0")
        i = 0
        while i < len(parts) - 1:
            meta, p = parts[i], parts[i + 1]
            i += 2
            if not meta.startswith(":"):
                continue
            sha = meta.split()[3]
            if (p, sha) in seen:
                continue
            seen.add((p, sha))
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


def report(found: dict[str, list[str]], what: str) -> int:
    if not found:
        print(f"copyright guard: clean ({what})")
        return 0
    print(f"copyright guard: {len(found)} file(s) blocked ({what}):")
    for p, fs in sorted(found.items()):
        for f in fs:
            print(f"  {p}: {f}")
    print("Derived data belongs in a gitignored dir (backend/data/sets/, backend/data/labels/). If a file must "
          "carry a protected term, add its path and the term id to term_allowlist in "
          "backend/scripts/copyright_guard.json; pin a synthetic image with --allow-image. Never commit the PDFs "
          "or anything rendered or extracted from them.")
    return 1


# ---------------------------------------------------------------- adding terms
def add_terms(lines: list[str], cfg: dict) -> list[str]:
    """Append the hash of each non-blank line to cfg; returns the new ids (no term is ever echoed)."""
    ids = []
    used = {t["id"] for t in cfg["terms"]}
    nxt = 1 + max([int(i[1:]) for i in used if i[1:].isdigit()] or [0])
    for line in lines:
        if not line.strip():
            continue
        h, n = hash_term(cfg["salt"], line)
        if h in cfg["_hashes"]:
            ids.append(cfg["_hashes"][h] + " (already present)")
            continue
        tid = f"t{nxt}"
        nxt += 1
        cfg["terms"].append({"id": tid, "sha256": h})
        cfg["_hashes"][h] = tid
        cfg["max_n"] = max(int(cfg.get("max_n", 1)), n)
        ids.append(tid)
    return ids


# ---------------------------------------------------------------- self-test
def _rand_word(k: int = 7) -> str:
    return "".join(secrets.choice("bcdfghjklmnpqrstvwxz") for _ in range(k))


def self_test() -> int:
    real = load_config()
    # a throwaway config: the real salt, a runtime-generated term, no real term anywhere
    cfg = {**real, "terms": [], "_hashes": {}, "max_n": 1, "term_allowlist": {}}
    w1, w2 = _rand_word().capitalize(), _rand_word()
    num = str(secrets.randbelow(9_000_000) + 1_000_000)
    ids = add_terms([f"{w1} {w2}", num], cfg)
    tid, nid = ids
    ok = True

    def expect(label: str, got: list[str], want: str | None) -> None:
        nonlocal ok
        hit = any(want in g for g in got) if want else not got
        print(f"{'PASS' if hit else 'FAIL'}  {label}: {got}")
        ok &= hit

    expect("PDF by name", check_blob("x/report.pdf", b"anything", None, cfg), "PDF file")
    expect("PDF by bytes", check_blob("x/notes.txt", b"%PDF-1.7 ...", None, cfg), "PDF file")
    expect("unpinned image", check_blob("x/shot.png", b"\x89PNG\r\n\x1a\n\0", None, cfg), "image not on")
    expect("unpinned image in public/", check_blob("public/thumb.png", b"\x89PNG\r\n\x1a\n\0", None, cfg), "image not on")
    expect("backend/data/sets path", check_blob("backend/data/sets/s/graph.json", b"{}", None, cfg), "data/sets")
    expect("backend/data/labels path", check_blob("backend/data/labels/s/tags.json", b"{}", None, cfg), "data/labels")
    expect("nested data/sets path", check_blob("src/fixtures/backend/data/sets/s/x.json", b"{}", None, cfg), "data/sets")
    planted = f"line one\nprepared by {w1.upper()}-{w2.upper()}, see sheet\n".encode()
    expect("planted term, other case + punctuation, line 2", check_blob("x/a.py", planted, None, cfg),
           f"protected term {tid} (line 2, col 13")
    expect("planted term with separators removed", check_blob("x/b.md", f"x {w1}{w2} y".encode(), None, cfg),
           f"protected term {tid}")
    expect("planted number", check_blob("x/c.json", f'{{"job": "{num}"}}'.encode(), None, cfg), f"protected term {nid}")
    expect("number inside a decimal is not a hit", check_blob("x/d.ifc", f"(0.{num},1.5)".encode(), None, cfg), None)
    expect("half a term is not a hit", check_blob("x/e.py", f"{w1} other".encode(), None, cfg), None)
    expect("clean file passes", check_blob("x/clean.py", b"print('synthetic office, fictional firm')\n", None, cfg), None)
    cfg["term_allowlist"] = {"x/a.py": [tid]}
    expect("term allowlist by path suppresses it", check_blob("x/a.py", planted, None, cfg), None)
    expect("allowlist is per path", check_blob("x/other.py", planted, None, cfg), f"protected term {tid}")
    cfg["term_allowlist"] = {}
    report_txt = " ".join(check_blob("x/a.py", planted, None, cfg))
    expect("report never echoes the term", [] if w2 not in report_txt.lower() else [report_txt], None)
    some = next(iter(cfg["image_allowlist"]), None)
    if some:  # an allowlisted image whose bytes changed must fail
        expect("re-used allowlisted image path with new bytes",
               check_blob(some, b"\x89PNG\r\n\x1a\n\0changed", "0" * 40, cfg), "content changed")
    with tempfile.TemporaryDirectory() as tmp:  # the staged path end to end, in a throwaway repo
        subprocess.run(["git", "init", "-q", tmp], check=True)
        open(os.path.join(tmp, "leak.txt"), "wb").write(planted)
        subprocess.run(["git", "add", "leak.txt"], cwd=tmp, check=True)
        got = scan_staged(tmp, cfg)
        expect("staged scan blocks a staged leak", got.get("leak.txt", []), f"protected term {tid}")
    # the real config is well formed
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
    g.add_argument("--allow-image", metavar="PATH")
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
    if a.allow_image:
        rel = os.path.relpath(os.path.abspath(a.allow_image), root)
        print(json.dumps({rel: blob_sha(open(a.allow_image, "rb").read())}))
        print("add this entry to image_allowlist in backend/scripts/copyright_guard.json - only for a SYNTHETIC "
              "image you have looked at")
        return
    if a.staged:
        sys.exit(report(scan_staged(root, cfg), "staged changes"))
    if a.tracked:
        sys.exit(report(scan_tree(root, cfg), "files in HEAD"))
    if a.history:
        revs = git("rev-list", a.history, cwd=root).split()
        sys.exit(report(scan_commits(root, cfg, revs), f"{len(revs)} commits on {a.history}"))
    if a.range:
        revs = git("rev-list", a.range, cwd=root).split()
        sys.exit(report(scan_commits(root, cfg, revs), f"{len(revs)} commits in {a.range}"))
    sys.exit(report(scan_paths(root, cfg, a.paths), f"{len(a.paths)} path(s)"))


if __name__ == "__main__":
    main()
