/**
 * Parity with the Python prototype (prototyping/calc-graph/backend/calcgraph).
 *
 * fixtures/golden/*.json are the Python pipeline's outputs on the synthetic package
 * (fixtures/calc_package.pdf + model_rev1.ifc, `synth.generate --seed 7`), dumped by
 * fixtures/golden/dump_golden.py. The rule modules get Python's own page text and
 * element records as input, so their output must match exactly.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  inferCalcDeps,
  propagateImpact,
  runMapping,
  segment,
  type Calc,
  type CalcEdge,
  type CalcElement,
  type CalcLink,
  type CalcPackage,
  type ImpactResult,
  type LoadEdge,
} from '../src/index.ts';

const golden = <T>(name: string): T =>
  JSON.parse(readFileSync(fileURLToPath(new URL(`./fixtures/golden/${name}`, import.meta.url)), 'utf8')) as T;

const pkg = golden<CalcPackage>('pages.json');
const elements = golden<CalcElement[]>('elements.json');
const pyCalcs = golden<Calc[]>('calcs.json');
const pyLinks = golden<CalcLink[]>('links.json');
const pyEdges = golden<CalcEdge[]>('calc_edges.json');
const loadEdges = golden<LoadEdge[]>('load_edges.json');
const pyImpact = golden<ImpactResult[]>('impact.json');

describe('parity with the Python calc-graph pipeline', () => {
  const calcs = segment(pkg.pages);
  const links = runMapping(elements, calcs, pkg.pages);

  it('segments the package into the same calcs', () => {
    expect(calcs.length).toBe(12);
    expect(calcs).toEqual(pyCalcs); // includes mark_hits, set by the matcher on both sides
  });

  it('produces the same element <-> calc links (tier, confidence, span, snippet, rects)', () => {
    expect(links.length).toBe(pyLinks.length);
    expect(links).toEqual(pyLinks);
  });

  it('infers the same calc dependency edges with the same evidence', () => {
    expect(inferCalcDeps(calcs, pkg.pages, links)).toEqual(pyEdges);
  });

  it('propagates change / remove impact the same way', () => {
    const byId = new Map(elements.map((e) => [e.global_id, e]));
    expect(pyImpact.length).toBeGreaterThan(0);
    for (const want of pyImpact) {
      const got = propagateImpact(want.global_id, want.mode, loadEdges, pyLinks, pyEdges, byId);
      expect(got).toEqual(want);
    }
  });
});
