"""Validate every per-set profile (committed + local data/profiles/) against the schema.

    uv run python scripts/check_profiles.py

Exits 1 naming each profile that fails to load (unknown key, missing field, bad regex, unknown
sheet / symbol kind, extends cycle). Safe for CI: needs no PDFs, and a missing local profile dir
is fine (only the committed ones are checked then).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from calcgraph import profiles  # noqa: E402


def main() -> int:
    bad = 0
    for pid in profiles.available():
        try:
            pf = profiles.load(pid)
            print(f"ok   {pid:24s} {pf.name}")
        except Exception as e:  # noqa: BLE001 - report every failure, then exit non-zero
            bad += 1
            print(f"FAIL {pid}: {e}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
