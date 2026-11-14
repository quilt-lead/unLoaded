// One original PDF page drawn with pdf.js: a whole-page underlay plus a sharp render of the visible
// region once the view settles (so the page stays crisp at any zoom), the pdf.js text layer, and
// evidence boxes over it. Wheel / pinch zoom, drag to pan, tools for zoom, evidence, whole page.
// Ported from the calc-graph prototype (frontend/src/components/PdfPage.tsx), restyled to Tailwind.
import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import type { PDFPageProxy, RenderTask } from 'pdfjs-dist';
import 'pdfjs-dist/web/pdf_viewer.css';
import { ExternalLink, Focus, Loader2, Maximize, Minus, Plus, TextCursor } from 'lucide-react';
import { loadPdf, pdfjs } from './pdf';

/** [x0, y0, x1, y1] in PDF points, top-left origin (PyMuPDF convention, as every backend bbox is). */
export type Box = readonly number[];

export interface PdfSource {
  /** URL of the PDF file */
  url: string;
  /** 1-based page number */
  page: number;
  /** evidence boxes to highlight */
  rects?: readonly Box[];
  /** box to zoom to on open (defaults to the union of rects, else the whole page) */
  focus?: Box | null;
  label?: React.ReactNode;
  sub?: React.ReactNode;
}

export interface PdfPageProps {
  source: PdfSource | null;
  emptyText?: React.ReactNode;
  className?: string;
  /** hide the caption bar (when the parent already shows one) */
  bare?: boolean;
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

const toolBtn =
  'h-7 min-w-7 px-1.5 rounded-lg bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] text-zinc-300 hover:text-white hover:bg-white/[0.1] flex items-center justify-center gap-1 transition text-[10px] mono shadow-[0_4px_12px_rgba(0,0,0,0.5)]';

export const PdfPage = forwardRef<PdfPageHandle, PdfPageProps>(function PdfPage({ source, emptyText, className, bare }, ref) {
  const stage = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const bg = useRef<HTMLCanvasElement>(null);
  const sharp = useRef<HTMLCanvasElement>(null);
  const textHost = useRef<HTMLDivElement>(null);
  const view = useRef({ s: 1, tx: 0, ty: 0 });
  /** true once the user pans or zooms; until then a resize re-fits the evidence */
  const userMoved = useRef(false);
  const pageRef = useRef<PDFPageProxy | null>(null);
  const sharpTask = useRef<RenderTask | null>(null);
  const settle = useRef(0);
  const [size, setSize] = useState<{ pw: number; ph: number } | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [err, setErr] = useState('');
  const [textMode, setTextMode] = useState(false);
  const [hlWidth, setHlWidth] = useState(2);

  const renderSharp = useCallback(async () => {
    const page = pageRef.current;
    const st = stage.current;
    const cv = sharp.current;
    if (!page || !st || !cv || !size) return;
    const { s, tx, ty } = view.current;
    const r = st.getBoundingClientRect();
    let x0 = -tx / s;
    let y0 = -ty / s;
    let x1 = x0 + r.width / s;
    let y1 = y0 + r.height / s;
    x0 = Math.max(0, x0);
    y0 = Math.max(0, y0);
    x1 = Math.min(size.pw, x1);
    y1 = Math.min(size.ph, y1);
    if (x1 - x0 < 2 || y1 - y0 < 2) return;
    let k = s * Math.min(window.devicePixelRatio || 1, 2);
    if (k <= (BG_W / size.pw) * 1.05) {
      cv.style.display = 'none'; // the underlay is already sharp enough
      return;
    }
    const area = (x1 - x0) * (y1 - y0) * k * k;
    if (area > MAX_PX) k *= Math.sqrt(MAX_PX / area);
    sharpTask.current?.cancel();
    const off = document.createElement('canvas');
    off.width = Math.ceil((x1 - x0) * k);
    off.height = Math.ceil((y1 - y0) * k);
    const task = page.render({
      canvasContext: off.getContext('2d')!,
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
    cv.getContext('2d')!.drawImage(off, 0, 0);
    Object.assign(cv.style, { display: 'block', left: `${x0}px`, top: `${y0}px`, width: `${x1 - x0}px`, height: `${y1 - y0}px` });
  }, [size]);

  const apply = useCallback(() => {
    const w = world.current;
    if (!w) return;
    const { s, tx, ty } = view.current;
    w.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
    setHlWidth(2 / s);
    window.clearTimeout(settle.current);
    settle.current = window.setTimeout(renderSharp, 200);
  }, [renderSharp]);

  const fitTo = useCallback(
    (b: Box) => {
      const st = stage.current;
      if (!st) return;
      const r = st.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const w = Math.max(1, b[2] - b[0]);
      const h = Math.max(1, b[3] - b[1]);
      const s = Math.min(r.width / w, r.height / h);
      view.current = { s, tx: r.width / 2 - ((b[0] + b[2]) / 2) * s, ty: r.height / 2 - ((b[1] + b[3]) / 2) * s };
      apply();
    },
    [apply],
  );

  const fitPage = useCallback(() => {
    if (size) fitTo([0, 0, size.pw, size.ph]);
  }, [size, fitTo]);

  const zoomToHighlight = useCallback(() => {
    if (!size || !source) return;
    const f = source.focus ?? unionBox(source.rects);
    if (!f) {
      fitPage();
      return;
    }
    // keep context: at least ~360 pt across on a large sheet, ~170 pt on a letter page
    const minSpan = Math.max(size.pw, size.ph) > 1500 ? 360 : 170;
    const cx = (f[0] + f[2]) / 2;
    const cy = (f[1] + f[3]) / 2;
    const w = Math.max(f[2] - f[0] + 60, minSpan);
    const h = Math.max(f[3] - f[1] + 60, minSpan * 0.6);
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
  const url = source?.url;
  const pageNo = source?.page;
  useEffect(() => {
    if (!url || !pageNo) {
      pageRef.current = null;
      setSize(null);
      setStatus('idle');
      return;
    }
    let dead = false;
    let bgTask: RenderTask | null = null;
    let textLayer: InstanceType<typeof pdfjs.TextLayer> | null = null;
    setStatus('loading');
    (async () => {
      try {
        const doc = await loadPdf(url);
        if (pageNo < 1 || pageNo > doc.numPages) throw new Error(`page ${pageNo} not in this PDF (${doc.numPages} pages)`);
        const page = await doc.getPage(pageNo);
        if (dead) return;
        const vp1 = page.getViewport({ scale: 1 });
        pageRef.current = page;
        if (sharp.current) sharp.current.style.display = 'none';
        const k = BG_W / vp1.width;
        const c = bg.current!;
        c.width = Math.round(vp1.width * k);
        c.height = Math.round(vp1.height * k);
        bgTask = page.render({ canvasContext: c.getContext('2d')!, viewport: page.getViewport({ scale: k }) });
        const th = textHost.current!;
        th.replaceChildren();
        textLayer = new pdfjs.TextLayer({ textContentSource: page.streamTextContent(), container: th, viewport: vp1 });
        setSize({ pw: vp1.width, ph: vp1.height });
        await Promise.all([bgTask.promise, textLayer.render()]);
        if (!dead) setStatus('ready');
      } catch (e) {
        if (dead || (e as Error)?.name === 'RenderingCancelledException') return;
        setErr(e instanceof Error ? e.message : String(e));
        setStatus('error');
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

  // wheel zoom (non-passive so the page does not scroll)
  useEffect(() => {
    const st = stage.current;
    if (!st) return;
    const onWheel = (e: WheelEvent) => {
      if (!pageRef.current) return;
      e.preventDefault();
      const r = st.getBoundingClientRect();
      zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * 0.0022));
    };
    st.addEventListener('wheel', onWheel, { passive: false });
    return () => st.removeEventListener('wheel', onWheel);
  }, [zoomAt]);

  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const drag = useRef<{ x: number; y: number; tx: number; ty: number; d?: number } | null>(null);
  const onPointerDown = (e: React.PointerEvent) => {
    if (textMode || (e.target as HTMLElement).closest('[data-pdf-tools]')) return;
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
  const hasRects = (source?.rects ?? []).length > 0;

  return (
    <div className={`flex flex-col min-h-0 min-w-0 h-full bg-[#262a32] ${className ?? ''}`}>
      {source && !bare && (
        <div className="px-3 py-2 border-b border-white/[0.1] bg-[#2d3139]/80 flex-shrink-0">
          <div className="text-[11px] font-semibold text-zinc-100 truncate">{source.label ?? `Page ${source.page}`}</div>
          {source.sub && <div className="mono text-[10px] text-zinc-500 mt-0.5 truncate">{source.sub}</div>}
        </div>
      )}
      <div
        ref={stage}
        className={`relative flex-1 min-h-[220px] overflow-hidden bg-[#1e2127] ${
          textMode ? 'cursor-text' : 'cursor-grab active:cursor-grabbing'
        }`}
        style={{ touchAction: textMode ? 'auto' : 'none' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div
          ref={world}
          className="absolute left-0 top-0 origin-top-left bg-white shadow-[0_12px_40px_rgba(0,0,0,0.65)]"
          style={size ? { width: size.pw, height: size.ph } : { display: 'none' }}
        >
          <canvas ref={bg} className="absolute left-0 top-0" style={size ? { width: size.pw, height: size.ph } : undefined} />
          <canvas ref={sharp} className="absolute left-0 top-0 hidden" />
          <div ref={textHost} className={`textLayer pdf-text-layer ${textMode ? 'pointer-events-auto select-text' : 'pointer-events-none'}`} />
          {size && (
            <svg
              className="absolute left-0 top-0 pointer-events-none overflow-visible"
              viewBox={`0 0 ${size.pw} ${size.ph}`}
              width={size.pw}
              height={size.ph}
              aria-hidden="true"
            >
              {(source?.rects ?? []).map((r, i) => (
                <rect
                  key={i}
                  x={r[0] - pad}
                  y={r[1] - pad}
                  width={r[2] - r[0] + 2 * pad}
                  height={r[3] - r[1] + 2 * pad}
                  rx={pad}
                  fill="rgba(250, 204, 21, 0.38)"
                  stroke="#d97706"
                  strokeWidth={hlWidth}
                />
              ))}
            </svg>
          )}
        </div>

        {source && (
          <div data-pdf-tools className="absolute right-2 top-2 flex items-center gap-1 flex-wrap justify-end" role="toolbar" aria-label="Page tools">
            <button type="button" className={toolBtn} title="Zoom in" aria-label="Zoom in" onClick={() => center(1.6)}>
              <Plus className="w-3 h-3" />
            </button>
            <button type="button" className={toolBtn} title="Zoom out" aria-label="Zoom out" onClick={() => center(1 / 1.6)}>
              <Minus className="w-3 h-3" />
            </button>
            {hasRects && (
              <button type="button" className={toolBtn} title="Zoom to the highlighted evidence" onClick={refocus}>
                <Focus className="w-3 h-3 text-amber-300" />
                Evidence
              </button>
            )}
            <button type="button" className={toolBtn} title="Whole page" onClick={refit}>
              <Maximize className="w-3 h-3" />
              Page
            </button>
            <button
              type="button"
              className={`${toolBtn} ${textMode ? '!bg-indigo-500/25 !text-indigo-200 !border-indigo-400/40' : ''}`}
              aria-pressed={textMode}
              title="Select and copy text (turns off drag to pan)"
              onClick={() => setTextMode((v) => !v)}
            >
              <TextCursor className="w-3 h-3" />
              Text
            </button>
            <a className={toolBtn} target="_blank" rel="noopener noreferrer" title="Open the original PDF at this page" href={`${source.url}#page=${source.page}`}>
              <ExternalLink className="w-3 h-3" />
              PDF
            </a>
          </div>
        )}

        {!source && (
          <div className="absolute inset-0 grid place-items-center p-6 text-center text-xs text-zinc-500">
            {emptyText ?? 'Pick a calculation or a link to open its original page here.'}
          </div>
        )}
        {source && status === 'loading' && (
          <div className="absolute left-2 bottom-2 mono text-[10px] text-zinc-300 bg-[#2d3139]/92 border border-white/[0.12] rounded-lg px-2 py-1 flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin text-indigo-300" />
            Loading page…
          </div>
        )}
        {source && status === 'error' && (
          <div role="alert" className="absolute left-2 bottom-2 right-2 text-[11px] text-rose-200 bg-rose-500/15 border border-rose-400/35 rounded-lg px-2.5 py-1.5">
            Could not open the page: {err}
          </div>
        )}
      </div>
    </div>
  );
});
