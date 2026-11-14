import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import { Viewer3D, type MemberStyle, type Viewer3DHandle } from "../../components/Viewer3D";
import type { Viewer } from "../../viewer";
import type { Impact } from "./api";
import { colShort, type DesignIndex } from "./util";

/**
 * Building feet <-> three.js coordinates, measured from the loaded model itself (the centres of
 * three corner columns and one column's height), so it holds whatever origin shift or axis swap
 * web-ifc applied. Composition only: the shared Viewer class is not modified.
 */
interface Mapping {
  o: THREE.Vector3; // three point of plan (0,0) at z = z0
  ex: THREE.Vector3; // three vector per ft of plan x
  ey: THREE.Vector3; // per ft of plan y
  up: number; // three units per ft vertically
  z0: number; // ft of o
  ftToUnit: number;
}

function centre(v: Viewer, gid: string | undefined) {
  const ms = gid ? v.meshes.get(gid) : undefined;
  if (!ms?.length) return null;
  const b = new THREE.Box3();
  ms.forEach((m) => b.expandByObject(m));
  return b;
}

function measure(v: Viewer, idx: DesignIndex): Mapping | null {
  const cols = idx.building.columns;
  const find = (x: number, y: number) =>
    idx.columns.find((c) => {
      const p = cols[colShort(c.id)];
      return p && p[0] === x && p[1] === y;
    });
  const xs = idx.building.grids.x.map((g) => g[1]);
  const ys = idx.building.grids.y.map((g) => g[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const a = find(x0, y0), bx = find(x1, y0), by = find(x0, y1);
  const A = centre(v, a?.global_id), B = centre(v, bx?.global_id), C = centre(v, by?.global_id);
  if (!a || !A || !B || !C) return null;
  const ca = A.getCenter(new THREE.Vector3()), cb = B.getCenter(new THREE.Vector3()), cc = C.getCenter(new THREE.Vector3());
  const z0 = Number(a.z0 ?? 0), z1 = Number(a.z1 ?? 40);
  const up = (A.max.y - A.min.y) / Math.max(1e-6, z1 - z0);
  const ex = cb.clone().sub(ca).setY(0).divideScalar(x1 - x0);
  const ey = cc.clone().sub(ca).setY(0).divideScalar(y1 - y0);
  const o = new THREE.Vector3(ca.x, A.min.y, ca.z).sub(ex.clone().multiplyScalar(x0)).sub(ey.clone().multiplyScalar(y0));
  return { o, ex, ey, up, z0, ftToUnit: ex.length() };
}

const toThree = (m: Mapping, x: number, y: number, z: number) =>
  m.o.clone().add(m.ex.clone().multiplyScalar(x)).add(m.ey.clone().multiplyScalar(y)).setY(m.o.y + (z - m.z0) * m.up);

function toPlan(m: Mapping, p: THREE.Vector3) {
  // solve o + ex*x + ey*y = p in the horizontal (x, z) components
  const qx = p.x - m.o.x, qz = p.z - m.o.z;
  const det = m.ex.x * m.ey.z - m.ey.x * m.ex.z;
  return { x: (qx * m.ey.z - m.ey.x * qz) / det, y: (m.ex.x * qz - qx * m.ex.z) / det };
}

function bar(a: THREE.Vector3, b: THREE.Vector3, t: number, mat: THREE.Material) {
  const len = a.distanceTo(b);
  const g = new THREE.BoxGeometry(t, t, Math.max(len, 1e-3));
  const mesh = new THREE.Mesh(g, mat);
  mesh.position.copy(a).add(b).multiplyScalar(0.5);
  mesh.lookAt(b);
  return mesh;
}

export interface MoveViewerProps {
  idx: DesignIndex;
  url: string;
  rev?: string | number;
  styleOf: (gid: string) => MemberStyle | undefined;
  selectedGid: string | null;
  onPick: (gid: string | null) => void;
  moveMode: boolean;
  selected: string | null;
  dx: number;
  dy: number;
  remove: boolean;
  step: number;
  impact: Impact | undefined;
  onDrag: (dx: number, dy: number) => void;
  onDrop: (dx: number, dy: number) => void;
  children?: ReactNode;
}

const LIMIT = 20;

export function MoveViewer(p: MoveViewerProps) {
  const { idx, url, rev, styleOf, selectedGid, onPick, moveMode, selected, dx, dy, remove, step, impact, onDrag, onDrop, children } = p;
  const handle = useRef<Viewer3DHandle>(null);
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [map, setMap] = useState<Mapping | null>(null);
  const ghost = useRef(new THREE.Group());
  const live = useRef({ dx, dy, step, onDrag, onDrop });
  live.current = { dx, dy, step, onDrag, onDrop };

  const onLoaded = useCallback(
    (v: Viewer) => {
      setViewer(v);
      setMap(measure(v, idx));
      if (!v.extra.children.includes(ghost.current)) v.extra.add(ghost.current);
    },
    [idx],
  );

  // the ghost: the column at its new position, an arrow on the ground, and the re-framed members
  useEffect(() => {
    const g = ghost.current;
    g.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
    });
    g.clear();
    if (!map || !selected || !moveMode) return;
    const c = idx.el.get(selected);
    const pos = idx.building.columns[colShort(selected)];
    if (!c || !pos) return;
    const z0 = Number(c.z0 ?? 0), z1 = Number(c.z1 ?? 40);
    const s = map.ftToUnit;
    if (remove) return;
    const nx = pos[0] + dx, ny = pos[1] + dy;
    const colMat = new THREE.MeshLambertMaterial({ color: "#2f6fed", transparent: true, opacity: 0.7, depthWrite: false });
    const box = new THREE.Mesh(new THREE.BoxGeometry(1.8 * s, (z1 - z0) * map.up, 1.8 * s), colMat);
    box.position.copy(toThree(map, nx, ny, (z0 + z1) / 2));
    box.userData.ghost = true;
    g.add(box);
    // grab handle at the base, bigger than the column so it is easy to hit
    const handleMat = new THREE.MeshLambertMaterial({ color: "#2f6fed", transparent: true, opacity: 0.7, depthWrite: false });
    const disk = new THREE.Mesh(new THREE.CylinderGeometry(2.4 * s, 2.4 * s, 0.25 * s, 32), handleMat);
    disk.position.copy(toThree(map, nx, ny, 0.2));
    disk.userData.ghost = true;
    g.add(disk);
    if (dx || dy) {
      const arrowMat = new THREE.MeshBasicMaterial({ color: "#2f6fed" });
      g.add(bar(toThree(map, pos[0], pos[1], 0.3), toThree(map, nx, ny, 0.3), 0.35 * s, arrowMat));
    }
    const memMat = new THREE.MeshLambertMaterial({ color: "#2f6fed", transparent: true, opacity: 0.55, depthWrite: false });
    for (const [eid, geo] of Object.entries(impact?.geometry ?? {})) {
      const e = idx.el.get(eid) as { p1?: number[] } | undefined;
      const z = e?.p1?.[2] ?? 0;
      g.add(bar(toThree(map, geo.p1[0], geo.p1[1], z), toThree(map, geo.p2[0], geo.p2[1], z), 0.7 * s, memMat.clone()));
    }
  }, [map, selected, moveMode, dx, dy, remove, impact, idx]);

  // drag the ghost (or the selected column) on the ground plane, with grid snap
  useEffect(() => {
    if (!viewer || !map || !moveMode || !selected) return;
    const el = viewer.renderer.domElement;
    const ray = new THREE.Raycaster();
    const ground = new THREE.Plane(new THREE.Vector3(0, 1, 0), -map.o.y);
    const pos = idx.building.columns[colShort(selected)];
    let start: { x: number; y: number } | null = null;
    const planAt = (ev: PointerEvent) => {
      const r = el.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1), viewer.camera);
      const hit = new THREE.Vector3();
      return ray.ray.intersectPlane(ground, hit) ? toPlan(map, hit) : null;
    };
    const snap = (v: number) => {
      const st = live.current.step;
      return Math.max(-LIMIT, Math.min(LIMIT, Math.round(v / st) * st));
    };
    const onDown = (ev: PointerEvent) => {
      if (ev.button !== 0 || !pos) return;
      const onGhost = !!viewer.hitExtra(ev, ghost.current.children.filter((o) => o.userData.ghost));
      if (!onGhost) return;
      const q = planAt(ev);
      if (!q) return;
      ev.stopImmediatePropagation();
      ev.preventDefault();
      viewer.controls.enabled = false;
      start = { x: q.x - live.current.dx, y: q.y - live.current.dy };
      el.setPointerCapture(ev.pointerId);
      el.style.cursor = "grabbing";
    };
    const onMove = (ev: PointerEvent) => {
      if (!start) return;
      const q = planAt(ev);
      if (q) live.current.onDrag(snap(q.x - start.x), snap(q.y - start.y));
    };
    const onUp = (ev: PointerEvent) => {
      if (!start) return;
      const q = planAt(ev);
      const s0 = start;
      start = null;
      viewer.controls.enabled = true;
      el.style.cursor = "";
      ev.stopImmediatePropagation();
      if (q) live.current.onDrop(snap(q.x - s0.x), snap(q.y - s0.y));
      else live.current.onDrop(live.current.dx, live.current.dy);
    };
    el.addEventListener("pointerdown", onDown, true);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp, true);
    return () => {
      el.removeEventListener("pointerdown", onDown, true);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp, true);
      viewer.controls.enabled = true;
    };
  }, [viewer, map, moveMode, selected, idx]);

  useEffect(() => {
    if (selectedGid && viewer) handle.current?.focus(selectedGid);
  }, [selectedGid, viewer]);

  return (
    <Viewer3D
      ref={handle}
      url={url}
      rev={rev}
      info="viewer3d.move-model"
      styleOf={styleOf}
      selected={selectedGid}
      onPick={(gid) => onPick(gid)}
      onLoaded={onLoaded}
    >
      {children}
      {moveMode && selected && !map && viewer && <div className="v2-3d-note">Could not place the ghost in this model (corner columns not found).</div>}
    </Viewer3D>
  );
}
