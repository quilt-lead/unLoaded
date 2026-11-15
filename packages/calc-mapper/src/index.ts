/**
 * @unloaded/calc-mapper - the calc engine, in the browser (and in Node for CI).
 *
 *   const text = await extractPdf(bytes);                      // pdf.js -> pages, words, spans
 *   const pkg = segmentCalcs(text.pages, "calcs.pdf");         // -> calcs (key, title, software, type, pages)
 *   const run = await mapCalcs(graph, pkg);                    // graph = ElementGraph.serialize(); hashes the graph
 *   const exp = buildExport(graph, pkg, run, decisions);       // the backend's /export shape
 *   const imp = await impactOf(graph, pkg, run, decisions, gid, "remove");
 *
 * Every derived record carries `provenance` (provenance.ts); runs carry producer records with the
 * sha256 of the graph JSON and of the PDF bytes; quantities are `Quantity` (units.ts); rects are
 * sheet-frame and graph geometry model-metre types (frames.ts).
 *   const cmp = diffGraphs(graphRev1, graphRev2);              // the backend's /compare shape
 *   decisions = addDecision(decisions, { global_id, calc_key, action: "confirm" });
 *   const b = parseBundle(json);                               // model bundle: element graph + calc graph in one file
 *   const exp2 = await bundleExport(b.elementGraph, b.calcGraph!, decisions);
 */
export * from "./types.ts";
export {
  extractPdf, extractPdfWords, rectsForSpan, buildPage, SCANNED_MAX_CHARS, type PdfjsLike, type PdfWord, type PdfWordsPage,
} from "./pdf.ts";
export { segment, segmentCalcs, uniqueKeys, isFrontMatter, FRONT_HEADING, packageSha256, titleOf, titleBox, catOfText, calcText, calcRegions, pageParts, CAT_WORDS, TITLE_BOX_RULE, HEADING_RATIO, TITLE_HEIGHT_RATIO } from "./segment.ts";
export {
  runMapping, mapElements, typicalGroups, groupId, bandOf, CONF, XREF_CAP, WEIGHTS, BANDS, normMark, dashless, normProfile, profileFrom,
  type MappingResult,
} from "./matcher.ts";
export { normaliseProfile, profileFromText, findSections, isDesignation, PROFILE_PATTERNS, CALC_SECTION_PATTERNS, type SectionHit } from "./profile.ts";
export { calcPackageProblem, isCalcPackage } from "./package.ts";
export { foldText, DASHES } from "./text.ts";
export { inferCalcEdges, designerOf, pageReferences, runningLines, RUNNING_BAND, type PageReference } from "./calcdeps.ts";
export { propagate } from "./impact.ts";
export { diffGraphs, diffElements } from "./diff.ts";
export { addDecision, applyDecisions, decisionFrom, effectiveDecisions, decisionLog } from "./decisions.ts";
export {
  parseGraph, graphElements, loadPath, connectivity, elementContentHash, diffFields, type DiffFields, GraphFormatError, GRAPH_FORMAT, GRAPH_VERSION,
} from "./elements.ts";
export { mapCalcs, runProducers, buildState, buildExport, impactOf, statusOf, packageOf, PALETTE, type CalcInput } from "./project.ts";
export {
  buildCalcSet, calcRef, parseCalcRef, isCalcSet, setPageOf, docPageOf, documentShas, documentStem, resolveRevisionTarget, diffCalcSets,
  CALC_REF_SEP, KEY_OVERLAP_MIN,
  type CalcSet, type CalcSetDoc, type CalcSetDocument, type KnownDocument, type RevisionTarget, type CalcSetDiff, type CalcDiffEntry,
} from "./calcset.ts";
export {
  BUNDLE_FORMAT, BUNDLE_VERSION, BundleFormatError, isBundle, parseBundle, makeBundle, bundleExport, bundleDecisions, exportToCalcGraph,
  type ModelBundle, type BundleMeta, type BundleCalcGraph, type BundleCalcSource, type BundleDocument, type BundleCalc, type BundleCalcEdge,
  type BundleLink, type BundleReview,
} from "./bundle.ts";
export { sha1, sha1Json, sha256, sha256Json, SHA256_HEX, canonicalJson } from "./hash.ts";
export {
  PACKAGE_NAME, PACKAGE_VERSION, RULES, producerOf, inputList, ruleProvenance, estimateProvenance, humanProvenance,
} from "./provenance.ts";
export { UNITS, ALIASES, UnknownUnit, UnitMismatch, canonicalUnit, dimensionOf, convert, q, to, unitFromKey } from "./units.ts";
export { sheetRect, modelPointM, buildingPointFt } from "./frames.ts";
