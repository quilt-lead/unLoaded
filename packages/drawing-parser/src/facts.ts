/**
 * Facts read off the sheets, before they become ModelInput elements. Every fact keeps the
 * occurrence (sheet, page, rect, text) that produced it. Building coordinates are feet.
 */
import type { MemberTag } from "./text.ts";
import type { Occurrence } from "./types.ts";

/** A linear member read from a plan or elevation tag. */
export interface MemberFact {
  /** Content id (see ids in README): no size in it, so a resize keeps the id. */
  id: string;
  kind: "beam" | "brace";
  /** "girder" (on a grid line), "infill" (between grid lines), "grade_beam", "frame_beam", "brace". */
  role: string;
  level: string;
  /** Plan ends (ft). */
  a: [number, number];
  b: [number, number];
  /** Labels of the grid lines at a and b (brace: the outer line, then "mid"). */
  ends: [string, string];
  /** Braces: the level at the top end (`level` is the bottom). */
  topLevel?: string;
  tag?: MemberTag;
  mark?: string;
  grid: string;
  rule: string;
  /** Estimated plan position error of the drawn line, ft (tag-to-line offset rule). */
  planErrFt: number;
  occ: Occurrence;
}

/** One storey of a column, from a column schedule cell or an elevation tag. */
export interface ColumnTierFact {
  at: string;
  lo: string;
  hi: string;
  tag?: MemberTag;
  occ: Occurrence;
  rule: string;
}

/** Footing / pier at a grid intersection, from a plan mark or a schedule cell. */
export interface PointFact {
  id: string;
  kind: "footing" | "column";
  role: "footing" | "pier";
  at: string;
  mark?: string;
  occ: Occurrence;
  rule: string;
}

/** A connection: a detail callout attributed to a member end, or a base plate from a column schedule. */
export interface ConnectionFact {
  id: string;
  /** Element the connection belongs to (member id or column id). */
  member: string;
  /** End of the member: grid label (beams), "bottom" / "top" (braces), "base" (column base plates). */
  end: string;
  /** "8/S-501" when it came from a callout. */
  detailRef?: string;
  /** Type designation, e.g. "ST-3", "BP-4" (from the schedule cell or the detail title). */
  type?: string;
  occ: Occurrence;
  rule: string;
  attribution?: string;
  /** Page distance from the callout bubble to the member it was attributed to, pt. */
  distPt?: number;
  /** A second member within 1.5 x that distance: the callout is ambiguous between the two. */
  runnerUp?: string;
  runnerUpDistPt?: number;
}

export interface SlabFact {
  level: string;
  text: string;
  thicknessIn?: number;
  /** How the thickness was read from the note (`deckThickness`). */
  thicknessRule?: string;
  occ: Occurrence;
}

/** A row of a mark-keyed schedule (footing, pier, grade beam, base plate ...). */
export interface ScheduleRow {
  mark: string;
  schedule: string;
  text: string;
  occ: Occurrence;
}

/** A drawn detail panel: number + title on a detail sheet. */
export interface DetailPanel {
  ref: string;
  title: string;
  type?: string;
  occ: Occurrence;
}

/** A level elevation stated somewhere in the set. */
export interface LevelStatement {
  level: string;
  ft: number;
  how: string;
  occ: Occurrence;
}

export interface Facts {
  members: MemberFact[];
  tiers: ColumnTierFact[];
  points: PointFact[];
  connections: ConnectionFact[];
  slabs: SlabFact[];
  rows: ScheduleRow[];
  details: Map<string, DetailPanel>;
  levels: LevelStatement[];
  /** Named elevations that are not levels: "top of footing", "top of pier". */
  datums: LevelStatement[];
  /** Frame markers ("*SMF") attached to members: member id -> system. */
  frames: Map<string, string>;
  warnings: string[];
}

export const emptyFacts = (): Facts => ({
  members: [], tiers: [], points: [], connections: [], slabs: [], rows: [], details: new Map(), levels: [], datums: [],
  frames: new Map(), warnings: [],
});
