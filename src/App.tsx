import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
  useBackendHealth,
  useCompare,
  useDecide,
  useImpact,
  useLoadSample,
  useProjectId,
  useProjectView,
  useRevisions,
  useUpload,
} from './api/hooks';
import { urls } from './api/client';
import { applyModelDiff, calcNodeId, loadProjectFromFile } from './data/loadProject';
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

const EMPTY_SET = new Set<string>();
const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<WorkspaceView>('element-graph');
  const [colorMode, setColorMode] = useState<ColorMode>('type');
  const [traceDirection, setTraceDirection] = useState<TraceDirection>('down');
  const [traceSteps, setTraceSteps] = useState<number>(16);

  // ---------------------------------------------------------------- data (backend or an export file)
  const health = useBackendHealth();
  const backend: 'checking' | 'online' | 'offline' = health.isSuccess ? 'online' : health.isError ? 'offline' : 'checking';
  const online = backend === 'online';
  const [offlineView, setOfflineView] = useState<ProjectViewModel | null>(null);
  const pidQ = useProjectId(online);
  const pid = online ? (pidQ.data ?? null) : null;
  const viewQ = useProjectView(offlineView ? null : pid);
  const revisionsQ = useRevisions(offlineView ? null : pid);
  const decide = useDecide(pid);
  const sample = useLoadSample(pid);
  const upload = useUpload(pid);

  const [diffRevs, setDiffRevs] = useState<{ a: number; b: number } | null>(null);
  const [diffFilter, setDiffFilter] = useState<DiffFilter>('ALL');
  const [compareOpen, setCompareOpen] = useState(false);
  const compareQ = useCompare(offlineView ? null : pid, diffRevs?.a ?? null, diffRevs?.b ?? null);

  const [impactReq, setImpactReq] = useState<{ gid: string; mode: 'change' | 'remove' } | null>(null);
  const impactQ = useImpact(offlineView ? null : pid, impactReq?.gid ?? null, impactReq?.mode ?? 'change');
  const impact = impactReq && impactQ.data && impactQ.data.elementId === impactReq.gid && impactQ.data.mode === impactReq.mode ? impactQ.data : null;

  const baseView: ProjectViewModel | null = offlineView ?? viewQ.data ?? null;

  const diffApplied = useMemo(() => {
    if (!baseView || !diffRevs || !compareQ.data) return null;
    const label = (rid: number) => {
      const r = revisionsQ.data?.find((x) => x.id === rid);
      return r ? `#${rid} ${r.label}` : `Revision #${rid}`;
    };
    return applyModelDiff(baseView, compareQ.data, { base: label(diffRevs.a), compare: label(diffRevs.b) });
  }, [baseView, diffRevs, compareQ.data, revisionsQ.data]);
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
  const [filters, setFilters] = useState<FilterState>({ search: '', type: 'ALL', level: 'ALL' });
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
  const [busyText, setBusyText] = useState('');

  const [toast, setToast] = useState<{ message: string; isError: boolean; visible: boolean }>({ message: '', isError: false, visible: false });
  const showToast = useCallback((message: string, isError = false) => {
    setToast({ message, isError, visible: true });
    window.setTimeout(() => setToast((prev) => (prev.message === message ? { ...prev, visible: false } : prev)), isError ? 7000 : 3400);
  }, []);

  useEffect(() => {
    if (viewQ.error) showToast(`Could not load the project: ${errMsg(viewQ.error)}`, true);
  }, [viewQ.error, showToast]);
  useEffect(() => {
    if (impactQ.error) showToast(`Impact check failed: ${errMsg(impactQ.error)}`, true);
  }, [impactQ.error, showToast]);
  useEffect(() => {
    if (compareQ.error) showToast(`Compare failed: ${errMsg(compareQ.error)}`, true);
  }, [compareQ.error, showToast]);
  useEffect(() => {
    if (diffSummary) showToast(`Diff ready: +${diffSummary.addedCount} added, ~${diffSummary.modifiedCount} modified, -${diffSummary.removedCount} removed`);
  }, [diffSummary, showToast]);

  const handleClearSelection = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedNodeIds(new Set());
    setSelectedCalcNodeId(null);
    setSelectedCalcNodeIds(new Set());
    setCalcAnchorKey(null);
  }, []);

  // a different project / revision pair: drop layout tweaks, groups and selection
  const projectKey = baseView ? `${baseView.source}:${baseView.modelRevisionId}:${baseView.calcRevisionId}` : 'none';
  useEffect(() => {
    setGroups([]);
    setMoved(new Map());
    handleClearSelection();
    setImpactReq(null);
    setPdfTarget(null);
    setResetTrigger((c) => c + 1);
  }, [projectKey, handleClearSelection]);

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

  const isDiffFilterActive = Boolean(diffSummary && diffFilter !== 'ALL');
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
      setActiveView('calculation-graph');
      setCalcAnchorKey(key);
      setSelectedCalcNodeId(calcNodeId(key));
      setSelectedCalcNodeIds(new Set([calcNodeId(key)]));
      const mapped = view?.calcToElementIds.get(key) ?? [];
      setSelectedNodeIds(new Set(mapped));
      setSelectedNodeId(mapped[0] ?? null);
    },
    [view],
  );

  const handleSelectGroup = useCallback(
    (groupId: string, opts?: { toggleMulti?: boolean }) => {
      const grp = groups.find((g) => g.id === groupId);
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
    [groups],
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

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        handleGroupSelection();
      } else if (e.key === 'Escape') {
        setDocFilterBySelected(false);
        setImpactReq(null);
        setCompareOpen(false);
        handleClearSelection();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleGroupSelection, handleClearSelection]);

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

  const handleLoadSample = () =>
    run('Ingesting the sample building and calc package…', async () => {
      setOfflineView(null);
      setDiffRevs(null);
      await sample.mutateAsync(1);
      return 'Sample loaded: model, calc package and links';
    });

  const handleLoadSampleRev2 = () =>
    run('Ingesting sample model rev 2 (column C8 removed)…', async () => {
      const before = baseView?.modelRevisionId ?? null;
      const out = await sample.mutateAsync(2);
      setCompareOpen(false);
      if (before != null && out.modelRevisionId != null) {
        setDiffRevs({ a: before, b: out.modelRevisionId });
        setDiffFilter('ALL');
      }
      return 'Model rev 2 ingested and made the head';
    });

  const handleUpload = (kind: 'model' | 'calcs', file: File) =>
    run(`Reading ${file.name}…`, async () => {
      setOfflineView(null);
      setDiffRevs(null);
      await upload.mutateAsync({ kind, file });
      return kind === 'model' ? `Model ${file.name} ingested and re-mapped` : `Calc package ${file.name} ingested and re-mapped`;
    });

  const handleOpenExport = (file: File) => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const v = loadProjectFromFile(String(ev.target?.result ?? ''));
        setDiffRevs(null);
        setOfflineView(v);
        showToast(`Opened ${file.name}: ${v.elementNodes.filter((n) => n.kind === 'element').length} elements, ${v.calcs.length} calcs (read-only)`);
      } catch (e) {
        showToast(`Could not open ${file.name}: ${errMsg(e)}`, true);
      }
    };
    reader.onerror = () => showToast('Failed to read file from disk.', true);
    reader.readAsText(file);
  };

  const handleDecide = useCallback(
    (elementId: string, calcKey: string, action: DecisionAction) => {
      decide
        .mutateAsync({ elementId, calcKey, action })
        .then(() =>
          showToast(
            action === 'confirm' ? 'Link confirmed' : action === 'reject' ? 'Link rejected' : action === 'manual' ? 'Linked by hand' : 'Decision undone',
          ),
        )
        .catch((e) => showToast(`Decision failed: ${errMsg(e)}`, true));
    },
    [decide, showToast],
  );

  const handleCompare = (a: number, b: number) => {
    setDiffRevs({ a, b });
    setDiffFilter('ALL');
    setCompareOpen(false);
  };
  const handleSwapDatabases = () => {
    if (!diffRevs) return;
    setDiffRevs({ a: diffRevs.b, b: diffRevs.a });
    handleClearSelection();
    showToast(`Swapped: A is now #${diffRevs.b}, B is now #${diffRevs.a}`);
  };
  const handleClearDiff = () => {
    setDiffRevs(null);
    setDiffFilter('ALL');
    handleClearSelection();
    showToast('Exited diff mode');
  };

  const handleResetAll = useCallback(() => {
    setFilters({ search: '', type: 'ALL', level: 'ALL' });
    setDiffFilter('ALL');
    setImpactReq(null);
    handleClearSelection();
    setMoved(new Map());
    setViewer3dDock('float');
    setInspectorDock('float');
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
      setActiveView('docs');
    },
    [handleSelectElementNode],
  );

  const showElementCalcs = useCallback(
    (elementId: string) => {
      const el = elementById.get(elementId);
      const top = el?.calcLinks?.find((l) => l.review !== 'rejected');
      const c = top ? view?.calcs.find((x) => x.key === top.calcKey) : undefined;
      handleSelectElementNode(elementId, { skipZoomFit: true });
      setDocFilterBySelected(true);
      if (top && c) setPdfTarget({ calcKey: c.key, page: top.evidence.page ?? c.pages[0] ?? 1, rects: top.evidence.rects, caption: `Matched "${top.matchedText}"` });
      setActiveView('docs');
    },
    [elementById, view, handleSelectElementNode],
  );

  // deep link, applied once the project has loaded: #view=docs&el=<GlobalId>&evidence=1&impact=remove&calc=<key>&compare=A,B
  const [deepLinkDone, setDeepLinkDone] = useState(false);
  useEffect(() => {
    if (deepLinkDone || !view || !hasProject) return;
    setDeepLinkDone(true);
    const h = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const el = h.get('el');
    const calc = h.get('calc');
    const v = h.get('view') as WorkspaceView | null;
    if (el && elementById.has(el)) handleSelectElementNode(el);
    if (calc) selectCalcByKey(calc);
    if (v && ['element-graph', 'calculation-graph', '3d', 'docs'].includes(v)) setActiveView(v);
    if (el && h.get('evidence')) showElementCalcs(el);
    const imp = h.get('impact');
    if (el && (imp === 'change' || imp === 'remove')) setImpactReq({ gid: el, mode: imp });
    const cmp = h.get('compare')?.split(',').map(Number);
    if (cmp && cmp.length === 2 && cmp.every(Number.isFinite)) setDiffRevs({ a: cmp[0], b: cmp[1] });
    const color = h.get('color') as ColorMode | null;
    if (color === 'review' || color === 'confidence' || color === 'type') setColorMode(color);
  }, [deepLinkDone, view, hasProject, elementById, handleSelectElementNode, selectCalcByKey, showElementCalcs]);

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
  const showInspector = hasProject && (activeView === 'element-graph' || activeView === 'calculation-graph' || activeView === '3d');
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

  const modelUrl = online && view?.modelRevisionId != null ? urls.revisionFile(view.modelRevisionId) : null;
  const pdfUrl = online && view?.calcRevisionId != null ? urls.revisionFile(view.calcRevisionId) : null;
  const ghostSources = useMemo(
    () => (diffApplied?.ghosts ?? []).map((g) => ({ url: urls.revisionFile(g.revisionId), gids: g.elementIds })),
    [diffApplied],
  );
  const model3dEmpty = !view?.modelRevisionId
    ? 'No IFC model in this project yet.'
    : 'Model geometry is served by the backend; it is offline, so only the graphs and links are shown.';

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
          ? 'bg-amber-400 shadow-[0_0_10px_#f59e0b]'
          : selectedNodeId
          ? 'bg-amber-400 shadow-[0_0_10px_#f59e0b] animate-pulse'
          : 'bg-cyan-400 shadow-[0_0_8px_#22d3ee]'
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
            className="mono text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-400/25 hover:bg-indigo-500/25 transition mr-0.5"
          >
            FIT
          </button>
          <button
            type="button"
            onClick={() => setResetTrigger((c) => c + 1)}
            title="Reset 3D camera"
            className="text-zinc-500 hover:text-zinc-200 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-white/[0.06] transition"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </>
      }
    >
      <div className="relative flex-1 w-full h-full overflow-hidden bg-[#282c34]">
        {viewer3d}
        <div className="absolute bottom-2 left-2.5 right-4 pointer-events-none flex items-center justify-between text-[10px] mono text-zinc-400 bg-black/65 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/[0.07]">
          <span className="truncate text-zinc-200">{status3d}</span>
          <span className="text-zinc-500 ml-2 flex-shrink-0">Drag Orbit • RMB Pan</span>
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
      indicatorClassName={inspectorNode ? 'bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse' : 'bg-indigo-500 shadow-[0_0_8px_#6366f1] animate-pulse'}
      dockSide={inspectorDock}
      defaultPos={defaultInspPos}
      zIndex={topHudZ.insp}
      onFocus={() => setTopHudZ((z) => ({ v3d: z.v3d, insp: Math.max(z.v3d, z.insp) + 1 }))}
      onChangeDockSide={setInspectorDock}
      onDragHoverEdge={setHoverEdge}
      onCloseAction={handleClearSelection}
      closeTitle="Clear Selection"
    >
      <div className="p-4 pb-8 space-y-3 flex-1 overflow-y-auto text-xs">
        <PropertyInspector
          node={inspectorNode}
          elementNodes={elementNodes}
          calcs={view?.calcs ?? []}
          calcDependencies={view?.calcDependencies ?? []}
          loadPath={view?.loadPath ?? []}
          calcToElementIds={view?.calcToElementIds ?? new Map()}
          counts={view ? view.counts : null}
          groups={groups}
          selectedNodeIds={activeView === 'calculation-graph' ? EMPTY_SET : selectedNodeIds}
          activeLoadChainNodeIds={activeLoadChainNodeIds}
          diffMode={diffMode}
          impact={impact}
          impactLoading={Boolean(impactReq) && impactQ.isFetching}
          canWrite={online && view?.source === 'api'}
          busy={decide.isPending || Boolean(busyText)}
          onSelectNode={(id) => {
            if (activeView === 'calculation-graph') setActiveView('element-graph');
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

  const loading = backend === 'checking' || (online && !offlineView && (pidQ.isLoading || viewQ.isLoading));

  const emptyState = (
    <div className="absolute inset-0 flex items-center justify-center p-6 z-10">
      <div className="bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] rounded-2xl px-7 py-6 text-center max-w-md w-full shadow-[0_24px_60px_rgba(0,0,0,0.85)]">
        <div className="w-11 h-11 mx-auto rounded-xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/10 border border-indigo-400/30 text-indigo-300 flex items-center justify-center mb-3">
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Network className="w-5 h-5" />}
        </div>
        <p className="mono text-[10px] text-indigo-400 uppercase tracking-widest mb-1">{loading ? 'Connecting' : 'No project loaded yet'}</p>
        <h3 className="text-sm font-semibold text-white">Map a structural model onto its calculations</h3>
        <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
          Upload an IFC model and its calc package PDF; every element is linked to the calcs that design it, with the matched text as evidence.
        </p>
        <button
          type="button"
          disabled={!online || Boolean(busyText)}
          onClick={handleLoadSample}
          className="mt-4 w-full bg-indigo-500/25 hover:bg-indigo-500/35 text-white border border-indigo-400/50 rounded-xl py-2.5 text-sm font-semibold transition flex items-center justify-center gap-2 shadow-[0_0_24px_rgba(99,102,241,0.3)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {busyText ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-indigo-200" />}
          {busyText || 'Load sample'}
        </button>
        <div className="grid grid-cols-3 gap-1.5 mt-2">
          {[
            { icon: <Box className="w-3.5 h-3.5 text-cyan-300" />, label: 'IFC model', accept: '.ifc', on: (f: File) => handleUpload('model', f), needs: true },
            { icon: <FileText className="w-3.5 h-3.5 text-rose-300" />, label: 'Calc PDF', accept: '.pdf,application/pdf', on: (f: File) => handleUpload('calcs', f), needs: true },
            { icon: <FileJson className="w-3.5 h-3.5 text-amber-300" />, label: 'Export JSON', accept: '.json,application/json', on: handleOpenExport, needs: false },
          ].map((b) => (
            <label
              key={b.label}
              className={`bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 border border-white/[0.14] rounded-lg py-2 text-[11px] font-medium transition flex flex-col items-center gap-1 ${
                b.needs && !online ? 'opacity-40 pointer-events-none' : 'cursor-pointer'
              }`}
            >
              {b.icon}
              {b.label}
              <input
                type="file"
                accept={b.accept}
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) b.on(f);
                  e.target.value = '';
                }}
              />
            </label>
          ))}
        </div>
        {backend === 'offline' && (
          <p className="mt-3 text-[11px] text-amber-200/90 bg-amber-500/10 border border-amber-400/25 rounded-lg px-3 py-2 leading-snug text-left">
            The backend is not reachable at <code className="mono text-amber-100">/api</code>. Start it with{' '}
            <code className="mono text-amber-100">cd backend && uv run calc-graph serve</code>, or open a saved export JSON (read-only).
          </p>
        )}
      </div>
    </div>
  );

  const subtitle = view
    ? `${view.modelName ?? 'no model'} ⇄ ${view.calcPackageName ?? 'no calc package'}${view.engine ? ` · ${view.engine}` : ''}`
    : 'ELEMENT TOPOLOGY ↔ CALCULATION GRAPH ↔ 3D MODEL ↔ PDF CALCS';

  return (
    <div className="h-full bg-[#24272d] text-zinc-100 flex flex-col overflow-hidden select-none">
      <HeaderBar
        projectName={hasProject && view ? view.projectName : 'No Model Loaded'}
        subtitle={subtitle}
        activeView={activeView}
        onChangeView={setActiveView}
        calcCount={view?.calcs.length ?? 0}
        colorMode={colorMode}
        onChangeColorMode={setColorMode}
        hasUtilization={Boolean(view?.hasUtilization)}
        backend={backend}
        source={view?.source ?? null}
        busy={Boolean(busyText)}
        onLoadSample={handleLoadSample}
        onUploadModel={(f) => handleUpload('model', f)}
        onUploadCalcs={(f) => handleUpload('calcs', f)}
        onOpenExport={handleOpenExport}
        exportUrl={online && pid != null && hasProject && view?.source === 'api' ? urls.exportProject(pid) : null}
        diffSummary={diffSummary}
        compareOpen={compareOpen}
        onToggleCompare={() => setCompareOpen((v) => !v)}
        onSwapDatabases={handleSwapDatabases}
        onClearDiff={handleClearDiff}
        onResetAll={handleResetAll}
      />

      {compareOpen && (
        <RevisionPanel
          revisions={revisionsQ.data ?? null}
          loading={revisionsQ.isLoading}
          active={diffRevs}
          busy={Boolean(busyText)}
          fileUrl={urls.revisionFile}
          onCompare={handleCompare}
          onLoadSampleRev2={handleLoadSampleRev2}
          onUploadModel={(f) => {
            const before = baseView?.modelRevisionId ?? null;
            run(`Reading ${f.name}…`, async () => {
              const out = await upload.mutateAsync({ kind: 'model', file: f });
              setCompareOpen(false);
              if (before != null) setDiffRevs({ a: before, b: out.revisionId });
              return `${f.name} ingested as model revision #${out.revisionId}`;
            });
          }}
          onClose={() => setCompareOpen(false)}
        />
      )}

      <FilterBar
        filters={filters}
        onChangeFilters={setFilters}
        onClearFilters={() => {
          setFilters({ search: '', type: 'ALL', level: 'ALL' });
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
        diffSummary={diffSummary}
        diffFilter={diffFilter}
        onChangeDiffFilter={setDiffFilter}
        impactActive={Boolean(impact)}
        matchedCount={matchingNodeIds.size}
        totalInstances={totalInstances}
      />

      {hoverEdge === 'left' && (
        <div className="fixed top-24 bottom-2 left-2 w-32 z-45 pointer-events-none border-2 border-dashed border-indigo-400 bg-indigo-500/20 backdrop-blur-md rounded-2xl flex flex-col items-center justify-center gap-1.5 text-indigo-200">
          <Columns className="w-5 h-5" />
          <span className="mono text-[10px] font-semibold uppercase tracking-wider">Dock Left</span>
        </div>
      )}
      {hoverEdge === 'right' && (
        <div className="fixed top-24 bottom-2 right-2 w-32 z-45 pointer-events-none border-2 border-dashed border-indigo-400 bg-indigo-500/20 backdrop-blur-md rounded-2xl flex flex-col items-center justify-center gap-1.5 text-indigo-200">
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
            <div onPointerDown={startDockColumnResize('left')} className="w-1.5 cursor-ew-resize hover:bg-indigo-400/50 transition flex-shrink-0 z-25" />
          </>
        )}

        <div className="flex-1 relative h-full flex flex-col overflow-hidden min-w-0">
          {!hasProject && emptyState}

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
            <section className="w-full h-full relative flex flex-col overflow-hidden bg-[#282c34]">
              <div className="absolute top-4 left-4 z-10 flex items-center space-x-2 bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] px-3 py-1.5 rounded-xl shadow-[0_12px_32px_rgba(0,0,0,0.8)]">
                <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
                <span className="mono text-[11px] text-zinc-200 font-medium">{view?.modelName ?? 'Model'}</span>
                <span className="text-zinc-700">|</span>
                <span className="mono text-[10px] text-zinc-400">{status3d}</span>
                <span className="text-zinc-700">|</span>
                <button
                  type="button"
                  onClick={() => setFit3dTrigger((c) => c + 1)}
                  className="mono text-[10px] px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-400/25 hover:bg-indigo-500/25 transition flex items-center gap-1"
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
            <DocumentBrowser
              calcs={view.calcs}
              calcPackageName={view.calcPackageName}
              pdfUrl={pdfUrl}
              elementNodes={elementNodes}
              calcToElementIds={view.calcToElementIds}
              calcDependencies={view.calcDependencies}
              selectedElement={selectedNodeId ? elementById.get(selectedNodeId) ?? null : null}
              filterBySelectedElement={docFilterBySelected}
              onClearElementFilter={() => setDocFilterBySelected(false)}
              target={pdfTarget ?? (view.calcs.find((c) => !c.frontMatter) ? calcTarget(view.calcs.find((c) => !c.frontMatter)!) : null)}
              onChangeTarget={setPdfTarget}
              diffMode={diffMode}
              onLocateElement={(nodeId, v) => {
                handleSelectElementNode(nodeId);
                setActiveView(v);
              }}
              onLocateCalc={selectCalcByKey}
            />
          )}
        </div>

        {rightDockedHasItems && (
          <>
            <div onPointerDown={startDockColumnResize('right')} className="w-1.5 cursor-ew-resize hover:bg-indigo-400/50 transition flex-shrink-0 z-25" />
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
        className={`fixed bottom-5 left-5 bg-[#2d3139]/92 backdrop-blur-xl text-zinc-100 px-4 py-3 rounded-xl border border-white/[0.12] shadow-[0_12px_32px_rgba(0,0,0,0.9)] flex items-center space-x-3 transition-all duration-300 z-50 max-w-md ${
          busyText || toast.visible ? 'translate-y-0 opacity-100' : 'translate-y-24 opacity-0 pointer-events-none'
        }`}
        role="status"
      >
        {busyText ? (
          <Loader2 className="w-4 h-4 text-indigo-300 animate-spin flex-shrink-0" />
        ) : toast.isError ? (
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
        ) : (
          <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
        )}
        <div className="text-xs font-medium">{busyText || toast.message}</div>
      </div>
    </div>
  );
};

export default App;
