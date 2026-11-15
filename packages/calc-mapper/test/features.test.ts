import { describe, expect, it } from "vitest";
import { normaliseProfile as parserNormalise } from "../../ifc-parser/src/profile.ts";
import { BANDS, CONF, WEIGHTS, bandOf, mapElements, normaliseProfile, pageParts, segment } from "../src/index.ts";
import { el, page, styledPage } from "./helpers.ts";

describe("profile normaliser", () => {
  it.each(["W12x26", " hea 200 ", "600 × 300", "HSS6x6x3/8", "W 18 X 35", "305x165x40 UB", "w14*90"])(
    "matches packages/ifc-parser's normaliseProfile: %s",
    (s) => expect(normaliseProfile(s)).toBe(parserNormalise(s)),
  );
});

describe("link role", () => {
  const pages = [page(1, "GIRDER 3G1 SPOT CHECK\nGirder 3G1 W18X35 design check OK\nLoads: reactions from beams 3B1 - 3B2")];
  const els = [el("g", "Beam", "3G1", "W18X35", "Level 3"), el("b1", "Beam", "3B1"), el("b2", "Beam", "3B2")];
  const { links } = mapElements(els, segment(pages), pages);
  const role = (g: string) => links.find((l) => l.global_id === g)?.role;

  it("is design for the member the calc checks, loads for members it only takes reactions from", () => {
    expect(role("g")).toBe("design");
    expect(role("b1")).toBe("loads");
    expect(role("b2")).toBe("loads");
    expect(links.find((l) => l.global_id === "b1")!.caveats.join(" ")).toMatch(/Loads \/ reference only/);
  });

  it("only design links count for the element status (exported via buildState)", async () => {
    const { statusOf } = await import("../src/index.ts");
    expect(statusOf(links.filter((l) => l.global_id === "b1"))).toBe("unmapped");
    expect(statusOf(links.filter((l) => l.global_id === "g"))).toBe("confirmed");
  });
});

describe("confidence = sum of weighted evidence", () => {
  it("adds size / storey agreement, subtracts a size mismatch, clamps to [0, 1], bands", () => {
    const pages = [page(1, "BEAM SPOT CHECK - LEVEL 3\nLevel 3 beam 3B5 W18X35 OK\nbeam 3B6 W27X94 OK")];
    const els = [el("ok", "Beam", "3B5", "W18X35", "Level 3"), el("bad", "Beam", "3B6", "W18X35", "Level 3")];
    const { links, findings } = mapElements(els, segment(pages), pages);
    const ok = links.find((l) => l.global_id === "ok")!;
    expect(ok.evidence.map((e) => e.kind)).toEqual(["tier", "storey-match", "size-match"]);
    expect(ok.evidence[0]!.weight).toBe(CONF.exact);
    expect(ok.conf).toBe(1); // 0.97 + 0.05 + 0.05, clamped
    expect(ok.band).toBe("high");
    const bad = links.find((l) => l.global_id === "bad")!;
    expect(bad.evidence.map((e) => e.kind)).toEqual(["tier", "size-mismatch"]);
    expect(bad.conf).toBeCloseTo(CONF.exact + WEIGHTS.sizeMismatch, 6);
    expect(bad.caveats.join(" ")).toMatch(/W27X94 where the model has W18X35/);
    expect(findings).toEqual([expect.objectContaining({
      kind: "size-mismatch", global_id: "bad", model_size: "W18X35", calc_size: "W27X94",
    })]);
    expect([bandOf(BANDS.high), bandOf(BANDS.medium), bandOf(0.49)]).toEqual(["high", "medium", "low"]);
  });
});

describe("typical groups", () => {
  const els = [
    el("a", "Beam", "3B1", "W18X35", "Level 3"), el("b", "Beam", "3B2", "W18X35", "Level 3"),
    el("c", "Beam", "2B1", "W18X35", "Level 2"), el("d", "Beam", "3B3", "W16X26", "Level 3"),
  ];

  it("a size-only line links the group once; members are linked via the group", () => {
    const pages = [page(1, "LEVEL 3 BEAM VIBRATION CHECK - TYPICAL\nLevel 3 typical beams W18X35, no marks\nfn = 6.1 Hz OK")];
    const r = mapElements(els, segment(pages), pages);
    expect(r.groups.find((g) => g.id === "group:Beam:Level 3:W18X35")?.members).toEqual(["a", "b"]);
    expect(r.group_links.map((g) => [g.group, g.role])).toEqual([["group:Beam:Level 3:W18X35", "design"]]);
    expect(r.links.map((l) => [l.global_id, l.tier, l.via_group])).toEqual([
      ["a", "size", "group:Beam:Level 3:W18X35"], ["b", "size", "group:Beam:Level 3:W18X35"]]);
  });

  it("a size beside a mark is not a typical statement: no group link", () => {
    const pages = [page(1, "BEAM DESIGN CHECK\nbeam 3B3 W18X35 OK")];
    const r = mapElements(els, segment(pages), pages);
    expect(r.group_links).toEqual([]);
    expect(r.links.filter((l) => l.via_group)).toEqual([]);
  });
});

describe("calcs as spans of page regions", () => {
  const p1 = styledPage(1, [
    "JOB 1 - SAMPLE", "# LEVEL 3 BEAM VIBRATION CHECK", "fn = 6.1 Hz OK", "more body text here",
    "# GIRDER 3G1 SPOT CHECK", "Girder 3G1 W18X35 design check OK",
  ]);
  const p2 = styledPage(2, ["JOB 1 - SAMPLE", "# PT SLAB TENDON PROFILE CHECK", "Slab SL2 cover OK, drape OK"]);
  const p3 = styledPage(3, ["JOB 1 - SAMPLE", "# GIRDER 3G1 SPOT CHECK (cont.)", "Deflection 3G1 L/412 OK"]);

  it("cuts a page at a mid-page heading that reads as a calc title", () => {
    const parts = pageParts(p1);
    expect(parts.map((p) => p.text.trim().split("\n")[0])).toEqual(["JOB 1 - SAMPLE", "GIRDER 3G1 SPOT CHECK"]);
  });

  it("does not cut at a body line that merely contains a title keyword", () => {
    const p = styledPage(1, ["JOB 1", "# BRACING DESIGN", "Concentric bracing per design basis", "more body text"]);
    expect(pageParts(p)).toHaveLength(1);
  });

  it("starts a calc mid-page and continues it after a gap as a second span", () => {
    const calcs = segment([p1, p2, p3]);
    expect(calcs.map((c) => [c.title, c.pages, c.spans.length])).toEqual([
      ["LEVEL 3 BEAM VIBRATION CHECK", [1], 1],
      ["GIRDER 3G1 SPOT CHECK", [1, 3], 2],
      ["PT SLAB TENDON PROFILE CHECK", [2], 1],
    ]);
    const girder = calcs[1]!;
    const first = girder.spans[0]!.regions[0]!;
    expect(first.page).toBe(1);
    expect(first.start).toBe(p1.text.indexOf("GIRDER 3G1 SPOT CHECK"));
    expect(first.rect[1]).toBeGreaterThan(0); // starts below the top of the page
    expect(girder.spans[1]!.regions[0]).toMatchObject({ page: 3, start: 0, end: p3.text.length });
    expect(girder.title_box.note).toBe("title line words");
  });

  it("matches only inside the calc's own regions", () => {
    const calcs = segment([p1]);
    const { links } = mapElements([el("g", "Beam", "3G1", "W18X35", "Level 3")], calcs, [p1]);
    expect(links.map((l) => l.calc_key)).toEqual(["girder-3g1-spot-check"]);
  });
});
