// Loads the four JSON files and works out stepper stops from them.
const NAMES = ["documents", "elements", "groups", "calcs", "links"];

export async function loadData(base = "data/") {
  // the double-click build (viewers/) ships the data as a script that sets window.CALC_DATA
  const parts = window.CALC_DATA ? NAMES.map((n) => window.CALC_DATA[n]) : await Promise.all(
    NAMES.map((n) => fetch(base + n + ".json").then((r) => { if (!r.ok) throw new Error(`${n}.json: ${r.status}`); return r.json(); }))
  );
  const D = Object.fromEntries(NAMES.map((n, i) => [n, parts[i][n]]));
  D.meta = parts[0].meta;
  D.doc = Object.fromEntries(D.documents.map((d) => [d.id, d]));
  D.el = Object.fromEntries(D.elements.map((e) => [e.id, e]));
  D.group = Object.fromEntries(D.groups.map((g) => [g.id, g]));
  D.calc = Object.fromEntries(D.calcs.map((c) => [c.id, c]));
  // callouts that point at each detail view (for "called out from" and the Connections tab)
  D.refBy = {};
  for (const e of D.elements) for (const r of e.refs || []) if (r.detail) (D.refBy[r.detail] ??= []).push(e);
  D.linksBySource = {};
  D.linksByCalc = {};
  for (const l of D.links) {
    (D.linksBySource[l.source.id] ??= []).push(l);
    (D.linksByCalc[l.calc] ??= []).push(l);
  }
  return D;
}

export const byConf = (a, b) => b.confidence - a.confidence;

/** Links for an element: its own, plus its typical group's. */
export function linksForElement(D, el) {
  // design links first (they size the member), then loads/reference; each by confidence
  return [...(D.linksBySource[el.id] || []), ...(el.group ? D.linksBySource[el.group] || [] : [])]
    .sort((a, b) => (a.role === "design" ? 0 : 1) - (b.role === "design" ? 0 : 1) || byConf(a, b));
}

/** Colour/review status of an item: the best *design* link. A loads-only link doesn't count as being designed. */
export function bestBand(links) {
  const design = links.filter((l) => l.role === "design");
  if (!design.length) return "none";
  return design.slice().sort(byConf)[0].band;
}

export function bestDesign(links) {
  return links.filter((l) => l.role === "design").sort(byConf)[0] || null;
}

export function sourceName(D, src) {
  if (src.kind === "group") return D.group[src.id]?.title ?? src.id;
  return D.el[src.id]?.tag ?? src.id;
}

export function sourceElements(D, src) {
  return src.kind === "group" ? D.group[src.id].members.map((id) => D.el[id]) : [D.el[src.id]];
}

/** Calc-side stops for a link: the calc spans that hold evidence (all spans when there is none). */
export function calcStops(D, link) {
  const c = D.calc[link.calc];
  const withHits = new Set(link.hits.map((h) => h.span));
  let idx = c.spans.map((_, i) => i);
  if (withHits.size) idx = idx.filter((i) => withHits.has(i));
  return idx.map((i) => ({ kind: "calc", doc: c.doc, span: i, title: c.spans[i].title || c.title, regions: c.spans[i].regions, link }));
}

/** Drawing-side stops for a link: every place its element (or every member of its group) is drawn. */
export function drawingStops(D, link) {
  const occ = sourceElements(D, link.source).flatMap((e) => e.occurrences.map((o, k) => ({ ...o, el: e, k })));
  occ.sort((a, b) => a.page - b.page || a.rect[1] - b.rect[1] || a.rect[0] - b.rect[0]);
  return occ.map((o) => ({ kind: "drawing", doc: o.doc, title: `${o.el.tag}${o.el.grid ? " · " + o.el.grid : ""}`, regions: [{ page: o.page, rect: o.rect }], elId: o.el.id, occ: o.k, link }));
}

/** Stops for "go to the detail sheet" on a callout. */
export function refStops(D, el) {
  // a callout points at its detail view's region when the view was found, otherwise at the whole sheet
  return (el.refs || []).map((r) => ({ kind: "sheet", sheet: r.sheet, detail: r.detail || null, doc: r.doc,
    title: r.detail ? `${D.el[r.detail]?.tag || r.sheet} – ${r.title || ""}` : `${r.sheet} ${r.title || ""}`.trim(),
    regions: [r.rect ? { page: r.page, rect: r.rect } : { page: r.page, rect: [0.005, 0.005, 0.995, 0.995], fullPage: true }] }));
}

/** Scroll options that frame a drawing rect: small labels zoom in, whole views fit the pane. */
export function frameOpts(rect, paneH) {
  const w = rect[2] - rect[0];
  return w > 0.12 ? { zoomFor: 0.94, maxZoom: 5, smooth: false, topMargin: 34 } : { zoomFor: 0.16, maxZoom: 5, smooth: false, topMargin: paneH * 0.4 };
}

/** Is an element a drawn member (vs. a callout or detail view)? */
export const isMember = (e) => e.type !== "callout" && e.type !== "detail";
export const LEVELS = ["Foundation", "Level 2", "Roof", "Elevation", "Details"];

export function pageLabel(D, docId, page) {
  return D.doc[docId].pages[page - 1]?.label || null;
}

/** "Page 57" / "Pages 76–78", with sheet numbers when the pages have them. */
export function stopLabel(D, stop) {
  const pages = stop.regions.map((r) => r.page);
  const a = Math.min(...pages), b = Math.max(...pages);
  const la = pageLabel(D, stop.doc, a), lb = pageLabel(D, stop.doc, b);
  const pg = a === b ? `Page ${a}` : `Pages ${a}–${b}`;
  const sh = la ? (a === b || !lb || la === lb ? `${D.doc[stop.doc].kind === "drawings" ? "" : "Sheet "}${la}` : `Sheets ${la}–${lb}`) : "";
  return { pg, sh, short: sh ? `${sh} · ${a === b ? "p. " + a : "p. " + a + "–" + b}` : pg, a, b };
}

export const pct = (c) => Math.round(c * 100) + "%";
export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const ROLE = { design: "design", loads: "loads", reference: "reference" };
