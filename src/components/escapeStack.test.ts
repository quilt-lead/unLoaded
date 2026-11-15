import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { dispatchEscape, registerEscapeFallback, registerEscapeLayer } from './escapeStack';

describe('escapeStack: one Escape does one thing', () => {
  it('closes only the topmost open layer, then the next, then runs the fallback', () => {
    const calls: string[] = [];
    const offFallback = registerEscapeFallback(() => calls.push('clear selection'));
    const offPanel = registerEscapeLayer(() => calls.push('panel'));
    const offMenu = registerEscapeLayer(() => calls.push('menu'));

    expect(dispatchEscape()).toBe('layer');
    expect(calls).toEqual(['menu']);
    offMenu(); // the menu closed, so it unregisters
    expect(dispatchEscape()).toBe('layer');
    expect(calls).toEqual(['menu', 'panel']);
    offPanel();
    expect(dispatchEscape()).toBe('fallback');
    expect(calls).toEqual(['menu', 'panel', 'clear selection']);
    offFallback();
    expect(dispatchEscape()).toBe('none');
  });

  it('unregistering a lower layer keeps the top one on top', () => {
    const calls: string[] = [];
    const offA = registerEscapeLayer(() => calls.push('a'));
    const offB = registerEscapeLayer(() => calls.push('b'));
    offA();
    dispatchEscape();
    expect(calls).toEqual(['b']);
    offB();
  });

  // ratchet: a component that listens for Escape on window/document itself would fire alongside the
  // stack (a menu closing AND the selection clearing). Escape handling inside an element's own
  // onKeyDown (an input cancelling a rename) is fine; only global listeners are banned.
  it('no file under src/ listens for Escape globally except escapeStack.ts', () => {
    const srcDir = fileURLToPath(new URL('../', import.meta.url));
    const files: string[] = [];
    const walk = (d: string) => {
      for (const f of readdirSync(d)) {
        const p = join(d, f);
        if (statSync(p).isDirectory()) walk(p);
        else if (/\.(ts|tsx)$/.test(f) && !/\.test\.tsx?$/.test(f)) files.push(p);
      }
    };
    walk(srcDir);
    const offenders = files.filter((p) => {
      if (p.endsWith(join('components', 'escapeStack.ts'))) return false;
      const s = readFileSync(p, 'utf8');
      // for each global keydown listener, look at the code that defines it: from the start of the
      // enclosing effect (or the file) to the addEventListener call. An element's own onKeyDown
      // handling Escape (e.g. an inline rename input) is local and allowed.
      const listener = /(window|document)\.addEventListener\(\s*['"]keydown['"]/g;
      for (let m = listener.exec(s); m; m = listener.exec(s)) {
        const start = Math.max(0, s.lastIndexOf('useEffect(', m.index));
        if (/['"]Escape['"]/.test(s.slice(start, m.index))) return true;
      }
      return false;
    });
    expect(offenders).toEqual([]);
  });
});
