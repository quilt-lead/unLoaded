// Drawing evidence for the selected element: where it is printed on its drawing set (plan tag, schedule row,
// elevation tag, ...), as a crop of the sheet with the box drawn on it, the drawing-side twin of the calc
// evidence. Shown by the inspector on plain selection (3D, plan, graph); clicking the crop opens the whole sheet
// at that box. Renders nothing when the element has no occurrence on a loaded drawing PDF (every IFC element).
import React, { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronLeft, ChevronRight, Maximize2, PencilRuler, X } from 'lucide-react';
import { PdfPage } from '../pdf/PdfPage';
import { useEscapeLayer } from '../escapeStack';
import { cropAround, HOW_LABEL, readOccurrences, shownOccurrences, type DrawingOccurrence } from '../../data/drawingOccurrences';

type Shown = DrawingOccurrence & { url: string };

interface DrawingEvidenceProps {
  /** the element's params (Drawing.Occurrences is read from them) */
  params: Record<string, string> | undefined;
  /** the element's label, for the sheet dialog's title */
  elementLabel: string;
  /** drawing PDFs of the model on screen, by file name; empty / absent for an IFC model */
  drawingUrls: Record<string, string> | undefined;
}

const iconBtn =
  'w-6 h-6 rounded-md flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/[0.08] disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap transition-colors';

const occLabel = (o: DrawingOccurrence) => `${o.sheet || `p. ${o.page}`} · ${HOW_LABEL[o.how]}${o.text ? ` · ${o.text}` : ''}`;

export const DrawingEvidence: React.FC<DrawingEvidenceProps> = ({ params, elementLabel, drawingUrls }) => {
  const occ = shownOccurrences(readOccurrences(params), drawingUrls);
  const [idx, setIdx] = useState(0);
  const [open, setOpen] = useState(false);
  const cropBtn = useRef<HTMLButtonElement>(null);
  if (!occ.length) return null;
  const i = Math.min(idx, occ.length - 1);
  const o = occ[i]!;
  const grid = params?.['Drawing.Grid'];
  const step = (d: number) => setIdx((i + d + occ.length) % occ.length);

  return (
    <div className="border-t border-white/[0.07] pt-2.5">
      <div className="flex items-center justify-between mb-1.5 gap-2">
        <p className="mono text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1 text-sky-300">
          <PencilRuler className="w-3 h-3" aria-hidden="true" />
          On the drawings ({occ.length})
        </p>
        {occ.length > 1 && (
          <div className="flex items-center gap-0.5">
            <button type="button" className={iconBtn} aria-label="Previous occurrence" onClick={() => step(-1)}>
              <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
            <span className="mono text-[9.5px] text-zinc-400 tabular-nums min-w-[2.25rem] text-center" aria-live="polite">
              {i + 1} / {occ.length}
            </span>
            <button type="button" className={iconBtn} aria-label="Next occurrence" onClick={() => step(1)}>
              <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      <button
        ref={cropBtn}
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Open sheet ${o.sheet || `page ${o.page}`} at the ${HOW_LABEL[o.how].toLowerCase()} ${o.text}`}
        className="group relative block w-full h-[200px] rounded-lg overflow-hidden border border-sky-400/25 hover:border-sky-300/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap transition-colors text-left"
      >
        {/* a static crop: panning and zoom live in the sheet view this button opens */}
        <div className="absolute inset-0 pointer-events-none">
          <PdfPage bare tools={false} minSpan={200} source={{ url: o.url, page: o.page, rects: [o.rect], focus: cropAround(o.rect) }} />
        </div>
        <span className="absolute right-1.5 top-1.5 mono text-[9px] px-1.5 py-0.5 rounded bg-black/70 text-zinc-200 border border-white/[0.12] flex items-center gap-1 opacity-80 group-hover:opacity-100 group-focus-visible:opacity-100">
          <Maximize2 className="w-2.5 h-2.5" aria-hidden="true" />
          Sheet
        </span>
      </button>

      <div className="mt-1.5 flex items-baseline gap-1.5 min-w-0">
        <span className="mono text-[11px] font-semibold text-zinc-100 flex-shrink-0">{o.sheet || `p. ${o.page}`}</span>
        <span className="mono text-[9px] px-1 py-px rounded bg-sky-500/10 text-sky-200 border border-sky-400/25 flex-shrink-0">{HOW_LABEL[o.how]}</span>
        <span className="mono text-[10px] text-zinc-300 truncate" title={o.text}>
          {o.text}
        </span>
      </div>
      <p className="mono text-[9px] text-zinc-500 mt-0.5 truncate" title={o.file}>
        p. {o.page}
        {grid ? ` · grid ${grid}` : ''} · {o.file}
      </p>

      {occ.length > 1 && (
        <ul className="mt-1.5 space-y-0.5" aria-label="Occurrences on the drawings">
          {occ.map((x, k) => (
            <li key={`${x.page}:${x.rect.join(',')}`}>
              <button
                type="button"
                aria-current={k === i ? 'true' : undefined}
                onClick={() => setIdx(k)}
                className={`w-full text-left px-2 py-1 rounded-md mono text-[9.5px] truncate border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap ${
                  k === i ? 'bg-sky-500/[0.12] border-sky-400/30 text-sky-100' : 'bg-white/[0.02] border-white/[0.06] text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.06]'
                }`}
                title={occLabel(x)}
              >
                {occLabel(x)}
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && (
        <SheetDialog
          occ={occ}
          index={i}
          elementLabel={elementLabel}
          onIndex={setIdx}
          onClose={() => {
            setOpen(false);
            requestAnimationFrame(() => cropBtn.current?.focus());
          }}
        />
      )}
    </div>
  );
};

/** The whole sheet, zoomed to the occurrence's box (Page shows the sheet), with stepping through the element's occurrences. */
const SheetDialog: React.FC<{ occ: Shown[]; index: number; elementLabel: string; onIndex: (i: number) => void; onClose: () => void }> = ({
  occ,
  index,
  elementLabel,
  onIndex,
  onClose,
}) => {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  useEscapeLayer(true, onClose);
  useEffect(() => closeBtn.current?.focus(), []);
  const o = occ[index]!;
  const step = (d: number) => onIndex((index + d + occ.length) % occ.length);

  // keep Tab inside the dialog
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== 'Tab' || !panel.current) return;
    const f = [...panel.current.querySelectorAll<HTMLElement>('button, a[href], [tabindex]:not([tabindex="-1"])')].filter((x) => !x.hasAttribute('disabled'));
    if (!f.length) return;
    const first = f[0]!;
    const last = f[f.length - 1]!;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[80] overscroll-contain bg-black/60 backdrop-blur-sm p-3 sm:p-6 flex" onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onKeyDown}
        className="flex-1 min-w-0 flex flex-col bg-[#2d3139] border border-white/[0.14] rounded-xl overflow-hidden shadow-[0_24px_60px_rgba(0,0,0,0.8)]"
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.1] flex-shrink-0">
          <PencilRuler className="w-3.5 h-3.5 text-sky-300 flex-shrink-0" aria-hidden="true" />
          <h2 id={titleId} className="text-xs font-semibold text-zinc-100 truncate min-w-0">
            {elementLabel}
            <span className="mono font-normal text-zinc-400"> · {occLabel(o)} · p. {o.page}</span>
          </h2>
          <div className="ml-auto flex items-center gap-0.5 flex-shrink-0">
            {occ.length > 1 && (
              <>
                <button type="button" className={iconBtn} aria-label="Previous occurrence" onClick={() => step(-1)}>
                  <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
                <span className="mono text-[10px] text-zinc-400 tabular-nums min-w-[2.5rem] text-center" aria-live="polite">
                  {index + 1} / {occ.length}
                </span>
                <button type="button" className={iconBtn} aria-label="Next occurrence" onClick={() => step(1)}>
                  <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </>
            )}
            <button ref={closeBtn} type="button" className={`${iconBtn} ml-1`} aria-label="Close sheet" onClick={onClose}>
              <X className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
        <div className="flex-1 min-h-0">
          <PdfPage bare source={{ url: o.url, page: o.page, rects: [o.rect], focus: o.rect }} />
        </div>
      </div>
    </div>,
    document.body,
  );
};
