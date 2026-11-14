// Inbox events for one element (item read, reading confirmed, impact run, reply drafted / posted), shown on
// the element page's Platforms tab. Source: GET /api/v2/inbox/history/{eid} (backend/calcgraph/inbox.py).
import { Link } from "react-router-dom";
import { InfoTip } from "../../help/InfoTip";
import { useInboxHistory } from "./inboxApi";
import "./asof-inbox.css";

const EVENT_LABEL: Record<string, string> = {
  read: "AI read",
  confirmed: "Reading confirmed",
  impact: "Impact run",
  "reply-drafted": "Reply drafted",
  posted: "Reply posted",
};

export function InboxHistory({ eid }: { eid: string }) {
  const h = useInboxHistory(eid);
  return (
    <div className="ai-hist-wrap" data-testid="inbox-history">
      <h3 className="v2-h3">
        Inbox history <InfoTip id="panel.inbox-history" />
      </h3>
      {h.isLoading && <p className="muted v2-small">Loading...</p>}
      {h.data && !h.data.length && <p className="muted v2-small">No inbox item has been read or confirmed against {eid}.</p>}
      <ul className="ai-hist">
        {(h.data ?? []).map((e, i) => (
          <li key={i} className="v2-small">
            <span className="muted">{e.at}</span> <span className="mono">{e.number}</span> <span className="v2-chip">{EVENT_LABEL[e.event] ?? e.event}</span> {e.text}{" "}
            <Link to="/v2/inbox">open inbox</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
