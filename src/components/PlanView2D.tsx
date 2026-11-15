// The 2D plan: one floor level of the model as a framing plan (src/utils/planSlice.ts decides what is
// drawn where), styled and selected exactly like the 3D view (src/utils/elementEmphasis.ts). Drag to
// pan, wheel to zoom, click to select (Shift toggles), Page Up / Page Down or [ ] to change level.
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Layers } from 'lucide-react';
import type { BimNode, ColorMode, HighlightOverlay } from '../types/bim';
import { computeLitSet, elementEmphasis, type Emphasis } from '../utils/elementEmphasis';
import { stepLevel, type PlanIndex, type PlanItem } from '../utils/planSlice';
import { LevelLadder } from './plan/LevelLadder';
import { PLAN_BG, PlanDrawing } from './plan/PlanDrawing';
import { fitCamera, inView, panBy, scaleBarMetres, zoomAt, type PlanCamera, type Viewport } from './plan/planCamera';

interface PlanView2DProps {
  nodes: BimNode[];
  index: PlanIndex;
  levelId: string | null;
  onLevelChange: (id: string) => void;
  selectedNodeId: string | null;
  selectedNodeIds: Set<string>;
  activeLoadChainNodeIds: Set<string>;
  matchingNodeIds: Set<string>;
  isFilterActive: boolean;
  colorMode: ColorMode;
  diffMode: boolean;
  overlay: HighlightOverlay | null;
  /** bumped by FIT: frame the selection on this level, or the whole plan */
  fitTrigger: number;
  /** bumped by Reset: frame the whole plan */
  resetTrigger: number;
  /** bumped on every selection: bring it into view without changing the zoom */
  revealTrigger: number;
  emptyText?: React.ReactNode;
  onSelectNode: (id: string, opts?: { toggleMulti?: boolean }) => void;
}

const CLICK_PX = 3;
const KIND_LABEL: Record<string, string> = { 'column-start': 'column, starts here', foundation: 'foundation', connection: 'connection' };

export const PlanView2D: React.FC<PlanView2DProps> = (props) => {
  const { nodes, index, levelId, onLevelChange, diffMode, onSelectNode } = props;
  const host = useRef<HTMLDivElement | null>(null);
  const [vp, setVp] = useState<Viewport>({ w: 0, h: 0 });
  const [cam, setCam] = useState<PlanCamera | null>(null);
  const [hover, setHover] = useState<{ item: PlanItem; x: number; y: number } | null>(null);
  const plan = levelId ? index.plans.get(levelId) : undefined;

  // size: the panel can be hidden (inactive tab), docked or resized at any time
  useLayoutEffect(() => {
    const el = host.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => {
      const r = e!.contentRect;
      setVp((p) => (p.w === r.width && p.h === r.height ? p : { w: r.width, h: r.height }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // frame the whole model (all levels share one frame, so stepping keeps your place), and keep it
  // framed through panel resizes and docking until the user pans or zooms
  const extKey = index.extents ? index.extents.min.join(',') + index.extents.max.join(',') : '';
  const visible = vp.w > 0 && vp.h > 0;
  const userMoved = useRef(false);
  // the pad leaves room for the marks drawn beside edge columns
  const fit = (ext: { min: [number, number]; max: [number, number] } | null | undefined, v: Viewport, pad = 44) =>
    ext && setCam(fitInto(ext, v, pad));
  useEffect(() => {
    userMoved.current = false;
  }, [extKey]);
  useEffect(() => {
    if (visible && !userMoved.current) fit(index.extents, vp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extKey, visible, vp.w, vp.h]);

  const lit = useMemo(
    () => computeLitSet(nodes, props.selectedNodeId, props.selectedNodeIds, props.activeLoadChainNodeIds),
    [nodes, props.selectedNodeId, props.selectedNodeIds, props.activeLoadChainNodeIds],
  );
  const emphasis = useMemo(() => {
    const m = new Map<string, Emphasis>();
    if (!plan) return m;
    const ctx = { colorMode: props.colorMode, diffMode, overlay: props.overlay, lit, isFilterActive: props.isFilterActive, matchingNodeIds: props.matchingNodeIds };
    for (const it of plan.items) if (!m.has(it.id)) m.set(it.id, elementEmphasis(it.id, it.node, ctx));
    return m;
  }, [plan, props.colorMode, diffMode, props.overlay, lit, props.isFilterActive, props.matchingNodeIds]);

  // camera commands. Selection only pans when the selection is off screen; FIT frames it.
  // the selection on this level; a selected category / family / group stands for its elements
  const selectedOnLevel = () => {
    if (!plan || !lit.any) return [];
    const direct = plan.items.filter((i) => lit.primary.has(i.id));
    return direct.length ? direct : plan.items.filter((i) => lit.ids.has(i.id));
  };
  const centreOf = (it: PlanItem): [number, number] =>
    it.shape.type === 'point' ? it.shape.at : it.shape.type === 'line' ? [(it.shape.a[0] + it.shape.b[0]) / 2, (it.shape.a[1] + it.shape.b[1]) / 2] : [(it.shape.min[0] + it.shape.max[0]) / 2, (it.shape.min[1] + it.shape.max[1]) / 2];
  const camRef = useRef({ cam, vp, plan, lit });
  camRef.current = { cam, vp, plan, lit };

  useEffect(() => {
    const { cam: c, vp: v } = camRef.current;
    if (props.revealTrigger === 0 || !c || !visible) return;
    const sel = selectedOnLevel();
    if (sel.length === 0 || sel.some((i) => inView(c, v, centreOf(i)))) return;
    const [x, y] = centreOf(sel[0]!);
    setCam({ ...c, cx: x, cy: y });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.revealTrigger, levelId]);

  useEffect(() => {
    const { vp: v, plan: p } = camRef.current;
    if (props.fitTrigger === 0 || !visible) return;
    const sel = selectedOnLevel();
    userMoved.current = sel.length > 0;
    fit(sel.length ? extentsAround(sel) : p?.extents ?? index.extents, v, sel.length ? 56 : 44);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.fitTrigger]);

  useEffect(() => {
    if (props.resetTrigger === 0 || !visible) return;
    userMoved.current = false;
    fit(index.extents, camRef.current.vp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.resetTrigger]);

  // wheel zoom needs a non-passive listener; it must not scroll or reach the panel behind
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const r = el.getBoundingClientRect();
      const factor = Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015));
      userMoved.current = true;
      setCam((c) => (c ? zoomAt(c, { w: r.width, h: r.height }, factor, [e.clientX - r.left, e.clientY - r.top]) : c));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  // drag pans; a press that moves less than CLICK_PX from pointerdown is a click
  const drag = useRef<{ id: number; x: number; y: number; lx: number; ly: number; moved: boolean; target: string | null } | null>(null);
  const idAt = (t: EventTarget | null) => ((t as Element | null)?.closest?.('[data-id]') as Element | null)?.getAttribute('data-id') ?? null;
  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0 && e.button !== 1) return;
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { id: e.pointerId, x: e.clientX, y: e.clientY, lx: e.clientX, ly: e.clientY, moved: false, target: idAt(e.target) };
  };
  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (d && d.id === e.pointerId) {
      if (!d.moved && Math.hypot(e.clientX - d.x, e.clientY - d.y) < CLICK_PX) return;
      d.moved = true;
      userMoved.current = true;
      const dx = e.clientX - d.lx;
      const dy = e.clientY - d.ly;
      d.lx = e.clientX;
      d.ly = e.clientY;
      setCam((c) => (c ? panBy(c, dx, dy) : c));
      setHover(null);
      return;
    }
    const id = idAt(e.target);
    const item = id ? plan?.items.find((i) => i.id === id) : undefined;
    const r = host.current!.getBoundingClientRect();
    setHover(item ? { item, x: e.clientX - r.left, y: e.clientY - r.top } : null);
  };
  const onPointerUp = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    drag.current = null;
    if (!d.moved && d.target && e.button === 0) onSelectNode(d.target, { toggleMulti: e.shiftKey });
  };

  const step = (dir: 1 | -1) => {
    const next = stepLevel(index, levelId, dir);
    if (next) onLevelChange(next);
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    const k = e.key;
    if (k === 'PageUp' || k === ']') step(1);
    else if (k === 'PageDown' || k === '[') step(-1);
    else if ((k === '+' || k === '=' || k === '-') && cam) setCam(zoomAt(cam, vp, k === '-' ? 1 / 1.25 : 1.25, [vp.w / 2, vp.h / 2]));
    else if (k.startsWith('Arrow') && cam) {
      const d = 48;
      setCam(panBy(cam, k === 'ArrowLeft' ? d : k === 'ArrowRight' ? -d : 0, k === 'ArrowUp' ? d : k === 'ArrowDown' ? -d : 0));
    } else return;
    if (k !== 'PageUp' && k !== 'PageDown' && k !== '[' && k !== ']') userMoved.current = true;
    e.preventDefault();
    e.stopPropagation();
  };

  useEffect(() => setHover(null), [levelId]);

  // a selection drawn only on other levels: say where it is, rather than leave a dimmed floor unexplained
  const elsewhere = useMemo(() => {
    if (!plan || !lit.any || plan.items.some((i) => lit.primary.has(i.id))) return null;
    for (const id of lit.primary) {
      const lv = index.levelsOf.get(id)?.[0];
      if (lv) return index.levels.find((l) => l.id === lv) ?? null;
    }
    return null;
  }, [plan, lit, index]);

  const counts = plan ? countRoles(plan.items) : '';
  const empty = index.levels.length === 0;
  const bar = cam ? scaleBarMetres(cam.s) : 0;

  return (
    <div
      ref={host}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="relative w-full h-full overflow-hidden outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-calcmap/60"
      style={{ background: PLAN_BG, touchAction: 'none' }}
      aria-label="2D plan view. Page Up and Page Down change level; arrow keys pan; plus and minus zoom."
    >
      {!empty && plan && cam && visible && (
        <svg
          width={vp.w}
          height={vp.h}
          className="absolute inset-0 block cursor-grab active:cursor-grabbing"
          role="img"
          aria-label={`Plan of ${plan.level.name}: ${counts}`}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => (drag.current = null)}
          onPointerLeave={() => setHover(null)}
        >
          <PlanDrawing plan={plan} camera={cam} viewport={vp} emphasis={emphasis} hoveredId={hover?.item.id ?? null} diffMode={diffMode} />
        </svg>
      )}

      {empty ? (
        <div className="absolute inset-0 grid place-items-center p-6 text-center pointer-events-none">
          <div className="flex flex-col items-center gap-2 max-w-xs">
            <div className="w-9 h-9 rounded-xl bg-white/[0.04] border border-white/[0.08] text-zinc-500 flex items-center justify-center">
              <Layers className="w-4 h-4" />
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              {props.emptyText ?? 'No plan to draw: the model has no element geometry to slice into levels.'}
            </p>
          </div>
        </div>
      ) : (
        levelId && <LevelLadder levels={index.levels} currentId={levelId} onChange={onLevelChange} compact={visible && vp.w < 480} />
      )}

      {elsewhere && (
        <button
          type="button"
          onClick={() => onLevelChange(elsewhere.id)}
          className="absolute top-2.5 left-1/2 -translate-x-1/2 text-[11px] text-zinc-200 bg-[#23272e]/95 border border-calcmap/40 hover:border-calcmap rounded-full pl-3 pr-2.5 py-1 flex items-center gap-1.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap transition"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-calcmap" aria-hidden />
          Selection is on {elsewhere.name}
          <span className="text-calcmap font-medium">Go to level</span>
        </button>
      )}

      {cam && !empty && bar > 0 && (
        <div className="absolute right-3 bottom-10 flex flex-col items-end gap-0.5 pointer-events-none" aria-hidden>
          <span className="mono text-[9px] text-zinc-400 tabular-nums">{bar >= 1 ? `${bar} m` : `${Math.round(bar * 1000)} mm`}</span>
          <span className="block h-1.5 border-x border-b border-zinc-400/80" style={{ width: bar * cam.s }} />
        </div>
      )}

      {hover && (
        <div
          role="tooltip"
          className="absolute pointer-events-none z-10 bg-[#1f2329]/95 border border-white/[0.12] rounded-md px-2 py-1.5 shadow-lg max-w-[220px]"
          style={{ left: Math.min(hover.x + 14, vp.w - 228), top: Math.max(hover.y - 8, 4) }}
        >
          <div className="text-[12px] font-semibold text-zinc-100 truncate">{hover.item.node.mark || hover.item.node.label}</div>
          <div className="text-[10px] text-zinc-400 truncate">
            {[KIND_LABEL[hover.item.role] ?? hover.item.node.elementKind, hover.item.node.size].filter(Boolean).join(', ')}
          </div>
          {hover.item.node.diffStatus && hover.item.node.diffStatus !== 'unchanged' && (
            <div className="text-[10px] text-zinc-300 capitalize">{hover.item.node.isGhost ? 'Removed (only in the base revision)' : hover.item.node.diffStatus}</div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Fit into the part of the view the overlays leave free: the level control on the left (when the
 * panel is wide enough to spare it) and the status strip and scale bar at the bottom.
 */
export function fitInto(ext: { min: [number, number]; max: [number, number] }, v: Viewport, pad: number): PlanCamera {
  const left = v.w >= 480 ? 150 : 0;
  const bottom = 52;
  const c = fitCamera(ext, { w: v.w - left, h: v.h - bottom }, pad);
  // shift the centre so the framed area sits in the free region, not under the overlays
  return { ...c, cx: c.cx - left / 2 / c.s, cy: c.cy - bottom / 2 / c.s };
}

function extentsAround(items: PlanItem[]) {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const { shape: s } of items) {
    const pts = s.type === 'line' ? [s.a, s.b] : s.type === 'rect' ? [s.min, s.max] : [s.at];
    for (const p of pts) {
      xs.push(p[0]);
      ys.push(p[1]);
    }
  }
  // never zoom in tighter than a 6 m window around a small selection
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const hw = Math.max((Math.max(...xs) - Math.min(...xs)) / 2, 3);
  const hh = Math.max((Math.max(...ys) - Math.min(...ys)) / 2, 3);
  return { min: [cx - hw, cy - hh] as [number, number], max: [cx + hw, cy + hh] as [number, number] };
}

const ROLE_NAMES: [string, string, string][] = [
  ['beam', 'beam', 'beams'],
  ['column', 'column', 'columns'],
  ['connection', 'connection', 'connections'],
  ['wall', 'wall', 'walls'],
  ['brace', 'brace', 'braces'],
  ['foundation', 'foundation', 'foundations'],
];

/** "31 beams, 20 columns, 16 connections" */
export function countRoles(items: PlanItem[]): string {
  const n = new Map<string, number>();
  for (const i of items) {
    const r = i.role === 'column-start' ? 'column' : i.role;
    n.set(r, (n.get(r) ?? 0) + 1);
  }
  return ROLE_NAMES.filter(([r]) => n.get(r))
    .map(([r, one, many]) => `${n.get(r)} ${n.get(r) === 1 ? one : many}`)
    .join(', ');
}
