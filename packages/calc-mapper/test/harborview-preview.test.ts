import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import { calcText, extractPdf, mapElements, segmentCalcs, type ElementRow, type PdfjsLike } from "../src/index.ts";

const previewPdf = new URL("../../../data/harborview/harborview-demo-calcs-preview.pdf", import.meta.url);
const harborviewBundle = new URL("../../../data/harborview/harborview-tower-rev1-base.bundle.json", import.meta.url);

describe("Harborview synthetic PDF preview", () => {
  it("segments four sheets and matches their marks to the Harborview model", async () => {
    const pdfjsModule = await import("pdfjs-dist/legacy/build/pdf.mjs");
    const pdfjs: PdfjsLike = { getDocument: (source) => pdfjsModule.getDocument(source) };
    const { pages } = await extractPdf(new Uint8Array(await readFile(previewPdf)), { pdfjs });
    const pkg = segmentCalcs(pages, "harborview-demo-calcs-preview.pdf");
    const calcs = pkg.calcs.filter((calc) => !calc.front);
    const bundle = JSON.parse(await readFile(harborviewBundle, "utf8")) as {
      elementGraph: {
        nodes: Array<{
          id: string;
          kind: string;
          mark?: string;
          name?: string;
          profile?: string;
          levelId?: string;
          source?: { nativeType?: string };
        }>;
      };
    };
    const expectedIds = new Set([
      "pcap-A1",
      "pile-A1",
      "girder-A1-B1-L01",
      "girder-B1-C1-L01",
      "girder-C1-D1-L01",
      "girder-D1-E1-L01",
      "col-A1-L01",
      "col-A1-L02",
      "col-A1-L03",
      "col-A1-L04",
      "col-A1-L05",
    ]);
    const categories: Record<string, ElementRow["cat"]> = {
      beam: "Beam",
      column: "Column",
      connection: "Connection",
      footing: "Footing",
      pile: "Pile",
    };
    const elements: ElementRow[] = bundle.elementGraph.nodes
      .filter((node) =>
        (expectedIds.has(node.id) || (node.kind === "connection" && node.mark?.startsWith("BP-"))) &&
        typeof node.mark === "string",
      )
      .map((node) => ({
        global_id: node.id,
        express_id: null,
        ifc_type: node.source?.nativeType ?? "IfcBuildingElementProxy",
        cat: categories[node.kind] ?? "Other",
        mark: node.mark ?? "",
        name: node.name ?? node.mark ?? "",
        type_name: "",
        profile: node.profile ?? "",
        storey: node.levelId ?? "",
        params: {},
        geom: null,
        content_hash: node.id,
      }));
    const textFor = (prefix: string) => {
      const calc = calcs.find((item) => item.title.startsWith(prefix));
      if (!calc) throw new Error(`Missing calc sheet: ${prefix}`);
      return calcText(pkg, calc);
    };

    expect(pkg.calcs.filter((calc) => calc.front)).toHaveLength(1);
    expect(calcs).toHaveLength(4);
    expect(textFor("S-102 Pile Cap")).toContain("CapA1");
    expect(textFor("S-102 Pile Cap")).toContain("PileP-A1");
    expect(textFor("S-302 L01 Grid Line 1")).toContain("G-A1B1-L01");
    expect(textFor("S-501 Column Stack C-01")).toContain("C-01-L05");
    expect(textFor("S-405 Column Base Plate")).toContain("BP-E4");

    const mapping = mapElements(elements, calcs, pkg.pages, "a".repeat(64));
    const expectLink = (elementId: string, titlePrefix: string, tier: "exact" | "xref") => {
      const calc = calcs.find((item) => item.title.startsWith(titlePrefix));
      if (!calc) throw new Error(`Missing calc sheet: ${titlePrefix}`);
      const link = mapping.links.find((item) => item.global_id === elementId && item.calc_key === calc.key);
      expect(link?.tier, `${elementId} should map to ${calc.title}`).toBe(tier);
    };
    expectLink("pcap-A1", "S-102 Pile Cap", "exact");
    expectLink("pile-A1", "S-102 Pile Cap", "xref");
    expectLink("girder-A1-B1-L01", "S-302 L01 Grid Line 1", "exact");
    expectLink("col-A1-L05", "S-501 Column Stack C-01", "exact");
    expectLink("conn-bp-E4", "S-405 Column Base Plate", "exact");
  });
});
