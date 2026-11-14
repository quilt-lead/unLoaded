// Inbound inbox (backend/calcgraph/inbox.py, /api/v2/inbox): items from the platform adapter, AI reading,
// confirmed reading, impact run, drafted reply, element history.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get } from "../../api/client";
import type { AsOfDescribe, Timeline } from "./asOf";

const enc = encodeURIComponent;

export type ChangeType =
  | "move_column"
  | "remove_column"
  | "substitute_section"
  | "resize_member"
  | "add_opening"
  | "modify_connection"
  | "add_member"
  | "other_structural"
  | "not_structural"
  | "unclear";

export const CHANGE_TYPES: ChangeType[] = [
  "move_column",
  "remove_column",
  "substitute_section",
  "resize_member",
  "add_opening",
  "modify_connection",
  "add_member",
  "other_structural",
  "not_structural",
  "unclear",
];

export interface ElementRef {
  element_id: string;
  role: "primary" | "affected";
  how_identified: string;
}

export interface Reading {
  change_type: ChangeType;
  elements: ElementRef[];
  move: { dx_ft: number; dy_ft: number } | null;
  new_section: string | null;
  summary: string;
  unresolved: string[];
  confidence: number;
  evidence_refs: string[];
}

export interface CoSummary {
  total_cost: { value: number };
  cost_range: { low: { value: number }; high: { value: number } };
  forecast_slip: { value: number };
  finish_delay: { value: number };
  worst_stage: string;
  headline: string;
  counts: Record<string, number>;
}

export interface InboxImpact {
  plan: {
    engine: "move" | "resize" | null;
    expressible: boolean | "partial";
    reason: string;
    move?: { column: string; dx: number; dy: number; remove: boolean };
    resize?: { id: string; old_size: string; new_size: string };
  };
  as_of: AsOfDescribe;
  computed_at: string;
  impact?: {
    column: string;
    stale: number;
    health: Record<string, string | number | null>;
    sheets?: string[];
  };
  change_order?: CoSummary | null;
  records_to_redo?: string[];
  links?: { move_page: string };
  timeline?: Timeline;
  status?: Record<
    string,
    {
      stage?: string;
      float_days?: number | null;
      reasons?: string[];
      submittals?: string[];
      error?: string;
    }
  >;
}

export interface InboxItem {
  key: string;
  platform: string;
  platform_label: string;
  kind: "rfi" | "change_event" | "change_order";
  number: string;
  title: string;
  body: string;
  status: string;
  received: string | null;
  required_by: string | null;
  linked_element_ids: string[];
  link: string | null;
  source: string;
  source_label: string | null;
  content_hash: string;
  reading: Reading | null;
  reading_error?: string;
  changed_since_read: boolean;
  state: {
    confirmed: Reading | null;
    impact: InboxImpact | null;
    reply: string | null;
    reply_edited_at: string | null;
    posted: unknown;
  };
}

export interface LlmStatus {
  provider: string;
  model: string;
  enabled: boolean;
  why: string;
  run: { calls: number; cache_hits: number; cost_usd: number };
  run_cap_usd: number;
}

export interface InboxList {
  platform: string;
  platforms: { name: string; label: string; source: string }[];
  items: InboxItem[];
  llm: LlmStatus;
  now: string;
}

export interface HistoryEvent {
  at: string;
  item_key: string;
  number: string;
  kind: string;
  platform: string;
  link: string | null;
  event: string;
  text: string;
  element_ids: string[];
}

async function send<T>(
  method: "POST" | "PUT",
  url: string,
  body?: unknown,
): Promise<T> {
  const r = await fetch(url, {
    method,
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!r.ok) {
    const d = data as { detail?: unknown } | null;
    throw new Error(
      typeof d?.detail === "string"
        ? d.detail
        : `${r.status} ${text.slice(0, 200)}`,
    );
  }
  return data as T;
}

export const useInbox = (platform: string | null) =>
  useQuery({
    queryKey: ["v2", "inbox", platform],
    queryFn: ({ signal }) =>
      get<InboxList>(
        `/api/v2/inbox${platform ? `?platform=${enc(platform)}` : ""}`,
        signal,
      ),
  });

export const useInboxHistory = (eid: string | undefined) =>
  useQuery({
    queryKey: ["v2", "inbox-history", eid],
    enabled: !!eid,
    queryFn: ({ signal }) =>
      get<HistoryEvent[]>(`/api/v2/inbox/history/${enc(eid!)}`, signal),
  });

export function useInboxActions() {
  const qc = useQueryClient();
  const done = () => {
    void qc.invalidateQueries({ queryKey: ["v2", "inbox"] });
    void qc.invalidateQueries({ queryKey: ["v2", "inbox-history"] });
  };
  return {
    read: useMutation({
      mutationFn: (key: string) =>
        send<{
          reading: Reading;
          cached: boolean;
          usage?: { cost_usd: number };
          llm: LlmStatus;
        }>("POST", `/api/v2/inbox/${enc(key)}/read`),
      onSuccess: done,
    }),
    confirm: useMutation({
      mutationFn: (a: { key: string; reading: Partial<Reading> }) =>
        send<{ confirmed: Reading }>(
          "PUT",
          `/api/v2/inbox/${enc(a.key)}/reading`,
          a.reading,
        ),
      onSuccess: done,
    }),
    impact: useMutation({
      mutationFn: (a: { key: string; as_of: string }) =>
        send<InboxImpact>("POST", `/api/v2/inbox/${enc(a.key)}/impact`, {
          as_of: a.as_of,
        }),
      onSuccess: done,
    }),
    reply: useMutation({
      mutationFn: (key: string) =>
        send<{ reply: string; post: { allowed: boolean; reason: string } }>(
          "POST",
          `/api/v2/inbox/${enc(key)}/reply`,
        ),
      onSuccess: done,
    }),
    saveReply: useMutation({
      mutationFn: (a: { key: string; reply: string }) =>
        send<{ reply: string; post: { allowed: boolean; reason: string } }>(
          "PUT",
          `/api/v2/inbox/${enc(a.key)}/reply`,
          { reply: a.reply },
        ),
      onSuccess: done,
    }),
    post: useMutation({
      mutationFn: (key: string) =>
        send<{ posted: unknown }>("POST", `/api/v2/inbox/${enc(key)}/post`, {
          confirm: true,
        }),
      onSuccess: done,
    }),
  };
}
