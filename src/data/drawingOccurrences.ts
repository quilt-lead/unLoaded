// Where an element is printed on its drawing set: the element's `Drawing.Occurrences` param (written by
// @unloaded/drawing-parser, see its README "Occurrences") read into typed targets for the drawing evidence card.
// Params reach the view as strings, so the array arrives as a JSON string; anything malformed is dropped, never
// thrown: an element from an IFC model (no such param) or a damaged one simply has no drawing evidence.
import type { PdfRect } from '../types/bim';

export type OccurrenceHow = 'plan_tag' | 'elevation_tag' | 'schedule_row' | 'detail_callout' | 'note';

/** One printed appearance of an element: a box on a page of a drawing PDF. */
export interface DrawingOccurrence {
  /** drawing PDF file name (the model revision's source file) */
  file: string;
  /** sheet number from the title block, e.g. "S2.0.2" */
  sheet: string;
  /** 1-based page within `file` */
  page: number;
  /** [x0, y0, x1, y1] in PDF points, top-left origin (the calc evidence convention) */
  rect: PdfRect;
  how: OccurrenceHow;
  /** the printed text, e.g. "W16x26" or a schedule row */
  text: string;
}

export const OCCURRENCES_PARAM = 'Drawing.Occurrences';

export const HOW_LABEL: Record<OccurrenceHow, string> = {
  plan_tag: 'Plan tag',
  elevation_tag: 'Elevation tag',
  schedule_row: 'Schedule row',
  detail_callout: 'Detail callout',
  note: 'Note',
};

const HOWS = new Set<string>(Object.keys(HOW_LABEL));

function asOccurrence(v: unknown): DrawingOccurrence | null {
  if (typeof v !== 'object' || v === null) return null;
  const o = v as Record<string, unknown>;
  const { file, sheet, page, rect, how, text } = o;
  if (typeof file !== 'string' || !file) return null;
  if (typeof page !== 'number' || !Number.isInteger(page) || page < 1) return null;
  if (typeof how !== 'string' || !HOWS.has(how)) return null;
  if (!Array.isArray(rect) || rect.length !== 4 || !rect.every((n) => typeof n === 'number' && Number.isFinite(n))) return null;
  const [x0, y0, x1, y1] = rect as number[];
  if (!(x1! > x0! && y1! > y0!)) return null;
  return {
    file,
    sheet: typeof sheet === 'string' ? sheet : '',
    page,
    rect: [x0!, y0!, x1!, y1!],
    how: how as OccurrenceHow,
    text: typeof text === 'string' ? text : '',
  };
}

/**
 * An element's printed occurrences, in the parser's order (plan / elevation tags first, then schedule rows,
 * callouts, notes). Missing param, invalid JSON, a non-array or invalid entries: those give nothing.
 */
export function readOccurrences(params: Record<string, string> | undefined | null): DrawingOccurrence[] {
  const raw = params?.[OCCURRENCES_PARAM];
  if (typeof raw !== 'string' || !raw.trim()) return [];
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(data)) return [];
  return data.map(asOccurrence).filter((o): o is DrawingOccurrence => o !== null);
}

/** The occurrences that can be shown: those whose drawing PDF is loaded (`urls` by file name), with that URL. */
export function shownOccurrences(occ: DrawingOccurrence[], urls: Record<string, string> | undefined): (DrawingOccurrence & { url: string })[] {
  if (!urls) return [];
  return occ.flatMap((o) => (urls[o.file] ? [{ ...o, url: urls[o.file]! }] : []));
}

/**
 * The crop to show around a box: the box plus `pad` on every side, grown to at least `minW` x `minH` and to the
 * frame's aspect ratio (width / height), centred on the box, so a short tag still shows its member line and the
 * nearby grid while a long schedule row is shown whole.
 */
export function cropAround(rect: PdfRect, opts: { pad?: number; minW?: number; minH?: number; aspect?: number } = {}): PdfRect {
  const { pad = 24, minW = 220, minH = 140, aspect = 1.5 } = opts;
  const [x0, y0, x1, y1] = rect;
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  let w = Math.max(x1 - x0 + 2 * pad, minW);
  let h = Math.max(y1 - y0 + 2 * pad, minH);
  if (w / h > aspect) h = w / aspect;
  else w = h * aspect;
  return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2];
}
