// Page list sidebar: every page of the open document, each expandable to the links found on it.
// Clicking a page (label or title) goes to it; the caret only expands/collapses. Clicking a link row shows that
// link where it sits in this window's PDF (the element on the drawing, or the calc box on the calc page) – it does
// not follow the link to the other viewer.
import { linksForElement, sourceName, pct, esc } from "./data.js";

const store = {
  get(k, d) { try { const v = localStorage.getItem("calcviewer." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("calcviewer." + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};

/** Rows for each page: [{band, from, to, pct, at}] – `at` says where the link sits on that page:
 *  drawings: {page, el, occ, link?}   calcs: {page, calc, span, link?} */
function linksByPage(D, mode, docId) {
  const pages = new Map();
  const els = new Map(); // page -> element count (drawings)
  pages.els = els;
  const add = (p, row, key) => {
    const list = pages.get(p) || (pages.set(p, []), pages.get(p));
    if (!list.some((r) => r.key === key)) list.push({ ...row, key });
  };
  if (mode === "drawings") {
    for (const e of D.elements) {
      const links = linksForElement(D, e);
      const from = `${e.tag}${e.grid ? " · " + e.grid : ""}`;
      e.occurrences.forEach((o, occ) => {
        if (o.doc !== docId) return;
        const at = { page: o.page, el: e.id, occ };
        els.set(o.page, (els.get(o.page) || 0) + 1);
        for (const r of e.refs || []) add(o.page, { band: "none", from, to: r.detail ? `→ Detail ${e.fields.detail}/${r.sheet} ${r.title || ""}` : `→ Detail sheet ${r.sheet}`, pct: "", ref: true, at: { ...at, ref: r.sheet } }, `${e.id}|${occ}|ref|${r.sheet}`);
        for (const l of links) add(o.page, { band: l.band, from, to: `→ ${D.calc[l.calc].title} (${l.role})`, pct: pct(l.confidence), at: { ...at, link: l.id } }, `${e.id}|${occ}|${l.id}`);
        if (!links.length && !(e.refs || []).length && e.type !== "detail") add(o.page, { band: "none", from, to: "→ no calc found", pct: "", none: true, at }, `${e.id}|${occ}|none`);
      });
    }
  } else {
    for (const c of D.calcs.filter((c) => c.doc === docId)) {
      const links = (D.linksByCalc[c.id] || []).slice().sort((a, b) => b.confidence - a.confidence);
      c.spans.forEach((s, span) => {
        for (const r of s.regions) {
          const at = { page: r.page, calc: c.id, span };
          for (const l of links) add(r.page, { band: l.band, from: c.title, to: `→ ${sourceName(D, l.source)} (${l.role})`, pct: pct(l.confidence), at: { ...at, link: l.id } }, l.id);
          if (!links.length) add(r.page, { band: "none", from: c.title, to: "→ no drawing linked", pct: "", none: true, at }, c.id + "|none");
        }
      });
    }
  }
  return pages;
}

export function buildPageNav(host, D, mode, docId, { goToPage, showLink, app, toggleBtn }) {
  const doc = D.doc[docId];
  const byPage = linksByPage(D, mode, docId);
  const onlyLinked = store.get("nav.onlyLinked", mode === "calcs");
  // calc links only: callout -> detail-view rows are navigation, not calc links
  const nLinks = (rows) => rows.filter((r) => !r.none && !r.ref).length;
  const total = [...byPage.values()].reduce((n, l) => n + nLinks(l), 0);

  host.innerHTML = `
    <div class="nav-head"><b>Pages</b><span class="empty" style="font-size:12px" title="${mode === "drawings" ? "grey count = elements, outlined = calc links" : ""}">${doc.pages.length} pages · ${total} calc links</span>
      <button class="tool" data-act="hide" title="Collapse the page list">«</button></div>
    <div class="nav-tools"><button data-act="expand">Expand all</button><button data-act="collapse">Collapse all</button>
      <label><input type="checkbox" data-act="only" ${onlyLinked ? "checked" : ""}> with links only</label></div>
    <div class="nav-list"></div>`;
  const list = host.querySelector(".nav-list");

  const render = (only) => {
    list.innerHTML = doc.pages.map((p) => {
      const rows = byPage.get(p.page) || [];
      if (only && !rows.length) return "";
      const label = mode === "drawings" ? p.label || `p. ${p.page}` : `p. ${p.page}`;
      const title = mode === "drawings" ? p.title || "" : p.label ? `Sheet ${p.label}` : "";
      const n = nLinks(rows);
      const ne = byPage.els.get(p.page) || 0;
      const counts = `${mode === "drawings" && ne ? `<span class="cnt el-cnt" title="${ne} elements on this page">${ne}</span>` : ""}${n ? `<span class="cnt" title="${n} calc links">${n}</span>` : ""}`;
      const items = rows.map((r, i) => `<li class="${r.none ? "none" : ""}" data-i="${i}" title="Show this on the page"><span class="dot b-${r.band}"></span><span class="txt"><span class="from">${esc(r.from)}</span><span class="to" title="${esc(r.to)}">${esc(r.to)}</span></span><span class="pct">${r.pct}</span></li>`).join("");
      return `<details class="pg-item${rows.length ? "" : " empty-page"}" data-page="${p.page}">
        <summary title="Go to ${esc(label)}"><span class="caret" title="Show / hide links"></span><span class="pgl">${esc(label)}</span><span class="pgt">${esc(title)}</span>${counts}</summary>
        ${rows.length ? `<ul class="pg-links">${items}</ul>` : ""}</details>`;
    }).join("") || `<div class="empty" style="padding:12px">No pages with links.</div>`;
    setCurrent(current, false);
  };

  // page click navigates (and opens); caret click only toggles
  list.addEventListener("click", (ev) => {
    const li = ev.target.closest(".pg-links li");
    if (li) {
      const row = byPage.get(+li.closest(".pg-item").dataset.page)[+li.dataset.i];
      list.querySelectorAll(".pg-links li.on").forEach((x) => x.classList.remove("on"));
      li.classList.add("on");
      showLink?.(row.at);
      return;
    }
    const sum = ev.target.closest("summary");
    if (!sum) return;
    const det = sum.parentElement;
    if (ev.target.closest(".caret")) return; // default toggle
    ev.preventDefault();
    if (!det.classList.contains("empty-page")) det.open = true;
    goToPage(+det.dataset.page);
  });

  host.querySelector(".nav-tools").addEventListener("click", (ev) => {
    const act = ev.target.dataset.act;
    if (act === "expand" || act === "collapse") list.querySelectorAll(".pg-item:not(.empty-page)").forEach((d) => (d.open = act === "expand"));
  });
  host.querySelector("[data-act=only]").addEventListener("change", (ev) => { store.set("nav.onlyLinked", ev.target.checked); render(ev.target.checked); });

  // collapse / expand the whole sidebar
  const setShown = (shown) => { app.classList.toggle("no-nav", !shown); store.set("nav.shown", shown); toggleBtn?.classList.toggle("on", shown); };
  host.querySelector("[data-act=hide]").addEventListener("click", () => setShown(false));
  if (toggleBtn) toggleBtn.onclick = () => setShown(app.classList.contains("no-nav"));
  setShown(store.get("nav.shown", true));

  let current = 1;
  function setCurrent(p, scroll = true) {
    current = p;
    list.querySelectorAll(".pg-item.cur").forEach((d) => d.classList.remove("cur"));
    const d = list.querySelector(`.pg-item[data-page="${p}"]`);
    if (!d) return;
    d.classList.add("cur");
    if (scroll && !host.matches(":hover")) {
      const r = d.getBoundingClientRect(), lr = list.getBoundingClientRect();
      if (r.top < lr.top || r.bottom > lr.bottom) list.scrollTop += r.top - lr.top - lr.height / 3;
    }
  }
  render(onlyLinked);
  /** Clear the highlighted row (e.g. when something else is selected on the page). */
  const clearRow = () => list.querySelectorAll(".pg-links li.on").forEach((x) => x.classList.remove("on"));
  return { setCurrent, clearRow };
}
