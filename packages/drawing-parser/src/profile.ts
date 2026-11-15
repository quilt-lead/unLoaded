/**
 * Drawing-set conventions: where the title block is, what a sheet number looks like, which
 * title words make a sheet a framing plan, the tag vocabulary. The defaults are generic US
 * structural-set conventions (the hackathon's `profiles/default.yaml`, ported); a set that
 * differs overrides only what differs via `parseDrawingSet(files, { profile: {...} })`.
 * Lengths are PDF points unless the name says otherwise.
 */
export interface DrawingProfile {
  /** Title-block strip starts at this fraction of the page width (right edge strip). */
  titleBlockXFrac: number;
  sheetNumber: RegExp;
  /** Title words: at least this font size, within this distance above the sheet number. */
  titleMinSize: number;
  titleWindow: number;
  titleStrip: RegExp;
  /** First title substring that matches decides the sheet kind. */
  sheetKinds: Array<{ contains: string; kind: import("./types.ts").SheetKind }>;
  /** A heading ending in this word, right of this fraction of the width, starts the plan notes column. */
  notesHeadingWord: string;
  notesXFrac: number;
  notesMargin: number;
  /** Grid bubble labels. */
  gridLabel: RegExp;
  bubbleSize: [number, number];
  /** Two bubbles of one label at least this far apart (same x or same y) make a plan grid line. */
  bubblePairMinSep: number;
  bubblePairTol: number;
  /** Foundation marks: footing, pier, grade / tie beam. */
  footingMark: RegExp;
  pierMark: RegExp;
  gradeBeamMark: RegExp;
  /** Lateral-frame markers printed beside frame members ("*SMF"). */
  frameMarker: RegExp;
  /** Prefix on a member tag that marks a member of the seismic force-resisting system. */
  sfrsPrefix: string;
  /** Detail / connection type designation inside a detail title ("MC-1", "ST-3", "BP-4"). */
  detailTypeMark: RegExp;
  /** Callout: detail number over a sheet number. */
  calloutNumber: RegExp;
  /** Max distance (pt) from a callout bubble to the member it is attributed to. */
  calloutMaxDist: number;
  /** Max distance (pt) from a footing / pier mark to its grid intersection. */
  markMaxDist: number;
  /** Nominal scale used when a sheet has no dimension strings between grid bubbles (pt per ft). */
  fallbackPtPerFt?: number;
}

export const DEFAULT_PROFILE: Readonly<DrawingProfile> = Object.freeze({
  titleBlockXFrac: 0.889,
  sheetNumber: /^S-?\d{1,4}(?:\.\d{1,3}){0,3}[A-Z]?$/,
  titleMinSize: 12,
  titleWindow: 300,
  titleStrip: /^DRAWING TITLE\s*/,
  sheetKinds: [
    { contains: "FOUNDATION PLAN", kind: "foundation" },
    { contains: "FRAMING PLAN", kind: "framing" },
    { contains: "ELEVATION", kind: "elevation" },
    { contains: "SCHEDULE", kind: "schedule" },
    { contains: "DETAIL", kind: "details" },
    { contains: "SECTION", kind: "sections" },
    { contains: "NOTES", kind: "notes" },
  ],
  notesHeadingWord: "NOTES",
  notesXFrac: 0.628,
  notesMargin: 12,
  gridLabel: /^(\d{1,2}(?:\.\d)?|[A-HJ-NP-Z](?:\.\d)?)$/,
  bubbleSize: [12, 30],
  bubblePairMinSep: 500,
  bubblePairTol: 6,
  footingMark: /^F\d{1,2}(?:\.\d{1,2})?[A-Z]?$/,
  pierMark: /^P-?\d{1,2}(?:\.\d)?$/,
  gradeBeamMark: /^(?:GB|TB)-?\d{1,2}$/,
  frameMarker: /^\*?(SMF|IMF|OMF|SCBF|OCBF|BRBF|EBF)$/,
  sfrsPrefix: "*",
  detailTypeMark: /\b([A-Z]{1,3}-\d{1,2}[A-Z]?)\b/,
  calloutNumber: /^\d{1,2}[A-Z]?$/,
  calloutMaxDist: 160,
  markMaxDist: 120,
}) as DrawingProfile;

export function resolveProfile(over?: Partial<DrawingProfile>): DrawingProfile {
  return { ...DEFAULT_PROFILE, ...(over ?? {}) };
}
