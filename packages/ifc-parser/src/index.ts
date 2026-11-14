/**
 * @unloaded/ifc-parser - IFC (STEP) -> ModelInput via web-ifc.
 * Works in Node and in the browser (pass `wasmPath` in the browser).
 */
import type { ModelInput, ModelParser } from "@unloaded/element-graph/input";
import { hasStepHeader, parseIfc, type IfcParseOptions } from "./parse.ts";

export { parseIfc, hasStepHeader };
export type { IfcParseOptions, IfcParsePhase } from "./parse.ts";
export { KIND_TABLE, LINEAR_KINDS, CONNECTION_NAME_RE, createKindResolver } from "./kind-map.ts";
export type { KindMap, KindRule } from "./kind-map.ts";
export { normaliseProfile, profileFromText } from "./profile.ts";

export const ifcParser: ModelParser<IfcParseOptions> = {
  id: "ifc",
  extensions: ["ifc"],
  canParse(fileName: string, head?: Uint8Array): boolean {
    if (head && head.length > 0) return hasStepHeader(head);
    return /\.ifc$/i.test(fileName);
  },
  parse(data: Uint8Array, options?: IfcParseOptions & { fileName?: string }): Promise<ModelInput> {
    return parseIfc(data, options);
  },
};
