// Small status chips shared by the inspector and the PDF browser.
import React from 'react';
import type { CalcLink, DiffStatus, LinkReview, MappingStatus } from '../../types/bim';
import { DIFF_PALETTE, REVIEW_LABELS, STATUS_COLORS, STATUS_LABELS, TIER_LABELS } from '../../utils/colors';

const TONE_CLASS = {
  good: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/30',
  warn: 'bg-amber-500/15 text-amber-300 border-amber-400/30',
  bad: 'bg-rose-500/15 text-rose-300 border-rose-400/30',
  info: 'bg-indigo-500/15 text-indigo-300 border-indigo-400/30',
  muted: 'bg-white/[0.05] text-zinc-300 border-white/[0.12]',
} as const;

export const Chip: React.FC<{ tone?: keyof typeof TONE_CLASS; title?: string; children: React.ReactNode }> = ({ tone = 'muted', title, children }) => (
  <span title={title} className={`mono text-[9px] px-1.5 py-0.5 rounded border whitespace-nowrap ${TONE_CLASS[tone]}`}>
    {children}
  </span>
);

export const ConfidenceChip: React.FC<{ link: CalcLink }> = ({ link }) => {
  if (link.review === 'confirmed') return <Chip tone="good">confirmed</Chip>;
  if (link.review === 'manual') return <Chip tone="info">by hand</Chip>;
  if (link.review === 'rejected') return <Chip tone="bad">rejected</Chip>;
  const tone = link.band === 'high' ? 'good' : link.band === 'medium' ? 'warn' : 'bad';
  return (
    <Chip tone={tone} title={`Confidence ${Math.round(link.confidence * 100)}% (${link.band}): the sum of the weighted evidence`}>
      {Math.round(link.confidence * 100)}%
    </Chip>
  );
};

/** Design = the calc sizes the element; Loads = it only takes loads from / refers to it. */
export const RoleChip: React.FC<{ role: CalcLink['role'] }> = ({ role }) =>
  role === 'design' ? (
    <Chip tone="info" title="The calc sizes this element">
      design
    </Chip>
  ) : (
    <Chip tone="muted" title="The calc only takes loads from or refers to this element; it does not size it">
      loads only
    </Chip>
  );

export const TierChip: React.FC<{ tier: string }> = ({ tier }) => (
  <Chip tone="muted" title={`Matcher tier: ${tier}`}>
    {TIER_LABELS[tier] ?? tier}
  </Chip>
);

export const ReviewChip: React.FC<{ review: LinkReview }> = ({ review }) => (
  <Chip tone={review === 'confirmed' ? 'good' : review === 'manual' ? 'info' : review === 'rejected' ? 'bad' : 'warn'}>{REVIEW_LABELS[review]}</Chip>
);

export const StatusDot: React.FC<{ status: MappingStatus }> = ({ status }) => (
  <span className="inline-flex items-center gap-1 mono text-[9px] text-zinc-300">
    <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: STATUS_COLORS[status] }} />
    {STATUS_LABELS[status]}
  </span>
);

export const DiffBadge: React.FC<{ status: DiffStatus }> = ({ status }) => (
  <span
    className="mono text-[8.5px] font-bold px-1.5 py-0.5 rounded uppercase"
    style={{ backgroundColor: `${DIFF_PALETTE[status]}26`, color: DIFF_PALETTE[status] }}
  >
    {status}
  </span>
);
