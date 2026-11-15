import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useEscapeLayer } from './escapeStack';
import {
  ArrowLeftRight,
  Box,
  Calculator,
  ChevronDown,
  CircleDot,
  Database,
  Download,
  FolderPlus,
  FileJson,
  FileText,
  GitCompareArrows,
  Loader2,
  Minimize2,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import type { ProjectSource, WorkspaceView } from '../types/bim';

interface HeaderBarProps {
  activeView: WorkspaceView;
  onChangeView: (view: WorkspaceView) => void;
  calcCount: number;
  /** the project store persists (IndexedDB) rather than living in memory for this tab only */
  persistent: boolean;
  source: ProjectSource | null;
  busy: boolean;
  projects: { id: string; name: string }[];
  activeProjectId: string | null;
  onSwitchProject: (id: string) => void;
  onNewProject: () => void;
  /** null when there is no project to save */
  onSaveProject: (() => void) | null;
  onLoadSample: () => void;
  onLoadDemo: () => void;
  onUploadModel: (file: File) => void;
  /** One or more calc PDFs (one large package, one per calc, or new revisions): each is placed in a calc document. */
  onUploadCalcs: (files: File[]) => void;
  /** any accepted file, dispatched by content (model / calc PDF / project file / export JSON) */
  onOpenFile: (file: File) => void;
  /** diff mode is set (A, B), whether or not its diff has loaded: Swap and Exit are offered whenever it is */
  diffRevs: { a: number; b: number } | null;
  compareOpen: boolean;
  onToggleCompare: () => void;
  onSwapDatabases: () => void;
  onClearDiff: () => void;
  onResetAll: () => void;
}

const viewBtn = (active: boolean) =>
  `relative z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
    active
      ? 'text-white border border-transparent'
      : 'text-zinc-400 hover:text-zinc-100 border border-transparent'
  }`;

const chromeBtn =
  'bg-white/[0.04] hover:bg-white/[0.08] active:bg-white/[0.1] text-zinc-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-white/[0.14] disabled:opacity-40 disabled:cursor-not-allowed';

const WORKSPACE_VIEW_ORDER: WorkspaceView[] = ['element-graph', 'calculation-graph', '3d', 'docs'];
const useIsomorphicLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

export const HeaderBar: React.FC<HeaderBarProps> = (p) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const viewNavRef = useRef<HTMLElement | null>(null);
  const viewButtonRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const modelInput = useRef<HTMLInputElement | null>(null);
  const calcInput = useRef<HTMLInputElement | null>(null);
  const openInput = useRef<HTMLInputElement | null>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });
  const [menuPosition, setMenuPosition] = useState<{ left: number; top: number; width: number; maxHeight: number } | null>(null);
  const activeViewIndex = WORKSPACE_VIEW_ORDER.indexOf(p.activeView);

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
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateIndicator);
      return () => window.removeEventListener('resize', updateIndicator);
    }

    const observer = new ResizeObserver(updateIndicator);
    observer.observe(nav);
    viewButtonRefs.current.forEach((viewButton) => viewButton && observer.observe(viewButton));
    return () => observer.disconnect();
  }, [activeViewIndex]);

  useEscapeLayer(menuOpen, () => setMenuOpen(false));
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!menuRef.current?.contains(target) && !menuButtonRef.current?.contains(target)) setMenuOpen(false);
    };
    window.addEventListener('pointerdown', onDown);
    return () => window.removeEventListener('pointerdown', onDown);
  }, [menuOpen]);
  useIsomorphicLayoutEffect(() => {
    if (!menuOpen) return;
    const updatePosition = () => {
      const button = menuButtonRef.current;
      if (!button) return;
      const rect = button.getBoundingClientRect();
      const width = Math.min(320, window.innerWidth - 16);
      const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
      const top = Math.min(rect.bottom + 8, Math.max(8, window.innerHeight - 160));
      setMenuPosition({ left, top, width, maxHeight: Math.max(80, window.innerHeight - top - 8) });
    };
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [menuOpen]);

  const pick = (ref: React.RefObject<HTMLInputElement>) => {
    setMenuOpen(false);
    ref.current?.click();
  };
  const fileInput = (ref: React.RefObject<HTMLInputElement>, accept: string, label: string, onFiles: (fs: File[]) => void, multiple = false) => (
    <input
      ref={ref}
      type="file"
      accept={accept}
      multiple={multiple}
      className="hidden"
      aria-label={label}
      onChange={(e) => {
        const fs = [...(e.target.files ?? [])];
        if (fs.length) onFiles(fs);
        e.target.value = '';
      }}
    />
  );

  const menuItem = (icon: React.ReactNode, label: string, sub: string, onClick: () => void, disabled = false) => (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      role="menuitem"
      className="w-full text-left flex items-start gap-2.5 px-2.5 py-2 rounded-lg hover:bg-white/[0.06] focus-visible:bg-white/[0.08] focus-visible:outline-none transition disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <span className="mt-0.5">{icon}</span>
      <span className="min-w-0">
        <span className="block text-xs font-medium text-zinc-100">{label}</span>
        <span className="block text-[10.5px] text-zinc-500 leading-snug">{sub}</span>
      </span>
    </button>
  );

  return (
    <header className="apple-glass-chrome border-b border-white/[0.12] px-5 py-2.5 flex items-center justify-between gap-4 overflow-x-auto shadow-[0_8px_32px_rgba(0,0,0,0.85)] z-30 flex-shrink-0">
      <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
        <img
          src="/unloaded-logo.svg"
          alt="CalcMap"
          width={1888}
          height={580}
          draggable={false}
          className="w-28 max-h-9 h-auto object-contain flex-shrink-0 select-none"
        />
      </div>

      <nav
        ref={viewNavRef}
        aria-label="Primary Workspace Views"
        className="relative flex items-center bg-[#1e2127]/80 p-1 rounded-xl border border-white/[0.14] shadow-inner flex-shrink-0"
      >
        <span
          aria-hidden="true"
          className="workspace-view-indicator absolute top-1 bottom-1 z-0 rounded-lg bg-white/[0.10] border border-white/[0.22] pointer-events-none transition-[transform,width] duration-300"
          style={{ width: indicatorStyle.width, transform: `translateX(${indicatorStyle.left}px)` }}
        />
        <button ref={(button) => { viewButtonRefs.current[0] = button; }} type="button" onClick={() => p.onChangeView('element-graph')} aria-pressed={p.activeView === 'element-graph'} className={viewBtn(p.activeView === 'element-graph')}>
          <CircleDot className="w-3.5 h-3.5 text-emerald-400" />
          <span>Element Graph</span>
        </button>
        <button ref={(button) => { viewButtonRefs.current[1] = button; }} type="button" onClick={() => p.onChangeView('calculation-graph')} aria-pressed={p.activeView === 'calculation-graph'} className={viewBtn(p.activeView === 'calculation-graph')}>
          <Calculator className="w-3.5 h-3.5 text-amber-400" />
          <span>Calculation Graph</span>
          <span className="mono text-[10px] px-1.5 rounded bg-white/[0.06] text-zinc-400">{p.calcCount}</span>
        </button>
        <button ref={(button) => { viewButtonRefs.current[2] = button; }} type="button" onClick={() => p.onChangeView('3d')} aria-pressed={p.activeView === '3d'} className={viewBtn(p.activeView === '3d')}>
          <Box className="w-3.5 h-3.5 text-cyan-400" />
          <span>3D Model</span>
        </button>
        <button ref={(button) => { viewButtonRefs.current[3] = button; }} type="button" onClick={() => p.onChangeView('docs')} aria-pressed={p.activeView === 'docs'} className={viewBtn(p.activeView === 'docs')}>
          <FileText className="w-3.5 h-3.5 text-rose-400" />
          <span>PDF Calcs</span>
        </button>
      </nav>

      <div className="flex items-center space-x-2 flex-shrink-0">
        <div className="relative">
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className={`${chromeBtn} hover:border-calcmap/40 max-w-[220px]`}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
          >
            {p.busy ? <Loader2 className="w-3.5 h-3.5 text-calcmap animate-spin" aria-hidden="true" /> : <Upload className="w-3.5 h-3.5 text-calcmap" aria-hidden="true" />}
            <span>Project</span>
            <ChevronDown className="w-3 h-3 text-zinc-500" aria-hidden="true" />
          </button>
          {menuOpen && menuPosition && createPortal(
            <div
              ref={menuRef}
              role="menu"
              style={{ position: 'fixed', ...menuPosition, zIndex: 1000 }}
              className="overflow-y-auto bg-[#2d3139]/96 backdrop-blur-2xl border border-white/[0.14] rounded-xl p-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.85)]"
            >
              {p.projects.length > 0 && (
                <>
                  <p className="mono text-[9px] text-zinc-500 uppercase tracking-wider px-2.5 pt-1.5 pb-1">Projects in this browser</p>
                  <div className="max-h-40 overflow-y-auto">
                    {p.projects.map((pr) => (
                      <button
                        key={pr.id}
                        type="button"
                        role="menuitemradio"
                        aria-checked={pr.id === p.activeProjectId}
                        onClick={() => {
                          setMenuOpen(false);
                          p.onSwitchProject(pr.id);
                        }}
                        className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs truncate transition ${
                          pr.id === p.activeProjectId ? 'bg-calcmap/15 text-white' : 'text-zinc-300 hover:bg-white/[0.06]'
                        }`}
                      >
                        {pr.name}
                      </button>
                    ))}
                  </div>
                  <div className="h-px bg-white/[0.08] my-1" />
                </>
              )}
              {menuItem(<Sparkles className="w-3.5 h-3.5 text-indigo-300" aria-hidden="true" />, 'Load sample', 'Synthetic office building + its calc package, as a new project', () => {
                setMenuOpen(false);
                p.onLoadSample();
              }, p.busy)}
              {menuItem(<Sparkles className="w-3.5 h-3.5 text-amber-300" aria-hidden="true" />, 'Harborview A/B demo', 'Two legacy JSON revisions with invented documents (demo data)', () => {
                setMenuOpen(false);
                p.onLoadDemo();
              }, p.busy)}
              {menuItem(<FolderPlus className="w-3.5 h-3.5 text-zinc-300" aria-hidden="true" />, 'New empty project', 'Start a project and add its files', () => {
                setMenuOpen(false);
                p.onNewProject();
              }, p.busy)}
              <div className="h-px bg-white/[0.08] my-1" />
              {menuItem(<Box className="w-3.5 h-3.5 text-cyan-300" aria-hidden="true" />, 'Add model revision', 'IFC (or element graph / ModelInput / legacy JSON); parsed in this browser', () => pick(modelInput), p.busy || p.source !== 'project')}
              {menuItem(<FileText className="w-3.5 h-3.5 text-rose-300" aria-hidden="true" />, 'Add calc PDFs', 'One package or one PDF per calc; each joins a calc document', () => pick(calcInput), p.busy || p.source !== 'project')}
              <div className="h-px bg-white/[0.08] my-1" />
              {menuItem(<FileJson className="w-3.5 h-3.5 text-amber-300" aria-hidden="true" />, 'Open file…', 'A project file (new project), an export JSON (read-only), a model or a PDF', () => pick(openInput), p.busy)}
              {p.onSaveProject &&
                menuItem(<Download className="w-3.5 h-3.5 text-zinc-300" aria-hidden="true" />, 'Save project file', 'Everything (files, graphs, decisions) in one file for a colleague', () => {
                  setMenuOpen(false);
                  p.onSaveProject?.();
                }, p.busy)}
              {!p.persistent && (
                <p className="mono text-[9.5px] text-amber-300/90 px-2.5 py-1.5 leading-snug">
                  Storage is blocked in this browser: projects last until the tab closes. Save a project file to keep work.
                </p>
              )}
            </div>,
            document.body,
          )}
        </div>
        {fileInput(modelInput, '.ifc,.json,application/json', 'Add model revision', (fs) => p.onUploadModel(fs[0]!))}
        {fileInput(calcInput, '.pdf,application/pdf', 'Add calc PDFs', p.onUploadCalcs, true)}
        {fileInput(openInput, '.json,.ifc,.pdf,application/json,application/pdf', 'Open file', (fs) => p.onOpenFile(fs[0]!))}

        {p.diffRevs && (
          <button type="button" onClick={p.onSwapDatabases} title="Swap base revision (A) and compare revision (B)" aria-label="Swap base and compare revisions" className="bg-calcmap/15 hover:bg-calcmap/25 text-calcmap px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-calcmap/35">
            <ArrowLeftRight className="w-3.5 h-3.5 text-calcmap" />
            <span className="hidden xl:inline">Swap A↔B</span>
          </button>
        )}

        <button
          type="button"
          onClick={p.onToggleCompare}
          disabled={p.source !== 'project'}
          title={p.source === 'project' ? 'Compare two model revisions across the graph, 3D and calcs' : 'Revisions belong to a project; an export JSON has none'}
          className={
            p.diffRevs || p.compareOpen
              ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-amber-400/45 shadow-[0_0_14px_rgba(245,158,11,0.2)]'
              : `${chromeBtn} hover:border-amber-400/40`
          }
        >
          <GitCompareArrows className="w-3.5 h-3.5 text-amber-400" />
          <span>{p.diffRevs ? `Rev ${p.diffRevs.a} → ${p.diffRevs.b}` : 'Revisions'}</span>
        </button>

        {p.diffRevs && (
          <button type="button" onClick={p.onClearDiff} title="Exit diff mode" aria-label="Exit diff mode" className="bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 px-2 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1 border border-rose-400/35">
            <X className="w-3.5 h-3.5" />
            <span className="hidden xl:inline">Exit Diff</span>
          </button>
        )}

        <span
          title={p.persistent ? 'Projects are saved in this browser (IndexedDB)' : 'Storage blocked: projects last until this tab closes'}
          className="flex items-center gap-1.5 mono text-[10px] text-zinc-500 px-1"
        >
          <Database className="w-3.5 h-3.5" aria-hidden="true" />
          <span className={`w-1.5 h-1.5 rounded-full ${p.persistent ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'bg-amber-400'}`} />
          <span className="sr-only">{p.persistent ? 'Saved in this browser' : 'Not persisted'}</span>
        </span>

        <button type="button" onClick={p.onResetAll} title="Reset view, filters & panels" aria-label="Reset view, filters and panels" className={chromeBtn}>
          <Minimize2 className="w-3.5 h-3.5 text-zinc-400" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
};
