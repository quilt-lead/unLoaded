/**
 * @unloaded/drawing-parser - structural drawing sets (PDF) -> ModelInput, for firms with plan
 * sheets but no IFC. The second model parser beside @unloaded/ifc-parser: buildGraph() consumes
 * its output the same way.
 *
 *   const model = await parseDrawingSet([{ name: "S-sheets.pdf", data: bytes }]);
 *   const { graph } = buildGraph(model);
 *
 * Runs in the browser and in Node (pass pdf.js's legacy build as `pdfjs` there).
 */
import type { ModelInput, ModelParser } from "@unloaded/element-graph/input";
import { parseDrawingSet, type DrawingParseOptions } from "./parse.ts";

export { parseDrawingSet, parseDrawingPages, readSheets } from "./parse.ts";
export type { DrawingParseOptions, DrawingFile } from "./parse.ts";
export { DEFAULT_PROFILE, resolveProfile, type DrawingProfile } from "./profile.ts";
export { memberTag, nominalSection, feetInches, phrases, levelName, type MemberTag } from "./text.ts";
export { SOURCE_FORMAT } from "./assemble.ts";
export type { DrawingPage, DrawingWord, Occurrence, OccurrenceHow, Rect, Sheet, SheetKind } from "./types.ts";

/** "%PDF-" */
export function hasPdfHeader(head: Uint8Array): boolean {
  return head.length >= 5 && head[0] === 0x25 && head[1] === 0x50 && head[2] === 0x44 && head[3] === 0x46 && head[4] === 0x2d;
}

/**
 * A PDF is a drawing set or a calc package; canParse cannot tell them apart from the header, so
 * the caller decides which parser gets a PDF. A PDF with no title-block sheet numbers parses to an
 * empty model with a warning per page.
 */
export const drawingParser: ModelParser<DrawingParseOptions> = {
  id: "drawing",
  extensions: ["pdf"],
  canParse(fileName: string, head?: Uint8Array): boolean {
    if (head && head.length > 0) return hasPdfHeader(head);
    return /\.pdf$/i.test(fileName);
  },
  parse(data: Uint8Array, options?: DrawingParseOptions & { fileName?: string }): Promise<ModelInput> {
    const { fileName, ...rest } = options ?? {};
    return parseDrawingSet([{ name: fileName ?? "drawings.pdf", data }], rest);
  },
};
