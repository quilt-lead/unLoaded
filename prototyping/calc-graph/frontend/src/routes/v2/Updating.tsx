import type { ReactNode } from "react";

/** Keep the previous answer on screen, dimmed with a spinner, while the new one is computed (the 3D view's
 * "updating" pattern, for panels): pair it with a query whose placeholder is the previous answer
 * (api.moveAtDate), so the panel never blanks between approval dates. */
export function Updating({ busy, label, children }: { busy: boolean; label: string; children: ReactNode }) {
  return (
    <div className={`v2-updating${busy ? " busy" : ""}`} aria-busy={busy}>
      {busy && (
        <div className="v2-updating-note" role="status" data-testid="panel-updating">
          <span className="v2-spin" aria-hidden="true" /> {label}
        </div>
      )}
      <div className="v2-updating-body">{children}</div>
    </div>
  );
}
