import { InfoTip } from "../../help/InfoTip";
import type { Band, Health, HealthReason } from "./api";
import { PlatformSourceBadge } from "./PlatformRecord";
import { BAND_COLOR, BAND_LABEL, BANDS } from "./util";

/** construction-status reasons come from the (mock) platforms; everything else is the design screen */
export const isConstructionReason = (r: HealthReason) => r.factor === "construction status";

function Meter({ score, band, label }: { score: number; band: Band; label: string }) {
  return (
    <div className="v2-meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score} aria-label={`${label}: ${BAND_LABEL[band]}, score ${score} of 100`}>
      <div className="v2-meter-track">
        {BANDS.map((b) => (
          <span key={b} style={{ background: BAND_COLOR[b] }} />
        ))}
        <i className="v2-meter-needle" style={{ left: `${Math.max(0, Math.min(100, score))}%` }} />
      </div>
      <div className="v2-meter-row">
        <span className="v2-meter-label">{label}</span>
        <b style={{ color: BAND_COLOR[band] }}>{BAND_LABEL[band]}</b>
        <span className="muted mono">{score}/100</span>
      </div>
    </div>
  );
}

function Reasons({ items, empty }: { items: HealthReason[]; empty: string }) {
  if (!items.length) return <p className="muted v2-small">{empty}</p>;
  return (
    <ul className="v2-reasons">
      {items.map((r, i) => (
        <li key={i}>
          <i className="v2-dot" style={{ background: BAND_COLOR[r.band] }} title={BAND_LABEL[r.band]} />
          <span>
            {r.reason} <span className="muted">({r.factor})</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** "How hard is this to move": the design band, the construction-adjusted band, and the reasons for each. */
export function HealthMeter({ health, title }: { health: Health; title?: string }) {
  const design = health.reasons.filter((r) => !isConstructionReason(r));
  const cons = health.reasons.filter(isConstructionReason);
  return (
    <div className="v2-health">
      {title && <div className="v2-health-title">{title}</div>}
      <div className="v2-meters">
        <div className="v2-meter-box">
          <Meter score={health.score} band={health.band} label="Design" />
          <InfoTip id="stat.move-health-design" />
        </div>
        {health.band_construction && (
          <div className="v2-meter-box">
            <Meter score={health.score_construction ?? health.score} band={health.band_construction} label="With construction status" />
            <InfoTip id="stat.move-health-construction" />
          </div>
        )}
      </div>
      <h3 className="v2-h3">
        Design reasons <InfoTip id="panel.move-reasons-design" />
      </h3>
      <Reasons items={design} empty="No design reasons: the screen found nothing that makes this hard." />
      <h3 className="v2-h3">
        Construction status reasons <InfoTip id="panel.move-reasons-construction" />
        <PlatformSourceBadge />
      </h3>
      <Reasons items={cons} empty="Nothing built or approved yet that this would affect." />
    </div>
  );
}
