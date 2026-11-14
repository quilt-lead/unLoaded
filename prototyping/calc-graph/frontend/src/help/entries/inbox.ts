// Help entries for the inbound inbox (InboxPage.tsx, InboxHistory.tsx). Merged into HELP by src/help/registry.ts; same rules as entries/v2.ts.
import type { HelpEntry } from "../registry";

export const INBOX_HELP = {
  "page.v2-inbox": {
    title: "Inbox",
    short:
      "Items arriving from Procore or Autodesk Build that need the engineer: RFIs, change events and change order requests. Read, confirm, run the impact, draft the reply.",
    what: "The AI step reads each item (which elements, what change, how confident, what it could not resolve). Nothing runs until you confirm the reading. The impact uses the same engine as Move a column, at the item's required-by date.",
    real: "Items come from the selected platform adapter: the synthetic mock unless CALCGRAPH_PLATFORM_PROCORE / _ACC is set to live and signed in.",
  },
  "panel.inbox-platform": {
    title: "Platform",
    short:
      "Which platform adapter the items come from, and whether it is live or the synthetic mock.",
  },
  "stat.inbox-open": {
    title: "Open items",
    short:
      "RFIs open or draft, change events pending without a change order, and pending change order requests on this platform.",
  },
  "stat.inbox-read": {
    title: "Read",
    short: "Items with an AI reading in the cache for their current text.",
  },
  "stat.inbox-confirmed": {
    title: "Confirmed",
    short:
      "Items whose reading the engineer has confirmed. Only confirmed readings run the impact or draft a reply.",
  },
  "panel.inbox-list": {
    title: "Incoming",
    short:
      "Open items, newest first, with the date received and the date a response is required by.",
  },
  "panel.inbox-item": {
    title: "Item",
    short:
      "The item as the platform holds it: text, sender dates, status, deep link and whether the platform links it to any model element.",
  },
  "panel.inbox-reading": {
    title: "AI reading",
    short:
      "What the AI step read: change type, primary and affected elements (with the words that identified them), the move or new section, confidence, and what it could not resolve.",
    what: "One structured-output call (Pydantic schema) through the app's AI step, using only element ids from the registry. Readings are cached by the item's content hash, so reloading or reading again costs nothing until the text changes.",
    real: "Model and spend are shown at the top of the page. Readings are suggestions: edit any field before confirming.",
  },
  "panel.inbox-confirm": {
    title: "Confirm reading",
    short:
      "Stores your reading (edited or not) for this item. The impact and the reply use the confirmed reading, never the raw AI one.",
  },
  "panel.inbox-unresolved": {
    title: "Could not resolve",
    short:
      "Facts the item does not pin down (which element, direction, size). Resolve them by editing the reading, or ask the sender in the reply.",
  },
  "panel.inbox-impact": {
    title: "Impact",
    short:
      "Runs the confirmed reading through the move-a-column engine at the approval date. Changes the engine cannot express say so instead of giving a number.",
    what: "Move or remove a column: the full impact (calcs to redo, health, change order, cost and slip vs date). A section substitution: the change-order estimate only, with the structural recheck flagged as not run. An opening, a connection change or anything else: no number, the reason and the construction status of the elements.",
    terms: ["term.as-of"],
  },
  "stat.inbox-slip": {
    title: "Forecast slip",
    short:
      "Working days the forecast project finish moves, from a CPM re-run of the platform schedule with the change's added durations.",
  },
  "stat.inbox-delay": {
    title: "Past contract",
    short:
      "Working days the new forecast finish passes the contract completion date (0 = absorbed by float).",
  },
  "panel.inbox-reply": {
    title: "Reply",
    short:
      "A drafted RFI response or change order review with the impact summary and links. Edit it here; it is a draft until you post or send it.",
    real: "Drafted from a template over the confirmed reading and the impact (no AI call).",
  },
  "panel.inbox-post": {
    title: "Post to platform",
    short:
      "Only for a live sandbox adapter that can post replies, and only after an explicit confirm. Otherwise disabled, with the reason shown.",
  },
  "panel.inbox-history": {
    title: "Inbox history",
    short:
      "Inbox items about this element: AI reading, confirmation, impact runs and replies, newest first (US Eastern).",
  },
} as const satisfies Record<string, HelpEntry>;
