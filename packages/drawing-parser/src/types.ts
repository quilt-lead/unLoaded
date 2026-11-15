/**
 * Internal data of the drawing parser. Pure data, no classes.
 *
 * Page coordinates are PDF points with the origin top-left and y down (what
 * `extractPdfWords` in @unloaded/calc-mapper returns). Building coordinates are
 * feet internally (drawings are dimensioned in feet and inches) and become metres
 * only when the ModelInput is assembled.
 */

/** [x0, y0, x1, y1] in PDF points, top-left origin. */
export type Rect = [number, number, number, number];

/** One word on a page, with its real (rotation-aware) box. */
export interface DrawingWord {
  s: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  /** Reading direction, degrees counter-clockwise: 0 = left to right, 90 = bottom to top. */
  rot: number;
  /** Font size in points. */
  size: number;
}

export interface DrawingPage {
  /** File the page came from (one drawing set can be several PDFs). */
  file: string;
  /** 1-based page number within its file. */
  n: number;
  width: number;
  height: number;
  words: DrawingWord[];
}

/** Words of one text run on one baseline, joined by single spaces. */
export interface Phrase {
  text: string;
  words: DrawingWord[];
  rect: Rect;
  rot: number;
  size: number;
}

export type SheetKind =
  | "foundation" | "framing" | "elevation" | "schedule" | "details" | "sections" | "notes" | "other";

export interface Sheet {
  file: string;
  page: number;
  /** Sheet number as printed in the title block, e.g. "S-201". */
  number: string;
  title: string;
  kind: SheetKind;
  /** Level the sheet shows (plans only), as a display name, e.g. "Level 2", "Roof", "Foundation". */
  level?: string;
  numberRect: Rect;
  /** Right edge of the drawing area (left of the plan notes column or the title block). */
  cutoff: number;
  width: number;
  height: number;
}

/** How a printed appearance of an element was read. Same vocabulary as the synthetic registry truth. */
export type OccurrenceHow = "plan_tag" | "elevation_tag" | "schedule_row" | "detail_callout" | "note";

/**
 * One printed appearance of an element: the drawing-side half of two-sided evidence
 * (drawing box <-> calc box). Serialized into the element's `Drawing.Occurrences` param.
 */
export interface Occurrence {
  file: string;
  sheet: string;
  page: number;
  rect: Rect;
  how: OccurrenceHow;
  text: string;
}

/** A grid line on one sheet: `axis` "x" = a line of constant x (drawn vertically on a north-up plan). */
export interface SheetGridLine {
  label: string;
  axis: "x" | "y";
  /** Page coordinate of the line: x for axis "x", y for axis "y". */
  pos: number;
  rects: Rect[];
}

export type Vec3 = [number, number, number];
