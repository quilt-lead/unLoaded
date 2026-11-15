import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Minus, Layers, Move, ZoomIn, MessageSquarePlus } from 'lucide-react';
import type { BimLink, BimNode, ColorMode, GraphComment, HighlightOverlay, LoadPathEdge, NodeGroup } from '../types/bim';
import {
  computeArcPath,
  computeCenterToCenterSplinePath,
  isElementTypeNode,
  isFamilyNode,
  isInstanceNode,
  isProjectNode,
  getCalcBubbleLayout,
  loadPathKey,
} from '../utils/graphEngine';
import { selectNodesInBox, selectRectsInBox } from '../utils/graphSelection';
import { DIFF_PALETTE, TONE_COLORS, getContrastingTextStyle, getEffectiveNodeColor, linkStrokeStyle, STATUS_COLORS } from '../utils/colors';
import { useEscapeLayer } from './escapeStack';
import { COMMENT_MIN_HEIGHT, COMMENT_WIDTH, GraphCommentNote } from './GraphCommentNote';

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
  onSelectNodes: (ids: string[], opts?: { additive?: boolean }) => void;
  onSelectGroup?: (groupId: string, opts?: { toggleMulti?: boolean }) => void;
  onRenameGroup?: (groupId: string, newName: string) => void;
  onClearSelection: () => void;
  onMoveNodes: (movedIds: Set<string>, dx: number, dy: number) => void;
  onGroupSelection: () => void;
  /** Ctrl / Cmd + click: jump to the node's calculation (PDF) */
  onOpenNode?: (node: BimNode) => void;
  /** free text comments on this graph workspace; comments are off unless onAddComment is given */
  comments?: GraphComment[];
  selectedCommentIds?: Set<string>;
  /** additive adds to the comment selection; otherwise it replaces the comment selection */
  onSelectComments?: (ids: string[], opts?: { additive?: boolean }) => void;
  /** adds an empty comment with its top-left at (x, y) in graph coordinates and returns its id */
  onAddComment?: (x: number, y: number) => string;
  onMoveComments?: (ids: Set<string>, dx: number, dy: number) => void;
  onEditComment?: (id: string, text: string) => void;
  onDeleteComments?: (ids: string[]) => void;
}

const NO_COMMENTS: GraphComment[] = [];
const NO_IDS = new Set<string>();

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
  onSelectNodes,
  onSelectGroup,
  onRenameGroup,
  onClearSelection,
  onMoveNodes,
  onGroupSelection,
  onOpenNode,
  comments = NO_COMMENTS,
  selectedCommentIds = NO_IDS,
  onSelectComments,
  onAddComment,
  onMoveComments,
  onEditComment,
  onDeleteComments,
}) => {
  const commentsEnabled = Boolean(onAddComment);
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null);
  // the textarea's blur can fire after Escape already ended the edit; the ref lets commit ignore it
  const editingCommentRef = useRef<string | null>(null);
  editingCommentRef.current = editingCommentId;
  const commentHeights = useRef(new Map<string, number>());
  const handleMeasureComment = useCallback((id: string, h: number) => {
    commentHeights.current.set(id, h);
  }, []);
  /** last pointer position over the canvas in container pixels: where the C shortcut drops a comment */
  const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [editingGroupName, setEditingGroupName] = useState<string>('');
  const [selectionBox, setSelectionBox] = useState<{ x: number; y: number; width: number; height: number; crossing: boolean } | null>(null);
  const [selectionActive, setSelectionActive] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [camera, setCamera] = useState({ panX: 0, panY: 0, scale: 0.74 });
  const cameraRef = useRef(camera);
  cameraRef.current = camera;

  const interactionRef = useRef<{
    isPanning: boolean;
    isSelecting: boolean;
    selectionAdditive: boolean;
    selectionStartX: number;
    selectionStartY: number;
    panMoved: boolean;
    pointerStartX: number;
    pointerStartY: number;
    startX: number;
    startY: number;
    draggedNodeId: string | null;
    draggedCommentId: string | null;
    lastDragGraphX: number;
    lastDragGraphY: number;
  }>({
    isPanning: false,
    isSelecting: false,
    selectionAdditive: false,
    selectionStartX: 0,
    selectionStartY: 0,
    panMoved: false,
    pointerStartX: 0,
    pointerStartY: 0,
    startX: 0,
    startY: 0,
    draggedNodeId: null,
    draggedCommentId: null,
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

  const cancelInteraction = useCallback(() => {
    const ix = interactionRef.current;
    ix.isPanning = false;
    ix.isSelecting = false;
    ix.panMoved = false;
    ix.draggedNodeId = null;
    ix.draggedCommentId = null;
    setSelectionActive(false);
    setSelectionBox(null);
  }, []);

  const graphPointAt = useCallback((clientX: number, clientY: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    const cam = cameraRef.current;
    return { x: (clientX - (rect?.left ?? 0) - cam.panX) / cam.scale, y: (clientY - (rect?.top ?? 0) - cam.panY) / cam.scale };
  }, []);

  /** adds a comment centred on a container-pixel point (default: the view centre) and opens it for editing */
  const addCommentAt = useCallback(
    (px?: { x: number; y: number }) => {
      if (!onAddComment) return;
      const el = containerRef.current;
      const p = px ?? { x: (el?.clientWidth || 600) / 2, y: (el?.clientHeight || 400) / 2 };
      const cam = cameraRef.current;
      const gx = (p.x - cam.panX) / cam.scale - COMMENT_WIDTH / 2;
      const gy = (p.y - cam.panY) / cam.scale - COMMENT_MIN_HEIGHT / 2;
      const id = onAddComment(gx, gy);
      onSelectComments?.([id]);
      setEditingCommentId(id);
    },
    [onAddComment, onSelectComments],
  );

  const commitComment = useCallback(
    (id: string, text: string) => {
      if (editingCommentRef.current !== id) return;
      setEditingCommentId(null);
      const trimmed = text.trim();
      if (trimmed) onEditComment?.(id, trimmed);
      else onDeleteComments?.([id]);
    },
    [onEditComment, onDeleteComments],
  );

  const cancelCommentEdit = useCallback(
    (id: string) => {
      if (editingCommentRef.current !== id) return;
      setEditingCommentId(null);
      // a new comment cancelled before it had any text is discarded
      if (!comments.find((c) => c.id === id)?.text) onDeleteComments?.([id]);
    },
    [comments, onDeleteComments],
  );

  // C adds a comment under the pointer; Delete / Backspace removes the selected comments
  useEffect(() => {
    if (!commentsEnabled) return;
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      if (target && (target.isContentEditable || target.closest('input, textarea, select'))) return;
      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault();
        addCommentAt(lastPointerRef.current ?? undefined);
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && selectedCommentIds.size > 0) {
        const ids = comments.filter((c) => selectedCommentIds.has(c.id)).map((c) => c.id);
        if (ids.length === 0) return;
        e.preventDefault();
        onDeleteComments?.(ids);
      } else if (e.key.startsWith('Arrow') && selectedCommentIds.size > 0) {
        // keyboard alternative to dragging: arrows nudge the selected comments, Shift for bigger steps
        const step = e.shiftKey ? 40 : 8;
        const dx = e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0;
        const dy = e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0;
        if (!dx && !dy) return;
        e.preventDefault();
        onMoveComments?.(selectedCommentIds, dx, dy);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [commentsEnabled, addCommentAt, comments, selectedCommentIds, onDeleteComments, onMoveComments]);

  useEscapeLayer(selectionActive, () => {
    cancelInteraction();
    onClearSelection();
  });

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
  const isCalcGraph = nodes.some((n) => n.kind === 'calc-root');
  const calcBubbleLayouts = useMemo(
    () => new Map(
      nodes
        .filter((n) => n.kind === 'calc' || n.kind === 'calc-category' || n.kind === 'calc-root')
        .map((n) => [n.id, getCalcBubbleLayout(n.label)]),
    ),
    [nodes],
  );

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
      ix.isSelecting = false;
      ix.panMoved = false;
      ix.draggedNodeId = null;
      ix.startX = e.clientX - cameraRef.current.panX;
      ix.startY = e.clientY - cameraRef.current.panY;
      return;
    }

    const tag = (e.target as Element).tagName?.toLowerCase();
    const elId = (e.target as Element).id;
    if (e.button === 0 && !ix.draggedNodeId && (tag === 'svg' || elId === 'graphContainer' || elId === 'viewport')) {
      const rect = e.currentTarget.getBoundingClientRect();
      const cam = cameraRef.current;
      ix.isSelecting = true;
      ix.isPanning = false;
      ix.panMoved = false;
      ix.selectionAdditive = e.shiftKey;
      ix.selectionStartX = (e.clientX - rect.left - cam.panX) / cam.scale;
      ix.selectionStartY = (e.clientY - rect.top - cam.panY) / cam.scale;
      ix.draggedNodeId = null;
      setSelectionActive(true);
      setSelectionBox(null);
    }
  };

  const handleCanvasPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const ix = interactionRef.current;
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      lastPointerRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }
    if (ix.isSelecting && containerRef.current) {
      if (Math.hypot(e.clientX - ix.pointerStartX, e.clientY - ix.pointerStartY) > 2) {
        ix.panMoved = true;
        const rect = containerRef.current.getBoundingClientRect();
        const cam = cameraRef.current;
        const endX = (e.clientX - rect.left - cam.panX) / cam.scale;
        const endY = (e.clientY - rect.top - cam.panY) / cam.scale;
        setSelectionBox({
          x: Math.min(ix.selectionStartX, endX),
          y: Math.min(ix.selectionStartY, endY),
          width: Math.abs(endX - ix.selectionStartX),
          height: Math.abs(endY - ix.selectionStartY),
          crossing: endX < ix.selectionStartX,
        });
      }
    } else if (ix.isPanning) {
      const nextPanX = e.clientX - ix.startX;
      const nextPanY = e.clientY - ix.startY;
      if (Math.hypot(e.clientX - ix.pointerStartX, e.clientY - ix.pointerStartY) > 2) {
        ix.panMoved = true;
      }
      setCamera((prev) => ({ ...prev, panX: nextPanX, panY: nextPanY }));
    } else if ((ix.draggedNodeId || ix.draggedCommentId) && containerRef.current) {
      const { x: currX, y: currY } = graphPointAt(e.clientX, e.clientY);
      const dx = currX - ix.lastDragGraphX;
      const dy = currY - ix.lastDragGraphY;
      ix.lastDragGraphX = currX;
      ix.lastDragGraphY = currY;

      // dragging a selected item drags the whole selection, nodes and comments alike
      const movedSet = new Set<string>();
      const movedComments = new Set<string>();
      const draggedIsSelected = ix.draggedNodeId
        ? selectedNodeIds.has(ix.draggedNodeId)
        : selectedCommentIds.has(ix.draggedCommentId!);
      if (ix.draggedNodeId) movedSet.add(ix.draggedNodeId);
      if (ix.draggedCommentId) movedComments.add(ix.draggedCommentId);
      if (draggedIsSelected) {
        selectedNodeIds.forEach((sid) => movedSet.add(sid));
        selectedCommentIds.forEach((cid) => movedComments.add(cid));
      }
      groups.forEach((grp) => {
        if (grp.nodeIds.some((nid) => movedSet.has(nid))) {
          grp.nodeIds.forEach((nid) => movedSet.add(nid));
        }
      });

      if (movedSet.size > 0) onMoveNodes(movedSet, dx, dy);
      if (movedComments.size > 0) onMoveComments?.(movedComments, dx, dy);
    }
  };

  const handleCanvasPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    const ix = interactionRef.current;
    if (ix.isSelecting) {
      if (ix.panMoved && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const cam = cameraRef.current;
        const end = {
          x: (e.clientX - rect.left - cam.panX) / cam.scale,
          y: (e.clientY - rect.top - cam.panY) / cam.scale,
        };
        const start = { x: ix.selectionStartX, y: ix.selectionStartY };
        const ids = selectNodesInBox(nodes, start, end);
        onSelectNodes(ids, { additive: ix.selectionAdditive });
        if (commentsEnabled) {
          const rects = comments.map((c) => ({
            id: c.id,
            x: c.x,
            y: c.y,
            width: COMMENT_WIDTH,
            height: commentHeights.current.get(c.id) ?? COMMENT_MIN_HEIGHT,
          }));
          onSelectComments?.(selectRectsInBox(rects, start, end), { additive: ix.selectionAdditive });
        }
      } else if (!ix.selectionAdditive && (selectedNodeId || selectedCommentIds.size > 0)) {
        onClearSelection();
      }
      ix.isSelecting = false;
      ix.panMoved = false;
      setSelectionActive(false);
      setSelectionBox(null);
      return;
    }

    ix.isPanning = false;
    ix.draggedNodeId = null;
    ix.draggedCommentId = null;
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
    if ((e.ctrlKey || e.metaKey) && onOpenNode) {
      // a jump, not a selection or a drag
      e.preventDefault();
      onOpenNode(node);
      return;
    }
    e.currentTarget.setPointerCapture(e.pointerId);

    const rect = containerRef.current.getBoundingClientRect();
    const cam = cameraRef.current;
    const ix = interactionRef.current;
    ix.draggedNodeId = node.id;
    ix.lastDragGraphX = (e.clientX - rect.left - cam.panX) / cam.scale;
    ix.lastDragGraphY = (e.clientY - rect.top - cam.panY) / cam.scale;

    if (!e.shiftKey && selectedNodeIds.size + selectedCommentIds.size > 1 && selectedNodeIds.has(node.id)) {
      onSelectNode(node.id, { preserveMulti: true, skipZoomFit: true });
    } else {
      // a plain click on a node starts a new selection, so drop the selected comments
      if (!e.shiftKey && selectedCommentIds.size > 0) onSelectComments?.([]);
      onSelectNode(node.id, { toggleMulti: e.shiftKey });
    }
  };

  const handleCommentPointerDown = (e: React.PointerEvent, comment: GraphComment) => {
    if (e.button === 1 || e.button === 2) return;
    e.stopPropagation();
    if (!containerRef.current) return;
    e.currentTarget.setPointerCapture(e.pointerId);

    const ix = interactionRef.current;
    const p = graphPointAt(e.clientX, e.clientY);
    ix.draggedCommentId = comment.id;
    ix.draggedNodeId = null;
    ix.lastDragGraphX = p.x;
    ix.lastDragGraphY = p.y;

    const isSelected = selectedCommentIds.has(comment.id);
    if (e.shiftKey) {
      // Shift toggles this comment and keeps everything else selected
      const next = comments.filter((c) => selectedCommentIds.has(c.id) && c.id !== comment.id).map((c) => c.id);
      onSelectComments?.(isSelected ? next : [...next, comment.id]);
    } else if (isSelected && selectedNodeIds.size + selectedCommentIds.size > 1) {
      // pressing on part of a multi-selection keeps it, so the whole selection drags together
    } else {
      onClearSelection();
      onSelectComments?.([comment.id]);
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

        {commentsEnabled && (
          <>
            <div className="h-4 w-px bg-white/[0.1] mx-0.5" />
            <button
              type="button"
              title="Add comment (C)"
              aria-label="Add comment"
              onClick={() => addCommentAt()}
              className="h-7 px-2 rounded-lg bg-white/[0.04] hover:bg-amber-300/15 text-zinc-300 hover:text-amber-100 flex items-center gap-1.5 text-[11px] font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300/70"
            >
              <MessageSquarePlus className="w-3.5 h-3.5" aria-hidden="true" />
              Comment
            </button>
          </>
        )}

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
                  if (!e.shiftKey && selectedCommentIds.size > 0) onSelectComments?.([]);
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
                      fill={isGroupSelected ? 'rgba(20, 174, 92, 0.11)' : 'rgba(255, 255, 255, 0.035)'}
                      stroke={isGroupSelected ? '#D2F2DF' : 'rgba(255, 255, 255, 0.55)'}
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
                          className="w-full h-5 px-2 rounded bg-[#181b20] text-white mono text-[10px] font-semibold border border-calcmap focus:outline-none shadow-lg"
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
                          fill={isGroupSelected ? '#14AE5C' : '#2d3139'}
                          stroke={isGroupSelected ? '#D2F2DF' : 'rgba(255, 255, 255, 0.35)'}
                          strokeWidth={1}
                        />
                        <text x={badgeX + 8} y={badgeY + 12.2} fill="#ffffff" fontFamily="'IBM Plex Mono', monospace" fontSize="9.5px" fontWeight={600}>
                          {badgeLabel}
                        </text>
                        <g transform={`translate(${badgeX + badgeWidth - 15}, ${badgeY + 3})`} onPointerDown={(e) => e.stopPropagation()} onClick={startRename}>
                          <title>Rename group</title>
                          <rect width={12} height={12} rx={3} fill="rgba(255,255,255,0.12)" />
                          <text x={6} y={9.2} textAnchor="middle" fill="#14AE5C" fontSize="8px" fontFamily="'Apercu Pro', 'Apercu', sans-serif">
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
            <g pointerEvents="none">
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
                    stroke={isConn && (hasSelection || isFilterActive) ? '#FFFFFF' : 'rgba(255, 255, 255, 0.16)'}
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
            <g pointerEvents="none">
              {links.map((link, idx) => {
                if (link.relation !== 'calc-dependency' && link.relation !== 'calc-mapping') return null;
                const s = nodeById.get(link.source);
                const t = nodeById.get(link.target);
                if (!s || !t) return null;
                const lit = isNodeHighlighted(s) && isNodeHighlighted(t);
                const dimmed = (hasSelection || isFilterActive) && !lit;
                if (link.relation === 'calc-dependency') {
                  // dependency wires are only drawn for the selected calc(s); always-on they bury the graph
                  if (!selectedNodeIds.has(link.source) && !selectedNodeIds.has(link.target)) return null;
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
                const labelFill = '#ffffff';
                const isRemovedDiff = diffMode && node.diffStatus === 'removed';
                const ringColor =
                  diffMode && node.diffStatus && node.diffStatus !== 'unchanged'
                    ? DIFF_PALETTE[node.diffStatus]
                    : showStatusRings && node.kind === 'element' && node.mappingStatus && node.mappingStatus !== 'confirmed'
                    ? STATUS_COLORS[node.mappingStatus]
                    : null;
                const calcBubble = calcBubbleLayouts.get(node.id);

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
                    {calcBubble ? (
                      <text
                        x="0"
                        y={-((calcBubble.lines.length - 1) * calcBubble.lineHeight) / 2 + calcBubble.fontSize / 2}
                        textAnchor="middle"
                        fill={labelFill}
                        fontFamily="'Apercu Pro', 'Apercu', sans-serif"
                        fontWeight={600}
                        fontSize={`${calcBubble.fontSize}px`}
                        pointerEvents="none"
                        style={{ textShadow: textStyle.shadow }}
                      >
                        {calcBubble.lines.map((line, index) => (
                          <tspan key={`${node.id}-${index}`} x="0" dy={index === 0 ? 0 : calcBubble.lineHeight}>
                            {line}
                          </tspan>
                        ))}
                      </text>
                    ) : (
                      <text
                        textAnchor="middle"
                        dy="0.34em"
                        fill={labelFill}
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

            {/* Comments: above nodes, never dimmed by selection or filters */}
            {commentsEnabled && comments.length > 0 && (
              <g>
                {comments.map((c) => (
                  <GraphCommentNote
                    key={c.id}
                    comment={c}
                    selected={selectedCommentIds.has(c.id)}
                    primary={selectedCommentIds.size + selectedNodeIds.size === 1 && selectedCommentIds.has(c.id)}
                    editing={editingCommentId === c.id}
                    onPointerDown={handleCommentPointerDown}
                    onStartEdit={setEditingCommentId}
                    onCommit={commitComment}
                    onCancelEdit={cancelCommentEdit}
                    onMeasure={handleMeasureComment}
                  />
                ))}
              </g>
            )}

            {selectionBox && (
              <rect
                aria-hidden="true"
                x={selectionBox.x}
                y={selectionBox.y}
                width={selectionBox.width}
                height={selectionBox.height}
                fill="#14AE5C"
                fillOpacity={0.12}
                stroke={selectionBox.crossing ? '#D2F2DF' : '#14AE5C'}
                strokeWidth={1.4 / camera.scale}
                strokeDasharray={selectionBox.crossing ? `${5 / camera.scale} ${3 / camera.scale}` : undefined}
                pointerEvents="none"
              />
            )}
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
          Drag L→R: contain • R→L: cross • Shift: add
        </span>
        {onOpenNode && (
          <>
            <span className="text-zinc-700">|</span>
            <span>Ctrl+Click: open calc • Alt+←/→: back/forward</span>
          </>
        )}
        {commentsEnabled && (
          <>
            <span className="text-zinc-700">|</span>
            <span className="flex items-center gap-1.5">
              <MessageSquarePlus className="w-3 h-3 text-amber-300" />
              C: Comment • Del: remove
            </span>
          </>
        )}
      </div>
    </section>
  );
};
