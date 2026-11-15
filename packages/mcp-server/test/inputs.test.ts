/** Up-front validation: every bad input fails fast with a message that says what to do. */
import { copyFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseCli } from "../src/inputs.ts";
import { loadModel } from "../src/engine.ts";
import { buildProjectFile, writeTemp } from "./fixtures.ts";
import { MODEL, MODEL_REV2, PDF, SUPPLEMENT, tempDir } from "./helpers.ts";

const cli = (...a: string[]) => () => parseCli(a);

describe("parseCli", () => {
  it("accepts repeated --model (oldest first) / repeated --calcs / --decisions / --actor", () => {
    const o = parseCli(["--model", MODEL, "--model", MODEL_REV2, "--calcs", PDF, "--calcs", SUPPLEMENT, "--decisions", join(tempDir(), "d.json"), "--actor", "Jane", "--check"]);
    expect(o.inputs).toMatchObject({ models: [MODEL, MODEL_REV2], calcs: [PDF, SUPPLEMENT], projectFile: null, actor: "Jane" });
    expect(o.check).toBe(true);
  });

  it("explains missing or wrong files", () => {
    expect(cli("--calcs", PDF)).toThrow(/--model is required/);
    expect(cli("--model", MODEL)).toThrow(/at least one --calcs PDF is required/);
    expect(cli("--model", "/no/such.ifc", "--calcs", PDF)).toThrow(/model file not found: \/no\/such.ifc/);
    expect(cli("--model", PDF, "--calcs", PDF)).toThrow(/is a PDF\. Pass the IFC model with --model/);
    expect(cli("--model", MODEL, "--calcs", MODEL)).toThrow(/is not a PDF \(no "%PDF-" header\)/);
    expect(cli("--model", MODEL, "--calcs", PDF, "--calcs", PDF)).toThrow(/is given twice/);
    expect(cli("--model", MODEL, "--model", MODEL, "--calcs", PDF)).toThrow(/--model .* is given twice/);
    expect(cli("--model", MODEL, "--calcs", PDF, "--decisions", "/no/dir/d.json")).toThrow(/directory \/no\/dir does not exist/);
    const fake = join(tempDir(), "fake.ifc");
    writeFileSync(fake, "hello");
    expect(cli("--model", fake, "--calcs", PDF)).toThrow(/no "ISO-10303-21" STEP header/);
    const lfs = join(tempDir(), "calcs.pdf");
    writeFileSync(lfs, "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 10\n");
    expect(cli("--model", MODEL, "--calcs", lfs)).toThrow(/is a Git LFS pointer, not the PDF: run `git lfs install && git lfs pull`/);
    expect(cli("--model", MODEL, "--calcs", PDF, "--bogus")).toThrow(/Unknown option '--bogus'/);
  });

  it("reads a project manifest with paths relative to it, and validates its shape", () => {
    const dir = tempDir();
    copyFileSync(MODEL, join(dir, "m1.json"));
    copyFileSync(MODEL_REV2, join(dir, "m2.json"));
    copyFileSync(PDF, join(dir, "a.pdf"));
    const man = join(dir, "project.json");
    writeFileSync(man, JSON.stringify({ model: "m1.json", calcs: ["a.pdf"], decisions: "d.json", actor: "Sam" }));
    expect(parseCli(["--project", man]).inputs).toMatchObject({ models: [join(dir, "m1.json")], calcs: [join(dir, "a.pdf")], decisions: join(dir, "d.json"), actor: "Sam", manifest: man });
    writeFileSync(man, JSON.stringify({ model: ["m1.json", "m2.json"], calcs: "a.pdf" }));
    expect(parseCli(["--project", man]).inputs).toMatchObject({ models: [join(dir, "m1.json"), join(dir, "m2.json")], calcs: [join(dir, "a.pdf")] });
    writeFileSync(man, JSON.stringify({ model: "m1.json", calcs: [] }));
    expect(cli("--project", man)).toThrow(/"calcs" must be a non-empty array/);
    writeFileSync(man, JSON.stringify({ model: [], calcs: ["a.pdf"] }));
    expect(cli("--project", man)).toThrow(/"model" must be a path, or an array of paths/);
    writeFileSync(man, JSON.stringify({ model: "m1.json", calcs: ["a.pdf"], pdfs: [] }));
    expect(cli("--project", man)).toThrow(/unknown key\(s\) pdfs/);
    expect(cli("--project", man, "--model", MODEL)).toThrow(/either --project or --model/);
  });

  it("takes a *.calcgraph.json project file through --project", async () => {
    const path = writeTemp((await buildProjectFile()).file);
    const dec = join(tempDir(), "d.json");
    expect(parseCli(["--project", path, "--decisions", dec, "--actor", "Kim"]).inputs).toEqual({
      models: [], calcs: [], projectFile: path, decisions: dec, actor: "Kim", manifest: null,
    });
  });
});

describe("loadModel (JSON models)", () => {
  const json = (v: unknown) => new TextEncoder().encode(JSON.stringify(v));
  it("rejects legacy {nodes, links} BIM JSON: it has no GlobalIds", async () => {
    await expect(loadModel(json({ nodes: [], links: [] }), "old.json")).rejects.toThrow(/legacy BIM graph JSON .* no IFC GlobalIds/);
  });
  it("rejects other JSON, non-JSON and a project file with what it expected", async () => {
    await expect(loadModel(json({ hello: 1 }), "x.json")).rejects.toThrow(/not an element graph .* or a ModelInput/);
    await expect(loadModel(new TextEncoder().encode("nope"), "x.dat")).rejects.toThrow(/neither an IFC file .* nor valid JSON/);
    await expect(loadModel(json((await buildProjectFile()).file), "p.calcgraph.json")).rejects.toThrow(/pass it with --project, not --model/);
  });
  it("refuses a graph the calc engine cannot read (units other than metres)", async () => {
    const g = { format: "unloaded.element-graph", version: 1, meta: { version: 1, units: "mm" }, levels: [], nodes: [], edges: [] };
    await expect(loadModel(json(g), "mm.json")).rejects.toThrow(/calc engine cannot read .* units must be "m"/);
  });
  it("loads a ModelInput and a serialized element graph like the app, as calc-mapper element rows", async () => {
    const mi = { meta: { version: 1, units: "m", source: { format: "test" } }, levels: [], warnings: [], relations: [],
      elements: [{ id: "A", kind: "beam", mark: "B1", params: {}, source: { format: "test" } }] };
    const m = await loadModel(json(mi), "mi.json");
    expect(m.format).toBe("model-input-json");
    expect(m.elements()).toMatchObject([{ global_id: "A", cat: "Beam", mark: "B1" }]);
    expect(m.graphSha256).toMatch(/^[0-9a-f]{64}$/);
    const g = await loadModel(json({ format: "unloaded.element-graph", version: 1, meta: { version: 1, units: "m" }, levels: [], nodes: [{ ...mi.elements[0], tags: {}, links: [] }], edges: [] }), "g.json");
    expect(g.format).toBe("element-graph-json");
    expect(g.nodes().map((n) => n.id)).toEqual(["A"]);
  });
});
