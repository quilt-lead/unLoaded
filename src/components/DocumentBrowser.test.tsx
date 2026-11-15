import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { FlattenedDocument } from '../types/bim';
import { DocumentBrowser } from './DocumentBrowser';

const document: FlattenedDocument = {
  id: 'beam-package',
  title: 'Beam checks',
  type: 'Calculation (PDF)',
  code: 'B-01',
  rev: 'Rev C',
  pages: 8,
  date: '2026-11-14',
  summary: 'Current beam checks',
  nodeId: 'B1',
  nodeLabel: 'B1',
  nodeColor: '#ffffff',
  nodeDisplayType: 'IfcBeam',
  mappedElementIds: ['B1'],
};

const renderDocument = (doc: FlattenedDocument) => renderToStaticMarkup(
  <DocumentBrowser
    allDocs={[doc]}
    nodes={[]}
    links={[]}
    selectedNodeId={null}
    activeLoadChainNodeIds={new Set()}
    filterBySelectedElement={false}
    onClearElementFilter={() => {}}
    initialDocId={doc.id}
    onLocateElement={() => {}}
  />
);

describe('document revision preview', () => {
  it('opens the declared current revision when history is oldest first', () => {
    const markup = renderDocument({
      ...document,
      revisions: [
        { rev: 'Rev A', date: '2026-10-01', pages: 3, summary: 'Original beam checks' },
        { rev: document.rev, date: document.date, pages: document.pages, summary: document.summary },
      ],
    });
    expect(markup).toContain('Issued 2026-11-14');
    expect(markup).toContain('Calculation Scope &amp; Design Check (Rev C)');
    expect(markup).not.toContain('Issued 2026-10-01');
  });

  it('keeps the current revision selectable when only past revisions are in history', () => {
    const markup = renderDocument({
      ...document,
      revisions: [{ rev: 'Rev A', date: '2026-10-01', pages: 3, summary: 'Original beam checks' }],
    });
    expect(markup).toContain('Rev C (2026-11-14)</button>');
    expect(markup).toContain('Issued 2026-11-14');
    expect(markup).not.toContain('pp. 1–4');
  });
});
