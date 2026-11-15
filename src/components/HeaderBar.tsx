import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  CircleDot,
  Calculator,
  Box,
  FileText,
  Flame,
  Upload,
  GitCompareArrows,
  ArrowLeftRight,
  X,
} from 'lucide-react';
import { DatabaseDiffSummary, WorkspaceView } from '../types/bim';

const WORKSPACE_VIEW_ORDER: WorkspaceView[] = ['element-graph', 'calculation-graph', '3d', 'docs'];
const useIsomorphicLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

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
}) => {
  const baseFileInputRef = useRef<HTMLInputElement | null>(null);
  const compareFileInputRef = useRef<HTMLInputElement | null>(null);
  const viewNavRef = useRef<HTMLElement | null>(null);
  const viewButtonRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });
  const activeViewIndex = WORKSPACE_VIEW_ORDER.indexOf(activeView);

  useIsomorphicLayoutEffect(() => {
    const nav = viewNavRef.current;
    const button = viewButtonRefs.current[activeViewIndex];
    if (!nav || !button) return;

    const updateIndicator = () => {
      const navRect = nav.getBoundingClientRect();
      const buttonRect = button.getBoundingClientRect();
      setIndicatorStyle({
        left: buttonRect.left - navRect.left - nav.clientLeft,
        width: buttonRect.width,
      });
    };

    updateIndicator();
    const resizeObserver = new ResizeObserver(updateIndicator);
    resizeObserver.observe(nav);
    viewButtonRefs.current.forEach((viewButton) => {
      if (viewButton) resizeObserver.observe(viewButton);
    });

    return () => resizeObserver.disconnect();
  }, [activeViewIndex]);

  return (
    <header className="apple-glass-chrome border-b border-white/[0.08] px-5 py-2.5 flex items-center justify-between gap-4 overflow-x-auto shadow-[0_4px_12px_rgba(0,0,0,0.24)] z-30 flex-shrink-0">
      <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
        <img
          src="/unloaded-logo.svg"
          alt="CalcMap"
          width={1888}
          height={580}
          draggable={false}
          className="w-28 max-h-9 h-auto object-contain flex-shrink-0 select-none"
        />
        <div className="min-w-0">
          {(projectName || diffSummary) && (
            <h1 className="font-medium text-xs text-zinc-300 tracking-tight flex items-center gap-2 truncate">
              {projectName && <span className="truncate">{projectName}</span>}
              {diffSummary && (
                <span className="mono text-[10px] font-semibold bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-400/35 tracking-wider flex-shrink-0">
                  DIFF MODE
                </span>
              )}
            </h1>
          )}
        </div>
      </div>

      {/* Center Dual-Graph + 3D + PDF Browser View Switcher */}
      <nav
        ref={viewNavRef}
        aria-label="Primary Workspace Views"
        className="relative flex items-center bg-[#1e2127]/80 p-1 rounded-xl border border-white/[0.14] shadow-inner flex-shrink-0"
      >
        <span
          aria-hidden="true"
          className="workspace-view-indicator absolute top-1 bottom-1 z-0 rounded-lg bg-white/[0.10] border border-white/[0.22] pointer-events-none"
          style={{ width: indicatorStyle.width, transform: `translateX(${indicatorStyle.left}px)` }}
        />
        <button
          ref={(button) => { viewButtonRefs.current[0] = button; }}
          type="button"
          onClick={() => onChangeView('element-graph')}
          aria-pressed={activeView === 'element-graph'}
          className={`relative z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeView === 'element-graph'
              ? 'text-white border border-transparent'
              : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
          }`}
        >
          <CircleDot className="w-3.5 h-3.5 text-emerald-400" />
          <span>Element Graph</span>
        </button>

        <button
          ref={(button) => { viewButtonRefs.current[1] = button; }}
          type="button"
          onClick={() => onChangeView('calculation-graph')}
          aria-pressed={activeView === 'calculation-graph'}
          className={`relative z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeView === 'calculation-graph'
              ? 'text-white border border-transparent'
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
          ref={(button) => { viewButtonRefs.current[2] = button; }}
          type="button"
          onClick={() => onChangeView('3d')}
          aria-pressed={activeView === '3d'}
          className={`relative z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeView === '3d'
              ? 'text-white border border-transparent'
              : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
          }`}
        >
          <Box className="w-3.5 h-3.5 text-cyan-400" />
          <span>3D Model</span>
        </button>

        <button
          ref={(button) => { viewButtonRefs.current[3] = button; }}
          type="button"
          onClick={() => onChangeView('docs')}
          aria-pressed={activeView === 'docs'}
          className={`relative z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeView === 'docs'
              ? 'text-white border border-transparent'
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

      {/* Workspace actions */}
      <div className="flex items-center space-x-2 flex-shrink-0">
        {!diffSummary && (
          <button
            type="button"
            onClick={onToggleHeatmap}
            aria-label="Toggle utilization heatmap"
            aria-pressed={heatmapMode}
            title="Color elements by axial load & demand-capacity heatmap"
            className={
              heatmapMode
                ? 'bg-amber-500/20 text-amber-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-amber-400/40'
                : 'bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14]'
            }
          >
            <Flame className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden 2xl:inline">{heatmapMode ? 'Heatmap: On' : 'Heatmap'}</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => baseFileInputRef.current?.click()}
          title="Import a structural model"
          className="bg-white/[0.04] hover:bg-white/[0.08] active:bg-white/[0.1] text-zinc-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14] hover:border-calcmap/40 cursor-pointer shadow-inner"
        >
          <Upload className="w-3.5 h-3.5 text-calcmap" />
          <span>Import</span>
        </button>
        <input
          ref={baseFileInputRef}
          type="file"
          accept=".json,.ifc,application/json"
          className="hidden"
          aria-label="Import model"
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
            aria-label="Swap compared models"
            title="Swap compared models"
            className="bg-calcmap/15 hover:bg-calcmap/25 text-calcmap px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-calcmap/35"
          >
            <ArrowLeftRight className="w-3.5 h-3.5 text-calcmap" />
            <span className="hidden xl:inline">Swap models</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => compareFileInputRef.current?.click()}
          title="Choose a second model to compare"
          className={
            diffSummary
              ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-amber-400/45 cursor-pointer'
              : 'bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14] hover:border-amber-400/40 cursor-pointer'
          }
        >
          <GitCompareArrows className="w-3.5 h-3.5 text-amber-400" />
          <span>Compare</span>
        </button>
        <input
          ref={compareFileInputRef}
          type="file"
          accept=".json,.ifc,application/json"
          className="hidden"
          aria-label="Import comparison model"
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
            aria-label="Exit diff mode"
            title="Exit comparison and return to the primary model"
            className="bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-rose-400/35"
          >
            <X className="w-3.5 h-3.5" />
            <span className="hidden xl:inline">Exit Diff</span>
          </button>
        )}
      </div>
    </header>
  );
};
