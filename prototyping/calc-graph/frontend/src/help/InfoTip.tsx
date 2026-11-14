import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { HELP, type HelpEntry, type HelpId } from "./registry";
import "./help.css";

export interface InfoTipProps {
  /** registry id - the only source of the text */
  id: HelpId;
  className?: string;
}

type Mode = null | "peek" | "pinned";

/**
 * The small "i" mark. Hover or keyboard focus shows the short explanation; click (or tap) pins it,
 * and a pinned tip offers "Learn more" (what it is, where the data comes from, how to read it, what is
 * real vs mocked). Esc closes and returns focus; clicking outside closes a pinned tip.
 */
export function InfoTip({ id, className }: InfoTipProps) {
  const entry: HelpEntry = HELP[id];
  const [mode, setMode] = useState<Mode>(null);
  const [more, setMore] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const leaveTimer = useRef(0);
  const popId = useId();
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  const close = useCallback((refocus: boolean) => {
    setMode(null);
    setMore(false);
    setPos(null);
    if (refocus) btn.current?.focus();
  }, []);

  // place the popover under the mark (or above when there is no room), clamped to the viewport
  useLayoutEffect(() => {
    if (!mode || !btn.current || !pop.current) return;
    const b = btn.current.getBoundingClientRect();
    const p = pop.current.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight, m = 8;
    let left = b.left + b.width / 2 - p.width / 2;
    left = Math.max(m, Math.min(left, vw - p.width - m));
    let top = b.bottom + 6;
    if (top + p.height > vh - m && b.top - 6 - p.height >= m) top = b.top - 6 - p.height;
    setPos({ left, top: Math.max(m, top) });
  }, [mode, more]);

  useEffect(() => {
    if (!mode) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close(true);
      }
    };
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (btn.current?.contains(t) || pop.current?.contains(t)) return;
      close(false);
    };
    const onScroll = () => mode === "peek" && close(false);
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("pointerdown", onDown, true);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("pointerdown", onDown, true);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [mode, close]);

  const peek = () => {
    window.clearTimeout(leaveTimer.current);
    setMode((m) => m ?? "peek");
  };
  const unpeek = () => {
    window.clearTimeout(leaveTimer.current);
    leaveTimer.current = window.setTimeout(() => setMode((m) => (m === "peek" ? null : m)), 140);
  };
  useEffect(() => () => window.clearTimeout(leaveTimer.current), []);

  const sections: [string, string | undefined][] = [
    ["What it is", entry.what],
    ["Where the data comes from", entry.source],
    ["How to read it", entry.read],
    ["Real or mocked", entry.real],
  ];
  const hasMore = sections.some(([, v]) => v) || (entry.terms?.length ?? 0) > 0;

  return (
    <>
      <button
        ref={btn}
        type="button"
        className={`infotip${mode ? " open" : ""}${className ? " " + className : ""}`}
        aria-label={`About: ${entry.title}`}
        aria-expanded={mode === "pinned"}
        aria-controls={mode ? popId : undefined}
        aria-describedby={mode === "peek" ? popId : undefined}
        data-help-id={id}
        onMouseEnter={peek}
        onMouseLeave={unpeek}
        onFocus={peek}
        onBlur={(e) => {
          if (!pop.current?.contains(e.relatedTarget as Node)) unpeek();
        }}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          if (mode === "pinned") close(false);
          else setMode("pinned");
        }}
      >
        i
      </button>
      {mode &&
        createPortal(
          <div
            ref={pop}
            id={popId}
            role={mode === "pinned" ? "dialog" : "tooltip"}
            aria-label={mode === "pinned" ? entry.title : undefined}
            className={`infotip-pop${mode === "pinned" ? " pinned" : ""}`}
            style={pos ? { left: pos.left, top: pos.top } : { left: -9999, top: 0 }}
            onMouseEnter={peek}
            onMouseLeave={unpeek}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="infotip-head">
              <b>{entry.title}</b>
              {mode === "pinned" && (
                <button type="button" className="infotip-x" aria-label="Close" onClick={() => close(true)}>
                  ×
                </button>
              )}
            </div>
            <p className="infotip-short">{entry.short}</p>
            {mode === "peek" && hasMore && <p className="infotip-hint">Click the i for more.</p>}
            {mode === "pinned" && hasMore && (
              <button type="button" className="infotip-more" aria-expanded={more} onClick={() => setMore((v) => !v)}>
                {more ? "Show less" : "Learn more"}
              </button>
            )}
            {mode === "pinned" && more && (
              <div className="infotip-body">
                {sections.map(([h, v]) =>
                  v ? (
                    <div key={h}>
                      <h4>{h}</h4>
                      <p>{v}</p>
                    </div>
                  ) : null,
                )}
                {entry.terms && entry.terms.length > 0 && (
                  <div>
                    <h4>Terms</h4>
                    <p className="infotip-terms">
                      {entry.terms.map((t) => (
                        <Link key={t} to={`/help#${t}`} onClick={() => close(false)}>
                          {(HELP as Record<string, HelpEntry>)[t]?.title ?? t}
                        </Link>
                      ))}
                    </p>
                  </div>
                )}
                <p>
                  <Link to={`/help#${id}`} onClick={() => close(false)}>
                    Open in the glossary
                  </Link>
                </p>
              </div>
            )}
          </div>,
          document.body,
        )}
    </>
  );
}
