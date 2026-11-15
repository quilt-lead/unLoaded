import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Minus, Layers, Move, ZoomIn } from 'lucide-react';
import { BimLink, BimNode, NodeGroup } from '../types/bim';
import {
  computeCenterToCenterSplinePath,
  isColumnStackNode,
  isElementTypeNode,
  isInstanceNode,
  isProjectNode,
} from '../utils/graphEngine';
import { getContrastingTextStyle, getGraphNodeColor } from '../utils/colors';

interface RadialGraphCanvasProps {
  nodes: BimNode[];
  links: BimLink[];
  groups: NodeGroup[];
  selectedNodeId: string | null;
  selectedNodeIds: Set<string>;
  activeLoadChainNodeIds: Set<string>;
  matchingNodeIds: Set<string>;
  isFilterActive: boolean;
  heatmapMode: boolean;
  diffMode?: boolean;
  resetTrigger: number;
  onSelectNode: (id: string, opts?: { toggleMulti?: boolean; preserveMulti?: boolean; skipZoomFit?: boolean }) => void;
  onSelectGroup?: (groupId: string, opts?: { toggleMulti?: boolean }) => void;
  onRenameGroup?: (groupId: string, newName: string) => void;
  onClearSelection: () => void;
  onMoveNodes: (movedIds: Set<string>, dx: number, dy: number) => void;
  onGroupSelection: () => void;
}

function getFittedFontSize(label: string, radius: number): string {
  const innerDiameter = Math.max(radius * 1.72, 4);
  const estCharWidthFactor = 0.6;
  const fittedSize = Math.min(
    radius * 0.56,
    innerDiameter / Math.max(String(label || '').length * estCharWidthFactor, 1)
  );
  return `${Math.max(1.2, fittedSize).toFixed(2)}px`;
}

export const RadialGraphCanvas: React.FC<RadialGraphCanvasProps> = ({
  nodes,
  links,
  groups,
  selectedNodeId,
  selectedNodeIds,
  activeLoadChainNodeIds,
  matchingNodeIds,
  isFilterActive,
  heatmapMode,
  diffMode = false,
  resetTrigger,
  onSelectNode,
  onSelectGroup,
  onRenameGroup,
  onClearSelection,
  onMoveNodes,
  onGroupSelection,
}) => {
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [editingGroupName, setEditingGroupName] = useState<string>('');
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [camera, setCamera] = useState({ panX: 0, panY: 0, scale: 0.74 });
  const cameraRef = useRef(camera);
  cameraRef.current = camera;

  const interactionRef = useRef<{
    isPanning: boolean;
    panButton: number;
    panMoved: boolean;
    pointerStartX: number;
    pointerStartY: number;
    startX: number;
    startY: number;
    draggedNodeId: string | null;
    lastDragGraphX: number;
    lastDragGraphY: number;
  }>({
    isPanning: false,
    panButton: 0,
    panMoved: false,
    pointerStartX: 0,
    pointerStartY: 0,
    startX: 0,
    startY: 0,
    draggedNodeId: null,
    lastDragGraphX: 0,
    lastDragGraphY: 0,
  });

  const centerCanvas = useCallback(() => {
    const el = containerRef.current;
    const cx = (el?.clientWidth || window.innerWidth) / 2;
    const cy = (el?.clientHeight || window.innerHeight) / 2;
    const defaultScale = nodes.length > 60 ? 0.74 : 0.95;
    setCamera({ panX: cx, panY: cy, scale: defaultScale });
  }, [nodes.length]);

  useEffect(() => {
    centerCanvas();
  }, [centerCanvas, resetTrigger]);

  const zoomAtPoint = useCallback((newScale: number, focalX: number, focalY: number) => {
    const clamped = Math.max(1e-5, Number.isFinite(newScale) ? newScale : 1);
    setCamera((prev) => {
      const ratio = clamped / prev.scale;
      return {
        panX: focalX - (focalX - prev.panX) * ratio,
        panY: focalY - (focalY - prev.panY) * ratio,
        scale: clamped,
      };
    });
  }, []);

  // Keyboard zoom shortcuts (+, -, 0)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      if (target && (target.isContentEditable || target.closest('input, textarea, select'))) return;
      const el = containerRef.current;
      const cx = (el?.clientWidth || window.innerWidth) / 2;
      const cy = (el?.clientHeight || window.innerHeight) / 2;

      if (e.key === '=' || e.key === '+') {
        zoomAtPoint(cameraRef.current.scale * 1.25, cx, cy);
      } else if (e.key === '-' || e.key === '_') {
        zoomAtPoint(cameraRef.current.scale / 1.25, cx, cy);
      } else if (e.key === '0') {
        centerCanvas();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [centerCanvas, zoomAtPoint]);

  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const { activeNodeSet, activeCategoryIds, activeStackIds } = useMemo(() => {
    const aNodes = new Set<string>();
    const aCats = new Set<string>();
    const aStacks = new Set<string>();

    if (selectedNodeIds.size > 0) {
      selectedNodeIds.forEach((id) => aNodes.add(id));
      activeLoadChainNodeIds.forEach((id) => aNodes.add(id));
      links.forEach((l) => {
        if (!l.isLoadPath && (selectedNodeIds.has(l.source) || selectedNodeIds.has(l.target))) {
          aNodes.add(l.source);
          aNodes.add(l.target);
        }
      });
    } else if (isFilterActive) {
      nodes.forEach((inst) => {
        if (isInstanceNode(inst) && matchingNodeIds.has(inst.id)) {
          if (inst.parent) {
            aCats.add(inst.parent);
            aStacks.add(inst.parent);
          }
          if (inst.categoryParent) {
            aCats.add(inst.categoryParent);
          }
        }
      });
    }

    return { activeNodeSet: aNodes, activeCategoryIds: aCats, activeStackIds: aStacks };
  }, [selectedNodeIds, activeLoadChainNodeIds, links, isFilterActive, nodes, matchingNodeIds]);

  const hasSelection = selectedNodeIds.size > 0;

  const isNodeHighlighted = useCallback(
    (node: BimNode) => {
      if (hasSelection) return activeNodeSet.has(node.id);
      if (isFilterActive) {
        if (isProjectNode(node)) return true;
        if (isElementTypeNode(node)) return activeCategoryIds.has(node.id);
        if (isColumnStackNode(node)) return activeStackIds.has(node.id);
        return matchingNodeIds.has(node.id);
      }
      return true;
    },
    [hasSelection, activeNodeSet, isFilterActive, activeCategoryIds, activeStackIds, matchingNodeIds]
  );

  const handleCanvasPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    const ix = interactionRef.current;
    ix.pointerStartX = e.clientX;
    ix.pointerStartY = e.clientY;

    if (e.button === 1 || e.button === 2) {
      e.preventDefault();
      ix.isPanning = true;
      ix.panButton = e.button;
      ix.panMoved = false;
      ix.draggedNodeId = null;
      ix.startX = e.clientX - cameraRef.current.panX;
      ix.startY = e.clientY - cameraRef.current.panY;
      return;
    }

    const tag = (e.target as Element).tagName?.toLowerCase();
    const elId = (e.target as Element).id;
    if (e.button === 0 && !ix.draggedNodeId && (tag === 'svg' || elId === 'graphContainer' || elId === 'viewport')) {
      ix.isPanning = true;
      ix.panButton = 0;
      ix.panMoved = false;
      ix.startX = e.clientX - cameraRef.current.panX;
      ix.startY = e.clientY - cameraRef.current.panY;
    }
  };

  const handleCanvasPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const ix = interactionRef.current;
    if (ix.isPanning) {
      const nextPanX = e.clientX - ix.startX;
      const nextPanY = e.clientY - ix.startY;
      if (Math.hypot(e.clientX - ix.pointerStartX, e.clientY - ix.pointerStartY) > 2) {
        ix.panMoved = true;
      }
      setCamera((prev) => ({ ...prev, panX: nextPanX, panY: nextPanY }));
    } else if (ix.draggedNodeId && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const cam = cameraRef.current;
      const currX = (e.clientX - rect.left - cam.panX) / cam.scale;
      const currY = (e.clientY - rect.top - cam.panY) / cam.scale;
      const dx = currX - ix.lastDragGraphX;
      const dy = currY - ix.lastDragGraphY;
      ix.lastDragGraphX = currX;
      ix.lastDragGraphY = currY;

      const movedSet = new Set<string>([ix.draggedNodeId]);
      if (selectedNodeIds.has(ix.draggedNodeId)) {
        selectedNodeIds.forEach((sid) => movedSet.add(sid));
      }
      groups.forEach((grp) => {
        if (grp.nodeIds.some((nid) => movedSet.has(nid))) {
          grp.nodeIds.forEach((nid) => movedSet.add(nid));
        }
      });

      onMoveNodes(movedSet, dx, dy);
    }
  };

  const handleCanvasPointerUp = () => {
    const ix = interactionRef.current;
    const wasEmptyLeftClick = ix.isPanning && ix.panButton === 0 && !ix.panMoved && !ix.draggedNodeId;
    ix.isPanning = false;
    ix.draggedNodeId = null;
    if (wasEmptyLeftClick && selectedNodeId) {
      onClearSelection();
    }
  };

  const cancelInteraction = () => {
    interactionRef.current.isPanning = false;
    interactionRef.current.draggedNodeId = null;
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const cursorX = e.clientX - rect.left;
    const cursorY = e.clientY - rect.top;

    if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      const mult = e.deltaMode === 1 ? 16 : 1;
      const dx = (e.shiftKey && e.deltaX === 0 ? e.deltaY : e.deltaX) * mult;
      const dy = (e.shiftKey && e.deltaX === 0 ? 0 : e.deltaY) * mult;
      setCamera((prev) => ({ ...prev, panX: prev.panX - dx, panY: prev.panY - dy }));
    } else {
      const mult = e.deltaMode === 1 ? 16 : 1;
      const zoomFactor = Math.exp(-e.deltaY * mult * 0.0022);
      zoomAtPoint(cameraRef.current.scale * zoomFactor, cursorX, cursorY);
    }
  };

  const handleNodePointerDown = (e: React.PointerEvent, node: BimNode) => {
    if (e.button === 1 || e.button === 2) return;
    e.stopPropagation();
    if (!containerRef.current) return;
    e.currentTarget.setPointerCapture(e.pointerId);

    const rect = containerRef.current.getBoundingClientRect();
    const cam = cameraRef.current;
    const ix = interactionRef.current;
    ix.draggedNodeId = node.id;
    ix.lastDragGraphX = (e.clientX - rect.left - cam.panX) / cam.scale;
    ix.lastDragGraphY = (e.clientY - rect.top - cam.panY) / cam.scale;

    if (!e.shiftKey && selectedNodeIds.size > 1 && selectedNodeIds.has(node.id)) {
      onSelectNode(node.id, { preserveMulti: true, skipZoomFit: true });
    } else {
      onSelectNode(node.id, { toggleMulti: e.shiftKey });
    }
  };

  return (
    <section className="w-full h-full relative flex flex-col overflow-hidden">
      {/* Top-Left Zoom & Multi-Select Toolbar */}
      <div className="absolute top-4 left-4 z-10 flex items-center space-x-1 bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] p-1 rounded-xl shadow-[0_12px_32px_rgba(0,0,0,0.8)]">
        <button
          type="button"
          title="Zoom In (+)"
          aria-label="Zoom in"
          onClick={() => {
            const el = containerRef.current;
            zoomAtPoint(camera.scale * 1.25, (el?.clientWidth || 600) / 2, (el?.clientHeight || 400) / 2);
          }}
          className="w-7 h-7 rounded-lg bg-white/[0.04] hover:bg-white/[0.1] text-zinc-300 hover:text-white flex items-center justify-center transition"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
        <span className="mono px-2 text-[11px] font-medium text-zinc-400 min-w-[48px] text-center">
          {Math.round(camera.scale * 100)}%
        </span>
        <button
          type="button"
          title="Zoom Out (-)"
          aria-label="Zoom out"
          onClick={() => {
            const el = containerRef.current;
            zoomAtPoint(camera.scale / 1.25, (el?.clientWidth || 600) / 2, (el?.clientHeight || 400) / 2);
          }}
          className="w-7 h-7 rounded-lg bg-white/[0.04] hover:bg-white/[0.1] text-zinc-300 hover:text-white flex items-center justify-center transition"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>

        {selectedNodeIds.size > 1 && (
          <>
            <div className="h-4 w-px bg-white/[0.1] mx-0.5" />
            <span className="mono text-[10px] px-2.5 h-7 rounded-lg bg-calcmap/15 text-calcmap border border-calcmap/40 flex items-center gap-1.5">
              <Layers className="w-3 h-3 text-calcmap" />
              <span>{selectedNodeIds.size} Selected</span>
              <button
                type="button"
                onClick={onGroupSelection}
                title="Group & Cluster Selected Elements (Ctrl+G / Cmd+G)"
                className="ml-1 px-1.5 py-0.5 rounded bg-emerald-500/25 hover:bg-emerald-500/40 text-emerald-200 border border-emerald-400/40 font-semibold transition"
              >
                Group (Ctrl+G)
              </button>
            </span>
          </>
        )}
      </div>

      {/* Interactive SVG Radial Graph */}
      <div
        ref={containerRef}
        id="graphContainer"
        style={{ touchAction: 'none' }}
        onContextMenu={(e) => e.preventDefault()}
        onPointerDown={handleCanvasPointerDown}
        onPointerMove={handleCanvasPointerMove}
        onPointerUp={handleCanvasPointerUp}
        onPointerCancel={cancelInteraction}
        onLostPointerCapture={cancelInteraction}
        onWheel={handleWheel}
        onDoubleClick={(e) => {
          const tag = (e.target as Element).tagName?.toLowerCase();
          if (tag === 'svg' || (e.target as Element).id === 'graphContainer') {
            centerCanvas();
          } else if (containerRef.current) {
            const rect = containerRef.current.getBoundingClientRect();
            zoomAtPoint(camera.scale * 1.45, e.clientX - rect.left, e.clientY - rect.top);
          }
        }}
        className="w-full h-full cursor-grab active:cursor-grabbing relative overflow-hidden flex items-center justify-center"
      >
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
            <div className="bg-[#2d3139]/90 backdrop-blur-xl border border-white/[0.14] rounded-2xl px-6 py-5 text-center max-w-sm shadow-[0_20px_50px_rgba(0,0,0,0.85)]">
              <h3 className="text-sm font-semibold text-white">Import a structural model</h3>
              <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
                Choose <span className="text-zinc-200 font-medium">Import</span> in the top-right bar, or drop a model file anywhere on the window.
              </p>
            </div>
          </div>
        )}
        <svg id="graphSvg" className="w-full h-full">
          <g id="viewport" transform={`translate(${camera.panX}, ${camera.panY}) scale(${camera.scale})`}>
            {/* Subtle Polar Reference Rings */}
            <g pointerEvents="none">
              {[215, 370, 580].map((rVal, idx) => (
                <circle
                  key={rVal}
                  cx={0}
                  cy={0}
                  r={rVal}
                  fill="none"
                  stroke={idx === 0 ? 'rgba(255, 255, 255, 0.06)' : 'rgba(255, 255, 255, 0.03)'}
                  strokeWidth={1}
                  strokeDasharray={idx > 0 ? '3 6' : undefined}
                />
              ))}
            </g>

            {/* Group Hulls (Click hull or group name to select all members; double-click or click pencil to rename) */}
            <g>
              {groups.map((grp) => {
                const members = grp.nodeIds.map((id) => nodeById.get(id)).filter((n): n is BimNode => Boolean(n));
                if (members.length < 2) return null;
                let minX = Infinity,
                  minY = Infinity,
                  maxX = -Infinity,
                  maxY = -Infinity;
                members.forEach((m) => {
                  const r = m.r || 12;
                  if (m.x - r < minX) minX = m.x - r;
                  if (m.y - r < minY) minY = m.y - r;
                  if (m.x + r > maxX) maxX = m.x + r;
                  if (m.y + r > maxY) maxY = m.y + r;
                });
                const pad = 16;
                const x = minX - pad;
                const y = minY - pad;
                const w = maxX - minX + pad * 2;
                const h = maxY - minY + pad * 2;
                const cornerR = Math.min(22, Math.min(w, h) * 0.25);

                const isGroupSelected = members.every((m) => selectedNodeIds.has(m.id));
                const badgeLabel = `${grp.name} (${members.length})`;
                const badgeWidth = Math.max(76, badgeLabel.length * 6.2 + 24);
                const badgeHeight = 18;
                const badgeX = x + 6;
                const badgeY = y - badgeHeight - 4;

                const handleSelectWholeGroup = (e: React.PointerEvent) => {
                  if (e.button === 1 || e.button === 2) return;
                  e.stopPropagation();
                  if (containerRef.current) {
                    e.currentTarget.setPointerCapture(e.pointerId);
                    const rect = containerRef.current.getBoundingClientRect();
                    const ix = interactionRef.current;
                    ix.draggedNodeId = members[0].id;
                    ix.lastDragGraphX = (e.clientX - rect.left - camera.panX) / camera.scale;
                    ix.lastDragGraphY = (e.clientY - rect.top - camera.panY) / camera.scale;
                  }
                  if (onSelectGroup) {
                    onSelectGroup(grp.id, { toggleMulti: e.shiftKey });
                  } else {
                    members.forEach((m, i) =>
                      onSelectNode(m.id, { preserveMulti: i > 0 || e.shiftKey, skipZoomFit: true })
                    );
                  }
                };

                const startRename = (e: React.MouseEvent | React.PointerEvent) => {
                  e.stopPropagation();
                  setEditingGroupId(grp.id);
                  setEditingGroupName(grp.name);
                };

                const commitRename = () => {
                  const trimmed = editingGroupName.trim();
                  if (trimmed && onRenameGroup) {
                    onRenameGroup(grp.id, trimmed);
                  }
                  setEditingGroupId(null);
                };

                return (
                  <g key={grp.id}>
                    {/* Dashed Hull Boundary */}
                    <rect
                      x={x}
                      y={y}
                      width={w}
                      height={h}
                      rx={cornerR}
                      ry={cornerR}
                      onPointerDown={handleSelectWholeGroup}
                      className="cursor-pointer"
                      fill={isGroupSelected ? 'rgba(20, 174, 92, 0.11)' : 'rgba(255, 255, 255, 0.035)'}
                      stroke={isGroupSelected ? '#D2F2DF' : 'rgba(255, 255, 255, 0.55)'}
                      strokeWidth={isGroupSelected ? 2.0 : 1.4}
                      strokeDasharray="6 4"
                    />

                    {/* Clickable & Namable Group Header Pill */}
                    {editingGroupId === grp.id ? (
                      <foreignObject
                        x={badgeX}
                        y={badgeY - 2}
                        width={Math.max(150, badgeWidth + 40)}
                        height={24}
                        onPointerDown={(e) => e.stopPropagation()}
                      >
                        <input
                          type="text"
                          aria-label="Group name"
                          autoFocus
                          value={editingGroupName}
                          onChange={(e) => setEditingGroupName(e.target.value)}
                          onBlur={commitRename}
                          onKeyDown={(e) => {
                            e.stopPropagation();
                            if (e.key === 'Enter') commitRename();
                            if (e.key === 'Escape') setEditingGroupId(null);
                          }}
                          className="w-full h-5 px-2 rounded bg-[#181b20] text-white mono text-[10px] font-semibold border border-calcmap focus:outline-none shadow-lg"
                        />
                      </foreignObject>
                    ) : (
                      <g
                        onPointerDown={handleSelectWholeGroup}
                        onDoubleClick={startRename}
                        className="cursor-pointer"
                      >
                        <rect
                          x={badgeX}
                          y={badgeY}
                          width={badgeWidth}
                          height={badgeHeight}
                          rx={5}
                          ry={5}
                          fill={isGroupSelected ? '#14AE5C' : '#2d3139'}
                          stroke={isGroupSelected ? '#D2F2DF' : 'rgba(255, 255, 255, 0.35)'}
                          strokeWidth={1}
                        />
                        <text
                          x={badgeX + 8}
                          y={badgeY + 12.2}
                          fill="#ffffff"
                          fontFamily="'IBM Plex Mono', monospace"
                          fontSize="9.5px"
                          fontWeight={600}
                        >
                          {badgeLabel}
                        </text>
                        {/* Rename Edit Trigger */}
                        <g
                          transform={`translate(${badgeX + badgeWidth - 15}, ${badgeY + 3})`}
                          onPointerDown={(e) => e.stopPropagation()}
                          onClick={startRename}
                        >
                          <title>Rename Group</title>
                          <rect width={12} height={12} rx={3} fill="rgba(255,255,255,0.12)" />
                          <text
                            x={6}
                            y={9.2}
                            textAnchor="middle"
                            fill="#14AE5C"
                            fontSize="8px"
                            fontFamily="'Apercu Pro', 'Apercu', sans-serif"
                          >
                            ✎
                          </text>
                        </g>
                      </g>
                    )}
                  </g>
                );
              })}
            </g>

            {/* Center-to-Center Wires (Rendered beneath Nodes) */}
            <g>
              {links.map((link, idx) => {
                const s = nodeById.get(link.source);
                const t = nodeById.get(link.target);
                if (!s || !t) return null;
                const isConn = Boolean(link.isLoadPath) || (isNodeHighlighted(s) && isNodeHighlighted(t));
                const dimmed = (hasSelection || isFilterActive) && !isConn;

                return (
                  <path
                    key={`${link.source}-${link.target}-${idx}`}
                    d={computeCenterToCenterSplinePath(s, t)}
                    fill="none"
                    strokeLinecap="round"
                    stroke={isConn && (hasSelection || isFilterActive) ? '#FFFFFF' : 'rgba(255, 255, 255, 0.16)'}
                    strokeWidth={isConn && hasSelection ? 1.85 : 1.05}
                    style={{
                      opacity: dimmed ? 0.06 : 1,
                      transition: 'stroke 0.18s ease, opacity 0.2s ease',
                    }}
                  />
                );
              })}
            </g>

            {/* Nodes */}
            <g>
              {nodes.map((node) => {
                const isSelected = selectedNodeIds.has(node.id);
                const isPrimary = selectedNodeId === node.id;
                const isLit = isNodeHighlighted(node);
                const dimmed = (hasSelection || isFilterActive) && !isLit;
                const isProj = isProjectNode(node);
                const isCategory = isElementTypeNode(node);
                const isStack = isColumnStackNode(node);
                const fillHex = getGraphNodeColor(node, heatmapMode, diffMode);
                const textStyle = getContrastingTextStyle(fillHex);
                const displayLabel = isStack ? node.colNumber || node.label : node.label;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x.toFixed(2)}, ${node.y.toFixed(2)})`}
                    onPointerDown={(e) => handleNodePointerDown(e, node)}
                    style={{
                      cursor: 'pointer',
                      opacity: dimmed ? 0.15 : 1,
                      transition: 'opacity 0.2s cubic-bezier(0.22, 1, 0.36, 1)',
                    }}
                  >
                    {isSelected && (
                      <circle
                        r={node.r + 6}
                        fill="none"
                        stroke="#D2F2DF"
                        strokeWidth={1.75}
                      />
                    )}
                    <circle
                      r={node.r}
                      fill={fillHex}
                      fillOpacity={1}
                      stroke={
                        isSelected
                          ? '#14AE5C'
                          : isProj
                          ? '#ffffff'
                          : isCategory
                          ? 'rgba(255,255,255,0.92)'
                          : 'rgba(255,255,255,0.72)'
                      }
                      strokeWidth={isSelected ? 2.6 : isProj ? 2.2 : isCategory ? 1.75 : 1.25}
                      strokeDasharray={diffMode && node.diffStatus === 'removed' ? '3 2' : undefined}
                    />
                    <text
                      textAnchor="middle"
                      dy="0.34em"
                      fill={textStyle.fill}
                      fontFamily="'Apercu Pro', 'Apercu', sans-serif"
                      fontWeight={isProj || isCategory || isStack ? 600 : 500}
                      fontSize={getFittedFontSize(displayLabel, node.r)}
                      pointerEvents="none"
                      style={{ textShadow: textStyle.shadow }}
                    >
                      {displayLabel}
                    </text>
                  </g>
                );
              })}
            </g>
          </g>
        </svg>
      </div>

      {/* Canvas Hint Footer */}
      <div className="absolute bottom-4 left-4 pointer-events-none hidden sm:flex items-center space-x-3 text-[11px] text-zinc-400 bg-[#2d3139]/92 px-3.5 py-1.5 rounded-xl border border-white/[0.12] backdrop-blur-xl shadow-[0_8px_24px_rgba(0,0,0,0.8)]">
        <span className="flex items-center gap-1.5">
          <Move className="w-3 h-3 text-calcmap" />
          MMB / RMB Drag: Pan
        </span>
        <span className="text-zinc-700">|</span>
        <span className="flex items-center gap-1.5">
          <ZoomIn className="w-3 h-3 text-cyan-400" />
          Wheel: Zoom
        </span>
        <span className="text-zinc-700">|</span>
        <span className="flex items-center gap-1.5">
          <Layers className="w-3 h-3 text-emerald-400" />
          Shift + Click: Multi-select • Ctrl+G: Group
        </span>
      </div>
    </section>
  );
};
