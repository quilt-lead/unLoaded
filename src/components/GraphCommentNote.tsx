import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { MessageSquare } from 'lucide-react';
import type { GraphComment } from '../types/bim';

/** Comment width in graph units; the height follows the text. */
export const COMMENT_WIDTH = 200;
export const COMMENT_MIN_HEIGHT = 52;

interface GraphCommentNoteProps {
  comment: GraphComment;
  selected: boolean;
  primary: boolean;
  editing: boolean;
  onPointerDown: (e: React.PointerEvent, comment: GraphComment) => void;
  onStartEdit: (id: string) => void;
  /** commit the edited text; an empty text deletes the comment */
  onCommit: (id: string, text: string) => void;
  onCancelEdit: (id: string) => void;
  /** reports the rendered height so box selection and the foreignObject match the note */
  onMeasure: (id: string, height: number) => void;
}

/**
 * A sticky note on the graph workspace. It lives inside the camera transform, so it pans and zooms
 * with the nodes. Drag, select and box-select go through RadialGraphCanvas exactly as for nodes;
 * double-click (or Enter when focused) edits the text.
 */
export const GraphCommentNote: React.FC<GraphCommentNoteProps> = ({
  comment,
  selected,
  primary,
  editing,
  onPointerDown,
  onStartEdit,
  onCommit,
  onCancelEdit,
  onMeasure,
}) => {
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [height, setHeight] = useState(COMMENT_MIN_HEIGHT);
  const [draft, setDraft] = useState(comment.text);

  // offsetHeight is the untransformed layout size, i.e. graph units
  useLayoutEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const measure = () => {
      const h = Math.max(COMMENT_MIN_HEIGHT, el.offsetHeight);
      setHeight(h);
      onMeasure(comment.id, h);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [comment.id, onMeasure]);

  useEffect(() => {
    if (!editing) return;
    setDraft(comment.text);
    const ta = textareaRef.current;
    if (ta) {
      ta.focus();
      ta.setSelectionRange(ta.value.length, ta.value.length);
    }
    // only on entering edit mode
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  // grow the textarea with its content so the note never scrolls
  useLayoutEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = '0px';
    ta.style.height = `${ta.scrollHeight}px`;
  }, [draft, editing]);

  const outline = selected
    ? { outline: `1.75px dashed ${primary ? '#ffffff' : '#38bdf8'}`, outlineOffset: 4 }
    : undefined;

  return (
    <foreignObject x={comment.x} y={comment.y} width={COMMENT_WIDTH} height={height} style={{ overflow: 'visible' }}>
      <div
        ref={bodyRef}
        role="note"
        aria-label={comment.text ? `Comment: ${comment.text}` : 'Empty comment'}
        tabIndex={0}
        onPointerDown={(e) => {
          if (editing) {
            e.stopPropagation();
            return;
          }
          onPointerDown(e, comment);
        }}
        onDoubleClick={(e) => {
          e.stopPropagation();
          onStartEdit(comment.id);
        }}
        onKeyDown={(e) => {
          if (!editing && e.key === 'Enter') {
            e.preventDefault();
            e.stopPropagation();
            onStartEdit(comment.id);
          }
        }}
        style={outline}
        className={`group w-full rounded-lg border-l-[3px] border border-amber-300/35 border-l-amber-300 bg-[#33302a]/95 shadow-[0_8px_22px_rgba(0,0,0,0.55)] backdrop-blur-sm select-none focus-visible:ring-2 focus-visible:ring-amber-300/70 focus:outline-none ${
          editing ? 'cursor-text' : 'cursor-move'
        }`}
      >
        <div className="flex items-center gap-1.5 px-2.5 pt-1.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-amber-200/80 mono">
          <MessageSquare className="w-2.5 h-2.5" aria-hidden="true" />
          <span>Comment</span>
          {editing && <span className="ml-auto normal-case tracking-normal font-normal text-amber-100/50">Ctrl+Enter to save</span>}
        </div>
        {editing ? (
          <textarea
            ref={textareaRef}
            aria-label="Comment text"
            name="graph-comment"
            autoComplete="off"
            value={draft}
            placeholder="Write a comment…"
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => onCommit(comment.id, draft)}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === 'Escape') {
                e.preventDefault();
                onCancelEdit(comment.id);
              } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                onCommit(comment.id, draft);
              }
            }}
            rows={2}
            className="block w-full resize-none overflow-hidden bg-transparent px-2.5 pt-1 pb-2 text-[13px] leading-[1.4] text-zinc-50 placeholder:text-zinc-500 focus:outline-none select-text"
          />
        ) : (
          <p
            className={`px-2.5 pt-1 pb-2 text-[13px] leading-[1.4] whitespace-pre-wrap break-words ${
              comment.text ? 'text-zinc-100' : 'italic text-zinc-500'
            }`}
          >
            {comment.text || 'Empty comment (double-click to edit)'}
          </p>
        )}
      </div>
    </foreignObject>
  );
};
