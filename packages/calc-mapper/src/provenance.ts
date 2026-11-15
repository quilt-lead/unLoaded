/**
 * Provenance: why a record exists. Port of the reference schema's `Provenance` (models.py) for the
 * records this engine derives. Every Link, GroupLink, CalcEdge, Calc, Finding, Impact and Decision
 * carries one, and the type makes it REQUIRED, so a record built without it does not type-check.
 *
 *   producer  "calc-mapper@<package version>/<module>"   which code made it
 *   rule      a stable rule id ("matcher.tier.exact")     which rule in that code
 *   method    "rule" | "human" | "estimate"              deterministic rule / a person / an estimate
 *   inputs    sha256 of the documents it rests on        the calc PDF's bytes, the element graph's JSON
 *   actor     who decided (method "human" only)
 *   at        when it was decided (method "human" only)
 *
 * The record's own evidence (Link.evidence, CalcEdge.evidence, a Finding's rects + snippet ...)
 * stays where it was: provenance says who and what rule produced the record; evidence says where.
 *
 * Every provenance object is built by one of the constructors below, so the producer string and
 * the version in it come from one place (PACKAGE_VERSION, pinned to package.json by a test).
 */
import { SHA256_HEX } from "./hash.ts";

/** This package's version: the `<version>` in every producer string. A test pins it to package.json. */
export const PACKAGE_VERSION = "0.1.0" as const;
export const PACKAGE_NAME = "calc-mapper" as const;

/** The modules that produce records. */
export type CalcMapperModule = "segment" | "matcher" | "calcdeps" | "impact" | "decisions";

/** "<package>@<version>/<module>", e.g. "calc-mapper@0.1.0/matcher" or "move-impact@0.1.0/impact".
 * Any package in the workspace produces records under this one contract; calc-mapper's own producers
 * are the narrower `CalcMapperProducer`. */
export type Producer = `${string}@${string}/${string}`;
export type CalcMapperProducer = `${typeof PACKAGE_NAME}@${string}/${CalcMapperModule}`;

/** rule: a deterministic rule produced it; human: a person decided it; estimate: a labelled estimate. */
export type ProvenanceMethod = "rule" | "human" | "estimate";

export interface Provenance {
  producer: Producer;
  /** Stable rule id (see RULES). */
  rule: string;
  method: ProvenanceMethod;
  /** Lowercase hex sha256 of each input document the record rests on (first-seen order, no repeats). */
  inputs: string[];
  /** Who decided (method "human"). */
  actor?: string | null;
  /** ISO time of the decision (method "human"). */
  at?: string;
}

/** Stable rule ids, by module. */
export const RULES = {
  segment: {
    calc: "segment.calc-title",
    scanned: "segment.scanned-run",
    front: "segment.front-matter",
  },
  matcher: {
    tier: (tier: string) => `matcher.tier.${tier}`,
    typicalGroup: "matcher.typical-group",
    sizeMismatch: "matcher.finding.size-mismatch",
  },
  calcdeps: {
    pageInput: "calcdeps.page-reference.input",
    pageOutput: "calcdeps.page-reference.output",
    crossReference: "calcdeps.cross-reference",
  },
  impact: {
    propagate: (mode: string) => `impact.propagate.${mode}`,
  },
  decisions: {
    action: (action: string) => `decision.${action}`,
  },
} as const;

export const producerOf = (module: CalcMapperModule): CalcMapperProducer => `${PACKAGE_NAME}@${PACKAGE_VERSION}/${module}`;

/**
 * First-seen order, no repeats. Throws on anything that is not a lowercase hex sha256 - a missing
 * or empty hash included - so a record can never silently claim fewer inputs than it rests on.
 */
export function inputList(...lists: readonly (readonly (string | null | undefined)[])[]): string[] {
  const out: string[] = [];
  for (const l of lists) {
    for (const h of l) {
      if (typeof h !== "string" || !SHA256_HEX.test(h)) {
        throw new Error(`provenance input must be a lowercase hex sha256, got ${JSON.stringify(h ?? null)}`);
      }
      if (!out.includes(h)) out.push(h);
    }
  }
  return out;
}

/** Provenance of a record a deterministic rule produced. */
export function ruleProvenance(module: CalcMapperModule, rule: string, inputs: readonly string[]): Provenance {
  return { producer: producerOf(module), rule, method: "rule", inputs: inputList(inputs) };
}

/** Provenance of a labelled estimate. */
export function estimateProvenance(module: CalcMapperModule, rule: string, inputs: readonly string[]): Provenance {
  return { producer: producerOf(module), rule, method: "estimate", inputs: inputList(inputs) };
}

/** Provenance of a human decision (the decision log). */
export function humanProvenance(
  rule: string, actor: string | null, at: string, inputs: readonly string[] = [],
): Provenance {
  return { producer: producerOf("decisions"), rule, method: "human", inputs: inputList(inputs), actor, at };
}
