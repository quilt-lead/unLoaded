/** Up-front validation: every bad input fails fast with a message that says what to do. */
import { copyFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseCli } from "../src/inputs.ts";
import { loadModel } from "../src/engine.ts";
import { MODEL, PDF, tempDir } from "./helpers.ts";

const cli = (...a: string[]) => () => parseCli(a);

describe("parseCli", () => {
  it("accepts --model / repeated --calcs / --decisions / --actor", () => {
    const o = parseCli(["--model", MODEL, "--calcs", PDF, "--decisions", join(tempDir(), "d.json"), "--actor", "Jane", "--check"]);
    expect(o.inputs).toMatchObject({ model: MODEL, calcs: [PDF], actor: "Jane" });
    expect(o.check).toBe(true);
  });

  it("explains missing or wrong files", () => {
    expect(cli("--calcs", PDF)).toThrow(/--model is required/);
    expect(cli("--model", MODEL)).toThrow(/at least one --calcs PDF is required/);
    expect(cli("--model", "/no/such.ifc", "--calcs", PDF)).toThrow(/model file not found: \/no\/such.ifc/);
    expect(cli("--model", PDF, "--calcs", PDF)).toThrow(/is a PDF\. Pass the IFC model with --model/);
    expect(cli("--model", MODEL, "--calcs", MODEL)).toThrow(/is not a PDF \(no "%PDF-" header\)/);
    expect(cli("--model", MODEL, "--calcs", PDF, "--calcs", PDF)).toThrow(/is given twice/);
    expect(cli("--model", MODEL, "--calcs", PDF, "--decisions", "/no/dir/d.json")).toThrow(/directory \/no\/dir does not exist/);
    const fake = join(tempDir(), "fake.ifc");
    writeFileSync(fake, "hello");
    expect(cli("--model", fake, "--calcs", PDF)).toThrow(/no "ISO-10303-21" STEP header/);
    expect(cli("--model", MODEL, "--calcs", PDF, "--bogus")).toThrow(/Unknown option '--bogus'/);
  });

  it("reads a project manifest with paths relative to it, and validates its shape", () => {
    const dir = tempDir();
    copyFileSync(MODEL, join(dir, "m.ifc"));
    copyFileSync(PDF, join(dir, "a.pdf"));
    const man = join(dir, "project.json");
    writeFileSync(man, JSON.stringify({ model: "m.ifc", calcs: ["a.pdf"], decisions: "d.json", actor: "Sam" }));
    expect(parseCli(["--project", man]).inputs).toMatchObject({ model: join(dir, "m.ifc"), calcs: [join(dir, "a.pdf")], decisions: join(dir, "d.json"), actor: "Sam" });
    writeFileSync(man, JSON.stringify({ model: "m.ifc", calcs: [] }));
    expect(cli("--project", man)).toThrow(/"calcs" must be a non-empty array/);
    writeFileSync(man, JSON.stringify({ model: "m.ifc", calcs: ["a.pdf"], pdfs: [] }));
    expect(cli("--project", man)).toThrow(/unknown key\(s\) pdfs/);
    expect(cli("--project", man, "--model", MODEL)).toThrow(/either --project or --model/);
  });
});

describe("loadModel (JSON models)", () => {
  const json = (v: unknown) => new TextEncoder().encode(JSON.stringify(v));
  it("rejects legacy {nodes, links} BIM JSON: it has no GlobalIds", async () => {
    await expect(loadModel(json({ nodes: [], links: [] }), "old.json")).rejects.toThrow(/legacy BIM graph JSON .* no IFC GlobalIds/);
  });
  it("rejects other JSON and non-JSON with what it expected", async () => {
    await expect(loadModel(json({ hello: 1 }), "x.json")).rejects.toThrow(/not an element graph .* or a ModelInput/);
    await expect(loadModel(new TextEncoder().encode("nope"), "x.dat")).rejects.toThrow(/neither an IFC file .* nor valid JSON/);
  });
  it("loads a ModelInput and a serialized element graph like the app", async () => {
    const mi = { meta: { version: 1, units: "m", source: { format: "test" } }, levels: [], warnings: [], relations: [],
      elements: [{ id: "A", kind: "beam", mark: "B1", params: {}, source: { format: "test" } }] };
    const m = await loadModel(json(mi), "mi.json");
    expect(m.format).toBe("model-input-json");
    expect(m.elements()).toMatchObject([{ global_id: "A", cat: "Beam", mark: "B1" }]);
    const g = await loadModel(json({ format: "unloaded.element-graph", version: 1, meta: null, levels: [], nodes: [{ ...mi.elements[0], tags: {}, links: [] }], edges: [] }), "g.json");
    expect(g.format).toBe("element-graph-json");
    expect(g.nodes().map((n) => n.id)).toEqual(["A"]);
  });
});
