// Element index: List, Hierarchy and Connections tabs over the same data.
import { loadData, linksForElement, bestBand, bestDesign, sourceName, calcStops, pct, esc, byConf, isMember } from "./data.js";
import { routeLinks } from "./windows.js";

const $ = (s, r = document) => r.querySelector(s);
const D = await loadData();
$("#built").textContent = `data built ${D.meta.builtAt.replace("T", " ")} · matcher ${D.meta.matcher}`;

const BAND_ORDER = { high: 3, medium: 2, low: 1, none: 0 };
const worst = (bands) => bands.reduce((w, b) => (BAND_ORDER[b] < BAND_ORDER[w] ? b : w), "high");
// Link attributes: a real href (middle-click / new tab still work) plus data-open, which routeLinks() uses to
// show the item in an already-open viewer window, or open one.
const viewerLink = (kind, params) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null)).toString();
  return `href="${kind}.html?${esc(qs)}" data-open="${kind}" data-params="${esc(qs)}"`;
};
const elUrl = (e, occ = 0) => viewerLink("drawings", { el: e.id, occ });
const calcUrl = (c, l) => viewerLink("calcs", { calc: c.id, span: l ? calcStops(D, l)[0]?.span ?? 0 : 0, link: l?.id });
const sheetUrl = (sheet) => viewerLink("drawings", { sheet });
const ZONES = ["Foundation", "Level 2", "Roof", "Moment frames", "Exterior walls", "Details & callouts"];
const zoneRank = (z) => (ZONES.indexOf(z) + 1 || 99);
const sheetKey = (s) => s.replace(/\d+/g, (d) => d.padStart(3, "0")); // S4.0.10 after S4.0.9

const rows = D.elements.map((e) => {
  const links = linksForElement(D, e);
  return { e, links, band: bestBand(links), sys: e.system, zone: e.zone };
});

// ------------------------------------------------------------------ stats
{
  const linked = rows.filter((r) => r.links.length).length;
  const members = rows.filter((r) => isMember(r.e));
  const review = members.filter((r) => r.band === "low" || r.band === "none").length;
  const linkedCalcs = new Set(D.links.map((l) => l.calc)).size;
  $("#stats").innerHTML = [
    [members.length, `members on ${(D.meta.memberSheets || []).length} sheets`],
    [rows.length - members.length, `callouts & detail views on ${D.doc.plans.pages.length} sheets`],
    [linked, "linked to a calc"],
    [review, "need review (low / no calc)"],
    [`${linkedCalcs} / ${D.calcs.length}`, "calcs linked"],
    [D.links.length, "links"],
  ].map(([n, t]) => `<div class="stat"><b>${n}</b><span>${esc(t)}</span></div>`).join("");
}

// ------------------------------------------------------------------ tabs
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
function setTab(t) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === t));
  for (const n of ["list", "tree", "graph"]) $("#tab-" + n).hidden = n !== t;
  try { history.replaceState(null, "", "#" + t); } catch { /* file:// */ }
}

function calcLinksHtml(links) {
  if (!links.length) return `<span class="empty">–</span>`;
  return `<div class="calclinks">${links.map((l) => {
    const c = D.calc[l.calc];
    return `<a ${calcUrl(c, l)} title="${esc(l.rationale.summary)}"><span class="dot b-${l.band}"></span><span class="mono">${pct(l.confidence)}</span><span class="t">${esc(c.title)}</span><span class="chip">${esc(c.sheetRange || "p. " + c.pageRange.join("–"))}</span></a>`;
  }).join("")}</div>`;
}

// ------------------------------------------------------------------ list
const LIST = { q: "", type: "", level: "", band: "", sheet: "", sys: "", sort: "sheet", dir: 1 };
function renderList() {
  const types = [...new Set(rows.map((r) => r.e.type))].sort();
  const levels = (D.meta.levels || []).filter((l) => rows.some((r) => r.e.level === l));
  const sheets = [...new Set(rows.map((r) => r.e.sheet))].sort((a, b) => (sheetKey(a) < sheetKey(b) ? -1 : 1));
  const systems = [...new Set(rows.map((r) => r.sys))].sort();
  const host = $("#tab-list");
  if (!host.dataset.ready) {
    host.innerHTML = `<div class="filters">
      <input id="f-q" type="search" placeholder="Search tag, grid, id…" style="min-width:220px">
      <select id="f-type"><option value="">All types</option>${types.map((t) => `<option>${t}</option>`).join("")}</select>
      <select id="f-level"><option value="">All levels</option>${levels.map((t) => `<option>${t}</option>`).join("")}</select>
      <select id="f-sheet"><option value="">All sheets</option>${sheets.map((t) => `<option>${t}</option>`).join("")}</select>
      <select id="f-sys"><option value="">All systems</option>${systems.map((t) => `<option>${esc(t)}</option>`).join("")}</select>
      <select id="f-band"><option value="">Any confidence</option><option value="review">Needs review (members, low / none)</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option><option value="none">No calc</option></select>
      <span class="empty" id="f-count"></span></div>
      <table class="list"><thead><tr>
        <th data-s="tag">Element</th><th data-s="type">Type</th><th data-s="grid">Level · grid</th><th data-s="sheet">Sheet · view</th><th data-s="band">Best link</th><th>Calcs</th><th>Drawings</th>
      </tr></thead><tbody></tbody></table>`;
    host.dataset.ready = 1;
    $("#f-q").addEventListener("input", (e) => { LIST.q = e.target.value.toLowerCase(); renderList(); });
    $("#f-type").addEventListener("change", (e) => { LIST.type = e.target.value; renderList(); });
    $("#f-level").addEventListener("change", (e) => { LIST.level = e.target.value; renderList(); });
    $("#f-band").addEventListener("change", (e) => { LIST.band = e.target.value; renderList(); });
    $("#f-sheet").addEventListener("change", (e) => { LIST.sheet = e.target.value; renderList(); });
    $("#f-sys").addEventListener("change", (e) => { LIST.sys = e.target.value; renderList(); });
    host.querySelectorAll("th[data-s]").forEach((th) => th.addEventListener("click", () => { LIST.dir = LIST.sort === th.dataset.s ? -LIST.dir : 1; LIST.sort = th.dataset.s; renderList(); }));
  }
  const key = { tag: (r) => r.e.tag, type: (r) => r.e.type, grid: (r) => r.e.level + (r.e.grid || ""), sheet: (r) => sheetKey(r.e.sheet) + r.e.view + (r.e.grid || ""), band: (r) => -(r.links[0]?.confidence ?? -1) }[LIST.sort];
  const list = rows.filter((r) =>
    (!LIST.q || `${r.e.tag} ${r.e.grid} ${r.e.id} ${r.e.view} ${r.e.fields.title || ""}`.toLowerCase().includes(LIST.q)) &&
    (!LIST.sheet || r.e.occurrences.some((o) => o.sheet === LIST.sheet)) && (!LIST.sys || r.sys === LIST.sys) &&
    (!LIST.type || r.e.type === LIST.type) && (!LIST.level || r.e.level === LIST.level) &&
    (!LIST.band || (LIST.band === "review" ? isMember(r.e) && (r.band === "low" || r.band === "none") : r.band === LIST.band))
  ).sort((a, b) => { const x = key(a), y = key(b); return (x < y ? -1 : x > y ? 1 : 0) * LIST.dir; });
  $("#f-count").textContent = `${list.length} of ${rows.length}`;
  $("#tab-list tbody").innerHTML = list.map(({ e, links, band }) => {
    const g = e.group ? D.group[e.group] : null;
    const r0 = e.refs?.[0];
    const drawings = `<a ${elUrl(e)}>${e.occurrences.length > 1 ? e.occurrences.length + " places" : "Open"}</a>${r0 ? ` · <a ${r0.detail ? elUrl(D.el[r0.detail]) : sheetUrl(r0.sheet)}>${r0.detail ? "detail view" : "sheet " + esc(r0.sheet)}</a>` : ""}`;
    return `<tr><td><b>${esc(e.tag)}</b>${e.type === "detail" ? `<div class="empty" style="font-size:11.5px">${esc(e.fields.title)}</div>` : ""}${g && g.members.length > 1 ? `<div class="empty" style="font-size:11.5px">typ. group ×${g.members.length}</div>` : ""}</td>
      <td>${esc(e.type)}</td><td class="mono">${esc(e.level)}${e.grid ? " · " + esc(e.grid) : ""}</td>
      <td>${esc(e.sheet)}<div class="empty" style="font-size:11.5px">${esc(e.view)}</div></td>
      <td><span class="badge b-${band}">${bestDesign(links) ? pct(bestDesign(links).confidence) + " " + band : isMember(e) ? "no design calc" : "no calc"}</span></td>
      <td>${calcLinksHtml(links)}</td><td>${drawings}</td></tr>`;
  }).join("");
}

// ------------------------------------------------------------------ hierarchy
function renderTree() {
  const tree = {};
  for (const r of rows) {
    const lv = (tree[r.zone] ??= {});
    const sy = (lv[r.sys] ??= {});
    const gk = r.e.type === "callout" ? "Callouts to " + r.e.fields.targetSheet : r.e.type === "detail" ? "Detail views on " + r.e.sheet : r.e.group || r.e.id;
    (sy[gk] ??= []).push(r);
  }
  const node = (label, items, inner, open = false, extra = "") => {
    const mem = items.filter((r) => isMember(r.e));
    const w = mem.length ? worst(mem.map((r) => r.band)) : items.some((r) => r.band !== "none") ? "high" : "none"; // annotations never make a node "needs review"
    const review = items.filter((r) => isMember(r.e) && (r.band === "low" || r.band === "none")).length;
    return `<details${open ? " open" : ""}><summary><span class="dot b-${w}"></span><span class="name">${esc(label)}</span><span class="cnt">${items.length} element${items.length > 1 ? "s" : ""}${review ? ` · ${review} need review` : ""}</span>${extra}</summary>${inner}</details>`;
  };
  const calcChips = (items) => {
    const best = new Map();
    items.flatMap((r) => r.links).forEach((l) => { if (!best.has(l.calc) || best.get(l.calc).confidence < l.confidence) best.set(l.calc, l); });
    return [...best.values()].sort(byConf).map((l) => `<a class="chip" ${calcUrl(D.calc[l.calc], l)} title="${esc(D.calc[l.calc].title)}"><span class="dot b-${l.band}"></span> ${esc(D.calc[l.calc].sheetRange || D.calc[l.calc].title)} ${pct(l.confidence)}</a>`).join(" ");
  };
  const all = rows;
  let html = node("Building 12", all, Object.entries(tree).sort((a, b) => zoneRank(a[0]) - zoneRank(b[0])).map(([lv, systems]) => {
    const lvItems = Object.values(systems).flatMap((s) => Object.values(s).flat());
    return node(lv, lvItems, Object.entries(systems).sort().map(([sys, groups]) => {
      const sysItems = Object.values(groups).flat();
      return node(sys, sysItems, Object.entries(groups).sort((a, b) => b[1].length - a[1].length).map(([gk, items]) => {
        const g = D.group[gk];
        const label = g && items.length > 1 ? `${g.size} (typ.) ×${items.length}` : items.length > 1 ? `${gk} ×${items.length}` : items[0].e.tag;
        const leaves = items.map((r) => `<div class="leaf"><span class="dot b-${r.band}"></span><a ${elUrl(r.e)}>${esc(r.e.tag)}</a><span class="cnt">${esc(r.e.type === "detail" ? r.e.fields.title : r.e.grid || r.e.view)}${r.e.occurrences.length > 1 ? ` · ${r.e.occurrences.length} places` : ""}</span></div>`).join("");
        return node(label, items, leaves, false, `<span style="margin-left:auto;display:flex;gap:4px;flex-wrap:wrap">${calcChips(items)}</span>`);
      }).join(""), false, `<span style="margin-left:auto;display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">${calcChips(sysItems).split("</a>").slice(0, 4).join("</a>")}${calcChips(sysItems).split("</a>").length > 5 ? " …" : ""}</span>`);
    }).join(""), false);
  }).join(""), true);
  $("#tab-tree").innerHTML = `<div class="legend"><span><span class="dot b-high"></span>high</span><span><span class="dot b-medium"></span>medium</span><span><span class="dot b-low"></span>low</span><span><span class="dot b-none"></span>no calc</span><span>Each node shows the weakest member link beneath it (callouts and detail views don't count), so problem areas stand out without opening everything. Top level: storeys, then the moment frames, exterior walls and details.</span></div><div class="tree">${html}</div>`;
}

// ------------------------------------------------------------------ connections
const nodesIndex = [
  ...D.groups.filter((g) => g.members.length > 1).map((g) => ({ kind: "group", id: g.id, label: g.title })),
  ...D.elements.map((e) => ({ kind: e.type === "detail" ? "detail" : "element", id: e.id, label: e.type === "detail" ? `${e.tag} ${e.fields.title}` : `${e.tag}${e.grid ? " · " + e.grid : ""}` })),
  ...D.calcs.map((c) => ({ kind: "calc", id: c.id, label: c.title })),
];
let focus = nodesIndex.find((n) => n.id === "detail/1-S4.0.1") || nodesIndex[0];

function neighbours(n) {
  // returns columns of {node, edge:{band,label}} relative to the focus
  const N = (kind, id) => nodesIndex.find((x) => x.kind === kind && x.id === id)
    || (kind === "element" && D.el[id]?.type === "detail" ? nodesIndex.find((x) => x.id === id) : null)
    || (kind === "group" && D.group[id]?.members.length === 1 ? nodesIndex.find((x) => x.kind === "element" && x.id === D.group[id].members[0]) : null)
    || { kind, id, label: D.group[id]?.title || id };
  const left = [], right = [], far = [];
  const linkEdge = (l) => ({ band: l.band, label: `${pct(l.confidence)} ${l.role}` });
  if (n.kind === "element" || n.kind === "group" || n.kind === "detail") {
    const el = n.kind !== "group" ? D.el[n.id] : null;
    const g = n.kind === "group" ? D.group[n.id] : el?.group && D.group[el.group].members.length > 1 ? D.group[el.group] : null;
    if (n.kind === "element" && g) left.push({ node: N("group", g.id), edge: { band: "none", label: "member of" } });
    if (n.kind === "group") g.members.slice(0, 7).forEach((id) => left.push({ node: N("element", id), edge: { band: "none", label: "" } }));
    if (n.kind === "group" && g.members.length > 7) left.push({ node: { kind: "more", id: "", label: `+${g.members.length - 7} more members` }, edge: { band: "none", label: "" } });
    if (el?.refs?.length) {
      const r = el.refs[0];
      left.push(r.detail ? { node: N("element", r.detail), edge: { band: "none", label: "points at" } }
        : { node: { kind: "sheet", id: r.sheet, label: `Sheet ${r.sheet} ${r.title || ""}` }, edge: { band: "none", label: "detail on" } });
    }
    if (n.kind === "detail") {
      const by = D.refBy[n.id] || [];
      by.slice(0, 6).forEach((c) => left.push({ node: N("element", c.id), edge: { band: "none", label: `called out ×${c.occurrences.length}` } }));
      const inView = D.elements.filter((x) => x.viewRef === `${el.fields.detail}/${el.sheet}` && isMember(x));
      if (inView.length) left.push({ node: { kind: "more", id: "", label: `${inView.length} members drawn in this view` }, edge: { band: "none", label: "contains" } });
    }
    const links = n.kind !== "group" ? linksForElement(D, el) : D.linksBySource[n.id] || [];
    links.forEach((l) => right.push({ node: N("calc", l.calc), edge: linkEdge(l) }));
    // second ring: what else those calcs cover
    const seen = new Set([n.id, el?.group].filter(Boolean));
    links.forEach((l) => (D.linksByCalc[l.calc] || []).forEach((o) => {
      if (seen.has(o.source.id) || far.length >= 9) return;
      seen.add(o.source.id);
      far.push({ node: N(o.source.kind, o.source.id), edge: linkEdge(o), from: l.calc });
    }));
  } else if (n.kind === "calc") {
    (D.linksByCalc[n.id] || []).slice().sort(byConf).slice(0, 10).forEach((l) => left.push({ node: N(l.source.kind, l.source.id), edge: linkEdge(l) }));
    const others = new Map();
    (D.linksByCalc[n.id] || []).forEach((l) => (D.linksBySource[l.source.id] || []).forEach((o) => { if (o.calc !== n.id && !others.has(o.calc)) others.set(o.calc, o); }));
    [...others.values()].forEach((o) => right.push({ node: N("calc", o.calc), edge: { band: o.band, label: "shares elements" } }));
  }
  return { left, right, far };
}

function renderGraph() {
  const host = $("#tab-graph");
  if (!host.dataset.ready) {
    host.innerHTML = `<div class="legend"><span>Shows only real relationships: typical-group membership, calc links (coloured by confidence), callouts pointing at detail views, and calcs that share elements. Click a node to move the focus to it.</span></div>
      <div class="graphwrap"><div class="pick"><input type="search" id="g-q" placeholder="Find element, group or calc…"><div id="g-list"></div></div><div><div class="graph" id="g-svg"></div><div id="g-open" style="margin-top:8px;display:flex;gap:8px"></div></div></div>`;
    host.dataset.ready = 1;
    $("#g-q").addEventListener("input", renderPick);
  }
  renderPick();
  const { left, right, far } = neighbours(focus);
  const W = 1040, colX = [16, 300, 584, 830], bw = 250, bh = 34, gap = 12;
  const colH = (n) => n * (bh + gap);
  const H = Math.max(420, colH(left.length), colH(right.length), colH(far.length), 120) + 40;
  const ys = (n) => { const tot = colH(n); return Array.from({ length: n }, (_, i) => (H - tot) / 2 + i * (bh + gap)); };
  const kindTag = { group: "GROUP", element: "ELEMENT", calc: "CALC", sheet: "SHEET", detail: "DETAIL VIEW", more: "" };
  const box = (node, x, y, cls = "") => {
    const lab = node.label.length > 34 ? node.label.slice(0, 33) + "…" : node.label;
    return `<g class="node ${cls}" data-kind="${node.kind}" data-id="${esc(node.id)}" transform="translate(${x},${y})"><title>${esc(node.label)}</title><rect width="${bw}" height="${bh}" rx="7"></rect>
      <text x="10" y="13" style="font-size:9.5px;fill:var(--muted)">${kindTag[node.kind] || ""}</text><text x="10" y="27">${esc(lab)}</text></g>`;
  };
  const edge = (x1, y1, x2, y2, e) => {
    const c = `var(--${e.band === "none" ? "line" : e.band})`;
    const mx = (x1 + x2) / 2;
    return `<path class="edge" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" stroke="${c}"></path>${e.label ? `<text class="elabel" x="${mx}" y="${(y1 + y2) / 2 - 4}" text-anchor="middle">${esc(e.label)}</text>` : ""}`;
  };
  let svg = "";
  const cy = H / 2 - bh / 2;
  const cx = left.length ? colX[1] : colX[0] + 140;
  const ly = ys(left.length), ry = ys(right.length);
  left.forEach((it, i) => { svg += edge(colX[0] + bw, ly[i] + bh / 2, cx, cy + bh / 2, it.edge); });
  const rx = cx + 284;
  right.forEach((it, i) => { svg += edge(cx + bw, cy + bh / 2, rx, ry[i] + bh / 2, it.edge); });
  const fx = rx + 284, fy = ys(far.length);
  far.forEach((it, i) => {
    const j = right.findIndex((r) => r.node.id === it.from);
    svg += edge(rx + bw, (ry[j] ?? cy) + bh / 2, fx, fy[i] + bh / 2, it.edge);
  });
  left.forEach((it, i) => { svg += box(it.node, colX[0], ly[i]); });
  right.forEach((it, i) => { svg += box(it.node, rx, ry[i]); });
  far.forEach((it, i) => { svg += box(it.node, fx, fy[i]); });
  svg += box(focus, cx, cy, "center");
  const width = Math.max(W, (far.length ? fx : right.length ? rx : cx) + bw + 20);
  $("#g-svg").innerHTML = `<svg width="${width}" height="${H}" viewBox="0 0 ${width} ${H}">${svg}</svg>${!left.length && !right.length ? `<div class="flag" style="margin:12px">No connections – this item has no calc link yet.</div>` : ""}`;
  $("#g-svg").querySelectorAll(".node").forEach((g) => g.addEventListener("click", () => {
    const k = g.dataset.kind, id = g.dataset.id;
    const n = nodesIndex.find((x) => x.kind === k && x.id === id);
    if (n) { focus = n; renderGraph(); }
  }));
  const open = [];
  if (focus.kind === "element" || focus.kind === "detail") open.push(`<a class="tool" ${elUrl(D.el[focus.id])}>Open in drawing viewer</a>`);
  if (focus.kind === "group") open.push(`<a class="tool" ${elUrl(D.el[D.group[focus.id].members[0]])}>Open first member in drawing viewer</a>`);
  if (focus.kind === "calc") open.push(`<a class="tool" ${calcUrl(D.calc[focus.id])}>Open in calc viewer</a>`);
  $("#g-open").innerHTML = open.join("");
}

function renderPick() {
  const q = ($("#g-q")?.value || "").toLowerCase();
  const list = nodesIndex.filter((n) => !q || n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)).slice(0, 200);
  const tag = { group: "G", element: "E", calc: "C", detail: "D" };
  $("#g-list").innerHTML = list.map((n) => `<div data-kind="${n.kind}" data-id="${esc(n.id)}" class="${n === focus ? "on" : ""}"><span class="chip">${tag[n.kind]}</span>${esc(n.label)}</div>`).join("");
  $("#g-list").querySelectorAll("div").forEach((d) => d.addEventListener("click", () => { focus = nodesIndex.find((x) => x.kind === d.dataset.kind && x.id === d.dataset.id); renderGraph(); }));
}

window.name = "bldg12-index"; // the viewers' "Element index" link reuses this window
routeLinks();
renderList();
renderTree();
renderGraph();
setTab(["list", "tree", "graph"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "list");
