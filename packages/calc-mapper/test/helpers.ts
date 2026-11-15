import type { CalcPage, ElementRow, SerializedElementGraph } from "../src/index.ts";

/** A page whose words are laid out one per line position (boxes are dummies; spans are real). */
export function page(n: number, text: string): CalcPage {
  const words: CalcPage["words"] = [];
  let pos = 0;
  for (const line of text.split("\n")) {
    for (const w of line.split(" ")) {
      words.push([0, 0, 1, 1, pos, pos + w.length]);
      pos += w.length + 1;
    }
  }
  return { n, text, words, width: 612, height: 792, scanned: text.trim().length < 25 };
}

/**
 * A page with realistic word heights: lines starting with "# " are headings (12 pt tall), others body
 * (8 pt). The "# " marker is not part of the text.
 */
export function styledPage(n: number, lines: string[]): CalcPage {
  const words: CalcPage["words"] = [];
  const out: string[] = [];
  let pos = 0;
  let y = 40;
  for (const raw of lines) {
    const heading = raw.startsWith("# ");
    const line = heading ? raw.slice(2) : raw;
    const h = heading ? 12 : 8;
    y += h + 6;
    let x = 40;
    for (const w of line.split(" ")) {
      words.push([x, y - h, x + w.length * 5, y, pos, pos + w.length]);
      pos += w.length + 1;
      x += w.length * 5 + 5;
    }
    out.push(line);
  }
  const text = out.join("\n");
  return { n, text, words, width: 612, height: 792, scanned: text.trim().length < 25 };
}

export function el(global_id: string, cat: ElementRow["cat"], mark: string, profile = "", storey = "Level 2"): ElementRow {
  return {
    global_id, express_id: null, ifc_type: "IfcBeam", cat, mark, name: mark, type_name: "", profile, storey, params: {},
    geom: null, content_hash: global_id,
  };
}

type N = SerializedElementGraph["nodes"][number];
export function node(id: string, kind: string, extra: Partial<N> = {}): N {
  return { id, kind, params: {}, source: { format: "ifc", nativeId: 7, nativeType: "IfcBeam" }, tags: {}, links: [], ...extra };
}

export function graph(over: Partial<SerializedElementGraph> = {}): SerializedElementGraph {
  return {
    format: "unloaded.element-graph", version: 1, meta: null,
    levels: [{ id: "L2", name: "Level 2", elevation: 4.2 }],
    nodes: [
      node("B1", "beam", {
        mark: "2B1", name: "2B1", profile: "W18X35", levelId: "L2", params: { "Attr.ObjectType": "W18X35", "Pset.Span": 6.1 },
        geometry: { bbox: { min: [0, 0, 4], max: [6, 0.2, 4.4] }, axis: { start: [0, 0.1, 4.2], end: [6, 0.1, 4.2] } },
      }),
      node("K1", "connection", { mark: "ST-1", source: { format: "ifc", nativeType: "IfcPlate" } }),
      node("C1", "column", { mark: "C1", source: { format: "ifc", nativeType: "IfcColumn" } }),
      node("F1", "fastener", { source: { format: "ifc", nativeType: "IfcMechanicalFastener" } }),
      node("X1", "stair", { source: { format: "ifc", nativeType: "IfcStairFlight" } }),
    ],
    edges: [
      { id: "supports:B1->K1", kind: "supports", a: "B1", b: "K1", directed: true,
        evidence: [{ rule: "connection contact", source: "inferred", detail: { gap_m: 0.004 } }] },
      { id: "supports:K1->C1", kind: "supports", a: "K1", b: "C1", directed: true,
        evidence: [{ rule: "connection contact", source: "inferred", detail: { gap_m: 0 } }] },
      { id: "connects:B1|C1", kind: "connects", a: "B1", b: "C1", directed: false,
        evidence: [{ rule: "IfcRelConnectsElements", source: "explicit", detail: { ifcRelId: 9 } },
          { rule: "bbox contact", source: "inferred" }] },
    ],
    ...over,
  };
}
