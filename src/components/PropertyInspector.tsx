// Inspector for whatever is selected: an element (its calc links ranked by confidence with
// review actions, impact, load path, diff before/after), a calc (dependencies, linked elements
// by tier), a category / family / group, or - with nothing selected - the mapping summary.
import React, { useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Calculator,
  Check,
  CircleDot,
  FileSearch,
  Layers,
  Link2,
  Loader2,
  Undo2,
  X,
  Zap,
} from 'lucide-react';
import type {
  BimNode,
  CalcDependency,
  CalcLink,
  CalcPackage,
  ConnectivityEdge,
  DecisionAction,
  FindingView,
  ImpactView,
  LoadPathEdge,
  MappingStatus,
  NodeGroup,
  PdfTarget,
  ProducerRecords,
  ProvenanceView,
  TypicalGroupView,
} from '../types/bim';
import { getDisplayType, getLoadNeighbors } from '../utils/graphEngine';
import { DIFF_PALETTE, STATUS_COLORS, STATUS_LABELS, TIER_LABELS, getEffectiveNodeColor, getHeatmapColor } from '../utils/colors';
import { calcTarget, linkTarget } from './DocumentBrowser';
import { Chip, ConfidenceChip, RoleChip, StatusDot, TierChip } from './ui/Chips';

interface PropertyInspectorProps {
  node: BimNode | null;
  elementNodes: BimNode[];
  calcs: CalcPackage[];
  calcDependencies: CalcDependency[];
  loadPath: LoadPathEdge[];
  connectivity: ConnectivityEdge[];
  calcToElementIds: Map<string, string[]>;
  typicalGroups: TypicalGroupView[];
  findings: FindingView[];
  producers: ProducerRecords | null;
  counts: Record<MappingStatus, number> | null;
  groups: NodeGroup[];
  selectedNodeIds: Set<string>;
  activeLoadChainNodeIds: Set<string>;
  diffMode: boolean;
  impact: ImpactView | null;
  impactLoading: boolean;
  /** decisions and impact need a project; an export JSON opened from disk is read-only */
  canWrite: boolean;
  busy: boolean;
  onSelectNode: (id: string) => void;
  onSelectCalc: (calcKey: string) => void;
  onSelectGroup: (groupId: string) => void;
  onRenameGroup: (groupId: string, newName: string) => void;
  onClearSelection: () => void;
  onOpenTarget: (t: PdfTarget, elementId?: string) => void;
  onShowElementCalcs: (elementId: string) => void;
  onDecide: (elementId: string, calcKey: string, action: DecisionAction) => void;
  onImpact: (elementId: string, mode: 'change' | 'remove') => void;
  onClearImpact: () => void;
}

const Section: React.FC<{ title: React.ReactNode; tone?: string; action?: React.ReactNode; children: React.ReactNode }> = ({
  title,
  tone = 'text-zinc-400',
  action,
  children,
}) => (
  <div className="border-t border-white/[0.07] pt-2.5">
    <div className="flex items-center justify-between mb-1.5 gap-2">
      <p className={`mono text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1 ${tone}`}>{title}</p>
      {action}
    </div>
    {children}
  </div>
);

const shortHash = (h: string) => (h ? `${h.slice(0, 10)}…` : '—');
const shortTime = (iso: string | null) => (iso ? `${iso.slice(0, 16).replace('T', ' ')} ET` : '');

/** Who / which rule made a record, how, and on which input documents (sha256). */
const ProvenanceLine: React.FC<{ label: string; prov: ProvenanceView }> = ({ label, prov }) => (
  <div className="text-[10px] leading-snug">
    <span className="mono text-[9px] text-zinc-500 uppercase">{label}</span>
    <div className="mono text-[9.5px] text-zinc-300 break-all">
      {prov.method === 'human' ? (
        <>
          {prov.actor ?? 'reviewer'} · {shortTime(prov.at)} · {prov.rule}
        </>
      ) : (
        <>
          {prov.producer} · {prov.rule} · {prov.method}
        </>
      )}
    </div>
    {prov.inputs.length > 0 && (
      <div className="mono text-[9px] text-zinc-500" title={prov.inputs.join('\n')}>
        inputs sha256 {prov.inputs.map(shortHash).join(', ')}
      </div>
    )}
  </div>
);

const smallBtn =
  'mono text-[9px] px-1.5 py-0.5 rounded border transition flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed';

const NodeRow: React.FC<{ node: BimNode; right?: React.ReactNode; onClick: () => void; tone?: string }> = ({ node, right, onClick, tone }) => (
  <button
    type="button"
    onClick={onClick}
    className={`w-full text-left flex items-center justify-between px-2 py-1.5 rounded-lg cursor-pointer transition-colors border focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 ${
      tone ?? 'bg-white/[0.03] hover:bg-white/[0.07] border-white/[0.06]'
    }`}
  >
    <span className="flex items-center space-x-2 min-w-0">
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: getEffectiveNodeColor(node, 'type') }} aria-hidden="true" />
      <span className="text-[11px] font-medium text-zinc-100 truncate">{node.label}</span>
    </span>
    {right && <span className="mono text-[9px] text-zinc-400 flex-shrink-0 ml-2 truncate max-w-[55%] text-right">{right}</span>}
  </button>
);

export const PropertyInspector: React.FC<PropertyInspectorProps> = (p) => {
  const { node } = p;
  const [renamingGroupId, setRenamingGroupId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  // Escape cancels a rename: the blur that follows unmounting the input must not commit the draft
  const renameCancelled = useRef(false);
  const [showAllParams, setShowAllParams] = useState(false);
  const nodeById = new Map(p.elementNodes.map((n) => [n.id, n]));
  const calcByKey = new Map(p.calcs.map((c) => [c.key, c]));
  const groupTitle = (id: string) => p.typicalGroups.find((g) => g.id === id)?.title ?? id;
  const writeTitle = p.canWrite ? undefined : 'Read-only: this is an export JSON (open the project file to review)';

  const impactBox = p.impact && (
    <div className="bg-amber-500/[0.08] border border-amber-400/30 rounded-xl p-2.5 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="mono text-[10px] font-semibold text-amber-200 uppercase tracking-wider flex items-center gap-1">
          <Zap className="w-3 h-3" />
          Impact · {p.impact.mode === 'remove' ? 'if removed' : 'if changed'} · {nodeById.get(p.impact.elementId)?.label ?? p.impact.elementId}
        </span>
        <button type="button" onClick={p.onClearImpact} className="mono text-[9px] text-zinc-400 hover:text-white underline">
          Clear
        </button>
      </div>
      <div className="grid grid-cols-3 gap-1.5 text-center">
        {[
          { n: p.impact.removed.length, l: 'Removed', c: 'text-rose-300' },
          { n: p.impact.hit.size, l: `Hit · ${p.impact.waves} waves`, c: 'text-amber-300' },
          { n: p.impact.stale.size, l: 'Calcs stale', c: 'text-amber-200' },
        ].map((x) => (
          <div key={x.l} className="bg-black/30 rounded-lg py-1.5 border border-white/[0.06]">
            <div className={`mono text-sm font-semibold ${x.c}`}>{x.n}</div>
            <div className="mono text-[8.5px] text-zinc-500 uppercase">{x.l}</div>
          </div>
        ))}
      </div>
      {p.impact.stale.size > 0 && (
        <div className="space-y-1 max-h-32 overflow-y-auto">
          <p className="mono text-[9px] text-zinc-500 uppercase">Re-run queue</p>
          {[...p.impact.stale.entries()].map(([k, why]) => {
            const c = calcByKey.get(k);
            return (
              <button
                type="button"
                key={k}
                onClick={() => p.onSelectCalc(k)}
                className="block w-full text-left px-2 py-1 rounded-lg bg-black/25 hover:bg-black/40 border border-white/[0.06] cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
              >
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: c?.color ?? '#71717a' }} />
                  <span className="text-[11px] text-zinc-100 truncate">{c?.title ?? k}</span>
                  {c?.software && <Chip tone="warn">{c.software}</Chip>}
                </div>
                <p className="mono text-[9px] text-zinc-500 mt-0.5 truncate">
                  {why}
                  {c?.scanned || c?.software === 'Hand calc' ? ' · hand calc: flag for engineer' : ''}
                </p>
              </button>
            );
          })}
        </div>
      )}
      {p.impact.hit.size > 0 && (
        <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
          {[...p.impact.hit.entries()]
            .sort((a, b) => a[1] - b[1])
            .slice(0, 40)
            .map(([g, w]) => (
              <button
                key={g}
                type="button"
                title={p.impact?.why.get(g) ?? `wave ${w}: load path from upstream`}
                onClick={() => p.onSelectNode(g)}
                className="mono text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-200 border border-amber-400/25 hover:border-amber-300/60"
              >
                {nodeById.get(g)?.label ?? g} <span className="text-amber-400/70">w{w}</span>
              </button>
            ))}
        </div>
      )}
    </div>
  );

  if (!node) {
    const review = p.elementNodes.filter((n) => n.kind === 'element' && n.mappingStatus === 'review');
    const unmapped = p.elementNodes.filter((n) => n.kind === 'element' && n.mappingStatus === 'unmapped');
    if (!p.counts) {
      return (
        <div className="text-center py-6 text-zinc-500">
          <div className="w-10 h-10 bg-white/[0.03] border border-white/[0.06] text-zinc-500 rounded-xl flex items-center justify-center mx-auto mb-2.5">
            <CircleDot className="w-4 h-4" />
          </div>
          <p className="font-medium text-zinc-300 text-xs">No project loaded</p>
          <p className="text-[11px] text-zinc-500 mt-1">Load the sample, or upload an IFC model and a calc package PDF.</p>
        </div>
      );
    }
    if (p.calcs.length === 0) {
      return (
        <div className="space-y-3">
          {impactBox}
          <div className="text-center py-5">
            <div className="w-10 h-10 bg-white/[0.03] border border-white/[0.06] text-zinc-500 rounded-xl flex items-center justify-center mx-auto mb-2.5">
              <Calculator className="w-4 h-4" aria-hidden="true" />
            </div>
            <p className="font-medium text-zinc-300 text-xs">No calc package in this project</p>
            <p className="text-[11px] text-zinc-500 mt-1 leading-relaxed">
              Click an element to see its properties, load path and connections. Add the calc package PDF (Project menu) to link elements to the calcs that design
              them.
            </p>
          </div>
        </div>
      );
    }
    return (
      <div className="space-y-3">
        {impactBox}
        <div>
          <h3 className="font-semibold text-sm text-white tracking-tight">Mapping summary</h3>
          <p className="text-xs text-zinc-400 mt-1">Click any element or calc to inspect its links and evidence.</p>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {(['confirmed', 'review', 'unmapped'] as MappingStatus[]).map((s) => (
            <div key={s} className="bg-white/[0.02] rounded-xl p-2 border border-white/[0.07]">
              <div className="mono text-base font-semibold" style={{ color: STATUS_COLORS[s] }}>
                {p.counts![s] ?? 0}
              </div>
              <div className="mono text-[9px] text-zinc-500 uppercase">{STATUS_LABELS[s]}</div>
            </div>
          ))}
        </div>
        {p.findings.length > 0 && (
          <Section title={`Findings (${p.findings.length})`} tone="text-rose-400">
            <ul className="space-y-1 max-h-36 overflow-y-auto">
              {p.findings.map((f, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => p.onOpenTarget({ calcKey: f.calcKey, page: f.page, rects: f.rects, caption: `Calc size ${f.calcSize}` }, f.elementId)}
                    className="w-full text-left px-2 py-1.5 rounded-lg bg-rose-500/[0.06] hover:bg-rose-500/[0.14] border border-rose-400/20 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-[11px] text-zinc-100 truncate">{nodeById.get(f.elementId)?.label ?? f.elementId}</span>
                      <span className="mono text-[9px] text-rose-200 flex-shrink-0">
                        {f.modelSize} ≠ {f.calcSize}
                      </span>
                    </span>
                    <span className="block mono text-[9px] text-zinc-500 truncate">
                      {calcByKey.get(f.calcKey)?.title ?? f.calcKey} · p. {f.page}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Section>
        )}
        {p.producers && (
          <Section title="Provenance" tone="text-zinc-400">
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 text-[10px]">
              <dt className="mono text-[9px] text-zinc-500 uppercase">Engine</dt>
              <dd className="mono text-zinc-300 break-all">
                {p.producers.engineProducer ?? 'calc-mapper'} · {p.producers.engine}
              </dd>
              {p.producers.graph && (
                <>
                  <dt className="mono text-[9px] text-zinc-500 uppercase">Model</dt>
                  <dd className="mono text-zinc-300 break-all" title={p.producers.graph.sha256}>
                    {p.producers.graph.source || p.producers.graph.producer} · sha256 {shortHash(p.producers.graph.sha256)}
                  </dd>
                </>
              )}
              {p.producers.calcPackage && (
                <>
                  <dt className="mono text-[9px] text-zinc-500 uppercase">Calcs</dt>
                  <dd className="mono text-zinc-300 break-all" title={p.producers.calcPackage.sha256}>
                    {p.producers.calcPackage.name ?? 'calc package'} · {p.producers.calcPackage.pages} pp · sha256 {shortHash(p.producers.calcPackage.sha256)}
                  </dd>
                </>
              )}
            </dl>
          </Section>
        )}
        {[
          { title: 'Needs review', list: review, tone: 'text-amber-400' },
          { title: 'No calc found', list: unmapped, tone: 'text-rose-400' },
        ].map((g) => (
          <Section key={g.title} title={`${g.title} (${g.list.length})`} tone={g.tone}>
            <div className="space-y-1 max-h-36 overflow-y-auto">
              {g.list.slice(0, 40).map((n) => (
                <NodeRow key={n.id} node={n} right={n.storey} onClick={() => p.onSelectNode(n.id)} />
              ))}
              {g.list.length === 0 && <p className="text-[11px] text-zinc-600 italic">None</p>}
            </div>
          </Section>
        ))}
      </div>
    );
  }

  const containingGroups = p.groups.filter((g) => g.nodeIds.includes(node.id));
  const multiList =
    p.selectedNodeIds.size > 1
      ? [...p.selectedNodeIds].map((id) => nodeById.get(id)).filter((n): n is BimNode => Boolean(n))
      : [];

  const groupsCard = containingGroups.length > 0 && (
    <div className="bg-emerald-500/10 border border-emerald-400/30 rounded-xl p-2.5 space-y-1.5">
      {containingGroups.map((g) => (
        <div key={g.id} className="flex items-center justify-between gap-2">
          {renamingGroupId === g.id ? (
            <input
              type="text"
              aria-label="Group name"
              name="groupName"
              autoComplete="off"
              autoFocus
              value={renameDraft}
              onChange={(e) => setRenameDraft(e.target.value)}
              onBlur={() => {
                // the one commit point: Enter blurs, so a rename is never applied twice
                if (!renameCancelled.current && renameDraft.trim()) p.onRenameGroup(g.id, renameDraft.trim());
                renameCancelled.current = false;
                setRenamingGroupId(null);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  e.stopPropagation();
                  e.currentTarget.blur();
                }
                if (e.key === 'Escape') {
                  // an Escape typed in a field is the field's (escapeStack ignores editable targets)
                  e.preventDefault();
                  e.stopPropagation();
                  renameCancelled.current = true;
                  e.currentTarget.blur();
                }
              }}
              className="min-w-0 flex-1 px-2 py-0.5 rounded bg-black/50 text-white mono text-[10px] border border-emerald-400 focus-visible:ring-2 focus-visible:ring-emerald-300"
            />
          ) : (
            <button
              type="button"
              onClick={() => p.onSelectGroup(g.id)}
              title="Select the whole group"
              className="mono text-[10px] font-semibold text-emerald-200 hover:text-white flex items-center gap-1.5 truncate"
            >
              <Layers className="w-3 h-3 text-emerald-300 flex-shrink-0" />
              <span className="truncate">{g.name}</span>
              <span className="text-emerald-400/80">({g.nodeIds.length})</span>
            </button>
          )}
          {renamingGroupId !== g.id && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <button type="button" onClick={() => p.onSelectGroup(g.id)} className="mono text-[9px] text-emerald-300 hover:text-white underline">
                Select All
              </button>
              <button
                type="button"
                onClick={() => {
                  setRenamingGroupId(g.id);
                  setRenameDraft(g.name);
                }}
                className="mono text-[9px] text-zinc-300 hover:text-white underline"
              >
                Rename
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );

  const multiCard = multiList.length > 1 && (
    <div className="bg-indigo-500/15 border border-indigo-400/35 rounded-xl p-2.5 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="mono text-[10px] font-semibold text-indigo-200 uppercase tracking-wider flex items-center gap-1">
          <Layers className="w-3 h-3 text-indigo-300" />
          {multiList.length} Selected
        </span>
        <button type="button" onClick={p.onClearSelection} className="mono text-[9px] text-zinc-400 hover:text-white underline">
          Clear All
        </button>
      </div>
      <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
        {multiList.map((mn) => (
          <button
            type="button"
            key={mn.id}
            onClick={() => p.onSelectNode(mn.id)}
            title="Focus this element alone"
            aria-pressed={mn.id === node.id}
            className={`mono text-[9px] px-1.5 py-0.5 rounded cursor-pointer border focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 ${
              mn.id === node.id ? 'bg-white text-zinc-900 border-white font-semibold' : 'bg-black/40 text-zinc-200 border-white/15 hover:border-indigo-400/50'
            }`}
          >
            {mn.label}
          </button>
        ))}
      </div>
    </div>
  );

  const header = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="mono text-[10px] font-medium px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-400/25">
          {getDisplayType(node)}
        </span>
        {node.storey && (
          <span className="mono text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-zinc-200 border border-white/[0.16]">{node.storey}</span>
        )}
        <span className="flex-1" />
        {node.kind === 'element' && node.mappingStatus && !node.isGhost && <StatusDot status={node.mappingStatus} />}
      </div>
      <div>
        <h3 className="font-semibold text-sm text-white tracking-tight">{node.label}</h3>
        {node.desc && <p className="text-xs text-zinc-400 mt-1 leading-relaxed">{node.desc}</p>}
      </div>
    </>
  );

  const diffCard = p.diffMode && node.diffStatus && (
    <div className="rounded-xl p-2.5 border space-y-2" style={{ backgroundColor: 'rgba(15, 18, 25, 0.72)', borderColor: DIFF_PALETTE[node.diffStatus] }}>
      <div className="flex items-center justify-between">
        <span
          className="mono text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
          style={{ backgroundColor: `${DIFF_PALETTE[node.diffStatus]}26`, color: DIFF_PALETTE[node.diffStatus] }}
        >
          DIFF: {node.diffStatus.toUpperCase()}
        </span>
        <span className="mono text-[9px] text-zinc-400">Rev A → Rev B</span>
      </div>
      {node.diffChanges && node.diffChanges.length > 0 ? (
        <div className="space-y-1.5">
          {node.diffChanges.map((chg, i) => (
            <div key={i} className="bg-black/40 rounded-lg p-2 border border-white/[0.06] text-[10px]">
              <span className="mono text-[9px] text-zinc-400 uppercase block">{chg.field}</span>
              <div className="flex items-center justify-between gap-2 mt-0.5 mono">
                <span className="text-rose-300 line-through truncate">{chg.before}</span>
                <span className="text-zinc-500">→</span>
                <span className="text-emerald-300 font-semibold truncate">{chg.after}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-zinc-400 italic">
          {node.diffStatus === 'added'
            ? 'This element exists only in rev B.'
            : node.diffStatus === 'removed'
              ? 'This element exists only in rev A.'
              : 'No property changes between rev A and rev B.'}
        </p>
      )}
    </div>
  );

  // ------------------------------------------------------------------ calc
  if (node.kind === 'calc' && node.calcKey) {
    const c = calcByKey.get(node.calcKey);
    if (!c) return <p className="text-xs text-zinc-500">This calc is not in the current revision.</p>;
    const linked = p.elementNodes
      .filter((n) => n.kind === 'element')
      .map((el) => ({ el, link: (el.calcLinks ?? []).find((l) => l.calcKey === c.key) }))
      .filter((x): x is { el: BimNode; link: CalcLink } => x.link !== undefined);
    const byTier = new Map<string, { el: BimNode; link: CalcLink }[]>();
    for (const x of linked) (byTier.get(x.link.tier) ?? byTier.set(x.link.tier, []).get(x.link.tier)!).push(x);
    const toReview = linked.filter((x) => x.link.review === 'auto' && x.link.confidence < 0.8);
    const inputs = p.calcDependencies.filter((d) => d.target === c.key);
    const feeds = p.calcDependencies.filter((d) => d.source === c.key);
    return (
      <div className="space-y-3">
        {impactBox}
        {header}
        <div className="flex items-center gap-1 flex-wrap">
          {c.software && <Chip tone="info">{c.software}</Chip>}
          {c.elementType && <Chip>{c.elementType}</Chip>}
          <Chip>{c.pages.length > 1 ? `pp. ${c.pages[0]}–${c.pages[c.pages.length - 1]}` : `p. ${c.pages[0] ?? '–'}`}</Chip>
          {c.scanned && <Chip tone="warn">scanned · no text layer</Chip>}
          {c.frontMatter && <Chip>front matter · never mapped</Chip>}
        </div>
        <button
          type="button"
          onClick={() => p.onOpenTarget(calcTarget(c))}
          className="w-full bg-rose-500/[0.1] hover:bg-rose-500/[0.18] border border-rose-400/35 text-rose-100 rounded-lg py-1.5 text-[11px] font-medium flex items-center justify-center gap-1.5 transition"
        >
          <FileSearch className="w-3.5 h-3.5 text-rose-300" />
          Open calc pages
        </button>
        {(inputs.length > 0 || feeds.length > 0) && (
          <Section title={`Dependencies (${inputs.length + feeds.length})`} tone="text-indigo-300">
            <div className="space-y-1">
              {inputs.map((d, i) => (
                <button type="button" key={`i${i}`} onClick={() => p.onSelectCalc(d.source)} className="block w-full text-left px-2 py-1.5 rounded-lg bg-indigo-500/[0.06] hover:bg-indigo-500/[0.14] border border-indigo-400/20 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400">
                  <div className="text-[11px] text-zinc-100 truncate">
                    <span className="mono text-[9px] text-indigo-300 mr-1.5">INPUT FROM</span>
                    {calcByKey.get(d.source)?.title ?? d.source}
                  </div>
                  <p className="mono text-[9px] text-zinc-500 truncate">{d.rules.join('; ')}</p>
                </button>
              ))}
              {feeds.map((d, i) => (
                <button type="button" key={`f${i}`} onClick={() => p.onSelectCalc(d.target)} className="block w-full text-left px-2 py-1.5 rounded-lg bg-indigo-500/[0.06] hover:bg-indigo-500/[0.14] border border-indigo-400/20 cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400">
                  <div className="text-[11px] text-zinc-100 truncate">
                    <span className="mono text-[9px] text-indigo-300 mr-1.5">FEEDS</span>
                    {calcByKey.get(d.target)?.title ?? d.target}
                  </div>
                  <p className="mono text-[9px] text-zinc-500 truncate">{d.rules.join('; ')}</p>
                </button>
              ))}
            </div>
          </Section>
        )}
        <Section
          title={`Linked elements (${linked.length})`}
          tone="text-emerald-400"
          action={
            toReview.length > 0 && (
              <button
                type="button"
                disabled={!p.canWrite || p.busy}
                title={writeTitle}
                onClick={() => toReview.forEach((x) => p.onDecide(x.el.id, c.key, 'confirm'))}
                className={`${smallBtn} bg-emerald-500/15 text-emerald-200 border-emerald-400/35 hover:bg-emerald-500/25`}
              >
                <Check className="w-2.5 h-2.5" />
                Confirm {toReview.length} to review
              </button>
            )
          }
        >
          {linked.length === 0 && <p className="text-[11px] text-zinc-600 italic">No model elements matched this calc.</p>}
          <div className="space-y-2 max-h-56 overflow-y-auto pr-0.5">
            {[...byTier.entries()].map(([tier, arr]) => (
              <div key={tier}>
                <p className="mono text-[9px] text-zinc-500 uppercase mb-1">
                  {TIER_LABELS[tier] ?? tier} ({arr.length})
                </p>
                <div className="space-y-1">
                  {arr.slice(0, 30).map(({ el, link }) => (
                    <NodeRow key={el.id} node={el} onClick={() => p.onSelectNode(el.id)} right={<ConfidenceChip link={link} />} />
                  ))}
                  {arr.length > 30 && <p className="mono text-[9px] text-zinc-500">+{arr.length - 30} more</p>}
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>
    );
  }

  // ------------------------------------------------------------------ project / category / family / calc group
  if (node.kind !== 'element' && node.kind !== 'mapped-element') {
    const children =
      node.kind === 'project'
        ? p.elementNodes.filter((n) => n.kind === 'category')
        : p.elementNodes.filter((n) => n.parent === node.id);
    const els =
      node.kind === 'family'
        ? children
        : node.kind === 'category'
        ? p.elementNodes.filter((n) => n.kind === 'element' && n.categoryParent === node.id)
        : p.elementNodes.filter((n) => n.kind === 'element');
    const st = { confirmed: 0, review: 0, unmapped: 0 } as Record<MappingStatus, number>;
    els.forEach((e) => e.mappingStatus && (st[e.mappingStatus] += 1));
    return (
      <div className="space-y-3">
        {impactBox}
        {groupsCard}
        {multiCard}
        {header}
        {els.length > 0 && (
          <div className="grid grid-cols-3 gap-1.5">
            {(['confirmed', 'review', 'unmapped'] as MappingStatus[]).map((s) => (
              <div key={s} className="bg-white/[0.02] rounded-lg p-1.5 border border-white/[0.07]">
                <div className="mono text-sm font-semibold" style={{ color: STATUS_COLORS[s] }}>
                  {st[s]}
                </div>
                <div className="mono text-[8.5px] text-zinc-500 uppercase">{STATUS_LABELS[s]}</div>
              </div>
            ))}
          </div>
        )}
        <Section title={`Children (${children.length})`}>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {children.slice(0, 60).map((cn) => (
              <NodeRow key={cn.id} node={cn} right={cn.storey ?? getDisplayType(cn)} onClick={() => p.onSelectNode(cn.id)} />
            ))}
            {children.length === 0 && <p className="text-[11px] text-zinc-600 italic">No children.</p>}
          </div>
        </Section>
      </div>
    );
  }

  // ------------------------------------------------------------------ element
  const el = node.kind === 'mapped-element' && node.elementId ? nodeById.get(node.elementId) ?? node : node;
  // utilisation is shown only when a source supplied a finite value (none does yet, D8); a supplied 0 or an
  // overload is real and shown, a missing or non-finite one is not a measurement and is not drawn
  const utilPct = typeof el.utilization === 'number' && Number.isFinite(el.utilization) ? Math.round(el.utilization * 100) : null;
  const links = el.calcLinks ?? [];
  const live = links.filter((l) => l.review !== 'rejected');
  const rejected = links.filter((l) => l.review === 'rejected');
  const candidates = p.calcs.filter((c) => !c.frontMatter && !links.some((l) => l.calcKey === c.key && l.review !== 'rejected'));
  const { carriesFrom, deliversTo } = getLoadNeighbors(el.id, p.loadPath);
  const elFindings = p.findings.filter((f) => f.elementId === el.id);
  const connected = p.connectivity
    .filter((e) => e.source === el.id || e.target === el.id)
    .map((e) => ({ e, other: nodeById.get(e.source === el.id ? e.target : e.source) }))
    .filter((x): x is { e: ConnectivityEdge; other: BimNode } => Boolean(x.other));
  const params = Object.entries(el.params ?? {});
  const shownParams = showAllParams ? params : params.slice(0, 8);

  const linkCard = (l: CalcLink) => {
    const c = calcByKey.get(l.calcKey);
    return (
      <div key={l.calcKey} className={`rounded-lg p-2 border ${l.review === 'rejected' ? 'bg-white/[0.02] border-white/[0.06] opacity-70' : 'bg-rose-500/[0.06] border-rose-400/20'}`}>
        <div className="flex items-start gap-2">
          <span className="w-2 h-2 mt-1 rounded-full flex-shrink-0" style={{ backgroundColor: c?.color ?? '#71717a' }} />
          <button type="button" onClick={() => p.onSelectCalc(l.calcKey)} className="text-left text-[11px] font-medium text-zinc-100 hover:text-white flex-1 min-w-0 leading-snug">
            {c?.title ?? l.calcKey}
          </button>
          <ConfidenceChip link={l} />
        </div>
        <div className="flex items-center gap-1 flex-wrap mt-1.5 pl-4">
          <RoleChip role={l.role} />
          <TierChip tier={l.tier} />
          {l.viaGroup && (
            <Chip tone="muted" title={`Linked through its typical group: ${groupTitle(l.viaGroup)}`}>
              via typical group
            </Chip>
          )}
          {l.evidence.page != null && <Chip>p. {l.evidence.page}</Chip>}
          {c?.software && <Chip tone="info">{c.software}</Chip>}
        </div>
        <p className="text-[10px] text-zinc-400 mt-1 pl-4 leading-snug">{l.rule}</p>
        {l.caveats.length > 0 && (
          <ul className="mt-1 ml-4 space-y-0.5">
            {l.caveats.map((cv, i) => (
              <li key={i} className="text-[10px] text-amber-200/90 leading-snug flex gap-1">
                <AlertTriangle className="w-2.5 h-2.5 mt-0.5 flex-shrink-0 text-amber-300" aria-hidden="true" />
                <span>{cv}</span>
              </li>
            ))}
          </ul>
        )}
        {(l.reasons.length > 0 || l.provenance) && (
          <details className="mt-1 ml-4 group">
            <summary className="mono text-[9px] text-zinc-400 hover:text-zinc-200 cursor-pointer select-none list-none flex items-center gap-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 rounded">
              <span className="inline-block transition-transform group-open:rotate-90" aria-hidden="true">›</span>
              Why {Math.round(l.confidence * 100)}%: {l.reasons.length} evidence item{l.reasons.length === 1 ? '' : 's'}, provenance
            </summary>
            <ul className="mt-1 space-y-0.5">
              {l.reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-1.5 text-[10px] leading-snug">
                  <span className={`mono tabular-nums w-10 flex-shrink-0 text-right ${r.weight < 0 ? 'text-rose-300' : 'text-emerald-300'}`}>
                    {r.weight > 0 ? '+' : ''}
                    {r.weight.toFixed(2)}
                  </span>
                  <span className="text-zinc-300 flex-1">{r.note}</span>
                  {r.page != null && r.rects.length > 0 && (
                    <button
                      type="button"
                      onClick={() => p.onOpenTarget({ calcKey: l.calcKey, page: r.page!, rects: r.rects, caption: r.note }, el.id)}
                      className="mono text-[9px] text-indigo-300 hover:text-white underline flex-shrink-0"
                      aria-label={`Show on page ${r.page}: ${r.note}`}
                    >
                      p. {r.page}
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {(l.provenance || l.reviewProvenance) && (
              <div className="mt-1.5 pt-1.5 border-t border-white/[0.06] space-y-1">
                {l.provenance && <ProvenanceLine label="Made by" prov={l.provenance} />}
                {l.reviewProvenance && <ProvenanceLine label="Reviewed" prov={l.reviewProvenance} />}
              </div>
            )}
          </details>
        )}
        {l.evidence.snippet && (
          <p className="mono text-[9.5px] text-zinc-400 mt-1 ml-4 px-2 py-1 rounded bg-black/30 border border-white/[0.05] leading-snug">
            {l.evidence.snippet.before}
            <mark className="bg-amber-400/30 text-amber-100 rounded-sm px-0.5">{l.evidence.snippet.match}</mark>
            {l.evidence.snippet.after}
          </p>
        )}
        <div className="flex items-center gap-1 mt-1.5 pl-4 flex-wrap">
          {l.evidence.page != null && (
            <button
              type="button"
              onClick={() => p.onOpenTarget(linkTarget(l, c), el.id)}
              className={`${smallBtn} bg-rose-500/15 text-rose-100 border-rose-400/35 hover:bg-rose-500/25`}
            >
              <FileSearch className="w-2.5 h-2.5" />
              Evidence
            </button>
          )}
          {l.review === 'auto' && (
            <button
              type="button"
              disabled={!p.canWrite || p.busy}
              title={writeTitle}
              onClick={() => p.onDecide(el.id, l.calcKey, 'confirm')}
              className={`${smallBtn} bg-emerald-500/15 text-emerald-200 border-emerald-400/35 hover:bg-emerald-500/25`}
            >
              <Check className="w-2.5 h-2.5" />
              Confirm
            </button>
          )}
          {l.review !== 'rejected' && (
            <button
              type="button"
              disabled={!p.canWrite || p.busy}
              title={writeTitle}
              onClick={() => p.onDecide(el.id, l.calcKey, 'reject')}
              className={`${smallBtn} bg-white/[0.04] text-zinc-300 border-white/[0.14] hover:text-rose-200 hover:border-rose-400/40`}
            >
              <X className="w-2.5 h-2.5" />
              Reject
            </button>
          )}
          {l.review !== 'auto' && (
            <button
              type="button"
              disabled={!p.canWrite || p.busy}
              title={writeTitle ?? 'Undo the last decision on this link'}
              onClick={() => p.onDecide(el.id, l.calcKey, 'undo')}
              className={`${smallBtn} bg-white/[0.04] text-zinc-300 border-white/[0.14] hover:text-white`}
            >
              <Undo2 className="w-2.5 h-2.5" />
              Undo
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-3">
      {impactBox}
      {groupsCard}
      {multiCard}
      {header}
      {diffCard}

      {!el.isGhost && (
        <div className="grid grid-cols-2 gap-2 bg-white/[0.02] p-2.5 rounded-xl border border-white/[0.07]">
          <div>
            <span className="mono text-[9px] text-zinc-500 uppercase block">Mark</span>
            <span className="mono text-[11px] font-semibold text-zinc-100">{el.mark ?? '—'}</span>
          </div>
          <div>
            <span className="mono text-[9px] text-zinc-500 uppercase block">Section / Size</span>
            <span className="mono text-[11px] font-semibold text-cyan-300">{el.size ?? '—'}</span>
          </div>
          {el.material && (
            <div className="col-span-2">
              <span className="mono text-[9px] text-zinc-500 uppercase block">Material</span>
              <span className="text-[11px] text-zinc-200">{el.material}</span>
            </div>
          )}
          {el.typeName && (
            <div className="col-span-2">
              <span className="mono text-[9px] text-zinc-500 uppercase block">Type</span>
              <span className="text-[11px] text-zinc-200">{el.typeName}</span>
            </div>
          )}
          <div className="col-span-2">
            <span className="mono text-[9px] text-zinc-500 uppercase block">GlobalId</span>
            <span className="mono text-[10px] text-zinc-400 select-text">{el.id}</span>
          </div>
          {utilPct !== null && (
            <div className="col-span-2 pt-1 border-t border-white/[0.06]">
              <div className="flex items-center justify-between mono text-[9px] mb-1">
                <span className="text-zinc-400 uppercase">Demand / Capacity Utilization</span>
                <span style={{ color: getHeatmapColor(el.utilization) }} className="font-semibold">
                  {utilPct}%
                </span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-white/[0.07] overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, utilPct))}%`, backgroundColor: getHeatmapColor(el.utilization) }} />
              </div>
            </div>
          )}
        </div>
      )}

      {!el.isGhost && (
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            disabled={!p.canWrite || p.impactLoading}
            title={writeTitle ?? 'Everything downstream on the load path, and every calc that goes stale'}
            onClick={() => p.onImpact(el.id, 'change')}
            className="bg-amber-500/[0.1] hover:bg-amber-500/[0.18] border border-amber-400/35 text-amber-100 rounded-lg py-1.5 text-[10.5px] font-medium flex items-center justify-center gap-1.5 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {p.impactLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3 text-amber-300" />}
            Impact if changed
          </button>
          <button
            type="button"
            disabled={!p.canWrite || p.impactLoading}
            title={writeTitle ?? 'What it supported is re-framed, orphans removed, and the calcs that go stale'}
            onClick={() => p.onImpact(el.id, 'remove')}
            className="bg-rose-500/[0.1] hover:bg-rose-500/[0.18] border border-rose-400/35 text-rose-100 rounded-lg py-1.5 text-[10.5px] font-medium flex items-center justify-center gap-1.5 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <AlertTriangle className="w-3 h-3 text-rose-300" />
            Impact if removed
          </button>
        </div>
      )}

      {elFindings.map((f, i) => (
        <button
          key={i}
          type="button"
          onClick={() => p.onOpenTarget({ calcKey: f.calcKey, page: f.page, rects: f.rects, caption: `Calc size ${f.calcSize}` }, el.id)}
          className="w-full text-left rounded-xl p-2.5 border border-rose-400/40 bg-rose-500/[0.08] hover:bg-rose-500/[0.14] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
        >
          <span className="mono text-[10px] font-semibold text-rose-200 uppercase tracking-wider flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" aria-hidden="true" />
            Size mismatch
          </span>
          <span className="block mono text-[11px] mt-1">
            <span className="text-zinc-300">model {f.modelSize}</span>
            <span className="text-zinc-500"> · </span>
            <span className="text-rose-200">calc {f.calcSize}</span>
          </span>
          <span className="block text-[10px] text-zinc-400 mt-0.5 leading-snug">
            {f.note} · {calcByKey.get(f.calcKey)?.title ?? f.calcKey}, p. {f.page}
          </span>
        </button>
      ))}

      {!el.isGhost && (
        <Section
          title={
            <>
              <Calculator className="w-3 h-3" />
              Linked calcs ({live.length})
            </>
          }
          tone="text-rose-400"
          action={
            <button type="button" onClick={() => p.onShowElementCalcs(el.id)} className="mono text-[9px] text-indigo-300 hover:text-white underline">
              PDF Viewer →
            </button>
          }
        >
          <div className="space-y-1.5">
            {live.map(linkCard)}
            {live.length === 0 && (
              <p className="text-[11px] text-zinc-500 leading-snug px-2 py-1.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                No calc in the package names this element{el.mark ? ` ("${el.mark}")` : ' (it has no mark)'}, its size or its type.
              </p>
            )}
            <select
              aria-label="Link to a calc by hand"
              value=""
              disabled={!p.canWrite || p.busy || candidates.length === 0}
              title={writeTitle}
              onChange={(e) => e.target.value && p.onDecide(el.id, e.target.value, 'manual')}
              className="w-full bg-[#1e2127]/80 border border-white/[0.14] focus:border-indigo-400/50 focus:outline-none rounded-lg px-2 py-1 text-[11px] text-zinc-300 cursor-pointer disabled:opacity-40"
            >
              <option value="" className="bg-[#2d3139]">
                + Link to a calc by hand…
              </option>
              {candidates.map((c) => (
                <option key={c.key} value={c.key} className="bg-[#2d3139]">
                  {c.title}
                </option>
              ))}
            </select>
            {rejected.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <p className="mono text-[9px] text-zinc-500 uppercase">Rejected ({rejected.length})</p>
                {rejected.map(linkCard)}
              </div>
            )}
          </div>
        </Section>
      )}

      {(carriesFrom.length > 0 || deliversTo.length > 0) && (
        <Section
          title={
            <>
              <Link2 className="w-3 h-3" />
              Load path
            </>
          }
          tone="text-amber-400"
        >
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {carriesFrom.map((e, i) => {
              const n = nodeById.get(e.source);
              return n ? (
                <NodeRow
                  key={`u${i}`}
                  node={n}
                  tone="bg-amber-500/[0.06] hover:bg-amber-500/[0.14] border-amber-500/20"
                  right={
                    <span className="flex items-center gap-1 justify-end" title={e.rule}>
                      <ArrowDown className="w-2.5 h-2.5 text-amber-300" />
                      carries from
                    </span>
                  }
                  onClick={() => p.onSelectNode(n.id)}
                />
              ) : null;
            })}
            {deliversTo.map((e, i) => {
              const n = nodeById.get(e.target);
              return n ? (
                <NodeRow
                  key={`d${i}`}
                  node={n}
                  tone="bg-amber-500/[0.06] hover:bg-amber-500/[0.14] border-amber-500/20"
                  right={
                    <span className="flex items-center gap-1 justify-end" title={e.rule}>
                      <ArrowUp className="w-2.5 h-2.5 text-amber-300 rotate-180" />
                      delivers to
                    </span>
                  }
                  onClick={() => p.onSelectNode(n.id)}
                />
              ) : null;
            })}
          </div>
          {p.activeLoadChainNodeIds.size > 1 && (
            <p className="mono text-[9px] text-zinc-500 mt-1.5">{p.activeLoadChainNodeIds.size - 1} elements on the traced chain (see Trace in the filter bar)</p>
          )}
        </Section>
      )}

      {connected.length > 0 && (
        <Section title={`Physical connectivity (${connected.length})`} tone="text-cyan-400">
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {connected.map(({ e, other }, i) => (
              <NodeRow
                key={i}
                node={other}
                tone="bg-cyan-500/[0.06] hover:bg-cyan-500/[0.14] border-cyan-500/20"
                right={<span title={e.rule}>{e.kind === 'part_of' ? (e.source === el.id ? 'part of' : 'has part') : getDisplayType(other)}</span>}
                onClick={() => p.onSelectNode(other.id)}
              />
            ))}
          </div>
        </Section>
      )}

      {params.length > 0 && (
        <Section
          title={`Parameters (${params.length})`}
          action={
            params.length > 8 && (
              <button type="button" onClick={() => setShowAllParams((v) => !v)} className="mono text-[9px] text-zinc-400 hover:text-white underline">
                {showAllParams ? 'Fewer' : 'All'}
              </button>
            )
          }
        >
          <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-x-2 gap-y-1">
            {shownParams.map(([k, v]) => (
              <React.Fragment key={k}>
                <dt className="mono text-[9px] text-zinc-500 truncate" title={k}>
                  {k}
                </dt>
                <dd className="mono text-[10px] text-zinc-200 truncate" title={v}>
                  {v}
                </dd>
              </React.Fragment>
            ))}
          </dl>
        </Section>
      )}
    </div>
  );
};
