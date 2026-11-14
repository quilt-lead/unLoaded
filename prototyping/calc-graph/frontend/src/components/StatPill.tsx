import type { ReactNode } from "react";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";

export type Tone = "neutral" | "good" | "warn" | "bad" | "accent" | "calc";

export interface StatPillProps {
  label: ReactNode;
  value: ReactNode;
  info: HelpId;
  tone?: Tone;
  /** makes the pill a toggle button (e.g. a filter) */
  onClick?: () => void;
  active?: boolean;
  title?: string;
}

export function StatPill({ label, value, info, tone = "neutral", onClick, active, title }: StatPillProps) {
  const cls = `cg-pill tone-${tone}${active ? " on" : ""}${onClick ? " clickable" : ""}`;
  const body = (
    <>
      <span className="cg-pill-label">{label}</span> <b className="cg-pill-value">{value}</b>
    </>
  );
  return (
    <span className={cls} title={title}>
      {onClick ? (
        <button type="button" className="cg-pill-btn" aria-pressed={!!active} onClick={onClick}>
          {body}
        </button>
      ) : (
        body
      )}
      <InfoTip id={info} />
    </span>
  );
}

/** a row of pills that wraps on narrow screens */
export function StatRow({ children }: { children: ReactNode }) {
  return <div className="cg-pills">{children}</div>;
}
