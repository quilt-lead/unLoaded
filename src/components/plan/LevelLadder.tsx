// The level control of the 2D plan: a small section through the building. Every level is a rung at
// its true relative height, the current one carries a datum marker and its elevation, and the
// arrows step one level up or down.
import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { formatElevation, type PlanLevel } from '../../utils/planSlice';

interface LevelLadderProps {
  levels: PlanLevel[];
  currentId: string;
  onChange: (id: string) => void;
  /** a narrow panel: arrows, name and elevation only */
  compact?: boolean;
}

const LADDER_PX = 88;
const MIN_GAP = 9;

/** rung offsets from the top, proportional to elevation unless that crowds them, then even */
export function rungOffsets(levels: PlanLevel[], height = LADDER_PX): number[] {
  if (levels.length < 2) return levels.map(() => height / 2);
  const lo = levels[0]!.elevation;
  const hi = levels[levels.length - 1]!.elevation;
  const prop = levels.map((l) => (hi === lo ? 0 : ((hi - l.elevation) / (hi - lo)) * height));
  const crowded = prop.some((y, i) => i > 0 && prop[i - 1]! - y < MIN_GAP);
  return crowded ? levels.map((_, i) => ((levels.length - 1 - i) / (levels.length - 1)) * height) : prop;
}

export const LevelLadder: React.FC<LevelLadderProps> = ({ levels, currentId, onChange, compact = false }) => {
  const i = levels.findIndex((l) => l.id === currentId);
  const current = levels[i];
  const above = levels[i + 1];
  const below = levels[i - 1];
  const showRungs = !compact && levels.length > 1 && levels.length <= 40;
  const ys = showRungs ? rungOffsets(levels) : [];
  const btn =
    'w-6 h-6 rounded-md flex items-center justify-center text-zinc-300 hover:text-white hover:bg-white/[0.08] disabled:text-zinc-700 disabled:hover:bg-transparent focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap transition';
  if (!current) return null;
  return (
    <nav aria-label="Plan level" className="absolute top-2.5 left-2.5 flex items-stretch gap-2 bg-[#23272e]/90 backdrop-blur-md border border-white/[0.08] rounded-lg pl-1 pr-2.5 py-1 select-none">
      <div className="flex flex-col justify-between">
        <button type="button" className={btn} disabled={!above} onClick={() => above && onChange(above.id)} aria-label={above ? `Level up to ${above.name}` : 'Top level'} title="Level up (Page Up)">
          <ChevronUp className="w-3.5 h-3.5" />
        </button>
        <button type="button" className={btn} disabled={!below} onClick={() => below && onChange(below.id)} aria-label={below ? `Level down to ${below.name}` : 'Lowest level'} title="Level down (Page Down)">
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className={`flex flex-col justify-center py-0.5 ${compact ? 'min-w-[64px]' : 'min-w-[84px]'}`}>
        <span className="text-[13px] font-semibold text-zinc-100 leading-tight max-w-[132px] truncate" aria-live="polite" title={current.name}>
          {current.name}
        </span>
        <span className="mono text-[10px] text-zinc-400 tabular-nums leading-tight mt-0.5">{formatElevation(current.elevation)}</span>
        {!compact && (
          <span className="text-[10px] text-zinc-500 leading-tight mt-0.5">
            Level {i + 1} of {levels.length}
            {current.hasSlab ? '' : ', no slab'}
          </span>
        )}
      </div>
      {showRungs && (
        <ol className="relative w-4 my-1" style={{ height: LADDER_PX }} aria-label="Levels">
          <span aria-hidden className="absolute left-1/2 top-0 bottom-0 w-px -translate-x-1/2 bg-white/[0.08]" />
          {levels.map((l, k) => {
            const on = l.id === currentId;
            return (
              <li key={l.id} className="absolute left-0 right-0 -translate-y-1/2" style={{ top: ys[k] }}>
                <button
                  type="button"
                  onClick={() => onChange(l.id)}
                  aria-current={on ? 'true' : undefined}
                  aria-label={`${l.name}, ${formatElevation(l.elevation)}`}
                  title={`${l.name}  ${formatElevation(l.elevation)}`}
                  className="group w-full h-2 flex items-center justify-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap rounded-sm"
                >
                  <span className={on ? 'block w-4 h-[3px] rounded-full bg-calcmap' : 'block w-2.5 h-px bg-zinc-500 group-hover:w-4 group-hover:bg-zinc-200 transition-[width,background-color] motion-reduce:transition-none'} />
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </nav>
  );
};
