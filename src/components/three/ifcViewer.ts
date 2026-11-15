// three.js viewer whose geometry comes from a stored IFC revision via web-ifc (MIT).
// Ported from the calc-graph prototype (frontend/src/viewer.ts): meshes are keyed by IFC GlobalId so
// every view can colour / pick elements by the same id the backend uses. Additions here: a dark
// theme, one shared web-ifc engine and file cache, and "ghost" meshes loaded from another revision
// (diff elements the head model does not have) placed in the same building coordinates.
import * as THREE from 'three';
import type { IfcAPI } from 'web-ifc';
import { Structural3DControls, type CameraPose } from '../Structural3DControls';

let enginePromise: Promise<IfcAPI> | null = null;
function engine(): Promise<IfcAPI> {
  if (!enginePromise) {
    enginePromise = (async () => {
      // lazy: web-ifc is its own ~3 MB chunk, fetched only when a model is shown or opened
      const { IfcAPI } = await import('web-ifc');
      const api = new IfcAPI();
      api.SetWasmPath(`${import.meta.env.BASE_URL}wasm/`, true); // copied by scripts/copy-assets.mjs
      await api.Init(undefined, true); // single-threaded build: no COOP/COEP headers, one wasm (web-ifc.wasm)
      return api;
    })();
    enginePromise.catch(() => {
      enginePromise = null;
    });
  }
  return enginePromise;
}

const files = new Map<string, Promise<Uint8Array>>();
function fetchIfc(url: string): Promise<Uint8Array> {
  let p = files.get(url);
  if (!p) {
    p = fetch(url).then(async (r) => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${url}`);
      return new Uint8Array(await r.arrayBuffer());
    });
    p.catch(() => files.delete(url));
    files.set(url, p);
  }
  return p;
}

export interface MeshStyle {
  color: string;
  opacity: number;
  visible: boolean;
  /** emissive glow colour (selection / load path), null for none */
  glow: string | null;
}

/** the default view direction: from the front-right, above (same as the camera's starting position) */
const HOME_DIR = new THREE.Vector3(0.75, 0.55, 0.9).normalize();
const HOME_THETA = Math.atan2(HOME_DIR.x, HOME_DIR.z);
const HOME_PHI = Math.acos(HOME_DIR.y);

/** Fit / Reset / zoom-to-selection animate (300 ms) unless the user asked for reduced motion. */
const animateCamera = () =>
  typeof window === 'undefined' || typeof window.matchMedia !== 'function' || !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export class IfcViewer {
  renderer: THREE.WebGLRenderer;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 5000);
  /**
   * Camera navigation (Structural3DControls): orbit / pan / zoom move the camera directly, with no
   * damping; only Fit, Reset and zoom-to-selection are animated, and any pointer or wheel input takes
   * over at the displayed pose. A click (under 3 px of movement from pointerdown) goes to onClick.
   */
  controls: Structural3DControls;
  /** building coordinates -> scene: offset so the head model sits at the origin */
  world = new THREE.Group();
  group = new THREE.Group();
  ghostGroup = new THREE.Group();
  /** element-graph bounding boxes, for elements with no IFC mesh (ModelInput / legacy JSON models, their diff ghosts) */
  boxGroup = new THREE.Group();
  boxIds = new Set<string>();
  meshes = new Map<string, THREE.Mesh[]>(); // GlobalId -> meshes (head model and ghosts)
  meshToGid = new Map<THREE.Object3D, string>();
  ghostIds = new Set<string>();
  grid: THREE.GridHelper | null = null;
  private ray = new THREE.Raycaster();
  private ro: ResizeObserver;
  private raf = 0;
  private disposed = false;
  private loadToken = 0;
  private ghostToken = 0;
  /** the URL of the head model on screen, set when its load() finished; null while none is */
  private headUrl: string | null = null;

  constructor(
    public el: HTMLElement,
    opts: { onClick?: (e: PointerEvent) => void } = {}
  ) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0);
    el.appendChild(this.renderer.domElement);
    const start: CameraPose = { theta: HOME_THETA, phi: HOME_PHI, radius: 50, target: { x: 0, y: 0, z: 0 } };
    this.controls = new Structural3DControls(this.camera, this.renderer.domElement, start, () => {}, (e) => opts.onClick?.(e));
    this.scene.add(new THREE.HemisphereLight(0xf8fafc, 0x2f333a, 1.7));
    const sun = new THREE.DirectionalLight(0xffffff, 1.5);
    sun.position.set(40, 80, 30);
    this.scene.add(sun);
    const rim = new THREE.DirectionalLight(0xbae6fd, 0.55);
    rim.position.set(-55, 40, -45);
    this.scene.add(rim);
    this.world.add(this.group);
    this.world.add(this.ghostGroup);
    this.world.add(this.boxGroup);
    this.scene.add(this.world);
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(el);
    this.resize();
    const loop = (now: number) => {
      if (this.disposed) return;
      this.raf = requestAnimationFrame(loop);
      this.controls.update(now);
      this.renderer.render(this.scene, this.camera);
    };
    this.raf = requestAnimationFrame(loop);
  }

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
    this.renderer.setSize(r.width, r.height);
    this.camera.aspect = r.width / Math.max(1, r.height);
    this.camera.updateProjectionMatrix();
  }

  private disposeGroup(g: THREE.Group) {
    g.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.geometry.dispose();
        (m.material as THREE.Material).dispose();
      }
    });
    g.clear();
  }

  clearGhosts() {
    for (const gid of this.ghostIds) {
      const kept = (this.meshes.get(gid) ?? []).filter((m) => m.parent !== this.ghostGroup);
      if (kept.length) this.meshes.set(gid, kept);
      else this.meshes.delete(gid);
    }
    this.ghostGroup.children.forEach((m) => this.meshToGid.delete(m));
    this.disposeGroup(this.ghostGroup);
    this.ghostIds.clear();
  }

  clearBoxes() {
    for (const gid of this.boxIds) {
      const kept = (this.meshes.get(gid) ?? []).filter((m) => m.parent !== this.boxGroup);
      if (kept.length) this.meshes.set(gid, kept);
      else this.meshes.delete(gid);
    }
    this.boxGroup.children.forEach((m) => this.meshToGid.delete(m));
    this.disposeGroup(this.boxGroup);
    this.boxIds.clear();
  }

  /**
   * Draw boxes (IFC frame: metres, Z up) for elements that have no mesh. Same frame conversion as
   * web-ifc (three = x, z, -y), so boxes and meshes line up. With no IFC loaded, the boxes set the
   * re-centring and the camera fit.
   */
  setBoxes(boxes: { gid: string; min: number[]; max: number[] }[], standalone: boolean) {
    this.clearBoxes();
    const geom = new THREE.BoxGeometry(1, 1, 1);
    for (const b of boxes) {
      const sx = Math.max(b.max[0] - b.min[0], 0.05);
      const sy = Math.max(b.max[2] - b.min[2], 0.05);
      const sz = Math.max(b.max[1] - b.min[1], 0.05);
      const m = new THREE.Mesh(geom.clone(), new THREE.MeshLambertMaterial({ color: '#9aa3ad', transparent: true }));
      m.scale.set(sx, sy, sz);
      m.position.set((b.min[0] + b.max[0]) / 2, (b.min[2] + b.max[2]) / 2, -(b.min[1] + b.max[1]) / 2);
      this.boxGroup.add(m);
      if (!this.meshes.has(b.gid)) this.meshes.set(b.gid, []);
      this.meshes.get(b.gid)!.push(m);
      this.meshToGid.set(m, b.gid);
      this.boxIds.add(b.gid);
    }
    geom.dispose();
    if (standalone && boxes.length) {
      this.world.position.set(0, 0, 0);
      this.world.updateMatrixWorld(true);
      const bb = new THREE.Box3().setFromObject(this.boxGroup);
      const c = bb.getCenter(new THREE.Vector3());
      this.world.position.set(-c.x, -bb.min.y, -c.z);
      this.world.updateMatrixWorld(true);
      if (this.grid) {
        this.scene.remove(this.grid);
        this.grid = null;
      }
      this.fit();
    }
  }

  /**
   * Empty the scene and invalidate every in-flight load: a load() or loadGhosts() still running
   * after this sees a stale token and paints nothing. Called by Structural3DViewer when the model
   * URL goes null, and by dispose().
   */
  clear() {
    this.invalidateLoads();
    this.emptyScene();
  }

  /**
   * The one place a load is invalidated. Anything that makes the current head model or its ghosts
   * obsolete (clear, dispose, a new load) goes through here; ghosts share the head model's
   * re-centring, so a new head model invalidates them too.
   */
  private invalidateLoads() {
    this.loadToken++;
    this.ghostToken++;
    this.headUrl = null;
  }

  private emptyScene() {
    this.clearGhosts();
    this.clearBoxes();
    this.disposeGroup(this.group);
    this.meshes.clear();
    this.meshToGid.clear();
    if (this.grid) {
      this.scene.remove(this.grid);
      this.grid = null;
    }
  }

  /** Stream the meshes of an IFC file into `target`; only GlobalIds in `only` when given. */
  private async stream(url: string, target: THREE.Group, only: Set<string> | null, isGhost: boolean, isCurrent: () => boolean) {
    const api = await engine();
    const buf = await fetchIfc(url);
    if (!isCurrent()) return;
    // keep the IFC's own coordinates so two revisions overlay exactly; `world` re-centres them
    const mid = api.OpenModel(buf, { COORDINATE_TO_ORIGIN: false });
    try {
      const vtx = new THREE.Vector3();
      const nrm = new THREE.Vector3();
      const gidOf = new Map<number, string>();
      api.StreamAllMeshes(mid, (fm) => {
        let gid = gidOf.get(fm.expressID);
        if (!gid) {
          const line = api.GetLine(mid, fm.expressID, false);
          gid = line?.GlobalId?.value as string | undefined;
          if (!gid) return;
          gidOf.set(fm.expressID, gid);
        }
        if (only && !only.has(gid)) return;
        const pos: number[] = [];
        const nor: number[] = [];
        const idx: number[] = [];
        let base = 0;
        for (let i = 0; i < fm.geometries.size(); i++) {
          const pg = fm.geometries.get(i);
          const g = api.GetGeometry(mid, pg.geometryExpressID);
          const v = api.GetVertexArray(g.GetVertexData(), g.GetVertexDataSize());
          const ix = api.GetIndexArray(g.GetIndexData(), g.GetIndexDataSize());
          const M = new THREE.Matrix4().fromArray(pg.flatTransformation);
          const NM = new THREE.Matrix3().getNormalMatrix(M);
          for (let k = 0; k < v.length; k += 6) {
            vtx.set(v[k], v[k + 1], v[k + 2]).applyMatrix4(M);
            pos.push(vtx.x, vtx.y, vtx.z);
            nrm.set(v[k + 3], v[k + 4], v[k + 5]).applyMatrix3(NM).normalize();
            nor.push(nrm.x, nrm.y, nrm.z);
          }
          for (let k = 0; k < ix.length; k++) idx.push(ix[k] + base);
          base += v.length / 6;
          g.delete();
        }
        if (!pos.length) return;
        const geom = new THREE.BufferGeometry();
        geom.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        geom.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
        geom.setIndex(idx);
        const m = new THREE.Mesh(geom, new THREE.MeshLambertMaterial({ color: '#9aa3ad', transparent: true }));
        target.add(m);
        if (!this.meshes.has(gid)) this.meshes.set(gid, []);
        this.meshes.get(gid)!.push(m);
        this.meshToGid.set(m, gid);
        if (isGhost) this.ghostIds.add(gid);
      });
    } finally {
      api.CloseModel(mid);
    }
  }

  /**
   * Load the head model. Resolves `false` (without painting) when the load was superseded by
   * clear(), dispose() or a newer load(), so the caller can tell a finished load from a dropped one.
   */
  async load(url: string, onProgress: (t: string, pct: number) => void): Promise<boolean> {
    this.invalidateLoads();
    const token = this.loadToken;
    const current = () => token === this.loadToken;
    onProgress('Loading IFC engine…', 5);
    await engine();
    if (!current()) return false;
    onProgress('Downloading model…', 20);
    await fetchIfc(url);
    if (!current()) return false;
    onProgress('Building geometry…', 45);
    this.emptyScene();
    await this.stream(url, this.group, null, false, current);
    if (!current()) return false;
    // re-centre: the head model's bounding-box centre at the origin, its base on the grid
    const box = new THREE.Box3().setFromObject(this.group);
    if (!box.isEmpty()) {
      const c = box.getCenter(new THREE.Vector3());
      this.world.position.set(-c.x, -box.min.y, -c.z);
    }
    this.headUrl = url;
    onProgress('', 100);
    this.fit();
    return true;
  }

  /**
   * Meshes of `gids` from another revision's IFC, in the same coordinates as the head model `headUrl`.
   * Ghosts share that model's re-centring, so they load only once it is the finished head model on
   * screen (else nothing happens and this resolves false), and they stop painting when it is replaced
   * (a new load, clear, dispose), when loadGhosts is called again, or on cancelGhosts().
   * Resolves true when every ghost was loaded for that head model.
   */
  async loadGhosts(headUrl: string, sources: { url: string; gids: string[] }[]): Promise<boolean> {
    if (this.headUrl !== headUrl) return false;
    const head = this.loadToken;
    const token = ++this.ghostToken;
    const current = () => token === this.ghostToken && head === this.loadToken;
    this.clearGhosts();
    for (const s of sources) {
      if (!s.gids.length) continue;
      await this.stream(s.url, this.ghostGroup, new Set(s.gids), true, current);
      if (!current()) return false;
    }
    return true;
  }

  /** Stop any ghost load in flight and remove the ghosts (the head model stays). */
  cancelGhosts() {
    this.ghostToken++;
    this.clearGhosts();
  }

  private boxOf(objs: THREE.Object3D[]): THREE.Box3 {
    const box = new THREE.Box3();
    objs.forEach((o) => box.expandByObject(o));
    return box;
  }

  private frame(box: THREE.Box3, minSize = 6) {
    if (box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3());
    const sz = Math.max(box.getSize(new THREE.Vector3()).length(), minSize);
    // keep the current view direction; move the target and distance only
    this.controls.moveTo({ target: { x: c.x, y: c.y, z: c.z }, radius: sz * 1.15 }, animateCamera());
    this.camera.near = Math.max(0.01, sz / 1000);
    this.camera.far = Math.max(1000, sz * 40);
    this.camera.updateProjectionMatrix();
  }

  /**
   * Frame the whole model from the home direction. `animate` is for the user's Fit / Reset; a fit
   * after a load jumps (there is no previous view of this model to move from).
   */
  fit(animate = false) {
    const box = this.boxOf([...this.group.children, ...this.boxGroup.children].filter((m) => m.visible));
    if (box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3());
    const sz = box.getSize(new THREE.Vector3()).length();
    this.controls.moveTo(
      { theta: HOME_THETA, phi: HOME_PHI, radius: sz * 0.95, target: { x: c.x, y: c.y, z: c.z } },
      animate && animateCamera()
    );
    this.camera.near = sz / 1000;
    this.camera.far = sz * 20;
    this.camera.updateProjectionMatrix();
    if (!this.grid) {
      const g = Math.ceil(sz * 1.2);
      this.grid = new THREE.GridHelper(g, 24, 0x565e6e, 0x383d47);
      (this.grid.material as THREE.Material).opacity = 0.6;
      (this.grid.material as THREE.Material).transparent = true;
      this.grid.position.set(c.x, box.min.y - 0.01, c.z);
      this.scene.add(this.grid);
    }
  }

  focusMany(gids: string[]) {
    const ms = gids.flatMap((g) => this.meshes.get(g) ?? []);
    if (!ms.length) return;
    this.frame(this.boxOf(ms));
  }

  pick(ev: MouseEvent): string | null {
    const r = this.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(ndc, this.camera);
    const cand = [...this.group.children, ...this.ghostGroup.children, ...this.boxGroup.children].filter((m) => m.visible);
    const hits = this.ray.intersectObjects(cand, false);
    // dimmed members are a highlight state, not unpickable: prefer the nearest solid one
    const solid = hits.find((h) => ((h.object as THREE.Mesh).material as THREE.Material).opacity > 0.3);
    const hit = solid ?? hits[0];
    return hit ? (this.meshToGid.get(hit.object) ?? null) : null;
  }

  style(gid: string, s: MeshStyle) {
    for (const m of this.meshes.get(gid) ?? []) {
      const mat = m.material as THREE.MeshLambertMaterial;
      m.visible = s.visible;
      mat.color.set(s.color);
      mat.opacity = s.opacity;
      mat.transparent = s.opacity < 1;
      mat.depthWrite = s.opacity >= 0.5;
      mat.emissive.set(s.glow ?? '#000000');
      mat.emissiveIntensity = s.glow ? 0.55 : 0;
      m.renderOrder = s.opacity < 0.5 ? 0 : 2;
    }
  }
}
