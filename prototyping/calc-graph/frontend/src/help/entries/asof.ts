// Help entries for the as-of (approval) date on impact (AsOfPanel.tsx). Merged into HELP by
// src/help/registry.ts; same rules as entries/v2.ts.
import type { HelpEntry } from "../registry";

export const ASOF_HELP = {
  "term.as-of": {
    kind: "term",
    title: "As-of (approval) date",
    short:
      "The date a change would be approved. The construction stage of every element on that date sets what the change costs and slips.",
    what: "A revised drawing before steel is detailed costs engineering time; the same change once steel is fabricated scraps pieces, and once erected it is field rework. The as-of date projects each element's stage from the platform schedule (activities) and submittal dates to that day.",
    real: "Projected from the synthetic schedule assuming the current forecast holds (no progress variance). A live platform source has no schedule logic, so it is used as it is today.",
  },
  "panel.asof-control": {
    title: "Approved on",
    short:
      "Pick when the change would be approved: today, +1 week, +2 weeks, +1 month or a date. This move's health, change order and construction status all move to that date (the every-column heat view stays at today).",
    what: "One projection (the construction state as of that date) feeds every number on the panel. Today is the current behaviour. The choice is part of the page's undo history.",
    terms: ["term.as-of"],
  },
  "panel.asof-timeline": {
    title: "Cost and slip vs approval date",
    short:
      "The change-order estimate and forecast slip at each approval date where something changes, and the date to approve by before the next jump.",
    read: "Points are today, +1 week, +2 weeks, +1 month, the selected date, every stage boundary of the affected elements and every finish of their submittal packages' and follow-on activities in the next 120 days (the estimate is a step function of those). The approve-by line names the element and the stage boundary that drives the next jump. Click a date to use it.",
    real: "Every figure is an estimate from stated unit rates on a synthetic project.",
    terms: ["term.as-of", "term.change-order"],
  },
} as const satisfies Record<string, HelpEntry>;
