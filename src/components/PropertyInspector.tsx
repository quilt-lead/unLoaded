import React, { useState } from 'react';
import { CircleDot, FileText, ArrowUpRight, Layers, Link2, Calculator } from 'lucide-react';
import { BimLink, BimNode } from '../types/bim';
import {
  getDirectConnectivityNeighbors,
  getDisplayType,
  getNodeDocuments,
  isInstanceNode,
} from '../utils/graphEngine';
import { DIFF_PALETTE, getEffectiveNodeColor, getHeatmapColor } from '../utils/colors';

interface PropertyInspectorProps {
  nodes: BimNode[];
  links: BimLink[];
  rawLinks: BimLink[];
  groups?: { id: string; name: string; nodeIds: string[] }[];
  selectedNodeId: string | null;
  selectedNodeIds: Set<string>;
  activeLoadChainNodeIds: Set<string>;
  heatmapMode: boolean;
  diffMode?: boolean;
  onSelectNode: (id: string) => void;
  onSelectGroup?: (groupId: string) => void;
  onRenameGroup?: (groupId: string, newName: string) => void;
  onClearSelection: () => void;
  onOpenDocument: (nodeId: string, docId?: string, preserveSelection?: boolean) => void;
  onSwitchToCalcGraph: (calcNodeId?: string) => void;
}

export const PropertyInspector: React.FC<PropertyInspectorProps> = ({
  nodes,
  links,
  rawLinks,
  groups = [],
  selectedNodeId,
  selectedNodeIds,
  activeLoadChainNodeIds,
  heatmapMode,
  diffMode = false,
  onSelectNode,
  onSelectGroup,
  onRenameGroup,
  onClearSelection,
  onOpenDocument,
  onSwitchToCalcGraph,
}) => {
  const [renamingGroupId, setRenamingGroupId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState<string>('');
  const node = selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) : null;

  if (!node) {
    return (
      <div className="text-center py-6 text-zinc-500">
        <div className="w-10 h-10 bg-white/[0.03] border border-white/[0.06] text-zinc-500 rounded-xl flex items-center justify-center mx-auto mb-2.5 text-sm">
          <CircleDot className="w-4 h-4" />
        </div>
        <p className="font-medium text-zinc-300 text-xs">No Element Selected</p>
        <p className="text-[11px] text-zinc-500 mt-1">
          Click any beam, column, slab, or connection to inspect its physical connectivity and mapped PDF calculations.
        </p>
      </div>
    );
  }

  const displayType = getDisplayType(node);
  const utilPct = typeof node.utilization === 'number' && Number.isFinite(node.utilization)
    ? Math.round(node.utilization * 100)
    : null;
  const utilColor = utilPct !== null ? getHeatmapColor(node.utilization) : '#6366f1';

  const connectedLinks = links.filter((l) => l.source === node.id || l.target === node.id);
  const hierarchyIds = connectedLinks
    .filter((l) => !l.isLoadPath)
    .map((l) => (l.source === node.id ? l.target : l.source));
  const hierarchyNodes = nodes.filter((n) => hierarchyIds.includes(n.id));

  // Physical topological connectivity neighbors (e.g., Beam <-> Connection <-> Column)
  const connectivityNeighbors = isInstanceNode(node)
    ? getDirectConnectivityNeighbors(node.id, nodes, rawLinks)
    : [];

  const loadPathNodes = Array.from(activeLoadChainNodeIds)
    .filter((nid) => nid !== node.id)
    .map((nid) => nodes.find((n) => n.id === nid))
    .filter((n): n is BimNode => Boolean(n))
    .sort((a, b) => (b.floorNum || 0) - (a.floorNum || 0));

  const multiList =
    selectedNodeIds.size > 1
      ? Array.from(selectedNodeIds)
          .map((sid) => nodes.find((n) => n.id === sid))
          .filter((n): n is BimNode => Boolean(n))
      : [];

  // Affected PDF calculation documents (primary + traced load chain + hierarchy)
  const affectedIds = new Set<string>([node.id]);
  activeLoadChainNodeIds.forEach((nid) => affectedIds.add(nid));
  connectedLinks.forEach((l) => {
    if (!l.isLoadPath) {
      affectedIds.add(l.source);
      affectedIds.add(l.target);
    }
  });

  const orderedAffectedNodes = [
    node,
    ...loadPathNodes,
    ...hierarchyNodes.filter((hn) => hn.id !== node.id && !activeLoadChainNodeIds.has(hn.id)),
  ];

  const allAffectedDocs: Array<{
    id: string;
    title: string;
    type: string;
    rev: string;
    pageRef?: string;
    ownerId: string;
    ownerLabel: string;
    ownerColor: string;
    isPrimary: boolean;
  }> = [];
  const seenDocKeys = new Set<string>();

  orderedAffectedNodes.forEach((targetNode) => {
    if (!affectedIds.has(targetNode.id)) return;
    getNodeDocuments(targetNode).forEach((doc) => {
      const key = `${targetNode.id}::${doc.id}`;
      if (!seenDocKeys.has(key)) {
        seenDocKeys.add(key);
        allAffectedDocs.push({
          ...doc,
          ownerId: targetNode.id,
          ownerLabel: targetNode.label,
          ownerColor: getEffectiveNodeColor(targetNode, heatmapMode),
          isPrimary: targetNode.id === node.id,
        });
      }
    });
  });

  return (
    <div className="space-y-3">
      {(() => {
        const containingGroups = groups.filter((g) => g.nodeIds.includes(node.id));
        if (containingGroups.length === 0) return null;
        return (
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
                      if (renameDraft.trim() && onRenameGroup) onRenameGroup(g.id, renameDraft.trim());
                      setRenamingGroupId(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        e.stopPropagation();
                        e.currentTarget.blur();
                      }
                      if (e.key === 'Escape') {
                        e.preventDefault();
                        e.stopPropagation();
                        setRenamingGroupId(null);
                      }
                    }}
                    className="min-w-0 flex-1 px-2 py-0.5 rounded bg-black/50 text-white mono text-[10px] border border-emerald-400 focus-visible:ring-2 focus-visible:ring-emerald-300"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => onSelectGroup?.(g.id)}
                    title="Click to select entire group"
                    className="mono text-[10px] font-semibold text-emerald-200 hover:text-white flex items-center gap-1.5 truncate"
                  >
                    <Layers className="w-3 h-3 text-emerald-300 flex-shrink-0" />
                    <span className="truncate">{g.name}</span>
                    <span className="text-emerald-400/80">({g.nodeIds.length})</span>
                  </button>
                )}
                {renamingGroupId !== g.id && (
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => onSelectGroup?.(g.id)}
                      className="mono text-[9px] text-emerald-300 hover:text-white underline"
                    >
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
      })()}

      {multiList.length > 1 && (
        <div className="bg-indigo-500/15 border border-indigo-400/35 rounded-xl p-2.5 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="mono text-[10px] font-semibold text-indigo-200 uppercase tracking-wider flex items-center gap-1">
              <Layers className="w-3 h-3 text-indigo-300" />
              {multiList.length} Elements Selected
            </span>
            <button
              type="button"
              onClick={onClearSelection}
              className="mono text-[9px] text-zinc-400 hover:text-white underline"
            >
              Clear All
            </button>
          </div>
          <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
            {multiList.map((mn) => (
              <button
                type="button"
                key={mn.id}
                onClick={() => onSelectNode(mn.id)}
                title="Click to focus solo"
                className={`mono text-[9px] px-1.5 py-0.5 rounded cursor-pointer border ${
                  mn.id === node.id
                    ? 'bg-white text-zinc-900 border-white font-semibold'
                    : 'bg-black/40 text-zinc-200 border-white/15 hover:border-indigo-400/50'
                }`}
              >
                {mn.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <span className="mono text-[10px] font-medium px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-400/25">
          {displayType}
        </span>
        {node.floor && node.floor !== 'ALL' && (
          <span className="mono text-[10px] px-2 py-0.5 rounded bg-white/[0.06] text-zinc-200 border border-white/[0.16]">
            {node.floor}
          </span>
        )}
        <span className="mono text-[10px] text-zinc-500 truncate">ID: {node.id}</span>
      </div>

      <div>
        <h3 className="font-semibold text-sm text-white tracking-tight">{node.label}</h3>
        <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
          {node.desc || 'Structural BIM element entity.'}
        </p>
      </div>

      {/* Database Diff Comparison Card (DB A vs DB B) */}
      {diffMode && node.diffStatus && (
        <div
          className="rounded-xl p-2.5 border space-y-2"
          style={{
            backgroundColor: 'rgba(15, 18, 25, 0.72)',
            borderColor: DIFF_PALETTE[node.diffStatus],
          }}
        >
          <div className="flex items-center justify-between">
            <span
              className="mono text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
              style={{
                backgroundColor: `${DIFF_PALETTE[node.diffStatus]}26`,
                color: DIFF_PALETTE[node.diffStatus],
              }}
            >
              DIFF: {node.diffStatus.toUpperCase()}
            </span>
            <span className="mono text-[9px] text-zinc-400">DB A → DB B</span>
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
                ? 'This element exists only in DB B.'
                : node.diffStatus === 'removed'
                  ? 'This element exists only in DB A.'
                  : 'No property changes between DB A and DB B.'}
            </p>
          )}
        </div>
      )}

      {isInstanceNode(node) && (
        <div className="grid grid-cols-2 gap-2 bg-white/[0.02] p-2.5 rounded-xl border border-white/[0.07]">
          {node.sectionSize && (
            <div>
              <span className="mono text-[9px] text-zinc-500 uppercase block">Section / Profile</span>
              <span className="mono text-[11px] font-semibold text-cyan-300">{node.sectionSize}</span>
            </div>
          )}
          {node.baySpacing && (
            <div>
              <span className="mono text-[9px] text-zinc-500 uppercase block">Grid Bay</span>
              <span className="mono text-[11px] font-semibold text-zinc-200">{node.baySpacing}</span>
            </div>
          )}
          <div>
            <span className="mono text-[9px] text-zinc-500 uppercase block">Rated Strength</span>
            <span className="mono text-[11px] font-semibold text-zinc-100">
              {node.strengthLabel || (typeof node.ratedStrength === 'number' && Number.isFinite(node.ratedStrength)
                ? `${node.ratedStrength.toLocaleString()} MPa`
                : '—')}
            </span>
          </div>
          <div>
            <span className="mono text-[9px] text-zinc-500 uppercase block">Axial / Gravity Load</span>
            <span className="mono text-[11px] font-semibold text-amber-300">
              {typeof node.axialLoadKn === 'number' && Number.isFinite(node.axialLoadKn)
                ? `${node.axialLoadKn.toLocaleString()} kN`
                : '—'}
            </span>
          </div>
          {utilPct !== null && (
            <div className="col-span-2 pt-1 border-t border-white/[0.06]">
              <div className="flex items-center justify-between mono text-[9px] mb-1">
                <span className="text-zinc-400 uppercase">Demand / Capacity Utilization</span>
                <span style={{ color: utilColor }} className="font-semibold">
                  {utilPct}%
                </span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-white/[0.07] overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, utilPct))}%`, backgroundColor: utilColor }} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Mapped PDF Calculations + Cross-Link to Calculation Graph */}
      <div className="border-t border-white/[0.07] pt-2.5">
        <div className="flex items-center justify-between mb-1.5 gap-1">
          <p className="mono text-[10px] font-semibold text-rose-400 uppercase tracking-wider">
            PDF Calculations ({allAffectedDocs.length})
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onSwitchToCalcGraph(allAffectedDocs[0] ? `calc-doc-${allAffectedDocs[0].id}` : undefined)}
              className="mono text-[9px] text-amber-300 hover:text-white underline flex items-center gap-0.5"
            >
              <Calculator className="w-2.5 h-2.5" />
              Calc Graph
            </button>
            <button
              type="button"
              onClick={() => onOpenDocument(node.id)}
              className="mono text-[9px] text-indigo-300 hover:text-white underline"
            >
              PDF Viewer →
            </button>
          </div>
        </div>
        <div className="space-y-1.5 max-h-44 overflow-y-auto pr-0.5">
          {allAffectedDocs.length === 0 && (
            <p className="text-xs text-zinc-500 italic">No PDF calculations mapped to this selection.</p>
          )}
          {allAffectedDocs.map((doc) => (
            <button
              type="button"
              key={`${doc.ownerId}-${doc.id}`}
              onClick={() => onOpenDocument(doc.ownerId, doc.id, true)}
              className={`w-full text-left flex items-center justify-between gap-2 ${
                doc.isPrimary
                  ? 'bg-rose-500/[0.11] border-rose-400/35'
                  : 'bg-rose-500/[0.04] border-rose-400/20'
              } hover:bg-rose-500/[0.16] p-2 rounded-lg cursor-pointer transition border`}
            >
              <span className="flex items-center space-x-2 min-w-0">
                <FileText className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                <span className="min-w-0">
                  <span className="block text-[11px] font-medium text-zinc-100 truncate">{doc.title}</span>
                  <span className="block mono text-[9px] text-zinc-400 truncate">
                    <span style={{ color: doc.ownerColor }} className="font-semibold">
                      {doc.ownerLabel}
                    </span>{' '}
                    • {doc.rev}{doc.pageRef ? ` (${doc.pageRef})` : ''}
                  </span>
                </span>
              </span>
              <ArrowUpRight className="w-3 h-3 text-zinc-400 flex-shrink-0" />
            </button>
          ))}
        </div>
      </div>

      {/* Physical Structural Connectivity (e.g., Beam <-> Connection <-> Column) */}
      {connectivityNeighbors.length > 0 && (
        <div className="border-t border-white/[0.07] pt-2.5">
          <p className="mono text-[10px] font-semibold text-cyan-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <Link2 className="w-3 h-3" />
            Physical Connectivity ({connectivityNeighbors.length})
          </p>
          <div className="space-y-1 max-h-28 overflow-y-auto">
            {connectivityNeighbors.map((nb) => (
              <button
                type="button"
                key={nb.id}
                onClick={() => onSelectNode(nb.id)}
                className="w-full text-left flex items-center justify-between bg-cyan-500/[0.06] hover:bg-cyan-500/[0.14] px-2 py-1.5 rounded-lg cursor-pointer transition border border-cyan-500/20"
              >
                <span className="flex items-center space-x-2 min-w-0">
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: getEffectiveNodeColor(nb, heatmapMode) }}
                  />
                  <span className="text-[11px] font-medium text-zinc-100 truncate">{nb.label}</span>
                </span>
                <span className="mono text-[9px] text-cyan-300 flex-shrink-0 ml-2">
                  Connected • {nb.floor || 'ALL'}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {loadPathNodes.length > 0 && (
        <div className="border-t border-white/[0.07] pt-2.5">
          <p className="mono text-[10px] font-semibold text-amber-400 uppercase tracking-wider mb-1.5">
            Continuous Load Path ({loadPathNodes.length})
          </p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {loadPathNodes.map((lp) => {
              const relativeFloor = typeof lp.floorNum !== 'number' || typeof node.floorNum !== 'number'
                ? 'Connected'
                : lp.floorNum > node.floorNum
                  ? 'Above ↑'
                  : lp.floorNum < node.floorNum ? 'Below ↓' : 'Same Level';
              return (
                <button
                  type="button"
                  key={lp.id}
                  onClick={() => onSelectNode(lp.id)}
                  className="w-full text-left flex items-center justify-between bg-amber-500/[0.06] hover:bg-amber-500/[0.14] px-2 py-1.5 rounded-lg cursor-pointer transition border border-amber-500/20"
                >
                  <span className="flex items-center space-x-2 min-w-0">
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: getEffectiveNodeColor(lp, heatmapMode) }}
                    />
                    <span className="text-[11px] font-medium text-zinc-100 truncate">{lp.label}</span>
                  </span>
                  <span className="mono text-[9px] text-amber-300 flex-shrink-0 ml-2">
                    {relativeFloor} • {typeof lp.axialLoadKn === 'number' && Number.isFinite(lp.axialLoadKn)
                      ? `${lp.axialLoadKn.toLocaleString()} kN`
                      : '—'}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="border-t border-white/[0.07] pt-2.5">
        <p className="mono text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
          Category & Children ({hierarchyNodes.length})
        </p>
        <div className="space-y-1 max-h-24 overflow-y-auto">
          {hierarchyNodes.length > 0 ? (
            hierarchyNodes.slice(0, 25).map((cn) => (
              <button
                type="button"
                key={cn.id}
                onClick={() => onSelectNode(cn.id)}
                className="w-full text-left flex items-center justify-between bg-white/[0.03] hover:bg-white/[0.07] px-2 py-1.5 rounded-lg cursor-pointer transition border border-white/[0.06]"
              >
                <span className="flex items-center space-x-2 min-w-0">
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: getEffectiveNodeColor(cn, heatmapMode) }}
                  />
                  <span className="text-[11px] font-medium text-zinc-200 truncate">{cn.label}</span>
                </span>
                <span className="mono text-[9px] text-indigo-400 flex-shrink-0">
                  {cn.floor && cn.floor !== 'ALL' ? cn.floor : getDisplayType(cn)}
                </span>
              </button>
            ))
          ) : (
            <p className="text-xs text-zinc-600 italic">No direct hierarchy connections.</p>
          )}
        </div>
      </div>
    </div>
  );
};
