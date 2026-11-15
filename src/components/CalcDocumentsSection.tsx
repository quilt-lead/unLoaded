// The calc documents of the project, in the revision panel: each logical PDF with its revisions
// (newest first; the head is what the calc set maps), where an upload landed and how to move it,
// withdrawing a document from the set, and what changed between a document's last two revisions.
import React, { useRef, useState } from 'react';
import { ExternalLink, FileText, GitCompareArrows, Loader2, Undo2, Upload, EyeOff } from 'lucide-react';
import type { CalcDocumentInfo, CalcRevisionDiffView } from '../types/bim';
import { useCalcCompare } from '../engine/hooks';

interface CalcDocumentsSectionProps {
  projectId: string | null;
  documents: CalcDocumentInfo[];
  loading: boolean;
  busy: boolean;
  onOpenRevisionFile: (rid: number) => void;
  onAddCalcs: (files: File[]) => void;
  onMoveRevision: (revisionId: number, docId: string | 'new') => void;
  onSetRemoved: (docId: string, removed: boolean) => void;
}

const shortTime = (iso: string) => `${iso.slice(5, 16).replace('T', ' ')} ET`;
const iconBtn =
  'text-zinc-400 hover:text-white w-6 h-6 rounded-md flex items-center justify-center hover:bg-white/[0.06] focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 disabled:opacity-40';

export const CalcDocumentsSection: React.FC<CalcDocumentsSectionProps> = ({ projectId, documents, loading, busy, onOpenRevisionFile, onAddCalcs, onMoveRevision, onSetRemoved }) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [comparing, setComparing] = useState<string | null>(null);
  const live = documents.filter((d) => !d.removed).length;

  return (
    <section aria-labelledby="calc-docs-heading">
      <div className="flex items-center justify-between mb-1.5">
        <h3 id="calc-docs-heading" className="mono text-[10px] font-semibold text-rose-400 uppercase tracking-wider flex items-center gap-1">
          <FileText className="w-3 h-3" aria-hidden="true" /> Calc documents ({documents.length})
        </h3>
        <span className="mono text-[9px] text-zinc-500">{live} in the calc set</span>
      </div>

      <ul className="space-y-1.5" role="list">
        {documents.map((d) => (
          <li key={d.docId} className={`rounded-lg border ${d.removed ? 'border-dashed border-white/[0.1] bg-transparent' : 'border-white/[0.06] bg-white/[0.02]'}`}>
            <div className="flex items-center gap-2 px-2 pt-1.5">
              <div className="min-w-0 flex-1">
                <div className={`text-[11px] font-semibold truncate ${d.removed ? 'text-zinc-500 line-through' : 'text-zinc-100'}`}>{d.name}</div>
                <div className="mono text-[9px] text-zinc-500">
                  {d.docId} · {d.revisions.length} revision{d.revisions.length === 1 ? '' : 's'}
                  {d.removed ? ' · withdrawn: not mapped' : ''}
                </div>
              </div>
              {d.revisions.length > 1 && (
                <button
                  type="button"
                  className={iconBtn}
                  aria-pressed={comparing === d.docId}
                  aria-label={`Compare the last two revisions of ${d.name}`}
                  title="What changed: previous revision → head"
                  onClick={() => setComparing((c) => (c === d.docId ? null : d.docId))}
                >
                  <GitCompareArrows className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              )}
              <button
                type="button"
                className={iconBtn}
                disabled={busy}
                aria-label={d.removed ? `Restore ${d.name} to the calc set` : `Withdraw ${d.name} from the calc set`}
                title={d.removed ? 'Restore to the calc set' : 'Withdraw from the calc set (kept, not mapped)'}
                onClick={() => onSetRemoved(d.docId, !d.removed)}
              >
                {d.removed ? <Undo2 className="w-3.5 h-3.5" aria-hidden="true" /> : <EyeOff className="w-3.5 h-3.5" aria-hidden="true" />}
              </button>
            </div>

            <ul className="px-2 pb-1.5 pt-1 space-y-0.5" role="list" aria-label={`Revisions of ${d.name}`}>
              {d.revisions.map((r) => (
                <li key={r.id} className="flex items-center gap-2 pl-2 border-l border-white/[0.08]">
                  <div className="min-w-0 flex-1">
                    <div className="text-[10.5px] text-zinc-200 truncate">
                      <span className="mono text-zinc-500 mr-1">#{r.id}</span>
                      {r.label}
                    </div>
                    <div className="mono text-[9px] text-zinc-500">
                      {shortTime(r.createdAt)}
                      {r.count != null ? ` · ${r.count} calcs` : ''}
                    </div>
                  </div>
                  {r.isHead && !d.removed && (
                    <span className="mono text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">head</span>
                  )}
                  <label className="sr-only" htmlFor={`move-${r.id}`}>Move revision {r.id} to</label>
                  <select
                    id={`move-${r.id}`}
                    disabled={busy}
                    value=""
                    title="Placed in the wrong document? Move it"
                    onChange={(e) => e.target.value && onMoveRevision(r.id, e.target.value)}
                    className="mono text-[9px] bg-white/[0.04] border border-white/[0.12] rounded-md text-zinc-300 px-1 py-0.5 max-w-[84px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 disabled:opacity-40"
                  >
                    <option value="">Move…</option>
                    {documents.filter((o) => o.docId !== d.docId).map((o) => (
                      <option key={o.docId} value={o.docId}>to {o.name}</option>
                    ))}
                    {d.revisions.length > 1 && <option value="new">to a new document</option>}
                  </select>
                  <button type="button" className={iconBtn} onClick={() => onOpenRevisionFile(r.id)} aria-label={`Open the PDF of calc revision ${r.id}`} title="Open this revision's PDF">
                    <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>

            {comparing === d.docId && d.revisions.length > 1 && (
              <CalcDiff projectId={projectId} a={d.revisions[1]!.id} b={d.revisions[0]!.id} />
            )}
          </li>
        ))}
        {!loading && documents.length === 0 && <li className="text-[11px] text-zinc-500 italic">No calc PDFs yet.</li>}
      </ul>

      <button
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        className="mt-1.5 w-full bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 border border-white/[0.14] rounded-lg py-1.5 text-[11px] font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-40"
      >
        <Upload className="w-3 h-3 text-rose-300" aria-hidden="true" />
        Add calc PDFs (one package, or one per calc)
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,application/pdf"
        className="sr-only"
        aria-label="Add calc PDFs"
        onChange={(e) => {
          const fs = [...(e.target.files ?? [])];
          if (fs.length) onAddCalcs(fs);
          e.target.value = '';
        }}
      />
    </section>
  );
};

/** Calcs added / removed / changed / moved between two revisions of one document. */
const CalcDiff: React.FC<{ projectId: string | null; a: number; b: number }> = ({ projectId, a, b }) => {
  const q = useCalcCompare(projectId, a, b);
  return (
    <div className="mx-2 mb-2 rounded-md border border-amber-400/25 bg-amber-500/[0.05] px-2 py-1.5" aria-live="polite">
      <p className="mono text-[9px] text-amber-300 mb-1">
        #{a} → #{b}
      </p>
      {q.isLoading && (
        <p className="mono text-[10px] text-zinc-400 flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" /> Comparing…
        </p>
      )}
      {q.error && <p className="text-[10.5px] text-rose-300">Could not compare: {(q.error as Error).message}</p>}
      {q.data && <CalcDiffBody d={q.data} />}
    </div>
  );
};

const LIST_MAX = 8;

const CalcDiffBody: React.FC<{ d: CalcRevisionDiffView }> = ({ d }) => {
  const total = d.added.length + d.removed.length + d.changed.length + d.moved.length;
  if (!total) return <p className="text-[10.5px] text-zinc-300">No calc changed ({d.unchanged} unchanged).</p>;
  const group = (label: string, sign: string, tone: string, rows: { key: string; title: string; note?: string }[]) =>
    rows.length > 0 && (
      <div>
        <p className={`mono text-[9px] font-semibold ${tone}`}>
          {sign} {label} ({rows.length})
        </p>
        <ul className="pl-3" role="list">
          {rows.slice(0, LIST_MAX).map((r) => (
            <li key={r.key} className="text-[10.5px] text-zinc-300 truncate" title={r.title}>
              {r.title}
              {r.note && <span className="mono text-[9px] text-zinc-500"> · {r.note}</span>}
            </li>
          ))}
          {rows.length > LIST_MAX && <li className="mono text-[9px] text-zinc-500">and {rows.length - LIST_MAX} more</li>}
        </ul>
      </div>
    );
  return (
    <div className="space-y-1">
      {group('Added', '+', 'text-emerald-300', d.added)}
      {group('Changed', '~', 'text-amber-300', d.changed.map((x) => ({ ...x, note: x.beforeTitle !== x.title ? `was "${x.beforeTitle}"` : 'text changed' })))}
      {group('Removed', '−', 'text-rose-300', d.removed)}
      {group('Moved', '↕', 'text-sky-300', d.moved.map((x) => ({ ...x, note: `p. ${x.beforePages.join(',')} → ${x.afterPages.join(',')}` })))}
      <p className="mono text-[9px] text-zinc-500">{d.unchanged} unchanged</p>
    </div>
  );
};
