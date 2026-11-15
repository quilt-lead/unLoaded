import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { HeaderBar } from './HeaderBar';

const noop = () => {};
const renderHeader = (subtitle = '') =>
  renderToStaticMarkup(
    <HeaderBar
      projectName="Harborview Tower"
      subtitle={subtitle}
      activeView="element-graph"
      onChangeView={noop}
      calcCount={0}
      colorMode="type"
      onChangeColorMode={noop}
      hasUtilization={false}
      persistent
      hasDemoData={false}
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
      diffSummary={null}
      diffRevs={null}
      compareOpen={false}
      onToggleCompare={noop}
      onSwapDatabases={noop}
      onClearDiff={noop}
      onResetAll={noop}
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

  it('shows what is loaded (model ⇄ calc package) once there is a project', () => {
    expect(renderHeader('model_rev1.ifc ⇄ calc_package.pdf')).toContain('model_rev1.ifc ⇄ calc_package.pdf');
  });
});
