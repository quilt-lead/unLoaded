import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PropertyInspector } from './PropertyInspector';
import type { BimNode, LoadPathEdge } from '../types/bim';

// Ported from prod's test onto the branch's view model (src/types/bim.ts): the fields prod's version
// asserted on (ratedStrength, axialLoadKn, baySpacing, sectionSize, floorNum, documents) were removed
// from the contract (D6) because nothing real supplies them; the behaviour under test is the same:
// missing engineering data is never shown as a value, real values (zero, overload) are, load-path
// neighbours are labelled by the graph's own direction, and diff-only elements say which revision.
const beam: BimNode = {
  id: 'beam-1', label: 'B101', kind: 'element', elementKind: 'beam', ifcType: 'IfcBeam', level: 2, r: 10, x: 0, y: 0,
};

function renderInspector(node: BimNode, relatedNodes: BimNode[] = [], loadPath: LoadPathEdge[] = []) {
  return renderToStaticMarkup(
    <PropertyInspector
      node={node}
      elementNodes={[node, ...relatedNodes]}
      calcs={[]}
      calcDependencies={[]}
      loadPath={loadPath}
      connectivity={[]}
      calcToElementIds={new Map()}
      typicalGroups={[]}
      findings={[]}
      producers={null}
      counts={null}
      groups={[]}
      selectedNodeIds={new Set([node.id])}
      activeLoadChainNodeIds={new Set()}
      diffMode
      impact={null}
      impactLoading={false}
      canWrite
      busy={false}
      onSelectNode={() => {}}
      onSelectCalc={() => {}}
      onSelectGroup={() => {}}
      onRenameGroup={() => {}}
      onClearSelection={() => {}}
      onOpenTarget={() => {}}
      onShowElementCalcs={() => {}}
      onDecide={() => {}}
      onImpact={() => {}}
      onClearImpact={() => {}}
    />,
  );
}

describe('PropertyInspector data display', () => {
  it('does not turn missing engineering data into design values or mapped PDFs', () => {
    const html = renderInspector({ ...beam, size: 'W310' });

    expect(html).toContain('W310');
    expect(html).toContain('>—<'); // no mark: shown as missing, not invented
    expect(html).not.toContain('MPa');
    expect(html).not.toContain('kN');
    expect(html).not.toContain('Grid Bay');
    expect(html).not.toContain('Demand / Capacity Utilization');
    expect(html).toContain('No calc in the package names this element');
  });

  it('preserves an explicit zero utilization', () => {
    const html = renderInspector({ ...beam, utilization: 0 });

    expect(html).toContain('Demand / Capacity Utilization');
    expect(html).toContain('>0%</span>');
  });

  it('omits invalid numeric data and preserves reported overload percentages', () => {
    const invalid = renderInspector({ ...beam, utilization: NaN });
    expect(invalid).not.toContain('NaN');
    expect(invalid).not.toContain('Demand / Capacity Utilization');

    const infinite = renderInspector({ ...beam, utilization: Infinity });
    expect(infinite).not.toContain('Infinity');
    expect(infinite).not.toContain('Demand / Capacity Utilization');

    const overload = renderInspector({ ...beam, utilization: 1.25 });
    expect(overload).toContain('>125%</span>');
    expect(overload).toContain('width:100%');
  });

  it('labels load-path neighbours by the graph edge direction, not by guessed levels', () => {
    const above = { ...beam, id: 'slab-1', label: 'S1' };
    const below = { ...beam, id: 'col-1', label: 'C1' };
    const html = renderInspector(beam, [above, below], [
      { source: 'slab-1', target: 'beam-1', rule: 'test' },
      { source: 'beam-1', target: 'col-1', rule: 'test' },
    ]);

    expect(html).toContain('carries from');
    expect(html).toContain('delivers to');
    expect(html).not.toContain('Below');
    expect(html).not.toContain('kN');
  });

  it.each([['added', 'B'], ['removed', 'A']] as const)('explains %s elements as belonging to only one revision', (diffStatus, rev) => {
    const html = renderInspector({ ...beam, diffStatus });

    expect(html).toContain(`This element exists only in rev ${rev}.`);
    expect(html).not.toContain('No property changes');
  });
});
