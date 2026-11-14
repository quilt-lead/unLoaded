// THE ONE PLACE the two halves of the view model meet, by GlobalId:
//   ElementTopology (src/loaders/elementGraphToBim.ts, from the element graph)
//   CalcData        (src/data/loadProject.ts, from the backend calc engine)
// plus applyModelDiff, which lays a backend revision diff over a merged view.
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
  projectId: number | null;
  /** IFC for the 3D view: a backend revision URL or a local object URL */
  modelFileUrl: string | null;
}

/**
 * Join topology and calc data by GlobalId (= element-graph node id = backend global_id).
 * Elements the calc engine has no row for are "unmapped" when a calc package is loaded, and carry
 * no mapping status when there is no calc data at all (a model opened without the backend).
 */
export function mergeProject(topology: ElementTopology, calc: CalcData | null, opts: MergeOptions): ProjectViewModel {
  const hasCalcs = Boolean(calc && calc.calcRevisionId != null);
  const counts: Record<MappingStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  const elementNodes: BimNode[] = topology.elementNodes.map((n) => {
    if (n.kind !== 'element') return n;
    const links = calc?.linksByElement.get(n.id) ?? [];
    const status: MappingStatus | undefined = calc?.statusByElement.get(n.id) ?? (hasCalcs ? 'unmapped' : undefined);
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
    modelFileUrl: opts.modelFileUrl,
    calcs: calc?.calcs ?? [],
    calcDependencies: calc?.calcDependencies ?? [],
    calcNodes: calc?.calcNodes ?? [],
    calcLinks: calc?.calcLinks ?? [],
    calcToElementIds: calc?.calcToElementIds ?? new Map(),
    counts,
    hasUtilization: elementNodes.some((n) => typeof n.utilization === 'number'),
  };
}

const GHOST_CATEGORY_ID = 'cat:not-in-head';

/**
 * Lay a backend diff over the head-model view: every element gets its diff status and field
 * changes, and elements of the diff that the head model does not have (removed ones when B is the
 * head, added ones when A is) become ghost nodes placed in their mark family, with their geometry
 * to be drawn from the revision that has them.
 */
export function applyModelDiff(
  view: ProjectViewModel,
  diff: ModelDiff,
  names: { base: string; compare: string },
): { view: ProjectViewModel; summary: DatabaseDiffSummary; ghosts: GhostSource[] } {
  const present = new Set(view.elementNodes.filter((n) => n.kind === 'element').map((n) => n.id));
  const families = view.elementNodes.filter((n) => n.kind === 'family');
  const categories = new Set(view.elementNodes.filter((n) => n.kind === 'category').map((n) => n.id));
  const nodes: BimNode[] = view.elementNodes.map((n) => {
    if (n.kind !== 'element') return n;
    const m = diff.meta.get(n.id);
    return { ...n, diffStatus: m?.status ?? 'unchanged', diffChanges: m?.changes ?? [] };
  });
  const links = [...view.hierarchyLinks];
  const ghostIds = new Map<number, string[]>();
  let needGhostCategory = false;

  const addGhost = (g: { elementId: string; mark: string; category: string }, status: DiffStatus, rid: number) => {
    if (present.has(g.elementId)) return;
    // its mark family if the head has it, else its kind's category (the backend's `cat` is the
    // element-graph kind), else a "Not in head" category
    const fam = markFamily(g.mark);
    const famNode = fam ? families.find((f) => f.label === fam && f.kind === 'family') : undefined;
    const catId = categoryFor(g.category.toLowerCase() || 'other').id;
    const catNode = categories.has(catId) ? catId : null;
    const parent = famNode?.id ?? catNode ?? GHOST_CATEGORY_ID;
    if (parent === GHOST_CATEGORY_ID) needGhostCategory = true;
    nodes.push({
      id: g.elementId,
      label: g.mark || g.category || 'Element',
      kind: 'element',
      level: 2,
      parent,
      categoryParent: famNode?.categoryParent ?? catNode ?? GHOST_CATEGORY_ID,
      elementKind: famNode?.elementKind ?? (catNode ? g.category.toLowerCase() : undefined),
      mark: g.mark || undefined,
      calcLinks: [],
      r: 8,
      x: 0,
      y: 0,
      desc: `${g.category || 'Element'} · only in revision ${rid}`,
      diffStatus: status,
      diffChanges: diff.meta.get(g.elementId)?.changes ?? [],
      isGhost: true,
    });
    links.push({ source: parent, target: g.elementId, relation: 'hierarchy' });
    (ghostIds.get(rid) ?? ghostIds.set(rid, []).get(rid)!).push(g.elementId);
  };
  diff.onlyInA.forEach((g) => addGhost(g, 'removed', diff.a));
  diff.onlyInB.forEach((g) => addGhost(g, 'added', diff.b));
  if (needGhostCategory) {
    nodes.push({ id: GHOST_CATEGORY_ID, label: 'Not in head', kind: 'category', level: 1, parent: PROJECT_NODE_ID, r: 26, x: 0, y: 0, desc: 'Diff elements whose mark family is not in the head model' });
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
    ghosts: [...ghostIds.entries()].map(([revisionId, elementIds]) => ({ revisionId, elementIds })),
  };
}
