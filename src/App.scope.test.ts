// Ratchet for "project-scoped state survives a project switch": the open project changes in one
// place (enterScope, which resets project-scoped state and bumps the epoch), and the components
// holding project-local state are keyed on that epoch so a switch remounts them.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const app = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

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
});
