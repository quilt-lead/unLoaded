// Public API of @unloaded/move-impact. Pure TypeScript, no runtime dependencies, no side effects.
export type * from "./types.ts";
export { ENGINE_VERSION, BANDS } from "./types.ts";
export { impact, UnknownColumn, CHANGE, TOUCH } from "./impact.ts";
export { buildModel } from "./model.ts";
export type { Model, Member, End } from "./model.ts";
export { solveSpan, COMBOS } from "./statics.ts";
export { PACKAGE_NAME, PACKAGE_VERSION, RULES, producerOf } from "./provenance.ts";
