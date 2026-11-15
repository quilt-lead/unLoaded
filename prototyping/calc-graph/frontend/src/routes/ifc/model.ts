// Derived data for the IFC app: indexes over /api/projects/{pid}/state, colours, labels.
import type {
  IfcCalc,
  IfcElement,
  IfcImpact,
  IfcLink,
  ProjectState,
} from "../../api/types";

export const CAT_COLORS: Record<string, string> = {
  Beam: "#4e79a7",
  Column: "#e15759",
  Slab: "#9aa5b1",
  Footing: "#9c755f",
  Pile: "#7a5c45",
  Wall: "#b07aa1",
  Brace: "#59a14f",
  Connection: "#f28e2b",
  Other: "#b8c0ca",
};
export const STATUS_COLORS: Record<IfcElement["status"], string> = {
  confirmed: "#1f9d63",
  review: "#e0942f",
  unmapped: "#d64545",
};
export const GREY = "#c3cad3";
export const REMOVED = "#d64545";
export const IMPACTED = "#f0a050";

/** How a link was made, in words (link tier -> label). */
export const TIER: Record<string, string> = {
  exact: "Named by mark",
  range: "Named in a mark range",
  loose: "Mark ignoring punctuation",
  family: "Mark family",
  partial: "Partial mark - review",
  xref: "Mentioned only (cross-reference) - review",
  size: "Section size + type",
  type: "Element type only - review",
  manual: "Linked by hand",
};

export type Sel = { kind: "el" | "calc"; id: string } | null;
export type ColorBy = "calc" | "status" | "cat";

export interface IfcIndex {
  st: ProjectState;
  els: Map<string, IfcElement>;
  calcs: Map<string, IfcCalc>;
  linksByEl: Map<string, IfcLink[]>;
  linksByCalc: Map<string, IfcLink[]>;
}

const push = <K, V>(m: Map<K, V[]>, k: K, v: V) =>
  (m.get(k) ?? m.set(k, []).get(k)!).push(v);

export function indexState(st: ProjectState): IfcIndex {
  const linksByEl = new Map<string, IfcLink[]>();
  const linksByCalc = new Map<string, IfcLink[]>();
  for (const l of st.links) {
    push(linksByEl, l.global_id, l);
    push(linksByCalc, l.calc_key, l);
  }
  return {
    st,
    els: new Map(st.elements.map((e) => [e.global_id, e])),
    calcs: new Map(st.calcs.map((c) => [c.key, c])),
    linksByEl,
    linksByCalc,
  };
}

/** live (not rejected) links, strongest first */
export const live = (ls: IfcLink[] | undefined) =>
  (ls ?? [])
    .filter((l) => l.status !== "rejected")
    .sort((a, b) => b.conf - a.conf);
export const linksFor = (ix: IfcIndex, gid: string) =>
  live(ix.linksByEl.get(gid));
export const linksOfCalc = (ix: IfcIndex, key: string) =>
  live(ix.linksByCalc.get(key));
export const elLabel = (e: IfcElement) => e.mark || e.name || e.ifc_type;
export const pageRange = (c: IfcCalc) =>
  c.pages.length > 1
    ? `pp. ${c.pages[0]}-${c.pages[c.pages.length - 1]}`
    : `p. ${c.pages[0]}`;
/** stored times carry their own offset (Eastern); shown as "MM-DD HH:MM ET" */
export const shortTime = (iso: string) =>
  `${iso.slice(5, 16).replace("T", " ")} ET`;

export interface PaintOpts {
  colorBy: ColorBy;
  sel: Sel;
  filter: string | null;
  impact: IfcImpact | null;
  xray: boolean;
  level: string;
}

/** colour / opacity / visibility of one element in the 3D view (the legacy paint() rules) */
export function paintOf(ix: IfcIndex, el: IfcElement, o: PaintOpts) {
  const ls = linksFor(ix, el.global_id);
  const selCalc = o.sel?.kind === "calc" ? o.sel.id : null;
  const selEl = o.sel?.kind === "el" ? o.sel.id : null;
  let color =
    o.colorBy === "status"
      ? STATUS_COLORS[el.status]
      : o.colorBy === "cat"
        ? (CAT_COLORS[el.cat] ?? CAT_COLORS.Other)
        : ls.length
          ? (ix.calcs.get(ls[0].calc_key)?.color ?? GREY)
          : GREY;
  let focus = true;
  const imp = o.impact;
  if (imp) {
    const removed = imp.removed.includes(el.global_id);
    focus = removed || imp.hit[el.global_id] !== undefined;
    if (removed) color = REMOVED;
    else if (imp.hit[el.global_id] !== undefined) color = IMPACTED;
  } else if (selCalc) {
    focus = ls.some((l) => l.calc_key === selCalc);
    if (focus && o.colorBy === "calc")
      color = ix.calcs.get(selCalc)?.color ?? color;
  } else if (o.filter) focus = el.status === o.filter;
  const visible = !o.level || el.storey === o.level;
  let opacity = focus ? (o.xray ? 0.55 : el.cat === "Slab" ? 0.45 : 1) : 0.07;
  if (selEl && el.global_id !== selEl && !selCalc && !imp)
    opacity = Math.min(opacity, o.xray ? 0.2 : 0.35);
  return { color, opacity, visible };
}
