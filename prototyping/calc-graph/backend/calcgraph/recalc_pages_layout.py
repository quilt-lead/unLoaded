"""Lay out the re-run calc sheets (recalc_pages.py) with WeasyPrint: parallel, batched, content-cached.

Why its own module: the layout workers are subprocesses (`python -m calcgraph.recalc_pages_layout
<batch>`), and a worker must import NOTHING but WeasyPrint and the standard library. When the workers
imported recalc_pages they also imported handcalcs, pint and the synthetic design code, so an import
error anywhere in the design code (a renamed constant) killed every math sheet with no page at all.

Where the time goes (profiled 2026-11-14, COL-2B dx 5, 175 records): KaTeX HTML is ~150 KiB and
~4,000 elements per steel record, and WeasyPrint spends ~1.3 s laying out each such page (style
cascade ~25 %, layout ~50 %, PDF write ~20 %). So:
- chunks are small (`CHUNK_BYTES` of rendered HTML, whole record blocks, a new page at each chunk
  start): the slowest chunk, not the largest calc, bounds the wall time;
- one worker process takes a BATCH of chunks (largest first, longest-processing-time assignment), so
  a process is started per worker, not per chunk;
- every chunk's layout is cached by content (sha256 of the chunk document + WeasyPrint version + this
  file), under <store>/cache/rerun_sheet_layout: a re-run of the same move, or any record block whose
  text is unchanged, is laid out once. So a chunk document carries nothing that changes from run to run:
  the revision id and the date are stamped into the merged PDF after layout (recalc_pages.render). The
  title block's date cell holds a hidden placeholder (`DATE_SLOT_CLASS`) whose position on every page
  is returned with the layout (`stamps`); the date itself is laid out by WeasyPrint too, as a one-line
  document of its own (cached per date), and placed over each placeholder.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

from .store_root import store_path

_HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK_BYTES = 320_000     # target rendered HTML per chunk (~2 steel records)
DATE_SLOT_CLASS = "date-slot"   # the hidden placeholder in the title block that the date is stamped over


def import_weasyprint():
    """WeasyPrint dlopens pango/gobject by bare name; on macOS Homebrew keeps them in
    /opt/homebrew/lib (or /usr/local/lib), which dyld does not search unless DYLD_* is set at
    process start. Retry those names under the Homebrew prefixes, only while importing."""
    try:
        import weasyprint
        return weasyprint
    except OSError:
        if sys.platform != "darwin":
            raise
    for k in [m for m in sys.modules if m == "weasyprint" or m.startswith("weasyprint.")]:
        del sys.modules[k]
    import cffi
    orig = cffi.FFI.dlopen

    def dlopen(self, name, flags=0):
        try:
            return orig(self, name, flags)
        except OSError:
            if isinstance(name, str) and "/" not in name:
                stem = name[:-2] if name.endswith("-0") else name
                for d in ("/opt/homebrew/lib", "/usr/local/lib"):
                    for cand in (name, stem + ".dylib", name + ".dylib"):
                        p = os.path.join(d, cand)
                        if os.path.exists(p):
                            return orig(self, p, flags)
            raise
    cffi.FFI.dlopen = dlopen
    try:
        import weasyprint
    finally:
        cffi.FFI.dlopen = orig
    return weasyprint


def _walk(box):
    yield box
    for ch in getattr(box, "children", []) or []:
        yield from _walk(ch)


def render_chunk(doc_html: str, want: list[str], base_url: str) -> tuple[bytes, dict, list[dict]]:
    """Lay out one chunk (its own HTML document) -> (PDF bytes, {block id: page/bbox}, stamps), pages
    1-based within the chunk, PDF points, top-left origin. stamps = [{page, bbox (the text box),
    baseline}]: where each page's date text (class DATE_SLOT_CLASS) was laid out."""
    weasyprint = import_weasyprint()
    document = weasyprint.HTML(string=doc_html, base_url=base_url).render()
    want_s = set(want)
    found: dict[str, dict] = {}
    stamps: list[dict] = []
    k = 0.75   # CSS px -> PDF pt
    for pno, page in enumerate(document.pages, 1):
        for box in _walk(page._page_box):
            el = getattr(box, "element", None)
            if el is not None and hasattr(box, "text") and DATE_SLOT_CLASS in (el.get("class") or "").split():
                x0, y0 = box.position_x, box.position_y
                stamps.append({"page": pno, "bbox": [round(x0 * k, 3), round(y0 * k, 3), round((x0 + box.width) * k, 3),
                                                     round((y0 + box.height) * k, 3)], "baseline": round((y0 + box.baseline) * k, 3)})
                continue
            bid = el.get("id") if el is not None else None
            if bid not in want_s:
                continue
            x0, y0 = box.border_box_x(), box.border_box_y()
            x1, y1 = x0 + box.border_width(), y0 + box.border_height()
            bb = [round(x0 * k, 2), round(y0 * k, 2), round(x1 * k, 2), round(y1 * k, 2)]
            f = found.get(bid)
            if f is None:
                found[bid] = {"page": pno, "bbox": bb, "parts": [{"page": pno, "bbox": bb}]}
            elif f["parts"][-1]["page"] != pno:
                f["parts"].append({"page": pno, "bbox": bb})
    document.metadata.created = None
    document.metadata.modified = None
    pdf = document.write_pdf(identifier=b"calc-graph-recalc-pages")   # bytes: no target given
    if pdf is None:
        raise RuntimeError("WeasyPrint wrote no PDF bytes for a re-run sheet chunk")
    return pdf, found, stamps


# ------------------------------------------------------------------ content cache
def _code_version() -> str:
    from importlib import metadata
    with open(os.path.abspath(__file__), "rb") as fh:
        src = fh.read()
    return f"weasyprint {metadata.version('weasyprint')} | {hashlib.sha256(src).hexdigest()[:16]}"


def cache_key(doc_html: str, want: list[str], base_url: str) -> str:
    h = hashlib.sha256()
    for part in (_code_version(), base_url, json.dumps(want), doc_html):
        h.update(part.encode())
        h.update(b"\x00")
    return h.hexdigest()


def _cache_dir() -> str:
    return store_path("cache", "rerun_sheet_layout")


def cache_get(key: str) -> tuple[bytes, dict, list[dict]] | None:
    base = os.path.join(_cache_dir(), key)
    try:
        with open(base + ".pdf", "rb") as fh:
            pdf = fh.read()
        with open(base + ".json") as fh:
            meta = json.load(fh)
        return pdf, meta["found"], meta["stamps"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return None


def cache_put(key: str, pdf: bytes, found: dict, stamps: list[dict]) -> None:
    d = _cache_dir()
    os.makedirs(d, exist_ok=True)
    base = os.path.join(d, key)
    tag = f".tmp{os.getpid()}"
    with open(base + ".pdf" + tag, "wb") as fh:
        fh.write(pdf)
    with open(base + ".json" + tag, "w") as fh:
        json.dump({"found": found, "stamps": stamps}, fh)
    os.replace(base + ".pdf" + tag, base + ".pdf")   # pdf first: a reader needs both, json last
    os.replace(base + ".json" + tag, base + ".json")


# ------------------------------------------------------------------ parallel layout
def default_workers() -> int:
    return max(1, min(12, (os.cpu_count() or 2) - 2))


def layout_all(jobs: list[tuple[str, list[str]]], base_url: str, workers: int | None = None,
               progress=None) -> tuple[list[tuple[bytes, dict, list[dict]]], dict]:
    """Lay out every chunk -> ([(pdf, found, stamps)] in job order, stats {chunks, cached, laid_out, workers,
    seconds}). Cached chunks are read back; the rest go to `workers` subprocesses, each taking a batch
    (largest chunks first, each to the least-loaded worker). progress(done, total) after each chunk."""
    t0 = time.time()
    keys = [cache_key(h, w, base_url) for h, w in jobs]
    out: list = [cache_get(k) for k in keys]
    todo = [i for i, r in enumerate(out) if r is None]
    total, done = len(jobs), len(jobs) - len(todo)
    if progress:
        progress(done, total)
    n = min(len(todo), workers or default_workers())
    if todo:
        root = os.path.dirname(os.path.dirname(_HERE))
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([os.path.dirname(_HERE), root, os.environ.get("PYTHONPATH", "")])}
        loads = [[0, []] for _ in range(n)]
        for i in sorted(todo, key=lambda i: -len(jobs[i][0])):
            w = min(loads, key=lambda x: x[0])
            w[0] += len(jobs[i][0])
            w[1].append(i)
        with tempfile.TemporaryDirectory(prefix="recalc_layout_") as td:
            procs = []
            for wi, (_, idxs) in enumerate(loads):
                for i in idxs:
                    with open(os.path.join(td, f"c{i}.html"), "w") as fh:
                        fh.write(jobs[i][0])
                    with open(os.path.join(td, f"c{i}.want.json"), "w") as fh:
                        json.dump(jobs[i][1], fh)
                batch = os.path.join(td, f"w{wi}.json")
                with open(batch, "w") as fh:
                    json.dump({"dir": td, "chunks": idxs, "base_url": base_url}, fh)
                procs.append(subprocess.Popen([sys.executable, "-m", "calcgraph.recalc_pages_layout", batch], env=env,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
            pending = set(todo)
            while pending:
                for i in sorted(pending):
                    if os.path.exists(os.path.join(td, f"c{i}.found.json")):
                        pending.discard(i)
                        done += 1
                        if progress:
                            progress(done, total)
                failed = [(p, p.poll()) for p in procs if p.poll() not in (None, 0)]
                if failed:
                    for p in procs:
                        if p.poll() is None:
                            p.kill()
                    err = failed[0][0].stderr.read().decode(errors="replace")
                    raise RuntimeError(f"rerun sheet layout worker failed (exit {failed[0][1]}): {err[-2000:]}")
                if pending and all(p.poll() == 0 for p in procs):
                    raise RuntimeError(f"rerun sheet layout workers exited without chunks {sorted(pending)[:5]}")
                time.sleep(0.05)
            for p in procs:
                p.wait()
            for i in todo:
                with open(os.path.join(td, f"c{i}.pdf"), "rb") as fh:
                    pdf = fh.read()
                with open(os.path.join(td, f"c{i}.found.json")) as fh:
                    meta = json.load(fh)
                out[i] = (pdf, meta["found"], meta["stamps"])
                cache_put(keys[i], pdf, meta["found"], meta["stamps"])
    return out, {"chunks": total, "cached": total - len(todo), "laid_out": len(todo), "workers": n,
                 "seconds": round(time.time() - t0, 1)}


def _worker_main(batch_path: str) -> None:
    with open(batch_path) as fh:
        b = json.load(fh)
    for i in b["chunks"]:
        base = os.path.join(b["dir"], f"c{i}")
        with open(base + ".html") as fh:
            doc_html = fh.read()
        with open(base + ".want.json") as fh:
            want = json.load(fh)
        pdf, found, stamps = render_chunk(doc_html, want, b["base_url"])
        with open(base + ".pdf", "wb") as fh:
            fh.write(pdf)
        with open(base + ".found.json.tmp", "w") as fh:   # found.json last: its presence = chunk complete
            json.dump({"found": found, "stamps": stamps}, fh)
        os.replace(base + ".found.json.tmp", base + ".found.json")


if __name__ == "__main__":
    _worker_main(sys.argv[1])
