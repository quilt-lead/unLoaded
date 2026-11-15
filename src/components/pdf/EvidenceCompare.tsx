// Two original pages side by side (stacked when narrow), each zoomed to its own evidence.
// Ported from the calc-graph prototype (frontend/src/components/EvidenceCompare.tsx).
import React from 'react';
import { Columns2, X } from 'lucide-react';
import { PdfPage, type PdfSource } from './PdfPage';

export interface EvidenceCompareProps {
  left: PdfSource | null;
  right: PdfSource | null;
  leftTitle: React.ReactNode;
  rightTitle: React.ReactNode;
  /** a line under the titles, e.g. what links the two pages */
  note?: React.ReactNode;
  onClose?: () => void;
}

export function EvidenceCompare({ left, right, leftTitle, rightTitle, note, onClose }: EvidenceCompareProps) {
  return (
    <div className="flex flex-col min-h-0 h-full gap-2">
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="text-xs font-semibold text-white flex items-center gap-1.5">
          <Columns2 className="w-3.5 h-3.5 text-indigo-300" />
          Evidence side by side
        </span>
        {note && <span className="mono text-[10px] text-zinc-400">{note}</span>}
        <span className="flex-1" />
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5"
          >
            <X className="w-3 h-3" />
            Back to one page
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2.5 flex-1 min-h-0">
        {[
          { src: left, title: leftTitle },
          { src: right, title: rightTitle },
        ].map((c, i) => (
          <div key={i} className="flex flex-col min-h-[320px] min-w-0 border border-white/[0.12] rounded-xl overflow-hidden">
            <div className="px-3 py-1.5 text-[11px] font-semibold text-zinc-200 bg-[#2d3139] border-b border-white/[0.1] truncate">{c.title}</div>
            <PdfPage source={c.src} bare />
          </div>
        ))}
      </div>
    </div>
  );
}
