// Drawing-set view: elements read off the S-sheets, the calc graph of the calc package,
// evidence links between them. Every node, edge, link and finding opens the ORIGINAL
// PDF page zoomed to and highlighting the words that produced it.
import "../style.css";
import "./set.css";
import { PdfView, type Shown } from "./pdfview";
import { Viewer } from "../../viewer";
import * as THREE from "three";

interface Ev {
  table?: string;
  doc: string;
  page: number;
  rects: number[][];
  text: string;
  note?: string;
  sheet?: string;
  calc?: string;
  extra?: Ev[];
}
interface Model3D {
  in3d: boolean;
  gid?: string;
  reason?: string;
  rule?: string;
  position?: string;
  elevation?: string;
  assumed?: string[];
  profile?: string;
  status3d?: string;
  grid3d?: string;
}
interface El {
  model?: Model3D;
  id: string;
  doc: string;
  page: number;
  sheet: string;
  sheet_title: string;
  sheet_kind: string;
  cat: string;
  type: string;
  mark: string;
  size: string;
  size_norm: string;
  family: string;
  level: string;
  grid: string;
  grid_node: string | null;
  bbox: number[];
  rects: number[][];
  text: string;
  params: Record<string, string>;
}
interface EEdge {
  src: string;
  dst: string;
  rule: string;
  evidence: Ev[];
}
interface Calc {
  id: string;
  doc: string;
  page: number;
  sheet_id: string;
  sheet_rect: number[] | null;
  section: string;
  group: string;
  title: string;
  title_rect: number[] | null;
  level: string;
  software: string;
  kind: string;
  toc: boolean;
  width: number;
  height: number;
  sizes: string[];
  labels: Record<string, number>;
}
interface CEdge {
  src: string;
  dst: string;
  rule: string;
  labels: string[];
  evidence: { src: Ev[]; dst: Ev[] };
}
interface Lnk {
  el: string;
  calc: string;
  score: number;
  tier: string;
  rule: string;
  evidence: { el: Ev; calc: Ev };
}
interface Finding {
  kind: string;
  severity: string;
  text: string;
  el?: string;
  calc?: string;
  rec?: string;
  evidence: Ev[];
}
interface Sheet {
  sheet: string;
  title: string;
  page: number;
  width: number;
  height: number;
  kind: string;
  level: string;
}
interface Graph {
  id: string;
  name: string;
  built_at: string;
  docs: Record<string, { name: string; role: string; pages?: number }>;
  sheets: Sheet[];
  elements: El[];
  element_edges: EEdge[];
  calcs: Calc[];
  calc_edges: CEdge[];
  links: Lnk[];
  findings: Finding[];
  coverage: Record<string, any>;
}

// ---- integrated layer: calc records, calc load path, connections, 2021 calc-model overlay ----
interface Rec {
  id: string;
  type: string;
  run: string;
  run_title: string;
  section: string;
  label: string;
  title: string;
  level: string;
  size: string;
  table: string;
  tables: string[];
  pages: number[];
  values: Record<string, any>;
  ev: (Ev & { table?: string })[];
}
interface REdge {
  src: string;
  dst: string | null;
  kind: string;
  join: "exact" | "inferred" | "absent";
  rule: string;
  end?: string;
  evidence: { src: Ev[]; dst: Ev[] };
}
interface RLink {
  el: string;
  calc: string;
  records: string[];
  tier: string;
  score: number;
  rule: string;
}
interface Note {
  id: string;
  doc: string;
  page: number;
  sheet: string;
  rects: number[][];
  bbox: number[];
  colour: string;
  text: string;
  attached: { record: string; join: string; rule: string }[];
}
interface Att {
  id: string;
  cat: string;
  type: string;
  size: string;
  dist: number;
  at_end?: boolean;
  role?: string;
}
interface CType {
  id: string;
  detail: string;
  sheet: string;
  page: number;
  doc: string;
  sheet_title: string;
  category: string;
  title: string;
  is_connection: boolean;
  scale: string;
  bbox: number[];
  number_rect: number[];
  title_rects: number[][];
  spec: { text: string; rect: number[] }[];
  sizes: string[];
  instances: string[];
  referenced_from_details: string[];
  calc_refs: any[];
  rule: string;
}
interface CInst {
  id: string;
  type_id: string | null;
  ref: string;
  sheet: string;
  page: number;
  doc: string;
  via: string;
  symbol: string | null;
  symbol_name?: string;
  legend_text?: string;
  bbox: number[];
  rects: number[][];
  point: number[];
  leader_end: number[] | null;
  grid: string;
  grid_node: string | null;
  attached: Att[];
  attach_rule: string;
  unattached_reason?: string;
  in_view: string;
  context?: string;
}
interface Marker {
  inst: string;
  el: string;
  pos: number[];
  rule: string;
}
interface OvMember {
  rec: string;
  label: string;
  size: string;
  level: string;
  a: number[];
  b: number[];
  elev: number;
  absent_ends: number;
}
interface OvColumn {
  rec: string;
  label: string;
  size: string;
  z: number;
  x: number;
  bot: number;
  top: number;
}
interface Overlay {
  levels: Record<string, number>;
  axes: string;
  members: OvMember[];
  columns: OvColumn[];
  orientation: string;
  transform_dropped: string;
  differences: { what: string; text: string; calc: Ev[]; draw: Ev[] }[];
}
interface Integrated {
  built_at: string;
  stale: string[];
  runs: Record<string, string>;
  records: Rec[];
  record_edges: REdge[];
  notes: Note[];
  record_links: RLink[];
  conn_types: CType[];
  conn_instances: CInst[];
  conn_markers: Marker[];
  overlay: Overlay;
  findings: Finding[];
  coverage: Record<string, any>;
}

const $ = <T extends HTMLElement = HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const esc = (s: unknown) =>
  String(s ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!,
  );
const nat = (a: string, b: string) =>
  a.localeCompare(b, undefined, { numeric: true });
const SEC_COL: Record<string, string> = {
  A: "#76b7b2",
  B: "#4e79a7",
  C: "#e15759",
  D: "#9c755f",
  E: "#59a14f",
  STAIR: "#b07aa1",
};
const CAT_COL: Record<string, string> = {
  Beam: "#4e79a7",
  Column: "#e15759",
  Footing: "#9c755f",
  Pile: "#7a5c45",
  Wall: "#b07aa1",
  Frame: "#f28e2b",
  Other: "#8a94a3",
};
const SEC_ORDER = ["CALCS", "A", "B", "C", "D", "E", "STAIR"];
const tierCls = (s: number) =>
  s >= 0.75 ? "good" : s >= 0.55 ? "warn" : "bad";

type SelKind = "el" | "calc" | "rec" | "ctype" | "cinst";
type Sel = { kind: SelKind; id: string } | null;
const S = {
  sid: "",
  g: null as Graph | null,
  els: new Map<string, El>(),
  calcs: new Map<string, Calc>(),
  sheets: new Map<string, Sheet>(),
  linksByEl: new Map<string, Lnk[]>(),
  linksByCalc: new Map<string, Lnk[]>(),
  down: new Map<string, EEdge[]>(), // element -> its supports
  up: new Map<string, EEdge[]>(), // element -> what it carries
  cin: new Map<string, CEdge[]>(),
  cout: new Map<string, CEdge[]>(),
  // integrated layer (absent until integrated.json is built)
  ig: null as Integrated | null,
  recs: new Map<string, Rec>(),
  rin: new Map<string, REdge[]>(), // record -> load-path edges arriving (what feeds it)
  rout: new Map<string, REdge[]>(), // record -> load-path edges leaving (what carries it)
  rlByEl: new Map<string, RLink[]>(),
  rlByRec: new Map<string, RLink[]>(),
  recsByPage: new Map<string, Rec[]>(),
  notesByRec: new Map<string, Note[]>(),
  ctypes: new Map<string, CType>(),
  cinst: new Map<string, CInst>(),
  instByEl: new Map<string, CInst[]>(),
  sel: null as Sel,
  tab: "el" as "el" | "rec" | "calc" | "conn" | "find",
  q: "",
  open: new Set<string>(),
};
const push = <K, V>(m: Map<K, V[]>, k: K, v: V) =>
  (m.get(k) ?? m.set(k, []).get(k)!).push(v);

const viewA = new PdfView($("pvA"));
const viewB = new PdfView($("pvB"));

function pageDims(doc: string, page: number): [number, number] {
  if (doc === "plans") {
    const s = [...S.sheets.values()].find((x) => x.page === page);
    return s ? [s.width, s.height] : [3024, 2160];
  }
  const c = [...S.calcs.values()].find((x) => x.doc === doc && x.page === page);
  return c ? [c.width, c.height] : [612, 792];
}
function docLabel(ev: Ev) {
  if (ev.doc === "plans") {
    const s = [...S.sheets.values()].find((x) => x.page === ev.page);
    return `Drawings · ${s ? `${s.sheet} ${esc(s.title)}` : ""} · PDF p${ev.page}`;
  }
  const c = [...S.calcs.values()].find(
    (x) => x.doc === ev.doc && x.page === ev.page,
  );
  return `${ev.doc === "stair" ? "Stair calcs" : "Calc package"} · ${c ? `<b>${esc(c.sheet_id)}</b> ${esc(ev.table || c.title)}` : ""} · PDF p${ev.page}`;
}
function shown(ev: Ev, focus?: number[] | null): Shown {
  const [pw, ph] = pageDims(ev.doc, ev.page);
  return {
    sid: S.sid,
    doc: ev.doc,
    page: ev.page,
    pw,
    ph,
    rects: ev.rects.filter((r) => r && r.length === 4),
    focus: focus ?? null,
    label: docLabel(ev),
    sub: `${ev.text ? `<span class="mono">${esc(ev.text)}</span>` : ""}${ev.note ? ` - ${esc(ev.note)}` : ""}`,
  };
}
function single(ev: Ev, focus?: number[] | null) {
  document.body.classList.remove("split", "split1");
  viewB.clear();
  viewA.show(shown(ev, focus));
}
function split(a: Ev, b: Ev, title: string) {
  document.body.classList.remove("split1");
  document.body.classList.add("split");
  $("splitTitle").innerHTML = title;
  viewA.show(shown(a));
  viewB.show(shown(b));
}
function elEv(e: El): Ev {
  return {
    doc: e.doc,
    page: e.page,
    rects: e.rects,
    text: e.text,
    note: `${e.type} · ${e.sheet} · grid ${e.grid || "-"}`,
  };
}
function calcEv(c: Calc): Ev {
  return {
    doc: c.doc,
    page: c.page,
    rects: [c.title_rect, c.sheet_rect].filter(Boolean) as number[][],
    text: `${c.sheet_id} ${c.title}`,
    note: c.software,
  };
}
/** Merge evidence items that sit on the same page into one view. */
function mergeEv(evs: Ev[]): Ev[] {
  const out: Ev[] = [];
  for (const e of evs) {
    const o = out.find((x) => x.doc === e.doc && x.page === e.page);
    if (o) {
      o.rects = [...o.rects, ...e.rects];
      o.text = `${o.text} | ${e.text}`;
      o.note = [o.note, e.note].filter(Boolean).join("; ");
    } else out.push({ ...e, rects: [...e.rects] });
  }
  return out;
}

// ---------------- data ----------------
async function load() {
  const sets = await fetch("/api/sets").then((r) => r.json());
  if (!sets.length) {
    $("graph").innerHTML =
      `<div class="empty">No drawing set ingested yet. Run <span class="mono">uv run calc-graph ingest-set --plans ... --calcs ...</span></div>`;
    return;
  }
  S.sid = new URLSearchParams(location.search).get("set") || sets[0].id;
  const [r, ir] = await Promise.all([fetch(`/api/sets/${S.sid}/graph`), fetch(`/api/sets/${S.sid}/integrated`)]);
  if (!r.ok) throw new Error(`graph: ${r.status}`);
  const g: Graph = await r.json();
  S.g = g;
  S.els = new Map(g.elements.map((e) => [e.id, e]));
  S.calcs = new Map(g.calcs.map((c) => [c.id, c]));
  S.sheets = new Map(g.sheets.map((s) => [s.sheet, s]));
  for (const l of g.links) {
    push(S.linksByEl, l.el, l);
    push(S.linksByCalc, l.calc, l);
  }
  for (const ls of [...S.linksByEl.values(), ...S.linksByCalc.values()])
    ls.sort((a, b) => b.score - a.score);
  for (const e of g.element_edges) {
    push(S.down, e.src, e);
    push(S.up, e.dst, e);
  }
  for (const e of g.calc_edges) {
    push(S.cout, e.src, e);
    push(S.cin, e.dst, e);
  }
  if (ir.ok) ingestIntegrated(await ir.json());
  $("setName").textContent = g.name;
  pills();
  fromHash();
  renderAll();
}

function ingestIntegrated(ig: Integrated) {
  S.ig = ig;
  S.recs = new Map(ig.records.map((r) => [r.id, r]));
  for (const e of ig.record_edges) {
    push(S.rout, e.src, e);
    if (e.dst) push(S.rin, e.dst, e);
  }
  for (const l of ig.record_links) {
    push(S.rlByEl, l.el, l);
    for (const r of l.records) push(S.rlByRec, r, l);
  }
  for (const ls of S.rlByEl.values()) ls.sort((a, b) => b.score - a.score);
  for (const r of ig.records) {
    const seen = new Set<string>();
    for (const e of r.ev) {
      const k = `${e.doc}|${e.page}`;
      if (!seen.has(k)) (seen.add(k), push(S.recsByPage, k, r));
    }
  }
  for (const n of ig.notes) for (const a of n.attached) push(S.notesByRec, a.record, n);
  S.ctypes = new Map(ig.conn_types.map((t) => [t.id, t]));
  S.cinst = new Map(ig.conn_instances.map((i) => [i.id, i]));
  for (const i of ig.conn_instances) for (const a of i.attached) push(S.instByEl, a.id, i);
  S.g!.findings = [...S.g!.findings, ...ig.findings];
}

function pills() {
  const c = S.g!.coverage;
  const unlinkedEls = c.elements - c.elements_linked;
  $("pills").innerHTML =
    `<span class="pill"><b>${c.elements}</b> elements from ${S.g!.sheets.length} S-sheets</span>` +
    `<span class="pill"><b>${c.load_path_edges}</b> load-path edges</span>` +
    `<span class="pill"><b>${c.calc_pages}</b> calc pages</span>` +
    `<span class="pill"><b>${c.calc_edges}</b> calc feed edges</span>` +
    `<span class="pill good"><b>${c.elements_linked}</b> elements linked</span>` +
    `<span class="pill bad" data-f="no calc found"><b>${unlinkedEls}</b> no calc found</span>` +
    `<span class="pill warn" data-f="calc page linked to nothing"><b>${c.calc_pages_unlinked}</b> calc pages linked to nothing</span>` +
    `<span class="pill" title="Links by rule">${Object.entries(c.links_by_tier)
      .map(([k, v]) => `${esc(k)} <b>${v}</b>`)
      .join(" · ")}</span>`;
  const ig = S.ig;
  if (ig) {
    const cv = ig.coverage, j = cv.record_edges_by_join ?? {};
    const nf = (k: string) => ig.findings.filter((f) => f.kind === k).length;
    $("pills").innerHTML +=
      (ig.stale.length ? `<span class="pill bad" title="${esc(ig.stale.join("; "))}">stale record / connection data - rebuild</span>` : "") +
      `<span class="pill" data-tab="rec"><b>${cv.records}</b> calc records</span>` +
      `<span class="pill" data-tab="rec" title="calc load path joins">load path <b>${j.exact ?? 0}</b> exact · <b>${j.inferred ?? 0}</b> inferred · <b>${j.absent ?? 0}</b> absent</span>` +
      `<span class="pill" data-tab="conn"><b>${cv.connection_types}</b> connection details · <b>${cv.connection_instances}</b> placed · <b>${cv.connection_instances_attached}</b> attached</span>` +
      `<span class="pill bad" data-f="gravity load-path gap"><b>${nf("gravity load-path gap")}</b> load-path gaps</span>` +
      `<span class="pill bad" data-f="unsupported member end"><b>${nf("unsupported member end")}</b> unsupported member ends</span>`;
  }
  $("pills")
    .querySelectorAll<HTMLElement>("[data-tab]")
    .forEach((p) => (p.onclick = () => ((S.tab = p.dataset.tab as typeof S.tab), renderList())));
  $("pills")
    .querySelectorAll<HTMLElement>("[data-f]")
    .forEach(
      (p) =>
        (p.onclick = () => (
          (S.tab = "find"),
          (S.q = ""),
          (($("q") as HTMLInputElement).value = ""),
          S.open.add(p.dataset.f!),
          renderList()
        )),
    );
}

// ---------------- selection / routing ----------------
function select(sel: Sel, open = true) {
  S.sel = sel;
  history.replaceState(
    null,
    "",
    sel ? `#${sel.kind}=${encodeURIComponent(sel.id)}` : "#",
  );
  if (sel && open) {
    if (sel.kind === "el") single(elEv(S.els.get(sel.id)!));
    else if (sel.kind === "calc") single(calcEv(S.calcs.get(sel.id)!));
    else if (sel.kind === "rec") single(recEv(S.recs.get(sel.id)!));
    else if (sel.kind === "ctype") {
      const t = S.ctypes.get(sel.id)!;
      single(ctypeEv(t), t.bbox);
    } else if (sel.kind === "cinst") single(cinstEv(S.cinst.get(sel.id)!));
  }
  renderAll();
  paint3d(true);
}
function openLink(l: Lnk) {
  const e = S.els.get(l.el)!,
    c = S.calcs.get(l.calc)!;
  const extra = l.evidence.el.extra ?? [];
  split(
    l.evidence.el,
    l.evidence.calc,
    `<b>${esc(e.text)}</b> (${esc(e.sheet)}) &harr; <b>${esc(c.sheet_id)}</b> ${esc(c.title)} <span class="chip ${tierCls(l.score)}">${esc(l.tier)} ${Math.round(l.score * 100)}%</span> <span class="why">${esc(l.rule)}</span>` +
      (extra.length ? ` <button class="sm" id="showExtra">Show schedule row on the left</button>` : ""),
  );
  document.getElementById("showExtra")?.addEventListener("click", () => viewA.show(shown({ ...extra[0], note: "foundation schedule row" })));
  history.replaceState(null, "", `#link=${encodeURIComponent(l.el)}|${encodeURIComponent(l.calc)}`);
}
function openEEdge(e: EEdge) {
  const evs = mergeEv(e.evidence);
  const a = S.els.get(e.src)!,
    b = S.els.get(e.dst)!;
  const t = `<b>${esc(a.text)}</b> (${esc(a.sheet)}) &rarr; <b>${esc(b.text)}</b> (${esc(b.sheet)}) <span class="chip">${esc(e.rule)}</span>`;
  if (evs.length >= 2) split(evs[0], evs[evs.length - 1], t);
  else {
    single(evs[0]);
    document.body.classList.add("split1");
    $("splitTitle").innerHTML = t;
  }
}
function openCEdge(e: CEdge) {
  const a = S.calcs.get(e.src)!,
    b = S.calcs.get(e.dst)!;
  const ev1 = mergeEv(e.evidence.src)[0],
    ev2 = mergeEv(e.evidence.dst)[0];
  split(
    ev1,
    ev2,
    `<b>${esc(a.sheet_id)}</b> ${esc(a.title)} &rarr; <b>${esc(b.sheet_id)}</b> ${esc(b.title)} <span class="chip">${esc(e.rule)}</span> <span class="why">${esc(e.labels.slice(0, 6).join(", "))}${e.labels.length > 6 ? "…" : ""}</span>`,
  );
}
function openFinding(f: Finding) {
  const evs = mergeEv(f.evidence);
  const t = `<span class="chip ${f.severity === "high" ? "bad" : ""}">${esc(f.kind)}</span> ${esc(f.text)}`;
  if (evs.length >= 2) split(evs[0], evs[1], t);
  else if (evs.length) {
    single(evs[0]);
    document.body.classList.add("split1");
    $("splitTitle").innerHTML = t;
  }
}

// ---------------- integrated layer: evidence openers ----------------
function recEv(r: Rec, i = 0): Ev {
  const e = r.ev[i] ?? r.ev[0];
  return { ...e, note: `${r.title} · ${(e as any).table || r.table}` };
}
function ctypeEv(t: CType): Ev {
  return { doc: t.doc, page: t.page, rects: [t.number_rect, ...(t.title_rects ?? [])].filter(Boolean), text: `${t.id} ${t.title}`, note: `${t.category} · ${t.sheet} ${t.sheet_title}` };
}
function cinstEv(i: CInst): Ev {
  const rects = [...i.rects];
  if (i.leader_end) rects.push([i.leader_end[0] - 4, i.leader_end[1] - 4, i.leader_end[0] + 4, i.leader_end[1] + 4]);
  return { doc: i.doc, page: i.page, rects, text: i.type_id ?? i.ref, note: `${i.via}${i.symbol_name ? " - " + i.symbol_name : ""} · ${i.sheet} · grid ${i.grid || "-"}${i.leader_end ? " · leader end marked" : ""}` };
}
/** One evidence list -> one view (all on one page) or a split (first and last page). */
function openEvs(evs: Ev[], title: string) {
  const m = mergeEv(evs.filter((e) => e && e.rects));
  if (!m.length) return;
  if (m.length >= 2) split(m[0], m[m.length - 1], title);
  else {
    single(m[0]);
    document.body.classList.add("split1");
    $("splitTitle").innerHTML = title;
  }
}
function openREdge(e: REdge) {
  const a = S.recs.get(e.src), b = e.dst ? S.recs.get(e.dst) : null;
  const t = `<b>${esc(a?.title ?? e.src)}</b> &rarr; ${b ? `<b>${esc(b.title)}</b>` : `<span class="chip bad">no support found</span>`} <span class="chip ${e.join === "exact" ? "good" : e.join === "inferred" ? "warn" : "bad"}">${esc(e.join)}</span> <span class="why">${esc(e.kind)}: ${esc(e.rule)}</span>`;
  const src = mergeEv(e.evidence.src), dst = mergeEv(e.evidence.dst);
  if (src.length && dst.length) split(src[0], dst[0], t);
  else openEvs([...src, ...dst], t);
}
function rowsOnPage(r: Rec, doc: string, page: number): Ev[] {
  return mergeEv(r.ev.filter((e) => e.doc === doc && e.page === page)).map((e) => ({ ...e, note: `${r.title} - row(s) on this page` }));
}
function openRLink(l: RLink, rid: string) {
  const e = S.els.get(l.el)!, c = S.calcs.get(l.calc)!, r = S.recs.get(rid)!;
  // a table record's row carries the size; a page record (sketch, Enercalc, hand calc) keeps the
  // page link's own evidence (the printed size) beside the record's title
  const rows = rowsOnPage(r, c.doc, c.page);
  const tableRow = rows.length && r.ev.some((e) => e.doc === c.doc && e.page === c.page && e.table);
  const pl = (S.linksByEl.get(l.el) ?? []).find((x) => x.calc === l.calc);
  const right = tableRow ? rows[0] : mergeEv([...(pl ? [pl.evidence.calc] : []), ...rows])[0] ?? recEv(r);
  split(elEv(e), right,
    `<b>${esc(e.text)}</b> (${esc(e.sheet)}) &harr; <b>${esc(r.title)}</b> on ${esc(c.sheet_id)} <span class="chip ${tierCls(l.score)}">${esc(l.tier)} ${Math.round(l.score * 100)}%</span> <span class="why">${esc(l.rule)}</span>`);
  history.replaceState(null, "", `#rlink=${encodeURIComponent(l.el)}|${encodeURIComponent(l.calc)}|${encodeURIComponent(rid)}`);
}
function openInstEl(i: CInst, elId: string) {
  const e = S.els.get(elId)!;
  const a = i.attached.find((x) => x.id === elId);
  openEvs([cinstEv(i), elEv(e)], `<b>${esc(i.type_id ?? i.ref)}</b> ${esc(i.via)} &rarr; <b>${esc(e.text)}</b> (${esc(e.sheet)}) <span class="chip">${esc(a?.role ?? "attached")} · ${a?.dist ?? "?"} pt</span> <span class="why">${esc(i.attach_rule)}</span>`);
}
function openNote(n: Note) {
  single({ doc: n.doc, page: n.page, rects: n.rects?.length ? n.rects : [n.bbox], text: n.text, note: `engineer note (${n.colour})` });
}

function fromHash() {
  const h = decodeURIComponent(location.hash.slice(1));
  const [k, v] = [h.slice(0, h.indexOf("=")), h.slice(h.indexOf("=") + 1)];
  if (k === "el" && S.els.has(v)) select({ kind: "el", id: v });
  else if (k === "calc" && S.calcs.has(v)) select({ kind: "calc", id: v });
  else if (k === "rec" && S.recs.has(v)) select({ kind: "rec", id: v });
  else if (k === "ctype" && S.ctypes.has(v)) select({ kind: "ctype", id: v });
  else if (k === "cinst" && S.cinst.has(v)) select({ kind: "cinst", id: v });
  else if (k === "rlink") {
    const [a, b, c] = v.split("|");
    const l = (S.rlByEl.get(a) ?? []).find((x) => x.calc === b && x.records.includes(c));
    if (l) {
      S.sel = { kind: "el", id: a };
      openRLink(l, c);
    }
  }
  else if (k === "link") {
    const [a, b] = v.split("|");
    const l = (S.linksByEl.get(a) ?? []).find((x) => x.calc === b);
    if (l) {
      S.sel = { kind: "el", id: a };
      openLink(l);
    }
  } else if (k === "find") {
    const f = S.g!.findings[+v];
    if (f) {
      S.tab = "find";
      openFinding(f);
    }
  }
}

// ---------------- left list ----------------
function matches(s: string) {
  return !S.q || s.toLowerCase().includes(S.q);
}
function renderList() {
  document
    .querySelectorAll<HTMLButtonElement>("#ltabs button")
    .forEach((b) => b.classList.toggle("on", b.dataset.t === S.tab));
  const host = $("list");
  let h = "";
  if (S.tab === "el") {
    const groups = new Map<string, El[]>();
    for (const e of S.g!.elements)
      if (
        matches(
          `${e.id} ${e.text} ${e.type} ${e.sheet} ${e.grid} ${e.level} ${e.size_norm}`,
        )
      )
        push(groups, `${e.sheet}|${e.type}`, e);
    for (const [k, es] of [...groups.entries()].sort((a, b) =>
      nat(a[0], b[0]),
    )) {
      const [sh, ty] = k.split("|");
      const nl = es.filter((e) => S.linksByEl.has(e.id)).length;
      const open =
        S.open.has(k) ||
        !!S.q ||
        (S.sel?.kind === "el" && es.some((e) => e.id === S.sel!.id));
      h += `<div class="grp ${open ? "open" : ""}" data-g="${esc(k)}"><span class="tw">${open ? "▾" : "▸"}</span><b>${esc(sh)}</b> ${esc(ty)} <span class="cnt">${nl}/${es.length} linked</span></div>`;
      if (open)
        h += es
          .sort((a, b) => nat(a.text, b.text) || nat(a.grid, b.grid))
          .map((e) => {
            const n = S.linksByEl.get(e.id)?.length ?? 0;
            return `<div class="row ${S.sel?.id === e.id ? "sel" : ""}" data-el="${esc(e.id)}"><i style="background:${CAT_COL[e.cat] ?? CAT_COL.Other}"></i><span class="mono">${esc(e.text)}</span><span class="m">${esc(e.grid || "")}</span>${n ? `<span class="chip good">${n}</span>` : `<span class="chip bad">no calc</span>`}</div>`;
          })
          .join("");
    }
  } else if (S.tab === "calc") {
    const groups = new Map<string, Calc[]>();
    for (const c of S.g!.calcs)
      if (
        matches(`${c.sheet_id} ${c.title} ${c.software} ${c.sizes.join(" ")}`)
      )
        push(groups, c.group, c);
    let lastSec = "";
    for (const [k, cs] of groups) {
      const sec = cs[0].doc === "stair" ? "STAIR" : cs[0].section;
      if (sec !== lastSec) {
        h += `<div class="sec" style="--c:${SEC_COL[sec] ?? "#888"}">${esc(secName(sec))}</div>`;
        lastSec = sec;
      }
      const nl = cs.filter((c) => S.linksByCalc.has(c.id)).length;
      const open =
        S.open.has(k) ||
        !!S.q ||
        (S.sel?.kind === "calc" && cs.some((c) => c.id === S.sel!.id));
      const range =
        cs.length > 1
          ? `${cs[0].sheet_id}-${cs[cs.length - 1].sheet_id}`
          : cs[0].sheet_id;
      h += `<div class="grp ${open ? "open" : ""}" data-g="${esc(k)}"><span class="tw">${open ? "▾" : "▸"}</span><b>${esc(range)}</b> ${esc(cs[0].title)} <span class="cnt">${cs.length} pp${nl ? ` · ${nl} linked` : ""}</span></div>`;
      if (open)
        h += cs
          .map((c) => {
            const n = new Set((S.linksByCalc.get(c.id) ?? []).map((l) => l.el))
              .size;
            return `<div class="row ${S.sel?.id === c.id ? "sel" : ""}" data-calc="${esc(c.id)}"><i style="background:${SEC_COL[sec] ?? "#888"}"></i><span class="mono">${esc(c.sheet_id)}</span><span class="m">${esc(c.title)}</span>${n ? `<span class="chip good">${n} el</span>` : ""}</div>`;
          })
          .join("");
    }
  } else if (S.tab === "rec") {
    if (!S.ig) h = `<div class="empty">No calc records yet - run <span class="mono">uv run python scripts/build_calc_records.py</span></div>`;
    else {
      // package -> section -> run -> table -> record
      const tree = new Map<string, Map<string, Map<string, Rec[]>>>();
      for (const r of S.ig.records)
        if (matches(`${r.id} ${r.title} ${r.table} ${r.level} ${r.size} ${r.run_title}`)) {
          const runs = tree.get(r.section) ?? tree.set(r.section, new Map()).get(r.section)!;
          const tabs = runs.get(r.run) ?? runs.set(r.run, new Map()).get(r.run)!;
          push(tabs, r.table, r);
        }
      const firstPage = (rs: Rec[]) => Math.min(...rs.map((r) => r.ev[0]?.page ?? 9999));
      for (const sec of [...tree.keys()].sort((a, b) => SEC_ORDER.indexOf(a) - SEC_ORDER.indexOf(b))) {
        h += `<div class="sec" style="--c:${SEC_COL[sec] ?? "#888"}">${esc(secName(sec))}</div>`;
        for (const [run, tabs] of tree.get(sec)!) {
          const n = [...tabs.values()].reduce((a, b) => a + b.length, 0);
          h += `<div class="runh">${esc(S.ig.runs[run] ?? run)} <span class="cnt">${n}</span></div>`;
          for (const [tab, rs] of [...tabs.entries()].sort((a, b) => firstPage(a[1]) - firstPage(b[1]))) {
            const k = `t:${sec}|${run}|${tab}`;
            const open = S.open.has(k) || !!S.q || (S.sel?.kind === "rec" && rs.some((r) => r.id === S.sel!.id));
            const nl = rs.filter((r) => S.rlByRec.has(r.id)).length;
            const gaps = rs.filter((r) => recEdgesOut(r.id).some((e) => e.join === "absent")).length;
            h += `<div class="grp ${open ? "open" : ""}" data-g="${esc(k)}"><span class="tw">${open ? "▾" : "▸"}</span>${esc(tab)} <span class="cnt">${rs.length}${nl ? ` · ${nl} linked` : ""}${gaps ? ` · <span class="bad">${gaps} gap</span>` : ""}</span></div>`;
            if (open)
              h += rs
                .sort((a, b) => nat(a.label, b.label))
                .map((r) => {
                  const ne = new Set((S.rlByRec.get(r.id) ?? []).map((l) => l.el)).size;
                  const gap = recEdgesOut(r.id).some((e) => e.join === "absent");
                  const note = S.notesByRec.has(r.id);
                  return `<div class="row ${S.sel?.id === r.id ? "sel" : ""}" data-rec="${esc(r.id)}"><i style="background:${recColor(r)}"></i><span class="mono">${esc(r.title)}</span><span class="m">${esc(r.level)}</span>${note ? `<span class="chip">note</span>` : ""}${gap ? `<span class="chip bad">gap</span>` : ""}${ne ? `<span class="chip good">${ne} el</span>` : ""}</div>`;
                })
                .join("");
          }
        }
      }
    }
  } else if (S.tab === "conn") {
    if (!S.ig) h = `<div class="empty">No connections yet - run <span class="mono">uv run python scripts/build_connections.py</span></div>`;
    else {
      const bySheet = new Map<string, CType[]>();
      for (const t of S.ig.conn_types) if (matches(`${t.id} ${t.title} ${t.sheet} ${t.sheet_title} ${t.category}`)) push(bySheet, t.sheet, t);
      h += `<div class="sec" style="--c:#e8590c">Connection details (types)</div>`;
      for (const [sh, ts] of [...bySheet.entries()].sort((a, b) => nat(a[0], b[0]))) {
        const k = `c:${sh}`;
        const open = S.open.has(k) || !!S.q || (S.sel?.kind === "ctype" && ts.some((t) => t.id === S.sel!.id));
        const ni = ts.reduce((a, t) => a + (t.instances?.length ?? 0), 0);
        h += `<div class="grp ${open ? "open" : ""}" data-g="${esc(k)}"><span class="tw">${open ? "▾" : "▸"}</span><b>${esc(sh)}</b> ${esc(ts[0].sheet_title)} <span class="cnt">${ts.length} details · ${ni} placed</span></div>`;
        if (open)
          h += ts
            .sort((a, b) => nat(a.detail, b.detail))
            .map((t) => `<div class="row ${S.sel?.id === t.id ? "sel" : ""}" data-ctype="${esc(t.id)}"><i style="background:${t.is_connection ? "#e8590c" : "var(--muted)"}"></i><span class="mono">${esc(t.detail)}</span><span class="m">${esc(t.title)}</span>${t.instances?.length ? `<span class="chip">${t.instances.length}</span>` : ""}</div>`)
            .join("");
      }
      const loose = new Map<string, CInst[]>();
      for (const i of S.ig.conn_instances) if (!i.type_id && matches(`${i.id} ${i.symbol_name ?? ""} ${i.ref} ${i.sheet} ${i.grid}`)) push(loose, i.symbol_name ?? i.ref, i);
      if (loose.size) h += `<div class="sec" style="--c:#e8590c">Plan symbols with no detail number</div>`;
      for (const [nm, is] of loose) {
        const k = `cs:${nm}`;
        const open = S.open.has(k) || !!S.q || (S.sel?.kind === "cinst" && is.some((i) => i.id === S.sel!.id));
        h += `<div class="grp ${open ? "open" : ""}" data-g="${esc(k)}"><span class="tw">${open ? "▾" : "▸"}</span>${esc(nm)} <span class="cnt">${is.length}</span></div>`;
        if (open)
          h += is.map((i) => `<div class="row ${S.sel?.id === i.id ? "sel" : ""}" data-cinst="${esc(i.id)}"><i style="background:#e8590c"></i><span class="mono">${esc(i.sheet)}</span><span class="m">${esc(i.grid || "")}</span>${i.attached.length ? `<span class="chip good">${i.attached.length} el</span>` : `<span class="chip">unattached</span>`}</div>`).join("");
      }
    }
  } else {
    const groups = new Map<string, [Finding, number][]>();
    S.g!.findings.forEach(
      (f, i) => matches(`${f.kind} ${f.text}`) && push(groups, f.kind, [f, i]),
    );
    for (const [k, fs] of groups) {
      const open = S.open.has(k) || !!S.q || fs.length <= 3;
      h += `<div class="grp ${open ? "open" : ""}" data-g="${esc(k)}"><span class="tw">${open ? "▾" : "▸"}</span><b>${esc(k)}</b> <span class="cnt">${fs.length}</span></div>`;
      if (open)
        h += fs
          .slice(0, 400)
          .map(
            ([f, i]) =>
              `<div class="row find" data-find="${i}"><i style="background:${f.severity === "high" ? "var(--bad)" : "var(--muted)"}"></i><span class="m">${esc(f.text)}</span></div>`,
          )
          .join("");
    }
  }
  host.innerHTML = h || `<div class="empty">Nothing matches.</div>`;
  host.querySelectorAll<HTMLElement>("[data-g]").forEach(
    (x) =>
      (x.onclick = () => {
        const k = x.dataset.g!;
        S.open.has(k) ? S.open.delete(k) : S.open.add(k);
        renderList();
      }),
  );
  host
    .querySelectorAll<HTMLElement>("[data-el]")
    .forEach(
      (x) => (x.onclick = () => select({ kind: "el", id: x.dataset.el! })),
    );
  host
    .querySelectorAll<HTMLElement>("[data-calc]")
    .forEach(
      (x) => (x.onclick = () => select({ kind: "calc", id: x.dataset.calc! })),
    );
  host.querySelectorAll<HTMLElement>("[data-rec]").forEach((x) => (x.onclick = () => select({ kind: "rec", id: x.dataset.rec! })));
  host.querySelectorAll<HTMLElement>("[data-ctype]").forEach((x) => (x.onclick = () => select({ kind: "ctype", id: x.dataset.ctype! })));
  host.querySelectorAll<HTMLElement>("[data-cinst]").forEach((x) => (x.onclick = () => select({ kind: "cinst", id: x.dataset.cinst! })));
  host.querySelectorAll<HTMLElement>("[data-find]").forEach(
    (x) =>
      (x.onclick = () => {
        const f = S.g!.findings[+x.dataset.find!];
        history.replaceState(null, "", `#find=${x.dataset.find}`);
        if (f.el) S.sel = { kind: "el", id: f.el };
        else if (f.calc) S.sel = { kind: "calc", id: f.calc };
        else if (f.rec && S.recs.has(f.rec)) S.sel = { kind: "rec", id: f.rec };
        renderGraph();
        renderInsp();
        openFinding(f);
      }),
  );
}
const secName = (s: string) =>
  ({
    A: "A - Loading criteria",
    B: "B - Gravity framing (RISAFloor)",
    C: "C - Lateral framing (RISA-3D)",
    D: "D - Foundation design",
    E: "E - Exterior metal studs",
    STAIR: "Stair calcs (2023)",
    CALCS: "Front matter",
  })[s] ?? s;

// ---------------- graph ----------------
const NW = 150,
  NH = 34;
function renderGraph() {
  const host = $("graph");
  const g = S.g!;
  if (!S.sel) return overview(host);
  if (S.sel.kind === "rec") return recGraph(host);
  if (S.sel.kind === "ctype" || S.sel.kind === "cinst") return connGraph(host);
  if (S.sel.kind === "el" && S.ig) return elGraph(host);
  type N = {
    id: string;
    kind: "el" | "calc";
    x: number;
    y: number;
    label: string;
    sub: string;
    color: string;
    sel?: boolean;
  };
  const nodes = new Map<string, N>();
  const lines: string[] = [];
  const W = Math.max(640, host.clientWidth - 8);
  const colX = [NW / 2 + 70, W * 0.3, W - NW * 1.5 - 40, W - NW / 2 - 14];
  const place = (
    ids: string[],
    kind: "el" | "calc",
    x: number,
    y0: number,
    step = 46,
  ) =>
    ids.forEach((id, i) => {
      if (nodes.has(id)) return;
      if (kind === "el") {
        const e = S.els.get(id)!;
        nodes.set(id, {
          id,
          kind,
          x,
          y: y0 + i * step,
          label: e.text,
          sub: `${e.sheet} · ${e.grid || e.type}`,
          color: CAT_COL[e.cat] ?? CAT_COL.Other,
        });
      } else {
        const c = S.calcs.get(id)!;
        const sec = c.doc === "stair" ? "STAIR" : c.section;
        nodes.set(id, {
          id,
          kind,
          x,
          y: y0 + i * step,
          label: `${c.sheet_id} ${c.title}`,
          sub: `${c.software}${c.level ? " · " + c.level : ""}`,
          color: SEC_COL[sec] ?? "#888",
        });
      }
    });
  let more: string[] = [];
  const LIM = 14;
  if (S.sel.kind === "el") {
    const id = S.sel.id;
    // load path: what it carries (above), what carries it (below, walked to the foundation)
    const carried = (S.up.get(id) ?? []).map((e) => e.src).slice(0, 6);
    const chain: string[] = [];
    const seen = new Set([id]);
    let frontier = [id];
    for (let d = 0; d < 5 && frontier.length; d++) {
      const next: string[] = [];
      for (const f of frontier)
        for (const e of S.down.get(f) ?? [])
          if (!seen.has(e.dst)) {
            seen.add(e.dst);
            chain.push(e.dst);
            next.push(e.dst);
          }
      frontier = next.slice(0, 4);
    }
    place(carried, "el", colX[0], 60);
    const yS = 60 + Math.max(carried.length, 1) * 46 + 20;
    place([id], "el", colX[0], yS);
    nodes.get(id)!.sel = true;
    place(chain.slice(0, 8), "el", colX[0], yS + 66);
    const ls = S.linksByEl.get(id) ?? [];
    const shownLinks = ls.slice(0, LIM);
    place(
      shownLinks.map((l) => l.calc),
      "calc",
      colX[2],
      60,
    );
    if (ls.length > LIM)
      more.push(`+${ls.length - LIM} more linked calc pages in the inspector`);
    // one hop of calc feeds around the linked pages
    const feeds = new Set<string>();
    for (const l of shownLinks.slice(0, 6))
      for (const e of [
        ...(S.cin.get(l.calc) ?? []),
        ...(S.cout.get(l.calc) ?? []),
      ].slice(0, 3))
        feeds.add(e.src === l.calc ? e.dst : e.src);
    place(
      [...feeds].filter((f) => !nodes.has(f)).slice(0, 12),
      "calc",
      colX[3],
      60,
    );
  } else {
    const id = S.sel.id;
    const ls = S.linksByCalc.get(id) ?? [];
    const els = [...new Set(ls.map((l) => l.el))];
    place(els.slice(0, 18), "el", colX[0], 60, 40);
    if (els.length > 18)
      more.push(`+${els.length - 18} more linked elements in the inspector`);
    const ins = (S.cin.get(id) ?? []).map((e) => e.src);
    const outs = (S.cout.get(id) ?? []).map((e) => e.dst);
    // feeding pages above, fed pages below, both in the right column; the page itself in the middle
    const insS = ins.slice(0, 8);
    const outsS = outs.filter((o) => !insS.includes(o)).slice(0, 10);
    place(insS, "calc", colX[3], 60);
    place(outsS, "calc", colX[3], 60 + insS.length * 46 + (insS.length ? 30 : 0));
    place([id], "calc", colX[2], 60 + Math.max(0, (insS.length + outsS.length - 1) * 23));
    nodes.get(id)!.sel = true;
    if (ins.length > 8 || outs.length > 10)
      more.push(`${ins.length} pages feed this page, it feeds ${outs.length}`);
  }
  const H = Math.max(
    420,
    Math.max(...[...nodes.values()].map((n) => n.y)) + 60,
  );
  // edges among the shown nodes
  const edgeEls: string[] = [];
  g.element_edges.forEach((e, i) => {
    const a = nodes.get(e.src),
      b = nodes.get(e.dst);
    if (a && b)
      edgeEls.push(
        `<path class="g-lp" data-ee="${i}" d="M${a.x - NW / 2},${a.y} C${a.x - NW / 2 - 50},${a.y} ${b.x - NW / 2 - 50},${b.y} ${b.x - NW / 2},${b.y}" marker-end="url(#arrL)"><title>${esc(e.rule)} - click for evidence</title></path>`,
      );
  });
  g.calc_edges.forEach((e, i) => {
    const a = nodes.get(e.src),
      b = nodes.get(e.dst);
    if (a && b) {
      const sx = a.x + (b.x >= a.x ? NW / 2 : -NW / 2),
        ex = b.x + (b.x >= a.x ? -NW / 2 : NW / 2);
      const d =
        Math.abs(a.x - b.x) < 5
          ? `M${a.x + NW / 2},${a.y} C${a.x + NW / 2 + 60},${a.y} ${b.x + NW / 2 + 60},${b.y} ${b.x + NW / 2},${b.y}`
          : `M${sx},${a.y} C${(sx + ex) / 2},${a.y} ${(sx + ex) / 2},${b.y} ${ex},${b.y}`;
      edgeEls.push(
        `<path class="g-ce" data-ce="${i}" d="${d}" marker-end="url(#arrC)"><title>${esc(e.rule)}: ${esc(e.labels.slice(0, 5).join(", "))} - click for evidence</title></path>`,
      );
    }
  });
  for (const l of g.links) {
    const a = nodes.get(l.el),
      b = nodes.get(l.calc);
    if (!a || !b) continue;
    const x1 = a.x + NW / 2,
      x2 = b.x - NW / 2,
      mx = (x1 + x2) / 2;
    lines.push(
      `<path class="g-ln ${tierCls(l.score)}" data-l="${esc(l.el)}|${esc(l.calc)}" d="M${x1},${a.y} C${mx},${a.y} ${mx},${b.y} ${x2},${b.y}"><title>${esc(l.tier)} ${Math.round(l.score * 100)}% - ${esc(l.rule)} - click to compare evidence</title></path>`,
    );
  }
  let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs>
    <marker id="arrC" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--calc)"/></marker>
    <marker id="arrL" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--ink)"/></marker></defs>
    <text class="g-head" x="${colX[0]}" y="26" text-anchor="middle">Elements (drawings)</text>
    <text class="g-head" x="${(colX[2] + colX[3]) / 2}" y="26" text-anchor="middle">Calc pages (calc package)</text>`;
  svg += lines.join("") + edgeEls.join("");
  for (const n of nodes.values()) {
    svg += `<g class="g-n ${n.kind} ${n.sel ? "sel" : ""}" data-${n.kind === "el" ? "nel" : "ncalc"}="${esc(n.id)}" transform="translate(${n.x - NW / 2},${n.y - NH / 2})"><rect width="${NW}" height="${NH}" rx="7"/><rect width="5" height="${NH}" rx="2" style="fill:${n.color};stroke:none"/>
      <text x="11" y="14">${esc(n.label.length > 24 ? n.label.slice(0, 23) + "…" : n.label)}</text><text class="t2" x="11" y="27">${esc(n.sub.slice(0, 27))}</text><title>${esc(n.label)}\n${esc(n.sub)}\nclick: select and open the original page</title></g>`;
  }
  if (more.length)
    svg += `<text class="g-more" x="${W - 10}" y="${H - 12}" text-anchor="end">${esc(more.join(" · "))}</text>`;
  svg += `</svg>`;
  host.innerHTML = svg + legend();
  wireGraph(host);
}


// ---------------- record / connection graphs (column layout) ----------------
type NK = SelKind | "absent";
type GN = { kind: NK; id: string; label: string; sub: string; color: string; sel?: boolean; dash?: boolean; act?: () => void };
type GE = { a: string; b: string; cls: string; title: string; act: () => void; arrow?: "C" | "L" | "R" };
const JOIN_TXT: Record<string, string> = { exact: "exact join (shared label)", inferred: "inferred join (coordinates)", absent: "absent - no support found" };
const nkey = (n: { kind: string; id: string }) => `${n.kind}:${n.id}`;
let edgeActs: (() => void)[] = [];
let nodeActs: (() => void)[] = [];

function recColor(r: Rec) {
  return SEC_COL[r.section] ?? "#888";
}
function recNode(r: Rec, sel = false): GN {
  return { kind: "rec", id: r.id, label: r.title, sub: `${r.table}${r.level && !r.table.includes(r.level) ? " · " + r.level : ""}`, color: recColor(r), sel };
}
function elNode(e: El, sel = false): GN {
  return { kind: "el", id: e.id, label: e.text, sub: `${e.sheet} · ${e.grid || e.type}`, color: CAT_COL[e.cat] ?? CAT_COL.Other, sel };
}
function calcNode(c: Calc): GN {
  const sec = c.doc === "stair" ? "STAIR" : c.section;
  return { kind: "calc", id: c.id, label: `${c.sheet_id} ${c.title}`, sub: `page · ${c.software}`, color: SEC_COL[sec] ?? "#888" };
}
function instNode(i: CInst, sel = false): GN {
  return { kind: "cinst", id: i.id, label: i.type_id ?? i.symbol_name ?? i.ref, sub: `${i.via}${i.symbol ? " " + i.symbol : ""} · ${i.sheet} ${i.grid || ""}`, color: "#e8590c", sel };
}
function typeNode(t: CType, sel = false): GN {
  return { kind: "ctype", id: t.id, label: `${t.id} ${t.title}`, sub: `detail · ${t.category}`, color: "#e8590c", sel };
}
const recEdgeCls = (e: REdge) => `g-re ${e.join}`;
const recEdgeTitle = (e: REdge) => `${e.kind} - ${JOIN_TXT[e.join]}: ${e.rule} - click for both rows`;

/** Draw columns of nodes left to right; edges between any two drawn nodes. */
function drawCols(host: HTMLElement, heads: string[], cols: GN[][], edges: GE[], more: string[], hint = "") {
  edgeActs = [];
  nodeActs = [];
  const keep = cols.map((c, i) => [c, heads[i]] as const).filter(([c]) => c.length);
  const n = keep.length;
  const W0 = Math.max(560, host.clientWidth - 8);
  // narrow the nodes before scrolling: the whole flow should fit the pane where it can
  const nw = Math.max(104, Math.min(NW, Math.floor((W0 - 28) / n) - 16));
  const W = Math.max(W0, n * (nw + 16) + 28);
  const xs = keep.map((_, i) => (n === 1 ? W / 2 : 14 + nw / 2 + (i * (W - 28 - nw)) / (n - 1)));
  const chars = Math.floor((nw - 16) / 6.6);
  const tall = Math.max(...keep.map(([c]) => c.length));
  const H = Math.max(380, 70 + tall * 44 + 40);
  const pos = new Map<string, { x: number; y: number; n: GN }>();
  keep.forEach(([c], i) => {
    const y0 = 60 + ((tall - c.length) * 44) / 2;
    c.forEach((g, j) => {
      if (!pos.has(nkey(g))) pos.set(nkey(g), { x: xs[i], y: y0 + j * 44, n: g });
    });
  });
  let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs>
    <marker id="arrC" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--calc)"/></marker>
    <marker id="arrL" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--ink)"/></marker>
    <marker id="arrR" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--bad)"/></marker></defs>`;
  keep.forEach(([, h], i) => (svg += `<text class="g-head" x="${xs[i]}" y="26" text-anchor="middle">${esc(n > 4 && h.length > chars ? h.slice(0, chars) : h)}</text>`));
  for (const e of edges) {
    const a = pos.get(e.a), b = pos.get(e.b);
    if (!a || !b) continue;
    let d: string;
    if (Math.abs(a.x - b.x) < 5) {
      const s = a.x - nw / 2;
      d = `M${s},${a.y} C${s - 50},${a.y} ${s - 50},${b.y} ${s},${b.y}`;
    } else {
      const dir = b.x > a.x ? 1 : -1;
      const sx = a.x + (dir * nw) / 2, ex = b.x - (dir * nw) / 2, mx = (sx + ex) / 2;
      d = `M${sx},${a.y} C${mx},${a.y} ${mx},${b.y} ${ex},${b.y}`;
    }
    edgeActs.push(e.act);
    // dashed thin strokes are hard to hit (gaps are not clickable): a wide transparent twin takes the click
    svg += `<path class="${e.cls}" d="${d}"${e.arrow ? ` marker-end="url(#arr${e.arrow})"` : ""}/><path class="g-hit" data-ea="${edgeActs.length - 1}" d="${d}"><title>${esc(e.title)}</title></path>`;
  }
  for (const { x, y, n: g } of pos.values()) {
    const attr = g.kind === "absent" || g.act ? `data-na="${nodeActs.push(g.act ?? (() => {})) - 1}"` : `data-nk="${g.kind}" data-ni="${esc(g.id)}"`;
    svg += `<g class="g-n ${g.kind} ${g.sel ? "sel" : ""} ${g.dash ? "dash" : ""}" ${attr} transform="translate(${x - nw / 2},${y - NH / 2})"><rect width="${nw}" height="${NH}" rx="7"/><rect width="5" height="${NH}" rx="2" style="fill:${g.color};stroke:none"/>
      <text x="11" y="14">${esc(g.label.length > chars ? g.label.slice(0, chars - 1) + "…" : g.label)}</text><text class="t2" x="11" y="27">${esc(g.sub.slice(0, chars + 3))}</text><title>${esc(g.label)}\n${esc(g.sub)}\n${g.kind === "absent" ? "click: show the row with no support" : "click: select and open the original page"}</title></g>`;
  }
  if (more.length) svg += `<text class="g-more" x="${W - 10}" y="${H - 12}" text-anchor="end">${esc(more.join(" · "))}</text>`;
  svg += `</svg>`;
  host.innerHTML = (hint ? `<div class="hint">${hint}</div>` : "") + svg + recLegend();
  // wider than the pane: scroll so the selected node sits in the middle
  const selP = [...pos.values()].find((p) => p.n.sel);
  const wrap = host.parentElement;
  if (wrap && selP && W > wrap.clientWidth) wrap.scrollLeft = Math.max(0, selP.x - wrap.clientWidth / 2);
  host.querySelectorAll<SVGGElement>("[data-nk]").forEach((g) => (g.onclick = () => select({ kind: g.dataset.nk as SelKind, id: g.dataset.ni! })));
  host.querySelectorAll<SVGGElement>("[data-na]").forEach((g) => (g.onclick = () => nodeActs[+g.dataset.na!]()));
  host.querySelectorAll<SVGPathElement>("[data-ea]").forEach((p) => (p.onclick = () => edgeActs[+p.dataset.ea!]()));
}
function recLegend() {
  return `<div class="glegend"><span><i class="lg lp"></i>load path (drawings)</span><span><i class="lg re exact"></i>calc load path - exact</span><span><i class="lg re inferred"></i>inferred</span><span><i class="lg re absent"></i>absent</span><span><i class="lg cn"></i>connection</span><span><i class="lg ln good"></i>link &ge; 75%</span><span><i class="lg ln warn"></i>55-74%</span><span><i class="lg ln bad"></i>&lt; 55%</span></div>`;
}
function absentNode(e: REdge, i: number): GN {
  return { kind: "absent", id: `${e.src}#${i}`, label: e.kind === "member->support" ? `no support (${e.end ?? "end"})` : "not traced", sub: e.rule, color: "var(--bad)", dash: true, act: () => openREdge(e) };
}
function recEdgesOut(id: string) {
  return S.rout.get(id) ?? [];
}

function recGraph(host: HTMLElement) {
  const r = S.recs.get(S.sel!.id);
  if (!r) return;
  const edges: GE[] = [];
  const more: string[] = [];
  const addRE = (e: REdge, absentId?: string) =>
    edges.push({ a: nkey({ kind: "rec", id: e.src }), b: absentId ?? nkey({ kind: "rec", id: e.dst! }), cls: recEdgeCls(e), title: recEdgeTitle(e), act: () => openREdge(e), arrow: e.join === "absent" ? "R" : "C" });
  // upstream (what feeds it) two hops, downstream (what carries it) three hops
  const up: GN[][] = [[], []];
  const seen = new Set([r.id]);
  let front = [r.id];
  for (let d = 0; d < 2; d++) {
    const next: string[] = [];
    for (const f of front)
      for (const e of S.rin.get(f) ?? []) {
        addRE(e);
        if (seen.has(e.src)) continue;
        seen.add(e.src);
        if (up[d].length >= 9) continue;
        const s = S.recs.get(e.src);
        if (s) (up[d].push(recNode(s)), next.push(e.src));
      }
    if ((S.rin.get(r.id) ?? []).length > 9 && d === 0) more.push(`${(S.rin.get(r.id) ?? []).length} records feed this one (9 shown - all in the inspector)`);
    front = next;
  }
  const down: GN[][] = [[], [], []];
  front = [r.id];
  for (let d = 0; d < 3; d++) {
    const next: string[] = [];
    for (const f of front)
      recEdgesOut(f).forEach((e, i) => {
        if (!e.dst) {
          if (down[d].length < 9) {
            const a = absentNode(e, i);
            down[d].push(a);
            addRE(e, nkey(a));
          }
          return;
        }
        addRE(e);
        if (seen.has(e.dst)) return;
        seen.add(e.dst);
        if (down[d].length >= 9) return;
        const s = S.recs.get(e.dst);
        if (s) (down[d].push(recNode(s)), next.push(e.dst));
      });
    front = next;
  }
  // elements linked to this record (re-targeted page links)
  const rls = S.rlByRec.get(r.id) ?? [];
  const els = [...new Set(rls.map((l) => l.el))];
  const elCol = els.slice(0, 12).map((id) => elNode(S.els.get(id)!));
  if (els.length > 12) more.push(`+${els.length - 12} more linked elements in the inspector`);
  for (const l of rls)
    edges.push({ a: nkey({ kind: "el", id: l.el }), b: nkey({ kind: "rec", id: r.id }), cls: `g-ln ${tierCls(l.score)}`, title: `${l.tier} - ${l.rule} - click to compare evidence`, act: () => openRLink(l, r.id) });
  const conn: GN[] = [];
  if (r.type === "connection_design") {
    const t = S.ctypes.get("2/S8.2.7");
    if (t) {
      conn.push({ ...typeNode(t), dash: true, sub: "candidate by title only" });
      edges.push({ a: nkey({ kind: "rec", id: r.id }), b: nkey({ kind: "ctype", id: t.id }), cls: "g-cn cand", title: "candidate detail by title only - not a link", act: () => select({ kind: "ctype", id: t.id }) });
    }
  }
  drawCols(
    host,
    ["Elements linked", "Feeds (2 hops)", "Feeds", "Calc record", "Carried by", "then", "then", "Connection detail"],
    [elCol, up[1], up[0], [recNode(r, true)], down[0], down[1], down[2], conn],
    edges,
    more,
    `Calc load path of <b>${esc(r.title)}</b> - ${esc(r.run_title)}. Solid = exact join on a shared label, dashed = inferred from coordinates, red dotted = no support found. Click any edge for both rows on the original pages.`,
  );
}

function elGraph(host: HTMLElement) {
  const id = S.sel!.id;
  const e0 = S.els.get(id)!;
  const edges: GE[] = [];
  const more: string[] = [];
  const carried = (S.up.get(id) ?? []).map((e) => e.src).slice(0, 6);
  const chain: string[] = [];
  const seen = new Set([id]);
  let frontier = [id];
  for (let d = 0; d < 5 && frontier.length; d++) {
    const next: string[] = [];
    for (const f of frontier)
      for (const e of S.down.get(f) ?? [])
        if (!seen.has(e.dst)) (seen.add(e.dst), chain.push(e.dst), next.push(e.dst));
    frontier = next.slice(0, 4);
  }
  const col0 = [...carried.map((x) => elNode(S.els.get(x)!)), elNode(e0, true), ...chain.slice(0, 8).map((x) => elNode(S.els.get(x)!))];
  const shown0 = new Set(col0.map((n) => n.id));
  S.g!.element_edges.forEach((e) => {
    if (shown0.has(e.src) && shown0.has(e.dst))
      edges.push({ a: nkey({ kind: "el", id: e.src }), b: nkey({ kind: "el", id: e.dst }), cls: "g-lp", title: `${e.rule} - click for evidence`, act: () => openEEdge(e), arrow: "L" });
  });
  const insts = S.instByEl.get(id) ?? [];
  const col1 = insts.slice(0, 10).map((i) => instNode(i));
  for (const i of insts.slice(0, 10))
    edges.push({ a: nkey({ kind: "cinst", id: i.id }), b: nkey({ kind: "el", id }), cls: "g-cn", title: `${i.via}: ${i.attach_rule} - click for evidence`, act: () => openInstEl(i, id) });
  // linked calc RECORDS (page links re-targeted); pages only where no record matched
  const col2: GN[] = [];
  const LIM = 14;
  const rls = S.rlByEl.get(id) ?? [];
  const retargeted = new Set(rls.map((l) => l.calc));
  const recIds: string[] = [];
  for (const l of rls)
    for (const rid of l.records) {
      if (!recIds.includes(rid)) recIds.push(rid);
      if (recIds.indexOf(rid) < LIM)
        edges.push({ a: nkey({ kind: "el", id }), b: nkey({ kind: "rec", id: rid }), cls: `g-ln ${tierCls(l.score)}`, title: `${l.tier} - ${l.rule} - click to compare evidence`, act: () => openRLink(l, rid) });
    }
  recIds.slice(0, LIM).forEach((rid) => col2.push(recNode(S.recs.get(rid)!)));
  if (recIds.length > LIM) more.push(`+${recIds.length - LIM} more linked calc records in the inspector`);
  for (const l of (S.linksByEl.get(id) ?? []).filter((x) => !retargeted.has(x.calc)).slice(0, 6)) {
    col2.push(calcNode(S.calcs.get(l.calc)!));
    edges.push({ a: nkey({ kind: "el", id }), b: nkey({ kind: "calc", id: l.calc }), cls: `g-ln ${tierCls(l.score)}`, title: `${l.tier} - page link (no record on the page matched) - ${l.rule}`, act: () => openLink(l) });
  }
  const col3: GN[] = [];
  const seen3 = new Set(recIds.slice(0, LIM));
  for (const rid of recIds.slice(0, 6))
    for (const e of recEdgesOut(rid).slice(0, 3)) {
      if (!e.dst) continue;
      edges.push({ a: nkey({ kind: "rec", id: rid }), b: nkey({ kind: "rec", id: e.dst }), cls: recEdgeCls(e), title: recEdgeTitle(e), act: () => openREdge(e), arrow: "C" });
      if (seen3.has(e.dst) || col3.length >= 10) continue;
      seen3.add(e.dst);
      const s = S.recs.get(e.dst);
      if (s) col3.push(recNode(s));
    }
  drawCols(host, ["Elements (drawings)", "Connections", "Calc records", "Calc load path"], [col0, col1, col2, col3], edges, more);
}

function connGraph(host: HTMLElement) {
  const edges: GE[] = [];
  const more: string[] = [];
  let insts: CInst[], t: CType | undefined, selInst: CInst | undefined;
  if (S.sel!.kind === "ctype") {
    t = S.ctypes.get(S.sel!.id);
    insts = (t?.instances ?? []).map((i) => S.cinst.get(i)!).filter(Boolean);
  } else {
    selInst = S.cinst.get(S.sel!.id);
    insts = selInst ? [selInst] : [];
    t = selInst?.type_id ? S.ctypes.get(selInst.type_id) : undefined;
  }
  const elIds: string[] = [];
  for (const i of insts.slice(0, 14))
    for (const a of i.attached) {
      if (!elIds.includes(a.id)) elIds.push(a.id);
      edges.push({ a: nkey({ kind: "el", id: a.id }), b: nkey({ kind: "cinst", id: i.id }), cls: "g-cn", title: `${a.role ?? "attached"} (${a.dist} pt) - click for evidence`, act: () => openInstEl(i, a.id) });
    }
  if (insts.length > 14) more.push(`+${insts.length - 14} more instances in the inspector`);
  const col0 = elIds.slice(0, 16).map((x) => elNode(S.els.get(x)!));
  const col1 = insts.slice(0, 14).map((i) => instNode(i, i === selInst));
  const col2 = t ? [typeNode(t, S.sel!.kind === "ctype")] : [];
  if (t) for (const i of insts.slice(0, 14)) edges.push({ a: nkey({ kind: "cinst", id: i.id }), b: nkey({ kind: "ctype", id: t.id }), cls: "g-cn", title: `instance of ${t.id}`, act: () => select({ kind: "ctype", id: t!.id }) });
  const col3: GN[] = [];
  const par = S.recs.get("stair:connection_design:PARAPET");
  if (t?.id === "2/S8.2.7" && par) {
    col3.push({ ...recNode(par), dash: true, sub: "candidate by title only" });
    edges.push({ a: nkey({ kind: "ctype", id: t.id }), b: nkey({ kind: "rec", id: par.id }), cls: "g-cn cand", title: "candidate design by title only - the calc cites no detail", act: () => select({ kind: "rec", id: par.id }) });
  } else if (t) {
    col3.push({ kind: "absent", id: `nocalc:${t.id}`, label: "no connection calc", sub: "no calc page designs this detail", color: "var(--bad)", dash: true, act: () => { const f = S.g!.findings.findIndex((x) => x.kind === "no connection calcs in the main package"); if (f >= 0) (location.hash = `find=${f}`); } });
  }
  drawCols(host, ["Elements", "Instances on the sheets", "Connection detail", "Design calc"], [col0, col1, col2, col3], edges, more,
    t ? `<b>${esc(t.id)}</b> ${esc(t.title)} - ${insts.length} instance${insts.length === 1 ? "" : "s"} (callout bubbles, plan symbols, text references), ${elIds.length} attached element${elIds.length === 1 ? "" : "s"}.` : `Plan symbol without a detail number${selInst?.legend_text ? `: ${esc(selInst.legend_text)}` : ""}`);
}

function legend() {
  return `<div class="glegend"><span><i class="lg lp"></i>load path (drawings)</span><span><i class="lg ce"></i>calc feeds</span><span><i class="lg ln good"></i>link &ge; 75%</span><span><i class="lg ln warn"></i>55-74%</span><span><i class="lg ln bad"></i>&lt; 55%</span></div>`;
}

function overview(host: HTMLElement) {
  // clusters: elements by sheet + type, calc pages by section
  const g = S.g!;
  const ecl = new Map<string, El[]>();
  for (const e of g.elements) push(ecl, `${e.sheet}|${e.type}`, e);
  const ccl = new Map<string, Calc[]>();
  for (const c of g.calcs)
    push(ccl, c.doc === "stair" ? "STAIR" : c.section, c);
  const ekeys = [...ecl.keys()]
    .sort(nat)
    .filter(
      (k) => ecl.get(k)!.length >= 2 || S.linksByEl.has(ecl.get(k)![0].id),
    );
  const ckeys = [...ccl.keys()].sort(
    (a, b) => SEC_ORDER.indexOf(a) - SEC_ORDER.indexOf(b),
  );
  const step = 26,
    H = Math.max(ekeys.length * step + 80, 420);
  const epos = new Map(ekeys.map((k, i) => [k, 50 + i * step]));
  const cstep = (H - 100) / Math.max(1, ckeys.length);
  const cpos = new Map(ckeys.map((k, i) => [k, 70 + i * cstep]));
  const bundle = new Map<string, number>();
  for (const l of g.links) {
    const e = S.els.get(l.el)!,
      c = S.calcs.get(l.calc)!;
    const k = `${e.sheet}|${e.type}#${c.doc === "stair" ? "STAIR" : c.section}`;
    bundle.set(k, (bundle.get(k) ?? 0) + 1);
  }
  const W = Math.max(560, host.clientWidth - 8);
  const EW = Math.min(300, W * 0.42),
    CW = Math.min(280, W * 0.36),
    CX = W - CW - 14;
  let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><text class="g-head" x="${14 + EW / 2}" y="24" text-anchor="middle">Elements by sheet and type</text><text class="g-head" x="${CX + CW / 2}" y="24" text-anchor="middle">Calc package sections</text>`;
  for (const [k, n] of bundle) {
    const [ek, ck] = k.split("#");
    const y1 = epos.get(ek),
      y2 = cpos.get(ck);
    if (y1 === undefined || y2 === undefined) continue;
    svg += `<path class="g-bundle" d="M${14 + EW},${y1} C${(14 + EW + CX) / 2},${y1} ${(14 + EW + CX) / 2},${y2} ${CX},${y2}" style="stroke-width:${Math.min(14, 1 + Math.sqrt(n))}"><title>${n} links ${esc(ek.replace("|", " "))} -> ${esc(secName(ck))}</title></path>`;
  }
  for (const k of ekeys) {
    const es = ecl.get(k)!,
      y = epos.get(k)!;
    const nl = es.filter((e) => S.linksByEl.has(e.id)).length;
    const [sh, ty] = k.split("|");
    svg += `<g class="g-cl" data-ecl="${esc(k)}" transform="translate(14,${y - 11})"><rect width="${EW}" height="22" rx="5"/><rect width="${(EW * nl) / es.length}" height="22" rx="5" class="fillok"/><text x="8" y="15"><tspan font-weight="600">${esc(sh)}</tspan> ${esc(ty)}</text><text x="${EW - 8}" y="15" text-anchor="end" class="t2">${nl}/${es.length}</text><title>${nl} of ${es.length} linked - click to list them</title></g>`;
  }
  for (const k of ckeys) {
    const cs = ccl.get(k)!,
      y = cpos.get(k)!;
    const nl = cs.filter((c) => S.linksByCalc.has(c.id)).length;
    svg += `<g class="g-cl calc" data-ccl="${esc(k)}" transform="translate(${CX},${y - 20})"><rect width="${CW}" height="40" rx="7"/><rect width="6" height="40" rx="2" style="fill:${SEC_COL[k] ?? "#888"}"/><text x="14" y="17" font-weight="600">${esc(secName(k))}</text><text x="14" y="32" class="t2">${cs.length} pages · ${nl} linked to elements</text></g>`;
  }
  svg += `</svg>`;
  host.innerHTML =
    `<div class="hint">Overview - every link bundled by element group and calc section. Pick an element or calc page (left, or click a group) to see its load path, its calc pages and the calc feeds, each opening the original page.</div>` +
    svg +
    legend();
  host.querySelectorAll<SVGGElement>("[data-ecl]").forEach(
    (n) =>
      (n.onclick = () => {
        S.tab = "el";
        S.open.add(n.dataset.ecl!);
        renderList();
        const first =
          ecl.get(n.dataset.ecl!)!.find((e) => S.linksByEl.has(e.id)) ??
          ecl.get(n.dataset.ecl!)![0];
        select({ kind: "el", id: first.id });
      }),
  );
  host.querySelectorAll<SVGGElement>("[data-ccl]").forEach(
    (n) =>
      (n.onclick = () => {
        S.tab = "calc";
        const cs = ccl.get(n.dataset.ccl!)!;
        const first = cs.find((c) => S.linksByCalc.has(c.id)) ?? cs[0];
        select({ kind: "calc", id: first.id });
      }),
  );
}

function wireGraph(host: HTMLElement) {
  host
    .querySelectorAll<SVGGElement>("[data-nel]")
    .forEach(
      (n) => (n.onclick = () => select({ kind: "el", id: n.dataset.nel! })),
    );
  host
    .querySelectorAll<SVGGElement>("[data-ncalc]")
    .forEach(
      (n) => (n.onclick = () => select({ kind: "calc", id: n.dataset.ncalc! })),
    );
  host.querySelectorAll<SVGPathElement>("[data-l]").forEach(
    (p) =>
      (p.onclick = () => {
        const [a, b] = p.dataset.l!.split("|");
        const l = S.linksByEl.get(a)!.find((x) => x.calc === b)!;
        openLink(l);
      }),
  );
  host
    .querySelectorAll<SVGPathElement>("[data-ee]")
    .forEach(
      (p) => (p.onclick = () => openEEdge(S.g!.element_edges[+p.dataset.ee!])),
    );
  host
    .querySelectorAll<SVGPathElement>("[data-ce]")
    .forEach(
      (p) => (p.onclick = () => openCEdge(S.g!.calc_edges[+p.dataset.ce!])),
    );
}

// ---------------- inspector ----------------

// ---------------- inspector: records / connections ----------------
let inspActs: (() => void)[] = [];
const ia = (f: () => void) => `data-ia="${inspActs.push(f) - 1}"`;
const joinChip = (j: string) => `<span class="chip ${j === "exact" ? "good" : j === "inferred" ? "warn" : "bad"}">${esc(j)}</span>`;
function fmtVal(v: any): string {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "number") return String(Math.round(v * 1000) / 1000);
  if (Array.isArray(v)) return v.map(fmtVal).join(", ");
  if (typeof v === "object")
    return Object.entries(v)
      .map(([k, x]) => `${k}: ${typeof x === "object" && x !== null && !Array.isArray(x) ? "{" + fmtVal(x) + "}" : fmtVal(x)}`)
      .join("; ");
  return String(v);
}
function inspRec(r: Rec): string {
  let h = `<div class="ih"><h2 class="mono">${esc(r.title)}</h2><span class="kind">${esc(r.type.replace(/_/g, " "))} record · ${esc(r.run_title)} · ${esc(secName(r.section))}${r.level ? " · " + esc(r.level) : ""} · PDF p${esc(r.pages.slice(0, 8).join(", "))}${r.pages.length > 8 ? "…" : ""}</span>
    <button class="sm" ${ia(() => single(recEv(r)))}>Show row</button></div>`;
  const skip = new Set(["geom", "end_reactions", "points", "axial", "vertical_loads_k", "col0", "Label"]);
  const kv = Object.entries(r.values).filter(([k, v]) => !skip.has(k) && fmtVal(v) !== "");
  if (kv.length) h += `<div class="kvs">${kv.slice(0, 24).map(([k, v]) => `<span><span class="m">${esc(k.replace(/_/g, " "))}</span> <span class="mono">${esc(fmtVal(v).slice(0, 120))}</span></span>`).join("")}</div>`;
  if (r.values.geom) h += `<div class="kv">Calc-model geometry (RISA own coordinates, ft): <span class="mono">Z,X ${esc(fmtVal(r.values.geom.start))} &rarr; ${esc(fmtVal(r.values.geom.end))} at elev ${esc(r.values.geom.elev_ft)} ft</span></div>`;
  if (r.values.axial) h += `<div class="kv">Column axial (k): <span class="mono">${esc(fmtVal(r.values.axial))}</span></div>`;
  if (r.values.end_reactions) h += `<div class="kv">End reactions (k): <span class="mono">${esc(fmtVal({ start: { DL: r.values.end_reactions.start?.dl_k, LL: r.values.end_reactions.start?.ll_k, max: r.values.end_reactions.start?.max_k }, end: { DL: r.values.end_reactions.end?.dl_k, LL: r.values.end_reactions.end?.ll_k, max: r.values.end_reactions.end?.max_k } }))}</span></div>`;
  if (r.values.vertical_loads_k) h += `<div class="kv">Footing vertical loads (k): <span class="mono">${esc(fmtVal(r.values.vertical_loads_k))}</span></div>`;
  const notes = S.notesByRec.get(r.id) ?? [];
  if (notes.length)
    h += `<h3>Engineer notes (${notes.length})</h3>` + notes.map((n) => `<div class="li note" ${ia(() => openNote(n))}><span class="mono">${esc(n.sheet)}</span> <span>"${esc(n.text.slice(0, 160))}"</span><div class="why">${esc(n.attached.find((a) => a.record === r.id)?.rule ?? "")}</div></div>`).join("");
  if (r.type === "connection_design") {
    const t = S.ctypes.get("2/S8.2.7");
    h += `<h3>Detail</h3>` + (t ? `<div class="li" ${ia(() => select({ kind: "ctype", id: t.id }))}><span class="mono"><b>${esc(t.id)}</b></span> <span class="m">${esc(t.title)}</span><span class="chip warn">candidate</span><div class="why">by title only - the calc cites no detail number, so this is not a link</div></div>` : `<div class="li none">no candidate detail</div>`);
  }
  const ins = S.rin.get(r.id) ?? [], outs = S.rout.get(r.id) ?? [];
  const reLi = (e: REdge, other: string | null, dir: string) => {
    const o = other ? S.recs.get(other) : null;
    return `<div class="li" ${ia(() => openREdge(e))}><span class="m">${dir}</span> <span class="mono"><b>${esc(o?.title ?? "no support found")}</b></span> <span class="m">${esc(o?.table ?? "")}</span>${joinChip(e.join)}<div class="why">${esc(e.kind)}: ${esc(e.rule)}</div></div>`;
  };
  h += `<h3>Fed by (${ins.length})</h3>` + (ins.slice(0, 80).map((e) => reLi(e, e.src, "from")).join("") || `<div class="li none">nothing in the calc load path</div>`);
  h += `<h3>Carried by (${outs.length})</h3>` + (outs.slice(0, 80).map((e) => reLi(e, e.dst, "to")).join("") || `<div class="li none">nothing in the calc load path</div>`);
  const rls = S.rlByRec.get(r.id) ?? [];
  h += `<h3>Elements linked (${new Set(rls.map((l) => l.el)).size})</h3>` +
    (rls.slice(0, 150).map((l) => { const e = S.els.get(l.el)!; return `<div class="li" ${ia(() => openRLink(l, r.id))}><span class="mono"><b>${esc(e.text)}</b></span> <span class="m">${esc(e.sheet)} ${esc(e.grid)}</span><span class="chip ${tierCls(l.score)}">${Math.round(l.score * 100)}%</span><div class="why">via ${esc(S.calcs.get(l.calc)?.sheet_id ?? l.calc)} - ${esc(l.rule)}</div></div>`; }).join("") || `<div class="li none">No drawn element is linked to this record.</div>`);
  const byTable = new Map<string, number[]>();
  r.ev.forEach((e, i) => push(byTable, (e as any).table || r.table, i));
  h += `<h3>Rows on the original pages (${r.ev.length})</h3>`;
  for (const [tab, idx] of byTable)
    h += `<div class="li" ${ia(() => single(recEv(r, idx[0])))}><span class="m">${esc(tab)}</span> <span class="chip">p${esc([...new Set(idx.map((i) => r.ev[i].page))].join(", "))}</span><div class="why mono">${esc((r.ev[idx[0]].text ?? "").slice(0, 140))}</div></div>`;
  return h;
}
function inspCtype(t: CType): string {
  const insts = (t.instances ?? []).map((i) => S.cinst.get(i)!).filter(Boolean);
  let h = `<div class="ih"><h2><span class="mono">${esc(t.id)}</span> ${esc(t.title)}</h2><span class="kind">Connection detail · ${esc(t.category)} · ${esc(t.sheet)} ${esc(t.sheet_title)} · PDF p${t.page}${t.scale ? " · " + esc(t.scale) : ""}</span>
    <button class="sm" ${ia(() => single(ctypeEv(t), t.bbox))}>Show detail</button></div>`;
  if (t.spec?.length) h += `<div class="kv">Printed: <span class="mono">${esc(t.spec.map((s) => s.text).join(" | ").slice(0, 300))}</span></div>`;
  if (t.sizes?.length) h += `<div class="kv">Sizes: <span class="mono">${esc(t.sizes.join(", "))}</span></div>`;
  const par = S.recs.get("stair:connection_design:PARAPET");
  h += `<h3>Design calc</h3>` + (t.id === "2/S8.2.7" && par
    ? `<div class="li" ${ia(() => select({ kind: "rec", id: par.id }))}><span class="mono"><b>${esc(par.title)}</b></span><span class="chip warn">candidate</span><div class="why">stair package pp ${esc(par.pages.join(", "))} - by title only, the calc cites no detail number</div></div>`
    : `<div class="li none">No calc page designs this detail (the main package designs no steel connection).</div>`);
  h += `<h3>Instances (${insts.length})</h3>` + (insts.map((i) => `<div class="li" ${ia(() => select({ kind: "cinst", id: i.id }))}><span class="mono">${esc(i.sheet)}</span> <span class="m">${esc(i.via)} · ${esc(i.grid || "-")}</span>${i.attached.length ? `<span class="chip good">${i.attached.map((a) => esc(S.els.get(a.id)?.text ?? a.id)).join(", ")}</span>` : `<span class="chip">unattached</span>`}</div>`).join("") || `<div class="li none">Not called out on any plan or elevation.</div>`);
  if (t.referenced_from_details?.length) h += `<div class="kv">Referenced from details: <span class="mono">${esc(t.referenced_from_details.join(", "))}</span></div>`;
  return h;
}
function inspCinst(i: CInst): string {
  const t = i.type_id ? S.ctypes.get(i.type_id) : undefined;
  let h = `<div class="ih"><h2 class="mono">${esc(i.type_id ?? i.symbol_name ?? i.ref)}</h2><span class="kind">Connection instance · ${esc(i.via)}${i.symbol_name ? " - " + esc(i.symbol_name) : ""} · ${esc(i.sheet)} · grid ${esc(i.grid || "-")} · PDF p${i.page}</span>
    <button class="sm" ${ia(() => single(cinstEv(i)))}>Show on sheet</button></div>`;
  if (i.legend_text) h += `<div class="kv">Legend: <span class="mono">${esc(i.legend_text)}</span></div>`;
  if (i.context) h += `<div class="kv">Text: <span class="mono">${esc(i.context)}</span></div>`;
  if (t) h += `<h3>Detail</h3><div class="li" ${ia(() => select({ kind: "ctype", id: t.id }))}><span class="mono"><b>${esc(t.id)}</b></span> <span class="m">${esc(t.title)}</span></div>`;
  h += `<h3>Attached elements (${i.attached.length})</h3>` + (i.attached.map((a) => `<div class="li" ${ia(() => openInstEl(i, a.id))}><span class="mono"><b>${esc(S.els.get(a.id)?.text ?? a.id)}</b></span> <span class="m">${esc(a.type)} · ${esc(a.role ?? "")} · ${a.dist} pt</span><button class="sm" ${ia(() => select({ kind: "el", id: a.id }))}>Select</button></div>`).join("") || `<div class="li none">${esc(i.unattached_reason ?? "No drawn element near enough")}</div>`);
  h += `<div class="why">${esc(i.attach_rule)}</div>`;
  const mk = S.ig?.conn_markers.find((m) => m.inst === i.id);
  h += `<div class="m3d">${mk ? `<b>In 3D</b> as a marker - ${esc(mk.rule)}` : "<b>Not in 3D</b> - no attached element in the 3D model, or not on a plan sheet"}</div>`;
  return h;
}
function inspElExtra(e: El): string {
  let h = "";
  const insts = S.instByEl.get(e.id) ?? [];
  if (insts.length)
    h += `<h3>Connections (${insts.length})</h3>` + insts.map((i) => `<div class="li" ${ia(() => openInstEl(i, e.id))}><span class="mono"><b>${esc(i.type_id ?? i.symbol_name ?? i.ref)}</b></span> <span class="m">${esc(i.via)}${i.type_id ? " · " + esc(S.ctypes.get(i.type_id)?.title ?? "") : ""}</span><button class="sm" ${ia(() => select({ kind: "cinst", id: i.id }))}>Select</button></div>`).join("");
  const rls = S.rlByEl.get(e.id) ?? [];
  if (S.ig)
    h += `<h3>Calc records (${new Set(rls.flatMap((l) => l.records)).size})</h3>` +
      (rls.map((l) => { const c = S.calcs.get(l.calc)!; return `<div class="li rl"><span class="mono"><b>${esc(c.sheet_id)}</b></span> <span class="m">${esc(c.title)}</span><span class="chip ${tierCls(l.score)}">${Math.round(l.score * 100)}%</span><div class="why">${esc(l.rule)}</div><div class="recs">${l.records.slice(0, 40).map((rid) => `<button class="sm" ${ia(() => openRLink(l, rid))} title="compare evidence">${esc(S.recs.get(rid)?.title ?? rid)}</button>`).join("")}${l.records.length > 40 ? ` +${l.records.length - 40}` : ""}</div></div>`; }).join("") || `<div class="li none">No calc record matched (see the page links below).</div>`);
  return h;
}
function inspCalcExtra(c: Calc): string {
  const rs = S.recsByPage.get(`${c.doc}|${c.page}`) ?? [];
  if (!S.ig) return "";
  return `<h3>Records on this page (${rs.length})</h3>` + (rs.slice(0, 120).map((r) => `<div class="li" ${ia(() => select({ kind: "rec", id: r.id }))}><span class="mono"><b>${esc(r.title)}</b></span> <span class="m">${esc(r.table)}</span></div>`).join("") || `<div class="li none">No record has a row on this page.</div>`) + (rs.length > 120 ? `<div class="why">+${rs.length - 120} more</div>` : "");
}

function renderInsp() {
  const host = $("insp");
  inspActs = [];
  if (!S.sel) {
    host.innerHTML = `<div class="ihint">Select an element, a calc page or a finding. Links show both sides' evidence side by side.</div>`;
    return;
  }
  let h = "";
  if (S.sel.kind === "rec") h = inspRec(S.recs.get(S.sel.id)!);
  else if (S.sel.kind === "ctype") h = inspCtype(S.ctypes.get(S.sel.id)!);
  else if (S.sel.kind === "cinst") h = inspCinst(S.cinst.get(S.sel.id)!);
  else if (S.sel.kind === "el") {
    const e = S.els.get(S.sel.id)!;
    const ls = S.linksByEl.get(e.id) ?? [];
    h += `<div class="ih"><h2 class="mono">${esc(e.text)}</h2><span class="kind">${esc(e.type)} · ${esc(e.sheet)} ${esc(e.sheet_title)} · ${esc(e.level || "no level")} · grid ${esc(e.grid || "-")}${e.grid_node ? ` (on ${esc(e.grid_node)})` : ""}</span>
      <button class="sm" data-open-el>Show on sheet</button></div>`;
    const sch = e.params.schedule
      ? `<div class="kv">Schedule: <span class="mono">${esc(e.params.schedule)}</span></div>`
      : "";
    h += sch;
    const m = e.model;
    if (m)
      h += m.in3d
        ? `<div class="m3d"><b>In 3D</b> (${esc(m.rule)}) - ${esc(m.position)}<br>Elevation: ${esc(m.elevation)}<br>Profile: ${esc(m.profile)}${(m.assumed ?? []).map((a) => ` <span class="chip assumed">assumed: ${esc(a)}</span>`).join("")}</div>`
        : `<div class="m3d"><b>Not in 3D</b> - ${esc(m.reason)}</div>`;
    const lp = [
      ...(S.down.get(e.id) ?? []).map((x) => ["bears on", x] as const),
      ...(S.up.get(e.id) ?? []).map((x) => ["carries", x] as const),
    ];
    if (lp.length)
      h +=
        `<h3>Load path (${lp.length})</h3>` +
        lp
          .map(([v, x]) => {
            const o = S.els.get(v === "bears on" ? x.dst : x.src)!;
            return `<div class="li" data-ee="${S.g!.element_edges.indexOf(x)}"><span class="m">${v}</span> <span class="mono">${esc(o.text)}</span> <span class="m">${esc(o.sheet)} ${esc(o.grid)}</span><span class="chip">${esc(x.rule)}</span></div>`;
          })
          .join("");
    h += inspElExtra(e);
    h += `<h3>Calc pages (${ls.length})</h3>`;
    h += ls.length
      ? ls
          .map((l) => {
            const c = S.calcs.get(l.calc)!;
            return `<div class="li" data-l="${esc(l.el)}|${esc(l.calc)}"><span class="mono"><b>${esc(c.sheet_id)}</b></span> <span class="m">${esc(c.title)}</span><span class="chip ${tierCls(l.score)}">${Math.round(l.score * 100)}%</span><div class="why">${esc(l.tier)} - ${esc(l.rule)}</div></div>`;
          })
          .join("")
      : `<div class="li none">${esc(S.g!.findings.find((f) => f.el === e.id)?.text ?? "No calc found")}</div>`;
  } else {
    const c = S.calcs.get(S.sel.id)!;
    const ls = S.linksByCalc.get(c.id) ?? [];
    h += `<div class="ih"><h2><span class="mono">${esc(c.sheet_id)}</span> ${esc(c.title)}</h2><span class="kind">${esc(secName(c.doc === "stair" ? "STAIR" : c.section))} · ${esc(c.software)} · PDF p${c.page}${c.level ? " · " + esc(c.level) : ""}${c.kind ? " · " + esc(c.kind) + " page" : ""}</span>
      <button class="sm" data-open-calc>Show page</button></div>`;
    if (c.sizes.length)
      h += `<div class="kv">Sizes printed: <span class="mono">${esc(c.sizes.join(", "))}</span></div>`;
    const ins = S.cin.get(c.id) ?? [],
      outs = S.cout.get(c.id) ?? [];
    const ce = (x: CEdge, other: string, dir: string) => {
      const o = S.calcs.get(other)!;
      return `<div class="li" data-ce="${S.g!.calc_edges.indexOf(x)}"><span class="m">${dir}</span> <span class="mono"><b>${esc(o.sheet_id)}</b></span> <span class="m">${esc(o.title)}</span><span class="chip">${esc(x.rule)}</span><div class="why">${esc(x.labels.slice(0, 8).join(", "))}${x.labels.length > 8 ? "…" : ""}</div></div>`;
    };
    h +=
      `<h3>Fed by (${ins.length})</h3>` +
      (ins.map((x) => ce(x, x.src, "from")).join("") ||
        `<div class="li none">nothing found</div>`);
    h +=
      `<h3>Feeds (${outs.length})</h3>` +
      (outs
        .slice(0, 60)
        .map((x) => ce(x, x.dst, "to"))
        .join("") || `<div class="li none">nothing found</div>`);
    h += inspCalcExtra(c);
    h += `<h3>Elements linked to this page (${new Set(ls.map((l) => l.el)).size})</h3>`;
    h += ls.length
      ? ls
          .slice(0, 200)
          .map((l) => {
            const e = S.els.get(l.el)!;
            return `<div class="li" data-l="${esc(l.el)}|${esc(l.calc)}"><span class="mono"><b>${esc(e.text)}</b></span> <span class="m">${esc(e.sheet)} ${esc(e.grid)}</span><span class="chip ${tierCls(l.score)}">${Math.round(l.score * 100)}%</span><div class="why">${esc(l.tier)} - ${esc(l.rule)}</div></div>`;
          })
          .join("")
      : `<div class="li none">No drawn element is linked to this page.</div>`;
  }
  host.innerHTML = h;
  host.querySelectorAll<HTMLElement>("[data-ia]").forEach(
    (x) =>
      (x.onclick = (ev) => {
        ev.stopPropagation();
        inspActs[+x.dataset.ia!]();
      }),
  );
  host
    .querySelector<HTMLElement>("[data-open-el]")
    ?.addEventListener("click", () => single(elEv(S.els.get(S.sel!.id)!)));
  host
    .querySelector<HTMLElement>("[data-open-calc]")
    ?.addEventListener("click", () => single(calcEv(S.calcs.get(S.sel!.id)!)));
  host.querySelectorAll<HTMLElement>("[data-l]").forEach(
    (x) =>
      (x.onclick = () => {
        const [a, b] = x.dataset.l!.split("|");
        openLink(S.linksByEl.get(a)!.find((l) => l.calc === b)!);
      }),
  );
  host
    .querySelectorAll<HTMLElement>("[data-ee]")
    .forEach(
      (x) => (x.onclick = () => openEEdge(S.g!.element_edges[+x.dataset.ee!])),
    );
  host
    .querySelectorAll<HTMLElement>("[data-ce]")
    .forEach(
      (x) => (x.onclick = () => openCEdge(S.g!.calc_edges[+x.dataset.ce!])),
    );
}

function renderAll() {
  renderList();
  renderGraph();
  renderInsp();
}

// ---------------- wiring ----------------
document.querySelectorAll<HTMLButtonElement>("#ltabs button").forEach(
  (b) =>
    (b.onclick = () => {
      S.tab = b.dataset.t as typeof S.tab;
      renderList();
    }),
);
$("q").addEventListener("input", (e) => {
  S.q = (e.target as HTMLInputElement).value.trim().toLowerCase();
  renderList();
});
$("overviewBtn").onclick = () => {
  select(null, false);
  document.body.classList.remove("split", "split1");
};
$("closeSplit").onclick = () => {
  document.body.classList.remove("split", "split1");
  viewB.clear();
};
$("themeBtn").onclick = () => {
  const r = document.documentElement;
  const dark = r.dataset.theme
    ? r.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  r.dataset.theme = dark ? "light" : "dark";
};
window.addEventListener("hashchange", () => S.g && fromHash());
load().catch((e) => {
  $("graph").innerHTML =
    `<div class="empty">Could not load the drawing set: ${esc(e.message ?? e)}</div>`;
  console.error(e);
});

let lastW = 0;
new ResizeObserver(() => {
  const w = $("graph").clientWidth;
  if (S.g && Math.abs(w - lastW) > 20) {
    lastW = w;
    renderGraph();
  }
}).observe($("graphWrap2"));


// ---------------- 3D model built from the plans + 2021 calc-model overlay ----------------
const STATUS3D: Record<string, string> = { linked: "#1f9d63", "no calc found": "#d64545", "size mismatch": "#e0942f" };
const CALC3D = "#8e5bd9", CALC3D_GAP = "#d64545", MARK3D = "#e8590c", SEL3D = "#ffb000";
const FTM = 0.3048;
let viewer3d: Viewer | null = null;
let loaded3d = false;
const gidToEl = new Map<string, string>();
const ov = {
  grp: new THREE.Group(), // 2021 calc model, own coordinates
  mk: new THREE.Group(), // connection instance markers (drawn-model coordinates)
  recMesh: new Map<string, THREE.Mesh[]>(),
  instMesh: new Map<string, THREE.Mesh>(),
  place: "beside" as "beside" | "extents",
  calcOn: false,
};
function show3d(on: boolean) {
  $("tab3").classList.toggle("on", on);
  $("tabG").classList.toggle("on", !on);
  $("graphWrap2").hidden = on;
  ($("wrap3d") as HTMLElement).hidden = !on;
  const u = new URL(location.href);
  if (on) u.searchParams.set("view", "3d");
  else u.searchParams.delete("view");
  history.replaceState(null, "", u.toString());
  if (on) load3d();
}
async function load3d() {
  if (loaded3d || !S.g) return;
  loaded3d = true;
  viewer3d = new Viewer($("v3d"));
  (window as any).__calcgraph3d = viewer3d; // inspection hook for headless checks
  (window as any).__calcgraphOverlay = ov;
  for (const e of S.g.elements) if (e.model?.gid) gidToEl.set(e.model.gid, e.id);
  const prog = $("prog3d");
  try {
    // keep the IFC's own building coordinates so markers computed from the plans line up
    await viewer3d.load(`/api/sets/${S.sid}/model.ifc`, 1, (t, p) => (prog.textContent = p >= 100 ? "" : `${t} ${p}%`), false);
  } catch (err) {
    prog.textContent = `Could not load the 3D model: ${(err as Error).message}`;
    return;
  }
  const v = viewer3d;
  v.camera.position.sub(v.controls.target).multiplyScalar(1.6).add(v.controls.target);
  const m = (S.g as any).model ?? {};
  const assumed = S.g.elements.filter((e) => e.model?.in3d && (e.model.assumed ?? []).length).length;
  $("note3d").textContent = `${m.elements_in_3d ?? 0} of ${S.g.elements.length} drawing elements in 3D · ${assumed} with an assumed value`;
  if (S.ig) buildOverlay();
  legend3d();
  viewer3d.renderer.domElement.addEventListener("click", (ev) => {
    const v3 = viewer3d!;
    const dIfc = $("cbDrawn") && ($("cbDrawn") as HTMLInputElement).checked ? v3.pickDist(ev) : Infinity;
    const hOv = ov.grp.visible ? v3.hitExtra(ev, ov.grp.children.filter((o) => (o as THREE.Mesh).isMesh)) : null;
    const hMk = ov.mk.visible ? v3.hitExtra(ev, ov.mk.children) : null;
    const best = [
      { d: dIfc, f: () => { const gid = v3.pick(ev); const id = gid ? gidToEl.get(gid) : null; if (id) select({ kind: "el", id }); } },
      { d: hOv?.distance ?? Infinity, f: () => select({ kind: "rec", id: hOv!.object.userData.rec }) },
      // markers are small: let them win ties with the member they sit on
      { d: (hMk?.distance ?? Infinity) - 0.6, f: () => select({ kind: "cinst", id: hMk!.object.userData.inst }) },
    ].sort((a, b) => a.d - b.d)[0];
    if (best.d < Infinity) best.f();
  });
  paint3d(true);
}
function legend3d() {
  $("legend3d").innerHTML =
    Object.entries(STATUS3D).map(([k, c]) => `<div><i style="background:${c}"></i>drawn: ${esc(k)}</div>`).join("") +
    (S.ig ? `<div><i style="background:${MARK3D};border-radius:50%"></i>connection instance</div>` : "") +
    (ov.calcOn ? `<div><i style="background:${CALC3D};opacity:.6"></i>calc model 2021 (ghost)</div><div><i style="background:${CALC3D_GAP};opacity:.6"></i>calc member with an end not supported</div>` : "") +
    `<div><i style="background:${SEL3D}"></i>selected</div><div style="color:var(--muted)">click a member or marker: its evidence</div>`;
}
function ghostMat(color: string, op: number) {
  return new THREE.MeshBasicMaterial({ color, transparent: true, opacity: op, depthWrite: false });
}
function boxBetween(a: THREE.Vector3, b: THREE.Vector3, t: number, mat: THREE.Material) {
  const len = a.distanceTo(b);
  const m = new THREE.Mesh(new THREE.BoxGeometry(t, t, Math.max(len, 0.01)), mat);
  m.position.copy(a).add(b).multiplyScalar(0.5);
  m.lookAt(b);
  return m;
}
/** The 2021 RISAFloor model from the calc records, in its own plan feet and its own storeys.
 *  Oriented only so its grid numbering runs the same way as the drawings' (both negate: RISA Z
 *  runs from grid 1, X from grid E); where it sits is a placement choice, never a registration. */
function buildOverlay() {
  const o = S.ig!.overlay;
  const v = viewer3d!;
  const add = (rec: string, m: THREE.Mesh) => {
    m.userData.rec = rec;
    ov.grp.add(m);
    (ov.recMesh.get(rec) ?? ov.recMesh.set(rec, []).get(rec)!).push(m);
  };
  const P = (z: number, x: number, el: number) => new THREE.Vector3(-z * FTM, el * FTM, -x * FTM);
  for (const mb of o.members) add(mb.rec, boxBetween(P(mb.a[0], mb.a[1], mb.elev), P(mb.b[0], mb.b[1], mb.elev), 0.22, ghostMat(mb.absent_ends ? CALC3D_GAP : CALC3D, 0.55)));
  for (const c of o.columns) add(c.rec, boxBetween(P(c.z, c.x, c.bot), P(c.z, c.x, c.top), 0.28, ghostMat(CALC3D, 0.55)));
  // storey outlines at the calc's own elevations, so the height difference is visible
  const zs = o.columns.map((c) => c.z).concat(o.members.flatMap((m) => [m.a[0], m.b[0]]));
  const xs = o.columns.map((c) => c.x).concat(o.members.flatMap((m) => [m.a[1], m.b[1]]));
  const [z0, z1, x0, x1] = [Math.min(...zs), Math.max(...zs), Math.min(...xs), Math.max(...xs)];
  for (const el of Object.values(o.levels)) {
    const pts = [P(z0, x0, el), P(z1, x0, el), P(z1, x1, el), P(z0, x1, el), P(z0, x0, el)];
    const ln = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineDashedMaterial({ color: CALC3D, dashSize: 0.6, gapSize: 0.4 }));
    ln.computeLineDistances();
    ov.grp.add(ln);
  }
  ov.grp.visible = false;
  v.extra.add(ov.grp);
  for (const mk of S.ig!.conn_markers) {
    const s = new THREE.Mesh(new THREE.SphereGeometry(0.28, 12, 8), new THREE.MeshBasicMaterial({ color: MARK3D }));
    s.position.set(mk.pos[0], mk.pos[1], mk.pos[2]);
    s.userData.inst = mk.inst;
    ov.mk.add(s);
    ov.instMesh.set(mk.inst, s);
  }
  v.extra.add(ov.mk);
  placeOverlay();
  $("ctl3d").hidden = false;
  ($("cbMk") as HTMLInputElement).nextElementSibling!.textContent = ` Connection markers (${S.ig!.conn_markers.length})`;
}
function drawnBox() {
  const b = new THREE.Box3();
  viewer3d!.group.children.forEach((m) => b.expandByObject(m));
  return b;
}
function placeOverlay() {
  if (!viewer3d || !S.ig) return;
  ov.grp.position.set(0, 0, 0);
  ov.grp.updateMatrixWorld(true);
  const cb = new THREE.Box3();
  ov.grp.children.forEach((m) => cb.expandByObject(m));
  const db = drawnBox();
  if (cb.isEmpty() || db.isEmpty()) return;
  const cc = cb.getCenter(new THREE.Vector3()), dc = db.getCenter(new THREE.Vector3());
  // both share level 1 = 0 (the calc's base elevation 0, the drawings' datum 0'-0"): only plan offsets move
  if (ov.place === "extents") ov.grp.position.set(dc.x - cc.x, 0, dc.z - cc.z);
  else ov.grp.position.set(db.max.x + 8 - cb.min.x, 0, dc.z - cc.z);
  ov.grp.updateMatrixWorld(true);
  $("ban3d").innerHTML = banner();
  $("ban3d").querySelectorAll<HTMLElement>("[data-diff]").forEach((b) => (b.onclick = () => openDiff(+b.dataset.diff!)));
}
function banner() {
  const o = S.ig!.overlay;
  return `<b>2021 calc model - NOT registered to the drawings.</b> ` +
    (ov.place === "extents" ? `Overlaid by centring the two plan extents: a visual approximation, not a match.` : `Placed beside the drawn model, no alignment.`) +
    `<div>Differences, with evidence: ` + o.differences.map((d, i) => `<button class="sm" data-diff="${i}" title="${esc(d.text)}">${esc(d.what)}</button>`).join("") + `</div>` +
    `<details><summary>What this shows</summary>Drawn from the RISAFloor tables in its own plan coordinates and its own storeys (Level 2 ${o.levels["Level 2"]} ft, roof ${o.levels["Roof"]} ft), oriented only so its grid numbering runs the same way as the drawings'. Members that look aligned are not the same members. A column-position fit was tried and dropped (${esc(o.transform_dropped)}). Click a calc member for its record rows.</details>`;
}
function openDiff(i: number) {
  const d = S.ig!.overlay.differences[i];
  const c = mergeEv(d.calc), w = mergeEv(d.draw);
  const t = `<span class="chip bad">${esc(d.what)}</span> ${esc(d.text)}`;
  if (c.length && w.length) split(c[0], w[0], t);
  else openEvs([...c, ...w], t);
}
function fit3dAll() {
  const v = viewer3d!;
  const b = drawnBox();
  if (ov.grp.visible) ov.grp.children.forEach((m) => b.expandByObject(m));
  if (b.isEmpty()) return;
  const c = b.getCenter(new THREE.Vector3()), sz = b.getSize(new THREE.Vector3()).length();
  v.controls.target.copy(c);
  // far enough that the bounding sphere fits the narrower of the two view angles
  const half = THREE.MathUtils.degToRad(v.camera.fov / 2);
  const dist = (sz / 2) / Math.sin(Math.min(half, Math.atan(Math.tan(half) * v.camera.aspect)));
  v.camera.position.copy(c).add(new THREE.Vector3(0.75, 0.55, 0.9).normalize().multiplyScalar(dist * 0.95));
  v.camera.far = Math.max(v.camera.far, sz * 20);
  v.camera.updateProjectionMatrix();
}
function focusObjs(objs: THREE.Object3D[]) {
  const v = viewer3d!;
  const b = new THREE.Box3();
  objs.forEach((o) => b.expandByObject(o));
  if (b.isEmpty()) return;
  const c = b.getCenter(new THREE.Vector3()), off = v.camera.position.clone().sub(v.controls.target);
  v.controls.target.copy(c);
  v.camera.position.copy(c).add(off.setLength(Math.max(12, b.getSize(new THREE.Vector3()).length() * 4)));
}
function paint3d(focus = false) {
  if (!viewer3d || !loaded3d || !S.g) return;
  const drawnOn = ($("cbDrawn") as HTMLInputElement | null)?.checked ?? true;
  const selEl = S.sel?.kind === "el" ? S.sel.id : null;
  const selCalcEls = S.sel?.kind === "calc" ? new Set((S.linksByCalc.get(S.sel.id) ?? []).map((l) => l.el)) : null;
  const selRecEls = S.sel?.kind === "rec" ? new Set((S.rlByRec.get(S.sel.id) ?? []).map((l) => l.el)) : null;
  const inst = S.sel?.kind === "cinst" ? S.cinst.get(S.sel.id) : null;
  const typ = S.sel?.kind === "ctype" ? S.ctypes.get(S.sel.id) : null;
  const connEls = inst ? new Set(inst.attached.map((a) => a.id)) : typ ? new Set((typ.instances ?? []).flatMap((i) => S.cinst.get(i)?.attached.map((a) => a.id) ?? [])) : null;
  const group = selCalcEls ?? selRecEls ?? connEls;
  for (const e of S.g.elements) {
    const m = e.model;
    if (!m?.gid) continue;
    const dim = (selEl && e.id !== selEl) || (group && !group.has(e.id));
    viewer3d.style(m.gid, STATUS3D[m.status3d ?? ""] ?? "#9aa5b1", dim ? 0.18 : 1, drawnOn, e.id === selEl || !!group?.has(e.id));
  }
  // calc model: highlight the selected record's members
  const selRec = S.sel?.kind === "rec" ? S.sel.id : null;
  for (const [rid, ms] of ov.recMesh)
    for (const mesh of ms) {
      const mat = mesh.material as THREE.MeshBasicMaterial;
      const om = S.ig!.overlay.members.find((x) => x.rec === rid);
      mat.color.set(rid === selRec ? SEL3D : om?.absent_ends ? CALC3D_GAP : CALC3D);
      mat.opacity = rid === selRec ? 1 : selRec ? 0.25 : 0.55;
    }
  const selInsts = new Set<string>(inst ? [inst.id] : typ ? typ.instances ?? [] : selEl ? (S.instByEl.get(selEl) ?? []).map((i) => i.id) : []);
  for (const [iid, mesh] of ov.instMesh) {
    (mesh.material as THREE.MeshBasicMaterial).color.set(selInsts.has(iid) ? SEL3D : MARK3D);
    mesh.scale.setScalar(selInsts.has(iid) ? 1.8 : 1);
  }
  if (!focus) return;
  if (selEl) {
    const g = S.els.get(selEl)?.model?.gid;
    if (g) viewer3d.focus(g);
  } else if (selRec && ov.grp.visible && ov.recMesh.has(selRec)) focusObjs(ov.recMesh.get(selRec)!);
  else if (inst && ov.instMesh.has(inst.id)) focusObjs([ov.instMesh.get(inst.id)!]);
}
$("tabG").onclick = () => show3d(false);
$("tab3").onclick = () => show3d(true);
$("cbDrawn").onchange = () => paint3d();
$("cbMk").onchange = (e) => ((ov.mk.visible = (e.target as HTMLInputElement).checked), paint3d());
$("cbCalc").onchange = (e) => {
  ov.calcOn = (e.target as HTMLInputElement).checked;
  ov.grp.visible = ov.calcOn;
  ($("ban3d") as HTMLElement).hidden = !ov.calcOn;
  ($("placeRow") as HTMLElement).hidden = !ov.calcOn;
  legend3d();
  placeOverlay();
  fit3dAll();
  paint3d();
};
document.querySelectorAll<HTMLInputElement>("input[name=place]").forEach(
  (r) =>
    (r.onchange = () => {
      ov.place = r.value as typeof ov.place;
      placeOverlay();
      fit3dAll();
    }),
);
if (new URLSearchParams(location.search).get("view") === "3d") {
  const wait = setInterval(() => {
    if (S.g) {
      clearInterval(wait);
      show3d(true);
    }
  }, 100);
}
