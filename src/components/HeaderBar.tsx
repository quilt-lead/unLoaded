import React, { useRef } from 'react';
import {
  Network,
  CircleDot,
  Calculator,
  Box,
  FileText,
  Flame,
  Upload,
  Minimize2,
  GitCompareArrows,
  ArrowLeftRight,
  X,
} from 'lucide-react';
import { DatabaseDiffSummary, WorkspaceView } from '../types/bim';

interface HeaderBarProps {
  projectName: string;
  activeView: WorkspaceView;
  onChangeView: (view: WorkspaceView) => void;
  calcCount: number;
  docCount: number;
  heatmapMode: boolean;
  onToggleHeatmap: () => void;
  onUploadFile: (file: File, slot: 'base' | 'compare') => void;
  diffSummary: DatabaseDiffSummary | null;
  onSwapDatabases: () => void;
  onClearDiff: () => void;
  onResetAll: () => void;
}

export const HeaderBar: React.FC<HeaderBarProps> = ({
  projectName,
  activeView,
  onChangeView,
  calcCount,
  docCount,
  heatmapMode,
  onToggleHeatmap,
  onUploadFile,
  diffSummary,
  onSwapDatabases,
  onClearDiff,
  onResetAll,
}) => {
  const baseFileInputRef = useRef<HTMLInputElement | null>(null);
  const compareFileInputRef = useRef<HTMLInputElement | null>(null);

  return (
    <header className="apple-glass-chrome border-b border-white/[0.12] px-5 py-2.5 flex items-center justify-between gap-4 shadow-[0_8px_32px_rgba(0,0,0,0.85)] z-30 flex-shrink-0">
      {/* Left Brand & Project Title */}
      <div className="flex items-center space-x-3.5 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500/20 to-cyan-500/10 border border-indigo-400/30 text-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.2)] flex items-center justify-center flex-shrink-0">
          <Network className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <h1 className="font-semibold text-[13px] text-white tracking-tight flex items-center gap-2 truncate">
            <span className="truncate">{projectName}</span>
            {diffSummary ? (
              <span className="mono text-[10px] font-semibold bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-400/35 tracking-wider flex-shrink-0">
                DIFF MODE
              </span>
            ) : (
              <span className="mono text-[10px] font-medium bg-indigo-500/15 text-indigo-300 px-2 py-0.5 rounded border border-indigo-400/25 tracking-wider flex-shrink-0">
                IFC 4.3
              </span>
            )}
          </h1>
          <p className="mono text-[10px] text-zinc-500 tracking-wide mt-0.5 truncate">
            {diffSummary
              ? `A: ${diffSummary.baseName}  ↔  B: ${diffSummary.compareName}`
              : 'ELEMENT TOPOLOGY ↔ CALCULATION GRAPH ↔ 3D MODEL ↔ PDF REVISIONS'}
          </p>
        </div>
      </div>

      {/* Center Dual-Graph + 3D + PDF Browser View Switcher */}
      <nav
        aria-label="Primary Workspace Views"
        className="flex items-center bg-[#1e2127]/80 p-1 rounded-xl border border-white/[0.14] shadow-inner flex-shrink-0"
      >
        <button
          type="button"
          onClick={() => onChangeView('element-graph')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeView === 'element-graph'
              ? 'bg-indigo-600/25 text-white border border-indigo-400/40 shadow-[0_0_16px_rgba(99,102,241,0.25)]'
              : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
          }`}
        >
          <CircleDot className="w-3.5 h-3.5 text-emerald-400" />
          <span>Element Graph</span>
        </button>

        <button
          type="button"
          onClick={() => onChangeView('calculation-graph')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeView === 'calculation-graph'
              ? 'bg-indigo-600/25 text-white border border-indigo-400/40 shadow-[0_0_16px_rgba(99,102,241,0.25)]'
              : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
          }`}
        >
          <Calculator className="w-3.5 h-3.5 text-amber-400" />
          <span>Calculation Graph</span>
          <span className="mono text-[10px] px-1.5 py-0.2 rounded bg-white/[0.06] text-zinc-400">
            {calcCount}
          </span>
        </button>

        <button
          type="button"
          onClick={() => onChangeView('3d')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeView === '3d'
              ? 'bg-indigo-600/25 text-white border border-indigo-400/40 shadow-[0_0_16px_rgba(99,102,241,0.25)]'
              : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
          }`}
        >
          <Box className="w-3.5 h-3.5 text-cyan-400" />
          <span>3D Model</span>
        </button>

        <button
          type="button"
          onClick={() => onChangeView('docs')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            activeView === 'docs'
              ? 'bg-indigo-600/25 text-white border border-indigo-400/40 shadow-[0_0_16px_rgba(99,102,241,0.25)]'
              : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
          }`}
        >
          <FileText className="w-3.5 h-3.5 text-rose-400" />
          <span>PDF Calcs</span>
          <span className="mono text-[10px] px-1.5 py-0.2 rounded bg-white/[0.06] text-zinc-400">
            {docCount}
          </span>
        </button>
      </nav>

      {/* Right Heatmap, Dual-Database Import (DB A + DB B Diff) & Reset */}
      <div className="flex items-center space-x-2 flex-shrink-0">
        {!diffSummary && (
          <button
            type="button"
            onClick={onToggleHeatmap}
            title="Color elements by axial load & demand-capacity heatmap"
            className={
              heatmapMode
                ? 'bg-amber-500/20 text-amber-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-amber-400/40 shadow-[0_0_16px_rgba(245,158,11,0.25)]'
                : 'bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14]'
            }
          >
            <Flame className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden 2xl:inline">{heatmapMode ? 'Heatmap: On' : 'Heatmap'}</span>
          </button>
        )}

        {/* Base DB (A) */}
        <button
          type="button"
          onClick={() => baseFileInputRef.current?.click()}
          title="Load Primary / Base Database (DB A: .ifc or .json)"
          className="bg-white/[0.04] hover:bg-white/[0.08] active:bg-white/[0.1] text-zinc-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14] hover:border-indigo-400/40 cursor-pointer shadow-inner"
        >
          <Upload className="w-3.5 h-3.5 text-indigo-400" />
          <span>{diffSummary ? 'DB A' : 'Import IFC / DB'}</span>
        </button>
        <input
          ref={baseFileInputRef}
          type="file"
          accept=".json,.ifc,application/json"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUploadFile(f, 'base');
            e.target.value = '';
          }}
        />

        {diffSummary && (
          <button
            type="button"
            onClick={onSwapDatabases}
            title="Swap Base DB (A) and Compare DB (B)"
            className="bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-200 px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-indigo-400/35"
          >
            <ArrowLeftRight className="w-3.5 h-3.5 text-indigo-300" />
            <span className="hidden xl:inline">Swap A↔B</span>
          </button>
        )}

        {/* Compare DB (B) for Diff */}
        <button
          type="button"
          onClick={() => compareFileInputRef.current?.click()}
          title="Select Second Database (DB B) to run a full structural diff across Graph, 3D & PDFs"
          className={
            diffSummary
              ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-amber-400/45 cursor-pointer shadow-[0_0_14px_rgba(245,158,11,0.2)]'
              : 'bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14] hover:border-amber-400/40 cursor-pointer'
          }
        >
          <GitCompareArrows className="w-3.5 h-3.5 text-amber-400" />
          <span>{diffSummary ? 'DB B' : 'Compare DB'}</span>
        </button>
        <input
          ref={compareFileInputRef}
          type="file"
          accept=".json,.ifc,application/json"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUploadFile(f, 'compare');
            e.target.value = '';
          }}
        />

        {diffSummary && (
          <button
            type="button"
            onClick={onClearDiff}
            title="Exit Diff Mode and return to Base DB (A)"
            className="bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-rose-400/35"
          >
            <X className="w-3.5 h-3.5" />
            <span className="hidden xl:inline">Exit Diff</span>
          </button>
        )}

        <button
          type="button"
          onClick={onResetAll}
          title="Reset View & Filters (0)"
          className="bg-white/[0.04] hover:bg-white/[0.08] active:bg-white/[0.1] text-zinc-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14] hover:border-white/20"
        >
          <Minimize2 className="w-3.5 h-3.5 text-zinc-400" />
        </button>
      </div>
    </header>
  );
};
