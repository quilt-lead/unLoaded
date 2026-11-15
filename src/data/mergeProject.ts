// THE ONE PLACE the two halves of the view model meet, by GlobalId:
//   ElementTopology (src/loaders/elementGraphToBim.ts, from the element graph)
//   CalcData        (src/data/loadProject.ts, from the calc engine)
// plus applyModelDiff, which lays the engine's revision diff (diffGraphs) over revision B's merged view.
import type {
  BimLink,
  BimNode,
  CalcData,
  DatabaseDiffSummary,
  DiffStatus,
  ElementTopology,
  GhostSource,
  MappingStatus,
  ModelDiff,
  ProjectSource,
  ProjectViewModel,
} from '../types/bim';
import { categoryFor, markFamily, PROJECT_NODE_ID } from '../loaders/elementGraphToBim';
import { computeRadialLayout } from '../utils/graphEngine';

export interface MergeOptions {
  source: ProjectSource;
  projectId: string | null;
  /** IFC for the 3D view: an object URL of the model revision's IFC */
  modelFileUrl: string | null;
}

/**
 * Join topology and calc data by GlobalId (= element-graph node id = engine global_id).
 * Elements the calc engine has no row for are "unmapped" whenever calc data exists, including a
 * loaded package that extracted zero calculations. Without calc data they carry no mapping status.
 */
export function mergeProject(topology: ElementTopology, calc: CalcData | null, opts: MergeOptions): ProjectViewModel {
  const hasCalcData = calc !== null;
  const counts: Record<MappingStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  const elementNodes: BimNode[] = topology.elementNodes.map((n) => {
    if (n.kind !== 'element') return n;
    const links = calc?.linksByElement.get(n.id) ?? [];
    const status: MappingStatus | undefined = calc?.statusByElement.get(n.id) ?? (hasCalcData ? 'unmapped' : undefined);
    if (status) counts[status] += 1;
    return { ...n, calcLinks: links, mappingStatus: status };
  });
  return {
    source: opts.source,
    projectId: opts.projectId,
    projectName: calc?.projectName || topology.projectName,
    modelName: calc?.modelName ?? null,
    modelRevisionId: calc?.modelRevisionId ?? null,
    calcPackageName: calc?.calcPackageName ?? null,
    calcRevisionId: calc?.calcRevisionId ?? null,
    engine: calc?.engine ?? '',
    elementNodes,
    hierarchyLinks: topology.hierarchyLinks,
    loadPath: topology.loadPath,
    connectivity: topology.connectivity,
    levels: topology.levels ?? [],
    modelFileUrl: opts.modelFileUrl,
    calcs: calc?.calcs ?? [],
    calcDependencies: calc?.calcDependencies ?? [],
    calcNodes: calc?.calcNodes ?? [],
    calcLinks: calc?.calcLinks ?? [],
    calcToElementIds: calc?.calcToElementIds ?? new Map(),
    groups: calc?.groups ?? [],
    findings: calc?.findings ?? [],
    producers: calc?.producers ?? null,
    counts,
    hasUtilization: elementNodes.some((n) => typeof n.utilization === 'number'),
    calcOrigin: calc?.calcOrigin ?? null,
    hasDemoData: calc?.calcOrigin === 'bundle-demo',
  };
}

const GHOST_CATEGORY_ID = 'cat:not-in-head';

/**
 * Lay the revision diff A -> B over revision B's view (useProjectView with modelRev = B): every
 * element gets its diff status and field changes, and the elements only A has (the removed ones)
 * become ghost nodes, placed in the mark family of their own kind, with their geometry to be drawn
 * from revision A. Returns null when `view` is not revision B's (e.g. while B's view is still
 * loading): statuses laid over another revision would be wrong.
 */
export function applyModelDiff(
  view: ProjectViewModel,
  diff: ModelDiff,
  names: { base: string; compare: string },
): { view: ProjectViewModel; summary: DatabaseDiffSummary; ghosts: GhostSource[] } | null {
  if (view.modelRevisionId !== diff.b) return null;
  const present = new Set(view.elementNodes.filter((n) => n.kind === 'element').map((n) => n.id));
  const families = view.elementNodes.filter((n) => n.kind === 'family');
  const categories = new Set(view.elementNodes.filter((n) => n.kind === 'category').map((n) => n.id));
  const nodes: BimNode[] = view.elementNodes.map((n) => {
    if (n.kind !== 'element') return n;
    const m = diff.meta.get(n.id);
    return { ...n, diffStatus: m?.status ?? 'unchanged', diffChanges: m?.changes ?? [] };
  });
  const links = [...view.hierarchyLinks];
  const ghostIds: string[] = [];
  let needGhostCategory = false;

  for (const g of diff.onlyInA) {
    if (present.has(g.elementId)) continue;
    // `category` is the element-graph kind (toModelDiff): its mark family of the same kind if B has
    // one (a removed brace B3 never lands under beam family B), else its kind's category, else "Not in B"
    const kind = g.category || 'other';
    const cat = categoryFor(kind);
    const fam = markFamily(g.mark);
    const famNode = fam ? families.find((f) => f.label === fam && f.elementKind === kind) : undefined;
    const catNode = categories.has(cat.id) ? cat.id : null;
    const parent = famNode?.id ?? catNode ?? GHOST_CATEGORY_ID;
    if (parent === GHOST_CATEGORY_ID) needGhostCategory = true;
    nodes.push({
      id: g.elementId,
      label: g.mark || cat.singular,
      kind: 'element',
      level: 2,
      parent,
      categoryParent: famNode?.categoryParent ?? catNode ?? GHOST_CATEGORY_ID,
      elementKind: kind,
      mark: g.mark || undefined,
      calcLinks: [],
      r: 8,
      x: 0,
      y: 0,
      desc: `${cat.singular} · only in revision ${diff.a}`,
      diffStatus: 'removed',
      diffChanges: diff.meta.get(g.elementId)?.changes ?? [],
      bbox: diff.ghostBoxes?.get(g.elementId),
      isGhost: true,
    });
    links.push({ source: parent, target: g.elementId, relation: 'hierarchy' });
    ghostIds.push(g.elementId);
  }
  if (needGhostCategory) {
    nodes.push({ id: GHOST_CATEGORY_ID, label: `Not in revision ${diff.b}`, kind: 'category', level: 1, parent: PROJECT_NODE_ID, r: 26, x: 0, y: 0, desc: 'Removed elements whose kind is not in the compared revision' });
    links.push({ source: PROJECT_NODE_ID, target: GHOST_CATEGORY_ID, relation: 'hierarchy' });
  }

  const els = nodes.filter((n) => n.kind === 'element');
  const count = (s: DiffStatus) => els.filter((n) => n.diffStatus === s).length;
  const summary: DatabaseDiffSummary = {
    baseName: names.base,
    compareName: names.compare,
    baseRevisionId: diff.a,
    compareRevisionId: diff.b,
    addedCount: diff.onlyInB.length,
    removedCount: diff.onlyInA.length,
    modifiedCount: count('modified'),
    unchangedCount: count('unchanged'),
    edgesAdded: diff.edgesAdded,
    edgesRemoved: diff.edgesRemoved,
  };
  return {
    view: { ...view, elementNodes: computeRadialLayout(nodes), hierarchyLinks: links },
    summary,
    ghosts: ghostIds.length ? [{ revisionId: diff.a, elementIds: ghostIds }] : [],
  };
}
