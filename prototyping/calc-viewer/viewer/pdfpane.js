// A continuous-scroll PDF pane (PDF.js) with zoom and named overlay layers.
// Overlay rects are fractions of the page (x0, y0, x1, y1), so they follow zoom without recalculation.
import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.worker.min.mjs";

const docCache = new Map(); // url -> Promise<{pdf, sizes}>
const MAX_CANVAS_PX = 14e6;

function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function loadDoc(url, docId) {
  if (!docCache.has(url)) {
    docCache.set(url, (async () => {
      // the double-click build (viewers/) ships each PDF as a script that sets window.PDF_DATA[docId]
      const packed = window.PDF_DATA?.[docId];
      const src = packed ? { data: b64ToBytes(packed) } : { url, disableAutoFetch: true };
      const pdf = await pdfjsLib.getDocument(src).promise;
      const sizes = await Promise.all(
        Array.from({ length: pdf.numPages }, (_, i) => pdf.getPage(i + 1).then((p) => { const v = p.getViewport({ scale: 1 }); return [v.width, v.height]; }))
      );
      return { pdf, sizes };
    })());
  }
  return docCache.get(url);
}

export class PdfPane {
  constructor(scroller, { onPage } = {}) {
    this.scroller = scroller;
    this.onPage = onPage;
    this.zoom = 1;
    this.layers = {};
    this.pageEls = [];
    this.url = null;
    this.io = new IntersectionObserver((ents) => this._onIntersect(ents), { root: scroller, rootMargin: "800px 0px" });
    this.visible = new Set();
    scroller.addEventListener("scroll", () => this._reportPage(), { passive: true });
    this._w = 0;
    new ResizeObserver(() => {
      if (!this.pdf || Math.abs(scroller.clientWidth - this._w) < 2) return;
      this._w = scroller.clientWidth;
      const t = this._target;
      this._layout(!t || Date.now() - t.at > 2500);
      // a resize right after a jump (e.g. the pane just opened) must not lose that jump
      if (t && Date.now() - t.at <= 2500) this.scrollTo(t.page, t.rect, { ...t.opts, smooth: false });
    }).observe(scroller);
    this._bindGestures();
  }

  /** Pinch to zoom: touchscreen (two fingers), trackpad pinch / ctrl+wheel, and Safari gesture events. */
  _bindGestures() {
    const sc = this.scroller;
    sc.style.touchAction = "pan-x pan-y"; // browser keeps one-finger panning; we own pinch
    const local = (x, y) => { const r = sc.getBoundingClientRect(); return [x - r.left, y - r.top]; };

    // trackpad pinch arrives as ctrl+wheel in Chromium/Firefox; also ctrl+mouse wheel
    sc.addEventListener("wheel", (e) => {
      if (!e.ctrlKey || !this.pdf) return;
      e.preventDefault();
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      this.setZoomAt(this.zoom * Math.exp(-dy * 0.01), ...local(e.clientX, e.clientY));
    }, { passive: false });

    // touchscreen two-finger pinch (pans with the midpoint too)
    let pinch = null;
    const two = (e) => {
      const [a, b] = e.touches;
      return { d: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY), x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
    };
    sc.addEventListener("touchstart", (e) => {
      if (e.touches.length !== 2 || !this.pdf) return;
      const t = two(e);
      pinch = { d: t.d, zoom: this.zoom, x: t.x, y: t.y };
    }, { passive: true });
    sc.addEventListener("touchmove", (e) => {
      if (!pinch || e.touches.length !== 2) return;
      e.preventDefault();
      const t = two(e);
      sc.scrollLeft -= t.x - pinch.x;
      sc.scrollTop -= t.y - pinch.y;
      pinch.x = t.x; pinch.y = t.y;
      this.setZoomAt(pinch.zoom * (t.d / Math.max(1, pinch.d)), ...local(t.x, t.y));
    }, { passive: false });
    const end = (e) => { if (pinch && e.touches.length < 2) pinch = null; };
    sc.addEventListener("touchend", end);
    sc.addEventListener("touchcancel", end);

    // Safari (macOS trackpad) sends proprietary gesture events instead of ctrl+wheel
    let g0 = 1;
    sc.addEventListener("gesturestart", (e) => { e.preventDefault(); g0 = this.zoom; });
    sc.addEventListener("gesturechange", (e) => { e.preventDefault(); this.setZoomAt(g0 * e.scale, ...local(e.clientX, e.clientY)); });
    sc.addEventListener("gestureend", (e) => e.preventDefault());
  }

  /** Zoom keeping the content under (px, py) — pane-local coords — fixed. Re-renders once the gesture settles. */
  setZoomAt(z, px, py) {
    z = Math.min(8, Math.max(0.25, z));
    if (!this.pdf || Math.abs(z - this.zoom) < 1e-3) return;
    const sc = this.scroller;
    const cy = sc.scrollTop + py, cx = sc.scrollLeft + px;
    let d = this.pageEls[0];
    for (const p of this.pageEls) { if (p.offsetTop <= cy) d = p; else break; }
    const fx = (cx - d.offsetLeft) / d.offsetWidth, fy = (cy - d.offsetTop) / d.offsetHeight;
    this.zoom = z;
    this._target = null;
    this._layout(false, true); // resize boxes now; existing canvases stretch until re-rendered
    sc.scrollLeft = d.offsetLeft + fx * d.offsetWidth - px;
    sc.scrollTop = d.offsetTop + fy * d.offsetHeight - py;
    clearTimeout(this._rerender);
    this._rerender = setTimeout(() => { for (const i of this.visible) this._render(i); }, 160);
  }

  async open(url, docId) {
    if (this.url === url) return;
    this.url = url;
    this.docId = docId;
    this.scroller.innerHTML = '<div class="empty" style="padding:20px">Loading PDF…</div>';
    const { pdf, sizes } = await loadDoc(url, docId);
    if (this.url !== url) return;
    this.pdf = pdf;
    this.sizes = sizes;
    const widths = sizes.map((s) => s[0]).sort((a, b) => a - b);
    this.refWidth = widths[Math.floor(widths.length / 2)];
    this.scroller.innerHTML = "";
    this.io.disconnect();
    this.visible.clear();
    this.pageEls = sizes.map((_, i) => {
      const d = document.createElement("div");
      d.className = "page";
      d.dataset.page = i + 1;
      d.innerHTML = `<span class="pno">${i + 1}</span><div class="overlay"></div>`;
      this.scroller.appendChild(d);
      this.io.observe(d);
      return d;
    });
    this.zoom = 1;
    this._w = this.scroller.clientWidth;
    this._layout(false);
    for (const name of Object.keys(this.layers)) this._paintLayer(name);
  }

  get fitScale() { return Math.max(0.05, (this.scroller.clientWidth - 28) / this.refWidth); }
  get scale() { return this.fitScale * this.zoom; }

  _layout(keepPosition, deferRender = false) {
    const anchor = keepPosition ? this._anchor() : null;
    this.pageEls.forEach((d, i) => {
      const [w, h] = this.sizes[i];
      // same scale for every page, except oversize pages (e.g. a fold-out sheet) which fit the pane width
      const s = Math.min(this.scale, ((this.scroller.clientWidth - 28) / w) * this.zoom);
      d.style.width = `${w * s}px`;
      d.style.height = `${h * s}px`;
      d.dataset.scale = s;
    });
    if (!deferRender) for (const i of this.visible) this._render(i);
    if (anchor) this._restore(anchor);
  }

  _anchor() {
    const p = this.currentPage();
    const d = this.pageEls[p - 1];
    if (!d) return null;
    return { p, fy: (this.scroller.scrollTop - d.offsetTop + this.scroller.clientHeight / 2) / d.offsetHeight, fx: (this.scroller.scrollLeft + this.scroller.clientWidth / 2) / this.scroller.scrollWidth };
  }

  _restore(a) {
    const d = this.pageEls[a.p - 1];
    this.scroller.scrollTop = d.offsetTop + a.fy * d.offsetHeight - this.scroller.clientHeight / 2;
    this.scroller.scrollLeft = a.fx * this.scroller.scrollWidth - this.scroller.clientWidth / 2;
  }

  setZoom(z, keep = true) {
    z = Math.min(8, Math.max(0.25, z));
    if (Math.abs(z - this.zoom) < 1e-3) return;
    this.zoom = z;
    this._layout(keep);
  }

  _onIntersect(ents) {
    for (const e of ents) {
      const i = +e.target.dataset.page - 1;
      if (e.isIntersecting) { this.visible.add(i); this._render(i); }
      else { this.visible.delete(i); this._drop(i); }
    }
  }

  _drop(i) {
    const d = this.pageEls[i];
    const c = d.querySelector("canvas");
    if (c) { c.width = c.height = 0; c.remove(); }
    d.dataset.rendered = "";
  }

  async _render(i) {
    const d = this.pageEls[i];
    const s = +d.dataset.scale;
    const key = `${s.toFixed(4)}`;
    if (d.dataset.rendered === key || d.dataset.rendering === key) return;
    d.dataset.rendering = key;
    const page = await this.pdf.getPage(i + 1);
    const [w, h] = this.sizes[i];
    let out = (window.devicePixelRatio || 1) * s;
    if (w * h * out * out > MAX_CANVAS_PX) out = Math.sqrt(MAX_CANVAS_PX / (w * h));
    const vp = page.getViewport({ scale: out });
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(vp.width);
    canvas.height = Math.floor(vp.height);
    try {
      d._task?.cancel();
      d._task = page.render({ canvasContext: canvas.getContext("2d"), viewport: vp });
      await d._task.promise;
    } catch (e) {
      if (e?.name !== "RenderingCancelledException") console.warn(e);
      return;
    }
    if (d.dataset.rendering !== key || !this.visible.has(i)) return;
    d.querySelector("canvas")?.remove();
    d.prepend(canvas);
    d.dataset.rendered = key;
    d.dataset.rendering = "";
  }

  currentPage() {
    const mid = this.scroller.scrollTop + this.scroller.clientHeight * 0.35;
    let p = 1;
    for (const d of this.pageEls) { if (d.offsetTop <= mid) p = +d.dataset.page; else break; }
    return p;
  }

  _reportPage() {
    const p = this.currentPage();
    if (p !== this._lastPage) { this._lastPage = p; this.onPage?.(p); }
  }

  /** Scroll so a fractional rect on a page is in view. zoomFor: fraction of pane width the rect should take. */
  scrollTo(page, rect, { zoomFor = null, maxZoom = 6, smooth = true, topMargin = 70 } = {}) {
    const d = this.pageEls[page - 1];
    if (!d) return;
    this._target = { page, rect, opts: { zoomFor, maxZoom, topMargin }, at: Date.now() };
    if (zoomFor) {
      const [w] = this.sizes[page - 1];
      const rw = Math.max(0.01, rect[2] - rect[0]);
      const z = (zoomFor * (this.scroller.clientWidth - 28)) / (rw * w * this.fitScale);
      this.setZoom(Math.min(maxZoom, Math.max(1, z)), false);
    }
    const top = d.offsetTop + rect[1] * d.offsetHeight - topMargin;
    const cx = d.offsetLeft + ((rect[0] + rect[2]) / 2) * d.offsetWidth;
    this.scroller.scrollTo({ top, left: cx - this.scroller.clientWidth / 2, behavior: smooth ? "smooth" : "auto" });
  }

  /** items: [{page, rect, cls, html, title, attrs, on:{click,...}}] */
  setLayer(name, items) {
    this.layers[name] = items;
    this._paintLayer(name);
  }

  _paintLayer(name) {
    this.scroller.querySelectorAll(`.ov[data-layer="${name}"]`).forEach((n) => n.remove());
    const items = this.layers[name] || [];
    for (const it of items) {
      const d = this.pageEls[it.page - 1];
      if (!d) continue;
      const n = document.createElement("div");
      n.className = "ov " + (it.cls || "");
      n.dataset.layer = name;
      const [x0, y0, x1, y1] = it.rect;
      if (it.point) { n.style.left = `${x0 * 100}%`; n.style.top = `${y0 * 100}%`; }
      else Object.assign(n.style, { left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` });
      if (it.html) n.innerHTML = it.html;
      if (it.title) n.title = it.title;
      for (const [k, v] of Object.entries(it.attrs || {})) n.dataset[k] = v;
      for (const [ev, fn] of Object.entries(it.on || {})) n.addEventListener(ev, fn);
      d.querySelector(".overlay").appendChild(n);
    }
  }

  nodes(name, sel = "") { return [...this.scroller.querySelectorAll(`.ov[data-layer="${name}"]${sel}`)]; }
}
