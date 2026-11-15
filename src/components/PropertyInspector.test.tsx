import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PropertyInspector } from './PropertyInspector';
import type { BimNode } from '../types/bim';

const beam: BimNode = {
  id: 'beam-1', label: 'B101', type: 'IfcBeam', level: 2, r: 10, x: 0, y: 0,
};

function renderInspector(node: BimNode, relatedNodes: BimNode[] = []) {
  return renderToStaticMarkup(
    <PropertyInspector
      nodes={[node, ...relatedNodes]}
      links={[]}
      rawLinks={[]}
      selectedNodeId={node.id}
      selectedNodeIds={new Set([node.id])}
      activeLoadChainNodeIds={new Set(relatedNodes.map((related) => related.id))}
      heatmapMode={false}
      diffMode
      onSelectNode={() => {}}
      onClearSelection={() => {}}
      onOpenDocument={() => {}}
      onSwitchToCalcGraph={() => {}}
    />,
  );
}

describe('PropertyInspector data display', () => {
  it('does not turn missing engineering data into design values or mapped PDFs', () => {
    const html = renderInspector({ ...beam, sectionSize: 'W310' });

    expect(html).toContain('W310');
    expect(html.match(/>—</g)).toHaveLength(2);
    expect(html).not.toContain('65 MPa');
    expect(html).not.toContain('0 kN');
    expect(html).not.toContain('Grid Bay');
    expect(html).not.toContain('F2F');
    expect(html).not.toContain('Demand / Capacity Utilization');
    expect(html).toContain('No PDF calculations mapped to this selection.');
  });

  it('preserves explicit zero values and bay spacing even without a section size', () => {
    const html = renderInspector({ ...beam, ratedStrength: 0, axialLoadKn: 0, utilization: 0, baySpacing: '6 m × 6 m' });

    expect(html).toContain('0 MPa');
    expect(html).toContain('0 kN');
    expect(html).toContain('6 m × 6 m');
    expect(html).toContain('Demand / Capacity Utilization');
    expect(html).toContain('>0%</span>');
  });

  it('omits invalid numeric data and preserves reported overload percentages', () => {
    const invalid = renderInspector({ ...beam, ratedStrength: NaN, axialLoadKn: Infinity, utilization: NaN });
    expect(invalid).not.toContain('NaN');
    expect(invalid).not.toContain('Infinity');
    expect(invalid).not.toContain('Demand / Capacity Utilization');

    const overload = renderInspector({ ...beam, utilization: 1.25 });
    expect(overload).toContain('>125%</span>');
    expect(overload).toContain('width:100%');
  });

  it('does not label same-level or unknown-level load-path neighbors as below', () => {
    const html = renderInspector({ ...beam, floorNum: 2 }, [
      { ...beam, id: 'same-level', floorNum: 2 },
      { ...beam, id: 'unknown-level' },
    ]);

    expect(html).toContain('Same Level • —');
    expect(html).toContain('Connected • —');
    expect(html).not.toContain('Below');
    expect(html).not.toContain('0 kN');
  });

  it.each([['added', 'B'], ['removed', 'A']] as const)('explains %s elements as belonging to only one database', (diffStatus, database) => {
    const html = renderInspector({ ...beam, diffStatus });

    expect(html).toContain(`This element exists only in DB ${database}.`);
    expect(html).not.toContain('No property changes');
  });
});
