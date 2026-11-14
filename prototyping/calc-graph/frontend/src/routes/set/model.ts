// Indexes and evidence helpers for the drawing-set view, built once per (graph, integrated) pair.
// Port of the legacy page's state object S and its evidence openers (src/legacy/set/main.ts).
import type {
  CEdge,
  CInst,
  CType,
  EEdge,
  El,
  Ev,
  Integrated,
  Lnk,
  Note,
  REdge,
  Rec,
  RLink,
  SetCalc,
  SetFinding,
  SetGraph,
  Sheet,
} from "../../api/types";

export const SEC_COL: Record<string, string> = {
  A: "#76b7b2",
  B: "#4e79a7",
  C: "#e15759",
  D: "#9c755f",
  E: "#59a14f",
  STAIR: "#b07aa1",
};
export const CAT_COL: Record<string, string> = {
  Beam: "#4e79a7",
  Column: "#e15759",
  Footing: "#9c755f",
  Pile: "#7a5c45",
  Wall: "#b07aa1",
  Frame: "#f28e2b",
  Other: "#8a94a3",
};
export const CONN_COL = "#e8590c";
export const SEC_ORDER = ["CALCS", "A", "B", "C", "D", "E", "STAIR"];
export const nat = (a: string, b: string) =>
  a.localeCompare(b, undefined, { numeric: true });
export type Tone = "good" | "warn" | "bad";
export const tierCls = (s: number): Tone =>
  s >= 0.75 ? "good" : s >= 0.55 ? "warn" : "bad";
export const TONE_COL: Record<Tone, string> = {
  good: "var(--good)",
  warn: "var(--warn)",
  bad: "var(--bad)",
};
export const secName = (s: string) =>
  ({
    A: "A - Loading criteria",
    B: "B - Gravity framing (RISAFloor)",
    C: "C - Lateral framing (RISA-3D)",
    D: "D - Foundation design",
    E: "E - Exterior metal studs",
    STAIR: "Stair calcs",
    CALCS: "Front matter",
  })[s] ?? s;
export const calcSec = (c: SetCalc) =>
  c.doc === "stair" ? "STAIR" : c.section;
export const recColor = (r: Rec) => SEC_COL[r.section] ?? "#888";
/** the connection detail a stair connection-design record is a title-only candidate for (and back) */
export const PARAPET_DETAIL = "2/S8.2.7";
export const PARAPET_REC = "stair:connection_design:PARAPET";

export type SelKind = "el" | "calc" | "rec" | "ctype" | "cinst";
export type Sel = { kind: SelKind; id: string } | null;
export type ListTab = "el" | "rec" | "calc" | "conn" | "find";

const push = <K, V>(m: Map<K, V[]>, k: K, v: V) =>
  (m.get(k) ?? m.set(k, []).get(k)!).push(v);

export interface SetIndex {
  sid: string;
  g: SetGraph;
  ig: Integrated | null;
  findings: SetFinding[];
  els: Map<string, El>;
  calcs: Map<string, SetCalc>;
  sheets: Map<string, Sheet>;
  sheetByPage: Map<number, Sheet>;
  linksByEl: Map<string, Lnk[]>;
  linksByCalc: Map<string, Lnk[]>;
  down: Map<string, EEdge[]>;
  up: Map<string, EEdge[]>;
  cin: Map<string, CEdge[]>;
  cout: Map<string, CEdge[]>;
  recs: Map<string, Rec>;
  rin: Map<string, REdge[]>;
  rout: Map<string, REdge[]>;
  rlByEl: Map<string, RLink[]>;
  rlByRec: Map<string, RLink[]>;
  recsByPage: Map<string, Rec[]>;
  notesByRec: Map<string, Note[]>;
  ctypes: Map<string, CType>;
  cinst: Map<string, CInst>;
  instByEl: Map<string, CInst[]>;
}

export function buildIndex(
  sid: string,
  g: SetGraph,
  ig: Integrated | null,
): SetIndex {
  const x: SetIndex = {
    sid,
    g,
    ig,
    findings: [...g.findings, ...(ig?.findings ?? [])],
    els: new Map(g.elements.map((e) => [e.id, e])),
    calcs: new Map(g.calcs.map((c) => [c.id, c])),
    sheets: new Map(g.sheets.map((s) => [s.sheet, s])),
    sheetByPage: new Map(g.sheets.map((s) => [s.page, s])),
    linksByEl: new Map(),
    linksByCalc: new Map(),
    down: new Map(),
    up: new Map(),
    cin: new Map(),
    cout: new Map(),
    recs: new Map(),
    rin: new Map(),
    rout: new Map(),
    rlByEl: new Map(),
    rlByRec: new Map(),
    recsByPage: new Map(),
    notesByRec: new Map(),
    ctypes: new Map(),
    cinst: new Map(),
    instByEl: new Map(),
  };
  for (const l of g.links) {
    push(x.linksByEl, l.el, l);
    push(x.linksByCalc, l.calc, l);
  }
  for (const ls of [...x.linksByEl.values(), ...x.linksByCalc.values()])
    ls.sort((a, b) => b.score - a.score);
  for (const e of g.element_edges) {
    push(x.down, e.src, e);
    push(x.up, e.dst, e);
  }
  for (const e of g.calc_edges) {
    push(x.cout, e.src, e);
    push(x.cin, e.dst, e);
  }
  if (ig) {
    x.recs = new Map(ig.records.map((r) => [r.id, r]));
    for (const e of ig.record_edges) {
      push(x.rout, e.src, e);
      if (e.dst) push(x.rin, e.dst, e);
    }
    for (const l of ig.record_links) {
      push(x.rlByEl, l.el, l);
      for (const r of l.records) push(x.rlByRec, r, l);
    }
    for (const ls of x.rlByEl.values()) ls.sort((a, b) => b.score - a.score);
    for (const r of ig.records) {
      const seen = new Set<string>();
      for (const e of r.ev) {
        const k = `${e.doc}|${e.page}`;
        if (!seen.has(k)) {
          seen.add(k);
          push(x.recsByPage, k, r);
        }
      }
    }
    for (const n of ig.notes)
      for (const a of n.attached) push(x.notesByRec, a.record, n);
    x.ctypes = new Map(ig.conn_types.map((t) => [t.id, t]));
    x.cinst = new Map(ig.conn_instances.map((i) => [i.id, i]));
    for (const i of ig.conn_instances)
      for (const a of i.attached) push(x.instByEl, a.id, i);
  }
  return x;
}

export const recEdgesOut = (x: SetIndex, id: string) => x.rout.get(id) ?? [];
export const has = (x: SetIndex, s: NonNullable<Sel>) =>
  s.kind === "el"
    ? x.els.has(s.id)
    : s.kind === "calc"
      ? x.calcs.has(s.id)
      : s.kind === "rec"
        ? x.recs.has(s.id)
        : s.kind === "ctype"
          ? x.ctypes.has(s.id)
          : x.cinst.has(s.id);

// ---------------------------------------------------------------- evidence
export function elEv(e: El): Ev {
  return {
    doc: e.doc,
    page: e.page,
    rects: e.rects,
    text: e.text,
    note: `${e.type} · ${e.sheet} · grid ${e.grid || "-"}`,
  };
}
export function calcEv(c: SetCalc): Ev {
  return {
    doc: c.doc,
    page: c.page,
    rects: [c.title_rect, c.sheet_rect].filter(Boolean) as number[][],
    text: `${c.sheet_id} ${c.title}`,
    note: c.software,
  };
}
export function recEv(r: Rec, i = 0): Ev {
  const e = r.ev[i] ?? r.ev[0];
  return { ...e, note: `${r.title} · ${e?.table || r.table}` };
}
export function ctypeEv(t: CType): Ev {
  return {
    doc: t.doc,
    page: t.page,
    rects: [t.number_rect, ...(t.title_rects ?? [])].filter(Boolean),
    text: `${t.id} ${t.title}`,
    note: `${t.category} · ${t.sheet} ${t.sheet_title}`,
  };
}
export function cinstEv(i: CInst): Ev {
  const rects = [...i.rects];
  if (i.leader_end)
    rects.push([
      i.leader_end[0] - 4,
      i.leader_end[1] - 4,
      i.leader_end[0] + 4,
      i.leader_end[1] + 4,
    ]);
  return {
    doc: i.doc,
    page: i.page,
    rects,
    text: i.type_id ?? i.ref,
    note: `${i.via}${i.symbol_name ? " - " + i.symbol_name : ""} · ${i.sheet} · grid ${i.grid || "-"}${i.leader_end ? " · leader end marked" : ""}`,
  };
}
export function noteEv(n: Note): Ev {
  return {
    doc: n.doc,
    page: n.page,
    rects: n.rects?.length ? n.rects : [n.bbox],
    text: n.text,
    note: `engineer note (${n.colour})`,
  };
}
/** Merge evidence items that sit on the same page into one view. */
export function mergeEv(evs: Ev[]): Ev[] {
  const out: Ev[] = [];
  for (const e of evs) {
    if (!e) continue;
    const o = out.find((y) => y.doc === e.doc && y.page === e.page);
    if (o) {
      o.rects = [...o.rects, ...e.rects];
      o.text = `${o.text} | ${e.text}`;
      o.note = [o.note, e.note].filter(Boolean).join("; ");
    } else out.push({ ...e, rects: [...(e.rects ?? [])] });
  }
  return out;
}
export function rowsOnPage(r: Rec, doc: string, page: number): Ev[] {
  return mergeEv(r.ev.filter((e) => e.doc === doc && e.page === page)).map(
    (e) => ({ ...e, note: `${r.title} - row(s) on this page` }),
  );
}
/** caption of an evidence page: which document, which sheet / calc page, which PDF page */
export function docLabel(x: SetIndex, ev: Ev): string {
  if (ev.doc === "plans") {
    const s = x.sheetByPage.get(ev.page);
    return `Drawings · ${s ? `${s.sheet} ${s.title}` : ""} · PDF p${ev.page}`;
  }
  const c = [...x.calcs.values()].find(
    (y) => y.doc === ev.doc && y.page === ev.page,
  );
  return `${ev.doc === "stair" ? "Stair calcs" : "Calc package"} · ${c ? `${c.sheet_id} ${ev.table || c.title}` : ""} · PDF p${ev.page}`;
}

export function fmtVal(v: unknown): string {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "number") return String(Math.round(v * 1000) / 1000);
  if (Array.isArray(v)) return v.map(fmtVal).join(", ");
  if (typeof v === "object")
    return Object.entries(v as Record<string, unknown>)
      .map(
        ([k, y]) =>
          `${k}: ${typeof y === "object" && y !== null && !Array.isArray(y) ? "{" + fmtVal(y) + "}" : fmtVal(y)}`,
      )
      .join("; ");
  return String(v);
}

// ---------------------------------------------------------------- deep links (#el= #calc= #rec= #ctype= #cinst= #link= #rlink= #find=)
export type Hash =
  | { k: SelKind; v: string }
  | { k: "link"; el: string; calc: string }
  | { k: "rlink"; el: string; calc: string; rec: string }
  | { k: "find"; i: number }
  | null;

export function parseHash(h: string): Hash {
  let s = h.replace(/^#/, "");
  try {
    s = decodeURIComponent(s);
  } catch {
    /* keep raw */
  }
  const i = s.indexOf("=");
  if (i < 0) return null;
  const k = s.slice(0, i),
    v = s.slice(i + 1);
  if (
    k === "el" ||
    k === "calc" ||
    k === "rec" ||
    k === "ctype" ||
    k === "cinst"
  )
    return { k, v };
  if (k === "link") {
    const [el, calc] = v.split("|");
    return { k, el, calc };
  }
  if (k === "rlink") {
    const [el, calc, rec] = v.split("|");
    return { k, el, calc, rec };
  }
  if (k === "find") return { k, i: +v };
  return null;
}
export const hashOf = (h: Hash): string => {
  if (!h) return "";
  const e = encodeURIComponent;
  if (h.k === "link") return `#link=${e(h.el)}|${e(h.calc)}`;
  if (h.k === "rlink") return `#rlink=${e(h.el)}|${e(h.calc)}|${e(h.rec)}`;
  if (h.k === "find") return `#find=${h.i}`;
  return `#${h.k}=${e(h.v)}`;
};
