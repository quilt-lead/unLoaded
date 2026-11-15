import React, { useCallback, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { BimNode } from '../types/bim';
import { getGraphNodeColor } from '../utils/colors';
import { isColumnStackNode, isElementTypeNode, isInstanceNode, isProjectNode } from '../utils/graphEngine';
import { Structural3DControls } from './Structural3DControls';

interface Structural3DViewerProps {
  nodes: BimNode[];
  /** IFC file of the head model revision; null shows the empty state */
  modelUrl: string | null;
  /** diff elements the head model lacks, drawn from the revision that has them */
  ghostSources: { url: string; gids: string[] }[];
  selectedNodeId: string | null;
  selectedNodeIds: Set<string>;
  activeLoadChainNodeIds: Set<string>;
  matchingNodeIds: Set<string>;
  isFilterActive: boolean;
  colorMode: ColorMode;
  diffMode: boolean;
  overlay: HighlightOverlay | null;
  fitTrigger: number;
  resetTrigger: number;
  emptyText?: React.ReactNode;
  onSelectNode: (id: string, opts?: { toggleMulti?: boolean }) => void;
}

const UNMAPPED_MESH = '#6b7280';

export const Structural3DViewer: React.FC<Structural3DViewerProps> = ({
  nodes,
  modelUrl,
  ghostSources,
  selectedNodeId,
  selectedNodeIds,
  activeLoadChainNodeIds,
  matchingNodeIds,
  isFilterActive,
  colorMode,
  diffMode,
  overlay,
  fitTrigger,
  resetTrigger,
  emptyText,
  onSelectNode,
}) => {
  const host = useRef<HTMLDivElement | null>(null);
  const viewer = useRef<IfcViewer | null>(null);
  const [progress, setProgress] = useState<{ text: string; pct: number } | null>(null);
  const [error, setError] = useState('');
  const [loadedUrl, setLoadedUrl] = useState<string | null>(null);
  const [ghostVersion, setGhostVersion] = useState(0);
  const onSelectRef = useRef(onSelectNode);
  onSelectRef.current = onSelectNode;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 320;
    const height = container.clientHeight || 220;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x2d3139);
    scene.fog = new THREE.FogExp2(0x2d3139, 0.00038);

    const camera = new THREE.PerspectiveCamera(40, width / height, 1.0, 4500);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setClearColor(0x2d3139, 1);
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.18;
    container.appendChild(renderer.domElement);

    const hemiLight = new THREE.HemisphereLight(0xf8fafc, 0x2f333a, 0.85);
    scene.add(hemiLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.15);
    keyLight.position.set(45, 90, 55);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0xbae6fd, 0.65);
    rimLight.position.set(-55, 40, -45);
    scene.add(rimLight);

    const gridHelper = new THREE.GridHelper(240, 8, 0x565e6e, 0x383d47);
    gridHelper.position.y = -0.05;
    scene.add(gridHelper);

    const rootGroup = new THREE.Group();
    scene.add(rootGroup);

    const st = stateRef.current;
    st.scene = scene;
    st.camera = camera;
    st.renderer = renderer;
    st.rootGroup = rootGroup;

    const raycaster = new THREE.Raycaster();
    const mouseNDC = new THREE.Vector2();
    const controls = new Structural3DControls(camera, container, DEFAULT_3D_CAM,
      () => { st.needsRender = true; },
      (event) => {
        const rect = container.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) return;
        mouseNDC.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        mouseNDC.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(mouseNDC, camera);
        const hits = raycaster.intersectObjects(Array.from(st.meshMap.values()), false);
        if (hits.length > 0 && hits[0].object.userData.nodeId) {
          onSelectRef.current(hits[0].object.userData.nodeId, { toggleMulti: event.shiftKey });
        }
      },
    });
    viewer.current = v;
    return () => {
      v.dispose();
      viewer.current = null;
    };
  }, []);

  // load the head model. Every URL change starts from a clean slate (no progress, error or loaded
  // model); a load that is superseded (new URL, null URL, unmount) is invalidated inside IfcViewer,
  // paints nothing and resolves false, so only the current load may report back.
  useEffect(() => {
    const st = stateRef.current;
    const rootGroup = st.rootGroup;
    if (!rootGroup) return;

    while (rootGroup.children.length > 0) {
      rootGroup.remove(rootGroup.children[0]);
    }
    st.meshMap.clear();

    const instances = nodes.filter(isInstanceNode);
    const geomCache = new Map<string, { geom: THREE.BufferGeometry; edges: THREE.EdgesGeometry }>();
    const catCounters: Record<string, number> = {};

    instances.forEach((node) => {
      const catKey = node.parent || 'default';
      const idx = catCounters[catKey] || 0;
      catCounters[catKey] = idx + 1;

      const spec = getStructural3DSpec(node, idx);
      const geomKey = `${spec.shape}:${spec.size[0]}:${spec.size[1]}:${spec.size[2]}`;
      let cached = geomCache.get(geomKey);
      if (!cached) {
        let g: THREE.BufferGeometry;
        if (spec.shape === 'cylinder') {
          g = new THREE.CylinderGeometry(spec.size[0], spec.size[2], spec.size[1], 14);
        } else if (spec.shape === 'joint') {
          g = new THREE.OctahedronGeometry(spec.size[0] * 0.62, 1);
        } else {
          g = new THREE.BoxGeometry(spec.size[0], spec.size[1], spec.size[2]);
        }
        cached = { geom: g, edges: new THREE.EdgesGeometry(g) };
        geomCache.set(geomKey, cached);
      }

      const resolvedHex = getGraphNodeColor(node, false);
      const baseColor = new THREE.Color(resolvedHex);
      const isSlab = node.parent === 'cat-slab' || (node.ifcType || '').toUpperCase() === 'IFCSLAB';

      const mat = new THREE.MeshStandardMaterial({
        color: baseColor,
        emissive: baseColor,
        emissiveIntensity: isSlab ? 0.12 : 0.22,
        roughness: 0.28,
        metalness: 0.35,
        transparent: isSlab,
        depthWrite: !isSlab,
        opacity: isSlab ? 0.26 : 1.0,
      });

      const mesh = new THREE.Mesh(cached.geom, mat);
      mesh.position.set(spec.pos[0], spec.pos[1], spec.pos[2]);
      mesh.renderOrder = isSlab ? 1 : 2;

      const lineMat = new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: isSlab ? 0.55 : 0.85,
      });
      const wireframe = new THREE.LineSegments(cached.edges, lineMat);
      mesh.add(wireframe);

      mesh.userData = { nodeId: node.id, node, isSlab, wireframe };
      rootGroup.add(mesh);
      st.meshMap.set(node.id, mesh);
    });

    st.needsRender = true;
  }, [nodes]);

  // Update 3D highlights on selection / filter / heatmap changes
  useEffect(() => {
    const st = stateRef.current;
    st.needsRender = true;
    if (st.meshMap.size === 0) return;

    if (!selectedNodeId) {
      st.meshMap.forEach((mesh, id) => {
        const mat = mesh.material as THREE.MeshStandardMaterial;
        const wf = mesh.userData.wireframe as THREE.LineSegments;
        const wfMat = wf.material as THREE.LineBasicMaterial;
        const nodeObj = mesh.userData.node as BimNode;
        const activeColor = new THREE.Color(getGraphNodeColor(nodeObj, heatmapMode, diffMode));
        const diffStatus = diffMode ? nodeObj.diffStatus : undefined;
        const matchesFilter = !isFilterActive || matchingNodeIds.has(id);
        const isSlab = mesh.userData.isSlab;

        if (matchesFilter) {
          const isUnchangedDiff = diffStatus === 'unchanged';
          const isRemovedDiff = diffStatus === 'removed';
          mat.transparent = isSlab || isUnchangedDiff || isRemovedDiff;
          mat.depthWrite = !(isSlab || isUnchangedDiff);
          mesh.renderOrder = isSlab ? 1 : isUnchangedDiff ? 0 : 2;
          mat.color.copy(activeColor);
          mat.emissive.copy(activeColor);
          mat.emissiveIntensity = diffStatus
            ? isUnchangedDiff
              ? 0.06
              : 0.65
            : heatmapMode
            ? isSlab
              ? 0.24
              : 0.52
            : isSlab
            ? 0.12
            : 0.22;
          mat.opacity = diffStatus
            ? isUnchangedDiff
              ? 0.11
              : isRemovedDiff
              ? 0.45
              : isSlab
              ? 0.42
              : 1.0
            : heatmapMode
            ? isSlab
              ? 0.3
              : 1.0
            : isSlab
            ? 0.26
            : 1.0;
          mat.needsUpdate = true;
          wfMat.color.setHex(isRemovedDiff ? 0xfca5a5 : 0xffffff);
          wfMat.opacity = isUnchangedDiff ? 0.18 : isSlab ? 0.55 : 0.9;
        } else {
          mat.transparent = true;
          mat.depthWrite = false;
          mesh.renderOrder = 0;
          mat.color.copy(activeColor);
          mat.emissive.copy(activeColor);
          mat.emissiveIntensity = 0.04;
          mat.opacity = 0.15;
          mat.needsUpdate = true;
          wfMat.color.setHex(0x94a3b8);
          wfMat.opacity = 0.22;
        }
      });
      return;
    }
    let dead = false;
    v.load(modelUrl, (text, pct) => !dead && setProgress(pct >= 100 ? null : { text, pct }))
      .then((done) => {
        if (!dead && done) setLoadedUrl(modelUrl);
      })
      .catch((e: unknown) => {
        if (dead) return;
        setProgress(null);
        setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      dead = true;
    };
  }, [modelUrl]);

  // ghosts (diff elements from the other revision), once the head model of THIS modelUrl has loaded
  // so they share its offset (on a swap, loadedUrl is still the previous model's until the new one
  // finishes); the cleanup cancels a ghost load still streaming, so it never paints into a later scene
  const ghostKey = JSON.stringify(ghostSources);
  useEffect(() => {
    const v = viewer.current;
    if (!v || !modelUrl || loadedUrl !== modelUrl) return;
    let dead = false;
    v.loadGhosts(modelUrl, ghostSources)
      .then((done) => !dead && done && setGhostVersion((n) => n + 1))
      .catch(() => {
        /* a missing ghost revision only loses the ghosts, never the model */
      });
    return () => {
      dead = true;
      v.cancelGhosts();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ghostKey, loadedUrl, modelUrl]);

  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  // element-graph boxes for every element the IFC (and its ghosts) did not mesh: the whole model
  // when there is no IFC (ModelInput / legacy JSON), else only stragglers such as legacy diff ghosts
  const [boxVersion, setBoxVersion] = useState(0);
  const [boxCount, setBoxCount] = useState(0);
  const boxKey = useMemo(
    () =>
      nodes
        .filter((n) => n.kind === 'element' && n.bbox)
        .map((n) => n.id)
        .join('|'),
    [nodes],
  );
  useEffect(() => {
    const v = viewer.current;
    if (!v) return;
    if (modelUrl && !loadedUrl) return; // wait for the IFC: it decides what still needs a box
    v.clearBoxes();
    const boxes = nodes
      .filter((n) => n.kind === 'element' && n.bbox && !v.meshes.has(n.id))
      .map((n) => ({ gid: n.id, min: n.bbox!.min, max: n.bbox!.max }));
    v.setBoxes(boxes, !modelUrl);
    setBoxCount(boxes.length);
    setBoxVersion((x) => x + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boxKey, modelUrl, loadedUrl, ghostVersion]);
  const hasGeometry = Boolean(modelUrl) || boxCount > 0;

  // the set an active selection lights up: selected elements, everything under a selected
  // category / family / project, and the traced load path
  const litIds = useMemo(() => {
    const ids = new Set<string>(activeLoadChainNodeIds);
    const sel = selectedNodeIds.size > 0 ? selectedNodeIds : selectedNodeId ? new Set([selectedNodeId]) : new Set<string>();
    sel.forEach((id) => elementIdsUnder(id, nodes).forEach((e) => ids.add(e)));
    return { ids, primary: sel, any: sel.size > 0 };
  }, [nodes, selectedNodeId, selectedNodeIds, activeLoadChainNodeIds]);

  // restyle every mesh
  useEffect(() => {
    const v = viewer.current;
    if (!v || (!loadedUrl && boxCount === 0)) return;
    for (const gid of v.meshes.keys()) {
      const node = nodeById.get(gid);
      const isGhost = v.ghostIds.has(gid);
      const s: MeshStyle = { color: UNMAPPED_MESH, opacity: 0.22, visible: true, glow: null };
      if (node) {
        s.color = getEffectiveNodeColor(node, colorMode, diffMode);
        s.opacity = node.elementKind === 'slab' ? 0.32 : 1;
      }
    });

    st.meshMap.forEach((mesh, id) => {
      const mat = mesh.material as THREE.MeshStandardMaterial;
      const wf = mesh.userData.wireframe as THREE.LineSegments;
      const wfMat = wf.material as THREE.LineBasicMaterial;
      const isPrimary = selectedSet.has(id);
      const isLit = litIds.has(id);
      const isSlab = mesh.userData.isSlab;
      const nodeObj = mesh.userData.node as BimNode;
      const activeColor = new THREE.Color(getGraphNodeColor(nodeObj, heatmapMode, diffMode));

      if (isPrimary) {
        mat.transparent = false;
        mat.depthWrite = true;
        mesh.renderOrder = 3;
        mat.color.copy(activeColor);
        mat.emissive.copy(activeColor);
        mat.emissiveIntensity = 1.15;
        mat.opacity = 1.0;
        mat.needsUpdate = true;
        wfMat.color.setHex(0xffffff);
        wfMat.opacity = 1.0;
      } else if (isLit) {
        mat.transparent = isSlab;
        mat.depthWrite = !isSlab;
        mesh.renderOrder = isSlab ? 1 : 2;
        mat.color.copy(activeColor);
        mat.emissive.copy(activeColor);
        mat.emissiveIntensity = isSlab ? 0.3 : 0.55;
        mat.opacity = isSlab ? 0.42 : 1.0;
        mat.needsUpdate = true;
        wfMat.color.setHex(0xffffff);
        wfMat.opacity = isSlab ? 0.75 : 0.95;
      } else {
        mat.transparent = true;
        mat.depthWrite = false;
        mesh.renderOrder = 0;
        mat.color.copy(activeColor);
        mat.emissive.copy(activeColor);
        mat.emissiveIntensity = 0.04;
        mat.opacity = 0.15;
        mat.needsUpdate = true;
        wfMat.color.setHex(0x94a3b8);
        wfMat.opacity = 0.18;
      }
      if (isGhost && !diffMode) s.visible = false;

      if (overlay) {
        const tone = overlay.tones.get(gid);
        if (tone) {
          s.color = TONE_COLORS[tone];
          s.opacity = 1;
          s.glow = tone === 'origin' ? '#6366f1' : TONE_COLORS[tone];
        } else {
          s.opacity = Math.min(s.opacity, 0.07);
          s.glow = null;
        }
      } else if (litIds.any) {
        if (litIds.primary.has(gid)) {
          s.color = '#ffffff';
          s.opacity = 1;
          s.glow = '#6366f1';
        } else if (litIds.ids.has(gid)) {
          s.opacity = Math.max(s.opacity, node?.elementKind === 'slab' ? 0.42 : 1);
          s.glow = '#bef264';
        } else {
          s.opacity = Math.min(s.opacity, 0.06);
          s.glow = null;
        }
      } else if (isFilterActive && !matchingNodeIds.has(gid)) {
        s.opacity = Math.min(s.opacity, 0.07);
        s.glow = null;
      }
      v.style(gid, s);
    }
  }, [loadedUrl, ghostVersion, boxVersion, boxCount, nodeById, colorMode, diffMode, overlay, litIds, isFilterActive, matchingNodeIds]);

  // zoom to the selection (or the whole model)
  const selRef = useRef({ selectedNodeId, litIds });
  selRef.current = { selectedNodeId, litIds };
  useEffect(() => {
    const v = viewer.current;
    if (!v || fitTrigger === 0) return;
    const { litIds: lit } = selRef.current;
    if (!lit.any) {
      v.fit(true);
      return;
    }
    const targets = [...lit.primary].flatMap((id) => elementIdsUnder(id, nodes));
    if (targets.length) v.focusMany(targets);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitTrigger]);

  useEffect(() => {
    if (resetTrigger > 0) viewer.current?.fit(true);
  }, [resetTrigger]);

  return (
    <div className="relative w-full h-full bg-[#282c34] overflow-hidden">
      <div ref={host} style={{ touchAction: 'none' }} className="absolute inset-0 cursor-grab active:cursor-grabbing" aria-label="3D model view" role="img" />
      {!hasGeometry && (
        <div className="absolute inset-0 grid place-items-center p-6 text-center pointer-events-none">
          <div className="flex flex-col items-center gap-2 max-w-xs">
            <div className="w-9 h-9 rounded-xl bg-white/[0.04] border border-white/[0.08] text-zinc-500 flex items-center justify-center">
              <Box className="w-4 h-4" />
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">{emptyText ?? 'No model loaded.'}</p>
          </div>
        </div>
      )}
      {progress && (
        <div role="status" className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 mono text-[10px] text-zinc-200 bg-[#2d3139]/92 backdrop-blur-xl border border-white/[0.14] rounded-xl px-3 py-2 flex items-center gap-2 shadow-[0_12px_32px_rgba(0,0,0,0.8)]">
          <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-300" />
          {progress.text} <span className="text-zinc-500">{Math.round(progress.pct)}%</span>
        </div>
      )}
      {error && (
        <div role="alert" className="absolute left-3 right-3 top-3 text-[11px] text-rose-200 bg-rose-500/15 border border-rose-400/35 rounded-lg px-2.5 py-1.5">
          Could not load the model geometry: {error}
        </div>
      )}
    </div>
  );
};
