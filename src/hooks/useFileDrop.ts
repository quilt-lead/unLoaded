import { useEffect, useRef, useState } from 'react';

export type DropSlot = 'base' | 'compare';

/** Attribute that marks an element as a drop target for a given slot. */
export const DROP_SLOT_ATTR = 'data-drop-slot';

const carriesFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files');

const slotAt = (target: EventTarget | null): DropSlot | null => {
  const el = target instanceof Element ? target.closest(`[${DROP_SLOT_ATTR}]`) : null;
  const slot = el?.getAttribute(DROP_SLOT_ATTR);
  return slot === 'base' || slot === 'compare' ? slot : null;
};

/**
 * Window-level OS file drag & drop. Listening on window (rather than one canvas)
 * means a drop over the docked/floating HUD panels still imports instead of the
 * browser navigating to the file. Only drags that carry files are handled, so
 * in-app pointer drags (nodes, panels) are unaffected.
 *
 * The slot is taken from the nearest `data-drop-slot` ancestor of the drop target;
 * anywhere else falls back to `defaultSlot`.
 */
export function useFileDrop(onDropFiles: (files: File[], slot: DropSlot) => void, defaultSlot: DropSlot = 'base') {
  const [isDragging, setIsDragging] = useState(false);
  const [hoverSlot, setHoverSlot] = useState<DropSlot | null>(null);

  // Keep the latest callback without re-binding listeners on every render.
  const handlerRef = useRef(onDropFiles);
  handlerRef.current = onDropFiles;
  const defaultSlotRef = useRef(defaultSlot);
  defaultSlotRef.current = defaultSlot;

  useEffect(() => {
    // dragenter/dragleave fire for every child element crossed; count depth so
    // the overlay only hides when the drag truly leaves the window.
    let depth = 0;
    const reset = () => {
      depth = 0;
      setIsDragging(false);
      setHoverSlot(null);
    };

    const onEnter = (e: DragEvent) => {
      if (!carriesFiles(e)) return;
      e.preventDefault();
      depth += 1;
      setIsDragging(true);
    };
    const onOver = (e: DragEvent) => {
      if (!carriesFiles(e)) return;
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
      setHoverSlot(slotAt(e.target));
    };
    const onLeave = (e: DragEvent) => {
      if (!carriesFiles(e)) return;
      depth = Math.max(0, depth - 1);
      if (depth === 0) reset();
    };
    const onDrop = (e: DragEvent) => {
      if (!carriesFiles(e)) return;
      e.preventDefault();
      const files = Array.from(e.dataTransfer?.files ?? []);
      const slot = slotAt(e.target) ?? defaultSlotRef.current;
      reset();
      if (files.length > 0) handlerRef.current(files, slot);
    };

    window.addEventListener('dragenter', onEnter);
    window.addEventListener('dragover', onOver);
    window.addEventListener('dragleave', onLeave);
    window.addEventListener('drop', onDrop);
    window.addEventListener('blur', reset);
    return () => {
      window.removeEventListener('dragenter', onEnter);
      window.removeEventListener('dragover', onOver);
      window.removeEventListener('dragleave', onLeave);
      window.removeEventListener('drop', onDrop);
      window.removeEventListener('blur', reset);
    };
  }, []);

  return { isDragging, hoverSlot };
}
