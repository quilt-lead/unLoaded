/**
 * AISC 360-16 strong-axis flexure of a doubly symmetric I-shape (F2 lateral-torsional buckling,
 * F3 noncompact flange), phi = 0.90, Cb = 1 - the same equations the hackathon engine evaluated
 * (synth/v2/aisc.phi_mn). Used ONLY as a ratio phiMn(Lb_after) / phiMn(Lb_before) of the same member,
 * so the printed capacity is scaled, never replaced. Needs a shape table row from the caller.
 * Units: kip, in, ksi.
 */
export interface FlexureSection {
  Zx: number;
  Sx: number;
  bf: number;
  tf: number;
  ry: number;
  rts: number;
  ho: number;
  J: number;
}

const E = 29000;

export function phiMn(s: FlexureSection, lbIn: number, fy: number, cb = 1.0): number {
  const mp = fy * s.Zx;
  const lamF = s.bf / (2 * s.tf);
  const lpf = 0.38 * Math.sqrt(E / fy);
  const lrf = 1.0 * Math.sqrt(E / fy);
  const lp = 1.76 * s.ry * Math.sqrt(E / fy);
  const jc = s.J / (s.Sx * s.ho);
  const lr = 1.95 * s.rts * (E / (0.7 * fy)) * Math.sqrt(jc + Math.sqrt(jc ** 2 + 6.76 * ((0.7 * fy) / E) ** 2));
  let mnLtb: number;
  if (lbIn <= lp) mnLtb = mp;
  else if (lbIn <= lr) mnLtb = Math.min(mp, cb * (mp - (mp - 0.7 * fy * s.Sx) * ((lbIn - lp) / (lr - lp))));
  else {
    const fcr = ((cb * Math.PI ** 2 * E) / (lbIn / s.rts) ** 2) * Math.sqrt(1 + 0.078 * jc * (lbIn / s.rts) ** 2);
    mnLtb = Math.min(mp, fcr * s.Sx);
  }
  const mnFlb = lamF > lpf ? mp - (mp - 0.7 * fy * s.Sx) * ((lamF - lpf) / (lrf - lpf)) : mp;
  return (0.9 * Math.min(mnLtb, mnFlb)) / 12;
}

/** Yield stress (ksi) from the model's material name when it names one ("A992", "Gr 50", "Fy 50 ksi"). */
export function yieldFromMaterial(material: string | null | undefined): number | null {
  if (!material) return null;
  const m = /(?:Gr(?:ade)?\.?\s*|Fy\s*=?\s*)(\d{2,3})\b/i.exec(material);
  if (m) return Number(m[1]);
  if (/A992|A572/i.test(material)) return 50;
  if (/A36\b/i.test(material)) return 36;
  return null;
}
