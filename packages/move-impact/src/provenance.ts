/**
 * Provenance of every record this package outputs, in calc-mapper's `Provenance` shape (see
 * types.ts `MoveImpactProvenance`). Inputs are validated by calc-mapper's `inputList` (lowercase hex
 * sha256, first-seen order, no repeats; a missing hash throws). One constructor, so the producer
 * string and its version come from one place (PACKAGE_VERSION, pinned to package.json by a test).
 */
import { inputList } from "@unloaded/calc-mapper";
import type { MoveImpactModule, MoveImpactProducer, MoveImpactProvenance } from "./types.ts";

export const PACKAGE_NAME = "move-impact" as const;
export const PACKAGE_VERSION = "0.1.0" as const;

export const producerOf = (module: MoveImpactModule): MoveImpactProducer => `${PACKAGE_NAME}@${PACKAGE_VERSION}/${module}`;

/** Stable rule ids. */
export const RULES = {
  topological: "move.topological.load-path",
  screen: {
    change: "move.screen.governing-change-over-5pct",
    noNumber: "move.screen.kept-no-screened-number",
    movesWithColumn: "move.screen.moves-with-column",
    merged: "move.screen.merged-transfer-member",
  },
  estimate: {
    beam: "move.estimate.beam-checks-scaled",
    frameGirder: "move.estimate.frame-girder",
    connection: "move.estimate.connection-end-reaction",
    column: "move.estimate.column-axial-ratio",
    footing: "move.estimate.footing-bearing",
    brace: "move.estimate.chevron-brace-share",
    transfer: "move.estimate.transfer-member-flexure",
  },
  staleRow: "move.stale.row-on-path",
  staleCalc: "move.stale.calc-on-path",
  health: "move.health.bands",
} as const;

export function provenance(
  module: MoveImpactModule,
  rule: string,
  method: "rule" | "estimate",
  ...inputs: readonly (readonly (string | null | undefined)[])[]
): MoveImpactProvenance {
  return { producer: producerOf(module), rule, method, inputs: inputList(...inputs) };
}
