/**
 * The auditability contract: provenance on every derived record, producer records with document
 * hashes, units, coordinate frames. The `@ts-expect-error` lines are checked by the type-check
 * (tsc -p packages/calc-mapper/tsconfig.json includes test/): each must stay a type error.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  ALIASES, PACKAGE_VERSION, UNITS, UnitMismatch, UnknownUnit, addDecision, buildExport, canonicalUnit, convert, decisionFrom,
  dimensionOf, impactOf, inputList, loadPath, mapCalcs, modelPointM, q, segmentCalcs, sha256, sha256Json, sheetRect, to,
  unitFromKey, type Decision, type Impact, type Link, type ModelPointM, type Provenance, type Quantity, type SheetRect,
} from "../src/index.ts";
import { DOC_SHA, graph, node, page } from "./helpers.ts";

const PRODUCER = /^calc-mapper@\d+\.\d+\.\d+\/(segment|matcher|calcdeps|impact|decisions)$/;
const SHA = /^[0-9a-f]{64}$/;

/** A graph + package that exercise every record kind: exact links, a size mismatch, a typical group, xrefs, page references. */
function fixture() {
  const g = graph({
    levels: [{ id: "L3", name: "Level 3", elevation: 8.4 }],
    nodes: [
      node("B5", "beam", { mark: "3B5", name: "3B5", profile: "W18X35", levelId: "L3" }),
      node("B6", "beam", { mark: "3B6", name: "3B6", profile: "W18X35", levelId: "L3" }),
      node("K1", "connection", { mark: "ST-1", source: { format: "ifc", nativeType: "IfcPlate" } }),
      node("C1", "column", { mark: "C1", source: { format: "ifc", nativeType: "IfcColumn" } }),
    ],
    edges: [
      { id: "supports:B5->K1", kind: "supports", a: "B5", b: "K1", directed: true,
        evidence: [{ rule: "connection contact", source: "inferred", detail: { gap_m: 0.004 } }] },
      { id: "supports:K1->C1", kind: "supports", a: "K1", b: "C1", directed: true,
        evidence: [{ rule: "connection contact", source: "inferred", detail: { gap_m: 0 } }] },
    ],
  });
  const pages = [
    page(1, "BEAM SPOT CHECK - LEVEL 3\nLevel 3 beam 3B5 W18X35 OK\nbeam 3B6 W27X94 OK"),
    page(2, "LEVEL 3 BEAM VIBRATION CHECK - TYPICAL\nLevel 3 typical beams W18X35, no marks"),
    page(3, "COLUMN DESIGN\ncolumn C1 design, see page 1\nbeam 3B5 end reaction carried"),
  ];
  return { g, pkg: segmentCalcs(pages, "calcs.pdf") };
}

function expectProvenance(p: Provenance | undefined, method: Provenance["method"], what: string): Provenance {
  expect(p, `${what} has provenance`).toBeDefined();
  expect(p!.producer, what).toMatch(PRODUCER);
  expect(p!.producer.startsWith(`calc-mapper@${PACKAGE_VERSION}/`), what).toBe(true);
  expect(p!.rule.length, what).toBeGreaterThan(0);
  expect(p!.method, what).toBe(method);
  for (const h of p!.inputs) expect(h, what).toMatch(SHA);
  if (method !== "human") expect(p!.inputs.length, `${what} rests on at least one document`).toBeGreaterThan(0);
  return p!;
}

describe("provenance on every record of a full run", () => {
  it("segmentation, links, group links, findings, calc edges, decisions, export records and impact all carry it", async () => {
    const { g, pkg } = fixture();
    const run = await mapCalcs(g, pkg);
    const graphSha = await sha256Json(g);
    expect(run.inputs).toEqual([graphSha, DOC_SHA]);

    // every record kind is present, so "every record has provenance" is not vacuous
    for (const [k, xs] of Object.entries({ calcs: pkg.calcs, links: run.links, group_links: run.group_links,
      findings: run.findings, calc_edges: run.calc_edges })) {
      expect(xs.length, `${k} produced`).toBeGreaterThan(0);
    }
    for (const c of pkg.calcs) expect(expectProvenance(c.provenance, "rule", `calc ${c.key}`).inputs).toEqual([DOC_SHA]);
    for (const l of run.links) {
      const p = expectProvenance(l.provenance, "rule", `link ${l.global_id}/${l.calc_key}`);
      expect(p.rule).toBe(`matcher.tier.${l.tier}`);
      expect(p.inputs).toEqual([graphSha, DOC_SHA]);
    }
    for (const gl of run.group_links) expect(expectProvenance(gl.provenance, "rule", "group link").rule).toBe("matcher.typical-group");
    for (const f of run.findings) expect(expectProvenance(f.provenance, "rule", "finding").rule).toBe("matcher.finding.size-mismatch");
    const kinds = new Set(run.calc_edges.flatMap((e) => expectProvenance(e.provenance, "rule", `edge ${e.src}->${e.dst}`).rule.split("+")));
    expect(kinds).toEqual(new Set(["calcdeps.page-reference.input", "calcdeps.cross-reference"]));

    const beam = run.links.find((l) => l.global_id === "B5" && l.tier === "exact")!;
    let decisions: Decision[] = [];
    decisions = addDecision(decisions, { global_id: beam.global_id, calc_key: beam.calc_key, action: "confirm", actor: "issy" },
      { at: "2026-11-14T20:00:00-05:00", inputs: run.inputs });
    decisions = addDecision(decisions, { global_id: "C1", calc_key: beam.calc_key, action: "manual", actor: "issy" },
      { at: "2026-11-14T20:01:00-05:00", inputs: run.inputs });
    for (const d of decisions) {
      const p = expectProvenance(d.provenance, "human", `decision ${d.id}`);
      expect([p.rule, p.actor, p.at, p.inputs]).toEqual([`decision.${d.action}`, "issy", d.at, run.inputs]);
    }

    const exp = buildExport(g, pkg, run, decisions);
    for (const c of exp.calcs) expectProvenance(c.provenance, "rule", `export calc ${c.key}`);
    for (const e of exp.calc_edges) expectProvenance(e.provenance, "rule", "export calc edge");
    for (const gl of exp.group_links) expectProvenance(gl.provenance, "rule", "export group link");
    for (const f of exp.findings) expectProvenance(f.provenance, "rule", "export finding");
    const exported = exp.elements.flatMap((e) => e.calcs.map((l) => ({ e, l })));
    for (const { e, l } of exported) {
      expectProvenance(l.provenance, l.tier === "manual" ? "human" : "rule", `export link ${e.global_id}/${l.calc}`);
    }
    const confirmed = exported.find(({ e, l }) => e.global_id === "B5" && l.calc === beam.calc_key)!.l;
    expect(confirmed.review).toBe("confirmed");
    expect(confirmed.provenance.method).toBe("rule"); // the matcher made it ...
    expect(confirmed.review_provenance).toEqual(decisions[0]!.provenance); // ... a person confirmed it
    const manual = exported.find(({ e, l }) => e.global_id === "C1" && l.calc === beam.calc_key)!.l;
    expect(manual.provenance).toEqual(decisions[1]!.provenance);

    expect(exp.producers.inputs).toEqual(run.inputs);
    expect(exp.producers.element_graph).toMatchObject({ producer: "unloaded.element-graph@1", sha256: graphSha });
    expect(exp.producers.calc_package).toEqual({ name: "calcs.pdf", sha256: DOC_SHA, pages: 3 });
    expect(exp.producers.calc_mapper).toEqual({ producer: `calc-mapper@${PACKAGE_VERSION}`, engine: exp.engine });
    // the original producer keys are kept (additive)
    expect(exp.producers.model).toBeDefined();
    expect(exp.producers.mapping).toBeDefined();

    const imp = await impactOf(g, pkg, run, decisions, "C1", "remove");
    const ip = expectProvenance(imp.provenance, "rule", "impact");
    expect([ip.rule, ip.inputs]).toEqual(["impact.propagate.remove", [graphSha, DOC_SHA]]);
    const graphOnly = await impactOf(g, null, null, [], "C1", "change");
    expect(graphOnly.provenance.inputs).toEqual([graphSha]);
  });

  it("a decision read back without provenance gets the human provenance its own fields state", () => {
    const d = decisionFrom({ id: 1, global_id: "B1", calc_key: "k", action: "reject", actor: "eval", note: null, at: "t" });
    expect(d.provenance).toEqual({ producer: `calc-mapper@${PACKAGE_VERSION}/decisions`, rule: "decision.reject", method: "human",
      inputs: [], actor: "eval", at: "t" });
    expect(() => decisionFrom({ ...d, action: "nope" as never })).toThrow();
  });

  it("a record cannot claim an input that is not a document hash", () => {
    expect(() => inputList([""])).toThrow(/sha256/);
    expect(() => inputList([undefined])).toThrow(/sha256/);
    expect(() => inputList(["ABC"])).toThrow(/sha256/);
    expect(inputList([DOC_SHA, DOC_SHA], [DOC_SHA])).toEqual([DOC_SHA]);
    expect(() => segmentCalcs([{ ...page(1, "BEAM DESIGN\nbeam 2B1"), doc_sha256: "" }])).toThrow(/extractPdf/);
    expect(() => segmentCalcs([page(1, "BEAM DESIGN\nbeam 2B1"), { ...page(2, "COLUMN DESIGN\nC1"), doc_sha256: "e".repeat(64) }]))
      .toThrow(/one PDF/);
  });

  it("the version in every producer string is the package's", () => {
    const pkgJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };
    expect(PACKAGE_VERSION).toBe(pkgJson.version);
  });

  it("is a required field: a record without it does not type-check", () => {
    // @ts-expect-error - provenance is required on Impact
    const impact: Impact = { global_id: "B1", mode: "change", removed: [], hit: {}, why: {}, stale: {}, waves: 0 };
    // @ts-expect-error - provenance is required on Link
    const link: Link = { global_id: "B1", calc_key: "k", conf: 1, tier: "manual", rule: "", page: null, token: "", span: null,
      snippet: null, rects: [], status: "manual", role: "design", band: "high", evidence: [], caveats: [] };
    // @ts-expect-error - provenance is required on Decision
    const decision: Decision = { id: 1, global_id: "B1", calc_key: "k", action: "confirm", actor: null, note: null, at: "t" };
    expect([impact, link, decision].length).toBe(3);
  });
});

describe("producer records: document hashes", () => {
  it("sha256 is SHA-256 (WebCrypto)", async () => {
    expect(await sha256(new TextEncoder().encode("abc"))).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("the graph hash ignores key order; hashes are stable across runs", async () => {
    expect(await sha256Json({ a: 1, b: [1, { c: 2, d: 3 }] })).toBe(await sha256Json({ b: [1, { d: 3, c: 2 }], a: 1 }));
    const { g, pkg } = fixture();
    const r1 = await mapCalcs(g, pkg);
    const r2 = await mapCalcs(structuredClone(g), structuredClone(pkg));
    expect(r1.producers).toEqual(r2.producers);
    expect(JSON.stringify(r1)).toBe(JSON.stringify(r2));
    const moved = structuredClone(g);
    moved.nodes[0]!.mark = "3B9";
    expect((await mapCalcs(moved, pkg)).producers.element_graph.sha256).not.toBe(r1.producers.element_graph.sha256);
  });
});

describe("units (units.py's canonical set and table)", () => {
  it("has exactly units.py's canonical units", () => {
    expect([...UNITS].sort()).toEqual([
      "1", "percent", "m", "mm", "cm", "ft", "in", "pt", "m2", "ft2", "in2", "m3", "ft3", "yd3", "in3", "mm2", "mm3", "cm2", "cm3",
      "m4", "mm4", "cm4", "in4", "ft4", "m6", "mm6", "in6", "N", "kN", "lbf", "kip", "N*m", "kN*m", "kip*ft", "kip*in", "lbf*ft",
      "N/m", "kN/m", "plf", "klf", "kip/in", "lbf/in", "N*m/rad", "kN*m/rad", "kip*in/rad", "kip*ft/rad", "Pa", "kPa", "MPa",
      "psf", "ksf", "psi", "ksi", "pcf", "kN/m3", "rad", "deg",
    ].sort());
    for (const a of Object.values(ALIASES)) expect(UNITS).toContain(a);
  });

  it.each<[number, string, string, number]>([
    [1, "ft", "m", 0.3048], [1, "in", "mm", 25.4], [72, "pt", "in", 1], [1, "kip", "kN", 4.4482216152605], [1, "lbf", "N", 4.4482216152605],
    [1, "kip*ft", "kN*m", 1.3558179483314004], [1, "ksi", "MPa", 6.894757293168361], [1, "psf", "Pa", 47.88025898033584],
    [1, "klf", "kN/m", 14.593902937206364], [1, "kip/in", "klf", 12], [1, "pcf", "kN/m3", 0.15708746384624617], [180, "deg", "rad", Math.PI],
    [50, "percent", "1", 0.5], [1, "yd3", "ft3", 27], [1, "in4", "mm4", 416231.4256], [1, "m2", "ft2", 10.763910416709722],
  ])("%d %s = %d %s", (v, from, to_, want) => {
    expect(convert(v, from, to_)).toBeCloseTo(want, 9);
    expect(convert(convert(v, from, to_), to_, from)).toBeCloseTo(v, 9);
  });

  it("every unit round-trips through every unit of its dimension", () => {
    for (const a of UNITS) {
      for (const b of UNITS) {
        if (dimensionOf(a).join() === dimensionOf(b).join()) expect(convert(convert(3.7, a, b), b, a)).toBeCloseTo(3.7, 9);
        else expect(() => convert(1, a, b)).toThrow(UnitMismatch);
      }
    }
  });

  it("accepts the sources' spellings, refuses unknown units and mixed dimensions (never silent)", () => {
    expect([canonicalUnit("k-ft"), canonicalUnit(" KSI "), canonicalUnit("°"), canonicalUnit("kn-m")]).toEqual(["kip*ft", "ksi", "deg", "kN*m"]);
    expect(() => convert(1, "furlong", "m")).toThrow(UnknownUnit);
    expect(() => convert(1, "m", "parsec")).toThrow(UnknownUnit);
    expect(() => convert(1, "kip", "ft")).toThrow(UnitMismatch);
    expect(() => convert(1, "rad", "1")).toThrow(UnitMismatch); // angle is its own dimension
    expect(() => q(Number.NaN, "m")).toThrow(TypeError);
    const inches = to(q(2, "ft"), "in");
    expect(inches.unit).toBe("in");
    expect(inches.value).toBeCloseTo(24, 9);
    // @ts-expect-error - a unit outside the set is a type error where it is a literal
    expect(() => q(1, "furlong")).toThrow(UnknownUnit);
    expect([unitFromKey("PreDL[ksf]"), unitFromKey("Magnitude[k,k-ft]"), unitFromKey("max_reaction_k"), unitFromKey("gap_m"),
      unitFromKey("size")]).toEqual(["ksf", null, "kip", "m", null]);
  });

  it("the engine reports the load-path gap as a quantity in metres", () => {
    const gaps: (Quantity<"m"> | null)[] = loadPath(graph()).map((e) => e.gap);
    expect(gaps).toEqual([{ value: 0.004, unit: "m" }, { value: 0, unit: "m" }]);
  });
});

describe("coordinate frames", () => {
  it("are plain numbers in JSON", () => {
    expect(JSON.stringify(sheetRect(1, 2, 3, 4))).toBe("[1,2,3,4]");
    expect(JSON.stringify(modelPointM([0, 0.1, 4.2]))).toBe("[0,0.1,4.2]");
  });

  it("cannot be passed as one another", () => {
    const sheet: SheetRect = sheetRect(10, 20, 30, 40);
    const model: ModelPointM = modelPointM([1, 2, 3]);
    // @ts-expect-error - model metres are not a sheet rect
    const a: SheetRect = model;
    // @ts-expect-error - a sheet rect is not model metres
    const b: ModelPointM = sheet;
    // @ts-expect-error - an unbranded tuple is not a sheet rect: it has no frame
    const c: SheetRect = [10, 20, 30, 40];
    // @ts-expect-error - a link's highlight rects are sheet rects, not model points
    const rects: Link["rects"] = [modelPointM([1, 2, 3])];
    expect([a, b, c, rects].length).toBe(4);
  });
});
