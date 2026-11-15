"""The package-style revised sheets of a re-run (synth.v2.calc_pdf_v2.write_revision), in a worker process.

recalc._write_pages starts this while it builds the handcalcs re-run sheets, so the two page sets are
written at the same time on different cores. In a thread they could not overlap: both are pure-Python
CPU work (matplotlib mathtext + PyMuPDF here, handcalcs there) and shared one interpreter lock, which
made the math sheets wait ~11 s on this writer (profiled 2026-11-14).

    python -m calcgraph.recalc_package <job.pickle>     # job: exp, d_new, recs, pdf, rev_label, base
writes <job>.out.pickle = {record id: page info} and exits 0; any failure exits non-zero with the
traceback on stderr (the caller records it as files.page_error).
"""
from __future__ import annotations

import os
import pickle
import subprocess
import sys


def start(job: dict, path: str) -> subprocess.Popen:
    """Write the job and start the worker (PYTHONPATH as the caller's, so synth.v2 imports)."""
    with open(path, "wb") as fh:
        pickle.dump(job, fh)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([os.path.dirname(here), root, os.environ.get("PYTHONPATH", "")])}
    return subprocess.Popen([sys.executable, "-m", "calcgraph.recalc_package", path], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def finish(proc: subprocess.Popen, path: str) -> dict:
    """Wait for the worker -> {record id: page info}; raises RuntimeError with its stderr on failure."""
    _, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"package-style sheet writer failed (exit {proc.returncode}): {err.decode(errors='replace')[-2000:]}")
    with open(path + ".out.pickle", "rb") as fh:
        return pickle.load(fh)


def _main(path: str) -> None:
    from synth.v2 import calc_pdf_v2
    with open(path, "rb") as fh:
        j = pickle.load(fh)
    pages = calc_pdf_v2.write_revision(j["exp"], j["d_new"], j["recs"], j["pdf"], rev_label=j["rev_label"], prev_exp=j["base"]) or {}
    with open(path + ".out.pickle.tmp", "wb") as fh:
        pickle.dump(pages, fh)
    os.replace(path + ".out.pickle.tmp", path + ".out.pickle")


if __name__ == "__main__":
    _main(sys.argv[1])
