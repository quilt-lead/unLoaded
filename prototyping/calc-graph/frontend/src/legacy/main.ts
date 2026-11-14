import "./style.css";
import {
  api,
  type Calc,
  type Element,
  type Impact,
  type Link,
  type State,
} from "./api";
import { renderGraph } from "./graph";
import { Viewer } from "../viewer";

const $ = <T extends HTMLElement = HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const esc = (s: unknown) =>
  String(s ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!,
  );
const CAT_COLORS: Record<string, string> = {
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
const STATUS_COLORS: Record<string, string> = {
  confirmed: "#1f9d63",
  review: "#e0942f",
  unmapped: "#d64545",
};
const GREY = "#c3cad3";
const TIER: Record<string, string> = {
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

type Sel = { kind: "el" | "calc"; id: string } | null;
const S = {
  st: null as State | null,
  els: new Map<string, Element>(),
  calcs: new Map<string, Calc>(),
  linksByEl: new Map<string, Link[]>(),
  linksByCalc: new Map<string, Link[]>(),
  sel: null as Sel,
  filter: null as string | null,
  colorBy: "calc",
  xray: false,
  level: "",
  tab: "3d" as "3d" | "graph",
  impact: null as Impact | null,
};
const viewer = new Viewer($("viewer"));

// ---------------- data ----------------
const live = (ls: Link[] | undefined) =>
  (ls ?? [])
    .filter((l) => l.status !== "rejected")
    .sort((a, b) => b.conf - a.conf);
const linksFor = (gid: string) => live(S.linksByEl.get(gid));
const linksOfCalc = (key: string) => live(S.linksByCalc.get(key));

function showError(e: unknown) {
  const box = $("err");
  box.textContent = e instanceof Error ? e.message : String(e);
  box.style.display = "block";
  setTimeout(() => (box.style.display = "none"), 8000);
  console.error(e);
}

let loadSeq = 0;
async function reload(focusModel = false) {
  const seq = ++loadSeq;
  const st = await api.state();
  if (seq !== loadSeq) return; // a newer reload started: drop this stale response
  S.st = st;
  S.els = new Map(st.elements.map((e) => [e.global_id, e]));
  S.calcs = new Map(st.calcs.map((c) => [c.key, c]));
  S.linksByEl = new Map();
  S.linksByCalc = new Map();
  for (const l of st.links) {
    (
      S.linksByEl.get(l.global_id) ??
      S.linksByEl.set(l.global_id, []).get(l.global_id)!
    ).push(l);
    (
      S.linksByCalc.get(l.calc_key) ??
      S.linksByCalc.set(l.calc_key, []).get(l.calc_key)!
    ).push(l);
  }
  if (S.sel?.kind === "el" && !S.els.has(S.sel.id)) S.sel = null;
  if (S.sel?.kind === "calc" && !S.calcs.has(S.sel.id)) S.sel = null;
  $("ifcName").textContent = st.model_rev
    ? `${st.model_rev.source_name} (rev ${st.model_rev.seq})`
    : "none";
  $("pdfName").textContent = st.calc_rev
    ? `${st.calc_rev.source_name} (rev ${st.calc_rev.seq}, ${st.pages.length} pp)`
    : "none";
  ($("exportBtn") as HTMLButtonElement).disabled = !st.run;
  ($("rev2Btn") as HTMLButtonElement).disabled = !st.model_rev;
  if (st.model_rev && viewer.loadedRev !== st.model_rev.id) {
    progress(true, "Loading model…", 10);
    await viewer.load(api.fileUrl(st.model_rev.id), st.model_rev.id, (t, p) =>
      progress(true, t, p),
    );
    levels();
  }
  progress(false);
  if (focusModel) viewer.fit();
  refresh();
}

// ---------------- painting ----------------
function paint() {
  const selCalc = S.sel?.kind === "calc" ? S.sel.id : null,
    selEl = S.sel?.kind === "el" ? S.sel.id : null;
  const imp = S.impact;
  for (const el of S.els.values()) {
    const ls = linksFor(el.global_id);
    let col =
      S.colorBy === "status"
        ? STATUS_COLORS[el.status]
        : S.colorBy === "cat"
          ? (CAT_COLORS[el.cat] ?? CAT_COLORS.Other)
          : ls.length
            ? S.calcs.get(ls[0].calc_key)!.color
            : GREY;
    let focus = true;
    if (imp) {
      focus =
        imp.removed.includes(el.global_id) ||
        imp.hit[el.global_id] !== undefined;
      if (imp.removed.includes(el.global_id)) col = "#d64545";
      else if (imp.hit[el.global_id] !== undefined) col = "#f0a050";
    } else if (selCalc) {
      focus = ls.some((l) => l.calc_key === selCalc);
      if (focus && S.colorBy === "calc") col = S.calcs.get(selCalc)!.color;
    } else if (S.filter) focus = el.status === S.filter;
    const visible = !S.level || el.storey === S.level;
    let op = focus ? (S.xray ? 0.55 : el.cat === "Slab" ? 0.45 : 1) : 0.07;
    if (selEl && el.global_id !== selEl && !selCalc && !imp)
      op = Math.min(op, S.xray ? 0.2 : 0.35);
    viewer.style(el.global_id, col, op, visible, el.global_id === selEl);
  }
  renderLegend();
  renderPills();
  if (S.tab === "graph") drawGraph();
}

function renderLegend() {
  let h = "";
  if (S.impact)
    h = `<div><i style="background:#d64545"></i>Removed / orphaned</div><div><i style="background:#f0a050"></i>On the impacted load path</div>`;
  else if (S.colorBy === "status")
    h = Object.entries({
      confirmed: "Linked (high confidence / confirmed)",
      review: "Needs review",
      unmapped: "No calc found",
    })
      .map(
        ([k, v]) =>
          `<div><i style="background:${STATUS_COLORS[k]}"></i>${v}</div>`,
      )
      .join("");
  else if (S.colorBy === "cat")
    h = [...new Set([...S.els.values()].map((e) => e.cat))]
      .map(
        (c) =>
          `<div><i style="background:${CAT_COLORS[c] ?? CAT_COLORS.Other}"></i>${c}</div>`,
      )
      .join("");
  else
    h =
      [...S.calcs.values()]
        .filter((c) => linksOfCalc(c.key).length)
        .map(
          (c) =>
            `<div><i style="background:${c.color}"></i>${esc(c.title)}</div>`,
        )
        .join("") +
      `<div><i style="background:${GREY}"></i>No calc found</div>`;
  $("legend").innerHTML = h;
  $("legend").style.display = S.els.size ? "" : "none";
}

function renderPills() {
  const st = S.st;
  if (!st || (!st.elements.length && !st.pages.length)) {
    $("pills").innerHTML = "";
    return;
  }
  const c = st.counts,
    linkedCalcs = [...S.calcs.values()].filter(
      (k) => linksOfCalc(k.key).length,
    ).length;
  const p = (k: string, cls: string, label: string, n: number) =>
    `<span class="pill ${cls} ${S.filter === k ? "on" : ""}" data-f="${k}"><b>${n}</b> ${label}</span>`;
  $("pills").innerHTML =
    `<span class="pill"><b>${st.elements.length}</b> model elements</span>` +
    `<span class="pill"><b>${st.edges.length}</b> load-path edges</span>` +
    `<span class="pill"><b>${st.calcs.length}</b> calcs in ${st.pages.length} pp</span>` +
    `<span class="pill"><b>${linkedCalcs}</b> calcs linked</span>` +
    `<span class="pill"><b>${st.calc_edges.length}</b> calc dependencies</span>` +
    p("confirmed", "good", "elements linked", c.confirmed ?? 0) +
    p("review", "warn", "need review", c.review ?? 0) +
    p("unmapped", "bad", "no calc found", c.unmapped ?? 0) +
    (st.model_rev
      ? `<span class="pill" title="Every upload is a revision">model rev <b>${st.model_rev.seq}</b> · calcs rev <b>${st.calc_rev?.seq ?? "-"}</b></span>`
      : "");
  $("pills")
    .querySelectorAll<HTMLElement>("[data-f]")
    .forEach(
      (x) =>
        (x.onclick = () => {
          S.filter = S.filter === x.dataset.f ? null : x.dataset.f!;
          S.sel = null;
          S.impact = null;
          refresh();
        }),
    );
}

function renderCalcList() {
  const calcs = [...S.calcs.values()];
  $("calcCount").textContent = calcs.length ? `${calcs.length} calcs` : "";
  if (!calcs.length) {
    $("calcList").innerHTML =
      `<div class="empty">Upload a calc package PDF, or press <b>Load sample</b>.</div>`;
    return;
  }
  const stale = S.impact?.stale ?? {};
  $("calcList").innerHTML = calcs
    .map((c) => {
      const ls = linksOfCalc(c.key),
        n = new Set(ls.map((l) => l.global_id)).size,
        rv = ls.filter((l) => l.conf < 0.8 && l.status === "auto").length;
      const pr =
        c.pages.length > 1
          ? `pp. ${c.pages[0]}-${c.pages[c.pages.length - 1]}`
          : `p. ${c.pages[0]}`;
      return `<div class="calc ${S.sel?.kind === "calc" && S.sel.id === c.key ? "sel" : ""}" data-c="${esc(c.key)}">
      <span class="sw" style="background:${n ? c.color : "transparent"};border:1px solid ${n ? c.color : "var(--line)"}"></span>
      <div><div class="t">${esc(c.title)}</div><div class="m">${pr}${c.software ? " · " + esc(c.software) : ""}</div>
      <div>${stale[c.key] ? `<span class="chip warn" title="${esc(stale[c.key])}">stale - re-run</span>` : ""}${c.front ? '<span class="chip">front matter - not mapped</span>' : n ? `<span class="chip good">${n} element${n > 1 ? "s" : ""}</span>` : `<span class="chip ${c.scanned ? "bad" : ""}">${c.scanned ? "no text - needs OCR" : "no elements"}</span>`}${rv ? `<span class="chip warn">${rv} to review</span>` : ""}${c.cat ? `<span class="chip">${c.cat}</span>` : ""}</div></div></div>`;
    })
    .join("");
  $("calcList")
    .querySelectorAll<HTMLElement>("[data-c]")
    .forEach(
      (x) =>
        (x.onclick = () =>
          select(
            S.sel?.kind === "calc" && S.sel.id === x.dataset.c
              ? null
              : { kind: "calc", id: x.dataset.c! },
          )),
    );
}

const confChip = (l: Link) => {
  const cls =
    l.status === "confirmed" || l.status === "manual"
      ? "good"
      : l.conf >= 0.8
        ? "good"
        : l.conf >= 0.5
          ? "warn"
          : "bad";
  const txt =
    l.status === "confirmed"
      ? "confirmed"
      : l.status === "manual"
        ? "linked by hand"
        : Math.round(l.conf * 100) + "%";
  return `<span class="conf chip ${cls}" style="margin:0 0 0 auto">${txt}</span>`;
};
const label = (e: Element) => e.mark || e.name || e.ifc_type;
const elist = (
  arr: Element[],
  extra: (e: Element) => string = (e) => `${esc(e.cat)} · ${esc(e.storey)}`,
) =>
  `<div class="elist">${arr
    .slice(0, 60)
    .map(
      (e) =>
        `<div data-e="${esc(e.global_id)}"><span>${esc(label(e))}</span><span style="color:var(--muted)">${extra(e)}</span></div>`,
    )
    .join(
      "",
    )}${arr.length > 60 ? `<div style="color:var(--muted)">+${arr.length - 60} more</div>` : ""}</div>`;

function renderImpact() {
  const imp = S.impact,
    box = $("impactBox");
  if (!imp) {
    box.innerHTML = "";
    return;
  }
  const el = S.els.get(imp.global_id);
  const hit = Object.entries(imp.hit).sort((a, b) => a[1] - b[1]);
  const stale = Object.entries(imp.stale);
  const nm = (g: string) => esc(S.els.get(g) ? label(S.els.get(g)!) : g);
  box.innerHTML = `<div class="impact"><h3>Impact · ${imp.mode === "remove" ? "remove" : "change"} ${esc(el ? label(el) : "")}</h3>
    <dl class="kv"><dt>Removed / orphaned</dt><dd>${imp.removed.length}</dd><dt>Elements on the load path</dt><dd>${hit.length} over ${imp.waves} waves</dd><dt>Calcs stale</dt><dd>${stale.length} of ${S.calcs.size}</dd></dl>
    <ul>${hit
      .slice(0, 12)
      .map(
        ([g, w]) =>
          `<li><b>${nm(g)}</b> <span class="why">wave ${w}${imp.why[g] ? " - " + esc(imp.why[g]) : " - load path from upstream"}</span></li>`,
      )
      .join(
        "",
      )}${hit.length > 12 ? `<li class="why">+${hit.length - 12} more</li>` : ""}</ul>
    <h3 style="margin-top:8px">Re-run queue</h3>
    <ul>${
      stale
        .map(([k, why]) => {
          const c = S.calcs.get(k);
          return `<li><b>${esc(c?.title ?? k)}</b>${c?.software ? ` <span class="chip warn">${esc(c.software)}</span>` : ""}<br><span class="why">${esc(why)}${c?.software === "Hand calc" || c?.scanned ? " · hand calc: flag for engineer, do not auto-replace" : ""}</span></li>`;
        })
        .join("") || '<li class="why">none</li>'
    }</ul>
    <div class="acts" style="margin-top:8px"><button id="impClear">Clear impact</button></div></div>`;
  $("impClear").onclick = () => {
    S.impact = null;
    refresh();
  };
}

function renderInsp() {
  renderImpact();
  const box = $("insp"),
    st = S.st;
  if (!st || (!st.elements.length && !st.calcs.length)) {
    box.innerHTML = `<div class="insp"><h2>Nothing loaded</h2><div class="kind">Upload an IFC model and a calc package PDF, or load the sample.</div></div>`;
    return;
  }
  if (!S.sel) {
    const els = [...S.els.values()];
    const review = els.filter((e) => e.status === "review"),
      un = els.filter((e) => e.status === "unmapped");
    const revs = st.revisions.slice().reverse();
    box.innerHTML = `<div class="insp"><h2>Mapping summary</h2><div class="kind">${esc(st.model_rev?.source_name ?? "no model")} ⇄ ${esc(st.calc_rev?.source_name ?? "no calc package")}${st.run ? ` · ${esc(st.run.engine_version)}` : ""}</div>
      <div class="kind">Click an element in the model or a calc on the left.</div>
      <h3>Needs review (${review.length})</h3>${review.length ? elist(review) : '<div class="kind">None</div>'}
      <h3>No calc found (${un.length})</h3>${un.length ? elist(un) : '<div class="kind">None</div>'}
      <h3>Elements without a mark</h3><div class="kind">${els.filter((e) => !e.mark).length} elements have no Mark property, so they can only link by size or type.</div>
      <h3>Revisions (${revs.length})</h3><div class="revs">${revs.map((r) => `<div><span>${r.kind === "model" ? "Model" : "Calcs"} rev ${r.seq}${r.id === st.model_rev?.id || r.id === st.calc_rev?.id ? " <b>(head)</b>" : ""} · ${esc(r.label ?? r.source_name)}</span><span style="color:var(--muted)">${esc(r.created_at.slice(5, 16).replace("T", " "))} ET</span></div>`).join("")}</div></div>`;
    box
      .querySelectorAll<HTMLElement>("[data-e]")
      .forEach(
        (x) =>
          (x.onclick = () => select({ kind: "el", id: x.dataset.e! }, true)),
      );
    return;
  }
  if (S.sel.kind === "calc") {
    const c = S.calcs.get(S.sel.id)!,
      ls = linksOfCalc(c.key);
    const groups: Record<string, [Element, Link][]> = {};
    ls.forEach((l) => {
      const el = S.els.get(l.global_id);
      if (el) (groups[l.tier] ??= []).push([el, l]);
    });
    const deps = st.calc_edges.filter((e) => e.dst === c.key),
      feeds = st.calc_edges.filter((e) => e.src === c.key);
    const toReview = ls.filter((l) => l.status === "auto" && l.conf < 0.8);
    box.innerHTML = `<div class="insp"><h2>${esc(c.title)}</h2><div class="kind">Calculation · ${c.pages.length > 1 ? `pp. ${c.pages[0]}-${c.pages[c.pages.length - 1]}` : `p. ${c.pages[0]}`}${c.software ? " · " + esc(c.software) : ""}${c.cat ? " · " + c.cat + "s" : ""}</div>
      <div class="acts"><button id="openPg">Open calc pages</button><button id="clrSel">Back to summary</button></div>
      ${c.scanned ? `<div class="snip" style="margin-top:12px">These pages have no text layer (scanned or handwritten), so nothing could be read from them. An OCR or vision pass would be needed to link them.</div>` : ""}
      ${c.front ? `<div class="snip" style="margin-top:12px">Front matter / contents page - never mapped.</div>` : ""}
      <h3>Takes input from (${deps.length})</h3>${deps.map((e) => `<div class="rule"><a href="#" data-c="${esc(e.src)}">${esc(S.calcs.get(e.src)?.title ?? e.src)}</a> - ${esc(e.rules.join("; "))}</div>`).join("") || '<div class="kind">None found</div>'}
      <h3>Feeds (${feeds.length})</h3>${feeds.map((e) => `<div class="rule"><a href="#" data-c="${esc(e.dst)}">${esc(S.calcs.get(e.dst)?.title ?? e.dst)}</a> - ${esc(e.rules.join("; "))}</div>`).join("") || '<div class="kind">None found</div>'}
      ${
        Object.entries(groups)
          .map(
            ([t, arr]) =>
              `<h3>${TIER[t] ?? t} (${arr.length})</h3>${elist(
                arr.map((x) => x[0]),
                (e) => {
                  const l = arr.find((x) => x[0] === e)![1];
                  return `${esc(e.cat)} · ${esc(e.storey)} · ${l.status === "confirmed" ? "confirmed" : Math.round(l.conf * 100) + "%"}`;
                },
              )}`,
          )
          .join("") ||
        (!c.scanned && !c.front
          ? '<h3>Elements</h3><div class="kind">No model elements matched this calc.</div>'
          : "")
      }
      ${toReview.length ? `<div class="acts" style="margin-top:12px"><button id="confAll">Confirm all ${toReview.length} to review</button></div>` : ""}</div>`;
    $("openPg").onclick = () => openPage(c.pages[0]);
    $("clrSel").onclick = () => select(null);
    const ca = document.getElementById("confAll");
    if (ca)
      ca.onclick = () =>
        act(
          Promise.all(
            toReview.map((l) => api.decide(l.global_id, l.calc_key, "confirm")),
          ),
        );
    box
      .querySelectorAll<HTMLElement>("[data-e]")
      .forEach(
        (x) =>
          (x.onclick = () => select({ kind: "el", id: x.dataset.e! }, true)),
      );
    box.querySelectorAll<HTMLElement>("a[data-c]").forEach(
      (x) =>
        (x.onclick = (ev) => {
          ev.preventDefault();
          select({ kind: "calc", id: x.dataset.c! });
        }),
    );
    return;
  }
  const el = S.els.get(S.sel.id)!,
    ls = linksFor(el.global_id),
    rejected = (S.linksByEl.get(el.global_id) ?? []).filter(
      (l) => l.status === "rejected",
    );
  const up = st.edges.filter((e) => e.dst === el.global_id),
    down = st.edges.filter((e) => e.src === el.global_id);
  const props = Object.entries(el.params).slice(0, 40);
  box.innerHTML = `<div class="insp"><h2>${esc(label(el))}</h2>
    <div class="kind">${esc(el.cat)} · ${esc(el.ifc_type)}${el.storey ? " · " + esc(el.storey) : ""}</div>
    <div class="acts"><button id="impChange">Impact if changed</button><button id="impRemove" class="danger">Impact if removed</button></div>
    <h3>Linked calcs (${ls.length})</h3>
    ${
      ls
        .map((l) => {
          const c = S.calcs.get(l.calc_key)!;
          return `<div class="link"><div class="top"><span class="sw" style="background:${c.color}"></span><span class="t" data-c="${esc(c.key)}">${esc(c.title)}</span>${confChip(l)}</div>
      <div class="rule" style="margin-top:4px">${esc(l.rule)}${l.page ? " · page " + l.page : ""}${c.software ? " · " + esc(c.software) : ""}${l.decided_at ? ` · decided ${esc(l.decided_at.slice(5, 16).replace("T", " "))} ET` : ""}</div>
      ${l.snippet ? `<div class="snip">${esc(l.snippet.before)}<mark>${esc(l.snippet.match)}</mark>${esc(l.snippet.after)}</div>` : ""}
      <div class="acts">${l.page ? `<button data-pg="${l.page}" data-k="${esc(c.key)}">Open page ${l.page}</button>` : ""}${l.status === "auto" ? `<button data-ok="${esc(c.key)}">Confirm</button>` : ""}<button data-rej="${esc(c.key)}">Reject</button></div></div>`;
        })
        .join("") ||
      `<div class="snip">No calc in the package names this element${el.mark ? ` ("${esc(el.mark)}")` : " (it has no Mark)"}, its size or its type.</div>`
    }
    <div class="acts" style="margin-top:4px"><select id="addCalc"><option value="">+ Link to a calc by hand…</option>${[
      ...S.calcs.values(),
    ]
      .filter((c) => !c.front && !ls.some((l) => l.calc_key === c.key))
      .map((c) => `<option value="${esc(c.key)}">${esc(c.title)}</option>`)
      .join("")}</select></div>
    ${rejected.length ? `<h3>Rejected</h3>${rejected.map((l) => `<div class="rule">${esc(S.calcs.get(l.calc_key)?.title)} <button data-undo="${esc(l.calc_key)}" style="padding:1px 7px;font-size:11px">undo</button></div>`).join("")}` : ""}
    <h3>Load path</h3><dl class="kv"><dt>Carries load from</dt><dd>${up.map((e) => `<a href="#" data-e2="${esc(e.src)}">${esc(S.els.get(e.src) ? label(S.els.get(e.src)!) : e.src)}</a>`).join(", ") || "-"}</dd>
      <dt>Delivers load to</dt><dd>${down.map((e) => `<a href="#" data-e2="${esc(e.dst)}" title="${esc(e.rule)}">${esc(S.els.get(e.dst) ? label(S.els.get(e.dst)!) : e.dst)}</a>`).join(", ") || "-"}</dd></dl>
    <h3>Element</h3><dl class="kv"><dt>Mark</dt><dd>${esc(el.mark || "-")}</dd><dt>Name</dt><dd>${esc(el.name || "-")}</dd><dt>Type</dt><dd>${esc(el.type_name || "-")}</dd><dt>Size</dt><dd>${esc(el.profile || "-")}</dd><dt>GlobalId</dt><dd class="mono" style="font-size:11px">${esc(el.global_id)}</dd></dl>
    ${props.length ? `<h3>Parameters (open set)</h3><dl class="kv">${props.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
    <div class="acts" style="margin-top:14px"><button id="clrSel">Back to summary</button></div></div>`;
  const g = el.global_id;
  box
    .querySelectorAll<HTMLElement>("[data-c]")
    .forEach(
      (x) => (x.onclick = () => select({ kind: "calc", id: x.dataset.c! })),
    );
  box.querySelectorAll<HTMLElement>("[data-pg]").forEach(
    (x) =>
      (x.onclick = () => {
        const l = ls.find((l) => l.calc_key === x.dataset.k)!;
        openPage(+x.dataset.pg!, l.rects);
      }),
  );
  box
    .querySelectorAll<HTMLElement>("[data-ok]")
    .forEach(
      (x) => (x.onclick = () => act(api.decide(g, x.dataset.ok!, "confirm"))),
    );
  box
    .querySelectorAll<HTMLElement>("[data-rej]")
    .forEach(
      (x) => (x.onclick = () => act(api.decide(g, x.dataset.rej!, "reject"))),
    );
  box
    .querySelectorAll<HTMLElement>("[data-undo]")
    .forEach(
      (x) => (x.onclick = () => act(api.decide(g, x.dataset.undo!, "undo"))),
    );
  box.querySelectorAll<HTMLElement>("a[data-e2]").forEach(
    (x) =>
      (x.onclick = (ev) => {
        ev.preventDefault();
        select({ kind: "el", id: x.dataset.e2! }, true);
      }),
  );
  ($("addCalc") as HTMLSelectElement).onchange = (e) => {
    const v = (e.target as HTMLSelectElement).value;
    if (v) act(api.decide(g, v, "manual"));
  };
  $("impChange").onclick = () => runImpact(g, "change");
  $("impRemove").onclick = () => runImpact(g, "remove");
  $("clrSel").onclick = () => select(null);
}

async function act(p: Promise<unknown>) {
  try {
    await p;
    await reload();
  } catch (e) {
    showError(e);
  }
}

async function runImpact(gid: string, mode: "change" | "remove") {
  try {
    S.impact = await api.impact(gid, mode);
    refresh();
  } catch (e) {
    showError(e);
  }
}

function drawGraph() {
  if (!S.st) return;
  renderGraph($("graphWrap"), {
    els: S.els,
    edges: S.st.edges,
    linksFor,
    calcs: S.st.calcs,
    calcEdges: S.st.calc_edges,
    sel: S.sel,
    impact: S.impact,
    onSelect: (sel) => select(sel, sel.kind === "el"),
  });
}

function refresh() {
  paint();
  renderCalcList();
  renderInsp();
}

function select(sel: Sel, focusCam = false) {
  S.sel = sel;
  if (sel) S.filter = null;
  refresh();
  if (focusCam && sel?.kind === "el" && S.tab === "3d") viewer.focus(sel.id);
}

// ---------------- page viewer ----------------
let dlgPage = 1,
  dlgRects: number[][] = [],
  dlgRectPage = 0;
function openPage(n: number, rects: number[][] = []) {
  const st = S.st;
  if (!st?.calc_rev) return;
  if (rects.length) {
    dlgRects = rects;
    dlgRectPage = n;
  } else if (n !== dlgRectPage) {
    dlgRects = [];
  }
  dlgPage = n;
  const dlg = $("pageDlg") as HTMLDialogElement;
  if (!dlg.open) dlg.showModal();
  const c = [...S.calcs.values()].find((c) => c.pages.includes(n));
  $("dlgTitle").textContent =
    `Page ${n} of ${st.pages.length}${c ? " · " + c.title : ""}`;
  const hl = n === dlgRectPage ? dlgRects : [];
  $("dlgBody").innerHTML =
    `<img class="pageimg" alt="Calc package page ${n}" src="${api.pageUrl(st.calc_rev.id, n, hl)}">`;
}
$("dlgClose").onclick = () => ($("pageDlg") as HTMLDialogElement).close();
$("dlgPrev").onclick = () => dlgPage > 1 && openPage(dlgPage - 1);
$("dlgNext").onclick = () =>
  S.st && dlgPage < S.st.pages.length && openPage(dlgPage + 1);

// ---------------- wiring ----------------
function progress(on: boolean, txt = "", pct = 0) {
  $("overlay").style.display = on || !S.els.size ? "flex" : "none";
  ($("bar") as HTMLElement).hidden = !on;
  $("barFill").style.width = pct + "%";
  $("progressTxt").textContent = txt;
  $("sampleBtn2").style.display = on ? "none" : "";
}
function levels() {
  const ls = [
    ...new Set([...S.els.values()].map((e) => e.storey).filter(Boolean)),
  ];
  $("levelSel").innerHTML =
    '<option value="">All levels</option>' +
    ls.map((l) => `<option>${esc(l)}</option>`).join("");
  S.level = "";
}
async function busy(txt: string, fn: () => Promise<unknown>) {
  progress(true, txt, 30);
  try {
    await fn();
    await reload(true);
  } catch (e) {
    progress(false);
    showError(e);
  }
}
const loadSample = () =>
  busy("Ingesting the synthetic building and calc package…", () =>
    api.sample(1),
  );
$("sampleBtn").onclick = loadSample;
$("sampleBtn2").onclick = loadSample;
$("rev2Btn").onclick = () =>
  busy("Ingesting model revision 2 (column C8 removed)…", () => api.sample(2));
($("ifcIn") as HTMLInputElement).onchange = (e) => {
  const inp = e.target as HTMLInputElement,
    f = inp.files?.[0];
  if (!f) return;
  busy(`Reading ${f.name}…`, () => api.upload("model", f));
  inp.value = "";
};
($("pdfIn") as HTMLInputElement).onchange = (e) => {
  const inp = e.target as HTMLInputElement,
    f = inp.files?.[0];
  if (!f) return;
  busy(`Reading ${f.name}…`, () => api.upload("calcs", f));
  inp.value = "";
};
($("colorBy") as HTMLSelectElement).onchange = (e) => {
  S.colorBy = (e.target as HTMLSelectElement).value;
  paint();
};
($("levelSel") as HTMLSelectElement).onchange = (e) => {
  S.level = (e.target as HTMLSelectElement).value;
  paint();
  viewer.fit();
};
$("xrayBtn").onclick = (e) => {
  S.xray = !S.xray;
  (e.target as HTMLElement).classList.toggle("on", S.xray);
  paint();
};
$("fitBtn").onclick = () => viewer.fit();
$("themeBtn").onclick = () => {
  const r = document.documentElement;
  const dark = r.dataset.theme
    ? r.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  r.dataset.theme = dark ? "light" : "dark";
};
$("exportBtn").onclick = () => {
  window.location.href = api.exportUrl();
};
function setTab(t: "3d" | "graph") {
  S.tab = t;
  $("tab3d").classList.toggle("on", t === "3d");
  $("tabGraph").classList.toggle("on", t === "graph");
  $("viewerWrap").style.display = t === "3d" ? "" : "none";
  $("graphWrap").style.display = t === "graph" ? "block" : "none";
  $("tabNote").textContent =
    t === "graph"
      ? "Selected element: full downstream path, two levels upstream"
      : "";
  if (t === "graph") drawGraph();
  else viewer.resize();
}
$("tab3d").onclick = () => setTab("3d");
$("tabGraph").onclick = () => setTab("graph");

// hover + click in 3D
let downAt: [number, number] | null = null;
const canvas = viewer.renderer.domElement;
canvas.addEventListener(
  "pointerdown",
  (e) => (downAt = [e.clientX, e.clientY]),
);
canvas.addEventListener("pointerup", (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4)
    return;
  const g = viewer.pick(e);
  select(g ? { kind: "el", id: g } : null);
});
canvas.addEventListener("pointermove", (e) => {
  const tip = $("tip");
  if (e.buttons) {
    tip.style.display = "none";
    return;
  }
  const g = viewer.pick(e),
    el = g ? S.els.get(g) : null;
  if (!el) {
    tip.style.display = "none";
    return;
  }
  const ls = linksFor(el.global_id),
    r = $("viewerWrap").getBoundingClientRect();
  tip.innerHTML =
    `<b>${esc(label(el))}</b> <span style="color:var(--muted)">${esc(el.cat)}${el.profile ? " · " + esc(el.profile) : ""}</span><br>` +
    (ls.length
      ? ls
          .map(
            (l) =>
              `${esc(S.calcs.get(l.calc_key)?.title)} <span style="color:var(--muted)">${Math.round(l.conf * 100)}%</span>`,
          )
          .join("<br>")
      : '<span style="color:var(--bad)">No calc found</span>');
  tip.style.display = "block";
  tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 270) + "px";
  tip.style.top = e.clientY - r.top + 14 + "px";
});
canvas.addEventListener(
  "pointerleave",
  () => ($("tip").style.display = "none"),
);

// console / headless-test handle
(window as unknown as { __cg: unknown }).__cg = {
  S, select, runImpact, setTab, openPage,
  byMark: (m: string) => [...S.els.values()].find(e => e.mark === m)?.global_id,
};
progress(false);
reload(true).catch(showError);
