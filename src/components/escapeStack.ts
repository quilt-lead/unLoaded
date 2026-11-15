// The one owner of the Escape key. A press does exactly one thing: it closes the topmost open layer
// (a menu, a panel), and only when no layer is open does it run the fallback (App: clear the
// selection). Components never listen for Escape on window/document themselves; they register here
// (src/components/escapeStack.test.ts fails on a file that does), so two handlers can never both
// react to the same press.
import { useEffect, useRef } from 'react';

type Close = () => void;

const layers: { close: Close }[] = [];
let fallback: Close | null = null;
let listening = false;

/** Run one Escape: the most recently opened layer closes, else the fallback runs. */
export function dispatchEscape(): 'layer' | 'fallback' | 'none' {
  const top = layers[layers.length - 1];
  if (top) {
    top.close();
    return 'layer';
  }
  if (fallback) {
    fallback();
    return 'fallback';
  }
  return 'none';
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key !== 'Escape' || e.defaultPrevented) return;
  dispatchEscape();
}

function syncListener() {
  if (typeof window === 'undefined') return;
  const want = layers.length > 0 || fallback != null;
  if (want && !listening) window.addEventListener('keydown', onKeyDown);
  if (!want && listening) window.removeEventListener('keydown', onKeyDown);
  listening = want;
}

/** Register an open layer; it sits on top of every layer opened before it. Returns the unregister. */
export function registerEscapeLayer(close: Close): () => void {
  const entry = { close };
  layers.push(entry);
  syncListener();
  return () => {
    const i = layers.indexOf(entry);
    if (i >= 0) layers.splice(i, 1);
    syncListener();
  };
}

/** Set what Escape does when no layer is open. Returns the unregister. */
export function registerEscapeFallback(handler: Close): () => void {
  fallback = handler;
  syncListener();
  return () => {
    if (fallback === handler) fallback = null;
    syncListener();
  };
}

/** While `open`, Escape closes this layer (and only this layer) via `close`. */
export function useEscapeLayer(open: boolean, close: Close) {
  const ref = useRef(close);
  ref.current = close;
  useEffect(() => (open ? registerEscapeLayer(() => ref.current()) : undefined), [open]);
}

/** Escape with nothing open runs `handler`. One per app (the last registered wins). */
export function useEscapeFallback(handler: Close) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => registerEscapeFallback(() => ref.current()), []);
}
