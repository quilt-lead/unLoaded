import { useEffect, useRef, useState } from "react";
import { InfoTip } from "../../help/InfoTip";
import { usePlatformRecordByLink, usePlatforms } from "./api";
import { PLATFORM_LABEL } from "./util";

/** mock://<platform>/projects/<id>/<path...>/<record id> -> adapter name + record type */
export function parseMockLink(url: string): { platform: string; type: string | null; id: string } | null {
  const m = url.match(/^mock:\/\/([^/]+)\/projects\/[^/]+\/(.+)$/);
  if (!m) return null;
  const platform = m[1] === "acc" ? "autodesk_build" : m[1];
  const path = m[2];
  const id = path.split("/").pop() ?? "";
  const rules: [RegExp, string][] = [
    [/^submittals\//, "submittals"],
    [/^rfis\//, "rfis"],
    [/^drawings\//, "sheets"],
    [/^sheets\//, "sheets"],
    [/^budget_line_items\//, "budget_lines"],
    [/^cost\/budgets\//, "budget_lines"],
    [/^schedule\//, "schedule_activities"],
    [/^change_events\//, "change_events"],
    [/^cost\/change-orders\/pco\//, "change_events"],
    [/^change_order_packages\//, "change_orders"],
    [/^cost\/change-orders\/oco\//, "change_orders"],
    [/^cost_codes\//, "cost_codes"],
    [/^cost\/budget-codes\//, "cost_codes"],
    [/^elements\//, "elements"],
    [/^proposals\//, "proposals"],
  ];
  const type = rules.find(([re]) => re.test(path))?.[1] ?? null;
  return { platform, type, id };
}

/** live / mock badge for construction-platform data. `source` when the caller has it (a record, an
 * occurrence); else looked up per platform from GET /platforms; with neither, a summary of all platforms. */
export function PlatformSourceBadge({ source, platform, big }: { source?: string | null; platform?: string | null; big?: boolean }) {
  const ps = usePlatforms();
  const list = ps.data ?? [];
  let src = source ?? (platform ? list.find((p) => p.name === platform)?.source : undefined);
  let title = platform ? list.find((p) => p.name === platform)?.fallback_reason ?? undefined : undefined;
  if (!source && !platform && list.length) {
    const live = list.filter((p) => p.source === "live");
    src = live.length === list.length ? "live" : live.length ? "mixed" : "mock";
    title = list.map((p) => `${PLATFORM_LABEL[p.name] ?? p.label}: ${p.source}${p.fallback_reason ? ` (${p.fallback_reason})` : ""}`).join("; ");
  }
  if (!src) return null;
  const cls = `${src === "live" ? "v2-live" : "v2-mock"}${big ? " big" : ""}`;
  if (src === "mixed") {
    const live = list.filter((p) => p.source === "live").map((p) => PLATFORM_LABEL[p.name] ?? p.label);
    return (
      <span className={cls} title={title}>
        live: {live.join(", ")}; rest mock
      </span>
    );
  }
  return (
    <span className={cls} title={title}>
      {src === "live" ? "live" : "mock"}
    </span>
  );
}

const platformOfLink = (url: string): string | null => {
  const p = parseMockLink(url);
  if (p) return p.platform;
  if (/procore\.com\//.test(url)) return "procore";
  return null;
};

/** Small button that opens a platform record (mock or live) by its link. */
export function MockLink({ url, onOpen, label }: { url?: string | null; onOpen: (url: string) => void; label?: string }) {
  const ps = usePlatforms();
  if (!url) return null;
  const plat = platformOfLink(url);
  const src = plat ? ps.data?.find((p) => p.name === plat)?.source : undefined;
  const name = PLATFORM_LABEL[plat ?? ""] ?? plat ?? "platform";
  return (
    <button type="button" className={src === "live" ? "v2-mocklink v2-livelink" : "v2-mocklink"} onClick={() => onOpen(url)} title={url}>
      {label ?? `${src === "live" ? "Live" : "Mock"} ${name} record`}
    </button>
  );
}

/** Dialog showing one platform record (live or mock): the normalised fields and the platform-shaped JSON. */
export function PlatformRecordDialog({ url, onClose }: { url: string; onClose: () => void }) {
  const q = usePlatformRecordByLink(url);
  const [showRaw, setShowRaw] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const rec = q.data;

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", k);
    box.current?.focus();
    return () => document.removeEventListener("keydown", k);
  }, [onClose]);

  const pname = rec?.platform ?? platformOfLink(url) ?? "";
  const plat = PLATFORM_LABEL[pname] ?? rec?.platform_label ?? pname;
  const live = rec?.source === "live";
  const type = rec?.record_type ?? parseMockLink(url)?.type ?? "record";
  return (
    <div className="v2-modal-back" onClick={onClose}>
      <div className="v2-modal" role="dialog" aria-modal="true" aria-label={`${live ? "Live" : "Mock"} ${plat} record`} ref={box} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <header className="v2-modal-head">
          <span className={live ? "v2-live big" : "v2-mock big"}>{live ? "LIVE" : "MOCK"}</span>
          <b>
            {plat} {type.replace(/_/g, " ")}
          </b>
          <InfoTip id="panel.platform-record" />
          <span className="spacer" />
          <button type="button" className="btn sm" onClick={onClose}>
            Close
          </button>
        </header>
        <p className="v2-small muted">
          {live
            ? `Read from the ${plat} API (${rec?.source_label ?? "live"}).`
            : `Synthetic record shaped like the ${plat} API. No network call was made and no real project exists${rec?.source_label ? ` - ${rec.source_label}` : ""}.`}{" "}
          <span className="mono">{url}</span>
        </p>
        {q.isLoading && <p className="muted">Loading...</p>}
        {q.error && <p className="v2-error">{String((q.error as Error).message)}</p>}
        {rec && (
          <>
            <h3 className="v2-modal-title">
              {rec.number && <span className="mono">{rec.number}</span>} {rec.title}
            </h3>
            <dl className="v2-dl">
              <dt>Status</dt>
              <dd>{rec.status}</dd>
              {Object.entries(rec.dates ?? {}).map(([k, v]) => (
                <div key={k} className="v2-dl-pair">
                  <dt>{k.replace(/_/g, " ")}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
              {Object.entries(rec.fields ?? {})
                .filter(([, v]) => v != null && typeof v !== "object")
                .map(([k, v]) => (
                  <div key={k} className="v2-dl-pair">
                    <dt>{k.replace(/_/g, " ")}</dt>
                    <dd>{String(v)}</dd>
                  </div>
                ))}
              {!!rec.element_ids?.length && (
                <>
                  <dt>Elements</dt>
                  <dd className="mono v2-small">{rec.element_ids.join(", ")}</dd>
                </>
              )}
            </dl>
            <button type="button" className="btn sm" onClick={() => setShowRaw((v) => !v)} aria-expanded={showRaw}>
              {showRaw ? "Hide" : "Show"} the {plat}-shaped JSON
            </button>
            {showRaw && <pre className="v2-pre">{rec.raw ? JSON.stringify(rec.raw, null, 2) : "No raw object."}</pre>}
          </>
        )}
      </div>
    </div>
  );
}
