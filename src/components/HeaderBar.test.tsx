import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { ColorMode } from '../types/bim';
import { HeaderBar } from './HeaderBar';

const noop = () => {};
const renderHeader = (options: { colorMode?: ColorMode; hasUtilization?: boolean } = {}) =>
  renderToStaticMarkup(
    <HeaderBar
      activeView="element-graph"
      onChangeView={noop}
      calcCount={0}
      colorMode={options.colorMode ?? 'type'}
      onChangeColorMode={noop}
      hasUtilization={options.hasUtilization ?? false}
      persistent
      source={null}
      busy={false}
      projects={[]}
      activeProjectId={null}
      onSwitchProject={noop}
      onNewProject={noop}
      onSaveProject={null}
      onLoadSample={noop}
      onLoadDemo={noop}
      onUploadModel={noop}
      onUploadCalcs={noop}
      onOpenFile={noop}
      diffRevs={null}
      compareOpen={false}
      onToggleCompare={noop}
      onSwapDatabases={noop}
      onClearDiff={noop}
    />,
  );

describe('workspace header', () => {
  it('keeps the top bar free of project and demo metadata', () => {
    const markup = renderHeader();

    expect(markup).toContain('src="/unloaded-logo.svg"');
    expect(markup).toContain('alt="CalcMap"');
    expect(markup).toContain('draggable="false"');
    expect(markup).not.toContain('Untitled project');
    expect(markup).not.toContain('DEMO DATA');
    expect(markup).not.toContain('harborview-tower-rev1-base.json');
    expect(markup).toContain('aria-haspopup="menu"');
    expect(markup).toContain('Project');
    expect(markup).not.toContain('IFC 4.3');
    expect(markup).not.toContain('ELEMENT TOPOLOGY');
    expect(markup).not.toContain('CALCULATION GRAPH ↔ 3D MODEL');
    expect(markup).not.toContain('Inspector');
  });

  it('uses a neutral indicator for the active workspace view', () => {
    const markup = renderHeader();

    expect(markup).toContain('workspace-view-indicator');
    expect(markup).toContain('bg-white/[0.10]');
    expect(markup).not.toContain('bg-indigo-600/25');
  });

  it('restores color-mode controls and keeps the heatmap unavailable without utilization data', () => {
    const markup = renderHeader({ colorMode: 'confidence' });

    expect(markup).toContain('aria-label="Colour elements by"');
    expect(markup).toContain('>Type</button>');
    expect(markup).toContain('>Review</button>');
    expect(markup).toContain('>Confidence</button>');
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain('aria-label="Toggle utilization heatmap"');
    const heatmapButton = markup.match(/<button[^>]*aria-label="Toggle utilization heatmap"[^>]*>/)?.[0];
    expect(heatmapButton).toContain('disabled=""');
    expect(markup).toContain('No utilisation data');
  });

  it('enables the heatmap when utilization data exists and removes the reset control', () => {
    const markup = renderHeader({ hasUtilization: true });

    expect(markup).toContain('title="Colour elements by demand / capacity utilisation"');
    const heatmapButton = markup.match(/<button[^>]*aria-label="Toggle utilization heatmap"[^>]*>/)?.[0];
    expect(heatmapButton).not.toContain('disabled=""');
    expect(markup).not.toContain('Reset view, filters and panels');
  });
});
