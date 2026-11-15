/**
 * The decisions file: calc-mapper's decision log as JSON, an array of `Decision`s oldest first
 * ({id, global_id, calc_key, action, actor, note, at, model_rev, calc_rev, provenance}). It is the
 * file calc-mapper's own CLI reads (`run-pipeline.ts --decisions`): entries are made by the engine's
 * `addDecision` (next id, human provenance) and read back through `decisionFrom`, which also accepts
 * an entry without provenance (it states it from the entry's own fields).
 *
 * Append-only: the server never rewrites or drops an entry (entries are written back exactly as they
 * were read; nothing is added to an old entry).
 *
 * Several writers (two MCP servers on the same file, e.g. Claude Desktop and Claude Code): every
 * append takes an exclusive cross-process lock, `<real file>.lock` (created with O_EXCL; it holds the
 * writer's pid, host, a token and the time). Under the lock the append re-reads the file, validates
 * against what is really there, writes the whole array to a temp file next to the real file, fsyncs
 * it, renames it over the original (atomic on POSIX file systems) and fsyncs the directory. A lock
 * whose owner is gone (same host, pid not running) or older than LOCK_STALE_MS is broken; a live one
 * is waited for up to LOCK_WAIT_MS, then the append fails with a message naming the lock file.
 *
 * Within one process every read (load, refresh) and every append goes through one queue, so a slow
 * read can never land after an append and roll the in-memory log back.
 *
 * A symlinked --decisions path is resolved once (realpath): the real file is read, written and
 * locked, so the link is never replaced by a regular file. The file's mode is kept.
 *
 * A file that cannot be read as a decision log (not JSON, a bad entry, empty) is a PROBLEM, not a
 * crash: reads keep serving the last good log (none, if it was never good) and every result carries
 * the problem as a warning; appends are refused until the file is fixed, and the file is never
 * overwritten.
 */
import { createHash, randomBytes } from "node:crypto";
import { existsSync, lstatSync, readlinkSync, realpathSync } from "node:fs";
import { link, open, readFile, rename, stat, unlink } from "node:fs/promises";
import { hostname } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
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

/** How long an append waits for another writer's lock before giving up. */
export const LOCK_WAIT_MS = 10_000;
/** A lock older than this is taken to be left behind by a crashed writer (an append holds it for milliseconds). */
export const LOCK_STALE_MS = 30_000;

type DiskRead =
  | { state: "missing" }
  | { state: "ok"; log: DecisionFields[]; snap: Snapshot }
  | { state: "bad"; reason: string; snap: Snapshot };

interface LockInfo {
  pid: number;
  host: string;
  token: string;
  at: string;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function pidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return (e as NodeJS.ErrnoException).code === "EPERM"; // exists, owned by someone else
  }
}

/**
 * The real file a --decisions path names: a symlink (even a dangling one) is followed; a path that
 * does not exist yet is the real directory + the name.
 */
export function realTarget(path: string, depth = 0): string {
  const abs = resolve(path);
  if (existsSync(abs)) return realpathSync(abs);
  try {
    if (lstatSync(abs).isSymbolicLink()) {
      if (depth >= 40) throw new DecisionsFileError(`decisions file ${path}: too many levels of symbolic links`);
      return realTarget(resolve(dirname(abs), readlinkSync(abs)), depth + 1);
    }
  } catch (e) {
    if (e instanceof DecisionsFileError) throw e;
    // does not exist at all
  }
  const dir = dirname(abs);
  return existsSync(dir) ? join(realpathSync(dir), basename(abs)) : abs;
}

export class DecisionsFile {
  /** The path as given (--decisions). */
  readonly path: string;
  /** The log as last read from disk (the last GOOD read; [] if the file does not exist yet), entries as stored. */
  log: DecisionFields[] = [];
  /** Why the file on disk cannot be used, or null. Reads go on with `log`; appends are refused. */
  problem: string | null = null;
  private snap: Snapshot | null = null;
  private target: string | null = null;
  private queue: Promise<unknown> = Promise.resolve();
  private readonly lockWaitMs: number;
  private readonly lockStaleMs: number;

  constructor(path: string, opts: { lockWaitMs?: number; lockStaleMs?: number } = {}) {
    this.path = path;
    this.lockWaitMs = opts.lockWaitMs ?? LOCK_WAIT_MS;
    this.lockStaleMs = opts.lockStaleMs ?? LOCK_STALE_MS;
  }

  get name(): string {
    return basename(this.path);
  }
  get exists(): boolean {
    return this.snap !== null;
  }
  get sha256(): string | null {
    return this.problem ? null : (this.snap?.sha256 ?? null);
  }
  /** The real file (symlinks resolved once, on the first read). */
  get realPath(): string {
    return (this.target ??= realTarget(this.path));
  }
  /** Is the --decisions path a symbolic link (to the real file)? */
  get isSymlink(): boolean {
    try {
      return lstatSync(resolve(this.path)).isSymbolicLink();
    } catch {
      return false;
    }
  }
  get lockPath(): string {
    return `${this.realPath}.lock`;
  }

  /** Run `fn` after everything queued before it (reads and appends alike). */
  private serial<T>(fn: () => Promise<T>): Promise<T> {
    const p = this.queue.then(fn, fn);
    this.queue = p.catch(() => {});
    return p;
  }

  /** Read (or re-read) the file. A missing file is an empty log; the first append creates it. */
  load(): Promise<void> {
    return this.serial(async () => {
      this.apply(await this.readDisk());
    });
  }

  /** Re-read when changed on disk. Returns true when the file was read again. */
  refresh(): Promise<boolean> {
    return this.serial(async () => {
      if (!(await this.changedOnDisk())) return false;
      this.apply(await this.readDisk());
      return true;
    });
  }

  private async readDisk(): Promise<DiskRead> {
    const path = this.realPath;
    if (!existsSync(path)) {
      if (!existsSync(dirname(path))) throw new DecisionsFileError(`decisions file ${this.path}: its directory does not exist`);
      return { state: "missing" };
    }
    const st = await stat(path);
    if (!st.isFile()) throw new DecisionsFileError(`decisions file ${this.path} is not a file`);
    const raw = await readFile(path);
    const snap = { size: raw.length, mtimeMs: st.mtimeMs, sha256: sha256(raw) };
    const text = raw.toString("utf8").replace(/^\uFEFF/, "");
    if (!text.trim()) {
      return {
        state: "bad",
        snap,
        reason: `${this.name} is empty (${raw.length} bytes). A decisions file is a JSON array: write [] into it, or delete it and the server creates it on the first decision`,
      };
    }
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch (e) {
      return { state: "bad", snap, reason: `${this.name} is not valid JSON: ${(e as Error).message}` };
    }
    try {
      return { state: "ok", snap, log: parseDecisions(data, this.name) };
    } catch (e) {
      return { state: "bad", snap, reason: (e as Error).message };
    }
  }

  private apply(r: DiskRead): void {
    if (r.state === "missing") {
      this.log = [];
      this.snap = null;
      this.problem = null;
    } else if (r.state === "ok") {
      this.log = r.log;
      this.snap = r.snap;
      this.problem = null;
    } else {
      // keep the last good log; remember the bad bytes so they are not re-parsed on every call
      this.snap = r.snap;
      this.problem =
        `the decisions file cannot be read: ${r.reason}. Answers use the last good copy of the log (${this.log.length} ` +
        `entr${this.log.length === 1 ? "y" : "ies"}); recording decisions is refused until the file is fixed. The server never overwrites it.`;
    }
  }

  /** Has the file changed on disk since it was last read? (size / mtime first, then sha256.) */
  private async changedOnDisk(): Promise<boolean> {
    const path = this.realPath;
    if (!existsSync(path)) return this.snap !== null;
    if (!this.snap) return true;
    const st = await stat(path);
    if (st.size === this.snap.size && st.mtimeMs === this.snap.mtimeMs) return false;
    const h = sha256(await readFile(path));
    if (h === this.snap.sha256) {
      this.snap = { ...this.snap, size: st.size, mtimeMs: st.mtimeMs };
      return false;
    }
    return true;
  }

  /**
   * Append decisions. Under the cross-process lock, the file is re-read and `build(currentLog)` runs
   * on what is actually in it; it returns the entries to append (made with the engine's `addDecision`
   * on that log) or throws. `reloaded` is true when the file held changes this server had not seen.
   */
  append(build: (current: readonly DecisionFields[]) => Decision[]): Promise<{ appended: Decision[]; reloaded: boolean }> {
    return this.serial(() =>
      this.withLock(async () => {
        const seen = this.snap?.sha256 ?? null;
        const r = await this.readDisk();
        const reloaded = (r.state === "missing" ? null : r.snap.sha256) !== seen;
        this.apply(r);
        if (this.problem) throw new DecisionsFileError(`nothing was written: ${this.problem}`);
        const add = build(this.log);
        if (!add.length) return { appended: [], reloaded };
        const next: DecisionFields[] = [...this.log, ...add];
        const body = Buffer.from(JSON.stringify(next, null, 2) + "\n", "utf8");
        const snap = await this.writeAtomic(body, r.state === "ok" ? (await stat(this.realPath)).mode & 0o7777 : null);
        this.log = next;
        this.snap = snap;
        return { appended: add, reloaded };
      }),
    );
  }

  /** temp file next to the real file -> fsync -> rename over it -> fsync the directory. Returns the snapshot of the bytes written. */
  private async writeAtomic(body: Buffer, mode: number | null): Promise<Snapshot> {
    const target = this.realPath;
    const dir = dirname(target);
    const tmp = join(dir, `.${basename(target)}.${process.pid}.${randomBytes(4).toString("hex")}.tmp`);
    let mtimeMs: number;
    try {
      const fh = await open(tmp, "wx");
      try {
        if (mode !== null) await fh.chmod(mode);
        await fh.writeFile(body);
        await fh.sync();
        mtimeMs = (await fh.stat()).mtimeMs; // rename keeps it
      } finally {
        await fh.close();
      }
      await rename(tmp, target);
    } catch (e) {
      await unlink(tmp).catch(() => {});
      throw new DecisionsFileError(`could not write ${target}: ${(e as Error).message}`);
    }
    try {
      const dh = await open(dir, "r");
      try {
        await dh.sync();
      } finally {
        await dh.close();
      }
    } catch {
      // directories cannot be opened / fsynced on every platform (Windows); the rename is still atomic
    }
    return { size: body.length, mtimeMs, sha256: sha256(body) };
  }

  /** Run `fn` holding `<real file>.lock` (O_EXCL), breaking a stale lock, waiting up to LOCK_WAIT_MS for a live one. */
  private async withLock<T>(fn: () => Promise<T>): Promise<T> {
    const lock = this.lockPath;
    const info: LockInfo = { pid: process.pid, host: hostname(), token: randomBytes(8).toString("hex"), at: new Date().toISOString() };
    const deadline = Date.now() + this.lockWaitMs;
    let delay = 5;
    for (;;) {
      try {
        const fh = await open(lock, "wx");
        try {
          await fh.writeFile(JSON.stringify(info));
        } finally {
          await fh.close();
        }
        break;
      } catch (e) {
        if ((e as NodeJS.ErrnoException).code !== "EEXIST") {
          throw new DecisionsFileError(`could not create the lock file ${lock}: ${(e as Error).message}`);
        }
      }
      const held = await readLock(lock);
      if (!held) continue; // released meanwhile
      if (isStale(held, this.lockStaleMs)) {
        await breakLock(lock, held.raw);
        continue;
      }
      if (Date.now() >= deadline) {
        const who = held.info ? `pid ${held.info.pid} on ${held.info.host}, since ${held.info.at}` : "an unknown writer";
        throw new DecisionsFileError(
          `nothing was written: ${this.name} is locked by another writer (${who}) for more than ${this.lockWaitMs / 1000} s. ` +
            `If no other unLoaded server or tool is writing it, delete ${lock} and try again.`,
        );
      }
      await sleep(delay);
      delay = Math.min(delay * 2, 100);
    }
    try {
      return await fn();
    } finally {
      const held = await readLock(lock);
      if (held?.info?.token === info.token) await unlink(lock).catch(() => {});
    }
  }
}

async function readLock(lock: string): Promise<{ raw: string; info: LockInfo | null; mtimeMs: number } | null> {
  try {
    const [raw, st] = await Promise.all([readFile(lock, "utf8"), stat(lock)]);
    let info: LockInfo | null = null;
    try {
      const o = JSON.parse(raw) as Partial<LockInfo>;
      if (typeof o.pid === "number" && typeof o.host === "string" && typeof o.token === "string") info = o as LockInfo;
    } catch {
      // being written, or not ours
    }
    return { raw, info, mtimeMs: st.mtimeMs };
  } catch {
    return null;
  }
}

function isStale(held: { info: LockInfo | null; mtimeMs: number }, staleMs: number): boolean {
  if (held.info && held.info.host === hostname() && !pidAlive(held.info.pid)) return true;
  return Date.now() - held.mtimeMs > staleMs;
}

/**
 * Remove a stale lock without removing a fresh one another process took meanwhile: move it aside
 * (atomic), and if what was moved is not the stale lock we judged, put it back (link fails if a
 * third lock appeared, which then stands).
 */
async function breakLock(lock: string, staleRaw: string): Promise<void> {
  const aside = `${lock}.${process.pid}.${randomBytes(4).toString("hex")}.stale`;
  try {
    await rename(lock, aside);
  } catch {
    return; // already gone
  }
  try {
    if ((await readFile(aside, "utf8")) !== staleRaw) await link(aside, lock).catch(() => {});
  } finally {
    await unlink(aside).catch(() => {});
  }
}

export type { DecisionAction };
