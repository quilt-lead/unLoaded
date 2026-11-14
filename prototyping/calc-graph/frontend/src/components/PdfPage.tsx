import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { PDFPageProxy, RenderTask } from "pdfjs-dist";
import "pdfjs-dist/web/pdf_viewer.css";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";
import { loadPdf, pdfjs } from "./pdf";

/** [x0, y0, x1, y1] in PDF points, top-left origin (PyMuPDF convention, as every backend bbox is). */
export type Box = readonly [number, number, number, number] | readonly number[];

export interface PdfSource {
  /** URL of the PDF file (e.g. urls.v2DocFile("calcs")) */
  url: string;
  /** 1-based page number */
  page: number;
  /** evidence boxes to highlight */
  rects?: readonly Box[];
  /** box to zoom to on open (defaults to the union of rects, else the whole page) */
  focus?: Box | null;
  label?: ReactNode;
  sub?: ReactNode;
  /** "open the PDF" link (defaults to url#page=N) */
  openUrl?: string;
}

export interface PdfPageProps {
  source: PdfSource | null;
  info: HelpId;
  emptyText?: ReactNode;
  className?: string;
}

export interface PdfPageHandle {
  zoomTo: (box: Box) => void;
  zoomToHighlight: () => void;
  fitPage: () => void;
}

const BG_W = 1600; // px width of the whole-page underlay render
const MAX_PX = 16e6; // canvas pixel budget for the sharp render

export function unionBox(rs: readonly Box[] | undefined): Box | null {
  const v = (rs ?? []).filter((r) => r && r.length === 4);
  if (!v.length) return null;
  return [
    Math.min(...v.map((r) => r[0])),
    Math.min(...v.map((r) => r[1])),
    Math.max(...v.map((r) => r[2])),
    Math.max(...v.map((r) => r[3])),
  ];
}

/**
 * One original PDF page drawn with pdf.js: a whole-page underlay plus a sharp render of the visible
 * region once the view settles (so large sheets stay crisp at any zoom), the pdf.js text layer, and
 * highlight boxes over it. Wheel / pinch zoom, drag to pan, tools for zoom, evidence, whole page.
 */
export const PdfPage = forwardRef<PdfPageHandle, PdfPageProps>(function PdfPage({ source, info, emptyText, className }, ref) {
  const stage = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const bg = useRef<HTMLCanvasElement>(null);
  const sharp = useRef<HTMLCanvasElement>(null);
  const textHost = useRef<HTMLDivElement>(null);
  const view = useRef({ s: 1, tx: 0, ty: 0 });
  /** true once the user pans or zooms; until then a resize re-fits the evidence (e.g. when a split opens) */
  const userMoved = useRef(false);
  const pageRef = useRef<PDFPageProxy | null>(null);
  const sharpTask = useRef<RenderTask | null>(null);
  const settle = useRef(0);
  const [size, setSize] = useState<{ pw: number; ph: number } | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [err, setErr] = useState("");
  const [textMode, setTextMode] = useState(false);

  const renderSharp = useCallback(async () => {
    const page = pageRef.current, st = stage.current, cv = sharp.current;
    if (!page || !st || !cv || !size) return;
    const { s, tx, ty } = view.current;
    const r = st.getBoundingClientRect();
    let x0 = -tx / s, y0 = -ty / s, x1 = x0 + r.width / s, y1 = y0 + r.height / s;
    x0 = Math.max(0, x0); y0 = Math.max(0, y0); x1 = Math.min(size.pw, x1); y1 = Math.min(size.ph, y1);
    if (x1 - x0 < 2 || y1 - y0 < 2) return;
    let k = s * Math.min(window.devicePixelRatio || 1, 2);
    if (k <= (BG_W / size.pw) * 1.05) {
      cv.style.display = "none"; // the underlay is already sharp enough
      return;
    }
    const area = (x1 - x0) * (y1 - y0) * k * k;
    if (area > MAX_PX) k *= Math.sqrt(MAX_PX / area);
    sharpTask.current?.cancel();
    const off = document.createElement("canvas");
    off.width = Math.ceil((x1 - x0) * k);
    off.height = Math.ceil((y1 - y0) * k);
    const task = page.render({
      canvasContext: off.getContext("2d")!,
      viewport: page.getViewport({ scale: k }),
      transform: [1, 0, 0, 1, -x0 * k, -y0 * k],
    });
    sharpTask.current = task;
    try {
      await task.promise;
    } catch {
      return; // cancelled by a newer view
    }
    if (sharpTask.current !== task) return;
    cv.width = off.width;
    cv.height = off.height;
    cv.getContext("2d")!.drawImage(off, 0, 0);
    Object.assign(cv.style, { display: "block", left: `${x0}px`, top: `${y0}px`, width: `${x1 - x0}px`, height: `${y1 - y0}px` });
  }, [size]);

  const apply = useCallback(() => {
    const w = world.current;
    if (!w) return;
    const { s, tx, ty } = view.current;
    w.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
    w.style.setProperty("--hl-w", String(2 / s));
    window.clearTimeout(settle.current);
    settle.current = window.setTimeout(renderSharp, 200);
  }, [renderSharp]);

  const fitTo = useCallback(
    (b: Box) => {
      const st = stage.current;
      if (!st) return;
      const r = st.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const w = Math.max(1, b[2] - b[0]), h = Math.max(1, b[3] - b[1]);
      const s = Math.min(r.width / w, r.height / h);
      view.current = { s, tx: r.width / 2 - ((b[0] + b[2]) / 2) * s, ty: r.height / 2 - ((b[1] + b[3]) / 2) * s };
      apply();
    },
    [apply],
  );

  const fitPage = useCallback(() => size && fitTo([0, 0, size.pw, size.ph]), [size, fitTo]);

  const zoomToHighlight = useCallback(() => {
    if (!size || !source) return;
    const f = source.focus ?? unionBox(source.rects);
    if (!f) return fitPage();
    // keep context: at least ~360 pt across on a large sheet, ~170 pt on a letter page
    const minSpan = Math.max(size.pw, size.ph) > 1500 ? 360 : 170;
    const cx = (f[0] + f[2]) / 2, cy = (f[1] + f[3]) / 2;
    const w = Math.max(f[2] - f[0] + 60, minSpan), h = Math.max(f[3] - f[1] + 60, minSpan * 0.6);
    fitTo([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]);
  }, [size, source, fitTo, fitPage]);

  const refocus = useCallback(() => {
    userMoved.current = false;
    zoomToHighlight();
  }, [zoomToHighlight]);
  const refit = useCallback(() => {
    userMoved.current = true;
    fitPage();
  }, [fitPage]);
  const zoomToBox = useCallback(
    (b: Box) => {
      userMoved.current = true;
      fitTo(b);
    },
    [fitTo],
  );

  useImperativeHandle(ref, () => ({ zoomTo: zoomToBox, zoomToHighlight: refocus, fitPage: refit }), [zoomToBox, refocus, refit]);

  const zoomAt = useCallback(
    (px: number, py: number, k: number) => {
      userMoved.current = true;
      const v = view.current;
      const ns = Math.max(0.03, Math.min(v.s * k, 40));
      const kk = ns / v.s;
      view.current = { s: ns, tx: px - (px - v.tx) * kk, ty: py - (py - v.ty) * kk };
      apply();
    },
    [apply],
  );

  // load document + page whenever the file or page changes
  const url = source?.url, pageNo = source?.page;
  useEffect(() => {
    if (!url || !pageNo) {
      pageRef.current = null;
      setSize(null);
      setStatus("idle");
      return;
    }
    let dead = false;
    let bgTask: RenderTask | null = null;
    let textLayer: InstanceType<typeof pdfjs.TextLayer> | null = null;
    setStatus("loading");
    (async () => {
      try {
        const doc = await loadPdf(url);
        if (pageNo < 1 || pageNo > doc.numPages) throw new Error(`page ${pageNo} not in this PDF (${doc.numPages} pages)`);
        const page = await doc.getPage(pageNo);
        if (dead) return;
        const vp1 = page.getViewport({ scale: 1 });
        pageRef.current = page;
        if (sharp.current) sharp.current.style.display = "none";
        // whole-page underlay
        const k = BG_W / vp1.width;
        const c = bg.current!;
        c.width = Math.round(vp1.width * k);
        c.height = Math.round(vp1.height * k);
        bgTask = page.render({ canvasContext: c.getContext("2d")!, viewport: page.getViewport({ scale: k }) });
        // text layer at 1 px per point (scaled with the world)
        const th = textHost.current!;
        th.replaceChildren();
        textLayer = new pdfjs.TextLayer({ textContentSource: page.streamTextContent(), container: th, viewport: vp1 });
        setSize({ pw: vp1.width, ph: vp1.height });
        await Promise.all([bgTask.promise, textLayer.render()]);
        if (!dead) setStatus("ready");
      } catch (e) {
        if (dead || (e as Error)?.name === "RenderingCancelledException") return;
        setErr(e instanceof Error ? e.message : String(e));
        setStatus("error");
      }
    })();
    return () => {
      dead = true;
      bgTask?.cancel();
      textLayer?.cancel();
      sharpTask.current?.cancel();
    };
  }, [url, pageNo]);

  // (re)focus when the page size is known or the evidence changes
  const rectKey = JSON.stringify([source?.rects ?? [], source?.focus ?? null]);
  useEffect(() => {
    if (size) requestAnimationFrame(refocus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size, rectKey]);

  // re-render the sharp layer when the stage is resized
  useEffect(() => {
    const st = stage.current;
    if (!st) return;
    const ro = new ResizeObserver(() => {
      if (!pageRef.current) return;
      if (userMoved.current) apply();
      else zoomToHighlight();
    });
    ro.observe(st);
    return () => ro.disconnect();
  }, [apply, zoomToHighlight]);

  // wheel zoom (non-passive so the page does not scroll), drag pan, two-finger pinch
  useEffect(() => {
    const st = stage.current;
    if (!st) return;
    const onWheel = (e: WheelEvent) => {
      if (!pageRef.current) return;
      e.preventDefault();
      const r = st.getBoundingClientRect();
      zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * 0.0022));
    };
    st.addEventListener("wheel", onWheel, { passive: false });
    return () => st.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const drag = useRef<{ x: number; y: number; tx: number; ty: number; d?: number } | null>(null);
  const onPointerDown = (e: React.PointerEvent) => {
    if (textMode || (e.target as HTMLElement).closest(".cg-pdf-tools")) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    const v = view.current;
    drag.current = { x: e.clientX, y: e.clientY, tx: v.tx, ty: v.ty };
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      drag.current.d = Math.hypot(a.x - b.x, a.y - b.y);
    }
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current || !pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2 && drag.current.d) {
      const [a, b] = [...pointers.current.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const r = stage.current!.getBoundingClientRect();
      zoomAt((a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top, d / drag.current.d);
      drag.current.d = d;
      return;
    }
    userMoved.current = true;
    view.current = { ...view.current, tx: drag.current.tx + e.clientX - drag.current.x, ty: drag.current.ty + e.clientY - drag.current.y };
    apply();
  };
  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size === 0) drag.current = null;
    else {
      const [p] = [...pointers.current.values()];
      const v = view.current;
      drag.current = { x: p.x, y: p.y, tx: v.tx, ty: v.ty };
    }
  };

  const center = (k: number) => {
    const r = stage.current?.getBoundingClientRect();
    if (r) zoomAt(r.width / 2, r.height / 2, k);
  };
  const pad = size ? Math.max(size.pw, size.ph) / 900 : 1;

  return (
    <div className={`cg-pdf${source ? " has" : ""}${className ? " " + className : ""}`}>
      {source && (
        <div className="cg-pdf-cap">
          <div className="cg-pdf-label">
            {source.label ?? `Page ${source.page}`}
            <InfoTip id={info} />
          </div>
          {source.sub && <div className="cg-pdf-sub">{source.sub}</div>}
        </div>
      )}
      <div
        ref={stage}
        className={`cg-pdf-stage${textMode ? " text-mode" : ""}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div ref={world} className="cg-pdf-world" style={size ? { width: size.pw, height: size.ph } : { display: "none" }}>
          <canvas ref={bg} className="cg-pdf-bg" style={size ? { width: size.pw, height: size.ph } : undefined} />
          <canvas ref={sharp} className="cg-pdf-sharp" />
          <div ref={textHost} className="textLayer cg-pdf-text" />
          {size && (
            <svg className="cg-pdf-hl" viewBox={`0 0 ${size.pw} ${size.ph}`} width={size.pw} height={size.ph} aria-hidden="true">
              {(source?.rects ?? []).map((r, i) => (
                <rect key={i} x={r[0] - pad} y={r[1] - pad} width={r[2] - r[0] + 2 * pad} height={r[3] - r[1] + 2 * pad} rx={pad} />
              ))}
            </svg>
          )}
        </div>
        {source && (
          <div className="cg-pdf-tools" role="toolbar" aria-label="Page tools">
            <button type="button" className="btn sm" title="Zoom in" aria-label="Zoom in" onClick={() => center(1.6)}>+</button>
            <button type="button" className="btn sm" title="Zoom out" aria-label="Zoom out" onClick={() => center(1 / 1.6)}>-</button>
            <button type="button" className="btn sm" title="Zoom to the highlighted text" onClick={refocus}>Highlight</button>
            <button type="button" className="btn sm" title="Whole page" onClick={refit}>Page</button>
            <button type="button" className={`btn sm${textMode ? " on" : ""}`} aria-pressed={textMode} title="Select and copy text (turns off drag to pan)" onClick={() => setTextMode((v) => !v)}>Text</button>
            <a className="btn sm" target="_blank" rel="noopener" title="Open the original PDF at this page" href={source.openUrl ?? `${source.url}#page=${source.page}`}>PDF</a>
          </div>
        )}
        {!source && <div className="cg-pdf-empty">{emptyText ?? "Click a link, node or finding to open the original page here."}</div>}
        {source && status === "loading" && <div className="cg-pdf-status">Loading page...</div>}
        {source && status === "error" && <div className="cg-pdf-status bad" role="alert">Could not open the page: {err}</div>}
      </div>
    </div>
  );
});

export interface PdfSplitProps {
  primary: PdfSource | null;
  secondary: PdfSource | null;
  /** closes the second page (back to one) */
  onCloseSecondary: () => void;
  /** caption on the bar between the two pages */
  splitTitle?: ReactNode;
  /** help id for the split bar */
  info: HelpId;
  /** help id passed to both pages */
  pageInfo: HelpId;
}

/** Two PdfPages one above the other with a bar between them (the drawing-set evidence layout). */
export function PdfSplit({ primary, secondary, onCloseSecondary, splitTitle, info, pageInfo }: PdfSplitProps) {
  return (
    <div className={`cg-pdf-split${secondary ? " two" : ""}`}>
      <PdfPage source={primary} info={pageInfo} />
      {secondary && (
        <>
          <div className="cg-pdf-splitbar">
            <span>{splitTitle}</span>
            <InfoTip id={info} />
            <span className="spacer" />
            <button type="button" className="btn sm" title="Back to a single page" onClick={onCloseSecondary}>
              Close
            </button>
          </div>
          <PdfPage source={secondary} info={pageInfo} />
        </>
      )}
    </div>
  );
}
