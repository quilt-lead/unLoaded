import { useEffect, useRef, useState } from "react";
import { InfoTip } from "../../help/InfoTip";
import { usePlatformRecords, type PlatformRecord } from "./api";
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

/** Small "Mock Procore" style badge + button that opens the mock record. */
export function MockLink({ url, onOpen, label }: { url?: string; onOpen: (url: string) => void; label?: string }) {
  if (!url) return null;
  const p = parseMockLink(url);
  return (
    <button type="button" className="v2-mocklink" onClick={() => onOpen(url)} title={url}>
      {label ?? `Mock ${PLATFORM_LABEL[p?.platform ?? ""] ?? p?.platform ?? "platform"} record`}
    </button>
  );
}

/** Dialog showing one mock platform record: the normalised fields and the platform-shaped JSON. */
export function PlatformRecordDialog({ url, onClose }: { url: string; onClose: () => void }) {
  const p = parseMockLink(url);
  const list = usePlatformRecords(p?.platform ?? null, p?.type ?? null);
  const raw = usePlatformRecords(p?.platform ?? null, p?.type ?? null, true);
  const [showRaw, setShowRaw] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const rec = (list.data as PlatformRecord[] | undefined)?.find((r) => r.links?.self === url || r.id === p?.id);
  const rawRec = (raw.data as Record<string, unknown>[] | undefined)?.find((r) => String(r.id) === String(rec?.id ?? p?.id));

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", k);
    box.current?.focus();
    return () => document.removeEventListener("keydown", k);
  }, [onClose]);

  const plat = PLATFORM_LABEL[p?.platform ?? ""] ?? p?.platform;
  return (
    <div className="v2-modal-back" onClick={onClose}>
      <div className="v2-modal" role="dialog" aria-modal="true" aria-label={`Mock ${plat} record`} ref={box} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <header className="v2-modal-head">
          <span className="v2-mock big">MOCK</span>
          <b>
            {plat} {p?.type?.replace(/_/g, " ")}
          </b>
          <InfoTip id="panel.platform-record" />
          <span className="spacer" />
          <button type="button" className="btn sm" onClick={onClose}>
            Close
          </button>
        </header>
        <p className="v2-small muted">
          Synthetic record shaped like the {plat} API. No network call was made and no real project exists. <span className="mono">{url}</span>
        </p>
        {list.isLoading && <p className="muted">Loading...</p>}
        {list.error && <p className="v2-error">{String((list.error as Error).message)}</p>}
        {!list.isLoading && !rec && <p className="muted">This record is not in the mock {plat} data.</p>}
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
            {showRaw && <pre className="v2-pre">{rawRec ? JSON.stringify(rawRec, null, 2) : raw.isLoading ? "Loading..." : "Not found in the raw list."}</pre>}
          </>
        )}
      </div>
    </div>
  );
}
