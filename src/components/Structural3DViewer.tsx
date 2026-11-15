import React, { useCallback, useEffect, useRef } from 'react';
import * as THREE from 'three';
import { BimNode } from '../types/bim';
import { DIFF_PALETTE, getEffectiveNodeColor, getHeatmapColor } from '../utils/colors';
import { isColumnStackNode, isElementTypeNode, isInstanceNode, isProjectNode } from '../utils/graphEngine';

interface Structural3DViewerProps {
  nodes: BimNode[];
  selectedNodeId: string | null;
  selectedNodeIds: Set<string>;
  activeLoadChainNodeIds: Set<string>;
  matchingNodeIds: Set<string>;
  isFilterActive: boolean;
  heatmapMode: boolean;
  diffMode?: boolean;
  fitTrigger: number;
  resetTrigger: number;
  onSelectNode: (id: string, opts?: { toggleMulti?: boolean }) => void;
}

const DEFAULT_3D_CAM = {
  theta: 0.76,
  phi: 1.08,
  radius: 335.0,
  target: { x: 0.0, y: 78.0, z: 0.0 },
};

function getStructural3DSpec(node: BimNode, indexInCat: number) {
  if (Array.isArray(node.pos3d) && Array.isArray(node.size3d)) {
    return {
      pos: node.pos3d,
      size: node.size3d,
      shape: node.shape3d || 'box',
    };
  }
  const parent = `${node.parent || ''} ${node.ifcType || ''}`.toLowerCase();
  const label = (node.label || '').toLowerCase();
  const angle = indexInCat * 1.15;
  const r = 14.0 + (indexInCat % 4) * 6.0;

  if (parent.includes('slab') || parent.includes('roof') || parent.includes('covering') || label.includes('slab')) {
    return { pos: [0, 12.0 + indexInCat * 12.0, 0] as [number, number, number], size: [48.0, 0.8, 48.0] as [number, number, number], shape: 'box' as const };
  }
  if (parent.includes('beam') || parent.includes('member') || label.includes('beam')) {
    return {
      pos: [Math.cos(angle) * r, 12.0 + (indexInCat % 6) * 12.0, Math.sin(angle) * r] as [number, number, number],
      size: [18.0, 1.4, 1.0] as [number, number, number],
      shape: 'box' as const,
    };
  }
  if (parent.includes('conn') || parent.includes('fastener') || parent.includes('plate') || label.includes('conn')) {
    return {
      pos: [Math.cos(angle) * r, 12.0 + (indexInCat % 6) * 12.0, Math.sin(angle) * r] as [number, number, number],
      size: [2.2, 1.2, 2.2] as [number, number, number],
      shape: 'joint' as const,
    };
  }
  if (parent.includes('pile') || label.includes('pile')) {
    return {
      pos: [Math.cos(angle) * r, -12.0, Math.sin(angle) * r] as [number, number, number],
      size: [1.8, 22.0, 1.8] as [number, number, number],
      shape: 'cylinder' as const,
    };
  }
  if (parent.includes('mat') || parent.includes('pcap') || parent.includes('footing') || label.includes('cap') || label.includes('mat')) {
    return {
      pos: [Math.cos(angle) * r, -2.5, Math.sin(angle) * r] as [number, number, number],
      size: [9.0, 4.5, 9.0] as [number, number, number],
      shape: 'box' as const,
    };
  }
  if (parent.includes('wall') || parent.includes('curtain') || label.includes('wall')) {
    return {
      pos: [Math.cos(angle) * r, 6.0 + (indexInCat % 6) * 12.0, Math.sin(angle) * r] as [number, number, number],
      size: [16.0, 11.5, 1.2] as [number, number, number],
      shape: 'box' as const,
    };
  }
  if (parent.includes('window') || parent.includes('door') || parent.includes('opening')) {
    return {
      pos: [Math.cos(angle) * r, 5.0 + (indexInCat % 6) * 12.0, Math.sin(angle) * r] as [number, number, number],
      size: [4.5, 7.5, 0.6] as [number, number, number],
      shape: 'box' as const,
    };
  }
  return {
    pos: [Math.cos(angle) * r, 6.0 + (indexInCat % 6) * 12.0, Math.sin(angle) * r] as [number, number, number],
    size: [2.2, 12.0, 2.2] as [number, number, number],
    shape: 'box' as const,
  };
}

export const Structural3DViewer: React.FC<Structural3DViewerProps> = ({
  nodes,
  selectedNodeId,
  selectedNodeIds,
  activeLoadChainNodeIds,
  matchingNodeIds,
  isFilterActive,
  heatmapMode,
  diffMode = false,
  fitTrigger,
  resetTrigger,
  onSelectNode,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef<{
    scene: THREE.Scene | null;
    camera: THREE.PerspectiveCamera | null;
    renderer: THREE.WebGLRenderer | null;
    rootGroup: THREE.Group | null;
    meshMap: Map<string, THREE.Mesh>;
    theta: number;
    phi: number;
    radius: number;
    target: { x: number; y: number; z: number };
    targetTheta: number;
    targetPhi: number;
    targetRadius: number;
    targetLookAt: { x: number; y: number; z: number };
    isDragging: boolean;
    dragButton: number;
    dragMoved: boolean;
    navMode: 'orbit' | 'pan' | 'zoom';
    prevMouse: { x: number; y: number };
    needsRender: boolean;
  }>({
    scene: null,
    camera: null,
    renderer: null,
    rootGroup: null,
    meshMap: new Map(),
    theta: DEFAULT_3D_CAM.theta,
    phi: DEFAULT_3D_CAM.phi,
    radius: DEFAULT_3D_CAM.radius,
    target: { ...DEFAULT_3D_CAM.target },
    targetTheta: DEFAULT_3D_CAM.theta,
    targetPhi: DEFAULT_3D_CAM.phi,
    targetRadius: DEFAULT_3D_CAM.radius,
    targetLookAt: { ...DEFAULT_3D_CAM.target },
    isDragging: false,
    dragButton: 0,
    dragMoved: false,
    navMode: 'orbit',
    prevMouse: { x: 0, y: 0 },
    needsRender: true,
  });

  const onSelectRef = useRef(onSelectNode);
  onSelectRef.current = onSelectNode;

  // Initialize Three.js WebGL scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 320;
    const height = container.clientHeight || 220;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x2a2e36);
    scene.fog = new THREE.FogExp2(0x2a2e36, 0.00038);

    const camera = new THREE.PerspectiveCamera(40, width / height, 1.0, 4500);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setClearColor(0x2a2e36, 1);
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

    const updateCamPos = () => {
      camera.position.x = st.target.x + st.radius * Math.sin(st.phi) * Math.sin(st.theta);
      camera.position.y = st.target.y + st.radius * Math.cos(st.phi);
      camera.position.z = st.target.z + st.radius * Math.sin(st.phi) * Math.cos(st.theta);
      camera.lookAt(st.target.x, st.target.y, st.target.z);
    };
    updateCamPos();

    const resizeObserver = new ResizeObserver(() => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w > 0 && h > 0) {
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        st.needsRender = true;
      }
    });
    resizeObserver.observe(container);

    let rafId = 0;
    const renderLoop = () => {
      const ease = 0.12;
      const dTheta = st.targetTheta - st.theta;
      const dPhi = st.targetPhi - st.phi;
      const dRadius = st.targetRadius - st.radius;
      const dTx = st.targetLookAt.x - st.target.x;
      const dTy = st.targetLookAt.y - st.target.y;
      const dTz = st.targetLookAt.z - st.target.z;

      const moving =
        Math.abs(dTheta) > 0.0002 ||
        Math.abs(dPhi) > 0.0002 ||
        Math.abs(dRadius) > 0.02 ||
        Math.abs(dTx) > 0.01 ||
        Math.abs(dTy) > 0.01 ||
        Math.abs(dTz) > 0.01;

      if (moving || st.needsRender) {
        st.needsRender = false;
        if (moving) {
          st.theta += dTheta * ease;
          st.phi += dPhi * ease;
          st.radius += dRadius * ease;
          st.target.x += dTx * ease;
          st.target.y += dTy * ease;
          st.target.z += dTz * ease;
          updateCamPos();
        }
        renderer.render(scene, camera);
      }
      rafId = requestAnimationFrame(renderLoop);
    };
    rafId = requestAnimationFrame(renderLoop);

    const raycaster = new THREE.Raycaster();
    const mouseNDC = new THREE.Vector2();

    const panByPixels = (dx: number, dy: number) => {
      const heightPx = Math.max(container.clientHeight || 300, 1);
      const fovRad = (camera.fov * Math.PI) / 180;
      const unitsPerPixel = (2 * st.targetRadius * Math.tan(fovRad * 0.5)) / heightPx;
      const forward = new THREE.Vector3();
      camera.getWorldDirection(forward);
      const right = new THREE.Vector3().crossVectors(forward, camera.up).normalize();
      const camUp = new THREE.Vector3().crossVectors(right, forward).normalize();

      st.targetLookAt.x += (-dx * right.x + dy * camUp.x) * unitsPerPixel;
      st.targetLookAt.y += (-dx * right.y + dy * camUp.y) * unitsPerPixel;
      st.targetLookAt.z += (-dx * right.z + dy * camUp.z) * unitsPerPixel;
    };

    const onPointerDown = (e: PointerEvent) => {
      e.stopPropagation();
      if (e.button === 1) e.preventDefault();
      st.isDragging = true;
      st.dragButton = e.button;
      st.dragMoved = false;
      st.prevMouse = { x: e.clientX, y: e.clientY };

      if (e.button === 1 || (e.shiftKey && e.button === 2)) {
        st.navMode = 'pan';
      } else if (e.ctrlKey && e.button === 2) {
        st.navMode = 'zoom';
      } else {
        st.navMode = 'orbit';
      }
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!st.isDragging) return;
      const dx = e.clientX - st.prevMouse.x;
      const dy = e.clientY - st.prevMouse.y;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) st.dragMoved = true;

      if (st.navMode === 'pan') {
        panByPixels(dx, dy);
      } else if (st.navMode === 'zoom') {
        st.targetRadius = Math.max(0.5, st.targetRadius * Math.exp(dy * 0.008));
      } else {
        st.targetTheta -= dx * 0.012;
        st.targetPhi = Math.max(0.22, Math.min(Math.PI * 0.48, st.targetPhi - dy * 0.012));
      }
      st.prevMouse = { x: e.clientX, y: e.clientY };
    };

    const onPointerUp = (e: PointerEvent) => {
      if (!st.isDragging) return;
      const wasLeftClick = !st.dragMoved && st.dragButton === 0;
      st.isDragging = false;

      if (wasLeftClick) {
        const rect = container.getBoundingClientRect();
        if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
          mouseNDC.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
          mouseNDC.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
          raycaster.setFromCamera(mouseNDC, camera);
          const meshes = Array.from(st.meshMap.values());
          const hits = raycaster.intersectObjects(meshes, false);
          if (hits.length > 0 && hits[0].object.userData.nodeId) {
            onSelectRef.current(hits[0].object.userData.nodeId, { toggleMulti: e.shiftKey });
          }
        }
      }
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.shiftKey) {
        panByPixels(-e.deltaX || -e.deltaY, 0);
      } else {
        const mult = e.deltaMode === 1 ? 16 : 1;
        st.targetRadius = Math.max(0.5, st.targetRadius * Math.exp(e.deltaY * mult * 0.0014));
      }
    };

    const onContext = (e: MouseEvent) => e.preventDefault();

    container.addEventListener('contextmenu', onContext);
    container.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    container.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      container.removeEventListener('contextmenu', onContext);
      container.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      container.removeEventListener('wheel', onWheel);
      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  // Build 3D structural meshes whenever nodes change
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

      const resolvedHex = getEffectiveNodeColor(node, false);
      const baseColor = new THREE.Color(resolvedHex);
      const heatColor = new THREE.Color(getHeatmapColor(node.utilization));
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

      mesh.userData = { nodeId: node.id, node, baseColor, heatColor, isSlab, wireframe };
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
        const diffStatus = diffMode ? nodeObj.diffStatus : undefined;
        const activeColor = diffStatus
          ? new THREE.Color(DIFF_PALETTE[diffStatus])
          : heatmapMode
          ? mesh.userData.heatColor
          : mesh.userData.baseColor;
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
          mat.color.setHex(0x3b404b);
          mat.emissive.setHex(0x24272d);
          mat.emissiveIntensity = 0.04;
          mat.opacity = 0.07;
          mat.needsUpdate = true;
          wfMat.color.setHex(0x94a3b8);
          wfMat.opacity = 0.22;
        }
      });
      return;
    }

    const selectedSet = selectedNodeIds.size > 0 ? selectedNodeIds : new Set([selectedNodeId]);
    const litIds = new Set<string>(activeLoadChainNodeIds);

    selectedSet.forEach((sid) => {
      const sNode = nodes.find((n) => n.id === sid);
      if (!sNode) return;
      if (isProjectNode(sNode)) {
        st.meshMap.forEach((_, id) => litIds.add(id));
      } else if (isElementTypeNode(sNode)) {
        nodes.filter(isInstanceNode).forEach((inst) => {
          if (inst.parent === sid || inst.categoryParent === sid) litIds.add(inst.id);
        });
      } else if (isColumnStackNode(sNode)) {
        nodes.filter(isInstanceNode).forEach((inst) => {
          if (inst.parent === sid) litIds.add(inst.id);
        });
      } else {
        litIds.add(sid);
      }
    });

    st.meshMap.forEach((mesh, id) => {
      const mat = mesh.material as THREE.MeshStandardMaterial;
      const wf = mesh.userData.wireframe as THREE.LineSegments;
      const wfMat = wf.material as THREE.LineBasicMaterial;
      const isPrimary = selectedSet.has(id);
      const isLit = litIds.has(id);
      const isSlab = mesh.userData.isSlab;
      const heatOrBase = heatmapMode ? mesh.userData.heatColor : mesh.userData.baseColor;

      if (isPrimary) {
        mat.transparent = false;
        mat.depthWrite = true;
        mesh.renderOrder = 3;
        mat.color.setHex(0xffffff);
        mat.emissive.copy(heatOrBase);
        mat.emissiveIntensity = 1.15;
        mat.opacity = 1.0;
        mat.needsUpdate = true;
        wfMat.color.setHex(0xffffff);
        wfMat.opacity = 1.0;
      } else if (isLit) {
        mat.transparent = isSlab;
        mat.depthWrite = !isSlab;
        mesh.renderOrder = isSlab ? 1 : 2;
        mat.color.copy(heatOrBase);
        mat.emissive.copy(heatmapMode ? mesh.userData.heatColor : new THREE.Color(0xbef264));
        mat.emissiveIntensity = isSlab ? 0.42 : 0.85;
        mat.opacity = isSlab ? 0.42 : 1.0;
        mat.needsUpdate = true;
        wfMat.color.setHex(0xffffff);
        wfMat.opacity = isSlab ? 0.75 : 0.95;
      } else {
        mat.transparent = true;
        mat.depthWrite = false;
        mesh.renderOrder = 0;
        mat.color.setHex(0x3b404b);
        mat.emissive.setHex(0x24272d);
        mat.emissiveIntensity = 0.04;
        mat.opacity = 0.05;
        mat.needsUpdate = true;
        wfMat.color.setHex(0x94a3b8);
        wfMat.opacity = 0.18;
      }
    });
  }, [nodes, selectedNodeId, selectedNodeIds, activeLoadChainNodeIds, matchingNodeIds, isFilterActive, heatmapMode, diffMode]);

  const zoomFitToSelection = useCallback(() => {
    const st = stateRef.current;
    if (!st.camera || st.meshMap.size === 0) return;

    if (!selectedNodeId) {
      st.targetTheta = DEFAULT_3D_CAM.theta;
      st.targetPhi = DEFAULT_3D_CAM.phi;
      st.targetRadius = DEFAULT_3D_CAM.radius;
      st.targetLookAt = { ...DEFAULT_3D_CAM.target };
      return;
    }

    const selectedNode = nodes.find((n) => n.id === selectedNodeId);
    if (!selectedNode) return;

    const targetMeshes: THREE.Mesh[] = [];
    if (isProjectNode(selectedNode)) {
      st.meshMap.forEach((m) => targetMeshes.push(m));
    } else if (isElementTypeNode(selectedNode)) {
      nodes.filter(isInstanceNode).forEach((inst) => {
        if ((inst.parent === selectedNodeId || inst.categoryParent === selectedNodeId) && st.meshMap.has(inst.id)) {
          targetMeshes.push(st.meshMap.get(inst.id)!);
        }
      });
    } else if (isColumnStackNode(selectedNode)) {
      nodes.filter(isInstanceNode).forEach((inst) => {
        if (inst.parent === selectedNodeId && st.meshMap.has(inst.id)) {
          targetMeshes.push(st.meshMap.get(inst.id)!);
        }
      });
    } else {
      if (st.meshMap.has(selectedNodeId)) targetMeshes.push(st.meshMap.get(selectedNodeId)!);
      activeLoadChainNodeIds.forEach((cid) => {
        if (cid !== selectedNodeId && st.meshMap.has(cid)) {
          targetMeshes.push(st.meshMap.get(cid)!);
        }
      });
    }

    if (targetMeshes.length === 0) return;

    const box = new THREE.Box3();
    targetMeshes.forEach((m) => box.expandByObject(m));

    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);

    const primaryMesh = st.meshMap.get(selectedNodeId);
    if (primaryMesh && isInstanceNode(selectedNode)) {
      center.lerp(primaryMesh.position, 0.55);
    }

    const maxDim = Math.max(size.x, size.y, size.z, 24.0);
    const fovRad = (st.camera.fov * Math.PI) / 180;
    const aspect = st.camera.aspect || 1.25;
    const fitHeightDist = (maxDim * 0.62) / Math.tan(fovRad / 2);
    const fitWidthDist = fitHeightDist / Math.min(aspect, 1.2);
    const idealRadius = Math.max(45.0, Math.min(720.0, Math.max(fitHeightDist, fitWidthDist) * 1.18));

    st.targetLookAt = { x: center.x, y: center.y, z: center.z };
    st.targetRadius = idealRadius;
  }, [selectedNodeId, nodes, activeLoadChainNodeIds]);

  useEffect(() => {
    if (fitTrigger > 0) zoomFitToSelection();
  }, [fitTrigger, zoomFitToSelection]);

  useEffect(() => {
    if (resetTrigger > 0) {
      const st = stateRef.current;
      st.targetTheta = DEFAULT_3D_CAM.theta;
      st.targetPhi = DEFAULT_3D_CAM.phi;
      st.targetRadius = DEFAULT_3D_CAM.radius;
      st.targetLookAt = { ...DEFAULT_3D_CAM.target };
    }
  }, [resetTrigger]);

  return <div ref={containerRef} style={{ touchAction: 'none' }} className="w-full h-full cursor-grab active:cursor-grabbing" />;
};
