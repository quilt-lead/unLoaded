/**
 * A small synthetic project built in the test, in memory: two element-graph revisions and a two-page
 * calc PDF written here byte by byte (Helvetica, no embedded fonts), so no generated PDF is committed.
 * Marks and sizes follow the synthetic package's conventions (tools/calcgraph-reference/synth):
 * calc titles "<KIND> DESIGN CHECK", design lines naming mark + section + storey, a "see page" cross
 * reference, a loads-only line, and one planted size mismatch (calc says W12X40, model W12X53).
 */
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { CalcPackage, SerializedElementGraph } from "@unloaded/calc-mapper";
import { makeProjectFile, type InputDecision } from "../src/makeProjectFile.ts";
import type { ProjectFile } from "../src/projectFile.ts";

// ------------------------------------------------------------------ PDF

export interface PdfLine {
  text: string;
  size: number;
}

const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");

/** A minimal valid PDF (US Letter pages, Helvetica), one text line per entry, top to bottom. */
export function minimalPdf(pages: PdfLine[][]): Uint8Array {
  const objs: string[] = [];
  const pageIds = pages.map((_, i) => 4 + i * 2);
  objs[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objs[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pages.length} >>`;
  objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>";
  pages.forEach((lines, i) => {
    let y = 740;
    const ops = lines.map((l) => {
      const s = `BT /F1 ${l.size} Tf 50 ${y} Td (${esc(l.text)}) Tj ET`;
      y -= l.size + 10;
      return s;
    }).join("\n");
    const pid = pageIds[i]!, cid = pid + 1;
    objs[pid] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${cid} 0 R >>`;
    objs[cid] = `<< /Length ${ops.length} >>\nstream\n${ops}\nendstream`;
  });
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (let id = 1; id < objs.length; id++) {
    offsets[id] = out.length;
    out += `${id} 0 obj\n${objs[id]}\nendobj\n`;
  }
  const xref = out.length;
  out += `xref\n0 ${objs.length}\n0000000000 65535 f \n`;
  for (let id = 1; id < objs.length; id++) out += `${String(offsets[id]).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objs.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return new TextEncoder().encode(out);
}

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
