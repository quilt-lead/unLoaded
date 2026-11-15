import React, { useEffect, useRef, useState } from 'react';
import { GripVertical, ArrowLeftToLine, ArrowRightToLine, ExternalLink, X } from 'lucide-react';
import { DockSide } from '../types/bim';

type PanelRect = { left: number; top: number; width: number; height: number };

export function clampPanelRect(
  rect: PanelRect,
  viewport: { width: number; height: number },
  minWidth = 260,
  minHeight = 185,
): PanelRect {
  const margin = 8;
  const minTop = Math.min(96, Math.max(margin, viewport.height - minHeight - margin));
  const width = Math.min(Math.max(minWidth, rect.width), Math.max(1, viewport.width - margin * 2));
  const height = Math.min(Math.max(minHeight, rect.height), Math.max(1, viewport.height - minTop - margin));
  return {
    width,
    height,
    left: Math.max(margin, Math.min(rect.left, viewport.width - width - margin)),
    top: Math.max(minTop, Math.min(rect.top, viewport.height - height - margin)),
  };
}

interface DockableHudPanelProps {
  id: string;
  title: string;
  indicatorClassName: string;
  dockSide: DockSide;
  defaultPos: { left: number; top: number; width: number; height: number };
  minWidth?: number;
  minHeight?: number;
  zIndex: number;
  onFocus: () => void;
  onChangeDockSide: (side: DockSide) => void;
  onDragHoverEdge?: (edge: 'left' | 'right' | null) => void;
  headerActions?: React.ReactNode;
  onCloseAction?: () => void;
  closeTitle?: string;
  children: React.ReactNode;
}

export const DockableHudPanel: React.FC<DockableHudPanelProps> = ({
  id,
  title,
  indicatorClassName,
  dockSide,
  defaultPos,
  minWidth = 260,
  minHeight = 185,
  zIndex,
  onFocus,
  onChangeDockSide,
  onDragHoverEdge,
  headerActions,
  onCloseAction,
  closeTitle,
  children,
}) => {
  const fitToViewport = (value: PanelRect) => typeof window === 'undefined'
    ? value
    : clampPanelRect(value, { width: window.innerWidth, height: window.innerHeight }, minWidth, minHeight);
  const [rect, setRect] = useState(() => fitToViewport(defaultPos));
  const [isDragging, setIsDragging] = useState(false);
  const interactionCleanup = useRef<(() => void) | null>(null);

  useEffect(() => {
    setRect(fitToViewport(defaultPos));
  }, [defaultPos, minWidth, minHeight]);

  useEffect(() => {
    const onResize = () => setRect((current) => fitToViewport(current));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [minWidth, minHeight]);

  useEffect(() => () => interactionCleanup.current?.(), []);

  const dragMeta = useRef<{
    offsetX: number;
    offsetY: number;
    startX: number;
    startY: number;
    detached: boolean;
    pendingDock: 'left' | 'right' | null;
  }>({
    offsetX: 0,
    offsetY: 0,
    startX: 0,
    startY: 0,
    detached: false,
    pendingDock: null,
  });

  const startDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement;
    if (target.closest('button') || target.closest('input') || target.closest('label')) return;
    interactionCleanup.current?.();
    e.preventDefault();
    e.stopPropagation();
    onFocus();
    const pointerTarget = e.currentTarget;
    pointerTarget.setPointerCapture(e.pointerId);

    const el = e.currentTarget.parentElement;
    const box = el ? el.getBoundingClientRect() : rect;
    dragMeta.current = {
      offsetX: e.clientX - box.left,
      offsetY: e.clientY - box.top,
      startX: e.clientX,
      startY: e.clientY,
      detached: dockSide === 'float',
      pendingDock: null,
    };
    setIsDragging(true);

    const snapThreshold = 42;

    const onMove = (ev: PointerEvent) => {
      if (ev.pointerId !== e.pointerId) return;
      if (!dragMeta.current.detached) {
        if (Math.hypot(ev.clientX - dragMeta.current.startX, ev.clientY - dragMeta.current.startY) < 14) return;
        dragMeta.current.detached = true;
        dragMeta.current.offsetX = Math.min(280, Math.max(24, dragMeta.current.offsetX));
        dragMeta.current.offsetY = 16;
        // Changing dock side remounts this panel. Finish the gesture first.
      }

      setRect((prev) => fitToViewport({
        ...prev,
        left: ev.clientX - dragMeta.current.offsetX,
        top: ev.clientY - dragMeta.current.offsetY,
      }));

      if (ev.clientX <= snapThreshold) {
        dragMeta.current.pendingDock = 'left';
        onDragHoverEdge?.('left');
      } else if (ev.clientX >= window.innerWidth - snapThreshold) {
        dragMeta.current.pendingDock = 'right';
        onDragHoverEdge?.('right');
      } else {
        dragMeta.current.pendingDock = null;
        onDragHoverEdge?.(null);
      }
    };

    const cleanup = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onCancel);
      window.removeEventListener('blur', cancel);
      pointerTarget.removeEventListener('lostpointercapture', onCancel);
      if (pointerTarget.hasPointerCapture(e.pointerId)) pointerTarget.releasePointerCapture(e.pointerId);
      interactionCleanup.current = null;
      onDragHoverEdge?.(null);
    };
    const cancel = () => {
      cleanup();
      setIsDragging(false);
    };
    const onCancel = (ev: PointerEvent) => {
      if (ev.pointerId === e.pointerId) cancel();
    };
    const onUp = (ev: PointerEvent) => {
      if (ev.pointerId !== e.pointerId) return;
      cancel();
      if (dragMeta.current.pendingDock) {
        onChangeDockSide(dragMeta.current.pendingDock);
      } else if (dragMeta.current.detached && dockSide !== 'float') {
        onChangeDockSide('float');
      }
    };

    interactionCleanup.current = cleanup;
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onCancel);
    window.addEventListener('blur', cancel);
    pointerTarget.addEventListener('lostpointercapture', onCancel);
  };

  const startResize = (dir: string) => (e: React.PointerEvent<HTMLDivElement>) => {
    if (dockSide !== 'float' || e.button !== 0) return;
    interactionCleanup.current?.();
    e.preventDefault();
    e.stopPropagation();
    onFocus();
    const pointerTarget = e.currentTarget;
    pointerTarget.setPointerCapture(e.pointerId);

    const startRect = { ...rect };
    const startX = e.clientX;
    const startY = e.clientY;
    const headerHeight = 96;
    const margin = 8;

    const onMove = (ev: PointerEvent) => {
      if (ev.pointerId !== e.pointerId) return;
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;
      let { left, top, width, height } = startRect;

      if (dir.includes('e')) {
        width = Math.max(minWidth, Math.min(window.innerWidth - startRect.left - margin, startRect.width + dx));
      }
      if (dir.includes('s')) {
        height = Math.max(minHeight, Math.min(window.innerHeight - startRect.top - margin, startRect.height + dy));
      }
      if (dir.includes('w')) {
        const clampedDx = Math.max(-(startRect.left - margin), Math.min(startRect.width - minWidth, dx));
        left = startRect.left + clampedDx;
        width = startRect.width - clampedDx;
      }
      if (dir.includes('n')) {
        const clampedDy = Math.max(-(startRect.top - headerHeight), Math.min(startRect.height - minHeight, dy));
        top = startRect.top + clampedDy;
        height = startRect.height - clampedDy;
      }
      setRect(fitToViewport({ left, top, width, height }));
    };

    const cleanup = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      window.removeEventListener('blur', cleanup);
      pointerTarget.removeEventListener('lostpointercapture', onUp);
      if (pointerTarget.hasPointerCapture(e.pointerId)) pointerTarget.releasePointerCapture(e.pointerId);
      interactionCleanup.current = null;
    };
    const onUp = (ev: PointerEvent) => {
      if (ev.pointerId === e.pointerId) cleanup();
    };

    interactionCleanup.current = cleanup;
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    window.addEventListener('blur', cleanup);
    pointerTarget.addEventListener('lostpointercapture', onUp);
  };

  const isDocked = dockSide !== 'float';

  return (
    <aside
      id={id}
      aria-labelledby={`${id}-title`}
      onPointerDown={() => {
        if (!isDocked) onFocus();
      }}
      style={
        isDocked
          ? { flex: '1 1 0%', minHeight: 150 }
          : {
              left: rect.left,
              top: rect.top,
              width: rect.width,
              height: rect.height,
              zIndex,
            }
      }
      className={
        isDocked
          ? 'relative w-full bg-[#2d3139]/92 flex flex-col overflow-hidden border-b border-white/[0.08] last:border-b-0'
          : `fixed bg-[#2d3139]/92 backdrop-blur-2xl border border-white/[0.16] rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.9)] flex flex-col overflow-hidden ${
              isDragging ? 'ring-1 ring-indigo-400/50' : ''
            }`
      }
    >
      {/* Title Bar */}
      <div
        style={{ touchAction: 'none' }}
        onPointerDown={startDrag}
        onDoubleClick={(e) => {
          if ((e.target as HTMLElement).closest('button')) return;
          onChangeDockSide(dockSide === 'float' ? 'right' : 'float');
        }}
        className="cursor-grab active:cursor-grabbing px-3.5 py-2.5 border-b border-white/[0.07] flex items-center justify-between bg-white/[0.02] flex-shrink-0"
      >
        <div className="flex items-center space-x-2 pointer-events-none min-w-0">
          <GripVertical className="w-3 h-3 text-zinc-600 flex-shrink-0" />
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${indicatorClassName}`} />
          <h2 id={`${id}-title`} className="mono font-semibold text-[10px] text-zinc-200 uppercase tracking-widest truncate">
            {title}
          </h2>
        </div>

        <div className="flex items-center space-x-0.5 flex-shrink-0">
          {headerActions}
          {dockSide !== 'left' && (
            <button
              type="button"
              onClick={() => onChangeDockSide('left')}
              title="Dock Left"
              aria-label={`Dock ${title} left`}
              className="text-zinc-500 hover:text-indigo-300 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-white/[0.06] transition"
            >
              <ArrowLeftToLine className="w-3 h-3" />
            </button>
          )}
          {dockSide !== 'right' && (
            <button
              type="button"
              onClick={() => onChangeDockSide('right')}
              title="Dock Right"
              aria-label={`Dock ${title} right`}
              className="text-zinc-500 hover:text-indigo-300 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-white/[0.06] transition"
            >
              <ArrowRightToLine className="w-3 h-3" />
            </button>
          )}
          {dockSide !== 'float' && (
            <button
              type="button"
              onClick={() => onChangeDockSide('float')}
              title="Undock (Floating Window)"
              aria-label={`Undock ${title}`}
              className="text-indigo-300 hover:text-white w-6 h-6 rounded-lg flex items-center justify-center bg-indigo-500/15 hover:bg-indigo-500/25 transition"
            >
              <ExternalLink className="w-3 h-3" />
            </button>
          )}
          {onCloseAction && (
            <button
              type="button"
              onClick={onCloseAction}
              title={closeTitle || 'Close'}
              aria-label={closeTitle || `Close ${title}`}
              className="text-zinc-500 hover:text-zinc-200 w-6 h-6 rounded-lg flex items-center justify-center hover:bg-white/[0.06] transition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="relative flex-1 flex flex-col overflow-hidden">{children}</div>

      {/* Floating Resize Handles */}
      {!isDocked && (
        <>
          <div onPointerDown={startResize('e')} className="absolute right-0 top-3 bottom-3 w-1.5 cursor-ew-resize touch-none z-30" />
          <div onPointerDown={startResize('w')} className="absolute left-0 top-3 bottom-3 w-1.5 cursor-ew-resize touch-none z-30" />
          <div onPointerDown={startResize('s')} className="absolute left-3 right-3 bottom-0 h-1.5 cursor-ns-resize touch-none z-30" />
          <div onPointerDown={startResize('se')} className="absolute right-0 bottom-0 w-4 h-4 cursor-nwse-resize touch-none z-40" />
          <div onPointerDown={startResize('sw')} className="absolute left-0 bottom-0 w-4 h-4 cursor-nesw-resize touch-none z-40" />
        </>
      )}
    </aside>
  );
};
