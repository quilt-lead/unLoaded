// three.js viewer; geometry comes from the stored IFC revision via web-ifc (MIT).
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { IfcAPI } from "web-ifc";

export class Viewer {
  renderer: THREE.WebGLRenderer;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
  controls: OrbitControls;
  group = new THREE.Group();
  /** Extra scene content a page adds beside the IFC model (overlays, markers); not touched by clear(). */
  extra = new THREE.Group();
  meshes = new Map<string, THREE.Mesh[]>(); // GlobalId -> meshes
  meshToGid = new Map<THREE.Object3D, string>();
  grid: THREE.GridHelper | null = null;
  loadedRev: number | null = null;
  private ifc: IfcAPI | null = null;
  private ray = new THREE.Raycaster();

  constructor(public el: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    el.appendChild(this.renderer.domElement);
    this.camera.position.set(30, 25, 35);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(40, 80, 30);
    this.scene.add(sun);
    this.scene.add(this.group);
    this.scene.add(this.extra);
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(el);
    this.resize();
    const loop = () => {
      if (this.disposed) return;
      this.raf = requestAnimationFrame(loop);
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    };
    loop();
  }

  private ro: ResizeObserver;
  private raf = 0;
  private disposed = false;

  /** Stop the render loop and free GPU resources (the React wrapper calls this on unmount). */
  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    this.clear();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
  }

  resize() {
    const r = this.el.getBoundingClientRect();
    if (!r.width || !r.height) return;
    this.renderer.setSize(r.width, r.height); // updateStyle: CSS size = panel, buffer = panel x devicePixelRatio
    this.camera.aspect = r.width / Math.max(1, r.height);
    this.camera.updateProjectionMatrix();
  }

  clear() {
    this.group.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      }
    });
    this.group.clear();
    this.meshes.clear();
    this.meshToGid.clear();
    if (this.grid) {
      this.scene.remove(this.grid);
      this.grid = null;
    }
  }

  async load(
    url: string,
    rev: number,
    onProgress: (t: string, pct: number) => void,
    toOrigin = true,
  ) {
    onProgress("Loading IFC engine…", 5);
    if (!this.ifc) {
      this.ifc = new IfcAPI();
      this.ifc.SetWasmPath("/wasm/", true);
      await this.ifc.Init();
    }
    const api = this.ifc;
    onProgress("Downloading model…", 15);
    const buf = new Uint8Array(await (await fetch(url)).arrayBuffer());
    onProgress("Building geometry…", 40);
    // toOrigin=false keeps the IFC's own coordinates (metres, Y up), so a page can place
    // content it computed in the same building coordinates (e.g. connection markers).
    const mid = api.OpenModel(buf, { COORDINATE_TO_ORIGIN: toOrigin });
    this.clear();
    const vtx = new THREE.Vector3(),
      nrm = new THREE.Vector3();
    const gidOf = new Map<number, string>();
    api.StreamAllMeshes(mid, (fm) => {
      let gid = gidOf.get(fm.expressID);
      if (!gid) {
        const line = api.GetLine(mid, fm.expressID, false);
        gid = line?.GlobalId?.value as string;
        if (!gid) return;
        gidOf.set(fm.expressID, gid);
      }
      const pos: number[] = [],
        nor: number[] = [],
        idx: number[] = [];
      let base = 0;
      for (let i = 0; i < fm.geometries.size(); i++) {
        const pg = fm.geometries.get(i),
          g = api.GetGeometry(mid, pg.geometryExpressID);
        const v = api.GetVertexArray(g.GetVertexData(), g.GetVertexDataSize());
        const ix = api.GetIndexArray(g.GetIndexData(), g.GetIndexDataSize());
        const M = new THREE.Matrix4().fromArray(pg.flatTransformation),
          NM = new THREE.Matrix3().getNormalMatrix(M);
        for (let k = 0; k < v.length; k += 6) {
          vtx.set(v[k], v[k + 1], v[k + 2]).applyMatrix4(M);
          pos.push(vtx.x, vtx.y, vtx.z);
          nrm
            .set(v[k + 3], v[k + 4], v[k + 5])
            .applyMatrix3(NM)
            .normalize();
          nor.push(nrm.x, nrm.y, nrm.z);
        }
        for (let k = 0; k < ix.length; k++) idx.push(ix[k] + base);
        base += v.length / 6;
        g.delete();
      }
      if (!pos.length) return;
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      geom.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
      geom.setIndex(idx);
      const m = new THREE.Mesh(
        geom,
        new THREE.MeshLambertMaterial({ color: "#c3cad3", transparent: true }),
      );
      this.group.add(m);
      if (!this.meshes.has(gid)) this.meshes.set(gid, []);
      this.meshes.get(gid)!.push(m);
      this.meshToGid.set(m, gid);
    });
    api.CloseModel(mid);
    this.loadedRev = rev;
    onProgress("", 100);
    this.fit();
  }

  fit(onlyVisible = true) {
    const box = new THREE.Box3();
    this.group.children.forEach((m) => {
      if (!onlyVisible || m.visible) box.expandByObject(m);
    });
    if (box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3()),
      sz = box.getSize(new THREE.Vector3()).length();
    this.controls.target.copy(c);
    this.camera.position
      .copy(c)
      .add(
        new THREE.Vector3(0.75, 0.55, 0.9)
          .normalize()
          .multiplyScalar(sz * 0.95),
      );
    this.camera.near = sz / 1000;
    this.camera.far = sz * 20;
    this.camera.updateProjectionMatrix();
    if (!this.grid) {
      const g = Math.ceil(sz * 1.2);
      this.grid = new THREE.GridHelper(g, 24, 0x9aa3ad, 0xc9ced5);
      (this.grid.material as THREE.Material).opacity = 0.35;
      (this.grid.material as THREE.Material).transparent = true;
      this.grid.position.set(c.x, box.min.y - 0.01, c.z);
      this.scene.add(this.grid);
    }
  }

  focus(gid: string) {
    const ms = this.meshes.get(gid);
    if (!ms) return;
    const b = new THREE.Box3();
    ms.forEach((m) => b.expandByObject(m));
    if (b.isEmpty()) return;
    const c = b.getCenter(new THREE.Vector3()),
      off = this.camera.position.clone().sub(this.controls.target);
    this.controls.target.copy(c);
    this.camera.position
      .copy(c)
      .add(
        off.setLength(
          Math.max(12, b.getSize(new THREE.Vector3()).length() * 4),
        ),
      );
  }

  private aim(ev: MouseEvent) {
    const r = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((ev.clientX - r.left) / r.width) * 2 - 1,
      -((ev.clientY - r.top) / r.height) * 2 + 1,
    );
    this.ray.setFromCamera(ndc, this.camera);
  }

  /** Nearest visible object of `objs` under the mouse (for page-added content in `extra`). */
  hitExtra(ev: MouseEvent, objs: THREE.Object3D[]): THREE.Intersection | null {
    this.aim(ev);
    const vis = objs.filter((o) => {
      for (let p: THREE.Object3D | null = o; p; p = p.parent) if (!p.visible) return false;
      return true;
    });
    return this.ray.intersectObjects(vis, false)[0] ?? null;
  }

  /** Distance along the ray to the IFC member pick() would return (Infinity if none). */
  pickDist(ev: MouseEvent): number {
    this.aim(ev);
    const hits = this.ray.intersectObjects(this.group.children.filter((m) => m.visible), false);
    const solid = hits.find((h) => ((h.object as THREE.Mesh).material as THREE.Material).opacity > 0.3);
    return (solid ?? hits[0])?.distance ?? Infinity;
  }

  pick(ev: MouseEvent): string | null {
    this.aim(ev);
    // Dimmed / x-rayed members are a highlight state, not unpickable: prefer the
    // nearest solid member on the ray, else the nearest faded one.
    const cand = this.group.children.filter((m) => m.visible);
    const hits = this.ray.intersectObjects(cand, false);
    const solid = hits.find(
      (h) =>
        ((h.object as THREE.Mesh).material as THREE.Material).opacity > 0.3,
    );
    const hit = solid ?? hits[0];
    return hit ? (this.meshToGid.get(hit.object) ?? null) : null;
  }

  style(
    gid: string,
    color: string,
    opacity: number,
    visible: boolean,
    selected: boolean,
  ) {
    for (const m of this.meshes.get(gid) ?? []) {
      const mat = m.material as THREE.MeshLambertMaterial;
      m.visible = visible;
      mat.color.set(selected ? "#ffb000" : color);
      const op = selected ? 1 : opacity;
      mat.opacity = op;
      mat.transparent = op < 1;
      mat.depthWrite = op >= 0.5;
      mat.emissive.set(selected ? 0x553300 : 0x000000);
    }
  }
}
