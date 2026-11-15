/**
 * Loading calcs (gravity, wind, seismic, load combinations) design no element; they feed other calcs.
 * The segmenter files them under the "Loading" category, and calcdeps rule 3 joins them to the calcs
 * that cite their sheet number.
 */
import { describe, expect, it } from "vitest";
import { calcCatOf, inferCalcEdges, runMapping, segment, sheetOf } from "../src/index.ts";
import { GRAPH_SHA, el, page } from "./helpers.ts";

describe("Loading calc category", () => {
  it.each([
    ["S-001 Gravity Load Criteria", "Loading"],
    ["S-002 Wind Load Analysis", "Loading"],
    ["Seismic Loads - ASCE 7-16", "Loading"],
    ["S-004 Load Combinations Schedule", "Loading"],
    ["Column Load Takedown", "Column"],
    ["Wind Load Analysis - Braced Frames", "Brace"],
    ["Beam Design", "Beam"],
    ["Design Criteria", ""],
  ])("%s -> %s", (title, cat) => {
    expect(calcCatOf(title)).toBe(cat);
  });

  it("links no elements to a Loading calc that names none", () => {
    const pages = [page(1, "S-001 GRAVITY LOAD CRITERIA\nSuperimposed dead load 15 psf, office live load 50 psf")];
    const calcs = segment(pages);
    expect(calcs.map((c) => c.cat)).toEqual(["Loading"]);
    expect(runMapping([el("b1", "Beam", "2B1", "W18X35")], calcs, pages, GRAPH_SHA)).toEqual([]);
  });
});

describe("calc reference by sheet number (calcdeps rule 3)", () => {
  it("reads a sheet number only from the start of a title", () => {
    expect(sheetOf("S-001 Gravity Load Criteria")).toBe("S-001");
    expect(sheetOf("SK-12A Wind Load Analysis")).toBe("SK-12A");
    expect(sheetOf("L01 Composite Slab Design")).toBeNull();
    expect(sheetOf("Gravity Load Criteria S-001")).toBeNull();
  });

  const pages = [
    page(1, "S-001 GRAVITY LOAD CRITERIA\nSDL 15 psf, LL 50 psf"),
    page(2, "S-003 SEISMIC LOAD ANALYSIS\nSeismic weight from S-001\nStorey forces carried to S-201"),
    page(3, "S-201 BEAM DESIGN\nbeam 2B1 W18X35 ok\nDesign loads per S-001\nSee S-0012 and XS-001 (not sheets here)"),
    page(4, "S-102 PILE CAP DESIGN - GRID A1\nLoads per S-001"),
    page(5, "S-102 PILE CAP DESIGN - GRID A2\nCap reaction per S-102"),
  ];
  const calcs = segment(pages);
  const key = (title: string) => calcs.find((c) => c.title.toUpperCase().startsWith(title))!.key;
  const edges = inferCalcEdges(calcs, pages, []);
  const pairs = edges.map((e) => [e.src, e.dst]);

  it("takes a cited calc's output as input; a 'to' cue reverses it", () => {
    expect(pairs).toContainEqual([key("S-001"), key("S-003")]);
    expect(pairs).toContainEqual([key("S-001"), key("S-201")]);
    expect(pairs).toContainEqual([key("S-003"), key("S-201")]);
    expect(pairs).toContainEqual([key("S-001"), key("S-102 PILE CAP DESIGN - GRID A1")]);
  });

  it("does not resolve a sheet number two calcs share, a longer token, or a self mention", () => {
    expect(edges).toHaveLength(4);
    for (const e of edges) {
      expect(e.provenance.rule).toBe("calcdeps.calc-reference");
      expect(e.evidence[0]!.rects!.length).toBeGreaterThan(0);
    }
  });
});
