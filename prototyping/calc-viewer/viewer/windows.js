// Cross-window routing between the three pages (works over http and when opened from disk).
// openViewer("calcs" | "drawings", params) shows params in an already-open viewer of that kind if there is one,
// otherwise opens a new window. Order:
//   1. a known peer window: one this page opened, or the page that opened this one – told by postMessage
//   2. any open viewer in another tab of this site – found over a BroadcastChannel (served mode)
//   3. a new window (or this tab, if pop-ups are blocked)
const CHANNEL = "bldg12-calcviewer";
let chan = null;
try { chan = "BroadcastChannel" in window ? new BroadcastChannel(CHANNEL) : null; } catch { chan = null; }
const myId = Math.random().toString(36).slice(2);
const myKind = document.body.dataset.mode; // drawings | calcs | index
let lastFocus = document.hasFocus() ? Date.now() : 0;
addEventListener("focus", () => (lastFocus = Date.now()));

const WIN_NAMES = { drawings: "bldg12-drawings", calcs: "bldg12-calcs", index: "bldg12-index" };
const LABEL = { drawings: "drawing viewer", calcs: "calc viewer" };
const peers = {}; // kind -> { win, ready }
let showHandler = null;
let pendingShow = null; // a "show" that arrived while this viewer was still loading (its PDF can take seconds)
const handleShow = (params) => {
  if (showHandler) showHandler(params);
  else pendingShow = params; // keep only the latest step; serveViewer() plays it once the viewer is ready
};

// peers introduce themselves: a page says hello to its opener, and answers hellos
addEventListener("message", (e) => {
  const m = e.data;
  if (!m || m.app !== CHANNEL || !e.source) return;
  if (m.type === "hello" || m.type === "hello-ack") {
    peers[m.kind] = { win: e.source, ready: true };
    if (m.type === "hello") e.source.postMessage({ app: CHANNEL, type: "hello-ack", kind: myKind }, "*");
  }
  if (m.type === "show" && m.kind === myKind) {
    handleShow(m.params);
    try { window.focus(); } catch { /* may be refused */ }
    markTitle();
  }
});
try { window.opener?.postMessage({ app: CHANNEL, type: "hello", kind: myKind }, "*"); } catch { /* no opener */ }

/** Called by a viewer page: makes it reachable by name, by message and over the channel. */
export function serveViewer(kind, show) {
  window.name = WIN_NAMES[kind];
  showHandler = (params) => { if (params && Object.keys(params).length) show(params); };
  if (pendingShow) { const p = pendingShow; pendingShow = null; showHandler(p); }
  chan?.addEventListener("message", (e) => {
    const m = e.data || {};
    if (m.kind !== kind) return;
    if (m.type === "probe") chan.postMessage({ type: "here", kind, reqId: m.reqId, id: myId, focus: lastFocus });
    if (m.type === "show" && m.target === myId) {
      showHandler(m.params);
      try { window.focus(); } catch { /* browsers may refuse */ }
      toast(`Updated from the ${m.from || "other"} window`);
      markTitle();
    }
  });
}

export async function openViewer(kind, params, from = myKind) {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== ""));
  const url = new URL(`${kind}.html?${new URLSearchParams(clean)}`, location.href).href;
  // 1. a known peer
  const p = peers[kind];
  if (p && p.win && !p.win.closed) {
    try {
      if (p.ready) p.win.postMessage({ app: CHANNEL, type: "show", kind, params: clean }, "*");
      else p.win.location.href = url; // still loading: just point it at the new place
      bringToFront(kind, p.win);
      toast(`Shown in the ${LABEL[kind]} window ↗`);
      return "reused";
    } catch { /* fall through */ }
  }
  // 2. a viewer open in some other tab (same site)
  if (chan) {
    const reqId = Math.random().toString(36).slice(2);
    const answers = [];
    const onMsg = (e) => { if (e.data?.type === "here" && e.data.reqId === reqId) answers.push(e.data); };
    chan.addEventListener("message", onMsg);
    chan.postMessage({ type: "probe", kind, reqId });
    await new Promise((r) => setTimeout(r, 180));
    chan.removeEventListener("message", onMsg);
    if (answers.length) {
      const best = answers.sort((a, b) => b.focus - a.focus)[0];
      chan.postMessage({ type: "show", kind, target: best.id, params: clean, from });
      // a page can't bring another tab to the front, so say where it went and offer a window we can focus
      toast(`Shown in the ${LABEL[kind]} that's open in another tab (marked ● in its tab title).`, {
        label: "Open in a new window",
        onClick: () => { const w = window.open(url, "_blank"); if (w) peers[kind] = { win: w, ready: false }; },
      }, 9000);
      return "other-tab";
    }
  }
  // 3. a new window
  const w = window.open(url, WIN_NAMES[kind]);
  if (w) { peers[kind] = { win: w, ready: false }; return "new"; }
  toast(`The browser blocked the new ${LABEL[kind]} window. Allow pop-ups for these pages, then click again.`, {
    label: "Open in this tab instead", onClick: () => { location.href = url; },
  }, 12000);
  return "blocked";
}

// win.focus() only raises pop-up windows; a viewer that opened as a *tab* stays behind, so the step looks like it
// did nothing. Targeting the tab by name with an empty URL activates it (during the click) without reloading it.
function bringToFront(kind, win) {
  try { win.focus(); } catch { /* refused */ }
  try {
    const w = window.open("", WIN_NAMES[kind]);
    if (w && w !== win) w.close(); // name lookup missed and made a blank window: drop it
  } catch { /* refused */ }
}

let titleTimer;
function markTitle() {
  const base = document.title.replace(/^● /, "");
  document.title = "● " + base;
  clearTimeout(titleTimer);
  const clear = () => { document.title = base; };
  if (document.hasFocus()) titleTimer = setTimeout(clear, 4000);
  else addEventListener("focus", () => (titleTimer = setTimeout(clear, 1500)), { once: true });
}

/** Make <a data-open="calcs|drawings" data-params="..."> links route through openViewer (plain clicks only). */
export function routeLinks(root = document) {
  root.addEventListener("click", (ev) => {
    const a = ev.target.closest("a[data-open]");
    if (!a || ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
    ev.preventDefault();
    openViewer(a.dataset.open, Object.fromEntries(new URLSearchParams(a.dataset.params || "")));
  });
}

let toastTimer;
export function toast(msg, action = null, ms = 2600) {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  if (action) {
    const b = document.createElement("button");
    b.textContent = action.label;
    b.addEventListener("click", () => { t.classList.remove("on"); action.onClick(); });
    t.appendChild(b);
  }
  t.classList.add("on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("on"), ms);
}
