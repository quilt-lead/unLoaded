// Inspector of the drawing-set view: element, calc page, calc record, connection detail or instance.
// Every row opens its evidence on the original pages.
import type { ReactNode } from "react";
import type { CEdge, CInst, CType, EEdge, El, Ev, Lnk, Note, REdge, Rec, RLink, SetCalc } from "../../api/types";
import { InfoTip } from "../../help/InfoTip";
import type { HelpId } from "../../help/registry";
import { PARAPET_DETAIL, PARAPET_REC, calcEv, calcSec, cinstEv, ctypeEv, elEv, fmtVal, recEv, secName, tierCls, type Sel, type SetIndex } from "./model";

export interface InspActions {
  select: (s: Sel) => void;
  show: (ev: Ev, focus?: readonly number[] | null) => void;
  openLink: (l: Lnk) => void;
  openEEdge: (e: EEdge) => void;
  openCEdge: (e: CEdge) => void;
  openREdge: (e: REdge) => void;
  openRLink: (l: RLink, rid: string) => void;
  openInstEl: (i: CInst, elId: string) => void;
  openNote: (n: Note) => void;
}

const H3 = ({ children, info }: { children: ReactNode; info: HelpId }) => (
  <h3 className="set-h3">
    {children}
    <InfoTip id={info} />
  </h3>
);
function Li({ onClick, children, cls = "" }: { onClick?: () => void; children: ReactNode; cls?: string }) {
  if (!onClick) return <div className={`set-li none ${cls}`}>{children}</div>;
  return (
    <div
      className={`set-li ${cls}`}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {children}
    </div>
  );
}
const joinChip = (j: string) => <span className={`chip ${j === "exact" ? "good" : j === "inferred" ? "warn" : "bad"}`}>{j}</span>;
const pct = (s: number) => <span className={`chip ${tierCls(s)}`}>{Math.round(s * 100)}%</span>;
function Head({ title, kind, button, onButton, mono }: { title: ReactNode; kind: ReactNode; button: string; onButton: () => void; mono?: boolean }) {
  return (
    <div className="set-ih">
      <h2 className={mono ? "mono" : undefined}>
        {title}
        <InfoTip id="panel.set-inspector" />
      </h2>
      <button type="button" className="btn sm" onClick={onButton}>
        {button}
      </button>
      <span className="kind">{kind}</span>
    </div>
  );
}
const stop = (f: () => void) => (e: React.MouseEvent) => {
  e.stopPropagation();
  f();
};

function InspEl({ x, e, a }: { x: SetIndex; e: El; a: InspActions }) {
  const ls = x.linksByEl.get(e.id) ?? [];
  const m = e.model;
  const lp = [...(x.down.get(e.id) ?? []).map((y) => ["bears on", y] as const), ...(x.up.get(e.id) ?? []).map((y) => ["carries", y] as const)];
  const insts = x.instByEl.get(e.id) ?? [];
  const rls = x.rlByEl.get(e.id) ?? [];
  return (
    <>
      <Head
        mono
        title={e.text}
        kind={`${e.type} · ${e.sheet} ${e.sheet_title} · ${e.level || "no level"} · grid ${e.grid || "-"}${e.grid_node ? ` (on ${e.grid_node})` : ""}`}
        button="Show on sheet"
        onButton={() => a.show(elEv(e))}
      />
      {e.params.schedule && (
        <div className="set-kv">
          Schedule: <span className="mono">{e.params.schedule}</span>
        </div>
      )}
      {m && (
        <div className="set-m3d">
          {m.in3d ? (
            <>
              <b>In 3D</b> ({m.rule}) - {m.position}
              <br />
              Elevation: {m.elevation}
              <br />
              Profile: {m.profile}
              {(m.assumed ?? []).map((s) => (
                <span key={s} className="chip assumed">
                  assumed: {s}
                </span>
              ))}
            </>
          ) : (
            <>
              <b>Not in 3D</b> - {m.reason}
            </>
          )}
          <InfoTip id="insp.set-in-3d" />
        </div>
      )}
      {lp.length > 0 && (
        <>
          <H3 info="insp.set-load-path">Load path ({lp.length})</H3>
          {lp.map(([v, y], i) => {
            const o = x.els.get(v === "bears on" ? y.dst : y.src);
            return (
              <Li key={i} onClick={() => a.openEEdge(y)}>
                <span className="m">{v}</span> <span className="mono">{o?.text}</span>{" "}
                <span className="m">
                  {o?.sheet} {o?.grid}
                </span>
                <span className="chip">{y.rule}</span>
              </Li>
            );
          })}
        </>
      )}
      {insts.length > 0 && (
        <>
          <H3 info="insp.set-connections">Connections ({insts.length})</H3>
          {insts.map((i) => (
            <Li key={i.id} onClick={() => a.openInstEl(i, e.id)}>
              <span className="mono">
                <b>{i.type_id ?? i.symbol_name ?? i.ref}</b>
              </span>{" "}
              <span className="m">
                {i.via}
                {i.type_id ? ` · ${x.ctypes.get(i.type_id)?.title ?? ""}` : ""}
              </span>
              <button type="button" className="btn sm" onClick={stop(() => a.select({ kind: "cinst", id: i.id }))}>
                Select
              </button>
            </Li>
          ))}
        </>
      )}
      {x.ig && (
        <>
          <H3 info="insp.set-el-records">Calc records ({new Set(rls.flatMap((l) => l.records)).size})</H3>
          {rls.map((l) => {
            const c = x.calcs.get(l.calc);
            return (
              <Li key={l.calc}>
                <span className="mono">
                  <b>{c?.sheet_id}</b>
                </span>{" "}
                <span className="m">{c?.title}</span>
                {pct(l.score)}
                <div className="why">{l.rule}</div>
                <div className="recs">
                  {l.records.slice(0, 40).map((rid) => (
                    <button type="button" key={rid} className="btn sm" title="compare evidence" onClick={() => a.openRLink(l, rid)}>
                      {x.recs.get(rid)?.title ?? rid}
                    </button>
                  ))}
                  {l.records.length > 40 && ` +${l.records.length - 40}`}
                </div>
              </Li>
            );
          })}
          {!rls.length && <Li>No calc record matched (see the page links below).</Li>}
        </>
      )}
      <H3 info="insp.set-el-pages">Calc pages ({ls.length})</H3>
      {ls.map((l) => {
        const c = x.calcs.get(l.calc);
        return (
          <Li key={l.calc} onClick={() => a.openLink(l)}>
            <span className="mono">
              <b>{c?.sheet_id}</b>
            </span>{" "}
            <span className="m">{c?.title}</span>
            {pct(l.score)}
            <div className="why">
              {l.tier} - {l.rule}
            </div>
          </Li>
        );
      })}
      {!ls.length && <Li>{x.findings.find((f) => f.el === e.id)?.text ?? "No calc found"}</Li>}
    </>
  );
}

function InspCalc({ x, c, a }: { x: SetIndex; c: SetCalc; a: InspActions }) {
  const ls = x.linksByCalc.get(c.id) ?? [];
  const ins = x.cin.get(c.id) ?? [], outs = x.cout.get(c.id) ?? [];
  const ce = (y: CEdge, other: string, dir: string, i: number) => {
    const o = x.calcs.get(other);
    return (
      <Li key={`${dir}${i}`} onClick={() => a.openCEdge(y)}>
        <span className="m">{dir}</span>{" "}
        <span className="mono">
          <b>{o?.sheet_id}</b>
        </span>{" "}
        <span className="m">{o?.title}</span>
        <span className="chip">{y.rule}</span>
        <div className="why">
          {y.labels.slice(0, 8).join(", ")}
          {y.labels.length > 8 ? "…" : ""}
        </div>
      </Li>
    );
  };
  const rs = x.recsByPage.get(`${c.doc}|${c.page}`) ?? [];
  return (
    <>
      <Head
        title={
          <>
            <span className="mono">{c.sheet_id}</span> {c.title}
          </>
        }
        kind={`${secName(calcSec(c))} · ${c.software} · PDF p${c.page}${c.level ? " · " + c.level : ""}${c.kind ? " · " + c.kind + " page" : ""}`}
        button="Show page"
        onButton={() => a.show(calcEv(c))}
      />
      {c.sizes.length > 0 && (
        <div className="set-kv">
          Sizes printed: <span className="mono">{c.sizes.join(", ")}</span>
        </div>
      )}
      <H3 info="insp.set-calc-fed-by">Fed by ({ins.length})</H3>
      {ins.map((y, i) => ce(y, y.src, "from", i))}
      {!ins.length && <Li>nothing found</Li>}
      <H3 info="insp.set-calc-feeds">Feeds ({outs.length})</H3>
      {outs.slice(0, 60).map((y, i) => ce(y, y.dst, "to", i))}
      {!outs.length && <Li>nothing found</Li>}
      {x.ig && (
        <>
          <H3 info="insp.set-calc-records">Records on this page ({rs.length})</H3>
          {rs.slice(0, 120).map((r) => (
            <Li key={r.id} onClick={() => a.select({ kind: "rec", id: r.id })}>
              <span className="mono">
                <b>{r.title}</b>
              </span>{" "}
              <span className="m">{r.table}</span>
            </Li>
          ))}
          {!rs.length && <Li>No record has a row on this page.</Li>}
          {rs.length > 120 && <div className="why">+{rs.length - 120} more</div>}
        </>
      )}
      <H3 info="insp.set-calc-elements">Elements linked to this page ({new Set(ls.map((l) => l.el)).size})</H3>
      {ls.slice(0, 200).map((l) => {
        const e = x.els.get(l.el);
        return (
          <Li key={l.el} onClick={() => a.openLink(l)}>
            <span className="mono">
              <b>{e?.text}</b>
            </span>{" "}
            <span className="m">
              {e?.sheet} {e?.grid}
            </span>
            {pct(l.score)}
            <div className="why">
              {l.tier} - {l.rule}
            </div>
          </Li>
        );
      })}
      {!ls.length && <Li>No drawn element is linked to this page.</Li>}
    </>
  );
}

const SKIP = new Set(["geom", "end_reactions", "points", "axial", "vertical_loads_k", "col0", "Label"]);
function InspRec({ x, r, a }: { x: SetIndex; r: Rec; a: InspActions }) {
  const kv = Object.entries(r.values).filter(([k, v]) => !SKIP.has(k) && fmtVal(v) !== "");
  const v = r.values as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const notes = x.notesByRec.get(r.id) ?? [];
  const ins = x.rin.get(r.id) ?? [], outs = x.rout.get(r.id) ?? [];
  const reLi = (e: REdge, other: string | null, dir: string, i: number) => {
    const o = other ? x.recs.get(other) : null;
    return (
      <Li key={`${dir}${i}`} onClick={() => a.openREdge(e)}>
        <span className="m">{dir}</span>{" "}
        <span className="mono">
          <b>{o?.title ?? "no support found"}</b>
        </span>{" "}
        <span className="m">{o?.table ?? ""}</span>
        {joinChip(e.join)}
        <div className="why">
          {e.kind}: {e.rule}
        </div>
      </Li>
    );
  };
  const rls = x.rlByRec.get(r.id) ?? [];
  const byTable = new Map<string, number[]>();
  r.ev.forEach((e, i) => {
    const t = e.table || r.table;
    (byTable.get(t) ?? byTable.set(t, []).get(t)!).push(i);
  });
  const t = r.type === "connection_design" ? x.ctypes.get(PARAPET_DETAIL) : undefined;
  return (
    <>
      <Head
        mono
        title={r.title}
        kind={`${r.type.replace(/_/g, " ")} record · ${r.run_title} · ${secName(r.section)}${r.level ? " · " + r.level : ""} · PDF p${r.pages.slice(0, 8).join(", ")}${r.pages.length > 8 ? "…" : ""}`}
        button="Show row"
        onButton={() => a.show(recEv(r))}
      />
      {kv.length > 0 && (
        <div className="set-kvs">
          {kv.slice(0, 24).map(([k, val]) => (
            <span key={k}>
              <span className="m">{k.replace(/_/g, " ")}</span> <span className="mono">{fmtVal(val).slice(0, 120)}</span>
            </span>
          ))}
        </div>
      )}
      {v.geom && (
        <div className="set-kv">
          Calc-model geometry (RISA own coordinates, ft):{" "}
          <span className="mono">
            Z,X {fmtVal(v.geom.start)} → {fmtVal(v.geom.end)} at elev {v.geom.elev_ft} ft
          </span>
        </div>
      )}
      {v.axial && (
        <div className="set-kv">
          Column axial (k): <span className="mono">{fmtVal(v.axial)}</span>
        </div>
      )}
      {v.end_reactions && (
        <div className="set-kv">
          End reactions (k):{" "}
          <span className="mono">
            {fmtVal({
              start: { DL: v.end_reactions.start?.dl_k, LL: v.end_reactions.start?.ll_k, max: v.end_reactions.start?.max_k },
              end: { DL: v.end_reactions.end?.dl_k, LL: v.end_reactions.end?.ll_k, max: v.end_reactions.end?.max_k },
            })}
          </span>
        </div>
      )}
      {v.vertical_loads_k && (
        <div className="set-kv">
          Footing vertical loads (k): <span className="mono">{fmtVal(v.vertical_loads_k)}</span>
        </div>
      )}
      {notes.length > 0 && (
        <>
          <H3 info="insp.set-rec-notes">Engineer notes ({notes.length})</H3>
          {notes.map((n) => (
            <Li key={n.id} cls="note" onClick={() => a.openNote(n)}>
              <span className="mono">{n.sheet}</span> <i>"{n.text.slice(0, 160)}"</i>
              <div className="why">{n.attached.find((y) => y.record === r.id)?.rule ?? ""}</div>
            </Li>
          ))}
        </>
      )}
      {r.type === "connection_design" && (
        <>
          <H3 info="insp.set-rec-detail">Detail</H3>
          {t ? (
            <Li onClick={() => a.select({ kind: "ctype", id: t.id })}>
              <span className="mono">
                <b>{t.id}</b>
              </span>{" "}
              <span className="m">{t.title}</span>
              <span className="chip warn">candidate</span>
              <div className="why">by title only - the calc cites no detail number, so this is not a link</div>
            </Li>
          ) : (
            <Li>no candidate detail</Li>
          )}
        </>
      )}
      <H3 info="insp.set-rec-fed-by">Fed by ({ins.length})</H3>
      {ins.slice(0, 80).map((e, i) => reLi(e, e.src, "from", i))}
      {!ins.length && <Li>nothing in the calc load path</Li>}
      <H3 info="insp.set-rec-carried-by">Carried by ({outs.length})</H3>
      {outs.slice(0, 80).map((e, i) => reLi(e, e.dst, "to", i))}
      {!outs.length && <Li>nothing in the calc load path</Li>}
      <H3 info="insp.set-rec-elements">Elements linked ({new Set(rls.map((l) => l.el)).size})</H3>
      {rls.slice(0, 150).map((l, i) => {
        const e = x.els.get(l.el);
        return (
          <Li key={i} onClick={() => a.openRLink(l, r.id)}>
            <span className="mono">
              <b>{e?.text}</b>
            </span>{" "}
            <span className="m">
              {e?.sheet} {e?.grid}
            </span>
            {pct(l.score)}
            <div className="why">
              via {x.calcs.get(l.calc)?.sheet_id ?? l.calc} - {l.rule}
            </div>
          </Li>
        );
      })}
      {!rls.length && <Li>No drawn element is linked to this record.</Li>}
      <H3 info="insp.set-rec-rows">Rows on the original pages ({r.ev.length})</H3>
      {[...byTable.entries()].map(([tb, idx]) => (
        <Li key={tb} onClick={() => a.show(recEv(r, idx[0]))}>
          <span className="m">{tb}</span> <span className="chip">p{[...new Set(idx.map((i) => r.ev[i].page))].join(", ")}</span>
          <div className="why mono">{(r.ev[idx[0]].text ?? "").slice(0, 140)}</div>
        </Li>
      ))}
    </>
  );
}

function InspCtype({ x, t, a }: { x: SetIndex; t: CType; a: InspActions }) {
  const insts = (t.instances ?? []).map((i) => x.cinst.get(i)!).filter(Boolean);
  const par = x.recs.get(PARAPET_REC);
  return (
    <>
      <Head
        title={
          <>
            <span className="mono">{t.id}</span> {t.title}
          </>
        }
        kind={`Connection detail · ${t.category} · ${t.sheet} ${t.sheet_title} · PDF p${t.page}${t.scale ? " · " + t.scale : ""}`}
        button="Show detail"
        onButton={() => a.show(ctypeEv(t), t.bbox)}
      />
      {t.spec?.length > 0 && (
        <div className="set-kv">
          Printed: <span className="mono">{t.spec.map((s) => s.text).join(" | ").slice(0, 300)}</span>
        </div>
      )}
      {t.sizes?.length > 0 && (
        <div className="set-kv">
          Sizes: <span className="mono">{t.sizes.join(", ")}</span>
        </div>
      )}
      <H3 info="insp.set-ctype-calc">Design calc</H3>
      {t.id === PARAPET_DETAIL && par ? (
        <Li onClick={() => a.select({ kind: "rec", id: par.id })}>
          <span className="mono">
            <b>{par.title}</b>
          </span>
          <span className="chip warn">candidate</span>
          <div className="why">stair package pp {par.pages.join(", ")} - by title only, the calc cites no detail number</div>
        </Li>
      ) : (
        <Li>No calc page designs this detail (the main package designs no steel connection).</Li>
      )}
      <H3 info="insp.set-ctype-instances">Instances ({insts.length})</H3>
      {insts.map((i) => (
        <Li key={i.id} onClick={() => a.select({ kind: "cinst", id: i.id })}>
          <span className="mono">{i.sheet}</span>{" "}
          <span className="m">
            {i.via} · {i.grid || "-"}
          </span>
          {i.attached.length ? <span className="chip good">{i.attached.map((y) => x.els.get(y.id)?.text ?? y.id).join(", ")}</span> : <span className="chip">unattached</span>}
        </Li>
      ))}
      {!insts.length && <Li>Not called out on any plan or elevation.</Li>}
      {t.referenced_from_details?.length > 0 && (
        <div className="set-kv">
          Referenced from details: <span className="mono">{t.referenced_from_details.join(", ")}</span>
        </div>
      )}
    </>
  );
}

function InspCinst({ x, i, a }: { x: SetIndex; i: CInst; a: InspActions }) {
  const t = i.type_id ? x.ctypes.get(i.type_id) : undefined;
  const mk = x.ig?.conn_markers.find((m) => m.inst === i.id);
  return (
    <>
      <Head
        mono
        title={i.type_id ?? i.symbol_name ?? i.ref}
        kind={`Connection instance · ${i.via}${i.symbol_name ? " - " + i.symbol_name : ""} · ${i.sheet} · grid ${i.grid || "-"} · PDF p${i.page}`}
        button="Show on sheet"
        onButton={() => a.show(cinstEv(i))}
      />
      {i.legend_text && (
        <div className="set-kv">
          Legend: <span className="mono">{i.legend_text}</span>
        </div>
      )}
      {i.context && (
        <div className="set-kv">
          Text: <span className="mono">{i.context}</span>
        </div>
      )}
      {t && (
        <>
          <H3 info="insp.set-cinst-detail">Detail</H3>
          <Li onClick={() => a.select({ kind: "ctype", id: t.id })}>
            <span className="mono">
              <b>{t.id}</b>
            </span>{" "}
            <span className="m">{t.title}</span>
          </Li>
        </>
      )}
      <H3 info="insp.set-cinst-attached">Attached elements ({i.attached.length})</H3>
      {i.attached.map((y) => (
        <Li key={y.id} onClick={() => a.openInstEl(i, y.id)}>
          <span className="mono">
            <b>{x.els.get(y.id)?.text ?? y.id}</b>
          </span>{" "}
          <span className="m">
            {y.type} · {y.role ?? ""} · {y.dist} pt
          </span>
          <button type="button" className="btn sm" onClick={stop(() => a.select({ kind: "el", id: y.id }))}>
            Select
          </button>
        </Li>
      ))}
      {!i.attached.length && <Li>{i.unattached_reason ?? "No drawn element near enough"}</Li>}
      <div className="why">{i.attach_rule}</div>
      <div className="set-m3d">
        {mk ? (
          <>
            <b>In 3D</b> as a marker - {mk.rule}
          </>
        ) : (
          <>
            <b>Not in 3D</b> - no attached element in the 3D model, or not on a plan sheet
          </>
        )}
        <InfoTip id="insp.set-in-3d" />
      </div>
    </>
  );
}

export function SetInspector({ x, sel, a }: { x: SetIndex; sel: Sel; a: InspActions }) {
  let body: ReactNode = null;
  if (!sel) body = <div className="set-ihint">Select an element, a calc page or a finding. Links show both sides' evidence side by side.</div>;
  else if (sel.kind === "el" && x.els.has(sel.id)) body = <InspEl x={x} e={x.els.get(sel.id)!} a={a} />;
  else if (sel.kind === "calc" && x.calcs.has(sel.id)) body = <InspCalc x={x} c={x.calcs.get(sel.id)!} a={a} />;
  else if (sel.kind === "rec" && x.recs.has(sel.id)) body = <InspRec x={x} r={x.recs.get(sel.id)!} a={a} />;
  else if (sel.kind === "ctype" && x.ctypes.has(sel.id)) body = <InspCtype x={x} t={x.ctypes.get(sel.id)!} a={a} />;
  else if (sel.kind === "cinst" && x.cinst.has(sel.id)) body = <InspCinst x={x} i={x.cinst.get(sel.id)!} a={a} />;
  return (
    <section className="set-insp" aria-label="Inspector">
      {body}
    </section>
  );
}
