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
    assert any("PDF content" in f for f in guard.check_blob("x/a.txt", b"junk\n%PDF-1.4\n", None, cfg))
    assert guard.check_blob("x/doc.md", b"the guard looks for a %PDF- header, e.g. %PDF-1.7", None, cfg) == []


def test_pdf_content_can_be_pinned_but_a_pdf_name_cannot():
    text = b"notes\n%PDF-1.7 is how a PDF starts\n"
    pinned = {**guard.throwaway_config(), "blob_allowlist": {"x/p.md": guard.blob_sha(text), "x/p.pdf": guard.blob_sha(text)}}
    assert guard.check_blob("x/p.md", text, None, pinned) == []
    assert any("content changed" in f for f in guard.check_blob("x/p.md", text + b"x", None, pinned))
    assert guard.check_blob("x/p.pdf", text, None, pinned) == ["PDF file"]


@pytest.mark.parametrize("data", [
    b"8BPS appears in prose\n",                       # PSD magic at 0
    b"a" * 257 + b"ustar format\n",                  # tar magic at 257
    b"abcdftypheic notes\n",                         # ISO-BMFF box at 4
    b"GIF89a was the second GIF version\n",
    b"BZh91AY&SY is the bzip2 block magic\n",
])
def test_magic_bytes_in_plain_text_are_text(data):
    assert guard.classify("x/n.txt", data) == ("text", "")


def test_magic_bytes_with_binary_context_still_classify():
    assert guard.classify("x/a.dat", b"8BPS\x00\x01\x00\x00")[0] == "image"
    assert guard.classify("x/a.dat", b"GIF89a\x10\x00\x10\x00")[0] == "image"
    assert guard.classify("x/a.dat", b"a" * 257 + b"ustar\x0000")[0] == "archive"


def test_raw_base64_without_data_prefix_must_be_pinned():
    cfg = guard.throwaway_config()
    std = b'{"png": "' + b"iVBORw0KGgoAAAANSUhEUg" * 15 + b'"}'
    url = b'{"png": "' + b"iVBORw0K-_AAANSUhEUg9" * 15 + b'"}'
    wrapped = b"".join(b"iVBORw0KGgoAAAANSUhEUgAAAZAAAAGQCAYAAACAvzbMAAAACXBIWXMAAAsTAAALEwEAmpwY\n" for _ in range(5))
    for data in (std, url, wrapped):
        assert any("raw base64" in f for f in guard.check_blob("x/d.json", data, None, cfg)), data[:30]
    pinned = {**cfg, "blob_allowlist": {"x/d.json": guard.blob_sha(std)}}
    assert guard.check_blob("x/d.json", std, None, pinned) == []


@pytest.mark.parametrize("data", [
    b'"integrity": "sha512-' + b"Ab9+" * 22 + b'=="',  # lockfile integrity (88 chars)
    b"a3f9" * 64 + b"\n",                            # 256 hex chars
    b"ABCDEF0123" * 30 + b"\n",                      # upper-case hex
    b"x" * 300 + b"\n",                              # one letter repeated (no case / digit mix)
    b"the quick brown fox jumps over the lazy dog " * 20,
])
def test_raw_base64_detector_passes_hashes_and_prose(data):
    assert guard.check_blob("x/a.txt", data, None, guard.throwaway_config()) == []


# ---------------------------------------------------------------- finding 3: glued terms
def test_long_term_glued_into_a_token(planted):
    cfg, (tid, *_), t = planted
    for s in (f"prj{t['w1'].lower()}{t['w2']}rev2", f"PRJ{t['w1'].upper()}{t['w2'].upper()}REV"):
        found = hits(guard.check_blob("x/a.py", s.encode(), None, cfg), tid)
        assert found and "glued tier" in found[0], s


def tier(text, cfg, name):
    """Term ids one tier finds on its own (the other two disabled)."""
    return [tid for tid, *_ in guard.term_hits(text, cfg, tiers=(name,))]


def test_camel_case_and_letter_digit_boundaries(planted):
    cfg, (tid, nid, did, _), t = planted
    # each input is one the token tier cannot see, so the unit tier is what finds it
    for text, want in ((f"get{t['w1']}{t['w2'].capitalize()}Value", tid), (f"PRJ{t['num']}Rev2", nid)):
        assert not tier(text, cfg, "token") and want in tier(text, cfg, "unit"), text


def test_decimal_is_one_number_in_both_directions():
    """A decimal is never joined across its point (no 1234.56 -> 123456), and a term stored WITH a
    dot keeps it, so the unit and glued tiers find it as stored."""
    cfg = guard.throwaway_config()
    n6 = str(secrets.randbelow(900_000) + 100_000)
    n5, d = str(secrets.randbelow(90_000) + 10_000), str(secrets.randbelow(9) + 1)
    six, dashed, dotted = guard.add_terms([n6, f"{n5}-{d}", f"{n5}.{d}{d}"], cfg)
    coords = f"#7=IFCCARTESIANPOINT(({n6[:4]}.{n6[4:]},{n5}.{d},0.));"
    assert guard.check_blob("x/m.ifc", coords.encode(), None, cfg) == []    # neither 6-digit term
    assert dotted in tier(f"Job{n5}.{d}{d}", cfg, "unit")                   # stored with a dot, glued to letters
    n4, d4 = str(secrets.randbelow(9_000) + 1_000), str(secrets.randbelow(9_000) + 1_000)
    long_dotted = guard.add_terms([f"{n4}.{d4}"], cfg)[0]                   # 9 canonical chars: glued tier
    assert long_dotted in tier(f"zz{n4}.{d4}zz", cfg, "glued")
    assert not tier(f"zz{n4}{d4}zz", cfg, "glued")                         # the dotless digits are another string


def test_units_and_glued_stream_use_the_term_canonical_form():
    """The invariant behind the three tiers: what a tier concatenates equals canonical_of."""
    alphabet = "abcXYZ019.-_ "
    for _ in range(500):
        s = "".join(secrets.choice(alphabet) for _ in range(secrets.randbelow(24) + 1))
        if not guard.tokens(s):
            continue
        canon = guard.canonical_of(s)
        assert "".join(u for u, _ in guard.units(s)) == canon, s


def test_no_hit_inside_a_longer_number(planted):
    cfg, _, t = planted
    assert guard.check_blob("x/a.ifc", f"#12=IFCCARTESIANPOINT((0.{t['num']},1.5));".encode(), None, cfg) == []
    n10 = str(secrets.randbelow(9 * 10**9) + 10**9)
    long_num = guard.add_terms([n10], cfg)[0]  # 10 digits: scanned by the glued tier
    assert [x for x in cfg["terms"] if x["id"] == long_num][0]["len"] == 10
    assert long_num in tier(f"id {n10}zz", cfg, "glued")              # the glued tier does see it ...
    for text in (f"(0.{n10},1.5)", f"({n10}.25,1.5)", f"v=3{n10}7"):  # ... but not inside a longer number
        assert long_num not in tier(text, cfg, "glued"), text


def test_glued_tier_respects_digit_runs():
    cfg = guard.throwaway_config()
    n10 = str(secrets.randbelow(9 * 10**9) + 10**9)
    tid = guard.add_terms([n10], cfg)[0]
    assert tid in tier(f"prj{n10}rev", cfg, "glued")
    assert not tier(f"prj{n10}rev", cfg, "token")             # only the glued (and unit) tier could see it
    assert not tier(f"v=3{n10}7", cfg, "glued")               # inside a longer number


def test_glued_digit_boundary_is_checked_on_the_original_text():
    """`Sheet 3 12345abcxyz`: the 3 is a separate number; only the separator-free stream glues it on."""
    cfg = guard.throwaway_config()
    term = str(secrets.randbelow(90_000) + 10_000) + word(6)   # digit-led, 11 chars
    tid = guard.add_terms([term], cfg)[0]
    for text in (f"Sheet 3 {term}zz", f"Sheet-3 {term}zz", f"3, {term}zz"):
        assert tid in tier(text, cfg, "glued"), text
    for text in (f"Sheet3{term}zz", f"0.{term}zz", f"3.{term}zz"):
        assert tid not in tier(text, cfg, "glued"), text


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


# ---------------------------------------------------------------- push scans (CI push events)
ZERO = "0" * 40


@pytest.fixture()
def pushed(tmp_path):
    """An origin with prod (holding pre-guard content, as the real prod does) and a clone of it."""
    origin, clone = tmp_path / "origin", tmp_path / "clone"
    origin.mkdir()
    o = str(origin)
    _git(o, "init", "-q", "-b", "prod")
    _git(o, "config", "uploadpack.allowAnySHA1InWant", "true")
    (origin / "shot.png").write_bytes(PNG)  # unpinned: --history over prod can only fail
    _git(o, "add", "."); _git(o, "commit", "-q", "-m", "pre-guard")
    _git(str(tmp_path), "clone", "-q", o, str(clone))
    return origin, clone


def _commit(repo, name, body):
    (repo / name).write_text(body)
    _git(str(repo), "add", name); _git(str(repo), "commit", "-q", "-m", name)
    return _git(str(repo), "rev-parse", "HEAD").strip()


def test_push_new_branch_scans_only_commits_not_on_the_base(pushed):
    _, clone = pushed
    c = str(clone)
    _git(c, "checkout", "-q", "-b", "main")
    head = _commit(clone, "a.txt", "clean\n")
    spec, _ = guard.push_spec(c, ZERO, head, "origin/prod", "main")
    assert spec == f"origin/prod..{head}"
    cfg = guard.throwaway_config()
    assert guard.scan_range(c, cfg, spec) == {}
    assert guard.scan_range(c, cfg, head)  # what the old fallback (--history) did: fails on prod's history


def test_push_force_push_fetches_the_old_head_by_sha(pushed):
    origin, clone = pushed
    old = _commit(origin, "old.txt", "old head\n")            # on origin only: the clone never saw it
    _git(str(origin), "reset", "-q", "--hard", "HEAD~1")        # force-push: old head is now unreferenced
    c = str(clone)
    assert subprocess.run(["git", "cat-file", "-e", f"{old}^{{commit}}"], cwd=c, capture_output=True).returncode
    head = _commit(clone, "new.txt", "new\n")
    spec, _ = guard.push_spec(c, old, head, "origin/prod", "prod")
    assert spec == f"{old}..{head}"


def test_push_unknown_before_scans_the_tree_and_warns(pushed, capsys):
    _, clone = pushed
    c = str(clone)
    head = _commit(clone, "new.txt", "new\n")
    spec, why = guard.push_spec(c, "1" * 40, head, "origin/prod", "prod")
    assert spec is None and "could not be fetched" in why
    cfg = {**guard.throwaway_config(), "blob_allowlist": {"shot.png": guard.blob_sha(PNG)}}
    assert guard.scan_push(c, cfg, "1" * 40, head, "origin/prod", "prod") == 0
    assert "::warning" in capsys.readouterr().out
    assert guard.push_spec(c, ZERO, head, "origin/prod", "prod")[0] is None  # creating the base branch itself


def test_ci_runs_the_guard_in_the_copyright_job():
    """The copyright job is the only CI run of the guard (evaluate_all has no copyright stage)."""
    ci = open(os.path.join(ROOT, "..", "..", ".github", "workflows", "ci.yml")).read()
    job = ci[ci.index("  copyright:"):ci.index("  tooling:")]
    for flag in ("--self-test", "--tracked", "--range", "--push"):
        assert f'"$guard" {flag}' in job, flag
    assert "--history" not in job.split("run: |", 1)[1]  # prod's history predates the guard


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
