"""Member size tokens: recognise them in drawing / calc text and normalise them so
the same section compares equal however each document prints it.

  W16x26 == W16X26                     (case)
  HSS6x6x1/4 == HSS6X6X2               (RISA prints HSS wall thickness in eighths
                                        of an inch: X2 = 1/4", X3 = 3/8", X4 = 1/2")
  HSS6x6x.25 == HSS6x6x1/4             (decimal wall)
  600S162-54 (50 ksi) == 600S162-54    (CFS designation, grade dropped)
  C12x20.7, MC18x42.7, L4x4x1/4        (channels, angles)
  8x10 (FLAT)                          (sawn timber, only where the caller allows it)

A token RISA truncated with an ellipsis ("HSS10X1...", "HSS5.5X5...") is NOT
normalised to a full size: it cannot be compared and is reported as truncated.
"""
from __future__ import annotations

import re
from fractions import Fraction

_STEEL = re.compile(
    r"^(?P<fam>W|HSS|MC|C|L|WT|S|HP)(?P<a>\d+(?:\.\d+)?)[xX×](?P<b>\d+(?:\.\d+)?)(?:[xX×](?P<c>\d+(?:\.\d+)?(?:/\d+)?|\.\d+))?$")
_CFS = re.compile(r"^(?P<d>\d{3})(?P<k>[STUF])(?P<w>\d{3})-(?P<t>\d{2,3})(?:\(\d+\)?)?,?$")
_TIMBER = re.compile(r"^(?P<a>2|3|4|6|8|10|12|14)[xX](?P<b>2|3|4|6|8|10|12|14|16|18|20|24)$")
_STRIP = re.compile(r"^[\(\[\"']+|[\)\]\"',;:.]+$")


def _frac(s: str) -> Fraction:
    if "/" in s:
        n, d = s.split("/")
        return Fraction(int(n), int(d))
    return Fraction(s)


def _fmt_frac(f: Fraction) -> str:
    if f.denominator == 1:
        return str(f.numerator)
    whole, rem = divmod(f.numerator, f.denominator)
    return f"{whole}-{rem}/{f.denominator}" if whole else f"{rem}/{f.denominator}"


def clean(tok: str) -> str:
    return _STRIP.sub("", tok.strip())


def norm(tok: str, *, risa: bool = False, timber: bool = False) -> dict | None:
    """Return {"norm", "family", "kind"} for a size token, else None.

    An HSS / angle wall written as a number >= 1 is RISA's eighths of an inch
    (HSS6X6X2 = HSS6x6x1/4); no real HSS or angle wall is 1" or more, so the rule
    is safe for every document. `risa` is kept for callers that want to say so.
    """
    t = clean(tok)
    if not t or "..." in t or "…" in t:
        return None
    m = _STEEL.match(t)
    if m:
        fam, a, b, c = m.group("fam").upper(), m.group("a"), m.group("b"), m.group("c")
        if fam in ("W", "MC", "C", "S", "HP", "WT") and c is None:
            return {"norm": f"{fam}{a}X{b}", "family": fam, "kind": "steel"}
        if fam in ("HSS", "L") and c is not None:
            if c.startswith("."):
                c = "0" + c
            if "/" in c:
                wall = _frac(c)
            else:
                v = Fraction(c)
                # a wall >= 1 is RISA's eighths (X2 = 1/4", X1.5 = 3/16"); a real 1"+ HSS / angle wall does not occur
                wall = v / 8 if v >= 1 else v
            return {"norm": f"{fam}{a}X{b}X{_fmt_frac(wall)}", "family": fam, "kind": "steel"}
        if fam == "HSS" and c is None:  # round HSS / pipe written without a wall - not a full size
            return None
        return None
    m = _CFS.match(t)
    if m:
        return {"norm": f"{m.group('d')}{m.group('k')}{m.group('w')}-{m.group('t')}", "family": "CFS", "kind": "cfs"}
    if timber:
        m = _TIMBER.match(t)
        if m:
            return {"norm": f"{m.group('a')}X{m.group('b')}", "family": "Timber", "kind": "timber"}
    return None


def is_truncated_size(tok: str) -> bool:
    """RISA cuts long shape names: 'HSS10X1...', 'HSS5.5X5...'."""
    return bool(re.match(r"^(W|HSS|MC|C|L)\d[\dXx.]*(\.\.\.|…)", tok.strip()))
