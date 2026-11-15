/**
 * The decisions file: calc-mapper's decision log as JSON, an array of `Decision`s oldest first
 * ({id, global_id, calc_key, action, actor, note, at, model_rev, calc_rev, provenance}). It is the
 * file calc-mapper's own CLI reads (`run-pipeline.ts --decisions`): entries are made by the engine's
 * `addDecision` (next id, human provenance) and read back through `decisionFrom`, which also accepts
 * an entry without provenance (it states it from the entry's own fields).
 *
 * Append-only: the server never rewrites or drops an entry (entries are written back exactly as they
 * were read; nothing is added to an old entry). An append re-reads the file first when it changed on
 * disk since it was last read (size, mtime or sha256), so a decision someone else recorded meanwhile
 * is kept, then writes the whole array to a temp file in the same directory and renames it over the
 * original (atomic on POSIX file systems).
 */
import { createHash, randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import { readFile, rename, stat, unlink, writeFile } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import { DECISION_ACTIONS, decisionFrom, type Decision, type DecisionAction, type DecisionFields } from "./engine.ts";

export class DecisionsFileError extends Error {
  override name = "DecisionsFileError";
}

export const sha256 = (b: Uint8Array | string) => createHash("sha256").update(b).digest("hex");

const SHAPE = '[{"id", "global_id", "calc_key", "action", "actor", "note", "at", "model_rev"?, "calc_rev"?, "provenance"?}, ...]';

/**
 * Validate parsed JSON as a decision log. Errors name the entry index and the field. Returns the
 * entries as read (DecisionFields; provenance only where the file has it).
 */
export function parseDecisions(data: unknown, file: string): DecisionFields[] {
  if (!Array.isArray(data)) {
    throw new DecisionsFileError(`${file}: a decisions file must be a JSON array of decisions (${SHAPE}), got ${data === null ? "null" : typeof data}`);
  }
  const ids = new Map<number, number>();
  return data.map((d, i): DecisionFields => {
    const at = `${file}: entry ${i}`;
    if (typeof d !== "object" || d === null || Array.isArray(d)) throw new DecisionsFileError(`${at} is not an object`);
    const o = d as Record<string, unknown>;
    if (typeof o.id !== "number" || !Number.isInteger(o.id) || o.id < 1) {
      throw new DecisionsFileError(`${at}: "id" must be a positive integer (calc-mapper's decision log orders decisions by id; got ${JSON.stringify(o.id)})`);
    }
    const prev = ids.get(o.id);
    if (prev !== undefined) throw new DecisionsFileError(`${at}: "id" ${o.id} is also the id of entry ${prev}`);
    ids.set(o.id, i);
    for (const k of ["global_id", "calc_key", "at"] as const) {
      if (typeof o[k] !== "string" || !(o[k] as string).length) throw new DecisionsFileError(`${at}: "${k}" must be a non-empty string`);
    }
    if (!(DECISION_ACTIONS as readonly unknown[]).includes(o.action)) {
      throw new DecisionsFileError(`${at}: "action" must be one of ${DECISION_ACTIONS.join(", ")} (got ${JSON.stringify(o.action)})`);
    }
    if (Number.isNaN(Date.parse(o.at as string))) throw new DecisionsFileError(`${at}: "at" must be an ISO date-time (got ${JSON.stringify(o.at)})`);
    for (const k of ["actor", "note"] as const) {
      if (o[k] !== undefined && o[k] !== null && typeof o[k] !== "string") throw new DecisionsFileError(`${at}: "${k}" must be a string or null`);
    }
    for (const k of ["model_rev", "calc_rev"] as const) {
      if (o[k] !== undefined && o[k] !== null && typeof o[k] !== "string" && typeof o[k] !== "number") {
        throw new DecisionsFileError(`${at}: "${k}" must be a string, a number or null`);
      }
    }
    if (o.provenance !== undefined && (typeof o.provenance !== "object" || o.provenance === null || Array.isArray(o.provenance))) {
      throw new DecisionsFileError(`${at}: "provenance" must be an object when present`);
    }
    const fields = { ...o, actor: (o.actor as string | null | undefined) ?? null, note: (o.note as string | null | undefined) ?? null } as unknown as DecisionFields;
    try {
      decisionFrom(fields); // the engine's own check of a stored decision
    } catch (e) {
      throw new DecisionsFileError(`${at}: ${(e as Error).message}`);
    }
    // keep the entry exactly as read, so writing the log back never changes an old entry
    return o as unknown as DecisionFields;
  });
}

interface Snapshot {
  size: number;
  mtimeMs: number;
  sha256: string | null;
}

export class DecisionsFile {
  readonly path: string;
  /** The log as last read from disk (or [] if the file does not exist yet), entries as stored. */
  log: DecisionFields[] = [];
  private snap: Snapshot | null = null;
  private queue: Promise<unknown> = Promise.resolve();

  constructor(path: string) {
    this.path = path;
  }

  get name(): string {
    return basename(this.path);
  }
  get exists(): boolean {
    return this.snap !== null;
  }
  get sha256(): string | null {
    return this.snap?.sha256 ?? null;
  }

  /** Read (or re-read) the file. A missing file is an empty log; the first append creates it. */
  async load(): Promise<void> {
    if (!existsSync(this.path)) {
      if (!existsSync(dirname(this.path))) {
        throw new DecisionsFileError(`decisions file ${this.path}: its directory does not exist`);
      }
      this.log = [];
      this.snap = null;
      return;
    }
    const st = await stat(this.path);
    if (!st.isFile()) throw new DecisionsFileError(`decisions file ${this.path} is not a file`);
    const raw = await readFile(this.path);
    const text = raw.toString("utf8").replace(/^﻿/, "");
    let data: unknown;
    if (!text.trim()) data = [];
    else {
      try {
        data = JSON.parse(text);
      } catch (e) {
        throw new DecisionsFileError(`${this.name} is not valid JSON: ${(e as Error).message}`);
      }
    }
    this.log = parseDecisions(data, this.name);
    this.snap = { size: st.size, mtimeMs: st.mtimeMs, sha256: sha256(raw) };
  }

  /** Has the file changed on disk since it was last read? (size / mtime first, then sha256.) */
  async changedOnDisk(): Promise<boolean> {
    const exists = existsSync(this.path);
    if (!exists) return this.snap !== null;
    if (!this.snap) return true;
    const st = await stat(this.path);
    if (st.size === this.snap.size && st.mtimeMs === this.snap.mtimeMs) return false;
    const h = sha256(await readFile(this.path));
    if (h === this.snap.sha256) {
      this.snap = { ...this.snap, size: st.size, mtimeMs: st.mtimeMs };
      return false;
    }
    return true;
  }

  /** Re-read when changed on disk. Returns true when the log was reloaded. */
  async refresh(): Promise<boolean> {
    if (!(await this.changedOnDisk())) return false;
    await this.load();
    return true;
  }

  /**
   * Append decisions. `build(currentLog)` runs after the on-disk log has been re-read (when it
   * changed), so validation sees what is actually in the file; it returns the entries to append (made
   * with the engine's `addDecision` on that log) or throws. Writes are serialised.
   */
  append(build: (current: readonly DecisionFields[]) => Decision[]): Promise<{ appended: Decision[]; reloaded: boolean }> {
    const run = async () => {
      const reloaded = await this.refresh();
      const add = build(this.log);
      if (!add.length) return { appended: [], reloaded };
      const next: DecisionFields[] = [...this.log, ...add];
      const body = JSON.stringify(next, null, 2) + "\n";
      const tmp = join(dirname(this.path), `.${basename(this.path)}.${process.pid}.${randomBytes(4).toString("hex")}.tmp`);
      try {
        await writeFile(tmp, body, { flag: "wx" });
        await rename(tmp, this.path);
      } catch (e) {
        await unlink(tmp).catch(() => {});
        throw new DecisionsFileError(`could not write ${this.path}: ${(e as Error).message}`);
      }
      const st = await stat(this.path);
      this.log = next;
      this.snap = { size: st.size, mtimeMs: st.mtimeMs, sha256: sha256(body) };
      return { appended: add, reloaded };
    };
    const p = this.queue.then(run, run);
    this.queue = p.catch(() => {});
    return p;
  }
}

export type { DecisionAction };
