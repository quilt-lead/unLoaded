// The 3D model: real IFC geometry (web-ifc) of the head model revision, meshes keyed by GlobalId,
// coloured from the view model (type / review status / link confidence / utilisation when present),
// with impact and revision-diff overlays, selection sync and zoom-to-selection.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Loader2 } from 'lucide-react';
import type { BimNode, ColorMode, HighlightOverlay } from '../types/bim';
import { computeLitSet, elementEmphasis } from '../utils/elementEmphasis';
import { elementIdsUnder } from '../utils/graphEngine';
import { IfcViewer, type MeshStyle } from './three/ifcViewer';

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
    // navigation, click-vs-drag (3 px from pointerdown) and stopping pointer / wheel events from
    // reaching the panel behind are all Structural3DControls' (inside IfcViewer); a click picks
    const v: IfcViewer = new IfcViewer(host.current!, {
      onClick: (e) => {
        const gid = v.pick(e);
        if (gid) onSelectRef.current(gid, { toggleMulti: e.shiftKey });
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
    const v = viewer.current;
    if (!v) return;
    setProgress(null);
    setError('');
    setLoadedUrl(null);
    if (!modelUrl) {
      v.clear();
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
  // when there is no IFC (ModelInput / model bundle), else only stragglers such as diff ghosts
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
  const litIds = useMemo(
    () => computeLitSet(nodes, selectedNodeId, selectedNodeIds, activeLoadChainNodeIds),
    [nodes, selectedNodeId, selectedNodeIds, activeLoadChainNodeIds],
  );

  // restyle every mesh
  useEffect(() => {
    const v = viewer.current;
    if (!v || (!loadedUrl && boxCount === 0)) return;
    const ctx = { colorMode, diffMode, overlay, lit: litIds, isFilterActive, matchingNodeIds };
    for (const gid of v.meshes.keys()) {
      const { color, opacity, glow } = elementEmphasis(gid, nodeById.get(gid), ctx);
      const s: MeshStyle = { color, opacity, glow, visible: !(v.ghostIds.has(gid) && !diffMode) };
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
    <div className="relative w-full h-full bg-[#2d3139] overflow-hidden">
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
