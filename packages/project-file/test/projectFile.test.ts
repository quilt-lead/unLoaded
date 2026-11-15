import { Buffer } from "node:buffer";
import { describe, expect, it } from "vitest";
import type { SerializedElementGraph } from "@unloaded/element-graph";
import { segmentCalcs } from "@unloaded/calc-mapper";
import {
  PROJECT_FILE_FORMAT, PROJECT_FILE_VERSION, ProjectFileError, decodeBase64, encodeBase64, headOf, isProjectFileFormat,
  parseProjectFile, storedExtractionFor, type ProjectFile, LEGACY_DOC_ID, documentHeads, documentName, nextDocId, projectDocuments, legacyCalcRef,
} from "../src/index.ts";

const graph = (): SerializedElementGraph => ({
  format: "unloaded.element-graph", version: 1, meta: { version: 1, units: "m" },
  levels: [{ id: "L1", name: "Level 1", elevation: 0 }],
  nodes: [
    { id: "C1", kind: "column", ifcType: "IfcColumn", mark: "C-1", levelId: "L1", params: {} },
    { id: "B1", kind: "beam", ifcType: "IfcBeam", mark: "B-1", levelId: "L1", params: {} },
  ],
  edges: [{ id: "e1", kind: "supports", a: "C1", b: "B1", evidence: [] }],
} as unknown as SerializedElementGraph);

/** Every byte value, then enough to cross the encoder's 32 KiB chunk boundary. */
const bytes = (n = 70_000) => Uint8Array.from({ length: n }, (_, i) => (i * 7 + (i >> 8)) % 256);

const base = (): ProjectFile => ({
  format: PROJECT_FILE_FORMAT, version: PROJECT_FILE_VERSION, exportedAt: "2026-11-14T21:00:00-05:00",
  project: { name: "P", createdAt: "2026-11-14T21:00:00-05:00" },
  documents: [{ docId: "d1", name: "c", removed: false }],
  revisions: [
    { id: 4, kind: "model", seq: 2, label: "b", sourceName: "b.ifc", mediaType: "application/x-step", createdAt: "t", meta: { elements: 2, project: null }, blob: encodeBase64(bytes(10)), graph: graph() },
    { id: 1, kind: "model", seq: 1, label: "a", sourceName: "a.ifc", mediaType: "application/x-step", createdAt: "t", meta: {}, blob: encodeBase64(bytes(3)), graph: graph() },
    { id: 2, kind: "calcs", seq: 1, label: "c", sourceName: "c.pdf", mediaType: "application/pdf", createdAt: "t", meta: { pages: 3 }, blob: encodeBase64(bytes()), extraction: { calcs: [] }, docId: "d1" },
  ],
  decisions: [
    { globalId: "G", calcKey: "d1#k", action: "confirm", actor: "r", note: null, at: "t1", modelRev: 1, calcRev: 2 },
    { globalId: "G", calcKey: "d1#k", action: "reject", actor: "r", note: "no", at: "t2", modelRev: 4, calcRev: null },
  ],
});

/** A copy of base() with one change applied, as unknown JSON (so a test can break the shape). */
const broken = (edit: (f: any) => void): unknown => {
  const f = JSON.parse(JSON.stringify(base()));
  edit(f);
  return f;
};

describe("project file round trip", () => {
  it("survives JSON text unchanged, payloads included", () => {
    const f = base();
    const back = parseProjectFile(JSON.parse(JSON.stringify(f)));
    expect(back).toEqual(f);
    expect(decodeBase64(back.revisions[2]!.blob)).toEqual(bytes());
  });

  it("base64 codec: round-trips every byte value across chunk boundaries, and matches Node's encoder", () => {
    for (const n of [0, 1, 2, 3, 0x8000, 0x8001, 70_000]) {
      const b = bytes(n);
      const s = encodeBase64(b);
      expect(s).toBe(Buffer.from(b).toString("base64"));
      expect(decodeBase64(s)).toEqual(b);
    }
  });
});

describe("parseProjectFile rejects what a reader can't use, naming the field", () => {
  it("format and version", () => {
    expect(isProjectFileFormat(base())).toBe(true);
    expect(isProjectFileFormat({ format: "unloaded.element-graph" })).toBe(false);
    expect(() => parseProjectFile({ ...base(), format: "unloaded.calc-graph-export" })).toThrow(/not a calc-graph project file/);
    expect(() => parseProjectFile({ ...base(), version: 3 })).toThrow(/version 3 is not supported/);
    expect(() => parseProjectFile([])).toThrow(ProjectFileError);
  });

  const cases: [string, (f: any) => void, RegExp][] = [
    ["duplicate revision id", (f: any) => { f.revisions[1].id = 4; }, /duplicate revision id 4/],
    ["unknown kind", (f: any) => { f.revisions[0].kind = "drawings"; }, /revisions\[0\]\.kind must be/],
    ["non-integer seq", (f: any) => { f.revisions[0].seq = 0; }, /revisions\[0\]\.seq/],
    ["missing mediaType", (f: any) => { delete f.revisions[2].mediaType; }, /revisions\[2\]\.mediaType must be a string/],
    ["nested meta", (f: any) => { f.revisions[0].meta.x = { y: 1 }; }, /revisions\[0\]\.meta\.x/],
    ["blob not base64", (f: any) => { f.revisions[0].blob = "not base64!"; }, /revisions\[0\]\.blob must be a non-empty base64 string/],
    // the old validator accepted "" (base64 of nothing), so a revision that lost its file saved and reopened as an empty file
    ["empty blob", (f: any) => { f.revisions[1].blob = ""; }, /revisions\[1\]\.blob must be a non-empty base64 string/],
    ["model without graph", (f: any) => { delete f.revisions[1].graph; }, /model revision 1 has no element graph/],
    ["graph edge to a missing node", (f: any) => { f.revisions[0].graph.edges[0].b = "X"; }, /revisions\[0\]\.graph: .*references a node/],
    ["calc revision with a graph", (f: any) => { f.revisions[2].graph = graph(); }, /calc revision 2 must not carry an element graph/],
    ["unknown action", (f: any) => { f.decisions[0].action = "approve"; }, /decisions\[0\]\.action must be one of confirm, reject, manual, undo/],
    ["missing actor", (f: any) => { delete f.decisions[0].actor; }, /decisions\[0\]\.actor must be a string/],
    ["decision on a revision not in the file", (f: any) => { f.decisions[0].modelRev = 9; }, /decisions\[0\]\.modelRev = 9 is not a model revision/],
    ["decision's calcRev pointing at a model", (f: any) => { f.decisions[0].calcRev = 1; }, /decisions\[0\]\.calcRev = 1 is not a calcs revision/],
  ];
  it.each(cases)("%s", (_name, edit, msg) => {
    expect(() => parseProjectFile(broken(edit))).toThrow(msg);
  });
});

describe("parseProjectFile returns only declared fields", () => {
  // the old parser returned its input unchanged, so a hand-added decision `id` reached the app's
  // importer, whose IndexedDB put kept it as the key and overwrote another project's decision
  it("drops undeclared keys at every level", () => {
    const f = broken((x) => {
      x.extra = 1;
      x.project.id = "other";
      x.revisions[0].projectId = "other";
      x.decisions[0].id = 7;
      x.decisions[0].projectId = "other";
    });
    const back = parseProjectFile(f) as any;
    expect(back.extra).toBeUndefined();
    expect(back.project).toEqual({ name: "P", createdAt: base().project.createdAt });
    expect(Object.keys(back.revisions[0]).sort()).toEqual(["blob", "createdAt", "graph", "id", "kind", "label", "mediaType", "meta", "seq", "sourceName"]);
    expect(Object.keys(back.decisions[0]).sort()).toEqual(["action", "actor", "at", "calcKey", "calcRev", "globalId", "modelRev", "note"]);
    expect(back).toEqual(base());
    expect(back).not.toBe(f);
  });
});

describe("storedExtractionFor: the one rule for using a stored calc package", () => {
  const sha = "a".repeat(64);
  /** A real package, as the app's worker and the MCP server store it (segmentCalcs of extracted pages). */
  const real = (h: string = sha) => {
    const text = "BEAM DESIGN\nbeam 2B1 W18X35 ok, stress ratio 0.81";
    const words: [number, number, number, number, number, number][] = [];
    let pos = 0;
    for (const w of text.split(/[ \n]/)) {
      words.push([0, 0, 1, 1, pos, pos + w.length]);
      pos += w.length + 1;
    }
    return JSON.parse(JSON.stringify(segmentCalcs([{ n: 1, text, words, width: 612, height: 792, scanned: false, doc_sha256: h }], "c.pdf")));
  };
  const edit = (f: (x: any) => void) => {
    const x = real();
    f(x);
    return x;
  };
  it("uses a current extraction whose every document hash names the PDF", () => {
    const p = real();
    expect(storedExtractionFor(p, sha)).toEqual({ pkg: p, reason: null });
  });
  // the app used to trust any extraction carrying hashes (and crashed with a TypeError on one with
  // source_sha256 but no pages); the MCP server checked the hash; both now take this answer
  it.each([
    ["missing", undefined, /no stored extraction/],
    ["not an object", "x", /malformed/],
    ["source_sha256 but no pages", { source_sha256: sha, calcs: [] }, /malformed \(pages/],
    ["no pages at all", edit((x) => (x.pages = [])), /malformed \(pages/],
    ["calcs missing", edit((x) => delete x.calcs), /malformed \(calcs/],
    ["no hashes", edit((x) => { delete x.source_sha256; delete x.pages[0].doc_sha256; }), /predates document hashes/],
    ["a page without its hash", edit((x) => x.pages.push({ ...x.pages[0], n: 2, doc_sha256: undefined })), /predates document hashes/],
    ["another PDF's hash", real("b".repeat(64)), /does not match the PDF/],
    ["a page from another PDF", edit((x) => (x.pages[0].doc_sha256 = "b".repeat(64))), /does not match the PDF/],
    // round 2: an extraction from an older segmenter (duplicate keys, untitled pages swallowed) was reused forever
    ["no segmenter recorded (made before it was)", edit((x) => delete x.segmenter), /predates versioning; the current one is segment-v/],
    ["an older segmenter", edit((x) => (x.segmenter = "segment-v1")), /older segmenter \(segment-v1\)/],
    // round 2: a stored extraction the engine cannot read is re-extracted, not handed to the engine to throw on
    ["a page without text", edit((x) => delete x.pages[0].text), /malformed \(pages\[0\]\.text/],
    ["page words that are not word boxes", edit((x) => (x.pages[0].words = [[1, 2]])), /malformed \(pages\[0\]\.words/],
    ["a calc without a key", edit((x) => delete x.calcs[0].key), /malformed \(calcs\[0\]\.key/],
    ["a calc whose spans are not a list", edit((x) => (x.calcs[0].spans = null)), /malformed \(calcs\[0\]\.spans/],
    ["two calcs with one key", edit((x) => x.calcs.push({ ...x.calcs[0], ord: 1 })), /duplicate calc key/],
  ] as [string, unknown, RegExp][])("refuses %s", (_name, x, why) => {
    const r = storedExtractionFor(x, sha);
    expect(r.pkg).toBeNull();
    expect(r.reason).toMatch(why);
  });
});

describe("headOf", () => {
  it("head of a kind = highest id (what importing leaves as head)", () => {
    const f = base();
    expect(headOf(f.revisions, "model")?.id).toBe(4);
    expect(headOf(f.revisions, "calcs")?.id).toBe(2);
    expect(headOf([], "calcs")).toBeNull();
  });
});

describe("calc documents (version 2) and version-1 files", () => {
  it("a version-1 file opens: its calc revisions are one legacy document, its bare calc keys refs into it", () => {
    const v1 = broken((f) => {
      f.version = 1;
      delete f.documents;
      for (const r of f.revisions) delete r.docId;
      for (const d of f.decisions) d.calcKey = "k";
    });
    const p = parseProjectFile(v1);
    expect(p.version).toBe(PROJECT_FILE_VERSION);
    expect(p.documents).toEqual([{ docId: LEGACY_DOC_ID, name: "c", removed: false }]);
    expect(p.revisions.find((r) => r.kind === "calcs")!.docId).toBe(LEGACY_DOC_ID);
    expect(p.revisions.filter((r) => r.kind === "model").every((r) => r.docId === undefined)).toBe(true);
    expect(p.decisions.map((d) => d.calcKey)).toEqual(["d1#k", "d1#k"]);
  });

  it("refuses documents and refs that do not hang together", () => {
    expect(() => parseProjectFile(broken((f) => delete f.documents))).toThrow(/documents must be a list/);
    expect(() => parseProjectFile(broken((f) => (f.documents[0].docId = "a#b")))).toThrow(/docId must be a non-empty string/);
    expect(() => parseProjectFile(broken((f) => f.documents.push({ ...f.documents[0] })))).toThrow(/duplicate docId d1/);
    expect(() => parseProjectFile(broken((f) => f.documents.push({ docId: "d2", name: "x", removed: false })))).toThrow(/document d2 has no calc revision/);
    expect(() => parseProjectFile(broken((f) => (f.revisions[2].docId = "d9")))).toThrow(/revisions\[2\]\.docId must name one of documents/);
    expect(() => parseProjectFile(broken((f) => (f.revisions[0].docId = "d1")))).toThrow(/model revision 4 must not name a calc document/);
    expect(() => parseProjectFile(broken((f) => (f.decisions[0].calcKey = "k")))).toThrow(/decisions\[0\]\.calcKey must be a calc ref/);
  });

  it("documents of a project, heads per document, next id, legacy refs", () => {
    const revs = [
      { id: 1, kind: "calcs" as const, sourceName: "Beams.pdf" },
      { id: 2, kind: "model" as const, sourceName: "m.ifc" },
      { id: 3, kind: "calcs" as const, sourceName: "Cols.pdf", docId: "d2" },
      { id: 5, kind: "calcs" as const, sourceName: "Beams rev B.pdf", docId: "d1" },
      { id: 6, kind: "calcs" as const, sourceName: "Stairs.pdf", docId: "d3" },
    ];
    const docs = projectDocuments(null, revs);
    expect(docs.map((d) => [d.docId, d.name])).toEqual([["d1", "Beams"], ["d2", "Cols"], ["d3", "Stairs"]]);
    const removed = docs.map((d) => (d.docId === "d3" ? { ...d, removed: true } : d));
    expect(documentHeads(removed, revs).map((h) => [h.doc.docId, h.rev.id])).toEqual([["d1", 5], ["d2", 3]]);
    expect(nextDocId(docs)).toBe("d4");
    expect(nextDocId([])).toBe("d1");
    expect(legacyCalcRef("k")).toBe("d1#k");
    expect(legacyCalcRef("d2#k")).toBe("d2#k");
    expect(documentName("calc package.pdf")).toBe("calc package");
  });
});
