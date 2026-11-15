/**
 * A small project built in the test, in memory: two element-graph revisions and two calc PDFs written
 * here byte by byte (Helvetica, no embedded fonts), so no generated PDF is committed and the suites
 * need nothing generated (the synthetic package in tools/calcgraph-reference is gitignored).
 * Marks and sizes follow the synthetic package's conventions (tools/calcgraph-reference/synth):
 * calc titles "<KIND> DESIGN CHECK", design lines naming mark + section + storey, a "see page"
 * reference, a loads-only line, and one planted size mismatch (calc says W12X40, model W12X53). The
 * supplement PDF designs the shear tabs and mentions beam B-101 (designed in the main PDF): a
 * cross-reference across the two PDFs.
 */
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { CalcPackage, SerializedElementGraph } from "@unloaded/calc-mapper";
import { makeProjectFile, type InputDecision } from "../scripts/makeProjectFile.ts";
import type { ProjectFile } from "@unloaded/project-file";

// ------------------------------------------------------------------ PDF

export { minimalPdf, type PdfLine } from "../scripts/minimalPdf.ts";
import { minimalPdf, type PdfLine } from "../scripts/minimalPdf.ts";

export const CALC_PDF_PAGES: PdfLine[][] = [
  [
    { text: "BEAM DESIGN CHECK", size: 16 },
    { text: "Beam B-101 W18X35 Level 2 design OK", size: 10 },
    { text: "Span 5.7 m, flexure ratio 0.62 OK", size: 10 },
    { text: "Reactions to columns, see page 2", size: 10 },
  ],
  [
    { text: "COLUMN DESIGN CHECK", size: 16 },
    { text: "Column C-1 W12X53 Level 1 design OK", size: 10 },
    { text: "Column C-2 W12X40 Level 1 design OK", size: 10 },
    { text: "Loads from beam B-101 reactions", size: 10 },
  ],
];

/** A second calc PDF: the connection calcs, which take beam B-101's reactions from the main package. */
export const SUPPLEMENT_PDF_PAGES: PdfLine[][] = [
  [
    { text: "CONNECTION DESIGN CHECK", size: 16 },
    { text: "Shear tab ST-1 Level 2 design OK", size: 10 },
    { text: "Shear tab ST-2 Level 2 design OK", size: 10 },
    { text: "End reactions from beam B-101 per beam design", size: 10 },
  ],
];

/**
 * A two-PDF pair that exercises every cross-PDF rule (test/multipdf.test.ts, and the parity script's
 * --two-pdf mode has its own on the synthetic marks):
 *   - B-101 is designed in BOTH PDFs (main "beam-design-check" and "supplement-b/beam-design-check",
 *     same tier and confidence): `designerOf` over every PDF's links picks ONE designer (the smaller
 *     calc key), so the supplement's mention of B-101 gets one fed-by edge, not two;
 *   - the supplement says "see page 2" (its own page 2): resolved in the supplement only. In a combined
 *     view whose page-reference rule were not switched off it would hit the MAIN PDF's page 2;
 *   - the main column calc says "carried to shear tab ST-2" (designed only in the supplement, on ITS
 *     page 2): the "to" cue is read from the main PDF's page 2. Were the combined view's page numbers
 *     not offset, the supplement's page 2 would be read instead and the edge would point the other way.
 */
export const CROSS_MAIN_PDF_PAGES: PdfLine[][] = [
  CALC_PDF_PAGES[0]!,
  [...CALC_PDF_PAGES[1]!, { text: "Column C-2 reactions carried to shear tab ST-2", size: 10 }],
];
export const CROSS_SUPPLEMENT_PDF_PAGES: PdfLine[][] = [
  [
    { text: "BEAM DESIGN CHECK", size: 16 },
    { text: "Beam B-101 W18X35 Level 2 design OK", size: 10 },
    { text: "Shear tab loads, see page 2", size: 10 },
  ],
  [
    { text: "CONNECTION DESIGN CHECK", size: 16 },
    { text: "Shear tab ST-2 Level 2 design OK", size: 10 },
    { text: "End reactions from beam B-101 per beam design", size: 10 },
  ],
];

// ------------------------------------------------------------------ element graphs

type Node = SerializedElementGraph["nodes"][number];
type Edge = SerializedElementGraph["edges"][number];

function node(id: string, kind: string, nativeType: string, extra: Partial<Node>): Node {
  return { id, kind, params: {}, source: { format: "ifc", nativeId: id.length, nativeType }, tags: {}, links: [], ...extra };
}
const sup = (a: string, b: string, rule: string): Edge =>
  ({ id: `supports:${a}->${b}`, kind: "supports", a, b, directed: true, evidence: [{ rule, source: "inferred", detail: { gap_m: 0 } }] });
const con = (a: string, b: string, rule: string, explicit = false): Edge => {
  const [x, y] = a < b ? [a, b] : [b, a];
  return { id: `connects:${x}|${y}`, kind: "connects", a: x, b: y, directed: false, evidence: [{ rule, source: explicit ? "explicit" : "inferred" }] };
};

const column = (id: string, mark: string, x: number, profile: string): Node => node(id, "column", "IfcColumn", {
  mark, name: mark, profile, levelId: "L1",
  params: { "Attr.ObjectType": profile, "Structural.Grid": `${mark === "C-1" ? "A" : "B"}/1`, "Identity Data.Mark": mark },
  geometry: { bbox: { min: [x - 0.15, -0.15, 0], max: [x + 0.15, 0.15, 4] }, axis: { start: [x, 0, 0], end: [x, 0, 4] }, section: { depth: 0.3, width: 0.3 } },
});

/** Revision 1: two columns on footings, one beam between them through two shear-tab connections. */
export function graphRev1(): SerializedElementGraph {
  return {
    format: "unloaded.element-graph", version: 1, meta: { version: 1, units: "m", source: { format: "ifc", file: "test_rev1.ifc" } },
    levels: [{ id: "L0", name: "Foundation", elevation: -1 }, { id: "L1", name: "Level 1", elevation: 0 }, { id: "L2", name: "Level 2", elevation: 4 }],
    nodes: [
      column("C1", "C-1", 0, "W12X53"),
      column("C2", "C-2", 6, "W12X53"),
      node("B1", "beam", "IfcBeam", {
        mark: "B-101", name: "B-101", profile: "W18X35", levelId: "L2",
        params: { "Attr.ObjectType": "W18X35", "Structural.Grid": "A-B/1", "Identity Data.Mark": "B-101" },
        geometry: { bbox: { min: [0.15, -0.1, 3.55], max: [5.85, 0.1, 4] }, axis: { start: [0.15, 0, 3.78], end: [5.85, 0, 3.78] }, section: { depth: 0.45, width: 0.15 } },
      }),
      node("K1", "connection", "IfcPlate", { mark: "ST-1", name: "Shear tab ST-1", levelId: "L2", geometry: { bbox: { min: [0.15, -0.01, 3.6], max: [0.3, 0.01, 3.9] } } }),
      node("K2", "connection", "IfcPlate", { mark: "ST-2", name: "Shear tab ST-2", levelId: "L2", geometry: { bbox: { min: [5.7, -0.01, 3.6], max: [5.85, 0.01, 3.9] } } }),
      node("F1", "footing", "IfcFooting", { mark: "F-1", name: "F-1", levelId: "L0", geometry: { bbox: { min: [-0.75, -0.75, -0.6], max: [0.75, 0.75, 0] } } }),
      node("F2", "footing", "IfcFooting", { mark: "F-2", name: "F-2", levelId: "L0", geometry: { bbox: { min: [5.25, -0.75, -0.6], max: [6.75, 0.75, 0] } } }),
    ],
    edges: [
      sup("B1", "K1", "connection contact"), sup("K1", "C1", "connection contact"),
      sup("B1", "K2", "connection contact"), sup("K2", "C2", "connection contact"),
      sup("C1", "F1", "column bottom bears on support"), sup("C2", "F2", "column bottom bears on support"),
      con("B1", "K1", "connection contact"), con("K1", "C1", "connection contact", true),
      con("B1", "K2", "connection contact"), con("K2", "C2", "connection contact"),
      con("C1", "F1", "column bottom bears on support"), con("C2", "F2", "column bottom bears on support"),
    ],
  };
}

/** Revision 2: C-2 resized to W12X65 and footing F-2 removed. */
export function graphRev2(): SerializedElementGraph {
  const g = graphRev1();
  g.meta = { version: 1, units: "m", source: { format: "ifc", file: "test_rev2.ifc" } };
  g.nodes = g.nodes.filter((n) => n.id !== "F2").map((n) => (n.id === "C2" ? { ...n, profile: "W12X65", params: { ...n.params, "Attr.ObjectType": "W12X65" } } : n));
  g.edges = g.edges.filter((e) => e.a !== "F2" && e.b !== "F2");
  return g;
}

// ------------------------------------------------------------------ project file

/**
 * A project file in the app's format: model rev 1 (id 1), the calc PDF (id 2), model rev 2 (id 3) -
 * heads 3 and 2. `stripExtraction` drops the document hashes from the stored extraction, as an
 * extraction saved before the provenance contract has none.
 */
export async function buildProjectFile(opts: { decisions?: InputDecision[]; stripExtraction?: boolean } = {}): Promise<{ file: ProjectFile; pdf: Uint8Array }> {
  const pdf = minimalPdf(CALC_PDF_PAGES);
  const enc = (v: unknown) => new TextEncoder().encode(JSON.stringify(v));
  const file = await makeProjectFile({
    name: "Test frame",
    revisions: [
      { kind: "model", name: "test_rev1.graph.json", bytes: enc(graphRev1()), label: "rev 1" },
      { kind: "calcs", name: "test_calcs.pdf", bytes: pdf, label: "calcs" },
      { kind: "model", name: "test_rev2.graph.json", bytes: enc(graphRev2()), label: "rev 2" },
    ],
    decisions: opts.decisions ?? [],
  });
  if (opts.stripExtraction) {
    const c = file.revisions.find((r) => r.kind === "calcs")!;
    const pkg = c.extraction as CalcPackage;
    c.extraction = { ...pkg, source_sha256: undefined, pages: pkg.pages.map(({ doc_sha256: _d, ...pg }) => pg) };
  }
  return { file, pdf };
}

/** Write a project file to a fresh temp directory; returns its path. */
export function writeTemp(file: ProjectFile, name = "test.calcgraph.json"): string {
  const dir = mkdtempSync(join(tmpdir(), "unloaded-mcp-"));
  const path = join(dir, name);
  writeFileSync(path, JSON.stringify(file));
  return path;
}

/** The fixture project as files in a fresh temp directory: two graph revisions, the two calc PDFs and the cross-PDF pair. */
export function writeFixtureFiles(): { dir: string; rev1: string; rev2: string; main: string; supplement: string; crossMain: string; crossSupplement: string } {
  const dir = mkdtempSync(join(tmpdir(), "unloaded-mcp-fixture-"));
  const put = (name: string, bytes: Uint8Array | string) => {
    const path = join(dir, name);
    writeFileSync(path, bytes);
    return path;
  };
  return {
    dir,
    rev1: put("test_rev1.graph.json", JSON.stringify(graphRev1())),
    rev2: put("test_rev2.graph.json", JSON.stringify(graphRev2())),
    main: put("test_calcs.pdf", minimalPdf(CALC_PDF_PAGES)),
    supplement: put("Supplement A.pdf", minimalPdf(SUPPLEMENT_PDF_PAGES)),
    crossMain: put("cross_calcs.pdf", minimalPdf(CROSS_MAIN_PDF_PAGES)),
    crossSupplement: put("Supplement B.pdf", minimalPdf(CROSS_SUPPLEMENT_PDF_PAGES)),
  };
}
