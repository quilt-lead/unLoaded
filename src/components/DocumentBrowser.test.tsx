import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { BimNode, CalcPackage } from '../types/bim';
import { DocumentBrowser, calcMatchesQuery } from './DocumentBrowser';

// Ported from prod's test onto the branch's data contract. Prod's version rendered `FlattenedDocument`s
// with per-document revision histories; on this branch documents are real calcs from a calc package
// (CalcPackage, D6) and revisions are project-level model/calc revisions, so there is no per-document
// revision picker to test. What carries over: page references come from the calc's real pages (never
// an invented "pp. 1–4"), a search finds calcs by the elements linked to them, and the empty state
// says why the list is empty.
const calc: CalcPackage = {
  key: 'beam-checks',
  title: 'Beam checks',
  software: 'RAM',
  elementType: 'beam',
  pages: [5, 6, 7],
  scanned: false,
  frontMatter: false,
  titleBox: null,
  color: '#ffffff',
  regions: [],
};

const b12: BimNode = { id: 'GUID-B12', label: 'B12', kind: 'element', level: 2, r: 10, x: 0, y: 0 };

const render = (calcs: CalcPackage[], elementNodes: BimNode[] = [], calcToElementIds = new Map<string, string[]>()) =>
  renderToStaticMarkup(
    <DocumentBrowser
      calcs={calcs}
      calcPackageName="calcs.pdf"
      pdfUrl={null}
      elementNodes={elementNodes}
      calcToElementIds={calcToElementIds}
      calcDependencies={[]}
      groups={[]}
      findings={[]}
      selectedElement={null}
      filterBySelectedElement={false}
      onClearElementFilter={() => {}}
      target={null}
      onChangeTarget={() => {}}
      diffMode={false}
      onLocateElement={() => {}}
      onLocateCalc={() => {}}
      onSelectElements={() => {}}
    />,
  );

describe('calc package list', () => {
  it("shows the calc's real page range, never an invented one", () => {
    const markup = render([calc], [b12], new Map([[calc.key, [b12.id]]]));
    expect(markup).toContain('pp. 5–7');
    expect(markup).not.toContain('pp. 1–4');
    expect(markup).toContain('1 linked');
  });

  it('has a labelled search field', () => {
    const markup = render([calc]);
    expect(markup).toContain('type="search"');
    expect(markup).toContain('aria-label="Search PDF calculations"');
  });

  it('says why the list is empty: no model, or a model without a calc package', () => {
    expect(render([])).toContain('Import a model and upload a calc package PDF');
    expect(render([], [b12])).toContain('This model has no calc package yet');
  });
});

describe('calc search', () => {
  it("matches a calc's own text", () => {
    expect(calcMatchesQuery(calc, 'ram', [])).toBe(true);
    expect(calcMatchesQuery(calc, '  ', [])).toBe(true);
    expect(calcMatchesQuery(calc, 'column', [])).toBe(false);
  });

  it('matches a calc by the id or label of an element linked to it', () => {
    expect(calcMatchesQuery(calc, 'b12', [b12])).toBe(true);
    expect(calcMatchesQuery(calc, 'guid-b1', [b12])).toBe(true);
    expect(calcMatchesQuery(calc, 'b13', [b12])).toBe(false);
  });
});
