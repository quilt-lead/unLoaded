// Revisions of the project (model + calc package) and the compare picker: base A vs compare B,
// both model revisions; the diff itself is the calc engine's diffGraphs (src/engine/).
import React, { useEffect, useState } from 'react';
import { Box, ExternalLink, FileText, GitCompareArrows, Loader2, Sparkles, Upload, X } from 'lucide-react';
import type { RevisionInfo } from '../types/bim';
import { useEscapeLayer } from './escapeStack';

interface RevisionPanelProps {
  revisions: RevisionInfo[] | null;
  loading: boolean;
  active: { a: number; b: number } | null;
  busy: boolean;
  onOpenRevisionFile: (rid: number) => void;
  onCompare: (a: number, b: number) => void;
  onLoadSampleRev2: () => void;
  onLoadSupplement: () => void;
  onUploadModel: (file: File) => void;
  onClose: () => void;
}

/** "11-14 16:41 ET": stored times carry their own Eastern offset */
const shortTime = (iso: string) => `${iso.slice(5, 16).replace('T', ' ')} ET`;

export const RevisionPanel: React.FC<RevisionPanelProps> = ({ revisions, loading, active, busy, onOpenRevisionFile, onCompare, onLoadSampleRev2, onLoadSupplement, onUploadModel, onClose }) => {
  const models = (revisions ?? []).filter((r) => r.kind === 'model');
  const calcs = (revisions ?? []).filter((r) => r.kind === 'calcs');
  const [a, setA] = useState<number | null>(active?.a ?? null);
  const [b, setB] = useState<number | null>(active?.b ?? null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  // open while mounted: Escape closes this panel (and does nothing else)
  useEscapeLayer(true, onClose);

  // default: the head as B, the revision before it as A
  useEffect(() => {
    if (active || models.length < 2) return;
    setB((cur) => cur ?? models[0].id);
    setA((cur) => cur ?? models[1].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [models.length, active]);

  const radio = (checked: boolean, onChange: () => void, label: string) => (
    <button
      type="button"
      onClick={onChange}
      aria-pressed={checked}
      aria-label={label}
      className={`w-5 h-5 rounded-md border mono text-[9px] font-bold flex items-center justify-center transition ${
        checked ? 'bg-amber-500/30 border-amber-400/60 text-amber-100' : 'border-white/[0.16] text-zinc-600 hover:text-zinc-300'
      }`}
    >
      {label.slice(-1)}
    </button>
  );

  return (
    <div className="fixed right-4 top-[58px] w-[400px] max-w-[calc(100vw-32px)] max-h-[calc(100vh-80px)] overflow-y-auto bg-[#2d3139]/96 backdrop-blur-2xl border border-white/[0.14] rounded-2xl shadow-[0_24px_60px_rgba(0,0,0,0.9)] z-50">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08]">
        <span className="text-xs font-semibold text-white flex items-center gap-2">
          <GitCompareArrows className="w-3.5 h-3.5 text-amber-400" />
          Revisions & compare
        </span>
        <button type="button" onClick={onClose} className="text-zinc-500 hover:text-zinc-200 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-white/[0.06]" aria-label="Close">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {loading && (
          <p className="mono text-[10px] text-zinc-400 flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin" /> Loading revisions…
          </p>
        )}

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <p className="mono text-[10px] font-semibold text-cyan-400 uppercase tracking-wider flex items-center gap-1">
              <Box className="w-3 h-3" /> Model revisions ({models.length})
            </p>
            <span className="mono text-[9px] text-zinc-500">A = base · B = compare</span>
          </div>
          <div className="space-y-1">
            {models.map((r) => (
              <div key={r.id} className={`flex items-center gap-2 px-2 py-1.5 rounded-lg border ${a === r.id || b === r.id ? 'bg-amber-500/[0.06] border-amber-400/25' : 'bg-white/[0.02] border-white/[0.06]'}`}>
                {radio(a === r.id, () => setA(r.id), `Base A`)}
                {radio(b === r.id, () => setB(r.id), `Compare B`)}
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] text-zinc-100 truncate">
                    <span className="mono text-zinc-500 mr-1">#{r.id}</span>
                    {r.label}
                  </div>
                  <div className="mono text-[9px] text-zinc-500">
                    {shortTime(r.createdAt)}
                    {r.count != null ? ` · ${r.count} elements` : ''}
                  </div>
                </div>
                {r.isHead && <span className="mono text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">head</span>}
              </div>
            ))}
            {!loading && models.length === 0 && <p className="text-[11px] text-zinc-500 italic">No model revisions yet.</p>}
          </div>
          <div className="flex items-center gap-1.5 mt-2.5">
            <button
              type="button"
              disabled={a == null || b == null || a === b}
              onClick={() => a != null && b != null && onCompare(a, b)}
              className="flex-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 border border-amber-400/45 rounded-lg py-1.5 text-[11px] font-semibold transition flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <GitCompareArrows className="w-3.5 h-3.5" />
              {a != null && b != null && a !== b ? `Compare #${a} → #${b}` : 'Pick two revisions'}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              title="Add another IFC (or JSON model) as a new model revision; it becomes the head"
              className="bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border border-white/[0.14] flex items-center gap-1.5 disabled:opacity-40"
            >
              <Upload className="w-3 h-3 text-indigo-400" />
              Add rev
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".ifc,.json,application/json"
              className="sr-only"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUploadModel(f);
                e.target.value = '';
              }}
            />
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={onLoadSampleRev2}
            className="mt-1.5 w-full bg-white/[0.03] hover:bg-white/[0.07] text-zinc-300 border border-white/[0.1] rounded-lg py-1.5 text-[11px] transition flex items-center justify-center gap-1.5 disabled:opacity-40"
          >
            <Sparkles className="w-3 h-3 text-indigo-300" />
            Ingest sample rev 2 (column C8 removed)
          </button>
        </div>

        <div>
          <p className="mono text-[10px] font-semibold text-rose-400 uppercase tracking-wider flex items-center gap-1 mb-1.5">
            <FileText className="w-3 h-3" /> Calc package revisions ({calcs.length})
          </p>
          <div className="space-y-1">
            {calcs.map((r) => (
              <div key={r.id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] text-zinc-100 truncate">
                    <span className="mono text-zinc-500 mr-1">#{r.id}</span>
                    {r.label}
                  </div>
                  <div className="mono text-[9px] text-zinc-500">
                    {shortTime(r.createdAt)}
                    {r.count != null ? ` · ${r.count} calcs` : ''}
                  </div>
                </div>
                {r.isHead && <span className="mono text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">head</span>}
                <button
                  type="button"
                  onClick={() => onOpenRevisionFile(r.id)}
                  aria-label={`Open the PDF of calc revision ${r.id}`}
                  title="Open this revision's PDF"
                  className="text-zinc-400 hover:text-white w-6 h-6 rounded-md flex items-center justify-center hover:bg-white/[0.06] focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                >
                  <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>
            ))}
            {!loading && calcs.length === 0 && <p className="text-[11px] text-zinc-500 italic">No calc package revisions yet.</p>}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={onLoadSupplement}
            className="mt-1.5 w-full bg-white/[0.03] hover:bg-white/[0.07] text-zinc-300 border border-white/[0.1] rounded-lg py-1.5 text-[11px] transition flex items-center justify-center gap-1.5 disabled:opacity-40"
          >
            <Sparkles className="w-3 h-3 text-indigo-300" aria-hidden="true" />
            Add sample calc supplement (roles, typical group, size mismatch)
          </button>
        </div>

        <p className="text-[10.5px] text-zinc-500 leading-snug border-t border-white/[0.06] pt-3">
          The graphs, links and calcs always show the head revisions (each added file becomes the head). A compare colours the head model by what changed between A and B; elements only in
          the other revision are drawn as ghosts from that revision's IFC (or its element boxes for a JSON model).
        </p>
      </div>
    </div>
  );
};
