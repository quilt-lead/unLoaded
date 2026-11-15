import React from 'react';
import { GitCompareArrows, Upload } from 'lucide-react';
import { DROP_SLOT_ATTR, DropSlot } from '../hooks/useFileDrop';

interface FileDropOverlayProps {
  visible: boolean;
  hoverSlot: DropSlot | null;
  /** A base model (DB A) is loaded, so the compare target is offered. */
  hasBaseModel: boolean;
  acceptedExtensions: string[];
}

interface ZoneProps {
  slot: DropSlot;
  active: boolean;
  eyebrow: string;
  title: string;
  detail: string;
}

const ZONE_TONE: Record<DropSlot, { idle: string; active: string; icon: string; eyebrow: string }> = {
  base: {
    idle: 'border-indigo-400/35 bg-[#2d3139]/80',
    active: 'border-indigo-300 bg-indigo-500/20',
    icon: 'text-indigo-300',
    eyebrow: 'text-indigo-300',
  },
  compare: {
    idle: 'border-amber-400/35 bg-[#2d3139]/80',
    active: 'border-amber-300 bg-amber-500/15',
    icon: 'text-amber-300',
    eyebrow: 'text-amber-300',
  },
};

const DropZone: React.FC<ZoneProps> = ({ slot, active, eyebrow, title, detail }) => {
  const tone = ZONE_TONE[slot];
  const Icon = slot === 'base' ? Upload : GitCompareArrows;
  return (
    <div
      {...{ [DROP_SLOT_ATTR]: slot }}
      className={`flex-1 min-w-0 rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-2 px-6 py-10 text-center transition-colors duration-100 motion-reduce:transition-none ${
        active ? tone.active : tone.idle
      }`}
    >
      <Icon className={`w-6 h-6 ${tone.icon}`} aria-hidden="true" />
      <p className={`mono text-[10px] uppercase tracking-widest ${tone.eyebrow}`}>{eyebrow}</p>
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="text-xs text-zinc-400 max-w-xs leading-relaxed">{detail}</p>
    </div>
  );
};

/**
 * Full-window target shown while an OS file is dragged over the app.
 * Drop handling lives in useFileDrop; this only renders the targets, tagged
 * with data-drop-slot so the hook can tell which one received the drop.
 */
export const FileDropOverlay: React.FC<FileDropOverlayProps> = ({
  visible,
  hoverSlot,
  hasBaseModel,
  acceptedExtensions,
}) => {
  const extList = acceptedExtensions.join(' / ');
  return (
    <>
      <div role="status" aria-live="polite" className="sr-only">
        {visible ? `Drop a ${extList} file to import it.` : ''}
      </div>
      {visible && (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-[70] overscroll-contain bg-[#1b1d22]/75 backdrop-blur-sm p-6 flex flex-col gap-4"
        >
          <div className="flex-1 flex flex-col sm:flex-row gap-4 min-h-0">
            {hasBaseModel ? (
              <>
                <DropZone
                  slot="base"
                  active={hoverSlot !== 'compare'}
                  eyebrow="Add to project"
                  title="Add as Newest Revision"
                  detail="A model or calc PDF becomes the newest revision of this project. A saved project file opens as its own project."
                />
                <DropZone
                  slot="compare"
                  active={hoverSlot === 'compare'}
                  eyebrow="Compare"
                  title="Compare With Current Model"
                  detail="Adds the model as a new revision and opens Diff Mode against the current one, across the graph, 3D model and PDFs."
                />
              </>
            ) : (
              <DropZone
                slot="base"
                active
                eyebrow="Open"
                title="Drop to Open"
                detail="An IFC or JSON model, a calc package PDF, or a saved project file."
              />
            )}
          </div>
          <p className="mono text-[10px] text-zinc-400 text-center uppercase tracking-wider">
            Accepts {extList} · one file at a time
          </p>
        </div>
      )}
    </>
  );
};
