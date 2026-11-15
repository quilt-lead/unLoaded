import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildGraph, type ModelInput } from '@unloaded/element-graph';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import { computeLitSet, elementEmphasis, type Emphasis } from '../utils/elementEmphasis';
import { buildPlanIndex } from '../utils/planSlice';
import { DockableHudPanel, PanelTabs } from './DockableHudPanel';
import { countRoles, PlanView2D } from './PlanView2D';
import { LevelLadder, rungOffsets } from './plan/LevelLadder';
import { PlanDrawing } from './plan/PlanDrawing';
import { fitCamera, inView, panBy, scaleBarMetres, toScreen, toWorld, zoomAt } from './plan/planCamera';

const root = new URL('../../', import.meta.url);
const topo = elementGraphToBim(buildGraph(JSON.parse(readFileSync(new URL('data/simple-frame.json', root), 'utf8')) as ModelInput).graph);
const nodes = topo.elementNodes;
const index = buildPlanIndex(nodes, topo.levels);
const noop = () => {};

const emphasisFor = (selected: string[]) => {
  const lit = computeLitSet(nodes, selected[0] ?? null, new Set(selected), new Set());
  const ctx = { colorMode: 'type' as const, diffMode: false, overlay: null, lit, isFilterActive: false, matchingNodeIds: new Set<string>() };
  const m = new Map<string, Emphasis>();
  for (const it of index.plans.get('L1')!.items) m.set(it.id, elementEmphasis(it.id, it.node, ctx));
  return m;
};

describe('plan camera', () => {
  const v = { w: 400, h: 300 };
  it('maps model metres to screen px with y up, and back', () => {
    const c = { cx: 10, cy: 5, s: 20 };
    expect(toScreen(c, v, [10, 5])).toEqual([200, 150]);
    expect(toScreen(c, v, [11, 6])).toEqual([220, 130]);
    expect(toWorld(c, v, [220, 130])).toEqual([11, 6]);
  });
  it('fits extents, zooms about the cursor and pans with the drag', () => {
    const c = fitCamera({ min: [0, 0], max: [36, 28] }, v, 40);
    expect(c).toEqual({ cx: 18, cy: 14, s: 220 / 28 });
    const q: [number, number] = [300, 80];
    const before = toWorld(c, v, q);
    const z = zoomAt(c, v, 2, q);
    expect(z.s).toBeCloseTo(c.s * 2);
    expect(toWorld(z, v, q)[0]).toBeCloseTo(before[0]);
    expect(toWorld(z, v, q)[1]).toBeCloseTo(before[1]);
    expect(panBy({ cx: 0, cy: 0, s: 10 }, 20, 10)).toEqual({ cx: -2, cy: 1, s: 10 });
    expect(inView(c, v, [18, 14])).toBe(true);
    expect(inView(c, v, [100, 14])).toBe(false);
  });
  it('picks a 1-2-5 scale bar', () => {
    expect(scaleBarMetres(20)).toBe(5);
    expect(scaleBarMetres(200)).toBe(0.5);
    expect(scaleBarMetres(3)).toBe(50);
  });
});

describe('PlanDrawing', () => {
  const plan = index.plans.get('L1')!;
  const camera = fitCamera(plan.extents!, { w: 600, h: 400 });
  const draw = (selected: string[]) =>
    renderToStaticMarkup(
      <svg>
        <PlanDrawing plan={plan} camera={camera} viewport={{ w: 600, h: 400 }} emphasis={emphasisFor(selected)} hoveredId={null} diffMode={false} />
      </svg>,
    );

  it('draws every item of the level as a selectable shape, with marks', () => {
    const svg = draw([]);
    for (const it of plan.items) expect(svg).toContain(`data-id="${it.id}"`);
    expect(svg).toContain('>B101</text>');
  });

  it('rings the selection in CalcMap green and dims the rest', () => {
    const beam = plan.items.find((i) => i.role === 'beam')!;
    const svg = draw([beam.id]);
    expect(svg).toContain('stroke="#14AE5C"');
    expect(svg).toMatch(/opacity="0.14"/);
  });
});

describe('level ladder', () => {
  it('spaces rungs by elevation, evenly when that crowds them', () => {
    const l = (id: string, elevation: number) => ({ id, name: id, elevation, hasSlab: true });
    expect(rungOffsets([l('a', 0), l('b', 3), l('c', 12)], 120)).toEqual([120, 90, 0]);
    expect(rungOffsets([l('a', 0), l('b', 0.1), l('c', 12)], 120)).toEqual([120, 60, 0]);
  });

  it('names the level, its datum and position, and disables the arrow at the top', () => {
    const html = renderToStaticMarkup(<LevelLadder levels={index.levels} currentId="L1" onChange={noop} />);
    expect(html).toContain('Level 1');
    expect(html).toContain('+3.500 m');
    expect(html).toContain('Level 2 of 2');
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Top level"/);
    expect(html).toContain('aria-label="Level down to Foundation"');
    expect(html).toContain('aria-current="true"');
  });
});

describe('PlanView2D', () => {
  const props = {
    nodes,
    onLevelChange: noop,
    selectedNodeId: null,
    selectedNodeIds: new Set<string>(),
    activeLoadChainNodeIds: new Set<string>(),
    matchingNodeIds: new Set<string>(),
    isFilterActive: false,
    colorMode: 'type' as const,
    diffMode: false,
    overlay: null,
    fitTrigger: 0,
    resetTrigger: 0,
    revealTrigger: 0,
    onSelectNode: noop,
  };

  it('shows the level control for a model with levels', () => {
    const html = renderToStaticMarkup(<PlanView2D {...props} index={index} levelId="L1" />);
    expect(html).toContain('aria-label="Plan level"');
    expect(html).not.toContain('No plan to draw');
  });

  it('says why there is no plan when the model has no geometry', () => {
    const html = renderToStaticMarkup(<PlanView2D {...props} index={buildPlanIndex([], [])} levelId={null} />);
    expect(html).toContain('No plan to draw');
    expect(html).not.toContain('aria-label="Plan level"');
  });

  it('summarises a level in words', () => {
    expect(countRoles(index.plans.get('L1')!.items)).toBe('1 beam, 2 columns, 2 connections');
  });
});

describe('model panel tabs', () => {
  it('are WAI-ARIA tabs: one selected and focusable, each controlling the panel body', () => {
    const html = renderToStaticMarkup(
      <PanelTabs panelId="p" tabs={[{ id: '3d', label: '3D' }, { id: 'plan', label: 'Plan' }]} active="plan" onChange={noop} />,
    );
    expect(html).toContain('role="tablist"');
    expect(html).toMatch(/id="p-tab-plan" aria-selected="true" aria-controls="p-tabpanel" tabindex="0"/);
    expect(html).toMatch(/id="p-tab-3d" aria-selected="false" aria-controls="p-tabpanel" tabindex="-1"/);
  });

  it('render in the title bar, with the body as the tab panel', () => {
    const html = renderToStaticMarkup(
      <DockableHudPanel
        id="v"
        title="Structural Model"
        indicatorClassName=""
        dockSide="right"
        defaultPos={{ left: 0, top: 0, width: 300, height: 200 }}
        zIndex={1}
        onFocus={noop}
        onChangeDockSide={noop}
        tabs={[{ id: '3d', label: '3D' }, { id: 'plan', label: 'Plan' }]}
        activeTab="3d"
        onTabChange={noop}
      >
        body
      </DockableHudPanel>,
    );
    expect(html).toContain('role="tablist"');
    expect(html).toMatch(/id="v-tabpanel" role="tabpanel" aria-labelledby="v-tab-3d"/);
  });
});
