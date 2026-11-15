// The calc package: the real calcs (title, software, pages, scanned / front-matter flags), or the
// selected element's linked calcs ranked by confidence; the original PDF page with the matched
// evidence highlighted; and the calc -> calc dependencies with their evidence side by side.
import React, { useMemo, useState } from 'react';
import { AlertTriangle, ArrowRight, Box, Calculator, ChevronLeft, ChevronRight, CircleDot, FileQuestion, FilterX, FolderOpen, ScanLine, Search, Users } from 'lucide-react';
import type { BimNode, CalcDependency, CalcLink, CalcPackage, DiffStatus, FindingView, PdfTarget, TypicalGroupView, WorkspaceView } from '../types/bim';
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
}

const pageRange = (c: CalcPackage) =>
  c.pages.length === 0 ? 'no pages' : c.pages.length > 1 ? `pp. ${c.pages[0]}–${c.pages[c.pages.length - 1]}` : `p. ${c.pages[0]}`;

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

  const listRow = (c: CalcPackage, extra?: { link: CalcLink }) => {
    const isActive = activeCalc?.key === c.key;
    const linked = calcToElementIds.get(c.key)?.length ?? 0;
    const badge = diffBadgeOf(c.key);
    return (
      <button
        type="button"
        key={c.key}
        aria-pressed={isActive}
        onClick={() => {
          setCompareDep(null);
          onChangeTarget(extra ? linkTarget(extra.link, c) : calcTarget(c));
        }}
        className={`block w-full text-left p-3 rounded-xl cursor-pointer transition-colors border focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 ${
          isActive
            ? 'bg-indigo-500/15 border-indigo-400/40 shadow-[0_0_20px_rgba(99,102,241,0.15)]'
            : 'bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.06]'
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: c.color }} />
            <span className="text-xs font-semibold text-zinc-100 truncate">{c.title}</span>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            {badge && <DiffBadge status={badge} />}
            <span className="mono text-[9px] px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-300">{pageRange(c)}</span>
          </div>
        </div>
        {extra ? (
          <div className="mt-2 space-y-1.5">
            <div className="flex items-center gap-1 flex-wrap">
              <ConfidenceChip link={extra.link} />
              <RoleChip role={extra.link.role} />
              <TierChip tier={extra.link.tier} />
              {extra.link.evidence.page != null && <Chip>p. {extra.link.evidence.page}</Chip>}
            </div>
            <p className="text-[10px] text-zinc-400 leading-snug">{extra.link.rule}</p>
          </div>
        ) : (
          <div className="flex items-center justify-between mt-2 text-[10px] mono text-zinc-400 gap-2">
            <span className="truncate">
              {multiDoc && c.docName && <span className="text-rose-300/80" title="Calc document (PDF)">{c.docName} · </span>}
              {c.software || (c.frontMatter ? 'Front matter' : 'No software named')}
            </span>
            <span className="flex items-center gap-1 flex-shrink-0">
              {c.scanned && <Chip tone="warn" title="No text layer: nothing could be read">scanned</Chip>}
              {c.frontMatter && <Chip title="Front matter / contents: never mapped">front</Chip>}
              {!c.frontMatter && <span className="text-zinc-300">{linked} linked</span>}
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

  return (
    <section className="w-full h-full overflow-hidden flex flex-col bg-[#282c34]/95">
      <div className="px-6 py-3.5 border-b border-white/[0.12] bg-[#2d3139]/92 flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-400/30 text-amber-400 flex items-center justify-center flex-shrink-0">
            <FolderOpen className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-semibold text-white tracking-tight flex items-center gap-2">
              <span className="truncate">
                {elementLinks && selectedElement ? `Calcs linked to ${selectedElement.label}` : calcPackageName ?? 'Calc package'}
              </span>
              {elementLinks && selectedElement && (
                <span className="mono text-[10px] px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-400/30 flex-shrink-0">
                  {elementLinks.length} link{elementLinks.length === 1 ? '' : 's'} · ranked by confidence
                </span>
              )}
            </h2>
            <p className="mono text-[10px] text-zinc-500 mt-0.5">
              {calcs.length} CALCULATIONS • ORIGINAL PAGES • MATCHED EVIDENCE HIGHLIGHTED
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          {elementLinks && (
            <button
              type="button"
              onClick={onClearElementFilter}
              className="bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-400/30 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5"
            >
              <FilterX className="w-3.5 h-3.5" />
              <span>All calcs</span>
            </button>
          )}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              aria-label="Search PDF calculations"
              autoComplete="off"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search PDFs, codes, members…"
              className="bg-[#1e2127]/80 border border-white/[0.16] focus:border-calcmap/50 focus:outline-none rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 w-64 transition"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 min-[900px]:grid-cols-12 overflow-hidden min-h-0">
        {/* Document List */}
        <div className="min-w-0 min-h-0 min-[900px]:col-span-5 min-[1280px]:col-span-4 border-r border-white/[0.12] overflow-y-auto p-4 space-y-2 bg-[#262a32]">
          {filteredDocs.length === 0 ? (
            <div className="text-center py-12 text-zinc-500">
              <FileQuestion className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
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
            filteredDocs.map((doc) => {
              const isActive = activeDoc?.id === doc.id;
              return (
                <button
                  key={doc.id}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => {
                    setSelectedDocId(doc.id);
                    setSelectedRevision(null);
                  }}
                  className={`block w-full text-left p-3 rounded-xl cursor-pointer transition border focus-visible:outline focus-visible:outline-2 focus-visible:outline-calcmap ${
                    isActive
                      ? 'bg-calcmap/15 border-calcmap/40'
                      : 'bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.06]'
                  }`}
                >
                  {(() => {
                    const statuses = doc.mappedElementIds
                      .map((eid) => nodeMap.get(eid)?.diffStatus)
                      .filter((s): s is DiffStatus => Boolean(s) && s !== 'unchanged');
                    const topStatus: DiffStatus | null = statuses.includes('modified')
                      ? 'modified'
                      : statuses.includes('added')
                      ? 'added'
                      : statuses.includes('removed')
                      ? 'removed'
                      : null;
                    return (
                      <span className="flex items-start justify-between gap-2">
                        <span className="flex items-center gap-2 min-w-0">
                          <FileText className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                          <span className="text-xs font-semibold text-zinc-100 truncate">{doc.title}</span>
                        </span>
                        <span className="flex items-center gap-1 flex-shrink-0">
                          {diffMode && topStatus && (
                            <span
                              className="mono text-[8.5px] font-bold px-1.5 py-0.5 rounded uppercase"
                              style={{
                                backgroundColor: `${DIFF_PALETTE[topStatus]}26`,
                                color: DIFF_PALETTE[topStatus],
                              }}
                            >
                              {topStatus}
                            </span>
                          )}
                          <span className="mono text-[9px] px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-300">
                            {doc.rev}
                          </span>
                        </span>
                      </span>
                    );
                  })()}
                  <span className="flex items-center justify-between mt-2 text-[10px] mono text-zinc-400">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: doc.nodeColor }} />
                      <span className="text-zinc-300">
                        {doc.mappedElementIds.length > 1
                          ? `${doc.mappedElementIds.length} Mapped Elements`
                          : doc.nodeLabel}
                      </span>
                    </span>
                    <span>
                      {doc.type} • {doc.pages}p
                    </span>
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Document Preview & Revision Selector */}
        <div className="min-w-0 min-h-0 min-[900px]:col-span-7 min-[1280px]:col-span-8 overflow-y-auto p-4 bg-[#252729] flex flex-col">
          {!activeDoc || !activeRevision ? (
            <div className="flex-1 flex items-center justify-center text-zinc-600 text-xs">
              Select a calculation PDF from the left panel to preview its engineering sheet.
            </div>
          ) : (
            <>
              <div className="bg-[#2d3139] border border-white/[0.14] rounded-xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 flex-shrink-0">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded bg-rose-500/15 border border-rose-400/30 text-rose-300 mono text-[9px] font-semibold">PDF</span>
                    <span className="text-xs font-semibold text-white truncate">{activeCalc.title}</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    {activeCalc.software && <Chip tone="info">{activeCalc.software}</Chip>}
                    {activeCalc.elementType && <Chip>{activeCalc.elementType}</Chip>}
                    {activeCalc.scanned && (
                      <Chip tone="warn" title="These pages have no text layer, so nothing could be read from them">
                        <ScanLine className="w-2.5 h-2.5 inline -mt-px mr-0.5" />
                        scanned
                      </Chip>
                    )}
                    {activeCalc.frontMatter && <Chip>front matter</Chip>}
                    {regions.length > 0 ? (
                      <span className="flex items-center gap-1 ml-1" role="group" aria-label="Calc regions">
                        <button
                          type="button"
                          onClick={() => goRegion(Math.max(0, regionIdx - 1))}
                          disabled={regionIdx <= 0}
                          aria-label="Previous region"
                          className="w-5 h-5 rounded border border-white/[0.1] text-zinc-300 hover:text-white flex items-center justify-center disabled:opacity-30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                        >
                          <ChevronLeft className="w-3 h-3" aria-hidden="true" />
                        </button>
                        <span className="mono text-[9px] text-zinc-400 tabular-nums">
                          Region {regionIdx >= 0 ? regionIdx + 1 : '–'} / {regions.length} · p. {target.page}
                        </span>
                        <button
                          type="button"
                          onClick={() => goRegion(Math.min(regions.length - 1, regionIdx + 1))}
                          disabled={regionIdx >= regions.length - 1}
                          aria-label="Next region"
                          className="w-5 h-5 rounded border border-white/[0.1] text-zinc-300 hover:text-white flex items-center justify-center disabled:opacity-30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                        >
                          <ChevronRight className="w-3 h-3" aria-hidden="true" />
                        </button>
                      </span>
                    ) : (
                      <>
                        <span className="mono text-[9px] text-zinc-500 ml-1">Pages</span>
                        {activeCalc.pages.map((p) => (
                          <button
                            key={p}
                            type="button"
                            onClick={() => onChangeTarget({ calcKey: activeCalc.key, page: p, rects: p === target.page ? target.rects : [] })}
                            aria-pressed={p === target.page}
                            className={`mono text-[9px] px-1.5 py-0.5 rounded border transition-colors ${
                              p === target.page
                                ? 'bg-indigo-500/25 text-indigo-200 border-indigo-400/45 font-semibold'
                                : 'bg-white/[0.03] text-zinc-400 border-white/[0.08] hover:text-zinc-200'
                            }`}
                          >
                            {p}
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => onLocateCalc(activeCalc.key)}
                    className="bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5"
                  >
                    <Calculator className="w-3 h-3 text-amber-400" />
                    Calc Graph
                  </button>
                  {linkedElements[0] && (
                    <>
                      <button
                        type="button"
                        onClick={() => onLocateElement(linkedElements[0].id, 'element-graph')}
                        className="bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5"
                      >
                        <CircleDot className="w-3 h-3 text-emerald-400" />
                        Element Graph
                      </button>
                      <button
                        type="button"
                        onClick={() => onLocateElement(linkedElements[0].id, '3d')}
                        className="bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5"
                      >
                        <Box className="w-3 h-3 text-cyan-400" />
                        3D
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* PDF Version / Revision Tabs */}
              {revisions.length > 0 && (
                <div className="px-5 py-2 border-b border-white/[0.08] bg-[#1e2127]/60 flex items-center justify-between gap-2">
                  <span className="mono text-[10px] text-zinc-400 flex items-center gap-1.5">
                    <History className="w-3 h-3 text-calcmap" />
                    PDF Versions ({revisions.length}):
                  </span>
                  <div className="flex items-center gap-1.5">
                    {revisions.map((r) => {
                      const isCurr = r.rev === activeRevision.rev;
                      return (
                        <button
                          key={r.rev}
                          type="button"
                          onClick={() => setSelectedRevision({ docId: activeDoc.id, rev: r.rev })}
                          aria-pressed={isCurr}
                          className={`mono text-[10px] px-2.5 py-0.5 rounded-md border transition ${
                            isCurr
                              ? 'bg-calcmap/15 text-calcmap border-calcmap/45 font-semibold'
                              : 'bg-white/[0.03] text-zinc-400 border-white/[0.08] hover:text-zinc-200'
                          }`}
                        >
                          {r.rev} ({r.date})
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="p-6 space-y-5">
                <div className="border border-white/[0.14] rounded-xl p-5 bg-[#05070c] relative overflow-hidden">
                  <div className="flex items-start justify-between gap-4 border-b border-white/[0.12] pb-4">
                    <div>
                      <p className="mono text-[10px] text-calcmap uppercase tracking-widest mb-1">
                        {activeDoc.type} // {activeDoc.code}
                      </p>
                      <h3 className="text-base font-bold text-white tracking-tight">{activeDoc.title}</h3>
                    </div>
                    <div className="text-right mono text-[10px] text-zinc-400 flex-shrink-0">
                      <div className="px-2 py-1 rounded bg-white/[0.04] border border-white/[0.12] text-zinc-200 font-semibold">
                        {activeRevision.rev}
                      </div>
                      <div className="mt-1 text-zinc-500">Issued {activeRevision.date}</div>
                    </div>
                  </div>

                  <div className="py-4 border-b border-white/[0.12]">
                    <span className="mono text-[9px] text-zinc-500 uppercase block mb-2">
                      Mapped Structural Elements ({mappedElements.length})
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {mappedElements.map((el) => (
                        <button
                          key={el.id}
                          type="button"
                          onClick={() => onLocateElement(el.id, 'element-graph')}
                          className="mono text-[10px] px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-calcmap/20 text-zinc-200 border border-white/[0.12] hover:border-calcmap/40 transition flex items-center gap-1.5"
                        >
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: activeDoc.nodeColor }} />
                          <span>{el.label}</span>
                          {el.sectionSize && <span className="text-zinc-500">({el.sectionSize})</span>}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="pt-4">
                    <p className="mono text-[10px] text-zinc-400 uppercase tracking-wider mb-1.5">
                      Calculation Scope & Design Check ({activeRevision.rev})
                    </p>
                    <p className="text-xs text-zinc-300 leading-relaxed">{activeRevision.summary}</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
