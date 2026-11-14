import { useMemo, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { InfoTip } from "../../help/InfoTip";
import type { Band, Health, Impact } from "./api";
import { BAND_COLOR, UC_COLOR, colShort, ucColor, type DesignIndex } from "./util";

export interface PlanViewProps {
  idx: DesignIndex;
  heat: Record<string, Health> | undefined;
  bandMode: "design" | "construction";
  selected: string | null;
  /** current (draft) offset of the selected column, ft */
  dx: number;
  dy: number;
  remove: boolean;
  step: number;
  impact: Impact | undefined;
  moveMode: boolean;
  onSelect: (col: string) => void;
  onDrag: (dx: number, dy: number) => void;
  onDrop: (dx: number, dy: number) => void;
  level?: string;
}

const M = 14; // ft margin
const LIMIT = 20; // ft max drag

export const bandOf = (h: Health | undefined, mode: "design" | "construction"): Band | undefined =>
  h ? (mode === "construction" ? h.band_construction ?? h.band : h.band) : undefined;

/** Plan of one level (default Level 2): grids, framing, columns coloured by health; drag a column to move it. */
export function PlanView(p: PlanViewProps) {
  const { idx, heat, bandMode, selected, dx, dy, remove, step, impact, moveMode, onSelect, onDrag, onDrop, level = "L2" } = p;
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ col: string; x0: number; y0: number; px: number; py: number; moved: boolean } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const b = idx.building;
  const xs = b.grids.x.map((g) => g[1]);
  const ys = b.grids.y.map((g) => g[1]);
  const W = Math.max(...xs), H = Math.max(...ys);

  const members = useMemo(
    () =>
      idx.design.elements.filter(
        (e) => (e.type === "beam" || e.type === "girder" || e.type === "brace") && e.level === level && Array.isArray(e.p1) && Array.isArray(e.p2),
      ) as unknown as { id: string; type: string; sfrs?: boolean; p1: number[]; p2: number[] }[],
    [idx, level],
  );

  const toPlan = (ev: { clientX: number; clientY: number }) => {
    const s = svg.current!;
    const pt = s.createSVGPoint();
    pt.x = ev.clientX;
    pt.y = ev.clientY;
    const q = pt.matrixTransform(s.getScreenCTM()!.inverse());
    return { x: q.x, y: -q.y };
  };
  const snap = (v: number) => Math.max(-LIMIT, Math.min(LIMIT, Math.round(v / step) * step));

  const down = (col: string, ev: RPointerEvent) => {
    ev.preventDefault();
    const q = toPlan(ev);
    const [x0, y0] = b.columns[colShort(col)];
    drag.current = { col, x0, y0, px: q.x, py: q.y, moved: false };
    (ev.target as Element).setPointerCapture?.(ev.pointerId);
  };
  const move = (ev: RPointerEvent) => {
    const d = drag.current;
    if (!d || !moveMode) return;
    const q = toPlan(ev);
    if (!d.moved && Math.hypot(q.x - d.px, q.y - d.py) < step * 0.4) return;
    if (!d.moved) {
      d.moved = true;
      if (d.col !== selected) onSelect(d.col);
    }
    onDrag(snap(q.x - d.x0), snap(q.y - d.y0));
  };
  const up = (ev: RPointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (!d.moved || !moveMode) return onSelect(d.col);
    const q = toPlan(ev);
    onDrop(snap(q.x - d.x0), snap(q.y - d.y0));
  };

  const est = impact?.estimates ?? {};
  const geo = impact?.geometry ?? {};
  const impacted = !!impact;
  const sel = selected ? b.columns[colShort(selected)] : null;
  const ghost = sel && moveMode && !remove && (dx || dy) ? [sel[0] + dx, sel[1] + dy] : null;

  return (
    <div className="v2-plan">
      <svg
        ref={svg}
        viewBox={`${-M} ${-(H + M)} ${W + 2 * M} ${H + 2 * M}`}
        role="img"
        aria-label={`Plan of ${level}: drag a column to move it`}
        onPointerMove={move}
        onPointerUp={up}
      >
        {/* grids */}
        {b.grids.x.map(([n, x]) => (
          <g key={`gx${n}`} className="v2-grid">
            <line x1={x} y1={4} x2={x} y2={-(H + 4)} />
            <circle cx={x} cy={8.5} r={3.2} />
            <text x={x} y={9.6} textAnchor="middle">{n}</text>
          </g>
        ))}
        {b.grids.y.map(([n, y]) => (
          <g key={`gy${n}`} className="v2-grid">
            <line x1={-4} y1={-y} x2={W + 4} y2={-y} />
            <circle cx={-8.5} cy={-y} r={3.2} />
            <text x={-8.5} y={-y + 1.1} textAnchor="middle">{n}</text>
          </g>
        ))}
        {/* framing at this level */}
        {members.map((m) => {
          const e = est[m.id];
          const g = geo[m.id];
          const color = impacted ? (e ? ucColor(e.uc_new) : g ? UC_COLOR.moved : "var(--edge)") : m.sfrs ? "var(--calc)" : "var(--edge)";
          return (
            <g key={m.id}>
              <line
                className={`v2-mem${m.sfrs ? " sfrs" : ""}${impacted && !e && !g ? " faded" : ""}`}
                x1={m.p1[0]}
                y1={-m.p1[1]}
                x2={m.p2[0]}
                y2={-m.p2[1]}
                stroke={color}
              >
                <title>{`${m.id}${e?.uc_new != null ? ` - est. UC ${e.uc_old?.toFixed(2)} -> ${e.uc_new.toFixed(2)}` : ""}`}</title>
              </line>
              {g && <line className="v2-mem ghost" x1={g.p1[0]} y1={-g.p1[1]} x2={g.p2[0]} y2={-g.p2[1]} />}
            </g>
          );
        })}
        {/* columns */}
        {idx.columns.map((c) => {
          const short = colShort(c.id);
          const [x, y] = b.columns[short] ?? [c.x as number, c.y as number];
          const band = bandOf(heat?.[c.id], bandMode);
          const isSel = c.id === selected;
          const fill = impacted && est[c.id] ? ucColor(est[c.id].uc_new) : band ? BAND_COLOR[band] : "var(--muted)";
          const sz = 3.4;
          return (
            <g
              key={c.id}
              className={`v2-col${isSel ? " sel" : ""}${moveMode ? " draggable" : ""}`}
              onPointerDown={(ev) => down(c.id, ev)}
              onPointerEnter={() => setHover(c.id)}
              onPointerLeave={() => setHover((h) => (h === c.id ? null : h))}
              data-col={c.id}
            >
              <rect x={x - sz / 2} y={-y - sz / 2} width={sz} height={sz} rx={0.5} fill={fill} className={c.sfrs ? "sfrs" : undefined} />
              {isSel && remove && <path className="v2-x" d={`M${x - 3} ${-y - 3} L${x + 3} ${-y + 3} M${x + 3} ${-y - 3} L${x - 3} ${-y + 3}`} />}
              <text x={x + 2.6} y={-y - 2.4} className="v2-col-label">{short}</text>
              <title>{`${c.id} ${c.size ?? ""}${band ? ` - ${band}` : ""}${c.sfrs ? " - lateral system" : ""}`}</title>
            </g>
          );
        })}
        {ghost && sel && (
          <g className="v2-ghost" pointerEvents="none">
            <line x1={sel[0]} y1={-sel[1]} x2={ghost[0]} y2={-ghost[1]} markerEnd="url(#v2-arrow)" />
            <rect x={ghost[0] - 2} y={-ghost[1] - 2} width={4} height={4} rx={0.6} />
            <text x={ghost[0] + 3} y={-ghost[1] + 4.5}>{`${dx >= 0 ? "+" : ""}${dx}, ${dy >= 0 ? "+" : ""}${dy} ft`}</text>
          </g>
        )}
        <defs>
          <marker id="v2-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="var(--accent)" />
          </marker>
        </defs>
      </svg>
      <div className="v2-plan-cap">
        <span>
          Plan, {idx.building.levels.find((l) => l.key === level)?.name ?? level} framing <InfoTip id="viewer3d.move-plan" />
        </span>
        {hover && <span className="mono muted">{hover}</span>}
      </div>
    </div>
  );
}
