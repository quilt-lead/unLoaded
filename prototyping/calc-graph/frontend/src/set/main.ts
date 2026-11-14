// Drawing-set view: elements read off the S-sheets, the calc graph of the calc package,
// evidence links between them. Every node, edge, link and finding opens the ORIGINAL
// PDF page zoomed to and highlighting the words that produced it.
import "../style.css";
import "./set.css";
import { PdfView, type Shown } from "./pdfview";

interface Ev {
  doc: string;
  page: number;
  rects: number[][];
  text: string;
  note?: string;
  sheet?: string;
  calc?: string;
  extra?: Ev[];
}
interface El {
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

type Sel = { kind: "el" | "calc"; id: string } | null;
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
  sel: null as Sel,
  tab: "el" as "el" | "calc" | "find",
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
  return `${ev.doc === "stair" ? "Stair calcs" : "Calc package"} · ${c ? `<b>${esc(c.sheet_id)}</b> ${esc(c.title)}` : ""} · PDF p${ev.page}`;
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
function single(ev: Ev) {
  document.body.classList.remove("split", "split1");
  viewB.clear();
  viewA.show(shown(ev));
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
  const r = await fetch(`/api/sets/${S.sid}/graph`);
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
  $("setName").textContent = g.name;
  pills();
  fromHash();
  renderAll();
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
    else single(calcEv(S.calcs.get(sel.id)!));
  }
  renderAll();
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
function fromHash() {
  const h = decodeURIComponent(location.hash.slice(1));
  const [k, v] = [h.slice(0, h.indexOf("=")), h.slice(h.indexOf("=") + 1)];
  if (k === "el" && S.els.has(v)) select({ kind: "el", id: v });
  else if (k === "calc" && S.calcs.has(v)) select({ kind: "calc", id: v });
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
  host.querySelectorAll<HTMLElement>("[data-find]").forEach(
    (x) =>
      (x.onclick = () => {
        const f = S.g!.findings[+x.dataset.find!];
        history.replaceState(null, "", `#find=${x.dataset.find}`);
        if (f.el) S.sel = { kind: "el", id: f.el };
        else if (f.calc) S.sel = { kind: "calc", id: f.calc };
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
function renderInsp() {
  const host = $("insp");
  if (!S.sel) {
    host.innerHTML = `<div class="ihint">Select an element, a calc page or a finding. Links show both sides' evidence side by side.</div>`;
    return;
  }
  let h = "";
  if (S.sel.kind === "el") {
    const e = S.els.get(S.sel.id)!;
    const ls = S.linksByEl.get(e.id) ?? [];
    h += `<div class="ih"><h2 class="mono">${esc(e.text)}</h2><span class="kind">${esc(e.type)} · ${esc(e.sheet)} ${esc(e.sheet_title)} · ${esc(e.level || "no level")} · grid ${esc(e.grid || "-")}${e.grid_node ? ` (on ${esc(e.grid_node)})` : ""}</span>
      <button class="sm" data-open-el>Show on sheet</button></div>`;
    const sch = e.params.schedule
      ? `<div class="kv">Schedule: <span class="mono">${esc(e.params.schedule)}</span></div>`
      : "";
    h += sch;
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
