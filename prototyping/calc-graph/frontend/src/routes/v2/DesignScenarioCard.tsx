import { InfoTip } from "../../help/InfoTip";
import type { Scenario } from "./api";
import { fmtUc, ucTone } from "./util";

/** A design scenario from the answer key (another lateral layout, not a move): its frames, the design's own
 * drift ratios, and what each saved real ETABS run of it found (worded by the server from the run's numbers). */
export function DesignScenarioCard({ scenario, id, onClose, onEtabs }: { scenario: Scenario | undefined; id: string; onClose: () => void; onEtabs: () => void }) {
  return (
    <section className="v2-job v2-design-scenario" data-testid="design-scenario" aria-label={`Design scenario ${id}`}>
      <div className="v2-toolbar">
        <b>
          Design scenario {id}
          {scenario ? `: ${scenario.label}` : " (not in the answer key any more)"}
        </b>
        <InfoTip id="panel.design-scenario" />
        <span className="spacer" />
        <button type="button" className="btn sm" onClick={onEtabs}>
          ETABS results
        </button>
        <button type="button" className="btn sm" onClick={onClose} data-testid="design-scenario-close">
          Back to the current design
        </button>
      </div>
      {scenario && (
        <>
          {scenario.real_etabs?.map((r) => (
            <p key={r.run_id} className={r.finding.drift_ng.length || r.finding.mode1.shape === "torsional" ? "v2-error" : "v2-ok"} data-testid="design-scenario-finding">
              <b>{r.label}:</b> {r.finding.headline}
            </p>
          ))}
          {!scenario.real_etabs?.length && <p className="v2-small muted">No real ETABS run of this scenario is saved.</p>}
          {scenario.stale_etabs?.map((r) => (
            <p key={r.run_id} className="v2-small v2-warnline">
              {r.label} not shown: {r.stale_reason}.
            </p>
          ))}
          <p className="v2-small">
            Frames:{" "}
            {Object.entries(scenario.frames ?? {})
              .map(([k, v]) => `${k} ${Object.entries(v).map(([m, sz]) => `${m} ${sz}`).join(", ")}`)
              .join("; ")}
            . Design drift / limit:{" "}
            {Object.entries(scenario.design_drift ?? {}).map(([k, v], i) => (
              <span key={k}>
                {i ? ", " : ""}
                {k} <span className={`mono tone-${ucTone(v)}`}>{fmtUc(v)}</span>
              </span>
            ))}
            .
          </p>
          <p className="v2-small muted">The 3D, plan and move tools stay on the current design; this layout exists as ETABS data only.</p>
        </>
      )}
    </section>
  );
}
