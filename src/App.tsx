import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Box,
  CheckCircle2,
  Columns,
  Crosshair,
  FileJson,
  FileText,
  Loader2,
  Network,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import type {
  BimNode,
  ColorMode,
  DecisionAction,
  DockSide,
  FilterState,
  HighlightOverlay,
  HighlightTone,
  NodeGroup,
  PdfTarget,
  ProjectViewModel,
  TraceDirection,
  WorkspaceView,
} from './types/bim';
import {
  useCompare,
  useCreateProject,
  useDecide,
  useImpact,
  useInitialProject,
  useLoadDemo,
  useLoadSample,
  useLoadSupplement,
  useProjectList,
  useProjectView,
  useRevisionUrls,
  useStoreInfo,
  useUploadCalcs,
  useMoveCalcRevision,
  useChangeDocument,
  useUploadModel,
} from './engine/hooks';
import { downloadModelBundle, downloadProjectFile, openAnyFile, rememberActiveProject, revisionFileUrl, SampleMissingError, type CalcPlacement } from './engine/projectService';

/** Where an added calc PDF went, in words (a toast): a new calc document, a new revision of one, or already loaded. */
function calcPlacementText(fileName: string, p: CalcPlacement, revisionId: number | null): string {
  if (p.kind === 'duplicate') return `${fileName} is already loaded (in ${p.docName}); not added again`;
  if (p.kind === 'new') return `${fileName} added as a new calc document, ${p.docName} (revision #${revisionId})`;
  return `${fileName} added as revision #${revisionId} of ${p.docName}${p.note && p.note !== 'chosen' ? ` (${p.note})` : ''}`;
}
import { calcNodeId } from './data/loadProject';
import { applyModelDiff } from './data/mergeProject';
import { diffRevisionsError, keepWhatExists } from './data/viewState';
import { exportFileView } from './data/openFile';
import {
  computeLoadPathTrace,
  isElementTypeNode,
  isInstanceNode,
  withMappingSatellites,
} from './utils/graphEngine';
import { HeaderBar } from './components/HeaderBar';
import { FilterBar, type DiffFilter } from './components/FilterBar';
import { RadialGraphCanvas } from './components/RadialGraphCanvas';
import { Structural3DViewer } from './components/Structural3DViewer';
import { PropertyInspector } from './components/PropertyInspector';
import { DocumentBrowser, calcTarget } from './components/DocumentBrowser';
import { DockableHudPanel } from './components/DockableHudPanel';
import { RevisionPanel } from './components/RevisionPanel';
import { useEscapeFallback } from './components/escapeStack';
import { FileDropOverlay } from './components/FileDropOverlay';
import { useFileDrop, type DropSlot } from './hooks/useFileDrop';
import { ACCEPTED_EXTENSIONS } from './loaders/parsers';

/** What a window drop accepts: every model format, calc package PDFs and project files (.json). */
const DROP_EXTENSIONS = [...new Set([...ACCEPTED_EXTENSIONS, '.pdf'])];

const EMPTY_SET = new Set<string>();
const NO_FILTERS: FilterState = { search: '', type: 'ALL', level: 'ALL' };

/**
 * What is open: a project in the store, or a read-only export file over it. `epoch` counts scope
 * changes (0 = the scope the app opened with); it keys every component that holds project-local
 * state, so a different project remounts them instead of inheriting their tabs and picks.
 */
interface Scope {
  projectId: string | null;
  exportView: ProjectViewModel | null;
  epoch: number;
}

/** The URL deep link (#view=docs&el=<GlobalId>&evidence=1&impact=remove&calc=<key>&compare=A,B), read once. */
const readDeepLink = () => {
  if (typeof window === 'undefined') return null;
  const h = window.location.hash.replace(/^#/, '');
  return h ? new URLSearchParams(h) : null;
};
const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<WorkspaceView>('element-graph');
  /** bumped by every explicit "open this in the PDF view": remounts the browser so its search / comparison cannot hide the target */
  const [documentOpenRequest, setDocumentOpenRequest] = useState(0);
  const [colorMode, setColorMode] = useState<ColorMode>('type');
  const [traceDirection, setTraceDirection] = useState<TraceDirection>('down');
  const [traceSteps, setTraceSteps] = useState<number>(16);

  // ---------------------------------------------------------------- data
  // A project in the local store (IndexedDB): its head model revision's element graph (topology)
  // merged with the calc engine's export (worker), by GlobalId. Or a plain calc-graph export JSON
  // opened from disk (exportView), read-only.
  const queryClient = useQueryClient();
  const [busyText, setBusyText] = useState('');
  const storeInfo = useStoreInfo();
  const initialProject = useInitialProject();
  const [scope, setScope] = useState<Scope>({ projectId: null, exportView: null, epoch: 0 });
  const { projectId, exportView } = scope;
  // the store's last-active project is the opening scope (epoch 0); every later change is enterScope
  useEffect(() => {
    const id = initialProject.data?.id;
    if (id) setScope((s) => (s.projectId ? s : { ...s, projectId: id }));
  }, [initialProject.data]);
  const pid = exportView ? null : projectId;

  // diff mode: (A, B) model revisions of `pid`; the diff is laid over revision B's view
  const [diffRevs, setDiffRevs] = useState<{ a: number; b: number } | null>(null);
  const [diffFilter, setDiffFilter] = useState<DiffFilter>('ALL');
  const [compareOpen, setCompareOpen] = useState(false);

  // progress of (re)building the project view: mapping runs in the worker the first time a
  // (model, calcs) pair is seen; shown only while that query is fetching
  const [viewProgress, setViewProgress] = useState('');
  const projectQ = useProjectView(pid, setViewProgress, diffRevs?.b ?? null);
  const viewBusy = projectQ.isFetching && viewProgress ? viewProgress : '';
  const projectsQ = useProjectList();
  const decide = useDecide(pid);
  const sample = useLoadSample(setBusyText);
  const demo = useLoadDemo(setBusyText);
  const supplement = useLoadSupplement(setBusyText);
  // revisions go to the store project, also when an export view is shown over it (addRevisionFile)
  const uploadModel = useUploadModel(setBusyText);
  const uploadCalcs = useUploadCalcs(setBusyText);
  const moveCalcRevision = useMoveCalcRevision(pid);
  const changeDocument = useChangeDocument(pid);
  const createProject = useCreateProject();
  const revisions = projectQ.data?.revisions ?? null;
  /** the head model revision: "before" when a new model revision is added (not B in diff mode) */
  const headModelRev = revisions?.find((r) => r.kind === 'model' && r.isHead)?.id ?? null;

  const compareQ = useCompare(pid, diffRevs?.a ?? null, diffRevs?.b ?? null);

  const baseView: ProjectViewModel | null = exportView ?? projectQ.data?.view ?? null;
  // The model revision ON SCREEN: while B's view loads, the previous revision's view is still shown
  // (placeholder data), and impact and decisions must be about what the reviewer sees, not about the
  // revision being loaded. Writes are disabled while the view is a placeholder (canWrite below).
  const shownModelRev = exportView ? null : (baseView?.modelRevisionId ?? null);
  const viewIsPlaceholder = !exportView && projectQ.isPlaceholderData;

  const [impactReq, setImpactReq] = useState<{ gid: string; mode: 'change' | 'remove' } | null>(null);
  const impactQ = useImpact(pid, impactReq?.gid ?? null, impactReq?.mode ?? 'change', shownModelRev);
  const impact = impactReq && impactQ.data && impactQ.data.elementId === impactReq.gid && impactQ.data.mode === impactReq.mode ? impactQ.data : null;

  const diffApplied = useMemo(() => {
    if (!baseView || !diffRevs || !compareQ.data) return null;
    const label = (rid: number) => {
      const r = revisions?.find((x) => x.id === rid);
      return r ? `#${rid} ${r.label}` : `Revision #${rid}`;
    };
    return applyModelDiff(baseView, compareQ.data, { base: label(diffRevs.a), compare: label(diffRevs.b) });
  }, [baseView, diffRevs, compareQ.data, revisions]);
  const diffSummary = diffApplied?.summary ?? null;
  const diffMode = Boolean(diffSummary);
  const view = diffApplied?.view ?? baseView;

  // ---------------------------------------------------------------- UI state
  const [groups, setGroups] = useState<NodeGroup[]>([]);
  const [moved, setMoved] = useState<Map<string, { x: number; y: number }>>(new Map());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const [selectedCalcNodeId, setSelectedCalcNodeId] = useState<string | null>(null);
  const [selectedCalcNodeIds, setSelectedCalcNodeIds] = useState<Set<string>>(new Set());
  const [calcAnchorKey, setCalcAnchorKey] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(NO_FILTERS);
  const [docFilterBySelected, setDocFilterBySelected] = useState(false);
  const [pdfTarget, setPdfTarget] = useState<PdfTarget | null>(null);
  const [fit3dTrigger, setFit3dTrigger] = useState(0);
  const [resetTrigger, setResetTrigger] = useState(0);
  const [viewer3dDock, setViewer3dDock] = useState<DockSide>('float');
  const [inspectorDock, setInspectorDock] = useState<DockSide>('float');
  const [leftDockWidth, setLeftDockWidth] = useState(340);
  const [rightDockWidth, setRightDockWidth] = useState(360);
  const [topHudZ, setTopHudZ] = useState<{ v3d: number; insp: number }>({ v3d: 31, insp: 32 });
  const [hoverEdge, setHoverEdge] = useState<'left' | 'right' | null>(null);

  /**
   * Every view change goes through here. Element and calc searches / type filters address different
   * records (element categories vs calc groups), so crossing into or out of the calc graph clears them.
   */
  const activeViewRef = useRef(activeView);
  activeViewRef.current = activeView;
  const changeView = useCallback((next: WorkspaceView) => {
    if ((activeViewRef.current === 'calculation-graph') !== (next === 'calculation-graph')) {
      setFilters((f) => (f.search || f.type !== 'ALL' ? { ...f, search: '', type: 'ALL' } : f));
    }
    setActiveView(next);
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedNodeIds(new Set());
    setSelectedCalcNodeId(null);
    setSelectedCalcNodeIds(new Set());
    setCalcAnchorKey(null);
  }, []);

  /**
   * The one way the open project changes (picker, sample, demo, new project, project or export
   * file). It resets every project-scoped piece of state here, synchronously: groups, moved nodes,
   * selection, impact, PDF target, the 3D camera, filters, diff mode. It also bumps the epoch that
   * remounts components holding project-local state. `diff` is applied as part of the same change,
   * so a caller entering a project in diff mode (the demo) cannot have it reset away. Re-entering
   * the scope already open changes nothing but the diff, when one is given.
   * A different revision of the SAME project on screen is not a project change: see keepWhatExists
   * below (src/data/viewState.ts).
   */
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const enterScope = useCallback(
    (next: { projectId: string } | { exportView: ProjectViewModel }, diff?: { a: number; b: number }) => {
      const cur = scopeRef.current;
      const nextProject = 'projectId' in next ? next.projectId : cur.projectId;
      const nextExport = 'exportView' in next ? next.exportView : null;
      if ('projectId' in next) rememberActiveProject(next.projectId);
      const same = nextProject === cur.projectId && nextExport === cur.exportView;
      if (!same) {
        const s = { projectId: nextProject, exportView: nextExport, epoch: cur.epoch + 1 };
        scopeRef.current = s;
        setScope(s);
        setDiffRevs(null);
        setDiffFilter('ALL');
        setFilters(NO_FILTERS);
        setCompareOpen(false);
        setDocFilterBySelected(false);
        setGroups([]);
        setMoved(new Map());
        handleClearSelection();
        setImpactReq(null);
        setPdfTarget(null);
        setResetTrigger((c) => c + 1);
      }
      if (diff) {
        setDiffRevs(diff);
        setDiffFilter('ALL');
      }
    },
    [handleClearSelection],
  );
  const switchProject = useCallback((id: string) => enterScope({ projectId: id }), [enterScope]);

  const [toast, setToast] = useState<{ message: string; isError: boolean; visible: boolean }>({ message: '', isError: false, visible: false });
  // one timer: a newer toast restarts the countdown; cleared on unmount
  const toastTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(toastTimer.current), []);
  const showToast = useCallback((message: string, isError = false) => {
    setToast({ message, isError, visible: true });
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast((prev) => (prev.message === message ? { ...prev, visible: false } : prev)), isError ? 7000 : 3400);
  }, []);

  // In diff mode the view is revision B's: if B's view or the diff fails, diff mode is left (back to
  // the head, which has its own view) with the reason, rather than leaving an empty workspace.
  useEffect(() => {
    const err = diffRevs ? (projectQ.error ?? compareQ.error) : projectQ.error;
    if (!err) return;
    if (diffRevs) {
      setDiffRevs(null);
      setDiffFilter('ALL');
      showToast(`Left diff mode: could not compare #${diffRevs.a} with #${diffRevs.b} (${errMsg(err)})`, true);
    } else {
      showToast(`Could not load the project: ${errMsg(err)}`, true);
    }
  }, [diffRevs, projectQ.error, compareQ.error, showToast]);
  useEffect(() => {
    if (impactQ.error) showToast(`Impact check failed: ${errMsg(impactQ.error)}`, true);
  }, [impactQ.error, showToast]);
  // the head calc package could not be read: the model is shown without calc data (calcError banner)
  const calcError = exportView ? null : (projectQ.data?.calcError ?? null);
  // once per diff entered (a scope's (A, B) pair), not per recomputation: every decision refetches
  // the base view and recomputes diffSummary
  const diffKey = diffRevs ? `${scope.epoch}:${diffRevs.a}:${diffRevs.b}` : null;
  const announcedDiff = useRef<string | null>(null);
  useEffect(() => {
    if (!diffKey) announcedDiff.current = null;
    else if (diffSummary && announcedDiff.current !== diffKey) {
      announcedDiff.current = diffKey;
      showToast(`Diff ready: +${diffSummary.addedCount} added, ~${diffSummary.modifiedCount} modified, -${diffSummary.removedCount} removed`);
    }
  }, [diffKey, diffSummary, showToast]);

  // The revision on screen changed within the project (a diff entered, swapped or left, a new head
  // or calc package): groups and moved nodes stay; selection, impact and PDF target stay where their
  // element / calc exists in the new view (src/data/viewState.ts). Applied once the view has settled:
  // not to a placeholder of the previous revision, and in diff mode not before the diff's ghosts are
  // laid over B (a selected removed element is still on screen, as a ghost).
  const viewSettled = !viewIsPlaceholder && (!diffRevs || Boolean(diffApplied) || compareQ.isError);
  const pointersRef = useRef({ selectedNodeId, selectedNodeIds, selectedCalcNodeId, selectedCalcNodeIds, calcAnchorKey, impactReq, pdfTarget });
  pointersRef.current = { selectedNodeId, selectedNodeIds, selectedCalcNodeId, selectedCalcNodeIds, calcAnchorKey, impactReq, pdfTarget };
  useEffect(() => {
    if (!view || !viewSettled) return;
    const cur = pointersRef.current;
    const next = keepWhatExists(cur, view);
    if (next === cur) return;
    setSelectedNodeId(next.selectedNodeId);
    setSelectedNodeIds(next.selectedNodeIds);
    setSelectedCalcNodeId(next.selectedCalcNodeId);
    setSelectedCalcNodeIds(next.selectedCalcNodeIds);
    setCalcAnchorKey(next.calcAnchorKey);
    setImpactReq(next.impactReq);
    setPdfTarget(next.pdfTarget);
  }, [view, viewSettled]);

  // ---------------------------------------------------------------- derived view data
  const elementNodes = useMemo<BimNode[]>(() => {
    const nodes = view?.elementNodes ?? [];
    if (moved.size === 0) return nodes;
    return nodes.map((n) => {
      const m = moved.get(n.id);
      return m ? { ...n, x: m.x, y: m.y } : n;
    });
  }, [view, moved]);
  const elementById = useMemo(() => new Map(elementNodes.map((n) => [n.id, n])), [elementNodes]);

  const calcGraph = useMemo(
    () => withMappingSatellites(view?.calcNodes ?? [], view?.calcLinks ?? [], calcAnchorKey, elementNodes),
    [view, calcAnchorKey, elementNodes],
  );

  const hasProject = Boolean(view && (view.elementNodes.length > 1 || view.calcs.length > 0));

  const { chainNodeIds: activeLoadChainNodeIds, chainLinkKeys: activeLoadChainLinkKeys } = useMemo(() => {
    const seeds = (selectedNodeIds.size > 0 ? [...selectedNodeIds] : selectedNodeId ? [selectedNodeId] : []).filter(
      (id) => elementById.get(id)?.kind === 'element',
    );
    return computeLoadPathTrace(view?.loadPath ?? [], seeds, traceDirection, traceSteps);
  }, [view, elementById, selectedNodeId, selectedNodeIds, traceDirection, traceSteps]);

  const overlay = useMemo<HighlightOverlay | null>(() => {
    if (!impact) return null;
    const tones = new Map<string, HighlightTone>();
    impact.hit.forEach((_, id) => tones.set(id, 'hit'));
    impact.removed.forEach((id) => tones.set(id, 'removed'));
    impact.stale.forEach((_, key) => tones.set(calcNodeId(key), 'stale'));
    tones.set(impact.elementId, 'origin');
    return { tones };
  }, [impact]);

  const categories = useMemo(
    () => (activeView === 'calculation-graph' ? view?.calcNodes ?? [] : elementNodes).filter(isElementTypeNode),
    [activeView, view, elementNodes],
  );
  const floors = useMemo(() => {
    const m = new Map<string, number>();
    elementNodes.forEach((n) => n.kind === 'element' && n.storey && m.set(n.storey, n.storeyOrder ?? 0));
    return [...m.entries()].sort((a, b) => a[1] - b[1]).map(([s]) => s);
  }, [elementNodes]);

  // the diff filter applies to elements only (see matchingNodeIds): in the calc graph it is not an active filter
  const isDiffFilterActive = Boolean(activeView !== 'calculation-graph' && diffSummary && diffFilter !== 'ALL');
  const isFilterActive = Boolean(filters.search.trim() || filters.type !== 'ALL' || filters.level !== 'ALL' || isDiffFilterActive);

  const { matchingNodeIds, totalInstances } = useMemo(() => {
    const inCalc = activeView === 'calculation-graph';
    const list = (inCalc ? calcGraph.nodes : elementNodes).filter(isInstanceNode);
    const matched = new Set<string>();
    const q = filters.search.trim().toLowerCase();
    list.forEach((n) => {
      if (filters.type !== 'ALL' && n.parent !== filters.type && n.categoryParent !== filters.type) return;
      if (!inCalc && filters.level !== 'ALL' && n.storey !== filters.level) return;
      if (!inCalc && diffSummary && diffFilter !== 'ALL') {
        const st = n.diffStatus ?? 'unchanged';
        if (diffFilter === 'CHANGED' ? st === 'unchanged' : st !== diffFilter) return;
      }
      if (q) {
        const hay = `${n.id} ${n.label} ${n.mark ?? ''} ${n.size ?? ''} ${n.storey ?? ''} ${n.ifcType ?? ''} ${n.name ?? ''} ${n.desc ?? ''}`.toLowerCase();
        if (!hay.includes(q)) return;
      }
      matched.add(n.id);
    });
    return { matchingNodeIds: matched, totalInstances: list.filter((n) => n.kind !== 'mapped-element').length };
  }, [activeView, calcGraph.nodes, elementNodes, filters, diffSummary, diffFilter]);

  // ---------------------------------------------------------------- selection
  const handleSelectElementNode = useCallback(
    (id: string, opts?: { toggleMulti?: boolean; preserveMulti?: boolean; skipZoomFit?: boolean }) => {
      if (opts?.toggleMulti) {
        setSelectedNodeIds((prev) => {
          const next = new Set(prev);
          if (next.has(id)) {
            next.delete(id);
            setSelectedNodeId(next.size === 0 ? null : Array.from(next).pop() || null);
          } else {
            next.add(id);
            setSelectedNodeId(id);
          }
          return next;
        });
      } else if (opts?.preserveMulti) {
        setSelectedNodeIds((prev) => new Set(prev).add(id));
        setSelectedNodeId(id);
      } else {
        setSelectedNodeIds(new Set([id]));
        setSelectedNodeId(id);
      }
      if (!opts?.skipZoomFit) setFit3dTrigger((c) => c + 1);
    },
    [],
  );

  const handleSelectCalcNode = useCallback(
    (id: string) => {
      const node = calcGraph.nodes.find((n) => n.id === id);
      setSelectedCalcNodeId(id);
      setSelectedCalcNodeIds(new Set([id]));
      if (!node) return;
      if (node.kind === 'mapped-element' && node.elementId) {
        setSelectedNodeIds(new Set([node.elementId]));
        setSelectedNodeId(node.elementId);
        setFit3dTrigger((c) => c + 1);
        return;
      }
      if (node.kind === 'calc' && node.calcKey) {
        setCalcAnchorKey(node.calcKey);
        const mapped = view?.calcToElementIds.get(node.calcKey) ?? [];
        setSelectedNodeIds(new Set(mapped));
        setSelectedNodeId(mapped[0] ?? null);
        if (mapped.length) setFit3dTrigger((c) => c + 1);
        return;
      }
      setCalcAnchorKey(null);
    },
    [calcGraph.nodes, view],
  );

  const selectCalcByKey = useCallback(
    (key: string) => {
      changeView('calculation-graph');
      setCalcAnchorKey(key);
      setSelectedCalcNodeId(calcNodeId(key));
      setSelectedCalcNodeIds(new Set([calcNodeId(key)]));
      const mapped = view?.calcToElementIds.get(key) ?? [];
      setSelectedNodeIds(new Set(mapped));
      setSelectedNodeId(mapped[0] ?? null);
    },
    [view, changeView],
  );

  const handleSelectGroup = useCallback(
    (groupId: string, opts?: { toggleMulti?: boolean }) => {
      const found = groups.find((g) => g.id === groupId);
      // a group outlives revisions; select the members this revision has
      const grp = found && { ...found, nodeIds: found.nodeIds.filter((id) => elementById.has(id)) };
      if (!grp || grp.nodeIds.length === 0) return;
      if (opts?.toggleMulti) {
        setSelectedNodeIds((prev) => {
          const next = new Set(prev);
          const allSelected = grp.nodeIds.every((id) => next.has(id));
          if (allSelected) {
            grp.nodeIds.forEach((id) => next.delete(id));
            setSelectedNodeId(next.size > 0 ? Array.from(next).pop() || null : null);
          } else {
            grp.nodeIds.forEach((id) => next.add(id));
            setSelectedNodeId(grp.nodeIds[0]);
          }
          return next;
        });
      } else {
        setSelectedNodeIds(new Set(grp.nodeIds));
        setSelectedNodeId(grp.nodeIds[0]);
      }
      setFit3dTrigger((c) => c + 1);
    },
    [groups, elementById],
  );

  const handleRenameGroup = useCallback(
    (groupId: string, newName: string) => {
      const trimmed = newName.trim();
      if (!trimmed) return;
      setGroups((prev) => prev.map((g) => (g.id === groupId ? { ...g, name: trimmed } : g)));
      showToast(`Renamed group to "${trimmed}"`);
    },
    [showToast],
  );

  const handleMoveNodes = useCallback(
    (movedIds: Set<string>, dx: number, dy: number) => {
      setMoved((prev) => {
        const next = new Map(prev);
        movedIds.forEach((id) => {
          const n = elementById.get(id);
          if (n) next.set(id, { x: n.x + dx, y: n.y + dy });
        });
        return next;
      });
    },
    [elementById],
  );

  const handleGroupSelection = useCallback(() => {
    const ids = Array.from(selectedNodeIds).filter((id) => elementById.has(id));
    if (ids.length < 2) {
      showToast('Shift + Click at least 2 elements before grouping (Ctrl+G).', true);
      return;
    }
    const selectedNodes = ids.map((id) => elementById.get(id)!);
    let cx = 0;
    let cy = 0;
    selectedNodes.forEach((n) => {
      cx += n.x;
      cy += n.y;
    });
    cx /= selectedNodes.length;
    cy /= selectedNodes.length;
    const sorted = [...selectedNodes].sort((a, b) => Math.atan2(a.y - cy, a.x - cx) - Math.atan2(b.y - cy, b.x - cx));
    const maxR = Math.max(...sorted.map((n) => n.r || 12));
    const spacing = maxR * 2.35;
    const cols = Math.ceil(Math.sqrt(sorted.length));
    setMoved((prev) => {
      const next = new Map(prev);
      sorted.forEach((n, idx) => {
        const r = Math.floor(idx / cols);
        const c = idx % cols;
        const colsInRow = Math.min(cols, sorted.length - r * cols);
        next.set(n.id, {
          x: cx + (c - (colsInRow - 1) / 2) * spacing,
          y: cy + (r - (Math.ceil(sorted.length / cols) - 1) / 2) * spacing,
        });
      });
      return next;
    });
    const idSet = new Set(ids);
    setGroups((prev) => {
      const cleaned = prev.map((g) => ({ ...g, nodeIds: g.nodeIds.filter((nid) => !idSet.has(nid)) })).filter((g) => g.nodeIds.length >= 2);
      return [...cleaned, { id: `grp-${Date.now()}`, name: `GROUP ${cleaned.length + 1}`, nodeIds: ids }];
    });
    showToast(`Grouped ${ids.length} elements (Ctrl+G)`);
  }, [selectedNodeIds, elementById, showToast]);

  // Escape with no menu or panel open (they close themselves through the escape stack)
  useEscapeFallback(() => {
    setDocFilterBySelected(false);
    setImpactReq(null);
    handleClearSelection();
  });
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.defaultPrevented || (t && (['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName) || t.isContentEditable))) return;
      // groups live on the element graph: Ctrl/Cmd+G elsewhere is the browser's
      if (activeView === 'element-graph' && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        handleGroupSelection();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activeView, handleGroupSelection]);

  // ---------------------------------------------------------------- actions
  const run = useCallback(
    async (text: string, fn: () => Promise<string | void>) => {
      setBusyText(text);
      try {
        const done = await fn();
        if (done) showToast(done);
        setFit3dTrigger((c) => c + 1);
      } catch (e) {
        showToast(errMsg(e), true);
      } finally {
        setBusyText('');
      }
    },
    [showToast],
  );

  const sampleError = (e: unknown) => (e instanceof SampleMissingError ? e.message : errMsg(e));

  const handleLoadSample = () =>
    run('Loading the sample building and calc package…', async () => {
      try {
        const out = await sample.mutateAsync({ rev: 1, projectId: null });
        switchProject(out.projectId);
      } catch (e) {
        throw new Error(sampleError(e));
      }
      return 'Sample loaded: model, calc package and links';
    });

  /**
   * After a revision was added to `target` by an action that started in scope epoch `startEpoch`:
   * show it (back from an export view; into diff `diff`, else out of diff mode so the new head is
   * shown), but only if the user is still in the scope the action started in. A project switched to
   * meanwhile is never switched away from. Returns whether it was shown.
   */
  const showAddedRevision = useCallback(
    (target: string, startEpoch: number, diff?: { a: number; b: number }) => {
      if (scopeRef.current.epoch !== startEpoch) return false;
      enterScope({ projectId: target }, diff);
      if (!diff) {
        setDiffRevs(null);
        setDiffFilter('ALL');
      }
      setCompareOpen(false);
      return true;
    },
    [enterScope],
  );
  const projectName = (id: string) => projectsQ.data?.find((x) => x.id === id)?.name ?? 'its project';

  const handleLoadSampleRev2 = () =>
    run('Adding sample model rev 2 (column C8 removed)…', async () => {
      const before = headModelRev;
      const startEpoch = scopeRef.current.epoch;
      let out: { projectId: string; modelRevisionId: number };
      try {
        out = await sample.mutateAsync({ rev: 2, projectId: pid });
      } catch (e) {
        throw new Error(sampleError(e));
      }
      const shown = showAddedRevision(out.projectId, startEpoch, before != null ? { a: before, b: out.modelRevisionId } : undefined);
      return shown ? 'Model rev 2 added and made the head' : `Model rev 2 added to ${projectName(out.projectId)}`;
    });

  const handleLoadSupplement = () =>
    run('Adding the sample calc supplement…', async () => {
      if (!pid) throw new Error('Open a project first (Load sample).');
      let placed;
      try {
        placed = await supplement.mutateAsync(pid);
      } catch (e) {
        throw new Error(sampleError(e));
      }
      setCompareOpen(false);
      return calcPlacementText('calc_supplement.pdf', placed.placement, placed.revision?.id ?? null);
    });

  const handleLoadDemo = () =>
    run('Loading the Harborview A/B demo (demo data)…', async () => {
      let out: { projectId: string; a: number; b: number };
      try {
        out = await demo.mutateAsync();
      } catch (e) {
        throw new Error(sampleError(e));
      }
      enterScope({ projectId: out.projectId }, { a: out.a, b: out.b });
      return 'Harborview demo loaded as two model revisions, compared A → B';
    });

  /**
   * The one path a chosen file becomes a revision of the store project (header menu, empty state,
   * revision panel, Open file). The revision goes to the project open when the action started (also
   * when an export view is shown over it); once added it is shown through showAddedRevision. With
   * `compareWithHead`, a new model revision is shown as the diff (previous head -> new revision).
   * `kind: 'any'` dispatches by content (openAnyFile): a project file opens as a new project and an
   * export JSON as a read-only view instead. Calcs take several PDFs at once (one large package, one PDF
   * per calc, or a new revision of some): each is placed in turn, and the toast says where each went.
   */
  const addRevisionFile = (kind: 'model' | 'calcs' | 'any', files: File | File[], opts?: { compareWithHead?: boolean }) => {
    const list = Array.isArray(files) ? files : [files];
    const file = list[0];
    if (!file) return;
    return run(`${kind === 'any' ? 'Opening' : 'Reading'} ${list.length > 1 ? `${list.length} PDFs` : file.name}…`, async () => {
      const target = projectId;
      if (!target) throw new Error('The project store is still opening; try again in a moment.');
      const startEpoch = scopeRef.current.epoch;
      const before = headModelRev;
      let added: { kind: 'model' | 'calcs'; id: number; warnings: string[]; placement?: CalcPlacement };
      if (kind === 'any') {
        const opened = await openAnyFile(target, file, setBusyText);
        if (opened.kind === 'export') {
          const v = exportFileView(opened.export);
          enterScope({ exportView: v });
          return `Opened ${file.name}: ${v.elementNodes.filter((x) => x.kind === 'element').length} elements, ${v.calcs.length} calcs (read-only export)`;
        }
        await queryClient.invalidateQueries({ queryKey: ['projects'] });
        if (opened.kind === 'project') {
          switchProject(opened.projectId);
          return `Imported project from ${file.name}`;
        }
        if (opened.kind === 'duplicate') return calcPlacementText(file.name, opened.placement, null);
        added = { kind: opened.revision.kind, id: opened.revision.id, warnings: opened.warnings, placement: opened.placement };
      } else if (kind === 'model') {
        const out = await uploadModel.mutateAsync({ projectId: target, file });
        added = { kind: 'model', id: out.revisionId, warnings: out.warnings };
      } else {
        // one at a time: each placement sees the documents the PDFs before it made
        const placed: { name: string; placement: CalcPlacement; id: number | null }[] = [];
        for (const [i, f] of list.entries()) {
          if (list.length > 1) setBusyText(`Reading ${f.name} (${i + 1} of ${list.length})…`);
          const out = await uploadCalcs.mutateAsync({ projectId: target, file: f });
          placed.push({ name: f.name, placement: out.placement, id: out.revisionId });
        }
        const last = [...placed].reverse().find((x) => x.id != null);
        if (!last) return placed.map((x) => calcPlacementText(x.name, x.placement, null)).join('; ');
        if (list.length > 1) {
          showAddedRevision(target, startEpoch, undefined);
          const fresh = placed.filter((x) => x.placement.kind === 'new').length;
          const revs = placed.filter((x) => x.placement.kind === 'revision').length;
          const dups = placed.length - fresh - revs;
          return `${list.length} calc PDFs: ${fresh} new document${fresh === 1 ? '' : 's'}, ${revs} new revision${revs === 1 ? '' : 's'}${dups ? `, ${dups} already loaded` : ''}. See Revisions to move any.`;
        }
        added = { kind: 'calcs', id: last.id!, warnings: [], placement: last.placement };
      }
      if (added.warnings.length) console.warn(`${file.name}: ${added.warnings.length} import warnings`, added.warnings);
      const diff = opts?.compareWithHead && added.kind === 'model' && before != null ? { a: before, b: added.id } : undefined;
      const shown = showAddedRevision(target, startEpoch, diff);
      const what = added.placement
        ? calcPlacementText(file.name, added.placement, added.id)
        : `${file.name} added as ${added.kind === 'model' ? 'model' : 'calc'} revision #${added.id}`;
      return shown ? what : `${what} of ${projectName(target)}`;
    });
  };
  const handleUpload = (kind: 'model' | 'calcs', file: File | File[]) => addRevisionFile(kind, file);
  /** Any accepted file, by content: model or calc PDF -> revision; project file -> new project; export -> read-only view. */
  const handleOpenFile = (file: File) => addRevisionFile('any', file);

  const handleMoveCalcRevision = (revisionId: number, docId: string | 'new') =>
    run('Moving the calc revision…', async () => {
      const to = await moveCalcRevision.mutateAsync({ revisionId, docId });
      const name = projectQ.data?.calcDocuments.find((d) => d.docId === to)?.name;
      return `Calc revision #${revisionId} moved to ${docId === 'new' ? 'a new document' : name ?? to}`;
    });
  const handleSetDocumentRemoved = (docId: string, removed: boolean) =>
    run(removed ? 'Withdrawing the calc document…' : 'Restoring the calc document…', async () => {
      await changeDocument.mutateAsync({ docId, removed });
      const name = projectQ.data?.calcDocuments.find((d) => d.docId === docId)?.name ?? docId;
      return removed ? `${name} withdrawn from the calc set (kept; restore it from Revisions)` : `${name} restored to the calc set`;
    });

  // OS drag & drop anywhere on the window: the same paths as the header's file pickers. Calc PDFs dropped together
  // are one upload (placed per document, like "Add calc PDFs"); anything else opens one file at a time. The
  // "compare" zone (shown once a model is loaded) adds a model revision and diffs it against the current head.
  const handleDropFiles = (files: File[], slot: DropSlot) => {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith('.pdf'));
    if (slot !== 'compare' && pdfs.length > 0 && pdfs.length === files.length) {
      void handleUpload('calcs', pdfs);
      return;
    }
    const file = files.find((f) => DROP_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext)));
    if (!file) {
      showToast(`Can't open ${files.map((f) => f.name).join(', ')}. Drop a ${DROP_EXTENSIONS.join(' / ')} file.`, true);
      return;
    }
    if (files.length > 1) showToast(`Opening ${file.name}; drop one file at a time (${files.length - 1} ignored).`, true);
    if (slot === 'compare' && headModelRev != null) void addRevisionFile('model', file, { compareWithHead: true });
    else void handleOpenFile(file);
  };
  const { isDragging, hoverSlot } = useFileDrop(handleDropFiles);

  const handleSaveProject = () =>
    run('Packing the project…', async () => {
      if (!pid) throw new Error('No project to save.');
      return `Saved ${await downloadProjectFile(pid)}`;
    });

  const handleExportBundle = () =>
    run('Packing the model bundle…', async () => {
      if (!pid) throw new Error('No project to export.');
      return `Saved ${await downloadModelBundle(pid, shownModelRev)}`;
    });

  const handleNewProject = () =>
    run('Creating a project…', async () => {
      switchProject(await createProject.mutateAsync('Untitled project'));
      return 'New empty project';
    });

  const handleDecide = useCallback(
    (elementId: string, calcKey: string, action: DecisionAction) => {
      decide
        .mutateAsync({ elementId, calcKey, action, modelRev: shownModelRev })
        .then(() =>
          showToast(
            action === 'confirm' ? 'Link confirmed' : action === 'reject' ? 'Link rejected' : action === 'manual' ? 'Linked by hand' : 'Decision undone',
          ),
        )
        .catch((e) => showToast(`Decision failed: ${errMsg(e)}`, true));
    },
    [decide, showToast, shownModelRev],
  );

  /**
   * Enter diff mode on model revisions (A, B) of the open project, chosen in the panel or named by a
   * deep link: checked against the project's revisions first (diffRevisionsError), so an id from
   * another browser's store or a calc revision is refused with the reason instead of failing B's view.
   */
  const requestDiff = (a: number, b: number): boolean => {
    const why = diffRevisionsError(revisions, a, b);
    if (why) {
      showToast(`Cannot compare #${a} with #${b}: ${why}`, true);
      return false;
    }
    setDiffRevs({ a, b });
    setDiffFilter('ALL');
    return true;
  };
  const handleCompare = (a: number, b: number) => {
    if (requestDiff(a, b)) setCompareOpen(false);
  };
  // swapping or leaving keeps the selection where its element exists in the new view (keepWhatExists)
  const handleSwapDatabases = () => {
    if (!diffRevs) return;
    setDiffRevs({ a: diffRevs.b, b: diffRevs.a });
    showToast(`Swapped: A is now #${diffRevs.b}, B is now #${diffRevs.a}`);
  };
  const handleClearDiff = () => {
    setDiffRevs(null);
    setDiffFilter('ALL');
    showToast('Exited diff mode');
  };

  const handleResetAll = useCallback(() => {
    setFilters(NO_FILTERS);
    setDiffFilter('ALL');
    setImpactReq(null);
    handleClearSelection();
    setMoved(new Map());
    setViewer3dDock('float');
    setInspectorDock('float');
    setLeftDockWidth(340);
    setRightDockWidth(360);
    setDocFilterBySelected(false);
    setPdfTarget(null);
    setDocumentOpenRequest((c) => c + 1);
    setResetTrigger((c) => c + 1);
    showToast('View, filters & panels reset');
  }, [handleClearSelection, showToast]);

  const openTarget = useCallback(
    (t: PdfTarget, elementId?: string) => {
      if (elementId) {
        handleSelectElementNode(elementId, { skipZoomFit: true });
        setDocFilterBySelected(true);
      }
      setPdfTarget(t);
      setDocumentOpenRequest((c) => c + 1);
      changeView('docs');
    },
    [handleSelectElementNode, changeView],
  );

  const showElementCalcs = useCallback(
    (elementId: string) => {
      const el = elementById.get(elementId);
      const top = el?.calcLinks?.find((l) => l.review !== 'rejected');
      const c = top ? view?.calcs.find((x) => x.key === top.calcKey) : undefined;
      handleSelectElementNode(elementId, { skipZoomFit: true });
      setDocFilterBySelected(true);
      if (top && c) setPdfTarget({ calcKey: c.key, page: top.evidence.page ?? c.pages[0] ?? 1, rects: top.evidence.rects, caption: `Matched "${top.matchedText}"` });
      setDocumentOpenRequest((n) => n + 1);
      changeView('docs');
    },
    [elementById, view, handleSelectElementNode, changeView],
  );

  const dropFromHash = (key: string) => {
    const h = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    if (!h.has(key)) return;
    h.delete(key);
    const rest = h.toString();
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${rest ? `#${rest}` : ''}`);
  };

  // the deep link belongs to the project the app opened with (scope epoch 0) and is applied once,
  // when that project's view has loaded; an empty or failed opening project, or a switch to another
  // project first, drops it rather than carrying it to whatever opens next
  const [deepLink, setDeepLink] = useState(readDeepLink);
  useEffect(() => {
    const h = deepLink;
    if (!h) return;
    if (scope.epoch !== 0) {
      setDeepLink(null);
      return;
    }
    if (!pid || projectQ.isPending || projectQ.isFetching) return;
    setDeepLink(null);
    if (!view || !hasProject) return;
    const el = h.get('el');
    const calc = h.get('calc');
    const v = h.get('view') as WorkspaceView | null;
    if (el && elementById.has(el)) handleSelectElementNode(el);
    if (calc) selectCalcByKey(calc);
    if (v && ['element-graph', 'calculation-graph', '3d', 'docs'].includes(v)) changeView(v);
    if (el && h.get('evidence')) showElementCalcs(el);
    const imp = h.get('impact');
    if (el && (imp === 'change' || imp === 'remove')) setImpactReq({ gid: el, mode: imp });
    const cmp = h.get('compare')?.split(',').map(Number);
    // a refused pair is dropped from the URL too, so a reload does not refuse it again
    if (cmp && !(cmp.length === 2 && requestDiff(cmp[0], cmp[1]))) dropFromHash('compare');
    const color = h.get('color') as ColorMode | null;
    if (color === 'review' || color === 'confidence' || color === 'type') setColorMode(color);
  }, [deepLink, scope.epoch, pid, projectQ.isPending, projectQ.isFetching, view, hasProject, elementById, handleSelectElementNode, selectCalcByKey, showElementCalcs, changeView]);

  // ---------------------------------------------------------------- panels
  const defaultV3dPos = useMemo(
    () => ({ left: Math.max(20, (typeof window !== 'undefined' ? window.innerWidth : 1280) - 360), top: 108, width: 340, height: 260 }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resetTrigger],
  );
  const defaultInspPos = useMemo(
    () => ({
      left: Math.max(20, (typeof window !== 'undefined' ? window.innerWidth : 1280) - 360),
      top: 384,
      width: 340,
      height: Math.max(260, (typeof window !== 'undefined' ? window.innerHeight : 800) - 404),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resetTrigger],
  );

  const showViewer3d = hasProject && (activeView === 'element-graph' || activeView === 'calculation-graph');
  const showInspector = hasProject && activeView !== 'docs';
  const leftDockedHasItems = (showViewer3d && viewer3dDock === 'left') || (showInspector && inspectorDock === 'left');
  const rightDockedHasItems = (showViewer3d && viewer3dDock === 'right') || (showInspector && inspectorDock === 'right');

  const startDockColumnResize = (side: 'left' | 'right') => (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = side === 'left' ? leftDockWidth : rightDockWidth;
    const onMove = (ev: PointerEvent) => {
      const dx = ev.clientX - startX;
      const raw = side === 'left' ? startW + dx : startW - dx;
      const clamped = Math.max(260, Math.min(560, raw));
      if (side === 'left') setLeftDockWidth(clamped);
      else setRightDockWidth(clamped);
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const modelUrl = view?.modelFileUrl ?? null;
  // ghosts of a diff are meshed from their own revision's IFC; JSON-model revisions fall back to boxes
  const ghostRids = (diffApplied?.ghosts ?? []).map((g) => g.revisionId).filter((rid) => revisions?.find((r) => r.id === rid)?.isIfc);
  const ghostUrls = useRevisionUrls(ghostRids);
  const pdfUrl = exportView ? null : (projectQ.data?.pdfUrl ?? null);
  const pdfUrls = exportView ? undefined : projectQ.data?.pdfUrls;
  const ghostSources = useMemo(
    () =>
      (diffApplied?.ghosts ?? [])
        .filter((g) => ghostUrls.data?.has(g.revisionId))
        .map((g) => ({ url: ghostUrls.data!.get(g.revisionId)!, gids: g.elementIds })),
    [diffApplied, ghostUrls.data],
  );
  const model3dEmpty =
    view?.source === 'file'
      ? 'An export JSON carries no geometry; open the project file or add the IFC to see the model.'
      : view?.modelRevisionId != null
        ? 'This model revision has no geometry (no IFC, and its elements carry no bounding boxes).'
        : 'No model in this project yet.';

  const viewer3d = (
    <Structural3DViewer
      nodes={elementNodes}
      modelUrl={modelUrl}
      ghostSources={ghostSources}
      selectedNodeId={selectedNodeId}
      selectedNodeIds={selectedNodeIds}
      activeLoadChainNodeIds={activeLoadChainNodeIds}
      matchingNodeIds={matchingNodeIds}
      isFilterActive={activeView !== 'calculation-graph' && isFilterActive}
      colorMode={colorMode}
      diffMode={diffMode}
      overlay={overlay}
      fitTrigger={fit3dTrigger}
      resetTrigger={resetTrigger}
      emptyText={model3dEmpty}
      onSelectNode={handleSelectElementNode}
    />
  );

  const status3d = diffMode
    ? `+${diffSummary?.addedCount} Added • ~${diffSummary?.modifiedCount} Mod • -${diffSummary?.removedCount} Rem`
    : impact
    ? `Impact: ${impact.removed.length} removed • ${impact.hit.size} hit`
    : selectedNodeId
    ? 'Selection & Load Path'
    : colorMode === 'review'
    ? 'Mapping status'
    : colorMode === 'confidence'
    ? 'Link confidence'
    : 'IFC Model';

  const renderViewer3dPanel = () => (
    <DockableHudPanel
      id="viewer3dPanel"
      title={diffMode ? '3D Diff Model (A vs B)' : '3D Structural Model'}
      indicatorClassName={
        diffMode || impact
          ? 'bg-amber-400'
          : selectedNodeId
          ? 'bg-amber-400'
          : 'bg-cyan-400'
      }
      dockSide={viewer3dDock}
      defaultPos={defaultV3dPos}
      zIndex={topHudZ.v3d}
      onFocus={() => setTopHudZ((z) => ({ v3d: Math.max(z.v3d, z.insp) + 1, insp: z.insp }))}
      onChangeDockSide={setViewer3dDock}
      onDragHoverEdge={setHoverEdge}
      headerActions={
        <>
          <button
            type="button"
            onClick={() => setFit3dTrigger((c) => c + 1)}
            title="Zoom to selection"
            className="mono text-[9px] px-1.5 py-0.5 rounded bg-calcmap/15 text-calcmap border border-calcmap/25 hover:bg-calcmap/25 transition mr-0.5"
          >
            FIT
          </button>
          <button
            type="button"
            onClick={() => setResetTrigger((c) => c + 1)}
            title="Reset 3D camera"
            aria-label="Reset 3D camera"
            className="text-zinc-500 hover:text-zinc-200 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-white/[0.06] transition"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </>
      }
    >
      <div className="relative flex-1 w-full h-full overflow-hidden bg-[#2d3139]">
        {viewer3d}
        <div className="absolute bottom-2 left-2.5 right-4 pointer-events-none flex items-center justify-between text-[10px] mono text-zinc-400 bg-black/65 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/[0.07]">
          <span className="truncate text-zinc-200">{status3d}</span>
          <span className="text-zinc-500 ml-2 flex-shrink-0" title="Drag: orbit · Middle or Shift+right drag: pan · Ctrl+right drag or wheel: zoom">Drag Orbit • MMB Pan • Wheel Zoom</span>
        </div>
      </div>
    </DockableHudPanel>
  );

  const inspectorNode =
    activeView === 'calculation-graph'
      ? calcGraph.nodes.find((n) => n.id === selectedCalcNodeId) ?? null
      : selectedNodeId
      ? elementById.get(selectedNodeId) ?? null
      : null;

  const renderInspectorPanel = () => (
    <DockableHudPanel
      id="inspectorPanel"
      title={diffMode ? 'Diff & Element Inspector' : activeView === 'calculation-graph' ? 'Calculation Inspector' : 'Element Inspector'}
      indicatorClassName="bg-calcmap"
      dockSide={inspectorDock}
      defaultPos={defaultInspPos}
      zIndex={topHudZ.insp}
      onFocus={() => setTopHudZ((z) => ({ v3d: z.v3d, insp: Math.max(z.v3d, z.insp) + 1 }))}
      onChangeDockSide={setInspectorDock}
      onDragHoverEdge={setHoverEdge}
    >
      <div className="p-4 pb-8 space-y-3 flex-1 overflow-y-auto text-xs">
        <PropertyInspector
          key={scope.epoch}
          node={inspectorNode}
          elementNodes={elementNodes}
          calcs={view?.calcs ?? []}
          calcDependencies={view?.calcDependencies ?? []}
          loadPath={view?.loadPath ?? []}
          connectivity={view?.connectivity ?? []}
          calcToElementIds={view?.calcToElementIds ?? new Map()}
          typicalGroups={view?.groups ?? []}
          findings={view?.findings ?? []}
          producers={view?.producers ?? null}
          counts={view ? view.counts : null}
          groups={groups}
          selectedNodeIds={activeView === 'calculation-graph' ? EMPTY_SET : selectedNodeIds}
          activeLoadChainNodeIds={activeLoadChainNodeIds}
          diffMode={diffMode}
          impact={impact}
          impactLoading={Boolean(impactReq) && impactQ.isFetching}
          canWrite={view?.source === 'project' && !viewIsPlaceholder}
          busy={decide.isPending || Boolean(busyText)}
          onSelectNode={(id) => {
            if (activeView === 'calculation-graph') changeView('element-graph');
            handleSelectElementNode(id);
          }}
          onSelectCalc={selectCalcByKey}
          onSelectGroup={(gid) => handleSelectGroup(gid)}
          onRenameGroup={handleRenameGroup}
          onClearSelection={handleClearSelection}
          onOpenTarget={openTarget}
          onShowElementCalcs={showElementCalcs}
          onDecide={handleDecide}
          onImpact={(gid, mode) => setImpactReq({ gid, mode })}
          onClearImpact={() => setImpactReq(null)}
        />
      </div>
      <div className="apple-panel-scroll-fade" />
    </DockableHudPanel>
  );

  const loading = storeInfo.isLoading || initialProject.isLoading || (pid != null && projectQ.isLoading);
  const calcOnly = Boolean(projectQ.data?.hasCalcPackage) && !projectQ.data?.view;

  const emptyState = (
    <div className="absolute inset-0 flex items-center justify-center p-6 z-10">
      <div className="bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] rounded-2xl px-7 py-6 text-center max-w-md w-full shadow-[0_24px_60px_rgba(0,0,0,0.85)]">
        <div className="w-11 h-11 mx-auto rounded-xl bg-calcmap/15 border border-calcmap/30 text-calcmap flex items-center justify-center mb-3">
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Network className="w-5 h-5" />}
        </div>
        <p className="mono text-[10px] text-calcmap uppercase tracking-widest mb-1">
          {loading ? 'Opening project' : calcOnly ? 'Calc package added' : 'No model in this project yet'}
        </p>
        <h2 className="text-sm font-semibold text-white">Map a structural model onto its calculations</h2>
        <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
          {calcOnly
            ? 'Add the IFC model the calcs design; every element is then linked to the calcs that name it, with the matched text as evidence.'
            : 'Add an IFC model and its calc package PDF; every element is linked to the calcs that design it, with the matched text as evidence. Everything stays in this browser.'}
        </p>
        <button
          type="button"
          disabled={Boolean(busyText)}
          onClick={handleLoadSample}
          className="mt-4 w-full bg-calcmap/20 hover:bg-calcmap/30 text-white border border-calcmap/40 rounded-xl py-2.5 text-sm font-semibold transition flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {busyText ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-calcmap" />}
          {busyText || 'Load sample'}
        </button>
        <div className="grid grid-cols-3 gap-1.5 mt-2">
          {[
            { icon: <Box className="w-3.5 h-3.5 text-cyan-300" aria-hidden="true" />, label: 'IFC model', accept: '.ifc,.json,application/json', multiple: false, on: (f: File[]) => handleUpload('model', f[0]!) },
            { icon: <FileText className="w-3.5 h-3.5 text-rose-300" aria-hidden="true" />, label: 'Calc PDFs', accept: '.pdf,application/pdf', multiple: true, on: (f: File[]) => handleUpload('calcs', f) },
            { icon: <FileJson className="w-3.5 h-3.5 text-amber-300" aria-hidden="true" />, label: 'Project file', accept: '.json,application/json', multiple: false, on: (f: File[]) => handleOpenFile(f[0]!) },
          ].map((b) => (
            <label
              key={b.label}
              className="bg-white/[0.04] hover:bg-white/[0.08] focus-within:ring-2 focus-within:ring-calcmap/60 text-zinc-200 border border-white/[0.14] rounded-lg py-2 text-[11px] font-medium transition flex flex-col items-center gap-1 cursor-pointer"
            >
              {b.icon}
              {b.label}
              <input
                type="file"
                accept={b.accept}
                multiple={b.multiple}
                className="sr-only"
                onChange={(e) => {
                  const fs = [...(e.target.files ?? [])];
                  if (fs.length) b.on(fs);
                  e.target.value = '';
                }}
              />
            </label>
          ))}
        </div>
        <button
          type="button"
          disabled={Boolean(busyText)}
          onClick={handleLoadDemo}
          className="mt-2 w-full text-[11px] text-zinc-400 hover:text-zinc-200 py-1.5 rounded-lg hover:bg-white/[0.04] transition disabled:opacity-40"
        >
          Or open the Harborview A/B diff demo <span className="text-amber-300/90">(invented calcs, demo data)</span>
        </button>
        {storeInfo.data && !storeInfo.data.persistent && (
          <p className="mt-3 text-[11px] text-amber-200/90 bg-amber-500/10 border border-amber-400/25 rounded-lg px-3 py-2 leading-snug text-left">
            This browser is not letting the app use IndexedDB (private window or blocked storage), so projects last only until the
            tab closes. Use <span className="font-semibold">Save project file</span> to keep your work.
          </p>
        )}
      </div>
    </div>
  );

  return (
    <div className="h-full bg-[#24272d] text-zinc-100 flex flex-col overflow-hidden select-none">
      <HeaderBar
        activeView={activeView}
        onChangeView={changeView}
        calcCount={view?.calcs.length ?? 0}
        persistent={storeInfo.data?.persistent ?? true}
        source={view?.source ?? null}
        busy={Boolean(busyText)}
        projects={(projectsQ.data ?? []).map((x) => ({ id: x.id, name: x.name }))}
        activeProjectId={pid}
        onSwitchProject={switchProject}
        onNewProject={handleNewProject}
        onSaveProject={pid ? handleSaveProject : null}
        onExportBundle={pid && view?.source === 'project' ? handleExportBundle : null}
        onLoadSample={handleLoadSample}
        onLoadDemo={handleLoadDemo}
        onUploadModel={(f) => handleUpload('model', f)}
        onUploadCalcs={(fs) => handleUpload('calcs', fs)}
        onOpenFile={handleOpenFile}
        diffRevs={diffRevs}
        compareOpen={compareOpen}
        onToggleCompare={() => setCompareOpen((v) => !v)}
        onSwapDatabases={handleSwapDatabases}
        onClearDiff={handleClearDiff}
        onResetAll={handleResetAll}
      />

      <FileDropOverlay
        visible={isDragging}
        hoverSlot={hoverSlot}
        hasBaseModel={headModelRev != null}
        acceptedExtensions={DROP_EXTENSIONS}
      />
      {compareOpen && (
        <RevisionPanel
          key={scope.epoch}
          projectId={pid}
          revisions={revisions}
          calcDocuments={projectQ.data?.calcDocuments ?? []}
          onAddCalcs={(fs) => handleUpload('calcs', fs)}
          onMoveCalcRevision={handleMoveCalcRevision}
          onSetDocumentRemoved={handleSetDocumentRemoved}
          loading={projectQ.isLoading}
          active={diffRevs}
          busy={Boolean(busyText)}
          onOpenRevisionFile={(rid) => {
            revisionFileUrl(rid).then((u) => u && window.open(u, '_blank', 'noopener'));
          }}
          onCompare={handleCompare}
          onLoadSampleRev2={handleLoadSampleRev2}
          onLoadSupplement={handleLoadSupplement}
          onUploadModel={(f) => addRevisionFile('model', f, { compareWithHead: true })}
          onClose={() => setCompareOpen(false)}
        />
      )}

      <FilterBar
        filters={filters}
        onChangeFilters={setFilters}
        onClearFilters={() => {
          setFilters(NO_FILTERS);
          setDiffFilter('ALL');
        }}
        isFilterActive={isFilterActive}
        categories={categories}
        floors={floors}
        traceDirection={traceDirection}
        onChangeTraceDirection={setTraceDirection}
        traceSteps={traceSteps}
        onChangeTraceSteps={setTraceSteps}
        colorMode={colorMode}
        diffSummary={activeView === 'calculation-graph' ? null : diffSummary}
        diffFilter={diffFilter}
        onChangeDiffFilter={setDiffFilter}
        impactActive={Boolean(impact)}
        matchedCount={matchingNodeIds.size}
        totalInstances={totalInstances}
      />

      {hoverEdge === 'left' && (
        <div className="fixed top-24 bottom-2 left-2 w-32 z-45 pointer-events-none border-2 border-dashed border-calcmap bg-calcmap/20 backdrop-blur-md rounded-2xl flex flex-col items-center justify-center gap-1.5 text-calcmap">
          <Columns className="w-5 h-5" />
          <span className="mono text-[10px] font-semibold uppercase tracking-wider">Dock Left</span>
        </div>
      )}
      {hoverEdge === 'right' && (
        <div className="fixed top-24 bottom-2 right-2 w-32 z-45 pointer-events-none border-2 border-dashed border-calcmap bg-calcmap/20 backdrop-blur-md rounded-2xl flex flex-col items-center justify-center gap-1.5 text-calcmap">
          <Columns className="w-5 h-5" />
          <span className="mono text-[10px] font-semibold uppercase tracking-wider">Dock Right</span>
        </div>
      )}

      <main className="flex-1 relative canvas-grid flex flex-row overflow-hidden">
        {leftDockedHasItems && (
          <>
            <div style={{ width: leftDockWidth }} className="bg-[#262a31]/95 backdrop-blur-2xl border-r border-white/[0.09] flex flex-col flex-shrink-0 overflow-hidden z-25">
              {showViewer3d && viewer3dDock === 'left' && renderViewer3dPanel()}
              {showInspector && inspectorDock === 'left' && renderInspectorPanel()}
            </div>
            <div onPointerDown={startDockColumnResize('left')} className="w-1.5 cursor-ew-resize hover:bg-calcmap/50 transition flex-shrink-0 z-25" />
          </>
        )}

        <div className="flex-1 relative h-full flex flex-col overflow-hidden min-w-0">
          {!hasProject && emptyState}

          {calcError && view && (
            <div
              role="alert"
              className="absolute top-3 left-1/2 -translate-x-1/2 z-20 w-[min(36rem,calc(100%-2rem))] flex items-start gap-2 bg-amber-500/12 backdrop-blur-xl border border-amber-400/35 text-amber-100 rounded-xl px-3 py-2 text-[11px] leading-snug shadow-[0_12px_32px_rgba(0,0,0,0.6)]"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-px" aria-hidden="true" />
              <span>
                <span className="font-semibold">Calc package unavailable; the model is shown without calc links.</span> {calcError}
              </span>
            </div>
          )}

          {hasProject && activeView === 'element-graph' && (
            <RadialGraphCanvas
              nodes={elementNodes}
              links={view?.hierarchyLinks ?? []}
              groups={groups}
              selectedNodeId={selectedNodeId}
              selectedNodeIds={selectedNodeIds}
              activeLoadChainNodeIds={activeLoadChainNodeIds}
              loadPath={view?.loadPath ?? []}
              activeLoadChainLinkKeys={activeLoadChainLinkKeys}
              matchingNodeIds={matchingNodeIds}
              isFilterActive={isFilterActive}
              colorMode={colorMode}
              diffMode={diffMode}
              overlay={overlay}
              showStatusRings={colorMode === 'type'}
              resetTrigger={resetTrigger}
              onSelectNode={handleSelectElementNode}
              onSelectGroup={handleSelectGroup}
              onRenameGroup={handleRenameGroup}
              onClearSelection={handleClearSelection}
              onMoveNodes={handleMoveNodes}
              onGroupSelection={handleGroupSelection}
            />
          )}

          {hasProject && activeView === 'calculation-graph' && (
            <RadialGraphCanvas
              nodes={calcGraph.nodes}
              links={calcGraph.links}
              groups={[]}
              selectedNodeId={selectedCalcNodeId}
              selectedNodeIds={selectedCalcNodeIds}
              activeLoadChainNodeIds={EMPTY_SET}
              matchingNodeIds={matchingNodeIds}
              isFilterActive={isFilterActive}
              colorMode={colorMode}
              overlay={overlay}
              resetTrigger={resetTrigger}
              onSelectNode={(id) => handleSelectCalcNode(id)}
              onClearSelection={handleClearSelection}
              onMoveNodes={() => {}}
              onGroupSelection={() => {}}
            />
          )}

          {hasProject && activeView === '3d' && (
            <section className="w-full h-full relative flex flex-col overflow-hidden bg-[#2d3139]">
              <div className="absolute top-4 left-4 z-10 flex items-center space-x-2 bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] px-3 py-1.5 rounded-xl shadow-[0_12px_32px_rgba(0,0,0,0.8)]">
                <span className="w-2 h-2 rounded-full bg-calcmap" />
                <span className="mono text-[11px] text-zinc-200 font-medium">{view?.modelName ?? 'Model'}</span>
                <span className="text-zinc-700">|</span>
                <span className="mono text-[10px] text-zinc-400">{status3d}</span>
                <span className="text-zinc-700">|</span>
                <button
                  type="button"
                  onClick={() => setFit3dTrigger((c) => c + 1)}
                  className="mono text-[10px] px-2 py-0.5 rounded bg-calcmap/15 text-calcmap border border-calcmap/25 hover:bg-calcmap/25 transition flex items-center gap-1"
                >
                  <Crosshair className="w-3 h-3" />
                  Zoom Fit
                </button>
                <button
                  type="button"
                  onClick={() => setResetTrigger((c) => c + 1)}
                  className="mono text-[10px] px-2 py-0.5 rounded bg-white/[0.05] text-zinc-300 border border-white/[0.14] hover:bg-white/[0.1] transition flex items-center gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  Reset
                </button>
              </div>
              {viewer3d}
            </section>
          )}

          {hasProject && activeView === 'docs' && view && (
            // the fragment's key remounts the browser on every explicit open (its search, tab or open
            // comparison could otherwise hide the target); its own key is the project scope's epoch
            <React.Fragment key={documentOpenRequest}>
            <DocumentBrowser
              key={scope.epoch}
              calcs={view.calcs}
              calcPackageName={view.calcPackageName}
              calcOrigin={view.calcOrigin}
              pdfUrl={pdfUrl}
              pdfUrls={pdfUrls}
              elementNodes={elementNodes}
              calcToElementIds={view.calcToElementIds}
              calcDependencies={view.calcDependencies}
              groups={view.groups}
              findings={view.findings}
              onSelectElements={(ids) => {
                if (!ids.length) return;
                setSelectedNodeIds(new Set(ids));
                setSelectedNodeId(ids[0]);
                setFit3dTrigger((c) => c + 1);
              }}
              selectedElement={selectedNodeId ? elementById.get(selectedNodeId) ?? null : null}
              filterBySelectedElement={docFilterBySelected}
              onClearElementFilter={() => setDocFilterBySelected(false)}
              target={pdfTarget ?? (view.calcs.find((c) => !c.frontMatter) ? calcTarget(view.calcs.find((c) => !c.frontMatter)!) : null)}
              onChangeTarget={setPdfTarget}
              diffMode={diffMode}
              onLocateElement={(nodeId, v) => {
                handleSelectElementNode(nodeId);
                changeView(v);
              }}
              onLocateCalc={selectCalcByKey}
            />
            </React.Fragment>
          )}
        </div>

        {rightDockedHasItems && (
          <>
            <div onPointerDown={startDockColumnResize('right')} className="w-1.5 cursor-ew-resize hover:bg-calcmap/50 transition flex-shrink-0 z-25" />
            <div style={{ width: rightDockWidth }} className="bg-[#262a31]/95 backdrop-blur-2xl border-l border-white/[0.09] flex flex-col flex-shrink-0 overflow-hidden z-25">
              {showViewer3d && viewer3dDock === 'right' && renderViewer3dPanel()}
              {showInspector && inspectorDock === 'right' && renderInspectorPanel()}
            </div>
          </>
        )}
      </main>

      {showViewer3d && viewer3dDock === 'float' && renderViewer3dPanel()}
      {showInspector && inspectorDock === 'float' && renderInspectorPanel()}

      <div
        className={`fixed bottom-5 left-5 bg-[#2d3139]/92 backdrop-blur-xl text-zinc-100 px-4 py-3 rounded-xl border border-white/[0.12] shadow-[0_12px_32px_rgba(0,0,0,0.9)] flex items-center space-x-3 transition-[transform,opacity] duration-300 z-50 max-w-md ${
          busyText || viewBusy || toast.visible ? 'translate-y-0 opacity-100' : 'translate-y-24 opacity-0 pointer-events-none'
        }`}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {busyText || viewBusy ? (
          <Loader2 className="w-4 h-4 text-calcmap animate-spin flex-shrink-0" aria-hidden="true" />
        ) : toast.isError ? (
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
        ) : (
          <CheckCircle2 className="w-4 h-4 text-calcmap flex-shrink-0" />
        )}
        <div className="text-xs font-medium">{busyText || viewBusy || (toast.visible ? toast.message : '')}</div>
      </div>
    </div>
  );
};

export default App;
