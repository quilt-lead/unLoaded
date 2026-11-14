// Original-PDF page viewer: zoom / pan over a server-side PyMuPDF render, highlight
// boxes drawn in PDF points on top. A low-resolution render of the whole page sits
// underneath; once the view settles, a sharp render of just the visible region is
// fetched and laid over it, so a 3024 x 2160 pt sheet stays crisp at any zoom.

export interface Shown {
  sid: string;
  doc: string;
  page: number;
  pw: number; // page width, PDF points
  ph: number;
  rects: number[][]; // highlight boxes, PDF points
  focus?: number[] | null; // box to zoom to (defaults to the union of rects)
  label?: string; // caption (doc / page / matched text)
  sub?: string;
}

const BG_W = 1600;

export class PdfView {
  host: HTMLElement;
  stage: HTMLDivElement;
  world: HTMLDivElement;
  bg: HTMLImageElement;
  sharp: HTMLImageElement;
  svg: SVGSVGElement;
  cap: HTMLDivElement;
  cur: Shown | null = null;
  s = 1; // px per pt
  tx = 0;
  ty = 0;
  private timer = 0;
  private seq = 0;

  constructor(host: HTMLElement) {
    this.host = host;
    host.classList.add("pv");
    host.innerHTML = `<div class="pv-cap"></div><div class="pv-stage"><div class="pv-world"><img class="pv-bg" alt=""><img class="pv-sharp" alt=""><svg class="pv-hl"></svg></div>
      <div class="pv-tools"><button data-z="in" title="Zoom in">+</button><button data-z="out" title="Zoom out">-</button><button data-z="hl" title="Zoom to the highlighted text">Highlight</button><button data-z="fit" title="Whole page">Page</button><a class="pv-open" target="_blank" rel="noopener" title="Open the original PDF at this page">PDF</a></div>
      <div class="pv-empty">Click any node, link or finding to open the original page here.</div></div>`;
    this.cap = host.querySelector(".pv-cap")!;
    this.stage = host.querySelector(".pv-stage")!;
    this.world = host.querySelector(".pv-world")!;
    this.bg = host.querySelector(".pv-bg")!;
    this.sharp = host.querySelector(".pv-sharp")!;
    this.svg = host.querySelector(".pv-hl")!;
    this.stage.addEventListener("wheel", (e) => this.onWheel(e), {
      passive: false,
    });
    let drag: { x: number; y: number; tx: number; ty: number } | null = null;
    this.stage.addEventListener("pointerdown", (e) => {
      if ((e.target as HTMLElement).closest(".pv-tools")) return;
      drag = { x: e.clientX, y: e.clientY, tx: this.tx, ty: this.ty };
      this.stage.setPointerCapture(e.pointerId);
    });
    this.stage.addEventListener("pointermove", (e) => {
      if (!drag) return;
      this.tx = drag.tx + e.clientX - drag.x;
      this.ty = drag.ty + e.clientY - drag.y;
      this.apply();
    });
    this.stage.addEventListener("pointerup", () => (drag = null));
    host.querySelectorAll<HTMLButtonElement>("[data-z]").forEach(
      (b) =>
        (b.onclick = () => {
          const z = b.dataset.z;
          const r = this.stage.getBoundingClientRect();
          if (z === "in") this.zoomAt(r.width / 2, r.height / 2, 1.6);
          else if (z === "out") this.zoomAt(r.width / 2, r.height / 2, 1 / 1.6);
          else if (z === "fit" && this.cur)
            this.fitTo([0, 0, this.cur.pw, this.cur.ph], 0);
          else if (z === "hl") this.focus();
        }),
    );
    new ResizeObserver(() => this.cur && this.apply()).observe(this.stage);
  }

  show(v: Shown) {
    const samePage =
      this.cur &&
      this.cur.doc === v.doc &&
      this.cur.page === v.page &&
      this.cur.sid === v.sid;
    this.cur = v;
    this.host.classList.add("has");
    this.cap.innerHTML = v.label ?? "";
    if (v.sub) this.cap.innerHTML += `<div class="pv-sub">${v.sub}</div>`;
    this.world.style.width = v.pw + "px";
    this.world.style.height = v.ph + "px";
    const base = `/api/sets/${v.sid}/docs/${v.doc}/pages/${v.page}.png`;
    (this.host.querySelector(".pv-open") as HTMLAnchorElement).href =
      `/api/sets/${v.sid}/docs/${v.doc}/file#page=${v.page}`;
    if (!samePage) {
      this.bg.src = `${base}?w=${BG_W}`;
      this.bg.style.width = v.pw + "px";
      this.bg.style.height = v.ph + "px";
      this.sharp.removeAttribute("src");
      this.sharp.style.display = "none";
    }
    this.svg.setAttribute("viewBox", `0 0 ${v.pw} ${v.ph}`);
    this.svg.style.width = v.pw + "px";
    this.svg.style.height = v.ph + "px";
    const pad = Math.max(v.pw, v.ph) / 900;
    this.svg.innerHTML = v.rects
      .map(
        (r) =>
          `<rect x="${r[0] - pad}" y="${r[1] - pad}" width="${r[2] - r[0] + 2 * pad}" height="${r[3] - r[1] + 2 * pad}" rx="${pad}"/>`,
      )
      .join("");
    requestAnimationFrame(() => this.focus());
  }

  focus() {
    const v = this.cur;
    if (!v) return;
    const f = v.focus ?? union(v.rects);
    if (!f) return this.fitTo([0, 0, v.pw, v.ph], 0);
    // keep context: at least ~ 360 pt on a sheet, ~ 160 pt on a letter page
    const minSpan = Math.max(v.pw, v.ph) > 1500 ? 360 : 170;
    const cx = (f[0] + f[2]) / 2,
      cy = (f[1] + f[3]) / 2;
    const w = Math.max(f[2] - f[0] + 60, minSpan),
      h = Math.max(f[3] - f[1] + 60, minSpan * 0.6);
    this.fitTo([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 0);
  }

  fitTo(r: number[], pad: number) {
    const st = this.stage.getBoundingClientRect();
    if (!st.width) return;
    const w = r[2] - r[0] + 2 * pad,
      h = r[3] - r[1] + 2 * pad;
    this.s = Math.min(st.width / w, st.height / h);
    this.tx = st.width / 2 - ((r[0] + r[2]) / 2) * this.s;
    this.ty = st.height / 2 - ((r[1] + r[3]) / 2) * this.s;
    this.apply();
  }

  private onWheel(e: WheelEvent) {
    if (!this.cur) return;
    e.preventDefault();
    const r = this.stage.getBoundingClientRect();
    this.zoomAt(
      e.clientX - r.left,
      e.clientY - r.top,
      Math.exp(-e.deltaY * 0.0022),
    );
  }

  zoomAt(px: number, py: number, k: number) {
    const ns = Math.max(0.05, Math.min(this.s * k, 40));
    k = ns / this.s;
    this.tx = px - (px - this.tx) * k;
    this.ty = py - (py - this.ty) * k;
    this.s = ns;
    this.apply();
  }

  private apply() {
    this.world.style.transform = `translate(${this.tx}px, ${this.ty}px) scale(${this.s})`;
    this.svg.style.setProperty("--sw", String(2 / this.s));
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.loadSharp(), 220);
  }

  private loadSharp() {
    const v = this.cur;
    if (!v) return;
    const st = this.stage.getBoundingClientRect();
    // visible region in PDF points, grown a little, clamped to the page
    let x0 = -this.tx / this.s,
      y0 = -this.ty / this.s;
    let x1 = x0 + st.width / this.s,
      y1 = y0 + st.height / this.s;
    const gx = (x1 - x0) * 0.15,
      gy = (y1 - y0) * 0.15;
    x0 = Math.max(0, x0 - gx);
    y0 = Math.max(0, y0 - gy);
    x1 = Math.min(v.pw, x1 + gx);
    y1 = Math.min(v.ph, y1 + gy);
    if (x1 - x0 < 2 || y1 - y0 < 2) return;
    const pxW = Math.round(
      (x1 - x0) * this.s * Math.min(devicePixelRatio || 1, 2),
    );
    if (pxW <= BG_W * ((x1 - x0) / v.pw) * 1.05) {
      this.sharp.style.display = "none"; // the background render is already sharp enough
      return;
    }
    const seq = ++this.seq;
    const clip = [x0, y0, x1, y1].map((n) => n.toFixed(1)).join(",");
    const img = new Image();
    img.onload = () => {
      if (seq !== this.seq || this.cur !== v) return; // a newer view or page replaced this one
      this.sharp.src = img.src;
      Object.assign(this.sharp.style, {
        display: "block",
        left: x0 + "px",
        top: y0 + "px",
        width: x1 - x0 + "px",
        height: y1 - y0 + "px",
      });
    };
    img.src = `/api/sets/${v.sid}/docs/${v.doc}/pages/${v.page}.png?clip=${clip}&w=${Math.min(pxW, 4096)}`;
  }

  clear() {
    this.cur = null;
    this.host.classList.remove("has");
    this.cap.innerHTML = "";
    this.svg.innerHTML = "";
    this.bg.removeAttribute("src");
    this.sharp.removeAttribute("src");
  }
}

export function union(rs: number[][]): number[] | null {
  const v = rs.filter((r) => r && r.length === 4);
  if (!v.length) return null;
  return [
    Math.min(...v.map((r) => r[0])),
    Math.min(...v.map((r) => r[1])),
    Math.max(...v.map((r) => r[2])),
    Math.max(...v.map((r) => r[3])),
  ];
}
