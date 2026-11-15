// 3D tab of the drawing-set view: the building's IFC model (each drawing tag tied to its model element by
// the registry resolver), connection markers, and - when the calc package prints a calc model's
// geometry - that calc model as a ghost placed beside or over it (a placement choice, never a registration).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { urls } from "../../api/client";
import { Legend, type LegendItem } from "../../components/Legend";
import { Viewer3D, type Viewer3DHandle } from "../../components/Viewer3D";
import { InfoTip } from "../../help/InfoTip";
import type { Viewer } from "../../viewer";
import type { Sel, SetIndex } from "./model";

const STATUS3D: Record<string, string> = { linked: "#1f9d63", "no calc found": "#d64545", "size mismatch": "#e0942f" };
const CALC3D = "#8e5bd9", CALC3D_GAP = "#d64545", MARK3D = "#e8590c", SEL3D = "#ffb000";
const FTM = 0.3048;

interface Ov {
  grp: THREE.Group;
  mk: THREE.Group;
  recMesh: Map<string, THREE.Mesh[]>;
  instMesh: Map<string, THREE.Mesh>;
}

function ghostMat(color: string, op: number) {
  return new THREE.MeshBasicMaterial({ color, transparent: true, opacity: op, depthWrite: false });
}
function boxBetween(a: THREE.Vector3, b: THREE.Vector3, t: number, mat: THREE.Material) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(t, t, Math.max(a.distanceTo(b), 0.01)), mat);
  m.position.copy(a).add(b).multiplyScalar(0.5);
  m.lookAt(b);
  return m;
}
const drawnBox = (v: Viewer) => {
  const b = new THREE.Box3();
  v.group.children.forEach((m) => b.expandByObject(m));
  return b;
};

export interface Set3DProps {
  x: SetIndex;
  sel: Sel;
  onSelect: (s: Sel) => void;
  onDiff: (i: number) => void;
}

export function Set3D({ x, sel, onSelect, onDiff }: Set3DProps) {
  const v3 = useRef<Viewer3DHandle>(null);
  const ov = useRef<Ov | null>(null);
  const [ready, setReady] = useState(0);
  const [drawnOn, setDrawnOn] = useState(true);
  const [mkOn, setMkOn] = useState(true);
  const [calcOn, setCalcOn] = useState(false);
  const [place, setPlace] = useState<"beside" | "extents">("beside");
  const ig = x.ig;

  const gidToEl = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of x.g.elements) if (e.model?.gid) m.set(e.model.gid, e.id);
    return m;
  }, [x]);
  const elByGid = useMemo(() => new Map(x.g.elements.filter((e) => e.model?.gid).map((e) => [e.model!.gid!, e])), [x]);

  /** build the calc-model ghost and the connection markers into viewer.extra, once per loaded model */
  const onLoaded = useCallback(
    (v: Viewer) => {
      v.camera.position.sub(v.controls.target).multiplyScalar(1.6).add(v.controls.target);
      if (ov.current) {
        v.extra.remove(ov.current.grp, ov.current.mk);
        ov.current = null;
      }
      if (ig) {
        const o = ig.overlay;
        const st: Ov = { grp: new THREE.Group(), mk: new THREE.Group(), recMesh: new Map(), instMesh: new Map() };
        const add = (rec: string, m: THREE.Mesh) => {
          m.userData.rec = rec;
          st.grp.add(m);
          (st.recMesh.get(rec) ?? st.recMesh.set(rec, []).get(rec)!).push(m);
        };
        // RISA Z runs from grid 1, X from grid E: both negated so grid numbering runs as on the drawings
        const P = (z: number, xx: number, el: number) => new THREE.Vector3(-z * FTM, el * FTM, -xx * FTM);
        for (const mb of o.members) add(mb.rec, boxBetween(P(mb.a[0], mb.a[1], mb.elev), P(mb.b[0], mb.b[1], mb.elev), 0.22, ghostMat(mb.absent_ends ? CALC3D_GAP : CALC3D, 0.55)));
        for (const c of o.columns) add(c.rec, boxBetween(P(c.z, c.x, c.bot), P(c.z, c.x, c.top), 0.28, ghostMat(CALC3D, 0.55)));
        const zs = o.columns.map((c) => c.z).concat(o.members.flatMap((m) => [m.a[0], m.b[0]]));
        const xs = o.columns.map((c) => c.x).concat(o.members.flatMap((m) => [m.a[1], m.b[1]]));
        if (zs.length) {
          const [z0, z1, x0, x1] = [Math.min(...zs), Math.max(...zs), Math.min(...xs), Math.max(...xs)];
          for (const el of Object.values(o.levels)) {
            const pts = [P(z0, x0, el), P(z1, x0, el), P(z1, x1, el), P(z0, x1, el), P(z0, x0, el)];
            const ln = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineDashedMaterial({ color: CALC3D, dashSize: 0.6, gapSize: 0.4 }));
            ln.computeLineDistances();
            st.grp.add(ln);
          }
        }
        st.grp.visible = false;
        v.extra.add(st.grp);
        for (const mk of ig.conn_markers) {
          const s = new THREE.Mesh(new THREE.SphereGeometry(0.28, 12, 8), new THREE.MeshBasicMaterial({ color: MARK3D }));
          s.position.set(mk.pos[0], mk.pos[1], mk.pos[2]);
          s.userData.inst = mk.inst;
          st.mk.add(s);
          st.instMesh.set(mk.inst, s);
        }
        v.extra.add(st.mk);
        ov.current = st;
      }
      setReady((n) => n + 1);
    },
    [ig],
  );

  const viewer = () => v3.current?.viewer() ?? null;

  // placement of the ghost: beside the drawn model, or centred on its plan extents
  useEffect(() => {
    const v = viewer(), o = ov.current;
    if (!v || !o || !ready) return;
    o.grp.visible = calcOn;
    o.grp.position.set(0, 0, 0);
    o.grp.updateMatrixWorld(true);
    const cb = new THREE.Box3();
    o.grp.children.forEach((m) => cb.expandByObject(m));
    const db = drawnBox(v);
    if (cb.isEmpty() || db.isEmpty()) return;
    const cc = cb.getCenter(new THREE.Vector3()), dc = db.getCenter(new THREE.Vector3());
    // both share level 1 = 0 (the calc's base elevation, the drawings' datum): only plan offsets move
    if (place === "extents") o.grp.position.set(dc.x - cc.x, 0, dc.z - cc.z);
    else o.grp.position.set(db.max.x + 8 - cb.min.x, 0, dc.z - cc.z);
    o.grp.updateMatrixWorld(true);
    // fit everything shown
    const b = drawnBox(v);
    if (calcOn) o.grp.children.forEach((m) => b.expandByObject(m));
    const c = b.getCenter(new THREE.Vector3()), sz = b.getSize(new THREE.Vector3()).length();
    v.controls.target.copy(c);
    const half = THREE.MathUtils.degToRad(v.camera.fov / 2);
    const dist = sz / 2 / Math.sin(Math.min(half, Math.atan(Math.tan(half) * v.camera.aspect)));
    v.camera.position.copy(c).add(new THREE.Vector3(0.75, 0.55, 0.9).normalize().multiplyScalar(dist * 0.95));
    v.camera.far = Math.max(v.camera.far, sz * 20);
    v.camera.updateProjectionMatrix();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calcOn, place, ready]);

  useEffect(() => {
    if (ov.current) ov.current.mk.visible = mkOn;
  }, [mkOn, ready]);

  // the group the selection lights up in the drawn model
  const group = useMemo(() => {
    if (!sel) return null;
    if (sel.kind === "calc") return new Set((x.linksByCalc.get(sel.id) ?? []).map((l) => l.el));
    if (sel.kind === "rec") return new Set((x.rlByRec.get(sel.id) ?? []).map((l) => l.el));
    if (sel.kind === "cinst") return new Set(x.cinst.get(sel.id)?.attached.map((a) => a.id) ?? []);
    if (sel.kind === "ctype") return new Set((x.ctypes.get(sel.id)?.instances ?? []).flatMap((i) => x.cinst.get(i)?.attached.map((a) => a.id) ?? []));
    return null;
  }, [sel, x]);
  const selEl = sel?.kind === "el" ? sel.id : null;
  const styleOf = useCallback(
    (gid: string) => {
      const e = elByGid.get(gid);
      if (!e) return undefined;
      const dim = (selEl && e.id !== selEl) || (group && !group.has(e.id));
      const lit = !!group?.has(e.id);
      return { color: lit ? SEL3D : (STATUS3D[e.model?.status3d ?? ""] ?? "#9aa5b1"), opacity: dim ? 0.18 : 1, visible: drawnOn };
    },
    [elByGid, selEl, group, drawnOn],
  );

  // calc-model + marker highlight, and camera focus on selection change
  useEffect(() => {
    const v = viewer(), o = ov.current;
    if (!v || !ready) return;
    const selRec = sel?.kind === "rec" ? sel.id : null;
    if (o && ig) {
      for (const [rid, ms] of o.recMesh)
        for (const mesh of ms) {
          const mat = mesh.material as THREE.MeshBasicMaterial;
          const om = ig.overlay.members.find((m) => m.rec === rid);
          mat.color.set(rid === selRec ? SEL3D : om?.absent_ends ? CALC3D_GAP : CALC3D);
          mat.opacity = rid === selRec ? 1 : selRec ? 0.25 : 0.55;
        }
      const inst = sel?.kind === "cinst" ? sel.id : null;
      const typ = sel?.kind === "ctype" ? x.ctypes.get(sel.id) : null;
      const selInsts = new Set<string>(inst ? [inst] : typ ? (typ.instances ?? []) : selEl ? (x.instByEl.get(selEl) ?? []).map((i) => i.id) : []);
      for (const [iid, mesh] of o.instMesh) {
        (mesh.material as THREE.MeshBasicMaterial).color.set(selInsts.has(iid) ? SEL3D : MARK3D);
        mesh.scale.setScalar(selInsts.has(iid) ? 1.8 : 1);
      }
    }
    const focusObjs = (objs: THREE.Object3D[]) => {
      const b = new THREE.Box3();
      objs.forEach((ob) => b.expandByObject(ob));
      if (b.isEmpty()) return;
      const c = b.getCenter(new THREE.Vector3()), off = v.camera.position.clone().sub(v.controls.target);
      v.controls.target.copy(c);
      v.camera.position.copy(c).add(off.setLength(Math.max(12, b.getSize(new THREE.Vector3()).length() * 4)));
    };
    if (selEl) {
      const g = x.els.get(selEl)?.model?.gid;
      if (g) v.focus(g);
    } else if (selRec && o?.grp.visible && o.recMesh.has(selRec)) focusObjs(o.recMesh.get(selRec)!);
    else if (sel?.kind === "cinst" && o?.instMesh.has(sel.id)) focusObjs([o.instMesh.get(sel.id)!]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel, ready, calcOn]);

  /** nearest of: a drawn member, a calc-model member, a marker (markers win near-ties) */
  const onPick = (gid: string | null, ev: MouseEvent) => {
    const v = viewer(), o = ov.current;
    if (!v) return;
    const dIfc = drawnOn ? v.pickDist(ev) : Infinity;
    const hOv = o && o.grp.visible ? v.hitExtra(ev, o.grp.children.filter((ob) => (ob as THREE.Mesh).isMesh)) : null;
    const hMk = o && o.mk.visible ? v.hitExtra(ev, o.mk.children) : null;
    const best = [
      { d: dIfc, f: () => { const id = gid ? gidToEl.get(gid) : null; if (id) onSelect({ kind: "el", id }); } },
      { d: hOv?.distance ?? Infinity, f: () => onSelect({ kind: "rec", id: hOv!.object.userData.rec as string }) },
      { d: (hMk?.distance ?? Infinity) - 0.6, f: () => onSelect({ kind: "cinst", id: hMk!.object.userData.inst as string }) },
    ].sort((a, b) => a.d - b.d)[0];
    if (best.d < Infinity) best.f();
  };

  const m = (x.g as unknown as { model?: { elements_in_3d?: number } }).model ?? {};
  const hasCalcModel = !!ig && ig.overlay.members.length + ig.overlay.columns.length > 0;
  const assumed = x.g.elements.filter((e) => e.model?.in3d && (e.model.assumed ?? []).length).length;
  const legend: LegendItem[] = [
    { label: "tag linked to a calc", color: STATUS3D.linked, info: "legend.set3d-linked" },
    { label: "tag: no calc found", color: STATUS3D["no calc found"], info: "legend.set3d-no-calc" },
    { label: "tag: size mismatch", color: STATUS3D["size mismatch"], info: "legend.set3d-size-mismatch" },
    ...(ig ? [{ label: "connection instance", color: MARK3D, shape: "dot" as const, info: "legend.set3d-marker" as const }] : []),
    ...(calcOn
      ? [
          { label: "calc model (ghost)", color: CALC3D, info: "legend.set3d-calc-model" as const },
          { label: "calc member with an end not supported", color: CALC3D_GAP, info: "legend.set3d-calc-gap" as const },
        ]
      : []),
    { label: "selected", color: SEL3D, info: "legend.set3d-selected" },
  ];
  const o = ig?.overlay;

  return (
    <div className="set-3d">
      <div className="set-3d-note muted">
        {m.elements_in_3d ?? 0} of {x.g.elements.length} drawing elements tied to the model{assumed ? ` · ${assumed} with an assumed value` : ""}
        <InfoTip id="stat.set3d-coverage" />
      </div>
      <div className="set-3d-stage">
        <Viewer3D ref={v3} url={urls.setModelIfc(x.sid)} rev={x.sid} toOrigin={false} info="viewer3d.set-model" styleOf={styleOf} selected={selEl ? (x.els.get(selEl)?.model?.gid ?? null) : null} onPick={onPick} onLoaded={onLoaded}>
          <div className="set-side3d">
            {ig && (
              <fieldset className="set-ctl3d">
                <legend className="sr-only">Layers</legend>
                <div className="set-ctl3d-h">
                  Layers <InfoTip id="tool.set3d-layers" />
                </div>
                <label>
                  <input type="checkbox" checked={drawnOn} onChange={(e) => setDrawnOn(e.target.checked)} /> Building model (IFC)
                </label>
                <label>
                  <input type="checkbox" checked={mkOn} onChange={(e) => setMkOn(e.target.checked)} /> Connection markers ({ig.conn_markers.length})
                </label>
                {hasCalcModel && (
                  <label title="The calc model's geometry from the calc records - not registered to the drawings">
                    <input type="checkbox" checked={calcOn} onChange={(e) => setCalcOn(e.target.checked)} /> Calc model (from the calc records)
                  </label>
                )}
                {calcOn && hasCalcModel && (
                  <div className="set-place" role="radiogroup" aria-label="Calc model placement">
                    <label>
                      <input type="radio" name="set-place" value="beside" checked={place === "beside"} onChange={() => setPlace("beside")} /> Beside - no alignment
                    </label>
                    <label title="Centres the two plan extents on each other - a visual approximation, not a registration">
                      <input type="radio" name="set-place" value="extents" checked={place === "extents"} onChange={() => setPlace("extents")} /> Overlaid on building extents (approximation)
                    </label>
                    <InfoTip id="tool.set3d-placement" />
                  </div>
                )}
              </fieldset>
            )}
            {calcOn && hasCalcModel && o && (
              <div className="set-ban3d">
                <b>Calc model - NOT registered to the drawings.</b>{" "}
                {place === "extents" ? "Overlaid by centring the two plan extents: a visual approximation, not a match." : "Placed beside the drawn model, no alignment."}
                <div>
                  Differences, with evidence <InfoTip id="evidence.set3d-differences" />:{" "}
                  {o.differences.map((d, i) => (
                    <button type="button" key={i} className="btn sm" title={d.text} onClick={() => onDiff(i)}>
                      {d.what}
                    </button>
                  ))}
                </div>
                <details>
                  <summary>What this shows</summary>
                  Drawn from the calc record tables in its own plan coordinates and its own storeys (
                  {Object.entries(o.levels)
                    .map(([k, v]) => `${k} ${v} ft`)
                    .join(", ")}
                  ). Members that look aligned are not the same members. A column-position fit was tried and dropped ({o.transform_dropped}). Click a calc member for its
                  record rows.
                </details>
              </div>
            )}
          </div>
          <Legend info="legend.set3d" title="3D colours" variant="overlay" items={legend} />
        </Viewer3D>
      </div>
    </div>
  );
}
