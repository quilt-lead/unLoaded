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
 * it, renames it over the original (atomic on POSIX file systems) and fsyncs the directory. The holder
 * heartbeats (refreshes the lock's mtime every LOCK_HEARTBEAT_MS). A lock is stale when its writer is
 * on this host (same `os.hostname()`) and its pid is not running, or when a waiter has seen nothing
 * about it change for LOCK_STALE_MS on its own monotonic clock (no two machines' clocks are ever
 * compared). A live lock is waited for up to LOCK_WAIT_MS, then the append fails with a message naming
 * the lock file; so does a lock file that cannot be read or removed. Every unlink of the lock (a break
 * or a release) happens under a second O_EXCL file, `<lock>.guard`, held for one re-read and one
 * unlink: the lock removed is exactly the one judged stale (or one's own, by token), never one another
 * writer took meanwhile. No hard links are needed.
 *
 * File-system assumptions, stated honestly:
 * - Local file systems (APFS, ext4, NTFS...): O_EXCL create, rename over a file and fsync behave as
 *   POSIX says; the guarantees above hold.
 * - Network file systems (NFS, SMB, synced folders): O_EXCL is atomic on NFSv3+ and SMB, but not on
 *   NFSv2 or on folder-sync tools (Dropbox, OneDrive), which can lose an append. Staleness never compares
 *   clocks, so skew is harmless; a writer on another host is only ever judged stale by observation.
 *   Two servers on different hosts with the same hostname are taken to be one host.
 * - Residual (not prevented): a holder that stops for longer than LOCK_STALE_MS (process suspended,
 *   event loop blocked; an append does no heavy synchronous work under the lock) can lose its lock and
 *   write alongside the next holder. A process that crashes while holding `<lock>.guard` leaves it; it is
 *   removed after GUARD_STALE_MS unchanged, and if two processes remove a left guard at the same moment
 *   both can believe they hold it (needs a crash inside the guard plus concurrent breakers).
 * - A crash can leave `<lock>`, `<lock>.guard` or a `.<name>.<pid>.<hex>.tmp` file. They are harmless:
 *   the lock and guard are broken as above; a temp file is never read and can be deleted.
 * - A write replaces the file (temp + rename): its mode is kept, but its owner can change (to the
 *   writer's user), a hard link to it stops seeing new entries, and ACLs / extended attributes are not
 *   carried over. A file this process may not write (e.g. chmod 444) is refused, never replaced.
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
import { access, constants, open, readFile, rename, stat, unlink, type FileHandle } from "node:fs/promises";
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
export const LOCK_WAIT_MS = 15_000;
/**
 * A lock that nothing has changed (content, mtime, identity) for this long, as watched by a waiter on its
 * own monotonic clock, was left by a writer that crashed or hung: a live holder heartbeats every
 * LOCK_HEARTBEAT_MS. Must be below LOCK_WAIT_MS, and several heartbeats long.
 */
export const LOCK_STALE_MS = 5_000;
/** How often a holder refreshes its lock's mtime. */
export const LOCK_HEARTBEAT_MS = 1_000;
/** `<lock>.guard` is held for one read and one unlink; one unchanged for this long was left by a crash. */
const GUARD_STALE_MS = 3_000;
/** How long a break or a release waits for `<lock>.guard` (longer than GUARD_STALE_MS, so a left guard is removed). */
const GUARD_WAIT_MS = 4_000;

type DiskRead =
  | { state: "missing" }
  | { state: "ok"; log: DecisionFields[]; snap: Snapshot }
  | { state: "bad"; reason: string; snap: Snapshot };

export interface LockInfo {
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
  private readonly lockHeartbeatMs: number;

  constructor(path: string, opts: { lockWaitMs?: number; lockStaleMs?: number; lockHeartbeatMs?: number } = {}) {
    this.path = path;
    this.lockWaitMs = opts.lockWaitMs ?? LOCK_WAIT_MS;
    this.lockStaleMs = opts.lockStaleMs ?? LOCK_STALE_MS;
    this.lockHeartbeatMs = opts.lockHeartbeatMs ?? LOCK_HEARTBEAT_MS;
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

  /**
   * Take a read. `log` stays the SAME array when the bytes are the ones it was read from, so a new
   * `log` object means the log really changed (Project recomputes on exactly that).
   */
  private apply(r: DiskRead): void {
    if (r.state === "missing") {
      if (this.snap !== null || this.problem !== null) this.log = [];
      this.snap = null;
      this.problem = null;
    } else if (r.state === "ok") {
      if (this.problem !== null || this.snap?.sha256 !== r.snap.sha256) this.log = r.log;
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
        // a write replaces the file (temp + rename), which needs only the directory writable: honour the file's own mode
        if (r.state === "ok") {
          try {
            await access(this.realPath, constants.W_OK);
          } catch {
            throw new DecisionsFileError(
              `nothing was written: ${this.realPath} is not writable by this server (its permissions forbid it). ` +
                `The server does not override them: make the file writable (e.g. chmod u+w) to record decisions.`,
            );
          }
        }
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

  /**
   * Run `fn` holding `<real file>.lock` (see `withFileLock`). Reads and appends of this process are
   * already serialised by `serial`, so this only ever waits for ANOTHER process.
   */
  private withLock<T>(fn: () => Promise<T>): Promise<T> {
    return withFileLock(this.lockPath, { waitMs: this.lockWaitMs, staleMs: this.lockStaleMs, heartbeatMs: this.lockHeartbeatMs, what: this.name }, fn);
  }
}

/** One look at a lock file: everything about it that a live holder changes (identity, heartbeat, content). */
export interface LockObservation {
  /** dev:ino:mtime:size:content - two observations with the same key saw the same, untouched lock. */
  key: string;
  raw: string;
  info: LockInfo | null;
}

/**
 * Read a lock file. Content and stat come from ONE open file descriptor, so they describe the same
 * file. null when there is no lock file; throws (with the OS reason) when it exists but cannot be
 * read (a directory, no permission).
 */
export async function observeLock(lock: string): Promise<LockObservation | null> {
  let fh: FileHandle;
  try {
    fh = await open(lock, "r");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw e;
  }
  try {
    const st = await fh.stat();
    if (!st.isFile()) throw new Error("it is not a regular file");
    const raw = await fh.readFile("utf8");
    let info: LockInfo | null = null;
    try {
      const o = JSON.parse(raw) as Partial<LockInfo>;
      if (typeof o.pid === "number" && typeof o.host === "string" && typeof o.token === "string") info = o as LockInfo;
    } catch {
      // being written, or not ours
    }
    return { key: `${st.dev}:${st.ino}:${st.mtimeMs}:${st.size}:${raw}`, raw, info };
  } finally {
    await fh.close();
  }
}

/**
 * Hold `<lock>.guard` (O_EXCL) while `fn` runs. Every unlink of a lock file (breaking a stale one,
 * releasing one's own) happens under this guard, so between re-reading the lock and unlinking it no
 * other process can unlink it, and therefore none can create a new one in its place: the lock that is
 * unlinked is exactly the one that was re-read. The guard is held for one read and one unlink
 * (milliseconds), so a guard whose state has not changed for GUARD_STALE_MS (on this process's
 * monotonic clock) is taken to be left by a process that crashed inside it, and removed. Returns
 * null when the guard could not be had within `waitMs`.
 */
async function underGuard<T>(lock: string, waitMs: number, fn: () => Promise<T>): Promise<T | null> {
  const guard = `${lock}.guard`;
  const deadline = performance.now() + waitMs;
  let seen: { key: string; since: number } | null = null;
  for (;;) {
    let fh: FileHandle | null = null;
    try {
      fh = await open(guard, "wx");
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw new Error(`could not create ${guard}: ${(e as Error).message}`);
    }
    if (fh) {
      try {
        return await fn();
      } finally {
        await fh.close().catch(() => {});
        await unlink(guard).catch(() => {});
      }
    }
    try {
      const st = await stat(guard);
      const key = `${st.dev}:${st.ino}:${st.mtimeMs}`;
      if (seen?.key !== key) seen = { key, since: performance.now() };
      else if (performance.now() - seen.since >= GUARD_STALE_MS) {
        await unlink(guard).catch(() => {}); // residual: see the module docstring
        seen = null;
        continue;
      }
    } catch {
      seen = null; // released meanwhile
    }
    if (performance.now() >= deadline) return null;
    await sleep(2);
  }
}

/**
 * Remove `lock` only if it is still exactly what `expected` says (`removeLock(lock, (o) => o.key ===
 * judged.key)` for a stale lock, `(o) => o.info?.token === mine` for one's own). The re-read and the
 * unlink happen under `<lock>.guard`. "removed": it was unlinked; "changed": it is not the expected
 * lock (left alone); "gone": there is no lock; "busy": the guard could not be had within `guardWaitMs`
 * (nothing was done). Throws when the guard cannot be created or the unlink fails (the OS reason).
 */
export async function removeLock(
  lock: string,
  expected: (o: LockObservation) => boolean,
  guardWaitMs = GUARD_WAIT_MS,
): Promise<"removed" | "changed" | "gone" | "busy"> {
  const r = await underGuard(lock, guardWaitMs, async () => {
    const now = await observeLock(lock).catch(() => undefined);
    if (now === null) return "gone" as const;
    if (now === undefined || !expected(now)) return "changed" as const;
    await unlink(lock);
    return "removed" as const;
  });
  return r ?? "busy";
}

/**
 * Run `fn` holding `lock`, created with O_EXCL and holding `{pid, host, token, at}`.
 *
 * - The holder keeps the lock alive: every `heartbeatMs` it sets the lock's mtime through its own
 *   open descriptor (so it can only ever touch its own lock file, never one that replaced it).
 * - A lock is stale when its writer is on this host (same hostname) and its pid is not running, or
 *   when nothing about it (content, mtime, identity) has changed for `staleMs`, measured on THIS
 *   process's monotonic clock while waiting (so no clock is compared with another machine's). A
 *   stale lock is removed with `removeLock`, only if it is still the one judged stale.
 * - Every turn of the loop that does not get the lock (held, unreadable, released meanwhile, just
 *   broken, guard busy) goes through one deadline check and one backoff sleep, so the wait always
 *   ends: after `waitMs` the call fails with a message naming the lock file and why.
 * - Release removes the lock only if it still holds this holder's token. If that cannot be done (the
 *   guard is busy) the lock is left; it stops heartbeating and so goes stale for everyone else.
 *
 * `staleMs` must be below `waitMs` for a waiter to ever break a lock by observation.
 */
export async function withFileLock<T>(
  lock: string,
  opts: { waitMs: number; staleMs: number; heartbeatMs: number; what?: string },
  fn: () => Promise<T>,
): Promise<T> {
  const what = opts.what ?? basename(lock);
  const info: LockInfo = { pid: process.pid, host: hostname(), token: randomBytes(8).toString("hex"), at: new Date().toISOString() };
  const deadline = performance.now() + opts.waitMs;
  let delay = 5;
  let seen: { key: string; since: number } | null = null;
  let why = "";
  let fh: FileHandle | null = null;
  for (;;) {
    try {
      fh = await open(lock, "wx");
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EEXIST") {
        throw new DecisionsFileError(`nothing was written: could not create the lock file ${lock}: ${(e as Error).message}`);
      }
    }
    if (fh) {
      try {
        await fh.writeFile(JSON.stringify(info));
        break;
      } catch (e) {
        // our own lock, just created and never valid: removed only if it is still that file
        const id = await fh.stat().then((st) => `${st.dev}:${st.ino}:`, () => null);
        await fh.close().catch(() => {});
        if (id) await removeLock(lock, (o) => o.key.startsWith(id)).catch(() => {});
        throw new DecisionsFileError(`nothing was written: could not write the lock file ${lock}: ${(e as Error).message}`);
      }
    }
    let held: LockObservation | null = null;
    try {
      held = await observeLock(lock);
      why = "";
    } catch (e) {
      why = `the lock file ${lock} cannot be read (${(e as Error).message})`;
    }
    if (held) {
      const now = performance.now();
      if (seen?.key !== held.key) seen = { key: held.key, since: now };
      const ownerGone = !!held.info && held.info.host === hostname() && !pidAlive(held.info.pid);
      const who = held.info ? `pid ${held.info.pid} on ${held.info.host}, since ${held.info.at}` : "an unknown writer";
      why = `${what} is locked by another writer (${who})`;
      if (ownerGone || now - seen.since >= opts.staleMs) {
        const judged = held.key;
        try {
          const r = await removeLock(lock, (o) => o.key === judged, Math.max(0, Math.min(GUARD_WAIT_MS, deadline - performance.now())));
          if (r === "removed" || r === "gone") seen = null;
          if (r === "busy") why = `${what} is locked by a writer that looks stale, but ${lock}.guard is held by another process`;
        } catch (e) {
          why = `the stale lock file ${lock} cannot be removed (${(e as Error).message})`;
        }
      }
    }
    // the one place a turn that did not get the lock ends: deadline, then backoff
    if (performance.now() >= deadline) {
      throw new DecisionsFileError(
        `nothing was written: ${why || `${what} is locked by another writer`}; gave up after ${opts.waitMs / 1000} s. ` +
          `If no other unLoaded server or tool is writing it, delete ${lock} and try again.`,
      );
    }
    await sleep(delay);
    delay = Math.min(delay * 2, 100);
  }
  if (!fh) throw new DecisionsFileError(`nothing was written: could not take the lock file ${lock}`); // the loop only breaks holding it
  const held: FileHandle = fh;
  let beat: Promise<unknown> = Promise.resolve();
  const timer = setInterval(() => {
    beat = beat.then(() => held.utimes(new Date(), new Date())).catch(() => {});
  }, opts.heartbeatMs);
  timer.unref?.();
  try {
    return await fn();
  } finally {
    clearInterval(timer);
    await beat;
    await held.close().catch(() => {});
    await removeLock(lock, (o) => o.info?.token === info.token).catch(() => {});
  }
}

export type { DecisionAction };
