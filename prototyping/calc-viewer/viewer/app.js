// Drawing viewer (drawings.html) and calc viewer (calcs.html, one tab per calc PDF).
// Left: page list. Centre: this window's PDF with clickable items. Right: sidebar for the selected item.
// Following a link opens the *other* viewer (reusing it if it's already open) at the linked bounding box;
// arriving here from the other viewer draws that box on this window's PDF.
import { loadData, linksForElement, bestBand, bestDesign, sourceName, calcStops, drawingStops, refStops, stopLabel, pageLabel, pct, esc } from "./data.js";
import { PdfPane } from "./pdfpane.js";
import { makeStepper } from "./stepper.js";
import { buildPageNav } from "./pagenav.js";
import { serveViewer, openViewer, routeLinks } from "./windows.js";

const mode = document.body.dataset.mode; // "drawings" | "calcs"
const other = mode === "drawings" ? "calcs" : "drawings";
const $ = (s, r = document) => r.querySelector(s);
const app = $(".app");
const side = $("#side");

let D;
try { D = await loadData(); }
catch (e) { side.innerHTML = `<section><div class="flag">Could not load data: ${esc(e.message)}. Run the build script and serve the repo root over HTTP (see README).</div></section>`; throw e; }
$("#built").textContent = `data built ${D.meta.builtAt.replace("T", " ")} · matcher ${D.meta.matcher}`;

const src = new PdfPane($("#src .pages"), { onPage: () => srcBar() });
const state = { srcDoc: mode === "drawings" ? "plans" : "calcs", sel: null, arrival: null, params: {} };
const visited = new Map();
const visitSet = (key) => (visited.has(key) ? visited.get(key) : visited.set(key, new Set()).get(key));
const linkById = (id) => D.links.find((l) => l.id === id) || null;
const docKind = (docId) => D.doc[docId].kind; // "drawings" | "calcs"

// ------------------------------------------------------------------ bars, tabs, page list
let pageNav = null;
function srcBar() {
  const doc = D.doc[state.srcDoc];
  const p = src.currentPage();
  const lab = pageLabel(D, doc.id, p);
  $("#src .sub").textContent = `p. ${p} / ${doc.pages.length}${lab ? " · " + lab : ""}`;
  const sel = $("#src-jump");
  if (sel && document.activeElement !== sel) sel.value = String(p);
  pageNav?.setCurrent(p);
}

function buildNav() {
  pageNav = buildPageNav($("#pagenav"), D, mode, state.srcDoc, {
    app, toggleBtn: $("#nav-toggle"),
    goToPage: (p) => { src.scrollTo(p, [0, 0, 1, 0], { smooth: false, topMargin: 10 }); srcBar(); },
    showLink: (at) => showLinkHere(at),
  });
  pageNav.setCurrent(src.currentPage(), false);
}

function buildTabs() {
  const host = $("#doctabs");
  if (!host) return;
  const docs = D.documents.filter((d) => d.kind === "calcs");
  host.innerHTML = docs.map((d) => {
    const n = D.calcs.filter((c) => c.doc === d.id).length;
    return `<button role="tab" data-doc="${d.id}" class="${d.id === state.srcDoc ? "on" : ""}" aria-selected="${d.id === state.srcDoc}">${esc(d.title)}<span class="cnt">${d.pages.length} pp · ${n} calcs</span></button>`;
  }).join("");
  host.querySelectorAll("[data-doc]").forEach((b) => b.addEventListener("click", () => { if (b.dataset.doc !== state.srcDoc) openSrcDoc(b.dataset.doc); }));
}

function buildSrcBar() {
  const bar = $("#src .pane-bar");
  const doc = D.doc[state.srcDoc];
  const scoped = new Set(D.elements.map((e) => e.sheet));
  const opts = doc.pages.map((p) => {
    const inScope = mode === "drawings" && scoped.has(p.label);
    const text = mode === "drawings" ? `${p.label}${p.title ? " – " + p.title : ""}${inScope ? "  ●" : ""}` : `p. ${p.page}${p.label ? " · " + p.label : ""}`;
    return `<option value="${p.page}">${esc(text)}</option>`;
  }).join("");
  bar.innerHTML = `<button id="nav-toggle" title="Show / hide the page list">☰</button><span class="title">${esc(doc.title)}</span><span class="sub"></span><span class="grow"></span>
    <button data-act="back" title="Scroll back to the linked box" hidden>↺ Box</button>
    <select id="src-jump" title="Go to page">${opts}</select>
    <button data-z="-1" title="Zoom out">−</button><button data-z="0" title="Fit width">Fit</button><button data-z="1" title="Zoom in">+</button>`;
  $("#src-jump").addEventListener("change", (e) => src.scrollTo(+e.target.value, [0, 0, 1, 0], { smooth: false, topMargin: 10 }));
  bar.querySelectorAll("[data-z]").forEach((b) => b.addEventListener("click", () => {
    const z = +b.dataset.z;
    src.setZoom(z === 0 ? 1 : src.zoom * (z > 0 ? 1.4 : 1 / 1.4));
  }));
  $("[data-act=back]", bar).addEventListener("click", () => state.arrival && scrollToStop(state.arrival.stop));
  srcBar();
}

async function openSrcDoc(docId, page) {
  state.srcDoc = docId;
  await src.open(D.doc[docId].file, docId);
  buildTabs();
  buildSrcBar();
  buildNav();
  paintSource();
  if (state.arrival?.stop.doc === docId) paintArrival(state.arrival.stop, state.arrival.link);
  else { src.setLayer("arrival", []); src.setLayer("marks", []); }
  if (page) src.scrollTo(page, [0, 0, 1, 0], { smooth: false, topMargin: 10 });
}

// ------------------------------------------------------------------ this window's items
function paintSource() {
  const items = [];
  if (mode === "drawings") {
    for (const e of D.elements) {
      const links = linksForElement(D, e);
      const band = bestBand(links);
      const best = bestDesign(links);
      const tip = `${e.tag}${e.grid ? " · grid " + e.grid : ""} — ${best ? `design calc ${pct(best.confidence)} (${best.band})` : "no design calc found"}${links.length ? ` · ${links.length} link${links.length > 1 ? "s" : ""}` : ""}${e.refs?.length ? " · detail sheet " + e.refs[0].sheet : ""}`;
      e.occurrences.forEach((o, k) => {
        if (o.doc !== state.srcDoc) return;
        items.push({
          page: o.page, rect: o.rect, title: tip, attrs: { id: e.id, occ: k },
          cls: `el b-${band}${e.type === "callout" ? " callout" : ""}`,
          on: { click: (ev) => { ev.stopPropagation(); select({ kind: "element", id: e.id, occ: k }); } },
        });
      });
    }
  } else {
    for (const c of D.calcs.filter((c) => c.doc === state.srcDoc)) {
      const band = bestBand(D.linksByCalc[c.id] || []);
      c.spans.forEach((s, si) => {
        const n = s.regions.length;
        const lab = stopLabel(D, { doc: c.doc, regions: s.regions });
        s.regions.forEach((r, ri) => items.push({
          page: r.page, rect: r.rect, attrs: { calc: c.id, span: si },
          cls: `span b-${band}${ri < n - 1 ? " cont-down" : ""}${ri > 0 ? " cont-up" : ""}`,
          html: ri === 0
            ? `<div class="strip">${esc(c.title)}${s.title && s.title !== c.title ? " — " + esc(s.title) : ""} · ${esc(lab.pg)}</div>`
            : `<div class="strip">continued (${lab.a}–${lab.b})</div>`,
          on: { click: (ev) => { ev.stopPropagation(); select({ kind: "calc", id: c.id, span: si }); } },
        }));
      });
    }
  }
  src.setLayer("items", items);
  markSourceSelection();
}

function markSourceSelection() {
  const id = state.sel?.id;
  if (mode === "drawings") src.nodes("items").forEach((n) => n.classList.toggle("sel", n.dataset.id === id));
  else src.nodes("items").forEach((n) => n.classList.toggle("sel", n.dataset.calc === id));
  if (mode === "calcs") {
    const links = state.sel?.kind === "calc" ? D.linksByCalc[id] || [] : [];
    const items = [];
    links.forEach((l) => l.hits.filter((h) => h.doc === state.srcDoc).forEach((h) => items.push({
      page: h.page, rect: h.rect, cls: "hit", title: `${h.text} → ${sourceName(D, l.source)} (click to open it in the drawing viewer)`,
      attrs: { link: l.id },
      on: { click: (ev) => { ev.stopPropagation(); const card = side.querySelector(`.linkcard[data-link="${CSS.escape(l.id)}"]`); card?._stepper?.go((card._stepper.index ?? -1) + 1); card?.scrollIntoView({ block: "nearest", behavior: "smooth" }); } },
    })));
    src.setLayer("hits", items);
  }
}

// ------------------------------------------------------------------ arrival box (a link from the other viewer)
function paintArrival(stop, link) {
  const lab = stopLabel(D, stop);
  const n = stop.regions.length;
  const band = link ? `b-${link.band}` : "b-none";
  src.setLayer("arrival", stop.regions.map((r, i) => ({
    page: r.page, rect: r.rect,
    cls: `tbox ${band}${i === 0 ? " first" : ""}${i === n - 1 ? " last" : ""}${i > 0 && i < n - 1 ? " mid" : ""}${r.fullPage ? " full" : ""}`,
    html: i === 0
      ? `<div class="tlabel"><span class="pg">${esc(lab.short)}</span>${link ? `<span class="conf ${band}" data-why>${pct(link.confidence)} · why?</span>` : ""}<span class="x" data-clear title="Clear this box">×</span></div>`
      : `<div class="ttag">continued (${lab.a}–${lab.b})</div>`,
  })));
  const first = src.nodes("arrival")[0];
  first?.querySelector("[data-clear]")?.addEventListener("click", (ev) => { ev.stopPropagation(); clearArrival(); });
  first?.querySelector("[data-why]")?.addEventListener("click", (ev) => {
    ev.stopPropagation();
    const open = first.querySelector(".why");
    if (open) { open.remove(); return; }
    const w = document.createElement("div");
    w.className = "why";
    w.innerHTML = whyHtml(link);
    w.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) w.remove(); });
    first.appendChild(w);
  });
  const pages = new Set(stop.regions.map((r) => r.page));
  const marks = [];
  if (link && stop.kind === "calc") {
    link.hits.filter((h) => h.doc === stop.doc && h.span === stop.span).forEach((h) => marks.push({ page: h.page, rect: h.rect, cls: "hit", title: h.text }));
  }
  if (link) {
    link.rationale.evidence.filter((e) => e.dest?.rect && e.dest.doc === stop.doc && pages.has(e.dest.page)).forEach((e) =>
      marks.push({ page: e.dest.page, rect: [e.dest.rect[0], e.dest.rect[1]], point: true, cls: "mark", html: String(e.n), title: e.note || e.kind }));
  }
  src.setLayer("marks", marks);
  $("#src [data-act=back]").hidden = false;
}

function clearArrival() {
  state.arrival = null;
  src.setLayer("arrival", []);
  src.setLayer("marks", []);
  $("#src [data-act=back]").hidden = true;
}

function scrollToStop(stop) {
  const r0 = stop.regions[0];
  if (docKind(stop.doc) === "drawings" && !r0.fullPage) src.scrollTo(r0.page, r0.rect, { zoomFor: 0.16, maxZoom: 5, smooth: false, topMargin: src.scroller.clientHeight * 0.4 });
  else if (docKind(stop.doc) === "drawings") { src.setZoom(1, false); src.scrollTo(r0.page, r0.rect, { smooth: false, topMargin: 10 }); }
  else src.scrollTo(r0.page, r0.rect, { smooth: false, topMargin: 64 });
}

async function arrive(stop, link) {
  if (stop.doc !== state.srcDoc) await openSrcDoc(stop.doc);
  state.arrival = { stop, link };
  paintArrival(stop, link);
  scrollToStop(stop);
  srcBar();
}

/** Show params in this window: {el, occ, link} | {sheet} | {calc, span, link} | {doc, page, rect, link} */
async function show(p) {
  state.params = p;
  const link = p.link ? linkById(p.link) : null;
  if (mode === "drawings" && p.el && D.el[p.el]) {
    const e = D.el[p.el];
    const occ = Math.min(+p.occ || 0, e.occurrences.length - 1);
    const o = e.occurrences[occ];
    await select({ kind: "element", id: e.id, occ }, { keepArrival: true });
    await arrive({ kind: "drawing", doc: o.doc, regions: [{ page: o.page, rect: o.rect }] }, link);
  } else if (mode === "drawings" && p.sheet) {
    const page = D.doc.plans.pages.find((x) => x.label === p.sheet)?.page;
    if (page) await arrive({ kind: "sheet", doc: "plans", regions: [{ page, rect: [0.005, 0.005, 0.995, 0.995], fullPage: true }] }, null);
  } else if (mode === "calcs" && p.calc && D.calc[p.calc]) {
    const c = D.calc[p.calc];
    const span = Math.min(+p.span || 0, c.spans.length - 1);
    if (c.doc !== state.srcDoc) await openSrcDoc(c.doc);
    await select({ kind: "calc", id: c.id, span }, { keepArrival: true });
    await arrive({ kind: "calc", doc: c.doc, span, regions: c.spans[span].regions }, link);
  } else if (p.doc && D.doc[p.doc] && docKind(p.doc) === (mode === "drawings" ? "drawings" : "calcs") && p.page) {
    const rect = String(p.rect || "0,0,1,1").split(",").map(Number);
    await arrive({ kind: "point", doc: p.doc, regions: [{ page: +p.page, rect }] }, link);
  }
  writeUrl();
}

// ------------------------------------------------------------------ a page-list link row: show it here, don't follow it
function flash(nodes) {
  src.scroller.querySelectorAll(".ov.flash").forEach((n) => n.classList.remove("flash"));
  nodes.forEach((n) => { void n.offsetWidth; n.classList.add("flash"); });
}

async function showLinkHere(at) {
  const onPage = (n) => +n.closest(".page")?.dataset.page === at.page;
  if (mode === "drawings") {
    const e = D.el[at.el];
    const o = e.occurrences[at.occ];
    await select({ kind: "element", id: e.id, occ: at.occ }, { fromNav: true });
    src.scrollTo(o.page, o.rect, { zoomFor: 0.16, maxZoom: 5, smooth: false, topMargin: src.scroller.clientHeight * 0.4 });
    setTimeout(() => flash(src.nodes("items").filter((n) => n.dataset.id === e.id && +n.dataset.occ === at.occ)), 60);
  } else {
    const c = D.calc[at.calc];
    await select({ kind: "calc", id: c.id, span: at.span }, { fromNav: true });
    // the evidence text for this link on this page if there is any, otherwise the calc's box on this page
    const hits = at.link ? (linkById(at.link)?.hits || []).filter((h) => h.doc === state.srcDoc && h.page === at.page) : [];
    const region = c.spans[at.span].regions.find((r) => r.page === at.page) || c.spans[at.span].regions[0];
    const target = hits[0]?.rect || region.rect;
    src.scrollTo(at.page, target, { smooth: false, topMargin: hits.length ? src.scroller.clientHeight * 0.35 : 50 });
    setTimeout(() => flash(hits.length
      ? src.nodes("hits").filter((n) => n.dataset.link === at.link && onPage(n))
      : src.nodes("items").filter((n) => n.dataset.calc === c.id && +n.dataset.span === at.span && onPage(n))), 60);
  }
  srcBar();
  // point at the matching link card in the sidebar (without following it)
  const key = at.ref ? "ref:" + at.el : at.link;
  const card = key && side.querySelector(`.linkcard[data-link="${CSS.escape(key)}"]`);
  side.querySelectorAll(".linkcard.active").forEach((x) => x.classList.remove("active"));
  if (card) {
    card.classList.add("active");
    const det = card.querySelector("details");
    if (det) det.open = true;
    card.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

// ------------------------------------------------------------------ following a link (to the other window)
function follow(stop, link) {
  if (stop.kind === "sheet") return show({ sheet: stop.sheet }); // a drawing sheet: stays in this window
  const params = stop.kind === "calc"
    ? { calc: link.calc, span: stop.span, link: link.id }
    : { el: stop.elId, occ: stop.occ, link: link.id };
  return openViewer(stop.kind === "calc" ? "calcs" : "drawings", params);
}

// ------------------------------------------------------------------ sidebar
function whyHtml(link) {
  const ev = link.rationale.evidence.map((e) => `<li><span class="n${e.weight < 0 ? " neg" : ""}">${e.n}</span><span>${esc(e.note || e.kind)}</span><span class="w">${e.weight > 0 ? "+" : ""}${e.weight.toFixed(2)}</span></li>`).join("");
  const cav = link.rationale.caveats.length ? `<ul class="caveats">${link.rationale.caveats.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : "";
  return `<div style="display:flex;gap:8px;align-items:center;margin-bottom:6px"><span class="badge b-${link.band}">${pct(link.confidence)} ${link.band}</span><b style="flex:1">Why this link</b><button class="tool" data-close>×</button></div>
    <div>${esc(link.rationale.summary)}</div><ul class="evid">${ev}</ul>${cav}${provHtml(link)}`;
}

function provHtml(link) {
  const p = link.provenance;
  return `<div class="prov">Found by ${esc(p.method)} (matcher ${esc(p.matcher)}, ${esc(p.at)}) · summary by ${esc(p.summaryBy)} · ${p.reviewed ? "reviewed " + esc(p.reviewed) : "not yet reviewed"}</div>`;
}

function kv(rows) {
  return `<dl class="kv">${rows.filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>`;
}

function linkCard({ key, title, sub, link, stops, label, chipText, opensIn }) {
  const card = document.createElement("div");
  card.className = "linkcard";
  card.dataset.link = key;
  const badge = link ? `<span class="badge b-${link.band}">${pct(link.confidence)} ${link.band}</span>` : `<span class="chip">${esc(chipText || "")}</span>`;
  card.innerHTML = `<div class="head"><div class="t">${esc(title)}${sub ? `<div class="empty" style="font-weight:400;font-size:12px">${esc(sub)}</div>` : ""}</div>${badge}</div>
    <div class="stp"></div>${opensIn ? `<div class="opens">${esc(opensIn)}</div>` : ""}`;
  const st = makeStepper({
    count: stops.length, visited: visitSet(key), label: (i) => label(stops[i]),
    onGo: (i) => {
      side.querySelectorAll(".linkcard.active").forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      follow(stops[i], link);
    },
  });
  card._stepper = st;
  $(".stp", card).appendChild(st.el);
  if (link) {
    const r = link.rationale;
    const ev = r.evidence.map((e) => {
      const nav = e.dest?.rect || e.origin?.rect;
      return `<li class="${nav ? "nav" : ""}" data-n="${e.n}" title="${nav ? "Show this evidence" : ""}"><span class="n${e.weight < 0 ? " neg" : ""}">${e.n}</span><span>${esc(e.note || e.kind)}</span><span class="w">${e.weight > 0 ? "+" : ""}${e.weight.toFixed(2)}</span></li>`;
    }).join("");
    card.insertAdjacentHTML("beforeend", `<div class="summary">${esc(r.summary)}</div>
      <details><summary>Evidence (${r.evidence.length})${r.caveats.length ? ` · ${r.caveats.length} caveat${r.caveats.length > 1 ? "s" : ""}` : ""}</summary>
      <ul class="evid">${ev}</ul>${r.caveats.length ? `<ul class="caveats">${r.caveats.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}${provHtml(link)}</details>`);
    card.querySelectorAll(".evid li.nav").forEach((li) => li.addEventListener("click", async () => {
      const e = r.evidence.find((x) => x.n === +li.dataset.n);
      const where = e.dest?.rect ? e.dest : e.origin;
      const here = docKind(where.doc) === (mode === "drawings" ? "drawings" : "calcs");
      if (!here) { openViewer(other, { doc: where.doc, page: where.page, rect: where.rect.join(","), link: link.id }); return; }
      if (where.doc !== state.srcDoc) await openSrcDoc(where.doc);
      src.scrollTo(where.page, where.rect, docKind(where.doc) === "drawings" ? { zoomFor: 0.16, maxZoom: 5, smooth: false, topMargin: src.scroller.clientHeight * 0.4 } : { topMargin: 80 });
      setTimeout(() => {
        src.nodes("marks").concat(src.nodes("hits"), src.nodes("items"))
          .filter((n) => n.textContent === String(e.n) || n.title?.startsWith(where.text))
          .forEach((n) => { n.classList.remove("flash"); void n.offsetWidth; n.classList.add("flash"); });
      }, 350);
    }));
  }
  return card;
}

function renderSide() {
  side.innerHTML = "";
  const sel = state.sel;
  if (!sel) {
    side.innerHTML = mode === "drawings"
      ? `<section><h2>Drawings → calcs</h2><p>Click any highlighted element on the drawing. The sidebar lists the calcs it links to. Following a link opens the <b>calc viewer</b> window at that calc's bounding box, or reuses it if it's already open.</p>
         <p><span class="badge b-high">high</span> <span class="badge b-medium">medium</span> <span class="badge b-low">low</span> <span class="badge b-none">no calc</span> — box colour shows the best design link's confidence. Dashed circles are detail callouts.</p>
         <p class="empty">In scope: ${[...new Set(D.elements.map((e) => e.sheet))].join(", ")} (marked ● in the sheet list).</p></section>`
      : `<section><h2>Calcs → drawings</h2><p>Click a calc box on the page. The sidebar lists the drawn elements it designs. Following a link opens the <b>drawing viewer</b> window at that element, or reuses it if it's already open. Yellow marks are the text that supports a link.</p>
         <p class="empty">Each calc PDF has its own tab above the page.</p></section>`;
    return;
  }
  if (sel.kind === "element") renderElementSide(D.el[sel.id], sel.occ ?? 0);
  else renderCalcSide(D.calc[sel.id], sel.span ?? 0);
}

function renderElementSide(e, occIdx) {
  const links = linksForElement(D, e);
  const g = e.group ? D.group[e.group] : null;
  const s1 = document.createElement("section");
  s1.innerHTML = `<h3>${esc(e.type)}</h3><h2>${esc(e.tag)}</h2>
    ${kv([["Grid", esc(e.grid)], ["Sheet", esc(e.sheet)], ["View", esc(e.view)], ["Level", esc(e.level)],
      ["IFC", e.ifc ? `<code>${esc(e.ifc.class)}${e.ifc.predefinedType ? "." + esc(e.ifc.predefinedType) : ""}</code>` : ""],
      ["Typical group", g && g.members.length > 1 ? `${esc(g.title)} · ${g.members.length} members` : ""], ["ID", `<code>${esc(e.id)}</code>`]])}`;
  side.appendChild(s1);
  if (e.occurrences.length > 1) {
    const s = document.createElement("section");
    s.innerHTML = `<h3>On the drawings</h3>`;
    const st = makeStepper({ count: e.occurrences.length, index: occIdx, visited: visitSet("occ:" + e.id), label: (i) => `${e.occurrences[i].sheet} · ${e.occurrences[i].view}`,
      onGo: (i) => { const o = e.occurrences[i]; src.scrollTo(o.page, o.rect, { zoomFor: 0.16, maxZoom: 5, smooth: false, topMargin: src.scroller.clientHeight * 0.4 }); } });
    s.appendChild(st.el);
    side.appendChild(s);
  }
  const s2 = document.createElement("section");
  s2.innerHTML = `<h3>Linked calcs (${links.length})</h3>`;
  if (e.refs?.length) {
    s2.appendChild(linkCard({ key: "ref:" + e.id, title: `Detail sheet ${e.refs[0].sheet}`, sub: e.refs[0].title, stops: refStops(D, e), chipText: "callout",
      label: (s) => stopLabel(D, s).short, opensIn: "Opens in this window" }));
  }
  if (!links.some((l) => l.role === "design")) s2.insertAdjacentHTML("beforeend", `<div class="flag">No design calc found for this element. ${e.type === "callout" ? "No calc names this detail." : "No calc in the packages sizes this member on this level."} Flagged for review.</div>`);
  for (const l of links) {
    const c = D.calc[l.calc];
    s2.appendChild(linkCard({
      key: l.id, link: l, stops: calcStops(D, l), title: c.title,
      sub: `${l.role}${l.source.kind === "group" ? " · via typical group" : ""} · ${c.sheetRange ? "sheets " + c.sheetRange : D.doc[c.doc].title}`,
      label: (s) => `${stopLabel(D, s).short}${s.title && s.title !== c.title ? " · " + s.title : ""}`,
      opensIn: `Opens in the calc viewer ↗ (${c.doc === "stair" ? "stair & parapet" : "calc package"} tab)`,
    }));
  }
  side.appendChild(s2);
}

function renderCalcSide(c, spanIdx) {
  const links = (D.linksByCalc[c.id] || []).slice().sort((a, b) => b.confidence - a.confidence);
  const s1 = document.createElement("section");
  const f = c.fields;
  s1.innerHTML = `<h3>${esc(c.category)}</h3><h2>${esc(c.title)}</h2>
    ${c.description ? `<p>${esc(c.description)}</p>` : ""}
    ${kv([["Sheets", esc(c.sheetRange || "–")], ["PDF pages", `${c.pageRange[0]}–${c.pageRange[1]}`], ["Document", esc(D.doc[c.doc].title)],
      ["Software", esc(f.software)], ["Level", esc(f.level)], ["Grids", esc(f.gridSystem || (f.grids || []).join(", "))],
      ["Sizes", esc((f.sizes || []).slice(0, 14).join(", ") + ((f.sizes || []).length > 14 ? " …" : ""))],
      ["Detail refs", esc((f.detailRefs || []).join(", "))], ["ID", `<code>${esc(c.id)}</code>`]])}`;
  side.appendChild(s1);
  const sp = document.createElement("section");
  sp.innerHTML = `<h3>In this PDF (${c.spans.length} part${c.spans.length > 1 ? "s" : ""})</h3>`;
  const spanStops = c.spans.map((s, i) => ({ doc: c.doc, regions: s.regions, title: s.title, span: i }));
  const st = makeStepper({ count: spanStops.length, index: spanIdx, visited: visitSet("span:" + c.id), label: (s) => `${stopLabel(D, spanStops[s]).short}${spanStops[s].title ? " · " + spanStops[s].title : ""}`,
    onGo: (i) => { const r = spanStops[i].regions[0]; src.scrollTo(r.page, r.rect, { topMargin: 50 }); } });
  sp.appendChild(st.el);
  side.appendChild(sp);
  const s2 = document.createElement("section");
  s2.innerHTML = `<h3>On the drawings (${links.length} link${links.length === 1 ? "" : "s"})</h3>`;
  if (!links.length) s2.insertAdjacentHTML("beforeend", `<div class="flag">No drawn element is linked to this calc yet.</div>`);
  for (const l of links) {
    const stops = drawingStops(D, l);
    s2.appendChild(linkCard({
      key: l.id, link: l, stops, title: sourceName(D, l.source),
      sub: `${l.role} · ${l.source.kind === "group" ? `typical group, ${stops.length} places` : stops.length + " place" + (stops.length > 1 ? "s" : "")} on the drawings`,
      label: (s) => `${stopLabel(D, s).short} · ${s.title}`, opensIn: "Opens in the drawing viewer ↗",
    }));
  }
  side.appendChild(s2);
}

// ------------------------------------------------------------------ selection + URL
async function select(sel, { keepArrival = false, fromNav = false } = {}) {
  state.sel = sel;
  if (!fromNav) pageNav?.clearRow();
  if (!keepArrival) { clearArrival(); state.params = sel.kind === "element" ? { el: sel.id, occ: sel.occ } : { calc: sel.id, span: sel.span }; }
  if (sel.kind === "calc" && D.calc[sel.id].doc !== state.srcDoc) await openSrcDoc(D.calc[sel.id].doc);
  markSourceSelection();
  renderSide();
  writeUrl();
}

function writeUrl() {
  const p = new URLSearchParams(Object.entries(state.params || {}).filter(([, v]) => v !== undefined && v !== null && v !== ""));
  if (!p.toString()) p.set("doc", state.srcDoc);
  try { history.replaceState(null, "", "?" + p.toString()); } catch { /* some browsers refuse this for file:// pages */ }
}

// ------------------------------------------------------------------ start
serveViewer(mode, (params) => show(params));
routeLinks();
const q = Object.fromEntries(new URLSearchParams(location.search));
if (mode === "drawings") {
  const start = D.doc.plans.pages.find((p) => p.label === "S2.0.3")?.page || 1;
  await openSrcDoc("plans", q.el || q.sheet || q.page ? null : start);
} else {
  const c = D.calc[q.calc];
  const docId = c ? c.doc : D.doc[q.doc]?.kind === "calcs" ? q.doc : "calcs";
  await openSrcDoc(docId);
  if (!c && !q.page) { const first = D.calcs.find((x) => x.doc === state.srcDoc); if (first) src.scrollTo(first.spans[0].regions[0].page, [0, 0, 1, 0], { smooth: false, topMargin: 10 }); }
}
renderSide();
if (q.el || q.sheet || q.calc || q.page) await show(q);
