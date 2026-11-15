// Ratchets over App.tsx's wiring (this suite has no DOM renderer; the behaviour each one guards is
// unit-tested in src/data/viewState.test.ts):
// - the open project changes in one place (enterScope, which resets project-scoped state and bumps
//   the epoch), and the components holding project-local state are keyed on that epoch;
// - a different REVISION of the same project on screen (entering, swapping, leaving a diff; a new
//   head) is not a project change: nothing resets user state on it. Round 1 keyed a reset effect on
//   the view's modelRevisionId, which in diff mode is B, so every diff entered, swap and exit wiped
//   groups, moved nodes, selection, impact, the PDF target and the 3D camera;
// - decisions and impact target the revision of the view on screen, not the one being loaded.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

// line endings normalised: a Windows checkout (core.autocrlf) has CRLF, and the slices below look for "\n"
const app = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');

/** The source of `const <name> = ...` up to the next line at the same indentation that closes it. */
function body(name: string): string {
  const start = app.indexOf(`  const ${name} = `);
  expect(start, `${name} not found in App.tsx`).toBeGreaterThan(-1);
  const end = app.indexOf('\n  );\n', start);
  const endFn = app.indexOf('\n  };\n', start);
  const stop = [end, endFn].filter((i) => i > -1).sort((a, b) => a - b)[0] ?? app.length;
  return app.slice(start, stop);
}

/** Every useEffect body in App.tsx. */
const effects = [...app.matchAll(/useEffect\(\(\) => \{([\s\S]*?)\n {2}\}, \[([^\]]*)\]\);/g)].map((m) => ({ body: m[1]!, deps: m[2]! }));

describe('App: one owner for the open project', () => {
  it('sets the scope only in the opening-project effect and in enterScope', () => {
    expect(app.match(/\bsetScope\(/g)?.length).toBe(2);
    expect(app).not.toMatch(/\bsetProjectId\(|\bsetExportView\(/);
  });

  it('keys every component with project-local state on the scope epoch', () => {
    for (const c of ['DocumentBrowser', 'RevisionPanel', 'PropertyInspector']) {
      expect(app).toMatch(new RegExp(`<${c}\\s+key=\\{scope\\.epoch\\}`));
    }
  });

  it('enterScope resets groups, moved nodes, selection, impact, PDF target and the camera', () => {
    const b = body('enterScope');
    for (const reset of ['setGroups([])', 'setMoved(new Map())', 'handleClearSelection()', 'setImpactReq(null)', 'setPdfTarget(null)', 'setResetTrigger(']) {
      expect(b).toContain(reset);
    }
  });
});

describe('App: a revision change is not a project change', () => {
  it('found the effects (the matcher still parses App.tsx)', () => {
    expect(effects.length).toBeGreaterThan(5);
  });

  // the round-1 `projectKey` effect is exactly this: it fails here
  it('no effect resets groups, moved nodes, the camera or the whole selection', () => {
    for (const e of effects) {
      expect(e.body).not.toMatch(/setGroups\(\[\]\)|setMoved\(new Map\(\)\)|setResetTrigger\(|handleClearSelection\(\)/);
    }
  });

  it('no effect is keyed on the revision ids of the view', () => {
    for (const e of effects) expect(e.deps).not.toMatch(/RevisionId|projectKey|diffRevs\??\.b\b/);
    expect(app).not.toMatch(/projectKey/);
  });

  it('pointers into the view are kept where they exist (keepWhatExists), once the view has settled', () => {
    const e = effects.find((x) => x.body.includes('keepWhatExists('));
    expect(e?.deps.replace(/\s/g, '')).toBe('view,viewSettled');
  });

  it('swapping A and B, or leaving the diff, does not clear the selection', () => {
    for (const h of ['handleSwapDatabases', 'handleClearDiff']) expect(body(h)).not.toContain('handleClearSelection');
  });
});

describe('App: writes target the revision on screen', () => {
  // round 1 passed diffRevs.b, which while B loads is not the revision on screen (placeholder data)
  it('decisions and impact are made on shownModelRev, and writes are off while the view is a placeholder', () => {
    expect(app).toMatch(/useImpact\(pid, [^)]*shownModelRev\)/);
    expect(app).toMatch(/mutateAsync\(\{ elementId, calcKey, action, modelRev: shownModelRev \}\)/);
    expect(app).toMatch(/canWrite=\{[^}]*!viewIsPlaceholder\}/);
    expect(app).not.toMatch(/useDecide\([^)]*diffRevs/);
  });
});

describe('App: one path for adding a revision from a file', () => {
  it('every upload goes through addRevisionFile; only it calls the upload mutations', () => {
    expect(app.match(/uploadModel\.mutateAsync\(/g)?.length).toBe(1);
    expect(app.match(/uploadCalcs\.mutateAsync\(/g)?.length).toBe(1);
    expect(app.match(/openAnyFile\(/g)?.length).toBe(1);
    expect(body('addRevisionFile')).toMatch(/uploadModel\.mutateAsync[\s\S]*uploadCalcs\.mutateAsync/);
    expect(app).toMatch(/onUploadModel=\{\(f\) => addRevisionFile\('model', f, \{ compareWithHead: true \}\)\}/);
  });

  it('an added revision is shown only if the user is still in the scope the upload started in', () => {
    expect(body('showAddedRevision')).toMatch(/scopeRef\.current\.epoch !== startEpoch\) return false/);
  });
});

describe('App: diff mode is entered on checked revisions', () => {
  it('the panel and the deep link go through requestDiff (diffRevisionsError)', () => {
    expect(body('requestDiff')).toContain('diffRevisionsError(revisions, a, b)');
    expect(body('handleCompare')).toContain('requestDiff(a, b)');
    expect(app).toMatch(/requestDiff\(cmp\[0\], cmp\[1\]\)/);
  });

  it('Exit and Swap are offered whenever diff mode is set, not only once the diff has loaded', () => {
    const header = readFileSync(new URL('./components/HeaderBar.tsx', import.meta.url), 'utf8');
    expect(header).toMatch(/\{p\.diffRevs && \(\s*<button type="button" onClick=\{p\.onClearDiff\}/);
    expect(header).toMatch(/\{p\.diffRevs && \(\s*<button type="button" onClick=\{p\.onSwapDatabases\}/);
  });
});
