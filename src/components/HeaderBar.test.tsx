import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { HeaderBar } from './HeaderBar';

const renderHeader = (projectName = 'Harborview Tower') => renderToStaticMarkup(
  <HeaderBar
    projectName={projectName}
    activeView="element-graph"
    onChangeView={() => {}}
    calcCount={0}
    docCount={0}
    heatmapMode={false}
    onToggleHeatmap={() => {}}
    onUploadFile={() => {}}
    diffSummary={null}
    onSwapDatabases={() => {}}
    onClearDiff={() => {}}
  />,
);

describe('workspace header', () => {
  it('uses the brand mark without schema or graph-flow copy', () => {
    const markup = renderHeader();

    expect(markup).toContain('src="/unloaded-logo.svg"');
    expect(markup).toContain('alt="CalcMap"');
    expect(markup).toContain('draggable="false"');
    expect(markup).toContain('Harborview Tower');
    expect(markup).toContain('>Import</span>');
    expect(markup).toContain('>Compare</span>');
    expect(markup).toContain('workspace-view-indicator');
    expect(markup).not.toContain('Reset view');
    expect(markup).not.toContain('Import IFC / DB');
    expect(markup).not.toContain('Compare DB');
    expect(markup).not.toContain('IFC 4.3');
    expect(markup).not.toContain('ELEMENT TOPOLOGY');
    expect(markup).not.toContain('CALCULATION GRAPH ↔ 3D MODEL');
    expect(markup).not.toContain('Inspector');
  });

  it('omits the project title when no model is loaded', () => {
    const markup = renderHeader('');

    expect(markup).not.toContain('No Model Loaded');
    expect(markup).not.toContain('<h1');
  });
});
