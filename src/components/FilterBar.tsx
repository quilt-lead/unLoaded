import React from 'react';
import { Search, ArrowDown, ArrowUp, ArrowUpDown, X } from 'lucide-react';
import { BimNode, DatabaseDiffSummary, DiffStatus, FilterState, TraceDirection } from '../types/bim';

interface FilterBarProps {
  filters: FilterState;
  onChangeFilters: (next: FilterState) => void;
  onClearFilters: () => void;
  isFilterActive: boolean;
  categories: BimNode[];
  floors: string[];
  traceDirection: TraceDirection;
  onChangeTraceDirection: (dir: TraceDirection) => void;
  traceSteps: number;
  onChangeTraceSteps: (steps: number) => void;
  heatmapMode: boolean;
  diffSummary: DatabaseDiffSummary | null;
  diffFilter: 'ALL' | 'CHANGED' | DiffStatus;
  onChangeDiffFilter: (val: 'ALL' | 'CHANGED' | DiffStatus) => void;
  matchedCount: number;
  totalInstances: number;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  filters,
  onChangeFilters,
  onClearFilters,
  isFilterActive,
  categories,
  floors,
  traceDirection,
  onChangeTraceDirection,
  traceSteps,
  onChangeTraceSteps,
  heatmapMode,
  diffSummary,
  diffFilter,
  onChangeDiffFilter,
  matchedCount,
  totalInstances,
}) => {
  return (
    <div className="apple-glass-chrome border-b border-white/[0.07] px-5 py-2 flex flex-wrap items-center justify-between gap-3 z-20 flex-shrink-0">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="w-3 h-3 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={filters.search}
            onChange={(e) => onChangeFilters({ ...filters, search: e.target.value })}
            placeholder="Search element, calc, level..."
            className="bg-[#1e2127]/80 border border-white/[0.14] focus:border-indigo-400/50 focus:outline-none rounded-lg pl-7 pr-2.5 py-1 text-[11px] text-zinc-200 placeholder-zinc-600 w-48 transition"
          />
        </div>

        <div className="flex items-center gap-1.5 bg-[#1e2127]/60 border border-white/[0.12] rounded-lg px-2 py-1">
          <span className="mono text-[9px] text-zinc-500 uppercase">Type</span>
          <select
            value={filters.type}
            onChange={(e) => onChangeFilters({ ...filters, type: e.target.value })}
            className="bg-transparent text-[11px] text-zinc-200 focus:outline-none cursor-pointer"
          >
            <option value="ALL" className="bg-[#2d3139]">
              All Types ({categories.length})
            </option>
            {categories.map((c) => (
              <option key={c.id} value={c.id} className="bg-[#2d3139]">
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5 bg-[#1e2127]/60 border border-white/[0.12] rounded-lg px-2 py-1">
          <span className="mono text-[9px] text-zinc-500 uppercase">Level</span>
          <select
            value={filters.level}
            onChange={(e) => onChangeFilters({ ...filters, level: e.target.value })}
            className="bg-transparent text-[11px] text-zinc-200 focus:outline-none cursor-pointer"
          >
            <option value="ALL" className="bg-[#2d3139]">
              All Levels ({floors.length})
            </option>
            {floors.map((fl) => (
              <option key={fl} value={fl} className="bg-[#2d3139]">
                {fl === 'FDN' ? 'FDN (Mat & Piles)' : fl}
              </option>
            ))}
          </select>
        </div>

        {/* Diff Status Quick-Filter Bar when comparing two databases */}
        {diffSummary ? (
          <div className="flex items-center gap-1 bg-[#1e2127]/85 border border-amber-400/35 rounded-lg p-0.5">
            <button
              type="button"
              onClick={() => onChangeDiffFilter('ALL')}
              className={`mono text-[10px] px-2 py-0.5 rounded-md transition ${
                diffFilter === 'ALL'
                  ? 'bg-white/15 text-white font-semibold'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              All ({totalInstances})
            </button>
            <button
              type="button"
              onClick={() => onChangeDiffFilter('CHANGED')}
              className={`mono text-[10px] px-2 py-0.5 rounded-md transition ${
                diffFilter === 'CHANGED'
                  ? 'bg-indigo-500/30 text-indigo-200 border border-indigo-400/40 font-semibold'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Changed ({diffSummary.addedCount + diffSummary.removedCount + diffSummary.modifiedCount})
            </button>
            <button
              type="button"
              onClick={() => onChangeDiffFilter('added')}
              className={`mono text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1 transition ${
                diffFilter === 'added'
                  ? 'bg-emerald-500/25 text-emerald-200 border border-emerald-400/40 font-semibold'
                  : 'text-emerald-400/80 hover:text-emerald-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />+{diffSummary.addedCount} Added
            </button>
            <button
              type="button"
              onClick={() => onChangeDiffFilter('modified')}
              className={`mono text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1 transition ${
                diffFilter === 'modified'
                  ? 'bg-amber-500/25 text-amber-200 border border-amber-400/40 font-semibold'
                  : 'text-amber-400/80 hover:text-amber-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />~{diffSummary.modifiedCount} Mod
            </button>
            <button
              type="button"
              onClick={() => onChangeDiffFilter('removed')}
              className={`mono text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1 transition ${
                diffFilter === 'removed'
                  ? 'bg-rose-500/25 text-rose-200 border border-rose-400/40 font-semibold'
                  : 'text-rose-400/80 hover:text-rose-300'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />-{diffSummary.removedCount} Rem
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 bg-[#1e2127]/70 border border-white/[0.14] rounded-lg p-0.5">
            <div role="group" aria-label="Load Path Trace Direction" className="flex items-center">
              <span className="mono text-[9px] text-zinc-500 uppercase px-1.5">Trace</span>
              <button
                type="button"
                onClick={() => onChangeTraceDirection('down')}
                className={`mono text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1 transition ${
                  traceDirection === 'down'
                    ? 'bg-indigo-500/25 text-indigo-200 border border-indigo-400/40 font-medium'
                    : 'text-zinc-400 hover:text-zinc-200 border border-transparent'
                }`}
              >
                <ArrowDown className="w-2.5 h-2.5" />
                Down
              </button>
              <button
                type="button"
                onClick={() => onChangeTraceDirection('up')}
                className={`mono text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1 transition ${
                  traceDirection === 'up'
                    ? 'bg-indigo-500/25 text-indigo-200 border border-indigo-400/40 font-medium'
                    : 'text-zinc-400 hover:text-zinc-200 border border-transparent'
                }`}
              >
                <ArrowUp className="w-2.5 h-2.5" />
                Up
              </button>
              <button
                type="button"
                onClick={() => onChangeTraceDirection('both')}
                className={`mono text-[10px] px-2 py-0.5 rounded-md flex items-center gap-1 transition ${
                  traceDirection === 'both'
                    ? 'bg-indigo-500/25 text-indigo-200 border border-indigo-400/40 font-medium'
                    : 'text-zinc-400 hover:text-zinc-200 border border-transparent'
                }`}
              >
                <ArrowUpDown className="w-2.5 h-2.5" />
                Up & Down
              </button>
            </div>

            <div className="h-3.5 w-px bg-white/[0.1]" />

            <div className="flex items-center gap-1.5 pr-2 pl-1">
              <label htmlFor="traceStepsSlider" className="mono text-[9px] text-zinc-500 uppercase cursor-pointer">
                Steps
              </label>
              <input
                id="traceStepsSlider"
                type="range"
                min={1}
                max={16}
                value={traceSteps}
                onChange={(e) => onChangeTraceSteps(parseInt(e.target.value, 10))}
                className="trace-steps-slider w-20"
              />
              <span className="mono text-[10px] font-semibold text-indigo-300 min-w-[26px] text-right">
                {traceSteps >= 16 ? 'ALL' : traceSteps}
              </span>
            </div>
          </div>
        )}

        {isFilterActive && (
          <button
            type="button"
            onClick={onClearFilters}
            className="mono text-[10px] px-2 py-1 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] text-zinc-300 flex items-center gap-1 transition"
          >
            <X className="w-3 h-3" />
            Clear
          </button>
        )}
      </div>

      <div className="flex items-center gap-3">
        {!diffSummary && heatmapMode && (
          <div className="hidden sm:flex items-center gap-2 bg-[#1e2127]/70 border border-white/[0.12] px-2.5 py-1 rounded-lg">
            <span className="mono text-[9px] text-zinc-400 uppercase">Load Utilization:</span>
            <span className="mono text-[9px] text-cyan-300">30%</span>
            <div
              className="w-24 h-2 rounded-full"
              style={{
                background: 'linear-gradient(90deg, #06b6d4 0%, #10b981 35%, #f59e0b 70%, #ef4444 100%)',
              }}
            />
            <span className="mono text-[9px] text-rose-400">95%+</span>
          </div>
        )}
        <span className="mono text-[10px] text-zinc-400 bg-white/[0.04] border border-white/[0.07] px-2.5 py-1 rounded-lg">
          {isFilterActive ? `${matchedCount} / ${totalInstances} elements matched` : `${totalInstances} elements`}
        </span>
      </div>
    </div>
  );
};
