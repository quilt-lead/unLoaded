import React, { useMemo, useState } from 'react';
import {
  FolderOpen,
  Search,
  FilterX,
  FileText,
  CircleDot,
  Box,
  FileQuestion,
  History,
  Calculator,
} from 'lucide-react';
import { BimLink, BimNode, DiffStatus, FlattenedDocument, WorkspaceView } from '../types/bim';
import { DIFF_PALETTE } from '../utils/colors';

interface DocumentBrowserProps {
  allDocs: FlattenedDocument[];
  nodes: BimNode[];
  links: BimLink[];
  selectedNodeId: string | null;
  activeLoadChainNodeIds: Set<string>;
  filterBySelectedElement: boolean;
  diffMode?: boolean;
  onClearElementFilter: () => void;
  initialDocId: string | null;
  onLocateElement: (nodeId: string, view: WorkspaceView) => void;
}

export const DocumentBrowser: React.FC<DocumentBrowserProps> = ({
  allDocs,
  nodes,
  links,
  selectedNodeId,
  activeLoadChainNodeIds,
  filterBySelectedElement,
  diffMode = false,
  onClearElementFilter,
  initialDocId,
  onLocateElement,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDocId, setSelectedDocId] = useState<string | null>(initialDocId);
  const [selectedRevision, setSelectedRevision] = useState<{ docId: string; rev: string } | null>(null);
  const nodeMap = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  const selectedNode = useMemo(
    () => (selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) || null : null),
    [selectedNodeId, nodes]
  );

  const { filteredDocs, affectedCount } = useMemo(() => {
    let list = allDocs;
    let affCount = 0;

    if (filterBySelectedElement && selectedNode) {
      const affectedIds = new Set<string>([selectedNode.id]);
      activeLoadChainNodeIds.forEach((nid) => affectedIds.add(nid));
      links.forEach((l) => {
        if (!l.isLoadPath && (l.source === selectedNode.id || l.target === selectedNode.id)) {
          affectedIds.add(l.source);
          affectedIds.add(l.target);
        }
      });
      affCount = Math.max(0, affectedIds.size - 1);
      list = list.filter((d) => d.mappedElementIds.some((eid) => affectedIds.has(eid)));
    }

    const q = searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (d) =>
          d.title.toLowerCase().includes(q) ||
          d.type.toLowerCase().includes(q) ||
          d.code.toLowerCase().includes(q) ||
          d.nodeLabel.toLowerCase().includes(q) ||
          d.mappedElementIds.some((id) =>
            id.toLowerCase().includes(q) || nodeMap.get(id)?.label.toLowerCase().includes(q)
          ) ||
          (d.summary && d.summary.toLowerCase().includes(q))
      );
    }

    return { filteredDocs: list, affectedCount: affCount };
  }, [allDocs, filterBySelectedElement, selectedNode, activeLoadChainNodeIds, links, searchQuery, nodeMap]);

  const activeDoc = useMemo(() => {
    if (filteredDocs.length === 0) return null;
    if (selectedDocId && filteredDocs.some((d) => d.id === selectedDocId)) {
      return filteredDocs.find((d) => d.id === selectedDocId)!;
    }
    if (initialDocId && filteredDocs.some((d) => d.id === initialDocId)) {
      return filteredDocs.find((d) => d.id === initialDocId)!;
    }
    return filteredDocs[0];
  }, [filteredDocs, selectedDocId, initialDocId]);

  const currentRevision = activeDoc
    ? {
        rev: activeDoc.rev,
        date: activeDoc.date,
        pages: activeDoc.pages,
        pageRef: activeDoc.pageRef,
        summary: activeDoc.summary,
      }
    : null;
  const history = activeDoc?.revisions || [];
  const revisions = currentRevision && history.length > 0 && !history.some((r) => r.rev === currentRevision.rev)
    ? [currentRevision, ...history]
    : history;
  const selectedRev = selectedRevision?.docId === activeDoc?.id ? selectedRevision?.rev : null;
  const activeRevision =
    revisions.find((r) => r.rev === selectedRev) ||
    revisions.find((r) => r.rev === activeDoc?.rev) ||
    currentRevision;

  const mappedElements = useMemo(() => {
    if (!activeDoc) return [];
    return activeDoc.mappedElementIds.map((id) => nodeMap.get(id)).filter((n): n is BimNode => Boolean(n));
  }, [activeDoc, nodeMap]);

  return (
    <section className="w-full h-full overflow-hidden flex flex-col bg-[#282c34]/95">
      <div className="px-6 py-3.5 border-b border-white/[0.12] bg-[#2d3139]/92 flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-400/30 text-amber-400 flex items-center justify-center">
            <FolderOpen className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-semibold text-white tracking-tight flex items-center gap-2">
              <span>
                {filterBySelectedElement && selectedNode
                  ? `PDF Calculations for ${selectedNode.label} & Affected Chain`
                  : 'Structural Calculation PDF Repository & Version Control'}
              </span>
              {filterBySelectedElement && selectedNode && (
                <span className="mono text-[10px] px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-400/30">
                  Chain: {selectedNode.label} (+{affectedCount} affected)
                </span>
              )}
            </h2>
            <p className="mono text-[10px] text-zinc-500 mt-0.5">
              1:1 & MULTI-ELEMENT PDF PACKAGES • REVISION HISTORY • DIRECT ELEMENT MAPPING
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          {filterBySelectedElement && selectedNode && (
            <button
              type="button"
              onClick={onClearElementFilter}
              className="bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-400/30 px-2.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5"
            >
              <FilterX className="w-3.5 h-3.5" />
              <span>Show All PDFs</span>
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
              <p className="text-xs font-medium text-zinc-300">No matching PDF calculations found</p>
              <p className="text-[11px] text-zinc-500 mt-1">
                {nodes.length === 0
                  ? 'Import a model with mapped PDF calculations to get started.'
                  : nodes.some((node) => node.documents?.length)
                  ? 'Try clearing the search query or filters.'
                  : 'This model has no mapped PDF calculations.'}
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
            <div className="max-w-3xl w-full mx-auto bg-[#2d3139] border border-white/[0.16] rounded-2xl shadow-[0_24px_60px_rgba(0,0,0,0.9)] overflow-hidden flex flex-col">
              <div className="px-5 py-3 border-b border-white/[0.12] bg-white/[0.02] flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="px-2 py-0.5 rounded bg-rose-500/15 border border-rose-400/30 text-rose-300 mono text-[10px] font-semibold">
                    PDF
                  </span>
                  <span className="mono text-xs text-zinc-200 font-medium">{activeDoc.id.toUpperCase()}.pdf</span>
                  <span className="mono text-[10px] text-zinc-500">
                    ({activeRevision.pages} Pages{activeRevision.pageRef ? ` • ${activeRevision.pageRef}` : ''})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onLocateElement(activeDoc.nodeId, 'element-graph')}
                    className="bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5"
                  >
                    <CircleDot className="w-3 h-3 text-emerald-400" />
                    <span>Element Graph</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onLocateElement(`calc-doc-${activeDoc.id}`, 'calculation-graph')}
                    className="bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5"
                  >
                    <Calculator className="w-3 h-3 text-amber-400" />
                    <span>Calc Graph</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onLocateElement(activeDoc.nodeId, '3d')}
                    className="bg-white/[0.04] hover:bg-white/[0.09] text-zinc-200 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-white/[0.14] transition flex items-center gap-1.5"
                  >
                    <Box className="w-3 h-3 text-cyan-400" />
                    <span>3D Model</span>
                  </button>
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
