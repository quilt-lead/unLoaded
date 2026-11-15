// The calc package: the real calcs (title, software, pages, scanned / front-matter flags), or the
// selected element's linked calcs ranked by confidence; the original PDF page with the matched
// evidence highlighted; and the calc -> calc dependencies with their evidence side by side.
import React, { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Box,
  Calculator,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  FileQuestion,
  FilterX,
  PanelLeftClose,
  PanelLeftOpen,
  ScanLine,
  Search,
  Users,
} from 'lucide-react';
import type { BimNode, CalcDependency, CalcLink, CalcOrigin, CalcPackage, DiffStatus, FindingView, PdfTarget, TypicalGroupView, WorkspaceView } from '../types/bim';
import { getEffectiveNodeColor } from '../utils/colors';
import { PdfPage, unionBox } from './pdf/PdfPage';
import { EvidenceCompare } from './pdf/EvidenceCompare';
import { Chip, ConfidenceChip, DiffBadge, RoleChip, TierChip } from './ui/Chips';

interface DocumentBrowserProps {
  calcs: CalcPackage[];
  calcPackageName: string | null;
  /** URL of the calc package PDF (null when there is no calc revision) */
  /** The calc PDF (one document), or the first document's when the calcs are a set of PDFs. */
  pdfUrl: string | null;
  /** Calc sets: each calc document's PDF by docId (a calc's `docId`); a calc whose document is missing falls back to pdfUrl. */
  pdfUrls?: Record<string, string>;
  elementNodes: BimNode[];
  calcToElementIds: Map<string, string[]>;
  calcDependencies: CalcDependency[];
  groups: TypicalGroupView[];
  findings: FindingView[];
  selectedElement: BimNode | null;
  filterBySelectedElement: boolean;
  onClearElementFilter: () => void;
  target: PdfTarget | null;
  onChangeTarget: (t: PdfTarget) => void;
  diffMode: boolean;
  onLocateElement: (nodeId: string, view: WorkspaceView) => void;
  onLocateCalc: (calcKey: string) => void;
  /** select a typical group's members in the graphs and 3D */
  onSelectElements: (ids: string[]) => void;
  /** where the calcs came from: a model bundle's calcs have no PDF here, and the page pane says why */
  calcOrigin?: CalcOrigin | null;
}

const pageRange = (c: CalcPackage, origin?: CalcOrigin | null) =>
  c.pages.length === 0
    ? origin === 'bundle-demo' ? 'no PDF' : 'no pages'
    : c.pages.length > 1 ? `pp. ${c.pages[0]}–${c.pages[c.pages.length - 1]}` : `p. ${c.pages[0]}`;

const LIST_PREF = 'calcmap.docs.listOpen';
const DETAILS_PREF = 'calcmap.docs.detailsOpen';
/** A remembered layout toggle; storage can be missing or blocked, so fall back to the default. */
function readPref(key: string, fallback: boolean): boolean {
  try {
    const v = window.localStorage.getItem(key);
    return v == null ? fallback : v === '1';
  } catch {
    return fallback;
  }
}
function writePref(key: string, value: boolean) {
  try {
    window.localStorage.setItem(key, value ? '1' : '0');
  } catch {
    /* not remembered: the toggle still works for this session */
  }
}

const iconBtn =
  'w-7 h-7 rounded-lg border border-white/[0.12] bg-white/[0.03] text-zinc-400 hover:text-white hover:bg-white/[0.08] flex items-center justify-center transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap';
const locateBtn =
  'h-7 bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap';

/** The page pane when a calc has no PDF to show: what the bundle states about it, and why there is no page. */
function NoPdfNote({ calc, origin }: { calc: CalcPackage; origin: CalcOrigin }) {
  const facts = [calc.meta?.code, calc.meta?.rev, calc.meta?.date].filter(Boolean).join(' · ');
  return (
    <div className="max-w-sm text-left bg-white/[0.02] border border-dashed border-white/[0.14] rounded-xl p-3 space-y-1.5" role="note">
      <div className="flex items-center gap-2">
        <FileQuestion className="w-3.5 h-3.5 text-zinc-400 flex-shrink-0" aria-hidden="true" />
        <p className="text-[11px] text-zinc-200 leading-snug">{calc.title}</p>
      </div>
      {facts && <p className="mono text-[9.5px] text-zinc-400">{facts}</p>}
      {calc.meta?.summary && <p className="text-[11px] text-zinc-300 leading-snug">{calc.meta.summary}</p>}
      <p className="text-[10px] text-zinc-400 leading-snug pt-1 border-t border-white/[0.08]">
        {origin === 'bundle-demo' ? (
          <>
            <span className="mono uppercase tracking-wider text-amber-200">Demo data</span>: an invented calc from a demo model bundle. There is no
            PDF behind it.
          </>
        ) : (
          'This calc came from a model bundle, which names its PDF but does not carry it. Add the PDF to the project to see the page.'
        )}
      </p>
    </div>
  );
}

/**
 * Does a calc match the search? Its own text (title, software, designed type, key) or the id / label of
 * any element linked to it, so searching "B12" finds the calcs that design B12.
 */
export function calcMatchesQuery(
  c: CalcPackage,
  query: string,
  linkedElements: readonly Pick<BimNode, 'id' | 'label'>[]
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (`${c.title} ${c.software} ${c.elementType} ${c.key}`.toLowerCase().includes(q)) return true;
  return linkedElements.some((n) => n.id.toLowerCase().includes(q) || n.label.toLowerCase().includes(q));
}

/** Where to open a calc: its first region (it can start mid-page), with the title box highlighted. */
export function calcTarget(c: CalcPackage): PdfTarget {
  const first = c.regions[0];
  const page = first?.page ?? c.titleBox?.page ?? c.pages[0] ?? 1;
  return {
    calcKey: c.key,
    page,
    rects: c.titleBox && c.titleBox.page === page && !c.frontMatter ? c.titleBox.rects : [],
    caption: 'Calc title',
    region: first?.rect,
  };
}

export function linkTarget(l: CalcLink, c: CalcPackage | undefined): PdfTarget {
  return {
    calcKey: l.calcKey,
    page: l.evidence.page ?? c?.pages[0] ?? 1,
    rects: l.evidence.rects,
    caption: l.matchedText ? `Matched "${l.matchedText}"` : 'Matched text',
  };
}

export const DocumentBrowser: React.FC<DocumentBrowserProps> = ({
  calcs,
  calcPackageName,
  pdfUrl,
  pdfUrls,
  elementNodes,
  calcToElementIds,
  calcDependencies,
  selectedElement,
  filterBySelectedElement,
  onClearElementFilter,
  target,
  onChangeTarget,
  diffMode,
  onLocateElement,
  onLocateCalc,
  groups,
  findings,
  onSelectElements,
  calcOrigin,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [compareDep, setCompareDep] = useState<CalcDependency | null>(null);
  const [tabPick, setTab] = useState<'calcs' | 'groups' | 'findings'>('calcs');
  // the tablist shows only while there are groups or findings; without it, the calc list is the
  // only reachable tab, so a pick made earlier (another revision, another package) cannot strand you
  const hasTabs = groups.length > 0 || findings.length > 0;
  const tab = hasTabs ? tabPick : 'calcs';
  const calcByKey = useMemo(() => new Map(calcs.map((c) => [c.key, c])), [calcs]);
  // several calc PDFs: each row says which document it is in
  const multiDoc = useMemo(() => new Set(calcs.map((c) => c.docId)).size > 1, [calcs]);
  /** The PDF a calc's pages are pages of: its document's, else the one package's. */
  const urlOf = (calcKey: string | null | undefined): string | null => {
    const doc = calcKey ? calcByKey.get(calcKey)?.docId : null;
    return (doc && pdfUrls?.[doc]) || pdfUrl;
  };
  const nodeById = useMemo(() => new Map(elementNodes.map((n) => [n.id, n])), [elementNodes]);

  const elementLinks = filterBySelectedElement && selectedElement?.kind === 'element' ? selectedElement.calcLinks ?? [] : null;

  const linkedNodesOf = (key: string) =>
    (calcToElementIds.get(key) ?? []).map((id) => nodeById.get(id) ?? { id, label: id });
  const matchCalc = (c: CalcPackage) => calcMatchesQuery(c, searchQuery, linkedNodesOf(c.key));

  const activeCalc = target?.calcKey ? calcByKey.get(target.calcKey) ?? null : null;

  const diffBadgeOf = (key: string): DiffStatus | null => {
    if (!diffMode) return null;
    const st = (calcToElementIds.get(key) ?? []).map((id) => nodeById.get(id)?.diffStatus).filter(Boolean);
    return st.includes('modified') ? 'modified' : st.includes('added') ? 'added' : st.includes('removed') ? 'removed' : null;
  };

  const linkedElements = useMemo(() => {
    if (!activeCalc) return [];
    return (calcToElementIds.get(activeCalc.key) ?? []).map((id) => nodeById.get(id)).filter((n): n is BimNode => Boolean(n));
  }, [activeCalc, calcToElementIds, nodeById]);

  const deps = activeCalc
    ? {
        inputs: calcDependencies.filter((d) => d.target === activeCalc.key),
        feeds: calcDependencies.filter((d) => d.source === activeCalc.key),
      }
    : { inputs: [], feeds: [] };

  const depSource = (d: CalcDependency, side: 'source' | 'target') => {
    const key = side === 'source' ? d.source : d.target;
    const ev = d.evidence.find((e) => e.calcKey === key) ?? null;
    const c = calcByKey.get(key);
    const url = urlOf(key);
    if (!url || !c) return null;
    const page = ev?.page ?? c.pages[0] ?? 1;
    const rects = ev ? ev.rects : [];
    const u = unionBox(rects);
    return {
      url,
      page,
      rects,
      focus: u ? [Math.max(0, u[0] - 240), Math.max(0, u[1] - 160), u[2] + 240, u[3] + 200] : null,
      label: c.title,
      sub: ev ? `p. ${page} · "${ev.text}"` : `p. ${page}`,
    };
  };

  // layout preferences: the calc list can be hidden to give the page the full width, and the
  // dependencies / linked elements footer folded away; both are remembered per browser
  const [listOpen, setListOpenState] = useState(() => readPref(LIST_PREF, true));
  const [detailsOpen, setDetailsOpenState] = useState(() => readPref(DETAILS_PREF, true));
  const setListOpen = (v: boolean) => {
    setListOpenState(v);
    writePref(LIST_PREF, v);
  };
  const setDetailsOpen = (v: boolean) => {
    setDetailsOpenState(v);
    writePref(DETAILS_PREF, v);
  };

  const listRow = (c: CalcPackage, extra?: { link: CalcLink }) => {
    const isActive = activeCalc?.key === c.key;
    const linked = calcToElementIds.get(c.key)?.length ?? 0;
    const badge = diffBadgeOf(c.key);
    const subline = [multiDoc && c.docName ? c.docName : null, c.software || c.meta?.code || (c.frontMatter ? 'Front matter' : null)]
      .filter(Boolean)
      .join(' · ');
    return (
      <button
        type="button"
        key={c.key}
        aria-pressed={isActive}
        title={c.title}
        onClick={() => {
          setCompareDep(null);
          onChangeTarget(extra ? linkTarget(extra.link, c) : calcTarget(c));
        }}
        className={`block w-full text-left px-2.5 py-2 rounded-lg cursor-pointer transition-colors border focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap ${
          isActive ? 'bg-calcmap/15 border-calcmap/40' : 'bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.06]'
        }`}
      >
        <div className="flex items-start gap-2">
          <span className="w-2 h-2 mt-[5px] rounded-full flex-shrink-0" style={{ backgroundColor: c.color }} aria-hidden="true" />
          <span className="flex-1 min-w-0 text-xs font-semibold text-zinc-100 leading-snug line-clamp-3 break-words">{c.title}</span>
          <span className="flex flex-col items-end gap-1 flex-shrink-0">
            <span className="mono text-[9px] px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-300 whitespace-nowrap">{pageRange(c, calcOrigin)}</span>
            {badge && <DiffBadge status={badge} />}
          </span>
        </div>
        {extra ? (
          <div className="mt-1.5 pl-4 space-y-1">
            <div className="flex items-center gap-1 flex-wrap">
              <ConfidenceChip link={extra.link} />
              <RoleChip role={extra.link.role} />
              <TierChip tier={extra.link.tier} />
              {extra.link.evidence.page != null && <Chip>p. {extra.link.evidence.page}</Chip>}
            </div>
            <p className="text-[10px] text-zinc-400 leading-snug">{extra.link.rule}</p>
          </div>
        ) : (
          <div className="mt-1 pl-4 flex items-end justify-between gap-2 text-[10px] mono leading-snug">
            <span className={`min-w-0 line-clamp-2 break-words ${subline ? 'text-zinc-400' : 'text-zinc-500 italic'}`}>
              {subline || 'No software named'}
            </span>
            <span className="flex items-center gap-1 flex-shrink-0">
              {c.scanned && <Chip tone="warn" title="No text layer: nothing could be read">scanned</Chip>}
              {c.frontMatter && <Chip title="Front matter / contents: never mapped">front</Chip>}
              {!c.frontMatter && (
                <span className={linked ? 'text-zinc-300' : 'text-zinc-500'} title={`${linked} linked element${linked === 1 ? '' : 's'}`}>
                  {linked} linked
                </span>
              )}
            </span>
          </div>
        )}
      </button>
    );
  };

  const filteredCalcs = calcs.filter(matchCalc);
  const filteredLinks = (elementLinks ?? []).filter((l) => {
    const c = calcByKey.get(l.calcKey);
    return c && matchCalc(c);
  });

  const targetUrl = target ? urlOf(target.calcKey) : null;
  const pdfSource =
    targetUrl && target
      ? {
          url: targetUrl,
          page: target.page,
          rects: target.rects,
          regions: target.region ? [target.region] : [],
          focus: (() => {
            const u = unionBox(target.rects);
            if (u) return [Math.max(0, u[0] - 160), Math.max(0, u[1] - 110), u[2] + 160, u[3] + 130];
            return target.region ?? null;
          })(),
        }
      : null;

  // step through the calc's regions (a calc can start or end mid-page)
  const regions = activeCalc?.regions ?? [];
  const regionIdx = target ? regions.findIndex((r) => r.page === target.page && (!target.region || r.rect.join() === target.region.join())) : -1;
  const goRegion = (i: number) => {
    const r = regions[i];
    if (!activeCalc || !r) return;
    onChangeTarget({ calcKey: activeCalc.key, page: r.page, rects: target && target.page === r.page ? target.rects : [], region: r.rect, caption: target?.caption });
  };

  const depCount = deps.inputs.length + deps.feeds.length;
  const hasDetails = depCount > 0 || linkedElements.length > 0;
  const listCount = elementLinks ? filteredLinks.length : tab === 'calcs' ? filteredCalcs.length : null;

  const showListButton = !listOpen && (
    <button
      type="button"
      onClick={() => setListOpen(true)}
      aria-label="Show the calc list"
      title="Show the calc list"
      className={`${iconBtn} flex-shrink-0`}
    >
      <PanelLeftOpen className="w-3.5 h-3.5" aria-hidden="true" />
    </button>
  );

  return (
    <section className="w-full h-full overflow-hidden flex flex-col min-[900px]:flex-row bg-[#24272d]" aria-label="PDF calcs">
      {listOpen && (
        <aside
          aria-label="Calc list"
          className="flex flex-col min-h-0 max-h-[42vh] min-[900px]:max-h-none w-full min-[900px]:w-[300px] xl:w-[340px] flex-shrink-0 border-b min-[900px]:border-b-0 min-[900px]:border-r border-white/[0.12] bg-[#262a32]"
        >
          <div className="px-3 pt-2.5 pb-2 space-y-2 border-b border-white/[0.08] flex-shrink-0">
            <div className="flex items-start gap-2">
              <div className="min-w-0 flex-1">
                <h2 className="text-xs font-semibold text-white leading-snug break-words">
                  {elementLinks && selectedElement ? `Calcs linked to ${selectedElement.label}` : calcPackageName ?? 'Calc package'}
                </h2>
                <p className="mono text-[9.5px] text-zinc-500 mt-0.5 uppercase tracking-wide">
                  {elementLinks
                    ? `${elementLinks.length} link${elementLinks.length === 1 ? '' : 's'} · ranked by confidence`
                    : `${calcs.length} calculation${calcs.length === 1 ? '' : 's'}${
                        calcOrigin === 'bundle-demo' ? ' · demo data, no PDF' : calcOrigin === 'bundle-pdf' ? ' · PDF not included' : ''
                      }`}
                </p>
              </div>
              <button type="button" onClick={() => setListOpen(false)} aria-label="Hide the calc list" title="Hide the calc list" className={`${iconBtn} flex-shrink-0`}>
                <PanelLeftClose className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>

            <div className="flex items-center gap-1.5">
              <div className="relative flex-1 min-w-0">
                <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
                <input
                  type="search"
                  aria-label="Search PDF calculations"
                  autoComplete="off"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search calcs, software, members…"
                  className="w-full bg-[#1e2127]/80 border border-white/[0.16] focus:border-calcmap/50 focus:outline-none rounded-lg pl-8 pr-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 transition"
                />
              </div>
              {elementLinks && (
                <button
                  type="button"
                  onClick={onClearElementFilter}
                  title="Show every calc, not only the ones linked to the selected element"
                  className="bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-400/30 px-2 py-1.5 rounded-lg text-[11px] font-medium transition flex items-center gap-1 flex-shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                >
                  <FilterX className="w-3.5 h-3.5" aria-hidden="true" />
                  All
                </button>
              )}
            </div>

            {!elementLinks && hasTabs && (
              <div role="tablist" aria-label="Calc package lists" className="flex items-center gap-0.5 bg-[#1e2127]/80 p-0.5 rounded-lg border border-white/[0.12]">
                {(
                  [
                    { id: 'calcs', label: 'Calcs', n: calcs.length },
                    { id: 'groups', label: 'Groups', n: groups.length },
                    { id: 'findings', label: 'Findings', n: findings.length },
                  ] as const
                ).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    role="tab"
                    aria-selected={tab === t.id}
                    onClick={() => setTab(t.id)}
                    title={t.id === 'groups' ? 'Typical groups' : undefined}
                    className={`flex-1 mono text-[10px] px-1.5 py-1 rounded-md transition-colors whitespace-nowrap focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap ${
                      tab === t.id ? 'bg-calcmap/15 text-calcmap border border-calcmap/40' : 'text-zinc-400 hover:text-zinc-200 border border-transparent'
                    } ${t.id === 'findings' && findings.length > 0 && tab !== t.id ? 'text-rose-300' : ''}`}
                  >
                    {t.label} <span className="tabular-nums opacity-80">{t.n}</span>
                  </button>
                ))}
              </div>
            )}
            {searchQuery.trim() && listCount != null && (
              <p className="mono text-[9.5px] text-zinc-500" role="status">
                {listCount} match{listCount === 1 ? '' : 'es'}
              </p>
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1.5">
            {!elementLinks && tab === 'groups' ? (
              groups.length === 0 ? (
                <p className="text-[11px] text-zinc-500 text-center py-8">No typical groups: no calc designs elements by size only.</p>
              ) : (
                groups.map((g) => (
                  <div key={g.id} className="px-2.5 py-2 rounded-lg border bg-white/[0.02] border-white/[0.06]">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-zinc-100 leading-snug break-words">{g.title}</p>
                        <p className="mono text-[10px] text-zinc-500 mt-0.5">
                          {g.category} · {g.storey || 'no storey'} · {g.profile}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => onSelectElements(g.members)}
                        className="mono text-[9px] px-1.5 py-0.5 rounded border border-white/[0.14] text-zinc-300 hover:text-white hover:border-calcmap/40 flex items-center gap-1 flex-shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                        title="Select the members in the graph and 3D"
                      >
                        <Users className="w-2.5 h-2.5" aria-hidden="true" />
                        {g.members.length}
                      </button>
                    </div>
                    <ul className="mt-1.5 space-y-1">
                      {g.links.map((gl) => {
                        const c = calcByKey.get(gl.calcKey);
                        return (
                          <li key={gl.calcKey}>
                            <button
                              type="button"
                              onClick={() => {
                                setCompareDep(null);
                                onChangeTarget({ calcKey: gl.calcKey, page: gl.page ?? c?.pages[0] ?? 1, rects: gl.rects, caption: `Typical size ${g.profile}` });
                              }}
                              className="w-full text-left flex items-start gap-1.5 px-2 py-1 rounded-md bg-black/20 hover:bg-black/35 border border-white/[0.05] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                            >
                              <span className="w-1.5 h-1.5 mt-[5px] rounded-full flex-shrink-0" style={{ backgroundColor: c?.color ?? '#71717a' }} aria-hidden="true" />
                              <span className="text-[11px] text-zinc-200 leading-snug line-clamp-2 flex-1 min-w-0">{c?.title ?? gl.calcKey}</span>
                              <Chip tone={gl.band === 'high' ? 'good' : gl.band === 'medium' ? 'warn' : 'bad'}>{Math.round(gl.confidence * 100)}%</Chip>
                              <RoleChip role={gl.role} />
                            </button>
                            {gl.caveats.length > 0 && <p className="text-[10px] text-amber-200/90 mt-0.5 pl-2">{gl.caveats.join(' · ')}</p>}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))
              )
            ) : !elementLinks && tab === 'findings' ? (
              findings.length === 0 ? (
                <p className="text-[11px] text-zinc-500 text-center py-8">No findings: every calc that sizes an element agrees with the model's size.</p>
              ) : (
                findings.map((f, i) => {
                  const el = nodeById.get(f.elementId);
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        setCompareDep(null);
                        onChangeTarget({ calcKey: f.calcKey, page: f.page, rects: f.rects, caption: `Calc size ${f.calcSize} (model ${f.modelSize})` });
                        onSelectElements([f.elementId]);
                      }}
                      className="block w-full text-left px-2.5 py-2 rounded-lg border bg-rose-500/[0.06] hover:bg-rose-500/[0.12] border-rose-400/25 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-zinc-100 flex items-center gap-1.5 min-w-0">
                          <AlertTriangle className="w-3 h-3 text-rose-300 flex-shrink-0" aria-hidden="true" />
                          <span className="truncate">{el?.label ?? f.elementId}</span>
                          {el?.storey && <span className="mono text-[10px] text-zinc-500 font-normal">{el.storey}</span>}
                        </span>
                        <span className="mono text-[10px] text-rose-200 flex-shrink-0">
                          {f.modelSize} ≠ {f.calcSize}
                        </span>
                      </span>
                      <span className="block text-[10px] text-zinc-400 mt-1 leading-snug">{f.note}</span>
                      <span className="block mono text-[9px] text-zinc-500 mt-0.5 line-clamp-2">
                        {calcByKey.get(f.calcKey)?.title ?? f.calcKey} · p. {f.page}
                      </span>
                    </button>
                  );
                })
              )
            ) : elementLinks ? (
              filteredLinks.length === 0 ? (
                <div className="text-center py-12 px-3 text-zinc-500">
                  <FileQuestion className="w-8 h-8 mx-auto mb-2 text-zinc-600" aria-hidden="true" />
                  <p className="text-xs font-medium text-zinc-300">No calc names this element</p>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    Nothing in the package mentions {selectedElement?.mark ? `"${selectedElement.mark}"` : 'it (it has no mark)'}, its size or its type.
                  </p>
                </div>
              ) : (
                filteredLinks.map((l) => listRow(calcByKey.get(l.calcKey)!, { link: l }))
              )
            ) : filteredCalcs.length === 0 ? (
              <div className="text-center py-12 px-3 text-zinc-500">
                <FileQuestion className="w-8 h-8 mx-auto mb-2 text-zinc-600" aria-hidden="true" />
                <p className="text-xs font-medium text-zinc-300">{calcs.length ? 'No matching calculations' : 'No calc package loaded'}</p>
                <p className="text-[11px] text-zinc-500 mt-1">
                  {calcs.length
                    ? 'Try clearing the search.'
                    : elementNodes.length
                    ? 'This model has no calc package yet. Upload a calc package PDF to map it.'
                    : 'Import a model and upload a calc package PDF, or load the sample.'}
                </p>
              </div>
            ) : (
              filteredCalcs.map((c) => listRow(c))
            )}
          </div>
        </aside>
      )}

      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        {compareDep ? (
          <div className="flex-1 min-h-0 flex flex-col gap-2 p-2">
            {showListButton && <div>{showListButton}</div>}
            <EvidenceCompare
              left={depSource(compareDep, 'source')}
              right={depSource(compareDep, 'target')}
              leftTitle={`Output · ${calcByKey.get(compareDep.source)?.title ?? compareDep.source}`}
              rightTitle={`Input · ${calcByKey.get(compareDep.target)?.title ?? compareDep.target}`}
              note={compareDep.rules.join(' · ')}
              onClose={() => setCompareDep(null)}
            />
          </div>
        ) : !activeCalc || !target ? (
          <div className="flex-1 flex flex-col">
            {showListButton && <div className="p-2">{showListButton}</div>}
            <div className="flex-1 flex items-center justify-center text-zinc-500 text-xs text-center px-6">
              {calcs.length ? 'Pick a calculation or a link on the left to open its original page.' : 'No calc package loaded yet.'}
            </div>
          </div>
        ) : (
          <>
            {/* one toolbar row: which calc, where in it, and where else to see it */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2.5 py-1.5 bg-[#2d3139] border-b border-white/[0.12] flex-shrink-0">
              {showListButton}
              {calcOrigin === 'bundle-demo' ? (
                <span
                  className="px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-400/40 text-amber-200 mono text-[9px] font-semibold flex-shrink-0"
                  title="Invented calc from a demo model bundle: no PDF behind it"
                >
                  DEMO
                </span>
              ) : (
                <span className="px-1.5 py-0.5 rounded bg-rose-500/15 border border-rose-400/30 text-rose-300 mono text-[9px] font-semibold flex-shrink-0">PDF</span>
              )}
              <h3 className="text-xs font-semibold text-white truncate min-w-0 max-w-full flex-shrink" title={activeCalc.title}>
                {activeCalc.title}
              </h3>
              <div className="flex items-center gap-1.5 flex-wrap">
                {activeCalc.software && <Chip tone="info">{activeCalc.software}</Chip>}
                {activeCalc.elementType && <Chip>{activeCalc.elementType}</Chip>}
                {activeCalc.scanned && (
                  <Chip tone="warn" title="These pages have no text layer, so nothing could be read from them">
                    <ScanLine className="w-2.5 h-2.5 inline -mt-px mr-0.5" aria-hidden="true" />
                    scanned
                  </Chip>
                )}
                {activeCalc.frontMatter && <Chip>front matter</Chip>}
                {regions.length > 0 ? (
                  <span className="flex items-center gap-1" role="group" aria-label="Calc regions">
                    <button
                      type="button"
                      onClick={() => goRegion(Math.max(0, regionIdx - 1))}
                      disabled={regionIdx <= 0}
                      aria-label="Previous region"
                      className="w-5 h-5 rounded border border-white/[0.1] text-zinc-300 hover:text-white flex items-center justify-center disabled:opacity-30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                    >
                      <ChevronLeft className="w-3 h-3" aria-hidden="true" />
                    </button>
                    <span className="mono text-[9.5px] text-zinc-400 tabular-nums whitespace-nowrap">
                      {regions.length > 1 && <>Region {regionIdx >= 0 ? regionIdx + 1 : '–'}/{regions.length} · </>}p. {target.page}
                    </span>
                    <button
                      type="button"
                      onClick={() => goRegion(Math.min(regions.length - 1, regionIdx + 1))}
                      disabled={regionIdx >= regions.length - 1}
                      aria-label="Next region"
                      className="w-5 h-5 rounded border border-white/[0.1] text-zinc-300 hover:text-white flex items-center justify-center disabled:opacity-30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                    >
                      <ChevronRight className="w-3 h-3" aria-hidden="true" />
                    </button>
                  </span>
                ) : (
                  activeCalc.pages.length > 0 && (
                    <span className="flex items-center gap-1" role="group" aria-label="Pages">
                      <span className="mono text-[9px] text-zinc-500">Pages</span>
                      {activeCalc.pages.map((p) => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => onChangeTarget({ calcKey: activeCalc.key, page: p, rects: p === target.page ? target.rects : [] })}
                          aria-pressed={p === target.page}
                          className={`mono text-[9px] px-1.5 py-0.5 rounded border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap ${
                            p === target.page
                              ? 'bg-calcmap/15 text-calcmap border-calcmap/45 font-semibold'
                              : 'bg-white/[0.03] text-zinc-400 border-white/[0.08] hover:text-zinc-200'
                          }`}
                        >
                          {p}
                        </button>
                      ))}
                    </span>
                  )
                )}
                {target.rects.length > 0 && (
                  <span className="hidden lg:flex items-center gap-1 mono text-[9.5px] text-amber-200/90 min-w-0" title={`${target.caption ?? 'Evidence'} highlighted on the page`}>
                    <span className="w-2 h-2 rounded-sm bg-amber-300/70 border border-amber-500 flex-shrink-0" aria-hidden="true" />
                    <span className="truncate max-w-[16rem]">{target.caption ?? 'Evidence'}</span>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1 ml-auto flex-shrink-0">
                <button type="button" onClick={() => onLocateCalc(activeCalc.key)} className={locateBtn} title="Show this calc in the Calculation Graph">
                  <Calculator className="w-3 h-3 text-amber-400" aria-hidden="true" />
                  <span className="hidden xl:inline">Calc Graph</span>
                  <span className="sr-only xl:hidden">Calculation Graph</span>
                </button>
                {linkedElements[0] && (
                  <>
                    <button
                      type="button"
                      onClick={() => onLocateElement(linkedElements[0].id, 'element-graph')}
                      className={locateBtn}
                      title={`Show ${linkedElements[0].label} in the Element Graph`}
                    >
                      <CircleDot className="w-3 h-3 text-emerald-400" aria-hidden="true" />
                      <span className="hidden xl:inline">Element Graph</span>
                      <span className="sr-only xl:hidden">Element Graph</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => onLocateElement(linkedElements[0].id, '3d')}
                      className={locateBtn}
                      title={`Show ${linkedElements[0].label} in the 3D model`}
                    >
                      <Box className="w-3 h-3 text-cyan-400" aria-hidden="true" />
                      <span>3D</span>
                    </button>
                  </>
                )}
              </div>
            </div>

            <div className="flex-1 min-h-[300px] min-w-0">
              <PdfPage
                bare
                source={pdfSource}
                emptyText={
                  calcOrigin && calcOrigin !== 'pdf' ? (
                    <NoPdfNote calc={activeCalc} origin={calcOrigin} />
                  ) : (
                    'The calc package PDF is not available here (an export JSON carries no PDF; open the project file instead).'
                  )
                }
              />
            </div>

            {hasDetails && (
              <div className="flex-shrink-0 border-t border-white/[0.12] bg-[#262a32]">
                <button
                  type="button"
                  onClick={() => setDetailsOpen(!detailsOpen)}
                  aria-expanded={detailsOpen}
                  aria-controls="calc-details"
                  className="w-full flex items-center gap-3 px-3 py-1.5 text-left mono text-[9.5px] uppercase tracking-wider text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] transition focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-calcmap"
                >
                  {depCount > 0 && (
                    <span>
                      Calc dependencies <span className="text-zinc-200 tabular-nums">{depCount}</span>
                    </span>
                  )}
                  {linkedElements.length > 0 && (
                    <span>
                      Linked elements <span className="text-zinc-200 tabular-nums">{linkedElements.length}</span>
                    </span>
                  )}
                  <ChevronDown className={`w-3.5 h-3.5 ml-auto transition-transform ${detailsOpen ? '' : 'rotate-180'}`} aria-hidden="true" />
                  <span className="sr-only">{detailsOpen ? 'Hide' : 'Show'} details</span>
                </button>
                {detailsOpen && (
                  <div id="calc-details" className="grid grid-cols-1 md:grid-cols-2 gap-2 px-2 pb-2 max-h-36 overflow-y-auto">
                    {depCount > 0 && (
                      <div className="space-y-1">
                        {[...deps.inputs.map((d) => ({ d, dir: 'in' as const })), ...deps.feeds.map((d) => ({ d, dir: 'out' as const }))].map(({ d, dir }, i) => {
                          const other = calcByKey.get(dir === 'in' ? d.source : d.target);
                          return (
                            <button
                              key={i}
                              type="button"
                              onClick={() => setCompareDep(d)}
                              title="Compare the evidence on both pages"
                              className="w-full text-left flex items-center gap-2 bg-calcmap/[0.06] hover:bg-calcmap/[0.14] border border-calcmap/20 rounded-md px-2 py-1 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                            >
                              <span className="mono text-[9px] text-calcmap flex-shrink-0 w-14">{dir === 'in' ? 'Input from' : 'Feeds'}</span>
                              <ArrowRight className={`w-3 h-3 text-calcmap flex-shrink-0 ${dir === 'in' ? 'rotate-180' : ''}`} aria-hidden="true" />
                              <span className="text-[11px] text-zinc-100 truncate">{other?.title ?? (dir === 'in' ? d.source : d.target)}</span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {linkedElements.length > 0 && (
                      <div className={`flex flex-wrap content-start gap-1 ${depCount === 0 ? 'md:col-span-2' : ''}`}>
                        {linkedElements.slice(0, 60).map((el) => (
                          <button
                            key={el.id}
                            type="button"
                            onClick={() => onLocateElement(el.id, 'element-graph')}
                            className="mono text-[10px] px-2 py-0.5 rounded-md bg-white/[0.04] hover:bg-calcmap/20 text-zinc-200 border border-white/[0.12] hover:border-calcmap/40 transition flex items-center gap-1.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap"
                          >
                            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: getEffectiveNodeColor(el, 'type') }} aria-hidden="true" />
                            {el.label}
                            {el.storey && <span className="text-zinc-500">{el.storey}</span>}
                          </button>
                        ))}
                        {linkedElements.length > 60 && <span className="mono text-[10px] text-zinc-500 self-center">+{linkedElements.length - 60} more</span>}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
};
