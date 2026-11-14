"""Section dimensions for drawn sizes (inches), for 3D profiles only.

W shapes: AISC Steel Construction Manual, 15th ed., Table 1-1 nominal d, bf, tw, tf
(values as published, to 3 significant figures). HSS rectangular: the designation
itself gives b x h x t; the wall is the AISC design wall 0.93 t. A W size not in the
table is NOT guessed - the caller gets None and builds a generic box flagged so.
"""
from __future__ import annotations

import re
from fractions import Fraction

W = {  # d, bf, tw, tf
    "W8X10": (7.89, 3.94, 0.170, 0.205),
    "W8X35": (8.12, 8.02, 0.310, 0.495),
    "W12X14": (11.9, 3.97, 0.200, 0.225),
    "W12X19": (12.2, 4.01, 0.235, 0.350),
    "W12X26": (12.2, 6.49, 0.230, 0.380),
    "W12X35": (12.5, 6.56, 0.300, 0.520),
    "W12X45": (12.1, 8.05, 0.335, 0.575),
    "W12X65": (12.1, 12.0, 0.390, 0.605),
    "W12X79": (12.4, 12.1, 0.470, 0.735),
    "W12X120": (13.1, 12.3, 0.710, 1.11),
    "W14X22": (13.7, 5.00, 0.230, 0.335),
    "W14X193": (15.5, 15.7, 0.890, 1.44),
    "W16X26": (15.7, 5.50, 0.250, 0.345),
    "W18X35": (17.7, 6.00, 0.300, 0.425),
    "W18X158": (19.7, 11.3, 0.810, 1.44),
    "W18X258": (21.5, 11.8, 1.28, 2.30),
    "W21X44": (20.7, 6.50, 0.350, 0.450),
    "W21X93": (21.6, 8.42, 0.580, 0.930),
    "W24X94": (24.3, 9.07, 0.515, 0.875),
}
IN = 0.0254


def w_dims_m(norm: str) -> dict | None:
    v = W.get(norm)
    if not v:
        return None
    d, bf, tw, tf = v
    return {"d": d * IN, "bf": bf * IN, "tw": tw * IN, "tf": tf * IN, "source": "AISC Manual 15th ed. Table 1-1 (nominal)"}


def hss_dims_m(norm: str) -> dict | None:
    m = re.fullmatch(r"HSS(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:-\d+)?/\d+|\d+(?:\.\d+)?)", norm)
    if not m:
        return None
    t = m.group(3)
    if "/" in t:
        whole, _, fr = t.rpartition("-")
        tv = float(Fraction(fr)) + (float(whole) if whole else 0.0)
    else:
        tv = float(t)
    return {"h": float(m.group(1)) * IN, "b": float(m.group(2)) * IN, "t": 0.93 * tv * IN,
            "source": "HSS designation b x h x t, design wall 0.93 t (AISC)"}
