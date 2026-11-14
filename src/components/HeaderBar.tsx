import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowLeftRight,
  Box,
  Calculator,
  ChevronDown,
  CircleDot,
  Database,
  Download,
  FileJson,
  FileText,
  Flame,
  GitCompareArrows,
  Loader2,
  Minimize2,
  Network,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import type { ColorMode, DatabaseDiffSummary, ProjectSource, WorkspaceView } from '../types/bim';

interface HeaderBarProps {
  projectName: string;
  subtitle: string;
  activeView: WorkspaceView;
  onChangeView: (view: WorkspaceView) => void;
  calcCount: number;
  colorMode: ColorMode;
  onChangeColorMode: (m: ColorMode) => void;
  hasUtilization: boolean;
  backend: 'checking' | 'online' | 'offline';
  source: ProjectSource | null;
  busy: boolean;
  onLoadSample: () => void;
  onUploadModel: (file: File) => void;
  onUploadCalcs: (file: File) => void;
  /** open an IFC / element graph / ModelInput / calc-graph export in the browser only */
  onOpenFile: (file: File) => void;
  exportUrl: string | null;
  diffSummary: DatabaseDiffSummary | null;
  compareOpen: boolean;
  onToggleCompare: () => void;
  onSwapDatabases: () => void;
  onClearDiff: () => void;
  onResetAll: () => void;
}

const viewBtn = (active: boolean) =>
  `flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
    active
      ? 'bg-indigo-600/25 text-white border border-indigo-400/40 shadow-[0_0_16px_rgba(99,102,241,0.25)]'
      : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
  }`;

const chromeBtn =
  'bg-white/[0.04] hover:bg-white/[0.08] active:bg-white/[0.1] text-zinc-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14] disabled:opacity-40 disabled:cursor-not-allowed';

const COLOR_MODES: { id: ColorMode; label: string; title: string }[] = [
  { id: 'type', label: 'Type', title: 'Colour elements by IFC type' },
  { id: 'review', label: 'Review', title: 'Colour elements by mapping status: mapped / needs review / no calc found' },
  { id: 'confidence', label: 'Confidence', title: 'Colour elements by the confidence of their strongest calc link' },
];

export const HeaderBar: React.FC<HeaderBarProps> = (p) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const modelInput = useRef<HTMLInputElement | null>(null);
  const calcInput = useRef<HTMLInputElement | null>(null);
  const openInput = useRef<HTMLInputElement | null>(null);
  const online = p.backend === 'online';

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    window.addEventListener('pointerdown', onDown);
    return () => window.removeEventListener('pointerdown', onDown);
  }, [menuOpen]);

  const pick = (ref: React.RefObject<HTMLInputElement>) => {
    setMenuOpen(false);
    ref.current?.click();
  };
  const fileInput = (ref: React.RefObject<HTMLInputElement>, accept: string, onFile: (f: File) => void) => (
    <input
      ref={ref}
      type="file"
      accept={accept}
      className="sr-only"
      onChange={(e) => {
        const f = e.target.files?.[0];
        if (f) onFile(f);
        e.target.value = '';
      }}
    />
  );

  const menuItem = (icon: React.ReactNode, label: string, sub: string, onClick: () => void, disabled = false) => (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="w-full text-left flex items-start gap-2.5 px-2.5 py-2 rounded-lg hover:bg-white/[0.06] transition disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <span className="mt-0.5">{icon}</span>
      <span className="min-w-0">
        <span className="block text-xs font-medium text-zinc-100">{label}</span>
        <span className="block text-[10.5px] text-zinc-500 leading-snug">{sub}</span>
      </span>
    </button>
  );

  return (
    <header className="apple-glass-chrome border-b border-white/[0.12] px-5 py-2.5 flex items-center justify-between gap-4 shadow-[0_8px_32px_rgba(0,0,0,0.85)] z-30 flex-shrink-0">
      <div className="flex items-center space-x-3.5 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500/20 to-cyan-500/10 border border-indigo-400/30 text-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.2)] flex items-center justify-center flex-shrink-0">
          <Network className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <h1 className="font-semibold text-[13px] text-white tracking-tight flex items-center gap-2 truncate">
            <span className="truncate">{p.projectName}</span>
            {p.diffSummary ? (
              <span className="mono text-[10px] font-semibold bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-400/35 tracking-wider flex-shrink-0">
                DIFF MODE
              </span>
            ) : p.source === 'file' || p.source === 'local' ? (
              <span
                title={p.source === 'file' ? 'Opened from an export JSON file: read-only' : 'Opened in the browser, not uploaded: no calcs, read-only'}
                className="mono text-[10px] font-medium bg-white/[0.06] text-zinc-300 px-2 py-0.5 rounded border border-white/[0.16] tracking-wider flex-shrink-0"
              >
                {p.source === 'file' ? 'OFFLINE EXPORT' : 'LOCAL · NOT UPLOADED'}
              </span>
            ) : null}
          </h1>
          <p className="mono text-[10px] text-zinc-500 tracking-wide mt-0.5 truncate">
            {p.diffSummary ? `A: ${p.diffSummary.baseName}  ↔  B: ${p.diffSummary.compareName}` : p.subtitle}
          </p>
        </div>
      </div>

      <nav aria-label="Primary Workspace Views" className="flex items-center bg-[#1e2127]/80 p-1 rounded-xl border border-white/[0.14] shadow-inner flex-shrink-0">
        <button type="button" onClick={() => p.onChangeView('element-graph')} className={viewBtn(p.activeView === 'element-graph')}>
          <CircleDot className="w-3.5 h-3.5 text-emerald-400" />
          <span>Element Graph</span>
        </button>
        <button type="button" onClick={() => p.onChangeView('calculation-graph')} className={viewBtn(p.activeView === 'calculation-graph')}>
          <Calculator className="w-3.5 h-3.5 text-amber-400" />
          <span>Calculation Graph</span>
          <span className="mono text-[10px] px-1.5 rounded bg-white/[0.06] text-zinc-400">{p.calcCount}</span>
        </button>
        <button type="button" onClick={() => p.onChangeView('3d')} className={viewBtn(p.activeView === '3d')}>
          <Box className="w-3.5 h-3.5 text-cyan-400" />
          <span>3D Model</span>
        </button>
        <button type="button" onClick={() => p.onChangeView('docs')} className={viewBtn(p.activeView === 'docs')}>
          <FileText className="w-3.5 h-3.5 text-rose-400" />
          <span>PDF Calcs</span>
        </button>
      </nav>

      <div className="flex items-center space-x-2 flex-shrink-0">
        {!p.diffSummary && (
          <div className="flex items-center bg-[#1e2127]/80 p-0.5 rounded-lg border border-white/[0.14]" role="group" aria-label="Colour elements by">
            {COLOR_MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                title={m.title}
                onClick={() => p.onChangeColorMode(m.id)}
                className={`mono text-[10px] px-2 py-1 rounded-md transition ${
                  p.colorMode === m.id ? 'bg-indigo-500/25 text-indigo-100 border border-indigo-400/40' : 'text-zinc-400 hover:text-zinc-200 border border-transparent'
                }`}
              >
                {m.label}
              </button>
            ))}
            <button
              type="button"
              disabled={!p.hasUtilization}
              onClick={() => p.onChangeColorMode(p.colorMode === 'utilisation' ? 'type' : 'utilisation')}
              title={
                p.hasUtilization
                  ? 'Colour elements by demand / capacity utilisation'
                  : 'No utilisation data: the loaded model and calcs carry no demand / capacity values yet'
              }
              className={`mono text-[10px] px-2 py-1 rounded-md transition flex items-center gap-1 disabled:opacity-35 disabled:cursor-not-allowed ${
                p.colorMode === 'utilisation' ? 'bg-amber-500/20 text-amber-200 border border-amber-400/40' : 'text-zinc-400 hover:text-zinc-200 border border-transparent'
              }`}
            >
              <Flame className="w-3 h-3 text-amber-400" />
              <span className="hidden 2xl:inline">Heatmap</span>
            </button>
          </div>
        )}

        <div className="relative" ref={menuRef}>
          <button type="button" onClick={() => setMenuOpen((v) => !v)} className={`${chromeBtn} hover:border-indigo-400/40`} aria-expanded={menuOpen}>
            {p.busy ? <Loader2 className="w-3.5 h-3.5 text-indigo-300 animate-spin" /> : <Upload className="w-3.5 h-3.5 text-indigo-400" />}
            <span>Import</span>
            <ChevronDown className="w-3 h-3 text-zinc-500" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-2 w-72 bg-[#2d3139]/96 backdrop-blur-2xl border border-white/[0.14] rounded-xl p-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.85)] z-50">
              {menuItem(<Sparkles className="w-3.5 h-3.5 text-indigo-300" />, 'Load sample', 'Synthetic office building + its calc package', () => {
                setMenuOpen(false);
                p.onLoadSample();
              }, !online || p.busy)}
              {menuItem(<Box className="w-3.5 h-3.5 text-cyan-300" />, 'Upload IFC model', 'Parsed in the browser, uploaded with its element graph; links re-mapped', () => pick(modelInput), !online || p.busy)}
              {menuItem(<FileText className="w-3.5 h-3.5 text-rose-300" />, 'Upload calc package PDF', 'New calc revision; links are re-mapped', () => pick(calcInput), !online || p.busy)}
              <div className="h-px bg-white/[0.08] my-1" />
              {menuItem(<FileJson className="w-3.5 h-3.5 text-amber-300" />, 'Open file in browser', 'IFC, element graph or saved export JSON; read-only, not uploaded', () => pick(openInput))}
              {p.exportUrl &&
                menuItem(<Download className="w-3.5 h-3.5 text-zinc-300" />, 'Download export JSON', 'The current mapping, to share or open offline', () => {
                  setMenuOpen(false);
                  window.open(p.exportUrl!, '_blank', 'noopener');
                })}
              {!online && (
                <p className="mono text-[9.5px] text-zinc-500 px-2.5 py-1.5 leading-snug">
                  {p.backend === 'checking' ? 'Checking the backend…' : 'Backend offline at /api: uploads and the sample need it.'}
                </p>
              )}
            </div>
          )}
        </div>
        {fileInput(modelInput, '.ifc', p.onUploadModel)}
        {fileInput(calcInput, '.pdf,application/pdf', p.onUploadCalcs)}
        {fileInput(openInput, '.ifc,.json,application/json', p.onOpenFile)}

        {p.diffSummary && (
          <button type="button" onClick={p.onSwapDatabases} title="Swap base revision (A) and compare revision (B)" className="bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-200 px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-indigo-400/35">
            <ArrowLeftRight className="w-3.5 h-3.5 text-indigo-300" />
            <span className="hidden xl:inline">Swap A↔B</span>
          </button>
        )}

        <button
          type="button"
          onClick={p.onToggleCompare}
          disabled={!online || p.source !== 'api'}
          title={online ? 'Compare two model revisions across the graph, 3D and calcs' : 'Revision compare needs the backend'}
          className={
            p.diffSummary || p.compareOpen
              ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-amber-400/45 shadow-[0_0_14px_rgba(245,158,11,0.2)]'
              : `${chromeBtn} hover:border-amber-400/40`
          }
        >
          <GitCompareArrows className="w-3.5 h-3.5 text-amber-400" />
          <span>{p.diffSummary ? `Rev ${p.diffSummary.baseRevisionId} → ${p.diffSummary.compareRevisionId}` : 'Revisions'}</span>
        </button>

        {p.diffSummary && (
          <button type="button" onClick={p.onClearDiff} title="Exit diff mode" className="bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-rose-400/35">
            <X className="w-3.5 h-3.5" />
            <span className="hidden xl:inline">Exit Diff</span>
          </button>
        )}

        <span
          title={p.backend === 'online' ? 'Backend online' : p.backend === 'checking' ? 'Checking backend' : 'Backend offline'}
          className="flex items-center gap-1.5 mono text-[10px] text-zinc-500 px-1"
        >
          <Database className="w-3.5 h-3.5" />
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              p.backend === 'online' ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : p.backend === 'checking' ? 'bg-zinc-500 animate-pulse' : 'bg-rose-500'
            }`}
          />
        </span>

        <button type="button" onClick={p.onResetAll} title="Reset view, filters & panels" className={chromeBtn}>
          <Minimize2 className="w-3.5 h-3.5 text-zinc-400" />
        </button>
      </div>
    </header>
  );
};
