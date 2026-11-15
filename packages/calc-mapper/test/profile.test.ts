import { describe, expect, it } from "vitest";
import { profileFromText as parserProfileFromText } from "../../ifc-parser/src/profile.ts";
import { GRAPH_SHA, el, page } from "./helpers.ts";
import { findSections, foldText, mapElements, normaliseProfile, profileFromText, segment } from "../src/index.ts";

/** Designations the model side (the parser's grammar) produces; the old calc-side regex missed most of them. */
const MODEL_FORMS = [
  "IPE 300", "HEA 200", "457X191X67 UB", "533X210X92UB", "UB 457x191x67", "C10X15.3", "L4X4X1/2", "HSS6X6X3/8", "W18X35",
  "HP12X53", "600 × 300",
];

describe("one section grammar for model profiles and calc text", () => {
  it.each(MODEL_FORMS)("the ported grammar matches packages/ifc-parser's profileFromText: %s", (s) => {
    expect(profileFromText([s])).toBe(parserProfileFromText([s]));
    expect(profileFromText([`beam ${s} ok`])).toBe(parserProfileFromText([`beam ${s} ok`]));
  });

  it.each(MODEL_FORMS)("calc text finds what the model side would carry: %s", (s) => {
    // rejects the old calc-side regex, which required "<prefix>NxN" and missed IPE 300, 457X191X67 UB, C10X15.3, L4X4X1/2 ...
    const line = foldText(`Beam B7 ${s} OK`);
    expect(findSections(line).map((h) => h.profile)).toEqual([parserProfileFromText([s])]);
  });

  it("finds a designation the model carries verbatim even where no text pattern describes it", () => {
    const known = new Set(["310UB40.4", "HSS6X6X.375"].map(normaliseProfile));
    const line = foldText("rafter 310UB40.4 and post HSS6X6X.375");
    expect(findSections(line, { known }).map((h) => [h.profile, line.slice(h.index, h.index + h.length)])).toEqual([
      ["310UB40.4", "310UB40.4"], ["HSS6X6X.375", "HSS6X6X.375"]]);
  });

  it("a token that is a model mark is a mark, not a size", () => {
    const line = foldText("hold-down HD1 at grid A");
    expect(findSections(line).map((h) => h.profile)).toEqual(["HD1"]);
    expect(findSections(line, { marks: new Set(["HD1"]), markOf: (s) => s })).toEqual([]);
  });

  it("an IPE 300 calc links by size (it fell through to the type tier before)", () => {
    const pages = [page(1, "BEAM DESIGN\ntypical beams IPE 300 at Level 2\nutilisation 0.81")];
    const links = mapElements([el("a", "Beam", "", normaliseProfile("IPE300"))], segment(pages), pages, GRAPH_SHA).links;
    expect(links.map((l) => [l.global_id, l.tier, l.token])).toEqual([["a", "size", "IPE 300"]]);
  });

  it("a mark line naming a different UB raises a size-mismatch finding (no size was found before)", () => {
    const pages = [page(1, "BEAM DESIGN\nbeam B7 533X210X92 UB OK")];
    const { findings } = mapElements([el("b", "Beam", "B7", "457X191X67UB")], segment(pages), pages, GRAPH_SHA);
    expect(findings.map((f) => [f.global_id, f.model_size, f.calc_size])).toEqual([["b", "457X191X67UB", "533X210X92UB"]]);
  });
});
