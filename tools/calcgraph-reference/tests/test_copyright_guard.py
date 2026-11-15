"""Copyright guard (scripts/check_no_copyrighted.py): content classification, range / staged scans
and the three term-matching tiers. Every protected term here is generated at runtime - no real
term is ever written to a file. Runs in CI only (a hook blocks local test runners)."""
import importlib.util
import os
import secrets
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_spec = importlib.util.spec_from_file_location("guard", os.path.join(ROOT, "scripts", "check_no_copyrighted.py"))
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

PNG = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR\0\0\0\x10"


def word(k=7):
    return "".join(secrets.choice("bcdfghjklmnpqrstvwxz") for _ in range(k))


@pytest.fixture()
def planted():
    """(cfg, ids, terms) with a two-word term, a 7-digit number, a dashed number and a short word."""
    cfg = guard.throwaway_config()
    w1, w2, short = word().capitalize(), word(), word(6)
    num = str(secrets.randbelow(9_000_000) + 1_000_000)
    n5, d1 = str(secrets.randbelow(90_000) + 10_000), str(secrets.randbelow(9) + 1)
    ids = guard.add_terms([f"{w1} {w2}", num, f"{n5}-{d1}", short], cfg)
    return cfg, ids, dict(w1=w1, w2=w2, num=num, n5=n5, d1=d1, short=short)


def hits(found, tid):
    return [f for f in found if f"protected term {tid}" in f]


def test_self_test_passes():
    assert guard.self_test() == 0


# ---------------------------------------------------------------- finding 1: classify by content
@pytest.mark.parametrize("path,data,want", [
    ("x/page.bin", PNG, "PNG image"),                       # rejected before: extension-only image rule
    ("x/page", PNG, "PNG image"),                           # no extension at all
    ("x/a.heic", b"\0\0\0\x18ftypheic\0\0\0\0mif1", "HEIF / AVIF"),
    ("x/a.dat", b"\0\0\0\x1cftypavif\0\0\0\0avifmif1", "HEIF / AVIF"),
    ("x/sheet.xlsx", b"PK\x03\x04\x14\0\x06\0", "zip archive"),
    ("x/notes.txt", b"PK\x03\x04\x14\0\x06\0", "zip archive"),
    ("x/old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\0\0", "OLE compound file"),
    ("x/plan.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>", "SVG image"),
    ("x/plan.xml", b"<?xml version='1.0'?>\n<!-- c -->\n<svg></svg>", "SVG image (by content)"),
    ("x/blob.dat", bytes(range(256)) * 8, "binary file (not text)"),
    ("x/a.avif", b"not really an image", "image (.avif)"),
])
def test_non_text_blobs_must_be_pinned(path, data, want):
    cfg = guard.throwaway_config()
    found = guard.check_blob(path, data, None, cfg)
    assert any(want in f and "not on the pinned blob allowlist" in f for f in found), found


def test_pinned_blob_passes_and_changed_bytes_fail():
    cfg = {**guard.throwaway_config(), "blob_allowlist": {"x/page.bin": guard.blob_sha(PNG)}}
    assert guard.check_blob("x/page.bin", PNG, None, cfg) == []
    assert any("content changed" in f for f in guard.check_blob("x/page.bin", PNG + b"x", None, cfg))


def test_base64_raster_in_text_must_be_pinned():
    cfg = guard.throwaway_config()
    svg_text = b"<div><img src=\"data:image/png;base64," + b"iVBORw0KGgo=" * 30 + b"\"/></div>"
    assert any("embedded base64" in f for f in guard.check_blob("x/page.md", svg_text, None, cfg))
    assert guard.check_blob("x/page.md", b"data:image/png;base64,iVBOR short", None, cfg) == []


def test_utf16_and_utf32_text_is_term_scanned(planted):
    cfg, (tid, *_), t = planted
    text = f"sheet notes\nprepared by {t['w1']} {t['w2']}\n"
    for data in (text.encode("utf-16"), text.encode("utf-16-le"), text.encode("utf-16-be"), text.encode("utf-32")):
        assert hits(guard.check_blob("x/export.txt", data, None, cfg), tid), data[:8]


def test_pdf_header_after_junk():
    cfg = guard.throwaway_config()
    assert "PDF file" in guard.check_blob("x/a.txt", b"junk\n%PDF-1.4\n", None, cfg)
    assert guard.check_blob("x/doc.md", b"the guard looks for a %PDF- header, e.g. %PDF-1.7", None, cfg) == []


# ---------------------------------------------------------------- finding 3: glued terms
def test_long_term_glued_into_a_token(planted):
    cfg, (tid, *_), t = planted
    for s in (f"prj{t['w1'].lower()}{t['w2']}rev2", f"PRJ{t['w1'].upper()}{t['w2'].upper()}REV"):
        found = hits(guard.check_blob("x/a.py", s.encode(), None, cfg), tid)
        assert found and "glued tier" in found[0], s


def test_camel_case_and_letter_digit_boundaries(planted):
    cfg, (tid, nid, did, _), t = planted
    assert hits(guard.check_blob("x/a.ts", f"get{t['w1']}{t['w2'].capitalize()}Value".encode(), None, cfg), tid)
    assert hits(guard.check_blob("x/a.ts", f"PRJ{t['num']}Rev2".encode(), None, cfg), nid)
    assert hits(guard.check_blob("x/a.json", f"{{\"job\": {t['n5']}.{t['d1']}}}".encode(), None, cfg), did)


def test_no_hit_inside_a_longer_number(planted):
    cfg, _, t = planted
    assert guard.check_blob("x/a.ifc", f"#12=IFCCARTESIANPOINT((0.{t['num']},1.5));".encode(), None, cfg) == []
    long_num = guard.add_terms([str(secrets.randbelow(9 * 10**9) + 10**9)], cfg)[0]  # 10 digits: glued tier
    digits = [x for x in cfg["terms"] if x["id"] == long_num][0]
    assert digits["len"] == 10


def test_glued_tier_respects_digit_runs():
    cfg = guard.throwaway_config()
    n10 = str(secrets.randbelow(9 * 10**9) + 10**9)
    tid = guard.add_terms([n10], cfg)[0]
    assert hits(guard.check_blob("x/a.txt", f"PRJ{n10}REV".encode(), None, cfg), tid)
    assert guard.check_blob("x/a.txt", f"v=3{n10}7".encode(), None, cfg) == []  # inside a longer number


def test_short_term_residual_is_documented(planted):
    cfg, _, t = planted
    assert len(t["short"]) < guard.GLUE_MIN_LEN
    assert guard.check_blob("x/a.py", f"xx{t['short']}yy".encode(), None, cfg) == []
    doc = guard.__doc__
    assert "RESIDUAL (mitigation, not a fix)" in doc and str(guard.GLUE_MIN_LEN) in doc
    readme = open(os.path.join(ROOT, "README.md")).read()
    assert "mitigation, not a fix" in readme


def test_legacy_term_without_len_is_glue_scanned(planted):
    cfg, (tid, *_), t = planted
    legacy = guard.index_config({**cfg, "terms": [{k: v for k, v in x.items() if k != "len"} for x in cfg["terms"]]})
    assert hits(guard.check_blob("x/a.py", f"zz{t['w1'].lower()}{t['w2']}zz".encode(), None, legacy), tid)
    # re-entering the term backfills its length
    ids = guard.add_terms([f"{t['w1']} {t['w2']}"], legacy)
    assert "length recorded" in ids[0] and not [x for x in legacy["_legacy"] if x == tid]


def test_report_never_echoes_a_term(planted):
    cfg, _, t = planted
    found = " ".join(guard.check_blob("x/a.py", f"prj{t['w1'].lower()}{t['w2']}rev".encode(), None, cfg)).lower()
    assert t["w2"] not in found and t["w1"].lower() not in found


# ---------------------------------------------------------------- finding 2: range and staged scans
def _git(repo, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.symlinks=true", *a],
                          cwd=repo, check=True, capture_output=True, text=True).stdout


def test_range_scans_merge_resolution(tmp_path, planted):
    cfg, (tid, *_), t = planted
    repo = str(tmp_path)
    _git(repo, "init", "-q", "-b", "main")
    f = tmp_path / "f.txt"
    f.write_text("base\n"); _git(repo, "add", "f.txt"); _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "side"); f.write_text("side\n"); _git(repo, "commit", "-q", "-am", "side")
    _git(repo, "checkout", "-q", "main"); f.write_text("main\n"); _git(repo, "commit", "-q", "-am", "main")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "side"], cwd=repo,
                   capture_output=True)  # conflict
    f.write_text(f"resolved by {t['w1']} {t['w2']}\n")  # the leak exists only in the merge resolution
    (tmp_path / "new.txt").write_text(f"{t['num']}\n")  # and a file added in the merge commit itself
    _git(repo, "add", "f.txt", "new.txt"); _git(repo, "commit", "-q", "-m", "merge")
    assert len(_git(repo, "rev-list", "--parents", "-n1", "HEAD").split()) == 3  # really a merge commit
    found = guard.scan_range(repo, cfg, "HEAD~2..HEAD")
    keys = " ".join(found)
    assert "f.txt" in keys and "new.txt" in keys, found
    pairs = guard.introduced_blobs(repo, "HEAD~2..HEAD")
    merge = _git(repo, "rev-parse", "HEAD").strip()
    assert any(c == merge and p == "f.txt" for c, p, _ in pairs)


def test_range_sees_same_blob_under_a_second_path(tmp_path, planted):
    """A blob allowlisted at one path and copied to another is checked at BOTH paths."""
    cfg, (tid, *_), t = planted
    repo = str(tmp_path)
    _git(repo, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("x\n"); _git(repo, "add", "."); _git(repo, "commit", "-q", "-m", "base")
    body = f"{t['w1']} {t['w2']}\n"
    (tmp_path / "ok.txt").write_text(body); (tmp_path / "leak.txt").write_text(body)
    _git(repo, "add", "."); _git(repo, "commit", "-q", "-m", "two paths")
    cfg["term_allowlist"] = {"ok.txt": [tid]}
    found = guard.scan_range(repo, cfg, "HEAD~1..HEAD")
    assert [k for k in found if k.endswith("leak.txt")] and not [k for k in found if k.endswith("ok.txt")]


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_staged_type_change_is_scanned(tmp_path, planted):
    cfg, (tid, *_), t = planted
    repo = str(tmp_path)
    _git(repo, "init", "-q", "-b", "main")
    os.symlink("target", tmp_path / "link")
    _git(repo, "add", "link"); _git(repo, "commit", "-q", "-m", "symlink")
    os.remove(tmp_path / "link")
    (tmp_path / "link").write_text(f"{t['w1']}-{t['w2']}\n")  # symlink -> regular file: status T
    _git(repo, "add", "link")
    assert "T" in _git(repo, "diff", "--cached", "--name-status")
    assert hits(guard.scan_staged(repo, cfg).get("link", []), tid)
