// Two different events change what the workspace shows, and they treat the user's state differently:
//
//   the PROJECT changed (App enterScope: picker, sample, demo, project or export file)
//       -> everything the user did in the old project is reset: groups, moved nodes, selection,
//          impact, PDF target, the 3D camera
//   the REVISION on screen changed, same project (entering / swapping / leaving a diff, a new head
//   revision, a new calc package)
//       -> groups and moved nodes stay (they are keyed by GlobalId and carry across revisions);
//          selection, impact and PDF target stay where what they point at exists in the new view and
//          are dropped where it does not: keepWhatExists
//
// diffRevisionsError is the one check every way into diff mode goes through (deep link, panel).
import type { PdfTarget, ProjectViewModel, RevisionInfo } from '../types/bim';

/** Why model revisions (A, B) cannot be compared in this project, or null when they can. */
export function diffRevisionsError(revisions: readonly RevisionInfo[] | null, a: number, b: number): string | null {
  if (!Number.isInteger(a) || !Number.isInteger(b)) return 'revision ids must be whole numbers';
  if (a === b) return `A and B are the same revision (#${a})`;
  if (!revisions) return "the project's revisions have not loaded";
  for (const rid of [a, b]) {
    const r = revisions.find((x) => x.id === rid);
    if (!r) return `revision #${rid} is not a revision of this project`;
    if (r.kind !== 'model') return `revision #${rid} is a calc package, not a model revision`;
  }
  return null;
}

/** The user's state that points into the view: selection, impact request, PDF target. */
export interface PointerState {
  selectedNodeId: string | null;
  selectedNodeIds: Set<string>;
  selectedCalcNodeId: string | null;
  selectedCalcNodeIds: Set<string>;
  calcAnchorKey: string | null;
  impactReq: { gid: string; mode: 'change' | 'remove' } | null;
  pdfTarget: PdfTarget | null;
}

type ViewIds = Pick<ProjectViewModel, 'elementNodes' | 'calcNodes' | 'calcs'>;

/**
 * The revision on screen changed: keep each pointer whose target exists in `view` (element-graph
 * nodes, ghosts of a diff included; calc nodes, the mapping satellites of a kept calc anchor; calcs),
 * drop the rest. Returns `s` itself when nothing was dropped, so a caller can skip the update.
 */
export function keepWhatExists(s: PointerState, view: ViewIds): PointerState {
  const elementIds = new Set(view.elementNodes.map((n) => n.id));
  const calcNodeIds = new Set(view.calcNodes.map((n) => n.id));
  const calcKeys = new Set(view.calcs.map((c) => c.key));

  const calcAnchorKey = s.calcAnchorKey != null && calcKeys.has(s.calcAnchorKey) ? s.calcAnchorKey : null;
  // a satellite id is `map:<anchor calc key>:<element id>` (withMappingSatellites)
  const satellitePrefix = calcAnchorKey != null ? `map:${calcAnchorKey}:` : null;
  const calcNodeExists = (id: string) =>
    calcNodeIds.has(id) || (satellitePrefix != null && id.startsWith(satellitePrefix) && elementIds.has(id.slice(satellitePrefix.length)));

  const keepSet = (ids: Set<string>, exists: (id: string) => boolean) => {
    const kept = new Set([...ids].filter(exists));
    return kept.size === ids.size ? ids : kept;
  };
  const selectedNodeIds = keepSet(s.selectedNodeIds, (id) => elementIds.has(id));
  const selectedNodeId =
    s.selectedNodeId != null && elementIds.has(s.selectedNodeId) ? s.selectedNodeId : selectedNodeIds.size ? [...selectedNodeIds].pop()! : null;
  const selectedCalcNodeIds = keepSet(s.selectedCalcNodeIds, calcNodeExists);
  const selectedCalcNodeId = s.selectedCalcNodeId != null && calcNodeExists(s.selectedCalcNodeId) ? s.selectedCalcNodeId : null;
  const impactReq = s.impactReq && elementIds.has(s.impactReq.gid) ? s.impactReq : null;
  const pdfTarget = s.pdfTarget && (s.pdfTarget.calcKey == null || calcKeys.has(s.pdfTarget.calcKey)) ? s.pdfTarget : null;

  const next: PointerState = { selectedNodeId, selectedNodeIds, selectedCalcNodeId, selectedCalcNodeIds, calcAnchorKey, impactReq, pdfTarget };
  return (Object.keys(next) as (keyof PointerState)[]).every((k) => next[k] === s[k]) ? s : next;
}
