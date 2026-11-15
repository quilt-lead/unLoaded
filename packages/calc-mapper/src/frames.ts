/**
 * Coordinate frames as types. Port of the reference schema's frames.py, at the type level: a
 * coordinate never travels without its frame, and one frame cannot be passed where another is
 * expected - the compiler refuses it.
 *
 *   SheetRect      [x0, y0, x1, y1] in PDF points on ONE page of the calc package (pdf.js / PyMuPDF
 *                  page space: origin top-left, y down). The page is the record's `page` field; the
 *                  document is the calc package (its sha256 is in the run's producer records).
 *   ModelPointM    [x, y, z] world metres of the element graph (the graph's meta.units is "m").
 *   BuildingPointFt [x, y, z] plan feet of a building read off its drawings. No producer in this
 *                  package yet (drawing-set ingest, D18 item 3); declared so the frame exists before
 *                  the first value does.
 *
 * The brand is type-level only: in JSON every one of these is a plain array of numbers, so the
 * export the UI reads is unchanged. There is no conversion between frames here; as in frames.py, a
 * registration between frames exists only where a measured relation does, and none is measured yet.
 */

declare const FRAME: unique symbol;

/** `T` tagged with the frame its numbers are in. */
export type Framed<T, F extends string> = T & { readonly [FRAME]: F };

/** A box in PDF points on one calc page: [x0, y0, x1, y1], origin top-left, y down. */
export type SheetRect = Framed<[number, number, number, number], "sheet-pt">;
/** A point in the element graph's world metres: [x, y, z]. */
export type ModelPointM = Framed<number[], "model-m">;
/** A point in a building's plan feet: [x, y, z]. */
export type BuildingPointFt = Framed<number[], "building-ft">;

/** A sheet rect from four PDF-point numbers. */
export const sheetRect = (x0: number, y0: number, x1: number, y1: number): SheetRect => [x0, y0, x1, y1] as SheetRect;

/** A model point from metre coordinates (copied). */
export const modelPointM = (xyz: readonly number[]): ModelPointM => [...xyz] as ModelPointM;

/** A building point from plan-feet coordinates (copied). */
export const buildingPointFt = (xyz: readonly number[]): BuildingPointFt => [...xyz] as BuildingPointFt;
