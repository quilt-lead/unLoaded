import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Crosshair, RotateCcw, CheckCircle2, AlertTriangle, Columns } from 'lucide-react';
import {
  BimGraphData,
  BimLink,
  BimNode,
  DatabaseDiffSummary,
  DiffStatus,
  DockSide,
  FilterState,
  NodeGroup,
  TraceDirection,
  WorkspaceView,
} from './types/bim';
import {
  buildCalculationGraph,
  buildHierarchyLinks,
  computeDatabaseDiff,
  computeLoadPathTrace,
  getAllDocumentsFlattened,
  isElementTypeNode,
  isInstanceNode,
} from './utils/graphEngine';
import { BIM_PARSERS } from './utils/ifcParser';
import { HeaderBar } from './components/HeaderBar';
import { FilterBar } from './components/FilterBar';
import { RadialGraphCanvas } from './components/RadialGraphCanvas';
import { Structural3DViewer } from './components/Structural3DViewer';
import { PropertyInspector } from './components/PropertyInspector';
import { DocumentBrowser } from './components/DocumentBrowser';
import { DockableHudPanel } from './components/DockableHudPanel';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<WorkspaceView>('element-graph');
  const [heatmapMode, setHeatmapMode] = useState(false);
  const [traceDirection, setTraceDirection] = useState<TraceDirection>('down');
  const [traceSteps, setTraceSteps] = useState<number>(16);

  // Dual-Database State (Base DB A + Optional Compare DB B)
  const [baseSnapshot, setBaseSnapshot] = useState<{ graph: BimGraphData; rawLinks: BimLink[] } | null>(null);
  const [compareSnapshot, setCompareSnapshot] = useState<{ graph: BimGraphData; rawLinks: BimLink[] } | null>(null);
  const [diffFilter, setDiffFilter] = useState<'ALL' | 'CHANGED' | DiffStatus>('ALL');

  const [projectName, setProjectName] = useState<string>('No Model Loaded');
  const [elementNodes, setElementNodes] = useState<BimNode[]>([]);
  const [rawLinks, setRawLinks] = useState<BimGraphData['links']>([]);
  const [groups, setGroups] = useState<NodeGroup[]>([]);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());

  const [selectedCalcNodeId, setSelectedCalcNodeId] = useState<string | null>(null);
  const [selectedCalcNodeIds, setSelectedCalcNodeIds] = useState<Set<string>>(new Set());

  const [filters, setFilters] = useState<FilterState>({
    search: '',
    type: 'ALL',
    level: 'ALL',
  });

  const [docFilterBySelected, setDocFilterBySelected] = useState(false);
  const [initialDocId, setInitialDocId] = useState<string | null>(null);

  const [fit3dTrigger, setFit3dTrigger] = useState(0);
  const [resetTrigger, setResetTrigger] = useState(0);

  const [viewer3dDock, setViewer3dDock] = useState<DockSide>('float');
  const [inspectorDock, setInspectorDock] = useState<DockSide>('float');
  const [leftDockWidth, setLeftDockWidth] = useState(340);
  const [rightDockWidth, setRightDockWidth] = useState(340);
  const [topHudZ, setTopHudZ] = useState<{ v3d: number; insp: number }>({ v3d: 31, insp: 32 });
  const [hoverEdge, setHoverEdge] = useState<'left' | 'right' | null>(null);

  const [toast, setToast] = useState<{ message: string; isError: boolean; visible: boolean }>({
    message: '',
    isError: false,
    visible: false,
  });

  const showToast = useCallback((message: string, isError = false) => {
    setToast({ message, isError, visible: true });
    window.setTimeout(() => {
      setToast((prev) => ({ ...prev, visible: false }));
    }, 3400);
  }, []);

  // Recompute active merged graph whenever Base DB (A) or Compare DB (B) changes
  const diffSummary: DatabaseDiffSummary | null = useMemo(() => {
    if (!baseSnapshot || !compareSnapshot) return null;
    const diffRes = computeDatabaseDiff(
      baseSnapshot.graph,
      baseSnapshot.rawLinks,
      compareSnapshot.graph,
      compareSnapshot.rawLinks
    );
    return diffRes.summary;
  }, [baseSnapshot, compareSnapshot]);

  useEffect(() => {
    if (!baseSnapshot) return;
    if (!compareSnapshot) {
      setProjectName(baseSnapshot.graph.projectName || 'Loaded Model');
      setElementNodes(baseSnapshot.graph.nodes);
      setRawLinks(baseSnapshot.rawLinks);
      setDiffFilter('ALL');
      return;
    }

    const diffRes = computeDatabaseDiff(
      baseSnapshot.graph,
      baseSnapshot.rawLinks,
      compareSnapshot.graph,
      compareSnapshot.rawLinks
    );
    setProjectName(`${diffRes.summary.baseName} vs ${diffRes.summary.compareName}`);
    setElementNodes(diffRes.mergedNodes);
    setRawLinks(diffRes.mergedRawLinks);
  }, [baseSnapshot, compareSnapshot]);

  const handleUploadFile = useCallback(
    (file: File, slot: 'base' | 'compare') => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const cleanText = String(ev.target?.result || '')
            .replace(/^\uFEFF/, '')
            .trim();
          const parser = BIM_PARSERS.find((p) => p.canParse(cleanText, file.name));
          if (!parser) {
            showToast('Unsupported file type. Upload an .ifc STEP file or .json BIM graph.', true);
            return;
          }
          const { graph, rawLinks: parsedLinks } = parser.parse(cleanText, file.name);
          if (graph.nodes.length <= 1) {
            showToast('No physical structural elements found in file.', true);
            return;
          }

          setGroups([]);
          setSelectedNodeId(null);
          setSelectedNodeIds(new Set());
          setSelectedCalcNodeId(null);
          setSelectedCalcNodeIds(new Set());
          setResetTrigger((c) => c + 1);

          if (slot === 'compare') {
            if (!baseSnapshot) {
              // If user clicked Compare DB first before loading DB A, load into DB A and prompt for DB B
              setBaseSnapshot({ graph, rawLinks: parsedLinks });
              showToast(`Loaded DB A (${graph.projectName || file.name}). Click "Compare DB" again to pick DB B.`);
              return;
            }
            setCompareSnapshot({ graph, rawLinks: parsedLinks });
            const diffRes = computeDatabaseDiff(baseSnapshot.graph, baseSnapshot.rawLinks, graph, parsedLinks);
            const s = diffRes.summary;
            showToast(`Diff ready: +${s.addedCount} added, ~${s.modifiedCount} modified, -${s.removedCount} removed`);
          } else {
            setBaseSnapshot({ graph, rawLinks: parsedLinks });
            const catCount = graph.nodes.filter(isElementTypeNode).length;
            const instCount = graph.nodes.filter(isInstanceNode).length;
            showToast(`Loaded DB A via ${parser.name}: ${instCount} elements across ${catCount} types`);
          }
        } catch (err: any) {
          showToast(`Import Error: ${err?.message || 'Parse failure'}`, true);
        }
      };
      reader.onerror = () => showToast('Failed to read file from disk.', true);
      reader.readAsText(file);
    },
    [baseSnapshot, showToast]
  );

  const handleSwapDatabases = useCallback(() => {
    if (!baseSnapshot || !compareSnapshot) return;
    const prevBase = baseSnapshot;
    const prevCompare = compareSnapshot;
    setBaseSnapshot(prevCompare);
    setCompareSnapshot(prevBase);
    setSelectedNodeId(null);
    setSelectedNodeIds(new Set());
    setSelectedCalcNodeId(null);
    setSelectedCalcNodeIds(new Set());
    showToast(
      `Swapped models: A is now "${prevCompare.graph.projectName || 'DB B'}" ↔ B is now "${prevBase.graph.projectName || 'DB A'}"`
    );
  }, [baseSnapshot, compareSnapshot, showToast]);

  const handleClearDiff = useCallback(() => {
    setCompareSnapshot(null);
    setDiffFilter('ALL');
    setSelectedNodeId(null);
    setSelectedNodeIds(new Set());
    showToast('Exited Diff Mode — showing Base DB (A)');
  }, [showToast]);

  const hierarchyLinks = useMemo(() => buildHierarchyLinks(elementNodes, rawLinks), [elementNodes, rawLinks]);

  const { calcNodes, calcLinks, docToElementIds } = useMemo(
    () => buildCalculationGraph(elementNodes, projectName),
    [elementNodes, projectName]
  );

  const { chainNodeIds: activeLoadChainNodeIds } = useMemo(() => {
    const seeds = selectedNodeIds.size > 0 ? Array.from(selectedNodeIds) : selectedNodeId ? [selectedNodeId] : [];
    return computeLoadPathTrace(elementNodes, rawLinks, seeds, traceDirection, traceSteps);
  }, [elementNodes, rawLinks, selectedNodeId, selectedNodeIds, traceDirection, traceSteps]);

  const categories = useMemo(
    () => (activeView === 'calculation-graph' ? calcNodes : elementNodes).filter(isElementTypeNode),
    [activeView, calcNodes, elementNodes]
  );

  const floors = useMemo(() => {
    const floorMap = new Map<string, number>();
    elementNodes.filter(isInstanceNode).forEach((n) => {
      if (n.floor) floorMap.set(n.floor, typeof n.floorNum === 'number' ? n.floorNum : 0);
    });
    return Array.from(floorMap.entries())
      .sort((a, b) => a[1] - b[1])
      .map(([fl]) => fl);
  }, [elementNodes]);

  const isDiffFilterActive = Boolean(diffSummary && diffFilter !== 'ALL');
  const isFilterActive = Boolean(
    filters.search.trim() || filters.type !== 'ALL' || filters.level !== 'ALL' || isDiffFilterActive
  );

  const { matchingNodeIds, totalInstances } = useMemo(() => {
    const targetList = (activeView === 'calculation-graph' ? calcNodes : elementNodes).filter(isInstanceNode);
    const matched = new Set<string>();
    const q = filters.search.trim().toLowerCase();

    targetList.forEach((n) => {
      if (filters.type !== 'ALL' && n.parent !== filters.type && n.categoryParent !== filters.type) return;
      if (filters.level !== 'ALL' && n.floor && n.floor !== 'ALL' && n.floor !== filters.level) return;

      if (diffSummary && diffFilter !== 'ALL' && activeView !== 'calculation-graph') {
        const st = n.diffStatus || 'unchanged';
        if (diffFilter === 'CHANGED' && st === 'unchanged') return;
        if (diffFilter !== 'CHANGED' && st !== diffFilter) return;
      }

      if (q) {
        const hay = `${n.id} ${n.label} ${n.floor || ''} ${n.strengthLabel || ''} ${n.desc || ''}`.toLowerCase();
        if (!hay.includes(q)) return;
      }
      matched.add(n.id);
    });

    return { matchingNodeIds: matched, totalInstances: targetList.length };
  }, [activeView, calcNodes, elementNodes, filters, diffSummary, diffFilter]);

  const allDocs = useMemo(
    () =>
      getAllDocumentsFlattened(
        elementNodes,
        activeView !== 'calculation-graph' && isFilterActive ? matchingNodeIds : new Set(),
        heatmapMode
      ),
    [elementNodes, activeView, isFilterActive, matchingNodeIds, heatmapMode]
  );

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
    []
  );

  const handleSelectCalcNode = useCallback(
    (calcId: string) => {
      setSelectedCalcNodeId(calcId);
      setSelectedCalcNodeIds(new Set([calcId]));
      const mappedEls = docToElementIds.get(calcId) || [];
      if (mappedEls.length > 0) {
        setSelectedNodeIds(new Set(mappedEls));
        setSelectedNodeId(mappedEls[0]);
        setFit3dTrigger((c) => c + 1);
      }
    },
    [docToElementIds]
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
    [groups]
  );

  const handleRenameGroup = useCallback(
    (groupId: string, newName: string) => {
      const trimmed = newName.trim();
      if (!trimmed) return;
      setGroups((prev) => prev.map((g) => (g.id === groupId ? { ...g, name: trimmed } : g)));
      showToast(`Renamed group to "${trimmed}"`);
    },
    [showToast]
  );

  const handleClearSelection = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedNodeIds(new Set());
    setSelectedCalcNodeId(null);
    setSelectedCalcNodeIds(new Set());
  }, []);

  const handleMoveNodes = useCallback((movedIds: Set<string>, dx: number, dy: number) => {
    setElementNodes((prev) =>
      prev.map((n) => (movedIds.has(n.id) ? { ...n, x: n.x + dx, y: n.y + dy } : n))
    );
  }, []);

  const handleGroupSelection = useCallback(() => {
    const ids = Array.from(selectedNodeIds);
    if (ids.length < 2) {
      showToast('Shift + Click at least 2 elements before grouping (Ctrl+G).', true);
      return;
    }

    const idSet = new Set(ids);
    setElementNodes((prev) => {
      const selectedNodes = prev.filter((n) => idSet.has(n.id));
      if (selectedNodes.length < 2) return prev;

      let cx = 0;
      let cy = 0;
      selectedNodes.forEach((n) => {
        cx += n.x;
        cy += n.y;
      });
      cx /= selectedNodes.length;
      cy /= selectedNodes.length;

      const sorted = [...selectedNodes].sort(
        (a, b) => Math.atan2(a.y - cy, a.x - cx) - Math.atan2(b.y - cy, b.x - cx)
      );
      const maxR = Math.max(...sorted.map((n) => n.r || 12));
      const spacing = maxR * 2.35;
      const cols = Math.ceil(Math.sqrt(sorted.length));

      const updatedCoords = new Map<string, { x: number; y: number }>();
      sorted.forEach((n, idx) => {
        const r = Math.floor(idx / cols);
        const c = idx % cols;
        const colsInRow = Math.min(cols, sorted.length - r * cols);
        updatedCoords.set(n.id, {
          x: cx + (c - (colsInRow - 1) / 2) * spacing,
          y: cy + (r - (Math.ceil(sorted.length / cols) - 1) / 2) * spacing,
        });
      });

      return prev.map((n) => {
        const nextPt = updatedCoords.get(n.id);
        return nextPt ? { ...n, x: nextPt.x, y: nextPt.y } : n;
      });
    });

    setGroups((prev) => {
      const cleaned = prev
        .map((g) => ({ ...g, nodeIds: g.nodeIds.filter((nid) => !idSet.has(nid)) }))
        .filter((g) => g.nodeIds.length >= 2);
      return [
        ...cleaned,
        { id: `grp-${Date.now()}`, name: `GROUP ${cleaned.length + 1}`, nodeIds: ids },
      ];
    });

    showToast(`Grouped ${ids.length} elements (Ctrl+G)`);
  }, [selectedNodeIds, showToast]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        handleGroupSelection();
      } else if (e.key === 'Escape') {
        setDocFilterBySelected(false);
        handleClearSelection();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleGroupSelection, handleClearSelection]);

  const handleResetAll = useCallback(() => {
    setFilters({ search: '', type: 'ALL', level: 'ALL' });
    setDiffFilter('ALL');
    handleClearSelection();
    setViewer3dDock('float');
    setInspectorDock('float');
    setResetTrigger((c) => c + 1);
    showToast('View, filters & panels reset');
  }, [handleClearSelection, showToast]);

  const handleOpenDocument = useCallback(
    (nodeId: string, docId?: string, preserveSelection = false) => {
      if (!preserveSelection && nodeId && selectedNodeId !== nodeId) {
        handleSelectElementNode(nodeId, { skipZoomFit: true });
      }
      setDocFilterBySelected(true);
      setInitialDocId(docId || null);
      setActiveView('docs');
    },
    [selectedNodeId, handleSelectElementNode]
  );

  const defaultV3dPos = useMemo(
    () => ({
      left: Math.max(20, (typeof window !== 'undefined' ? window.innerWidth : 1280) - 340),
      top: 108,
      width: 320,
      height: 245,
    }),
    [resetTrigger]
  );

  const defaultInspPos = useMemo(
    () => ({
      left: Math.max(20, (typeof window !== 'undefined' ? window.innerWidth : 1280) - 340),
      top: Math.max(370, (typeof window !== 'undefined' ? window.innerHeight : 800) - 275),
      width: 320,
      height: 255,
    }),
    [resetTrigger]
  );

  const showViewer3d = activeView === 'element-graph' || activeView === 'calculation-graph';
  const showInspector = activeView === 'element-graph' || activeView === 'calculation-graph' || activeView === '3d';

  const leftDockedHasItems =
    (showViewer3d && viewer3dDock === 'left') || (showInspector && inspectorDock === 'left');
  const rightDockedHasItems =
    (showViewer3d && viewer3dDock === 'right') || (showInspector && inspectorDock === 'right');

  const startDockColumnResize = (side: 'left' | 'right') => (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = side === 'left' ? leftDockWidth : rightDockWidth;

    const onMove = (ev: PointerEvent) => {
      const dx = ev.clientX - startX;
      const raw = side === 'left' ? startW + dx : startW - dx;
      const clamped = Math.max(260, Math.min(540, raw));
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

  const diffMode = Boolean(diffSummary);

  const renderViewer3dPanel = () => (
    <DockableHudPanel
      id="viewer3dPanel"
      title={diffMode ? '3D Diff Model (A vs B)' : '3D Structural Model'}
      indicatorClassName={
        diffMode
          ? 'bg-amber-400 shadow-[0_0_10px_#f59e0b]'
          : selectedNodeId
          ? 'bg-amber-400 shadow-[0_0_10px_#f59e0b] animate-pulse'
          : heatmapMode
          ? 'bg-amber-400 shadow-[0_0_8px_#f59e0b]'
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
            title="Zoom Fit Selected Element"
            className="mono text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-400/25 hover:bg-indigo-500/25 transition mr-0.5"
          >
            FIT
          </button>
          <button
            type="button"
            onClick={() => setResetTrigger((c) => c + 1)}
            title="Reset 3D Camera"
            className="text-zinc-500 hover:text-zinc-200 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-white/[0.06] transition"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </>
      }
    >
      <div className="relative flex-1 w-full h-full overflow-hidden bg-[#282c34]">
        <Structural3DViewer
          nodes={elementNodes}
          selectedNodeId={selectedNodeId}
          selectedNodeIds={selectedNodeIds}
          activeLoadChainNodeIds={activeLoadChainNodeIds}
          matchingNodeIds={matchingNodeIds}
          isFilterActive={activeView !== 'calculation-graph' && isFilterActive}
          heatmapMode={heatmapMode}
          diffMode={diffMode}
          fitTrigger={fit3dTrigger}
          resetTrigger={resetTrigger}
          onSelectNode={handleSelectElementNode}
        />
        <div className="absolute bottom-2 left-2.5 right-4 pointer-events-none flex items-center justify-between text-[10px] mono text-zinc-400 bg-black/65 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/[0.07]">
          <span className="truncate text-zinc-200">
            {diffMode
              ? `+${diffSummary?.addedCount} Added • ~${diffSummary?.modifiedCount} Mod • -${diffSummary?.removedCount} Rem`
              : selectedNodeId
              ? 'Mapped Element & Load Path'
              : heatmapMode
              ? 'Utilization Heatmap'
              : '3D Structural Frame'}
          </span>
          <span className="text-zinc-500 ml-2 flex-shrink-0">RMB Orbit • MMB Pan</span>
        </div>
      </div>
    </DockableHudPanel>
  );

  const renderInspectorPanel = () => (
    <DockableHudPanel
      id="inspectorPanel"
      title={diffMode ? 'Diff & Element Inspector' : activeView === 'calculation-graph' ? 'Calculation Inspector' : 'Element Inspector'}
      indicatorClassName={
        selectedNodeId
          ? 'bg-emerald-400 shadow-[0_0_8px_#34d399] animate-pulse'
          : 'bg-indigo-500 shadow-[0_0_8px_#6366f1] animate-pulse'
      }
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
          nodes={elementNodes}
          links={hierarchyLinks}
          rawLinks={rawLinks}
          groups={groups}
          selectedNodeId={selectedNodeId}
          selectedNodeIds={selectedNodeIds}
          activeLoadChainNodeIds={activeLoadChainNodeIds}
          heatmapMode={heatmapMode}
          diffMode={diffMode}
          onSelectNode={(id) => handleSelectElementNode(id)}
          onSelectGroup={(gid) => handleSelectGroup(gid)}
          onRenameGroup={handleRenameGroup}
          onClearSelection={handleClearSelection}
          onOpenDocument={handleOpenDocument}
          onSwitchToCalcGraph={(calcId) => {
            if (calcId) {
              setSelectedCalcNodeId(calcId);
              setSelectedCalcNodeIds(new Set([calcId]));
            }
            setActiveView('calculation-graph');
          }}
        />
      </div>
      <div className="apple-panel-scroll-fade" />
    </DockableHudPanel>
  );

  return (
    <div className="h-full bg-[#24272d] text-zinc-100 flex flex-col overflow-hidden select-none">
      <HeaderBar
        projectName={projectName}
        activeView={activeView}
        onChangeView={setActiveView}
        calcCount={calcNodes.filter(isInstanceNode).length}
        docCount={allDocs.length}
        heatmapMode={heatmapMode}
        onToggleHeatmap={() => setHeatmapMode((v) => !v)}
        onUploadFile={handleUploadFile}
        diffSummary={diffSummary}
        onSwapDatabases={handleSwapDatabases}
        onClearDiff={handleClearDiff}
        onResetAll={handleResetAll}
      />

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
        heatmapMode={heatmapMode}
        diffSummary={diffSummary}
        diffFilter={diffFilter}
        onChangeDiffFilter={setDiffFilter}
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
            <div
              style={{ width: leftDockWidth }}
              className="bg-[#262a31]/95 backdrop-blur-2xl border-r border-white/[0.09] flex flex-col flex-shrink-0 overflow-hidden z-25"
            >
              {showViewer3d && viewer3dDock === 'left' && renderViewer3dPanel()}
              {showInspector && inspectorDock === 'left' && renderInspectorPanel()}
            </div>
            <div
              onPointerDown={startDockColumnResize('left')}
              className="w-1.5 cursor-ew-resize hover:bg-indigo-400/50 transition flex-shrink-0 z-25"
            />
          </>
        )}

        <div className="flex-1 relative h-full flex flex-col overflow-hidden min-w-0">
          {activeView === 'element-graph' && (
            <RadialGraphCanvas
              nodes={elementNodes}
              links={hierarchyLinks}
              groups={groups}
              selectedNodeId={selectedNodeId}
              selectedNodeIds={selectedNodeIds}
              activeLoadChainNodeIds={activeLoadChainNodeIds}
              matchingNodeIds={matchingNodeIds}
              isFilterActive={isFilterActive}
              heatmapMode={heatmapMode}
              diffMode={diffMode}
              resetTrigger={resetTrigger}
              onSelectNode={handleSelectElementNode}
              onSelectGroup={handleSelectGroup}
              onRenameGroup={handleRenameGroup}
              onClearSelection={handleClearSelection}
              onMoveNodes={handleMoveNodes}
              onGroupSelection={handleGroupSelection}
            />
          )}

          {activeView === 'calculation-graph' && (
            <RadialGraphCanvas
              nodes={calcNodes}
              links={calcLinks}
              groups={[]}
              selectedNodeId={selectedCalcNodeId}
              selectedNodeIds={selectedCalcNodeIds}
              activeLoadChainNodeIds={new Set()}
              matchingNodeIds={matchingNodeIds}
              isFilterActive={isFilterActive}
              heatmapMode={false}
              diffMode={false}
              resetTrigger={resetTrigger}
              onSelectNode={(id) => handleSelectCalcNode(id)}
              onClearSelection={handleClearSelection}
              onMoveNodes={() => {}}
              onGroupSelection={() => {}}
            />
          )}

          {activeView === '3d' && (
            <section className="w-full h-full relative flex flex-col overflow-hidden bg-[#282c34]">
              <div className="absolute top-4 left-4 z-10 flex items-center space-x-2 bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] px-3 py-1.5 rounded-xl shadow-[0_12px_32px_rgba(0,0,0,0.8)]">
                <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
                <span className="mono text-[11px] text-zinc-200 font-medium">{projectName} 3D Frame</span>
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
              <Structural3DViewer
                nodes={elementNodes}
                selectedNodeId={selectedNodeId}
                selectedNodeIds={selectedNodeIds}
                activeLoadChainNodeIds={activeLoadChainNodeIds}
                matchingNodeIds={matchingNodeIds}
                isFilterActive={isFilterActive}
                heatmapMode={heatmapMode}
                diffMode={diffMode}
                fitTrigger={fit3dTrigger}
                resetTrigger={resetTrigger}
                onSelectNode={handleSelectElementNode}
              />
            </section>
          )}

          {activeView === 'docs' && (
            <DocumentBrowser
              allDocs={allDocs}
              nodes={elementNodes}
              links={hierarchyLinks}
              selectedNodeId={selectedNodeId}
              activeLoadChainNodeIds={activeLoadChainNodeIds}
              filterBySelectedElement={docFilterBySelected}
              diffMode={diffMode}
              onClearElementFilter={() => setDocFilterBySelected(false)}
              initialDocId={initialDocId}
              onLocateElement={(nodeId, view) => {
                if (view === 'calculation-graph') {
                  handleSelectCalcNode(nodeId);
                } else {
                  handleSelectElementNode(nodeId);
                }
                setActiveView(view);
              }}
            />
          )}
        </div>

        {rightDockedHasItems && (
          <>
            <div
              onPointerDown={startDockColumnResize('right')}
              className="w-1.5 cursor-ew-resize hover:bg-indigo-400/50 transition flex-shrink-0 z-25"
            />
            <div
              style={{ width: rightDockWidth }}
              className="bg-[#262a31]/95 backdrop-blur-2xl border-l border-white/[0.09] flex flex-col flex-shrink-0 overflow-hidden z-25"
            >
              {showViewer3d && viewer3dDock === 'right' && renderViewer3dPanel()}
              {showInspector && inspectorDock === 'right' && renderInspectorPanel()}
            </div>
          </>
        )}
      </main>

      {showViewer3d && viewer3dDock === 'float' && renderViewer3dPanel()}
      {showInspector && inspectorDock === 'float' && renderInspectorPanel()}

      <div
        className={`fixed bottom-5 left-5 bg-[#2d3139]/92 backdrop-blur-xl text-zinc-100 px-4 py-3 rounded-xl border border-white/[0.12] shadow-[0_12px_32px_rgba(0,0,0,0.9)] flex items-center space-x-3 transition-all duration-300 z-50 ${
          toast.visible ? 'translate-y-0 opacity-100' : 'translate-y-24 opacity-0 pointer-events-none'
        }`}
      >
        {toast.isError ? (
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
        ) : (
          <CheckCircle2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
        )}
        <div className="text-xs font-medium">{toast.message}</div>
      </div>
    </div>
  );
};

export default App;
