"""Copyright guard: block committing anything derived from the copyrighted Dana Point documents.

The repo is public (Apache-2.0). The Dana Point permit set (plans + calcs) carries copyright
notices, so no PDF, page render, extracted text, derived JSON or screenshot of it may enter git.
The set was retired from the app on 2026-11-14 (the app runs on the synthetic Harbor View building);
local copies of its PDFs and derived data may still exist outside the repo, so the guard stays.
Rules (config in scripts/copyright_guard.json):
  1. any *.pdf, or any file whose bytes start with %PDF
  2. any image (png/jpg/jpeg/gif/webp/tif/tiff/bmp) not on the image allowlist, which pins
     each allowed synthetic image by path AND blob sha (a re-used path with new pixels fails)
  3. anything under data/sets/ or data/labels/ (anywhere in the path)
  4. any text file containing a distinctive string from the Dana Point documents, unless that
     file is on the term allowlist for exactly that term (code/docs that name the set by path)

  python scripts/check_no_copyrighted.py --staged            # pre-commit hook (index contents)
  python scripts/check_no_copyrighted.py --tracked           # every file in HEAD
  python scripts/check_no_copyrighted.py --history [REV]     # every blob ever added on REV's history
  python scripts/check_no_copyrighted.py --range A..B        # blobs added by the commits in A..B (CI)
  python scripts/check_no_copyrighted.py --paths F [F ...]   # files on disk (working tree)
  python scripts/check_no_copyrighted.py --allow-image PATH  # pin a synthetic image (prints the entry)
  python scripts/check_no_copyrighted.py --self-test         # prove each rule fires

Exit 1 on any finding. Matched text is never echoed beyond the term itself.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "copyright_guard.json")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".bmp")
FORBIDDEN_DIRS = ("data/sets/", "data/labels/")


def git(*args: str, cwd: str | None = None, binary: bool = False):
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout
    return out if binary else out.decode()


def repo_root() -> str:
    return git("rev-parse", "--show-toplevel", cwd=HERE).strip()


def load_config(path: str = CONFIG) -> dict:
    cfg = json.load(open(path))
    cfg["_terms"] = [(t["name"], re.compile(t["regex"], re.I)) for t in cfg["terms"]]
    return cfg


def check_blob(path: str, data: bytes, sha: str | None, cfg: dict) -> list[str]:
    """Findings for one file (path relative to the repo root)."""
    found = []
    low = path.lower()
    norm = "/" + path
    if any(f"/{d}" in norm for d in FORBIDDEN_DIRS):
        found.append("path under data/sets/ or data/labels/ (derived from the drawing set)")
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
    text = data.decode("utf-8", "replace")
    allowed = set(cfg["term_allowlist"].get(path, []))
    for name, rx in cfg["_terms"]:
        if name in allowed:
            continue
        m = rx.search(text)
        if m:
            line = text.count("\n", 0, m.start()) + 1
            found.append(f"contains distinctive term {name!r} (line {line})")
    return found


def blob_sha(data: bytes) -> str:
    import hashlib
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
    print("Derived data belongs in a gitignored dir (data/sets/, data/labels/). If a file only names the set by "
          "path, add the term to its entry in scripts/copyright_guard.json term_allowlist; pin a synthetic image "
          "with --allow-image. Never commit the PDFs or anything rendered or extracted from them.")
    return 1


def self_test() -> int:
    cfg = load_config()
    cases = [
        ("x/report.pdf", b"anything", "PDF file"),
        ("x/notes.txt", b"%PDF-1.7 ...", "PDF file"),
        ("x/shot.png", b"\x89PNG\r\n\x1a\n\0", "image not on"),
        ("prototyping/calc-graph/data/sets/s/graph.json", b"{}", "data/sets"),
        ("prototyping/calc-graph/data/labels/s/tags.json", b"{}", "data/labels"),
        ("x/a.py", b"# prepared by K P F F\nx = 'kpff'\n", "'KPFF'"),
        ("x/b.md", b"Model: Dana  Point Harbor\n", "'Dana Point'"),
        ("x/c.json", b'{"job": "1900799"}', "'KPFF job number'"),
    ]
    ok = True
    for p, data, want in cases:
        got = check_blob(p, data, blob_sha(data), cfg)
        hit = any(want in g for g in got)
        print(f"{'PASS' if hit else 'FAIL'}  {p}: {got}")
        ok &= hit
    clean = check_blob("x/clean.py", b"print('synthetic office, fictional firm')\n", None, cfg)
    print(f"{'PASS' if not clean else 'FAIL'}  clean file passes: {clean}")
    ok &= not clean
    # an allowlisted image whose bytes changed must fail
    some = next(iter(cfg["image_allowlist"]), None)
    if some:
        got = check_blob(some, b"\x89PNG\r\n\x1a\n\0changed", "0" * 40, cfg)
        hit = any("content changed" in g for g in got)
        print(f"{'PASS' if hit else 'FAIL'}  re-used allowlisted image path with new bytes: {got}")
        ok &= hit
    # the staged path end to end, in a throwaway repo
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        open(os.path.join(tmp, "leak.txt"), "w").write("KPFF calc page\n")
        subprocess.run(["git", "add", "leak.txt"], cwd=tmp, check=True)
        got = scan_staged(tmp, cfg)
        hit = "leak.txt" in got
        print(f"{'PASS' if hit else 'FAIL'}  staged scan blocks a staged leak: {got}")
        ok &= hit
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
    g.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    root = repo_root()
    cfg = load_config()
    if a.allow_image:
        rel = os.path.relpath(os.path.abspath(a.allow_image), root)
        print(json.dumps({rel: blob_sha(open(a.allow_image, "rb").read())}))
        print("add this entry to image_allowlist in scripts/copyright_guard.json - only for a SYNTHETIC image you have looked at")
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
