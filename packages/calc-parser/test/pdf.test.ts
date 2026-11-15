/**
 * End to end on the real files: pdf.js text extraction and the IFC adapter against
 * the Python pipeline (PyMuPDF + IfcOpenShell) on the same synthetic package.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import * as pdfjs from 'pdfjs-dist/legacy/build/pdf.mjs';
import { parseIfc } from '@unloaded/ifc-parser';
import {
  mapCalcs,
  readPdf,
  toCalcElements,
  type CalcElement,
  type CalcLink,
  type CalcPackage,
  type PdfjsLike,
} from '../src/index.ts';

const fixture = (name: string) => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));
const golden = <T>(name: string): T => JSON.parse(readFileSync(fixture(`golden/${name}`), 'utf8')) as T;

const pyPkg = golden<CalcPackage>('pages.json');
const pyElements = golden<CalcElement[]>('elements.json');
const pyLinks = golden<CalcLink[]>('links.json');

describe('pdf.js reader vs PyMuPDF', async () => {
  const pkg = await readPdf(new Uint8Array(readFileSync(fixture('calc_package.pdf'))), pdfjs as unknown as PdfjsLike);

  it('reads every page with the same size and image count', () => {
    expect(pkg.meta.page_count).toBe(pyPkg.meta.page_count);
    expect(pkg.pages.map((p) => [p.n, Math.round(p.width), Math.round(p.height), p.images])).toEqual(
      pyPkg.pages.map((p) => [p.n, Math.round(p.width), Math.round(p.height), p.images]),
    );
  });

  it('rebuilds the same page text', () => {
    for (const [i, p] of pkg.pages.entries()) expect(p.text, `page ${p.n}`).toBe(pyPkg.pages[i]!.text);
  });

  it('places word boxes close to MuPDF (highlight accuracy)', () => {
    // pdf.js gives run widths, not glyph positions, and MuPDF uses per-font ascent/descent,
    // so boxes are approximate. Measured: x p95 0.6 pt / max 2.9 pt; y max ~3 pt.
    const err: number[] = [];
    for (const [i, p] of pkg.pages.entries()) {
      const want = pyPkg.pages[i]!.words;
      expect(p.words.length, `page ${p.n}`).toBe(want.length);
      p.words.forEach((w, k) => {
        const v = want[k]!;
        expect([w[4], w[5]]).toEqual([v[4], v[5]]); // same text spans
        for (let j = 0; j < 4; j++) err.push(Math.abs(w[j]! - v[j]!));
      });
    }
    err.sort((a, b) => a - b);
    expect(err[Math.floor(err.length * 0.95)]).toBeLessThan(1.5);
    expect(err[err.length - 1]).toBeLessThan(4);
  });

  it('maps the same links from pdf.js pages as Python does from PyMuPDF pages', () => {
    const { links } = mapCalcs(pyElements, pkg.pages);
    const strip = (l: CalcLink) => ({ ...l, rects: l.rects.length });
    expect(links.map(strip)).toEqual(pyLinks.map(strip));
  });
});

describe('IFC adapter (web-ifc) vs IfcOpenShell', async () => {
  const model = await parseIfc(new Uint8Array(readFileSync(fixture('model_rev1.ifc'))), { fileName: 'model_rev1.ifc' });
  const levels = new Map(model.levels.map((l) => [l.id, l.name]));
  const els = toCalcElements(model.elements, levels);
  const byId = new Map(els.map((e) => [e.global_id, e]));

  it('yields the same elements with the same category, mark and storey', () => {
    expect(els.length).toBe(pyElements.length);
    for (const want of pyElements) {
      const got = byId.get(want.global_id);
      expect(got, want.global_id).toBeDefined();
      expect({ cat: got!.cat, mark: got!.mark, storey: got!.storey }).toEqual({
        cat: want.cat,
        mark: want.mark,
        storey: want.storey,
      });
    }
  });

  it('finds every section size IfcOpenShell found, plus geometry-derived plate / footing sizes', () => {
    let extra = 0;
    for (const want of pyElements) {
      const got = byId.get(want.global_id)!;
      if (want.profile.startsWith('HSS') && got.profile.startsWith(want.profile + '/')) {
        // Python bug: ifc_ingest's profile regex stops at "/", so HSS6X6X3/8 became HSS6X6X3 and never
        // matched the matcher's size regex (which reads HSS6X6X3/8). The TS parser keeps the fraction.
        continue;
      }
      if (want.profile) expect(got.profile, want.global_id).toBe(want.profile);
      else if (got.profile) {
        // @unloaded/ifc-parser synthesises "<depth>X<width>" from the profile / extrusion when the file names none
        expect(['Connection', 'Footing', 'Slab', 'Wall', 'Pile']).toContain(got.cat);
        expect(got.profile).toMatch(/^\d+X\d+$/);
        extra += 1;
      }
    }
    expect(extra).toBeGreaterThan(0);
  });

  it('maps the whole package from the TS IFC + TS PDF pipeline exactly like Python', async () => {
    const pkg = await readPdf(new Uint8Array(readFileSync(fixture('calc_package.pdf'))), pdfjs as unknown as PdfjsLike, {
      countImages: false,
    });
    const { links } = mapCalcs(els, pkg.pages);
    const key = (l: CalcLink) => `${l.calc_key}|${l.global_id}|${l.tier}|${l.conf}|${l.page}|${l.span}`;
    expect(links.map(key).sort()).toEqual(pyLinks.map(key).sort());
  });
});
