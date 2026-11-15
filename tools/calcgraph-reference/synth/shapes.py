"""Small AISC-style section table (imperial nominal values, rounded).

Values are the usual published nominal properties to 3 significant figures. They
are used for both the IFC profiles (converted to metres) and the PyNite analysis
(converted to kN / m). Synthetic data: close enough to be realistic, not a design
reference.
"""
from __future__ import annotations

IN = 0.0254
IN2 = IN**2
IN3 = IN**3
IN4 = IN**4

# name: d, bf, tw, tf, A, Ix, Iy, Zx, rx, ry   (in, in2, in4, in3)
W = {
    "W12X19": (12.2, 4.01, 0.235, 0.350, 5.57, 130, 3.76, 24.7, 4.82, 0.822),
    "W12X53": (12.1, 10.0, 0.345, 0.575, 15.6, 425, 95.8, 77.9, 5.23, 2.48),
    "W14X68": (14.0, 10.0, 0.415, 0.720, 20.0, 722, 121, 115, 6.01, 2.46),
    "W14X90": (14.0, 14.5, 0.440, 0.710, 26.5, 999, 362, 157, 6.14, 3.70),
    "W16X26": (15.7, 5.50, 0.250, 0.345, 7.68, 301, 9.59, 44.2, 6.26, 1.12),
    "W16X31": (15.9, 5.53, 0.275, 0.440, 9.13, 375, 12.4, 54.0, 6.41, 1.17),
    "W18X35": (17.7, 6.00, 0.300, 0.425, 10.3, 510, 15.3, 66.5, 7.04, 1.22),
    "W21X44": (20.7, 6.50, 0.350, 0.450, 13.0, 843, 20.7, 95.4, 8.06, 1.26),
    "W24X55": (23.6, 7.01, 0.395, 0.505, 16.2, 1350, 29.1, 134, 9.11, 1.34),
    "W24X68": (23.7, 8.97, 0.415, 0.585, 20.1, 1830, 70.4, 177, 9.55, 1.87),
    # used by the Harborview generator (synth/harborview)
    "W14X132": (14.7, 14.7, 0.645, 1.03, 38.8, 1530, 548, 234, 6.28, 3.76),
    "W18X46": (18.1, 6.06, 0.360, 0.605, 13.5, 712, 22.5, 90.7, 7.25, 1.29),
    "W21X62": (21.0, 8.24, 0.400, 0.615, 18.3, 1330, 57.5, 144, 8.54, 1.77),
    "W14X145": (14.8, 15.5, 0.680, 1.09, 42.7, 1710, 677, 260, 6.33, 3.98),
    "W24X84": (24.1, 9.02, 0.470, 0.770, 24.7, 2370, 94.4, 224, 9.79, 1.95),
}
# name: b, t_design, A, I, r
HSS = {"HSS6X6X3/8": (6.0, 0.349, 7.58, 39.5, 2.28), "HSS8X8X1/2": (8.0, 0.465, 13.5, 125, 3.04),
       "HSS10X10X5/8": (10.0, 0.581, 21.0, 304, 3.80)}

FY_KSI = 50.0
E_KSI = 29000.0
KSI_TO_KPA = 6894.757
KN_TO_KIP = 0.224809
KNM_TO_KFT = 0.737562
M_TO_FT = 3.28084


def w_si(name: str) -> dict:
    d, bf, tw, tf, A, Ix, Iy, Zx, rx, ry = W[name]
    return {
        "d": d * IN, "bf": bf * IN, "tw": tw * IN, "tf": tf * IN,
        "A": A * IN2, "Ix": Ix * IN4, "Iy": Iy * IN4, "Zx": Zx * IN3,
        "rx": rx * IN, "ry": ry * IN, "J": max(1e-8, (2 * bf * tf**3 + d * tw**3) / 3 * IN4),
    }


def hss_si(name: str) -> dict:
    b, t, A, I, r = HSS[name]
    return {"b": b * IN, "t": t * IN, "A": A * IN2, "I": I * IN4, "r": r * IN, "J": 2 * I * IN4}


def phi_mn_kft(name: str) -> float:
    """Flexural strength, compact and fully braced (deck / composite): 0.9 Fy Zx."""
    return 0.9 * FY_KSI * W[name][7] / 12.0


def phi_pn_kips(area_in2: float, r_in: float, kl_in: float) -> float:
    """AISC 360-16 E3 flexural buckling."""
    import math
    slender = kl_in / r_in
    fe = math.pi**2 * E_KSI / slender**2
    fcr = (0.658 ** (FY_KSI / fe)) * FY_KSI if FY_KSI / fe <= 2.25 else 0.877 * fe
    return 0.9 * fcr * area_in2
