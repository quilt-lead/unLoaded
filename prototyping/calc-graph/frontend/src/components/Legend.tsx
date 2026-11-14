import type { ReactNode } from "react";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";

export type SwatchShape = "line" | "dashed" | "dotted" | "box" | "dot";

export interface LegendItem {
  label: ReactNode;
  /** any CSS colour or var(--token) */
  color: string;
  shape?: SwatchShape;
  /** help id for this entry (required) */
  info: HelpId;
}

export interface LegendProps {
  items: readonly LegendItem[];
  /** help id for the legend as a whole */
  info: HelpId;
  title?: ReactNode;
  /** overlay style (floating card over a viewer) vs inline row */
  variant?: "inline" | "overlay";
}

export function Legend({ items, info, title, variant = "inline" }: LegendProps) {
  return (
    <div className={`cg-legend ${variant}`} role="group" aria-label={typeof title === "string" ? title : "Legend"}>
      {title && (
        <span className="cg-legend-title">
          {title}
          <InfoTip id={info} />
        </span>
      )}
      {!title && <InfoTip id={info} />}
      {items.map((it, i) => (
        <span key={i} className="cg-legend-item">
          <Swatch color={it.color} shape={it.shape ?? "box"} />
          {it.label}
          <InfoTip id={it.info} />
        </span>
      ))}
    </div>
  );
}

export function Swatch({ color, shape }: { color: string; shape: SwatchShape }) {
  if (shape === "box" || shape === "dot")
    return <i className={`cg-swatch ${shape}`} style={{ background: color }} aria-hidden="true" />;
  const dash = shape === "dashed" ? "5 3" : shape === "dotted" ? "1.5 3" : undefined;
  return (
    <svg className="cg-swatch line" width="22" height="10" aria-hidden="true">
      <line x1="1" y1="5" x2="21" y2="5" stroke={color} strokeWidth={2.2} strokeDasharray={dash} strokeLinecap="round" />
    </svg>
  );
}
