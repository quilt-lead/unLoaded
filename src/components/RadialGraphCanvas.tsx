import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Minus, Layers, Move, ZoomIn } from 'lucide-react';
import type { BimLink, BimNode, ColorMode, HighlightOverlay, LoadPathEdge, NodeGroup } from '../types/bim';
import {
  computeArcPath,
  computeCenterToCenterSplinePath,
  isElementTypeNode,
  isFamilyNode,
  isInstanceNode,
  isProjectNode,
  loadPathKey,
} from '../utils/graphEngine';
import { DIFF_PALETTE, TONE_COLORS, getContrastingTextStyle, getEffectiveNodeColor, linkStrokeStyle, STATUS_COLORS } from '../utils/colors';

interface RadialGraphCanvasProps {
  nodes: BimNode[];
  links: BimLink[];
  groups: NodeGroup[];
  selectedNodeId: string | null;
  selectedNodeIds: Set<string>;
  activeLoadChainNodeIds: Set<string>;
  /** directed load-path edges drawn while they are part of the traced chain */
  loadPath?: LoadPathEdge[];
  activeLoadChainLinkKeys?: Set<string>;
  matchingNodeIds: Set<string>;
  isFilterActive: boolean;
  colorMode: ColorMode;
  diffMode?: boolean;
  overlay?: HighlightOverlay | null;
  /** ring element nodes by mapping status (element graph) */
  showStatusRings?: boolean;
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
  loadPath = [],
  activeLoadChainLinkKeys,
  matchingNodeIds,
  isFilterActive,
  colorMode,
  diffMode = false,
  overlay = null,
  showStatusRings = false,
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

    if (overlay) {
      overlay.tones.forEach((_, id) => aNodes.add(id));
      nodes.forEach((n) => {
        if (aNodes.has(n.id) && n.parent) {
          aCats.add(n.parent);
          if (n.categoryParent) aCats.add(n.categoryParent);
        }
      });
      aCats.forEach((id) => aNodes.add(id));
      nodes.filter(isProjectNode).forEach((n) => aNodes.add(n.id));
    } else if (selectedNodeIds.size > 0) {
      selectedNodeIds.forEach((id) => aNodes.add(id));
      activeLoadChainNodeIds.forEach((id) => aNodes.add(id));
      links.forEach((l) => {
        if (selectedNodeIds.has(l.source) || selectedNodeIds.has(l.target)) {
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
  }, [overlay, selectedNodeIds, activeLoadChainNodeIds, links, isFilterActive, nodes, matchingNodeIds]);

  const hasSelection = selectedNodeIds.size > 0 || Boolean(overlay);

  const isNodeHighlighted = useCallback(
    (node: BimNode) => {
      if (hasSelection) return activeNodeSet.has(node.id);
      if (isFilterActive) {
        if (isProjectNode(node)) return true;
        if (isElementTypeNode(node)) return activeCategoryIds.has(node.id);
        if (isFamilyNode(node)) return activeStackIds.has(node.id);
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
            <span className="mono text-[10px] px-2.5 h-7 rounded-lg bg-indigo-500/20 text-indigo-200 border border-indigo-400/40 flex items-center gap-1.5">
              <Layers className="w-3 h-3 text-indigo-300" />
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

            <defs>
              <marker id="arrow-calc" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#a5b4fc" />
              </marker>
              <marker id="arrow-load" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#fbbf24" />
              </marker>
            </defs>

            {/* Group Hulls: click hull or name pill to select all members; double-click or the pencil to rename */}
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
                    members.forEach((m, i) => onSelectNode(m.id, { preserveMulti: i > 0 || e.shiftKey, skipZoomFit: true }));
                  }
                };

                const startRename = (e: React.MouseEvent | React.PointerEvent) => {
                  e.stopPropagation();
                  setEditingGroupId(grp.id);
                  setEditingGroupName(grp.name);
                };

                const commitRename = () => {
                  const trimmed = editingGroupName.trim();
                  if (trimmed && onRenameGroup) onRenameGroup(grp.id, trimmed);
                  setEditingGroupId(null);
                };

                return (
                  <g key={grp.id}>
                    <rect
                      x={x}
                      y={y}
                      width={w}
                      height={h}
                      rx={cornerR}
                      ry={cornerR}
                      onPointerDown={handleSelectWholeGroup}
                      className="cursor-pointer"
                      fill={isGroupSelected ? 'rgba(99, 102, 241, 0.11)' : 'rgba(255, 255, 255, 0.035)'}
                      stroke={isGroupSelected ? '#818cf8' : 'rgba(255, 255, 255, 0.55)'}
                      strokeWidth={isGroupSelected ? 2.0 : 1.4}
                      strokeDasharray="6 4"
                    />
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
                          className="w-full h-5 px-2 rounded bg-[#181b20] text-white mono text-[10px] font-semibold border border-indigo-400 focus:outline-none shadow-lg"
                        />
                      </foreignObject>
                    ) : (
                      <g onPointerDown={handleSelectWholeGroup} onDoubleClick={startRename} className="cursor-pointer">
                        <rect
                          x={badgeX}
                          y={badgeY}
                          width={badgeWidth}
                          height={badgeHeight}
                          rx={5}
                          ry={5}
                          fill={isGroupSelected ? '#4f46e5' : '#2d3139'}
                          stroke={isGroupSelected ? '#a5b4fc' : 'rgba(255, 255, 255, 0.35)'}
                          strokeWidth={1}
                        />
                        <text x={badgeX + 8} y={badgeY + 12.2} fill="#ffffff" fontFamily="'IBM Plex Mono', monospace" fontSize="9.5px" fontWeight={600}>
                          {badgeLabel}
                        </text>
                        <g transform={`translate(${badgeX + badgeWidth - 15}, ${badgeY + 3})`} onPointerDown={(e) => e.stopPropagation()} onClick={startRename}>
                          <title>Rename group</title>
                          <rect width={12} height={12} rx={3} fill="rgba(255,255,255,0.12)" />
                          <text x={6} y={9.2} textAnchor="middle" fill="#e0e7ff" fontSize="8px" fontFamily="'Apercu Pro', 'Apercu', sans-serif">
                            ✎
                          </text>
                        </g>
                      </g>
                    )}
                  </g>
                );
              })}
            </g>

            {/* Hierarchy wires (centre to centre, beneath nodes) */}
            <g>
              {links.map((link, idx) => {
                if (link.relation !== 'hierarchy') return null;
                const s = nodeById.get(link.source);
                const t = nodeById.get(link.target);
                if (!s || !t) return null;
                const isConn = isNodeHighlighted(s) && isNodeHighlighted(t);
                const dimmed = (hasSelection || isFilterActive) && !isConn;
                return (
                  <path
                    key={`h-${link.source}-${link.target}-${idx}`}
                    d={computeCenterToCenterSplinePath(s, t)}
                    fill="none"
                    strokeLinecap="round"
                    stroke={isConn && (hasSelection || isFilterActive) ? '#bef264' : 'rgba(255, 255, 255, 0.16)'}
                    strokeWidth={isConn && hasSelection ? 1.85 : 1.05}
                    style={{ opacity: dimmed ? 0.06 : 1, transition: 'stroke 0.18s ease, opacity 0.2s ease' }}
                  />
                );
              })}
            </g>

            {/* Traced load path: the element graph's directed supports edges, drawn only while traced */}
            {activeLoadChainLinkKeys && activeLoadChainLinkKeys.size > 0 && !overlay && (
              <g pointerEvents="none">
                {loadPath.map((e, idx) => {
                  if (!activeLoadChainLinkKeys.has(loadPathKey(e.source, e.target))) return null;
                  const s = nodeById.get(e.source);
                  const t = nodeById.get(e.target);
                  if (!s || !t) return null;
                  return (
                    <path
                      key={`lp-${idx}`}
                      d={computeArcPath(s, t, 0.12)}
                      fill="none"
                      stroke="#fbbf24"
                      strokeWidth={1.3}
                      strokeOpacity={0.85}
                      markerEnd="url(#arrow-load)"
                    >
                      <title>{e.rule}</title>
                    </path>
                  );
                })}
              </g>
            )}

            {/* Calc dependencies (output feeds input) and calc-mapping edges styled by review state */}
            <g>
              {links.map((link, idx) => {
                if (link.relation !== 'calc-dependency' && link.relation !== 'calc-mapping') return null;
                const s = nodeById.get(link.source);
                const t = nodeById.get(link.target);
                if (!s || !t) return null;
                const lit = isNodeHighlighted(s) && isNodeHighlighted(t);
                const dimmed = (hasSelection || isFilterActive) && !lit;
                if (link.relation === 'calc-dependency') {
                  return (
                    <path
                      key={`cd-${idx}`}
                      d={computeArcPath(s, t, 0.22)}
                      fill="none"
                      stroke="#a5b4fc"
                      strokeWidth={lit && hasSelection ? 1.8 : 1.2}
                      strokeDasharray="5 3"
                      markerEnd="url(#arrow-calc)"
                      style={{ opacity: dimmed ? 0.1 : 0.85, transition: 'opacity 0.2s ease' }}
                    />
                  );
                }
                const st = linkStrokeStyle(link.review, link.confidence);
                return (
                  <path
                    key={`cm-${idx}`}
                    d={`M ${s.x.toFixed(2)} ${s.y.toFixed(2)} L ${t.x.toFixed(2)} ${t.y.toFixed(2)}`}
                    fill="none"
                    stroke={st.stroke}
                    strokeWidth={st.width}
                    strokeDasharray={st.dash}
                    strokeLinecap="round"
                    style={{ opacity: dimmed ? 0.12 : 0.9 }}
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
                const isFamily = isFamilyNode(node);
                const tone = overlay?.tones.get(node.id);
                const fillHex = tone ? TONE_COLORS[tone] : getEffectiveNodeColor(node, colorMode, diffMode);
                const textStyle = getContrastingTextStyle(fillHex);
                const isRemovedDiff = diffMode && node.diffStatus === 'removed';
                const ringColor =
                  diffMode && node.diffStatus && node.diffStatus !== 'unchanged'
                    ? DIFF_PALETTE[node.diffStatus]
                    : showStatusRings && node.kind === 'element' && node.mappingStatus && node.mappingStatus !== 'confirmed'
                    ? STATUS_COLORS[node.mappingStatus]
                    : null;
                const labelOutside = node.kind === 'calc';

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x.toFixed(2)}, ${node.y.toFixed(2)})`}
                    onPointerDown={(e) => handleNodePointerDown(e, node)}
                    style={{
                      cursor: 'pointer',
                      opacity: dimmed ? 0.15 : isRemovedDiff ? 0.7 : 1,
                      transition: 'opacity 0.2s cubic-bezier(0.22, 1, 0.36, 1)',
                    }}
                  >
                    <title>{node.desc ? `${node.label} — ${node.desc}` : node.label}</title>
                    {isSelected && (
                      <circle r={node.r + 6} fill="none" stroke={isPrimary ? '#ffffff' : '#38bdf8'} strokeWidth={1.75} strokeDasharray="4 3" />
                    )}
                    {ringColor && !isSelected && <circle r={node.r + 2.6} fill="none" stroke={ringColor} strokeWidth={1.6} />}
                    {tone === 'origin' && <circle r={node.r + 7} fill="none" stroke="#818cf8" strokeWidth={2} />}
                    <circle
                      r={node.r}
                      fill={fillHex}
                      fillOpacity={isRemovedDiff ? 0.55 : 1}
                      stroke={
                        isSelected
                          ? '#ffffff'
                          : isProj
                          ? '#ffffff'
                          : isCategory
                          ? 'rgba(255,255,255,0.92)'
                          : 'rgba(255,255,255,0.72)'
                      }
                      strokeWidth={isSelected ? 2.6 : isProj ? 2.2 : isCategory ? 1.75 : node.r < 6 ? 0.8 : 1.25}
                      strokeDasharray={isRemovedDiff || node.isGhost ? '3 2' : undefined}
                    />
                    {labelOutside ? (
                      <text
                        textAnchor="middle"
                        y={node.r + 11}
                        fill="#e4e4e7"
                        fontFamily="'Apercu Pro', 'Apercu', sans-serif"
                        fontWeight={500}
                        fontSize="9px"
                        pointerEvents="none"
                        style={{ textShadow: '0 1px 2px rgba(0,0,0,0.9)' }}
                      >
                        {node.label}
                      </text>
                    ) : (
                      <text
                        textAnchor="middle"
                        dy="0.34em"
                        fill={textStyle.fill}
                        fontFamily="'Apercu Pro', 'Apercu', sans-serif"
                        fontWeight={isProj || isCategory || isFamily ? 600 : 500}
                        fontSize={getFittedFontSize(node.label, node.r)}
                        pointerEvents="none"
                        style={{ textShadow: textStyle.shadow }}
                      >
                        {node.label}
                      </text>
                    )}
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
          <Move className="w-3 h-3 text-indigo-400" />
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
