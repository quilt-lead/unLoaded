/**
 * @unloaded/calc-mapper - the calc engine, in the browser (and in Node for CI).
 *
 *   const text = await extractPdf(bytes);                      // pdf.js -> pages, words, spans
 *   const pkg = segmentCalcs(text.pages, "calcs.pdf");         // -> calcs (key, title, software, type, pages)
 *   const run = mapCalcs(graph, pkg);                          // graph = ElementGraph.serialize()
 *   const exp = buildExport(graph, pkg, run, decisions);       // the backend's /export shape
 *   const imp = impactOf(graph, pkg, run, decisions, gid, "remove");
 *   const cmp = diffGraphs(graphRev1, graphRev2);              // the backend's /compare shape
 *   decisions = addDecision(decisions, { global_id, calc_key, action: "confirm" });
 */
export * from "./types.ts";
export { extractPdf, rectsForSpan, buildPage, SCANNED_MAX_CHARS, type PdfjsLike, type PdfWord } from "./pdf.ts";
export { segment, segmentCalcs, titleOf, titleBox, catOfText, calcText, CAT_WORDS, TITLE_BOX_RULE } from "./segment.ts";
export { runMapping, CONF, XREF_CAP, normMark, dashless, normProfile, profileFrom } from "./matcher.ts";
export { inferCalcEdges } from "./calcdeps.ts";
export { propagate } from "./impact.ts";
export { diffGraphs, diffElements } from "./diff.ts";
export { addDecision, applyDecisions, effectiveDecisions, decisionLog, DECISION_ACTIONS } from "./decisions.ts";
export {
  parseGraph, graphElements, loadPath, connectivity, elementContentHash, GraphFormatError, GRAPH_FORMAT, GRAPH_VERSION,
} from "./elements.ts";
export { mapCalcs, buildState, buildExport, impactOf, statusOf, PALETTE } from "./project.ts";
export { sha1, sha1Json, canonicalJson } from "./hash.ts";
