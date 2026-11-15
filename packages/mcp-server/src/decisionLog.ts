/**
 * The project file's decision log as the engine reads it. The file format itself (type, validator,
 * base64 codec, head rule) lives in `@unloaded/project-file`, shared with the app; this is the one
 * mapping the MCP server adds on top.
 */
import type { DecisionFields } from "@unloaded/calc-mapper";
import type { ProjectFile } from "@unloaded/project-file";

/**
 * The decision log as calc-mapper DecisionFields, oldest first. The file keeps the log in order and
 * without ids; ids are re-assigned 1..n in that order, exactly as the app's importer's auto-increment
 * does, so "the latest decision per pair wins" resolves the same way. The engine states each
 * decision's provenance from these fields (decisionFrom).
 */
export function decisionsOf(file: ProjectFile): DecisionFields[] {
  return file.decisions.map((d, i) => ({
    id: i + 1,
    global_id: d.globalId,
    calc_key: d.calcKey,
    action: d.action,
    actor: d.actor,
    note: d.note,
    at: d.at,
    model_rev: d.modelRev,
    calc_rev: d.calcRev,
  }));
}
