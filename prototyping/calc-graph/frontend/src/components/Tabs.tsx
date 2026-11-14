import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";

export interface TabItem<K extends string = string> {
  id: K;
  label: ReactNode;
  /** help id for this tab's "i" mark (required) */
  info: HelpId;
  badge?: ReactNode;
  disabled?: boolean;
}

export interface TabsProps<K extends string = string> {
  items: readonly TabItem<K>[];
  value: K;
  onChange: (id: K) => void;
  /** help id for the tab group as a whole */
  info: HelpId;
  /** accessible name of the tab list */
  label: string;
  size?: "md" | "sm";
}

/** WAI-ARIA tabs: arrow keys move between tabs, Home/End jump. Panels are rendered by the caller. */
export function Tabs<K extends string>({ items, value, onChange, info, label, size = "md" }: TabsProps<K>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    const n = items.length;
    let j = -1;
    if (e.key === "ArrowRight") j = (i + 1) % n;
    else if (e.key === "ArrowLeft") j = (i - 1 + n) % n;
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = n - 1;
    if (j < 0) return;
    e.preventDefault();
    for (let k = 0; k < n && items[j].disabled; k++) j = (j + (e.key === "ArrowLeft" ? n - 1 : 1)) % n;
    refs.current[j]?.focus();
    onChange(items[j].id);
  };
  return (
    <div className={`cg-tabs size-${size}`}>
      <div role="tablist" aria-label={label} className="cg-tablist">
        {items.map((t, i) => (
          <span key={t.id} className={`cg-tab${t.id === value ? " on" : ""}`}>
            <button
              ref={(el) => {
                refs.current[i] = el;
              }}
              role="tab"
              type="button"
              id={`tab-${t.id}`}
              aria-selected={t.id === value}
              tabIndex={t.id === value ? 0 : -1}
              disabled={t.disabled}
              onClick={() => onChange(t.id)}
              onKeyDown={(e) => onKey(e, i)}
            >
              {t.label}
              {t.badge != null && <span className="cg-tab-badge">{t.badge}</span>}
            </button>
            <InfoTip id={t.info} />
          </span>
        ))}
      </div>
      <InfoTip id={info} className="cg-tabs-info" />
    </div>
  );
}
