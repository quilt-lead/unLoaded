import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { HeaderBar } from './HeaderBar';

const renderHeader = () => renderToStaticMarkup(
  <HeaderBar
    projectName="Harborview Tower"
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
    onResetAll={() => {}}
  />,
);

describe('workspace header', () => {
  it('uses the brand mark without schema or graph-flow copy', () => {
    const markup = renderHeader();

    expect(markup).toContain('src="/unloaded-logo.svg"');
    expect(markup).toContain('alt="CalcMap"');
    expect(markup).toContain('Harborview Tower');
    expect(markup).not.toContain('IFC 4.3');
    expect(markup).not.toContain('ELEMENT TOPOLOGY');
    expect(markup).not.toContain('CALCULATION GRAPH ↔ 3D MODEL');
    expect(markup).not.toContain('Inspector');
  });
});
