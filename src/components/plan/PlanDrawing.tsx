// One level of the 2D plan as SVG, drawn like a framing plan: slab edge with a light hatch, beams as
// members at their section width, braces dashed, columns and walls cut solid, a column that starts on
// this level dashed, footings as hidden lines, connections as small diamonds. Geometry is in model
// metres under one transform; labels are laid out in screen px so they stay legible at any zoom.
import React from 'react';
import type { Emphasis } from '../../utils/elementEmphasis';
import type { LevelPlan, PlanItem, Vec2 } from '../../utils/planSlice';
import { toScreen, type PlanCamera, type Viewport } from './planCamera';

export const PLAN_BG = '#2d3139';
export const SELECT = '#14AE5C';

interface PlanDrawingProps {
  plan: LevelPlan;
  camera: PlanCamera;
  viewport: Viewport;
  emphasis: Map<string, Emphasis>;
  hoveredId: string | null;
  diffMode: boolean;
}

/** opacity of an item in the plan, from its emphasis state */
function alpha(e: Emphasis | undefined, item: PlanItem, diffMode: boolean): number {
  if (!e) return 1;
  if (e.state === 'dim') return diffMode && !e.glow ? 0.22 : 0.14;
  return item.node.isGhost ? 0.7 : 1;
}

function Shape({ item, e, s, a, hovered }: { item: PlanItem; e: Emphasis | undefined; s: number; a: number; hovered: boolean }) {
  const color = e?.color ?? '#6b7280';
  const sh = item.shape;
  const px = (n: number) => n / s; // screen px -> metres
  const ghostDash = item.node.isGhost ? `${px(5)} ${px(3)}` : undefined;
  const common = { 'data-id': item.id, opacity: a, style: { cursor: 'pointer' } } as const;
  const outline = hovered ? '#ffffff' : undefined;

  if (sh.type === 'line') {
    const w = Math.max(sh.width, px(item.role === 'brace' ? 1.5 : 2.5));
    return (
      <line
        {...common}
        x1={sh.a[0]}
        y1={sh.a[1]}
        x2={sh.b[0]}
        y2={sh.b[1]}
        stroke={color}
        strokeWidth={w}
        strokeLinecap="butt"
        strokeDasharray={item.role === 'brace' ? `${px(7)} ${px(4)}` : ghostDash}
      />
    );
  }
  if (sh.type === 'point') {
    const r = Math.max(sh.size / 2, px(4.5));
    const [x, y] = sh.at;
    return (
      <polygon
        {...common}
        points={`${x},${y + r} ${x + r},${y} ${x},${y - r} ${x - r},${y}`}
        fill={color}
        stroke={outline ?? PLAN_BG}
        strokeWidth={px(1)}
      />
    );
  }
  const x = sh.min[0];
  const y = sh.min[1];
  const w = Math.max(sh.max[0] - sh.min[0], px(3));
  const h = Math.max(sh.max[1] - sh.min[1], px(3));
  const rect = { ...common, x, y, width: w, height: h };
  switch (item.role) {
    case 'slab':
      return (
        <g {...common}>
          <rect x={x} y={y} width={w} height={h} fill={color} fillOpacity={0.07} />
          <rect x={x} y={y} width={w} height={h} fill="url(#plan-hatch)" />
          <rect x={x} y={y} width={w} height={h} fill="none" stroke={outline ?? color} strokeOpacity={0.7} strokeWidth={px(1)} strokeDasharray={ghostDash} />
        </g>
      );
    case 'foundation':
      return <rect {...rect} fill="none" stroke={outline ?? color} strokeWidth={px(1)} strokeDasharray={`${px(4)} ${px(3)}`} />;
    case 'column-start':
      return <rect {...rect} fill={color} fillOpacity={0.12} stroke={outline ?? color} strokeWidth={px(1.25)} strokeDasharray={`${px(3)} ${px(2)}`} />;
    case 'other':
      return <rect {...rect} fill="none" stroke={outline ?? color} strokeWidth={px(1)} strokeDasharray={ghostDash} />;
    default: // column, wall: cut, solid
      return <rect {...rect} fill={color} stroke={outline ?? 'rgba(255,255,255,0.55)'} strokeWidth={px(1)} strokeDasharray={ghostDash} />;
  }
}

/** A highlight drawn under a selected item: CalcMap green, a few px wider than the item. */
function Halo({ item, s }: { item: PlanItem; s: number }) {
  const px = (n: number) => n / s;
  const sh = item.shape;
  const ring = { fill: 'none', stroke: SELECT, strokeWidth: px(3), strokeLinejoin: 'round' as const };
  if (sh.type === 'line')
    return <line x1={sh.a[0]} y1={sh.a[1]} x2={sh.b[0]} y2={sh.b[1]} stroke={SELECT} strokeWidth={Math.max(sh.width, px(2.5)) + px(6)} strokeLinecap="round" />;
  if (sh.type === 'point') {
    const r = Math.max(sh.size / 2, px(4.5)) + px(4);
    return <circle cx={sh.at[0]} cy={sh.at[1]} r={r} {...ring} />;
  }
  const g = px(3);
  return <rect x={sh.min[0] - g} y={sh.min[1] - g} width={sh.max[0] - sh.min[0] + 2 * g} height={sh.max[1] - sh.min[1] + 2 * g} {...ring} />;
}

interface Label {
  id: string;
  text: string;
  at: Vec2;
  angle: number;
  selected: boolean;
}

/** Marks in screen space: beams along their length (kept upright), columns beside their section. */
function layoutLabels(plan: LevelPlan, c: PlanCamera, v: Viewport, emphasis: Map<string, Emphasis>): Label[] {
  const out: Label[] = [];
  for (const it of plan.items) {
    const e = emphasis.get(it.id);
    const selected = e?.state === 'primary';
    if (e?.state === 'dim') continue;
    const text = it.node.mark || it.node.label;
    if (!text) continue;
    const sh = it.shape;
    if (it.role === 'beam' && sh.type === 'line') {
      const a = toScreen(c, v, sh.a);
      const b = toScreen(c, v, sh.b);
      const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (!selected && (len < text.length * 6.2 + 16 || c.s < 9)) continue;
      let angle = (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI;
      if (angle > 90) angle -= 180;
      if (angle <= -90) angle += 180;
      const off = (Math.max(sh.width * c.s, 2.5) / 2) + 4;
      const rad = (angle * Math.PI) / 180;
      out.push({ id: it.id, text, angle, selected, at: [(a[0] + b[0]) / 2 + Math.sin(rad) * off, (a[1] + b[1]) / 2 - Math.cos(rad) * off] });
    } else if ((it.role === 'column' || it.role === 'column-start') && sh.type === 'rect') {
      if (!selected && c.s < 16) continue;
      const p = toScreen(c, v, [sh.max[0], sh.max[1]]);
      out.push({ id: it.id, text, angle: 0, selected, at: [p[0] + 4, p[1] - 3] });
    } else if (selected) {
      const p = sh.type === 'point' ? sh.at : sh.type === 'line' ? sh.a : sh.max;
      const q = toScreen(c, v, p);
      out.push({ id: it.id, text, angle: 0, selected, at: [q[0] + 6, q[1] - 6] });
    }
  }
  return out;
}

export const PlanDrawing: React.FC<PlanDrawingProps> = ({ plan, camera: c, viewport: v, emphasis, hoveredId, diffMode }) => {
  const minor = c.s >= 10 ? 1 : c.s >= 2 ? 5 : 25;
  const major = minor * 5;
  const origin = toScreen(c, v, [0, 0]);
  const selected = plan.items.filter((i) => emphasis.get(i.id)?.state === 'primary');
  const labels = layoutLabels(plan, c, v, emphasis);
  return (
    <>
      <defs>
        <pattern id="plan-grid-minor" width={minor * c.s} height={minor * c.s} x={origin[0]} y={origin[1]} patternUnits="userSpaceOnUse">
          <path d={`M ${minor * c.s} 0 L 0 0 0 ${minor * c.s}`} fill="none" stroke="rgba(255,255,255,0.035)" strokeWidth={1} />
        </pattern>
        <pattern id="plan-grid-major" width={major * c.s} height={major * c.s} x={origin[0]} y={origin[1]} patternUnits="userSpaceOnUse">
          <rect width={major * c.s} height={major * c.s} fill="url(#plan-grid-minor)" />
          <path d={`M ${major * c.s} 0 L 0 0 0 ${major * c.s}`} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={1} />
        </pattern>
        <pattern id="plan-hatch" width={0.6} height={0.6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1={0} y1={0} x2={0} y2={0.6} stroke="rgba(255,255,255,0.07)" strokeWidth={0.08} />
        </pattern>
      </defs>
      <rect width={v.w} height={v.h} fill="url(#plan-grid-major)" />
      <g transform={`translate(${v.w / 2} ${v.h / 2}) scale(${c.s} ${-c.s}) translate(${-c.cx} ${-c.cy})`}>
        {selected.map((it) => (
          <Halo key={`halo:${it.id}`} item={it} s={c.s} />
        ))}
        {plan.items.map((it) => {
          const e = emphasis.get(it.id);
          return <Shape key={`${it.role}:${it.id}`} item={it} e={e} s={c.s} a={alpha(e, it, diffMode)} hovered={hoveredId === it.id} />;
        })}
      </g>
      <g className="mono" fontSize={10} pointerEvents="none">
        {labels.map((l) => (
          <text
            key={`label:${l.id}`}
            x={l.at[0]}
            y={l.at[1]}
            transform={l.angle ? `rotate(${l.angle} ${l.at[0]} ${l.at[1]})` : undefined}
            textAnchor={l.angle || l.selected ? 'middle' : 'start'}
            fill={l.selected ? '#ffffff' : 'rgba(228,228,231,0.78)'}
            fontWeight={l.selected ? 600 : 400}
            stroke={PLAN_BG}
            strokeWidth={3}
            paintOrder="stroke"
          >
            {l.text}
          </text>
        ))}
      </g>
    </>
  );
};
