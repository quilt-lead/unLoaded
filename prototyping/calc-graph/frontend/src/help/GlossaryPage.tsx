import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { HELP, type HelpEntry, type HelpId } from "./registry";
import { InfoTip } from "./InfoTip";

const GROUPS: [string, string][] = [
  ["nav.", "App shell"],
  ["page.", "Pages"],
  ["home.", "Home"],
  ["panel.", "Panels"],
  ["stat.", "Stat pills"],
  ["tab.", "Tabs"],
  ["legend.", "Legends"],
  ["graph.", "Graphs"],
  ["pdf.", "PDF pages"],
  ["evidence.", "Evidence"],
  ["viewer3d.", "3D viewer"],
];

/** /help - generated from the help registry; every entry has an anchor (#id) the InfoTips link to. */
export function GlossaryPage() {
  const [q, setQ] = useState("");
  const loc = useLocation();
  const all = Object.entries(HELP) as [HelpId, HelpEntry][];
  const match = (e: HelpEntry) =>
    !q || [e.title, e.short, e.what, e.source, e.read, e.real].some((s) => s?.toLowerCase().includes(q.toLowerCase()));
  const terms = all.filter(([, e]) => e.kind === "term" && match(e)).sort((a, b) => a[1].title.localeCompare(b[1].title));
  const groups = useMemo(() => {
    const ui = all.filter(([, e]) => e.kind !== "term");
    const known = GROUPS.map(([p, label]) => [label, ui.filter(([id]) => id.startsWith(p))] as const);
    const rest = ui.filter(([id]) => !GROUPS.some(([p]) => id.startsWith(p)));
    return rest.length ? [...known, ["Other", rest] as const] : known;
  }, [all]);

  useEffect(() => {
    const id = decodeURIComponent(loc.hash.slice(1));
    if (!id) return;
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ block: "center" });
      el.classList.add("flash");
      const t = window.setTimeout(() => el.classList.remove("flash"), 1600);
      return () => window.clearTimeout(t);
    }
  }, [loc.hash]);

  return (
    <div className="glossary">
      <header className="glossary-head">
        <h1>
          Glossary <InfoTip id="page.glossary" />
        </h1>
        <input
          type="search"
          className="glossary-q"
          placeholder="Search terms and help text"
          aria-label="Search the glossary"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </header>
      <section>
        <h2>Terms</h2>
        <dl>
          {terms.map(([id, e]) => (
            <Entry key={id} id={id} e={e} />
          ))}
        </dl>
      </section>
      {groups.map(([label, items]) => {
        const shown = items.filter(([, e]) => match(e));
        if (!shown.length) return null;
        return (
          <section key={label}>
            <h2>{label}</h2>
            <dl>
              {shown.map(([id, e]) => (
                <Entry key={id} id={id} e={e} />
              ))}
            </dl>
          </section>
        );
      })}
    </div>
  );
}

function Entry({ id, e }: { id: HelpId; e: HelpEntry }) {
  return (
    <div className="glossary-entry" id={id}>
      <dt>
        {e.title} <code className="mono">{id}</code>
      </dt>
      <dd>
        <p>{e.short}</p>
        {e.what && <p><b>What it is.</b> {e.what}</p>}
        {e.source && <p><b>Data source.</b> {e.source}</p>}
        {e.read && <p><b>How to read it.</b> {e.read}</p>}
        {e.real && <p><b>Real or mocked.</b> {e.real}</p>}
        {e.terms && e.terms.length > 0 && (
          <p className="muted">
            See:{" "}
            {e.terms.map((t, i) => (
              <span key={t}>
                {i > 0 && ", "}
                <a href={`#${t}`}>{(HELP as Record<string, HelpEntry>)[t]?.title ?? t}</a>
              </span>
            ))}
          </p>
        )}
      </dd>
    </div>
  );
}
