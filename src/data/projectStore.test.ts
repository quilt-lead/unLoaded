// Save project -> Open project through the shared format (@unloaded/project-file): the app's writer
// (exportProject), the shared reader (parseProjectFile, what the MCP server also reads with) and the
// app's importer (importProject) agree, payloads and the decision log included. Runs on the store's
// memory backend (no IndexedDB in Node).
import { describe, expect, it } from 'vitest';
import type { SerializedElementGraph } from '@unloaded/element-graph';
import { decodeBase64, parseProjectFile, type ProjectFile } from '@unloaded/project-file';
import { addDecision, addRevision, createProject, exportProject, getBlob, getGraph, importProject, listRevisions } from './projectStore';

const graph = (mark: string): SerializedElementGraph =>
  ({
    format: 'unloaded.element-graph',
    version: 1,
    meta: { version: 1, units: 'm' },
    levels: [{ id: 'L1', name: 'Level 1', elevation: 0 }],
    nodes: [{ id: 'C1', kind: 'column', ifcType: 'IfcColumn', mark, levelId: 'L1', params: {} }],
    edges: [],
  }) as unknown as SerializedElementGraph;

/** Bytes with every value, past the encoder's 32 KiB chunk. */
const pdfBytes = Uint8Array.from({ length: 40_000 }, (_, i) => (i * 13 + 5) % 256);

/** A file with store ids replaced by each revision's (kind, seq), so two imports compare equal. */
function normalise(f: ProjectFile) {
  const key = new Map(f.revisions.map((r) => [r.id, `${r.kind}#${r.seq}`]));
  return {
    project: f.project.name,
    revisions: f.revisions.map(({ id: _id, ...r }) => r),
    decisions: f.decisions.map((d) => ({
      ...d,
      modelRev: d.modelRev == null ? null : key.get(d.modelRev),
      calcRev: d.calcRev == null ? null : key.get(d.calcRev),
    })),
  };
}

describe('project file: app writer -> shared reader -> app importer', () => {
  it('round-trips revisions, payloads and decisions', async () => {
    const p = await createProject('Round trip');
    const m1 = await addRevision(p.id, { kind: 'model', label: 'rev 1', sourceName: 'a.ifc', mediaType: 'application/x-step', meta: { elements: 1, project: null } }, new Blob(['ISO-10303-21;']), { graph: graph('C-1') });
    const c1 = await addRevision(p.id, { kind: 'calcs', label: 'calcs', sourceName: 'c.pdf', mediaType: 'application/pdf', meta: { pages: 1 } }, new Blob([pdfBytes]), { extraction: { calcs: [], pages: [] } });
    const m2 = await addRevision(p.id, { kind: 'model', label: 'rev 2', sourceName: 'b.ifc', mediaType: 'application/x-step', meta: {} }, new Blob(['ISO-10303-21;2']), { graph: graph('C-1A') });
    await addDecision({ projectId: p.id, globalId: 'C1', calcKey: 'k1', action: 'confirm', actor: 'reviewer', note: null, modelRev: m1.id, calcRev: c1.id });
    await addDecision({ projectId: p.id, globalId: 'C1', calcKey: 'k1', action: 'reject', actor: 'reviewer', note: 'wrong size', modelRev: m2.id, calcRev: null });

    const saved = await exportProject(p.id);
    const read = parseProjectFile(JSON.parse(JSON.stringify(saved)));
    expect(read).toEqual(JSON.parse(JSON.stringify(saved)));
    expect(decodeBase64(read.revisions.find((r) => r.kind === 'calcs')!.blob)).toEqual(pdfBytes);

    const q = await importProject(read);
    expect(q.id).not.toBe(p.id);
    const revs = await listRevisions(q.id);
    const pdf = revs.find((r) => r.kind === 'calcs')!;
    expect(new Uint8Array(await (await getBlob(pdf.id))!.arrayBuffer())).toEqual(pdfBytes);
    const head = revs.filter((r) => r.kind === 'model').sort((a, b) => b.id - a.id)[0]!;
    expect((await getGraph(head.id))?.nodes[0]?.mark).toBe('C-1A');

    expect(normalise(await exportProject(q.id))).toEqual(normalise(saved));
  });

  it('refuses to save a model revision whose graph is missing (no reader could open the file)', async () => {
    const p = await createProject('No graph');
    await addRevision(p.id, { kind: 'model', label: 'x', sourceName: 'x.ifc', mediaType: 'application/x-step', meta: {} }, new Blob(['x']), {});
    await expect(exportProject(p.id)).rejects.toThrow(/has no stored element graph/);
  });
});
