import { describe, expect, it } from 'vitest';
import { clampPanelRect } from './DockableHudPanel';

describe('floating panel viewport bounds', () => {
  it('keeps a resized panel unchanged while it fits', () => {
    const rect = { left: 180, top: 140, width: 410, height: 320 };
    expect(clampPanelRect(rect, { width: 1200, height: 800 })).toEqual(rect);
  });

  it('brings an offscreen close button back into the viewport', () => {
    const rect = clampPanelRect(
      { left: 1100, top: 720, width: 320, height: 255 },
      { width: 800, height: 600 },
    );
    expect(rect).toEqual({ left: 472, top: 337, width: 320, height: 255 });
  });

  it('shrinks panels to fit short or narrow windows, including below their minimum size', () => {
    const rect = clampPanelRect(
      { left: 20, top: 370, width: 320, height: 255 },
      { width: 240, height: 160 },
    );
    expect(rect).toEqual({ left: 8, top: 8, width: 224, height: 144 });
  });

  it('keeps ordinary windows clear of the workspace header', () => {
    const rect = clampPanelRect(
      { left: -20, top: -50, width: 320, height: 255 },
      { width: 1200, height: 800 },
    );
    expect(rect.left).toBe(8);
    expect(rect.top).toBe(96);
  });
});
