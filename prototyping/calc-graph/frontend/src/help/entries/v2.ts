// Help entries for the v2 move-a-column UI (src/routes/v2, owned by R3). Merged into HELP by
// src/help/registry.ts; scripts/check-help.mjs reads every file in src/help/entries/ as part of the
// registry, so the same rules apply (ids used, entries used, no em dashes, terms link to terms).
// Same format as registry.ts: two-space indented "id": { ... } entries.
import type { HelpEntry } from "../registry";

export const V2_HELP = {
} as const satisfies Record<string, HelpEntry>;
