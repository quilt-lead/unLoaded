// Undo / redo for the move-a-column page: ONE history for every edit.
//
// Two kinds of entry share one linear stack:
//  - "setup": an edit of the move setup (column, dx/dy, drag, snap, Remove, scenario, Reset,
//    Check impact). Undo/redo swaps the whole setup snapshot, so the Check impact query (keyed by
//    the committed move) follows the restored setup with no extra wiring.
//  - "model" / "calc": a write to a revision store (Apply as model revision, Re-run calcs). The
//    store never deletes, so undo/redo asks the caller to write ANOTHER revision restoring the
//    other side (POST /api/v2/revisions/{model,calc}/restore) and records the new head.
//
// The page edits the setup only through this hook: `record` for a step that belongs in the history,
// `preview` for transient frames (a drag in progress, which `record` then closes as one step).
// History + setup persist in sessionStorage (every access in try/catch; the page works without it).
import { useCallback, useEffect, useRef, useState } from "react";
import type { Move } from "./api";

export interface Setup {
  selected: string | null;
  dx: number;
  dy: number;
  remove: boolean;
  step: number;
  /** the move Check impact ran for (null = nothing checked) */
  committed: Move | null;
}

export const EMPTY_SETUP: Setup = {
  selected: null,
  dx: 0,
  dy: 0,
  remove: false,
  step: 1,
  committed: null,
};

export type HistoryEntry =
  | {
      kind: "setup";
      label: string;
      before: Setup;
      after: Setup;
      key?: string;
      at: number;
    }
  /** rev = the applied revision, parent = the head before it (NOT its store parent, which is the base
   * design), head = the current head this entry produced */
  | { kind: "model"; label: string; rev: number; parent: number; head: number }
  /** rev = the re-run's calc revision, prev = the calc state before it (null = original package), head = current */
  | {
      kind: "calc";
      label: string;
      rev: string;
      prev: string | null;
      head: string;
    };

export type StoreEntry = Extract<HistoryEntry, { kind: "model" | "calc" }>;

interface State {
  setup: Setup;
  /** the setup as of the last recorded step (the `before` of the next one) */
  base: Setup;
  past: HistoryEntry[];
  future: HistoryEntry[];
  /** the calc revision the history last wrote (null = original package) */
  calcHead: string | null;
}

const KEY = "calc-graph.v2.move-history.v1";
const MAX = 200;
const COALESCE_MS = 1500;

function load(): State {
  const empty: State = {
    setup: EMPTY_SETUP,
    base: EMPTY_SETUP,
    past: [],
    future: [],
    calcHead: null,
  };
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return empty;
    const s = JSON.parse(raw) as Partial<State>;
    if (
      !s ||
      typeof s !== "object" ||
      !Array.isArray(s.past) ||
      !Array.isArray(s.future) ||
      !s.setup
    )
      return empty;
    const setup = { ...EMPTY_SETUP, ...s.setup };
    return {
      setup,
      base: setup,
      past: s.past,
      future: s.future,
      calcHead: s.calcHead ?? null,
    };
  } catch {
    return empty;
  }
}

function save(s: State) {
  try {
    window.sessionStorage.setItem(
      KEY,
      JSON.stringify({
        setup: s.base,
        past: s.past,
        future: s.future,
        calcHead: s.calcHead,
      }),
    );
  } catch {
    /* storage blocked or full: history just will not survive a reload */
  }
}

export type Direction = "undo" | "redo";
/** writes the restoring revision for a store entry; returns the new head and the line to show */
export type StoreUndo = (
  entry: StoreEntry,
  dir: Direction,
) => Promise<{ head: number | string; note: string }>;

const isTyping = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  if (!el) return false;
  if (el.isContentEditable || el.tagName === "TEXTAREA") return true;
  if (el.tagName !== "INPUT") return false;
  return ![
    "checkbox",
    "radio",
    "button",
    "submit",
    "reset",
    "range",
    "color",
    "file",
  ].includes((el as HTMLInputElement).type);
};

export function useMoveHistory(storeUndo: StoreUndo) {
  const [state, setState] = useState<State>(load);
  const ref = useRef(state);
  ref.current = state;
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const storeRef = useRef(storeUndo);
  storeRef.current = storeUndo;

  useEffect(() => save(state), [state]);

  /** transient: change what is shown without adding a step (drag frames) */
  const preview = useCallback(
    (patch: Partial<Setup>) =>
      setState((s) => ({ ...s, setup: { ...s.setup, ...patch } })),
    [],
  );

  /** one undoable step; `key` merges quick repeats of the same edit (typing a number) into one */
  const record = useCallback(
    (
      label: string,
      next: Partial<Setup> | ((s: Setup) => Setup),
      key?: string,
    ) => {
      setState((s) => {
        const after =
          typeof next === "function" ? next(s.setup) : { ...s.setup, ...next };
        const top = s.past[s.past.length - 1];
        const now = Date.now();
        if (
          key &&
          top?.kind === "setup" &&
          top.key === key &&
          !s.future.length &&
          now - top.at < COALESCE_MS
        ) {
          const merged = { ...top, label, after, at: now };
          return {
            ...s,
            setup: after,
            base: after,
            past: [...s.past.slice(0, -1), merged],
          };
        }
        if (JSON.stringify(after) === JSON.stringify(s.base))
          return { ...s, setup: after };
        const entry: HistoryEntry = {
          kind: "setup",
          label,
          before: s.base,
          after,
          key,
          at: now,
        };
        return {
          ...s,
          setup: after,
          base: after,
          past: [...s.past, entry].slice(-MAX),
          future: [],
        };
      });
      setNote(null);
      setError(null);
    },
    [],
  );

  /** a revision-store write that just succeeded */
  const pushStore = useCallback((entry: StoreEntry) => {
    setState((s) => ({
      ...s,
      past: [...s.past, entry].slice(-MAX),
      future: [],
      calcHead: entry.kind === "calc" ? entry.head : s.calcHead,
    }));
    setNote(null);
    setError(null);
  }, []);

  const step = useCallback(async (dir: Direction) => {
    if (busyRef.current) return;
    const s = ref.current;
    const from = dir === "undo" ? s.past : s.future;
    const entry = from[from.length - 1];
    if (!entry) return;
    setError(null);
    const move = (e: HistoryEntry, patch: Partial<State> = {}) =>
      setState((cur) => {
        const src = dir === "undo" ? cur.past : cur.future;
        if (src[src.length - 1] !== entry) return cur; // changed underneath us
        const rest = src.slice(0, -1);
        return dir === "undo"
          ? { ...cur, ...patch, past: rest, future: [...cur.future, e] }
          : { ...cur, ...patch, future: rest, past: [...cur.past, e] };
      });
    if (entry.kind === "setup") {
      const to = dir === "undo" ? entry.before : entry.after;
      move(entry, { setup: to, base: to });
      setNote(`${dir === "undo" ? "Undid" : "Redid"}: ${entry.label}`);
      return;
    }
    busyRef.current = true;
    setBusy(true);
    try {
      const r = await storeRef.current(entry, dir);
      const e: StoreEntry =
        entry.kind === "model"
          ? { ...entry, head: Number(r.head) }
          : { ...entry, head: String(r.head) };
      move(e, e.kind === "calc" ? { calcHead: e.head } : {});
      setNote(r.note);
    } catch (err) {
      setError(
        `${dir === "undo" ? "Undo" : "Redo"} failed: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  const undo = useCallback(() => void step("undo"), [step]);
  const redo = useCallback(() => void step("redo"), [step]);

  // Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z - not while typing in a text field (the field keeps its own undo)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        !(e.metaKey || e.ctrlKey) ||
        e.altKey ||
        e.key.toLowerCase() !== "z" ||
        isTyping(e.target)
      )
        return;
      e.preventDefault();
      if (e.shiftKey) redo();
      else undo();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo]);

  const nextUndo = state.past[state.past.length - 1];
  const nextRedo = state.future[state.future.length - 1];
  return {
    setup: state.setup,
    calcHead: state.calcHead,
    preview,
    record,
    pushStore,
    undo,
    redo,
    undoLabel: nextUndo?.label ?? null,
    redoLabel: nextRedo?.label ?? null,
    busy,
    note,
    error,
  };
}
