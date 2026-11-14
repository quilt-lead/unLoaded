import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type ReactNode } from "react";
import { Viewer } from "../viewer";
import { InfoTip } from "../help/InfoTip";
import type { HelpId } from "../help/registry";

export interface MemberStyle {
  color: string;
  /** 0..1, default 1 */
  opacity?: number;
  /** default true */
  visible?: boolean;
}

export interface Viewer3DProps {
  /** IFC file URL; null shows the empty state */
  url: string | null;
  /** cache key for the loaded model (a revision id); a change of url or rev reloads */
  rev?: number | string;
  /** false keeps the IFC's own coordinates (needed when the page adds content in building coordinates) */
  toOrigin?: boolean;
  info: HelpId;
  /** colour / opacity / visibility per IFC GlobalId; unstyled members keep the default grey */
  styleOf?: (gid: string) => MemberStyle | undefined;
  /** selected GlobalId (drawn in the selection colour) */
  selected?: string | null;
  /** click on a member (null = click on empty space); drags do not count as clicks */
  onPick?: (gid: string | null, ev: MouseEvent) => void;
  /** called once per loaded model with the underlying Viewer, for page-added content (viewer.extra) */
  onLoaded?: (viewer: Viewer) => void;
  /** overlays drawn over the canvas (legend, tools) */
  children?: ReactNode;
  emptyText?: ReactNode;
  className?: string;
}

export interface Viewer3DHandle {
  fit: () => void;
  focus: (gid: string) => void;
  viewer: () => Viewer | null;
}

/**
 * React wrapper around the existing three.js + web-ifc Viewer class (src/viewer.ts) by composition:
 * the class keeps its pick and resize behaviour; this component owns its lifecycle (create on mount,
 * dispose on unmount), loading, restyling and click-vs-drag picking.
 */
export const Viewer3D = forwardRef<Viewer3DHandle, Viewer3DProps>(function Viewer3D(
  { url, rev, toOrigin = true, info, styleOf, selected, onPick, onLoaded, children, emptyText, className },
  ref,
) {
  const host = useRef<HTMLDivElement>(null);
  const v = useRef<Viewer | null>(null);
  const [progress, setProgress] = useState<{ text: string; pct: number } | null>(null);
  const [err, setErr] = useState("");
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const cb = useRef({ onPick, onLoaded });
  cb.current = { onPick, onLoaded };

  useEffect(() => {
    const viewer = new Viewer(host.current!);
    v.current = viewer;
    const el = viewer.renderer.domElement;
    let down: { x: number; y: number } | null = null;
    const onDown = (e: PointerEvent) => (down = { x: e.clientX, y: e.clientY });
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4 || e.button !== 0) return (down = null);
      down = null;
      cb.current.onPick?.(viewer.pick(e), e);
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointerup", onUp);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointerup", onUp);
      viewer.dispose();
      v.current = null;
    };
  }, []);

  const key = url ? `${url}|${rev ?? ""}|${toOrigin}` : null;
  useEffect(() => {
    const viewer = v.current;
    if (!viewer || !url || !key) {
      viewer?.clear();
      setLoadedKey(null);
      return;
    }
    let dead = false;
    setErr("");
    setLoadedKey(null);
    viewer
      .load(url, typeof rev === "number" ? rev : 0, (text, pct) => !dead && setProgress(pct >= 100 ? null : { text, pct }), toOrigin)
      .then(() => {
        if (dead) return;
        setLoadedKey(key);
        cb.current.onLoaded?.(viewer);
      })
      .catch((e: unknown) => {
        if (dead) return;
        setProgress(null);
        setErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      dead = true;
    };
  }, [key, url, rev, toOrigin]);

  // restyle every member when the style function, the selection or the model changes
  useEffect(() => {
    const viewer = v.current;
    if (!viewer || !loadedKey) return;
    for (const gid of viewer.meshes.keys()) {
      const st = styleOf?.(gid);
      viewer.style(gid, st?.color ?? "#c3cad3", st?.opacity ?? 1, st?.visible ?? true, gid === selected);
    }
  }, [styleOf, selected, loadedKey]);

  useImperativeHandle(ref, () => ({
    fit: () => v.current?.fit(),
    focus: (gid: string) => v.current?.focus(gid),
    viewer: () => v.current,
  }));

  return (
    <div className={`cg-3d${className ? " " + className : ""}`}>
      <div ref={host} className="cg-3d-canvas" aria-label="3D model view" role="img" />
      <div className="cg-3d-info">
        <InfoTip id={info} />
      </div>
      {!url && <div className="cg-3d-empty">{emptyText ?? "No model loaded."}</div>}
      {progress && (
        <div className="cg-3d-progress" role="status">
          {progress.text} <span className="mono">{Math.round(progress.pct)}%</span>
        </div>
      )}
      {err && (
        <div className="cg-3d-progress bad" role="alert">
          Could not load the model: {err}
        </div>
      )}
      {children}
    </div>
  );
});
