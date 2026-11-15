import { describe, expect, it } from "vitest";
import { CONF, XREF_CAP, runMapping, segment } from "../src/index.ts";
import { el, page } from "./helpers.ts";

describe("mapping tiers (rules unchanged from the reference engine)", () => {
  it("finds range, exact, loose-as-xref, partial and size links", () => {
    const pages = [page(1, "HEADER LINE\nBEAM DESIGN - RAM STEEL\nbeams 2B1 - 2B3 and SL2\n2B9 W18X35\nCB1 see hand calc")];
    const calcs = segment(pages);
    const els = [el("a", "Beam", "2B1"), el("b", "Beam", "2B2"), el("c", "Beam", "2B9"), el("s", "Slab", "SL-2"),
      el("k", "Beam", "2CB1"), el("u", "Beam", "", "W18X35")];
    const got = new Map(runMapping(els, calcs, pages).map((l) => [`${l.global_id}:${l.tier}`, l]));
    expect(got.get("a:range")?.conf).toBe(CONF.range);
    expect(got.has("b:range")).toBe(true);
    expect(got.get("c:exact")?.conf).toBe(CONF.exact);
    expect(got.get("s:xref")?.conf).toBe(XREF_CAP); // slab mark ignoring punctuation, but in a beam calc
    expect(got.get("k:partial")?.conf).toBe(CONF.partial);
    expect(got.get("u:size")?.conf).toBe(CONF.size);
    const c = got.get("c:exact")!;
    expect(c.token).toBe("2B9");
    expect(pages[0]!.text.slice(c.span![0], c.span![1])).toBe("2B9");
    expect(c.snippet?.match).toBe("2B9");
  });

  it("never maps scanned pages or front matter", () => {
    const pages = [page(1, "Design criteria .... 2\nBeams .... 3\nColumns .... 4"), page(2, "")];
    const calcs = segment(pages);
    expect(calcs[0]!.front).toBe(true);
    expect(calcs[1]!.scanned).toBe(true);
    expect(runMapping([el("a", "Beam", "B1")], calcs, pages)).toEqual([]);
  });

  it("software named in the title wins; type falls back to the line under the title", () => {
    const pages = [page(1, "JOB 1 - SAMPLE\nFLOOR DESIGN - RAM STRUCTURAL SYSTEM\nTypical girders\nslab reactions from RAM Concept")];
    const [c] = segment(pages);
    expect(c!.software).toBe("RAM Structural System");
    expect(c!.cat).toBe("Beam");
    expect(c!.title_box.note).toBe("title line words");
  });

  it("type tier covers unclaimed elements of a calc that names no marks or sizes", () => {
    const pages = [page(1, "COLUMN DESIGN CHECK\ntypical columns, all levels")];
    const links = runMapping([el("c1", "Column", ""), el("b1", "Beam", "")], segment(pages), pages);
    expect(links.map((l) => [l.global_id, l.tier, l.conf])).toEqual([["c1", "type", CONF.type]]);
  });
});
