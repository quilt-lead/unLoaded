// Left column of the drawing-set view: five tabs (elements, calc records, calc pages, connections,
// findings) of collapsible groups, filtered by the search box.
import type { ReactNode } from "react";
import type { CInst, CType, El, Rec, SetCalc, SetFinding } from "../../api/types";
import { CAT_COL, CONN_COL, SEC_COL, SEC_ORDER, calcSec, nat, recColor, recEdgesOut, secName, type ListTab, type Sel, type SetIndex } from "./model";

export interface SetListProps {
  x: SetIndex;
  tab: ListTab;
  q: string;
  open: Set<string>;
  sel: Sel;
  onToggle: (key: string) => void;
  onSelect: (s: Sel) => void;
  onFinding: (i: number) => void;
}

const push = <K, V>(m: Map<K, V[]>, k: K, v: V) => (m.get(k) ?? m.set(k, []).get(k)!).push(v);

function Grp({ k, open, onToggle, children, count }: { k: string; open: boolean; onToggle: (k: string) => void; children: ReactNode; count: ReactNode }) {
  return (
    <button type="button" className={`set-grp${open ? " open" : ""}`} aria-expanded={open} onClick={() => onToggle(k)}>
      <span className="tw">{open ? "▾" : "▸"}</span>
      <span className="set-grp-l">{children}</span>
      <span className="cnt">{count}</span>
    </button>
  );
}
function Row({ on, color, onClick, children, find }: { on: boolean; color: string; onClick: () => void; children: ReactNode; find?: boolean }) {
  return (
    <button type="button" className={`set-row${on ? " sel" : ""}${find ? " find" : ""}`} aria-pressed={on} onClick={onClick}>
      <i style={{ background: color }} />
      {children}
    </button>
  );
}

export function SetList({ x, tab, q, open, sel, onToggle, onSelect, onFinding }: SetListProps) {
  const matches = (s: string) => !q || s.toLowerCase().includes(q);
  const isOpen = (k: string, selHere: boolean) => open.has(k) || !!q || selHere;
  const out: ReactNode[] = [];

  if (tab === "el") {
    const groups = new Map<string, El[]>();
    for (const e of x.g.elements) if (matches(`${e.id} ${e.text} ${e.type} ${e.sheet} ${e.grid} ${e.level} ${e.size_norm}`)) push(groups, `${e.sheet}|${e.type}`, e);
    for (const [k, es] of [...groups.entries()].sort((a, b) => nat(a[0], b[0]))) {
      const [sh, ty] = k.split("|");
      const nl = es.filter((e) => x.linksByEl.has(e.id)).length;
      const o = isOpen(k, sel?.kind === "el" && es.some((e) => e.id === sel.id));
      out.push(
        <Grp key={k} k={k} open={o} onToggle={onToggle} count={`${nl}/${es.length} linked`}>
          <b>{sh}</b> {ty}
        </Grp>,
      );
      if (o)
        for (const e of es.slice().sort((a, b) => nat(a.text, b.text) || nat(a.grid, b.grid))) {
          const n = x.linksByEl.get(e.id)?.length ?? 0;
          out.push(
            <Row key={e.id} on={sel?.id === e.id} color={CAT_COL[e.cat] ?? CAT_COL.Other} onClick={() => onSelect({ kind: "el", id: e.id })}>
              <span className="mono">{e.text}</span>
              <span className="m">{e.grid || ""}</span>
              {n ? <span className="chip good">{n}</span> : <span className="chip bad">no calc</span>}
            </Row>,
          );
        }
    }
  } else if (tab === "calc") {
    const groups = new Map<string, SetCalc[]>();
    for (const c of x.g.calcs) if (matches(`${c.sheet_id} ${c.title} ${c.software} ${c.sizes.join(" ")}`)) push(groups, c.group, c);
    let lastSec = "";
    for (const [k, cs] of groups) {
      const sec = calcSec(cs[0]);
      if (sec !== lastSec) {
        out.push(
          <div key={`sec:${k}`} className="set-sec" style={{ borderLeftColor: SEC_COL[sec] ?? "#888" }}>
            {secName(sec)}
          </div>,
        );
        lastSec = sec;
      }
      const nl = cs.filter((c) => x.linksByCalc.has(c.id)).length;
      const o = isOpen(k, sel?.kind === "calc" && cs.some((c) => c.id === sel.id));
      const range = cs.length > 1 ? `${cs[0].sheet_id}-${cs[cs.length - 1].sheet_id}` : cs[0].sheet_id;
      out.push(
        <Grp key={k} k={k} open={o} onToggle={onToggle} count={`${cs.length} pp${nl ? ` · ${nl} linked` : ""}`}>
          <b>{range}</b> {cs[0].title}
        </Grp>,
      );
      if (o)
        for (const c of cs) {
          const n = new Set((x.linksByCalc.get(c.id) ?? []).map((l) => l.el)).size;
          out.push(
            <Row key={c.id} on={sel?.id === c.id} color={SEC_COL[sec] ?? "#888"} onClick={() => onSelect({ kind: "calc", id: c.id })}>
              <span className="mono">{c.sheet_id}</span>
              <span className="m">{c.title}</span>
              {n > 0 && <span className="chip good">{n} el</span>}
            </Row>,
          );
        }
    }
  } else if (tab === "rec") {
    if (!x.ig)
      out.push(
        <div key="e" className="set-empty">
          No calc records yet - run <span className="mono">uv run python scripts/build_calc_records.py</span>
        </div>,
      );
    else {
      const tree = new Map<string, Map<string, Map<string, Rec[]>>>();
      for (const r of x.ig.records)
        if (matches(`${r.id} ${r.title} ${r.table} ${r.level} ${r.size} ${r.run_title}`)) {
          const runs = tree.get(r.section) ?? tree.set(r.section, new Map()).get(r.section)!;
          const tabs = runs.get(r.run) ?? runs.set(r.run, new Map()).get(r.run)!;
          push(tabs, r.table, r);
        }
      const firstPage = (rs: Rec[]) => Math.min(...rs.map((r) => r.ev[0]?.page ?? 9999));
      for (const sec of [...tree.keys()].sort((a, b) => SEC_ORDER.indexOf(a) - SEC_ORDER.indexOf(b))) {
        out.push(
          <div key={`sec:${sec}`} className="set-sec" style={{ borderLeftColor: SEC_COL[sec] ?? "#888" }}>
            {secName(sec)}
          </div>,
        );
        for (const [run, tabs] of tree.get(sec)!) {
          const n = [...tabs.values()].reduce((a, b) => a + b.length, 0);
          out.push(
            <div key={`run:${sec}|${run}`} className="set-runh">
              {x.ig.runs[run] ?? run} <span className="cnt">{n}</span>
            </div>,
          );
          for (const [tb, rs] of [...tabs.entries()].sort((a, b) => firstPage(a[1]) - firstPage(b[1]))) {
            const k = `t:${sec}|${run}|${tb}`;
            const o = isOpen(k, sel?.kind === "rec" && rs.some((r) => r.id === sel.id));
            const nl = rs.filter((r) => x.rlByRec.has(r.id)).length;
            const gaps = rs.filter((r) => recEdgesOut(x, r.id).some((e) => e.join === "absent")).length;
            out.push(
              <Grp
                key={k}
                k={k}
                open={o}
                onToggle={onToggle}
                count={
                  <>
                    {rs.length}
                    {nl ? ` · ${nl} linked` : ""}
                    {gaps ? <span className="bad"> · {gaps} gap</span> : null}
                  </>
                }
              >
                {tb}
              </Grp>,
            );
            if (o)
              for (const r of rs.slice().sort((a, b) => nat(a.label, b.label))) {
                const ne = new Set((x.rlByRec.get(r.id) ?? []).map((l) => l.el)).size;
                const gap = recEdgesOut(x, r.id).some((e) => e.join === "absent");
                out.push(
                  <Row key={r.id} on={sel?.id === r.id} color={recColor(r)} onClick={() => onSelect({ kind: "rec", id: r.id })}>
                    <span className="mono">{r.title}</span>
                    <span className="m">{r.level}</span>
                    {x.notesByRec.has(r.id) && <span className="chip">note</span>}
                    {gap && <span className="chip bad">gap</span>}
                    {ne > 0 && <span className="chip good">{ne} el</span>}
                  </Row>,
                );
              }
          }
        }
      }
    }
  } else if (tab === "conn") {
    if (!x.ig)
      out.push(
        <div key="e" className="set-empty">
          No connections yet - run <span className="mono">uv run python scripts/build_connections.py</span>
        </div>,
      );
    else {
      const bySheet = new Map<string, CType[]>();
      for (const t of x.ig.conn_types) if (matches(`${t.id} ${t.title} ${t.sheet} ${t.sheet_title} ${t.category}`)) push(bySheet, t.sheet, t);
      out.push(
        <div key="sec:types" className="set-sec" style={{ borderLeftColor: CONN_COL }}>
          Connection details (types)
        </div>,
      );
      for (const [sh, ts] of [...bySheet.entries()].sort((a, b) => nat(a[0], b[0]))) {
        const k = `c:${sh}`;
        const o = isOpen(k, sel?.kind === "ctype" && ts.some((t) => t.id === sel.id));
        const ni = ts.reduce((a, t) => a + (t.instances?.length ?? 0), 0);
        out.push(
          <Grp key={k} k={k} open={o} onToggle={onToggle} count={`${ts.length} details · ${ni} placed`}>
            <b>{sh}</b> {ts[0].sheet_title}
          </Grp>,
        );
        if (o)
          for (const t of ts.slice().sort((a, b) => nat(a.detail, b.detail)))
            out.push(
              <Row key={t.id} on={sel?.id === t.id} color={t.is_connection ? CONN_COL : "var(--muted)"} onClick={() => onSelect({ kind: "ctype", id: t.id })}>
                <span className="mono">{t.detail}</span>
                <span className="m">{t.title}</span>
                {t.instances?.length > 0 && <span className="chip">{t.instances.length}</span>}
              </Row>,
            );
      }
      const loose = new Map<string, CInst[]>();
      for (const i of x.ig.conn_instances) if (!i.type_id && matches(`${i.id} ${i.symbol_name ?? ""} ${i.ref} ${i.sheet} ${i.grid}`)) push(loose, i.symbol_name ?? i.ref, i);
      if (loose.size)
        out.push(
          <div key="sec:loose" className="set-sec" style={{ borderLeftColor: CONN_COL }}>
            Plan symbols with no detail number
          </div>,
        );
      for (const [nm, is] of loose) {
        const k = `cs:${nm}`;
        const o = isOpen(k, sel?.kind === "cinst" && is.some((i) => i.id === sel.id));
        out.push(
          <Grp key={k} k={k} open={o} onToggle={onToggle} count={is.length}>
            {nm}
          </Grp>,
        );
        if (o)
          for (const i of is)
            out.push(
              <Row key={i.id} on={sel?.id === i.id} color={CONN_COL} onClick={() => onSelect({ kind: "cinst", id: i.id })}>
                <span className="mono">{i.sheet}</span>
                <span className="m">{i.grid || ""}</span>
                {i.attached.length ? <span className="chip good">{i.attached.length} el</span> : <span className="chip">unattached</span>}
              </Row>,
            );
      }
    }
  } else {
    const groups = new Map<string, [SetFinding, number][]>();
    x.findings.forEach((f, i) => matches(`${f.kind} ${f.text}`) && push(groups, f.kind, [f, i]));
    for (const [k, fs] of groups) {
      const o = open.has(k) || !!q || fs.length <= 3;
      out.push(
        <Grp key={k} k={k} open={o} onToggle={onToggle} count={fs.length}>
          <b>{k}</b>
        </Grp>,
      );
      if (o)
        for (const [f, i] of fs.slice(0, 400))
          out.push(
            <Row key={`f${i}`} on={false} find color={f.severity === "high" ? "var(--bad)" : "var(--muted)"} onClick={() => onFinding(i)}>
              <span className="m">{f.text}</span>
            </Row>,
          );
    }
  }
  return <div className="set-list">{out.length ? out : <div className="set-empty">Nothing matches.</div>}</div>;
}
