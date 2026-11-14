import type { ReactNode } from "react";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";

export interface PanelProps {
  title: ReactNode;
  /** help id for the title's "i" mark (required: every panel explains itself) */
  info: HelpId;
  /** right side of the header: counts, buttons */
  actions?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
  /** let the body scroll inside a fixed-height panel (default true) */
  scroll?: boolean;
}

export function Panel({ title, info, actions, footer, children, className, scroll = true }: PanelProps) {
  return (
    <section className={`cg-panel${className ? " " + className : ""}`}>
      <header className="cg-panel-head">
        <h2>
          {title}
          <InfoTip id={info} />
        </h2>
        {actions && <div className="cg-panel-actions">{actions}</div>}
      </header>
      <div className={`cg-panel-body${scroll ? " scroll" : ""}`}>{children}</div>
      {footer && <footer className="cg-panel-foot">{footer}</footer>}
    </section>
  );
}
