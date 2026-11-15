"""SQLite revision store for BOTH paths (IFC model + calc package, and drawing sets).

Every ingest is an immutable REVISION; nothing is updated in place. Store version 2 (F2).

Shared tables (both paths)
  project          one per IFC project (kind 'ifc') or drawing set (kind 'drawing-set', slug = set id);
                   head_model_rev / head_calc_rev kept for the IFC path's existing responses
  document         every source document, CONTENT-ADDRESSED by sha256 (kind drawing / calc / ifc ...),
                   raw bytes in blobs/<sha256>.<ext>
  revision         one row per ingest or build. IFC path: kind 'model' | 'calcs' (one document each).
                   Drawing-set path: 'set' (plans + calc PDFs -> graph), 'records', 'connections',
                   'integrated'. parent = previous head of that kind; producer_json = the engine /
                   rule versions and declared confidences of the code that produced it
  revision_doc     which documents a revision read (doc key -> sha256)
  head             current revision per (project, kind)
  artifact         an output file of a revision (graph.json, integrated.json, model.ifc ...),
                   content-addressed in blobs/ - the existing API responses are served from these
  fact             the schema (calcgraph.schema) facts of a revision or mapping run, keyed by their
                   STABLE schema id: body_json + prov_json (provenance is stored with every fact),
                   body_hash (data only) and content_hash (data + provenance). A diff between two
                   revisions of one kind is a key join on (coll, id) comparing body_hash.
  calibration      sheet calibrations (named frames) of a revision
  decision         APPEND-ONLY human decisions keyed by (GlobalId, calc_key) - not by revision -
                   so they carry forward to every later revision

IFC-path detail tables (the producer's native records, keyed by revision; unchanged from v1)
  element, element_edge, page, calc (params_json now holds the calc's title box), mapping_run,
  link, calc_edge

Opening a v1 store migrates it in place (one transaction, backup at calcgraph.sqlite.pre-f2.bak):
revision ids, decisions and every v1 row are kept; documents, heads, title boxes are backfilled.
Schema facts of migrated revisions are backfilled by revstore.open_store().
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
STORE_VERSION = 2

IFC_KINDS = ("model", "calcs")
SET_KINDS = ("set", "records", "connections", "integrated")
REVISION_KINDS = IFC_KINDS + SET_KINDS
# the column sets the v1 API returned - legacy responses select exactly these
LEGACY_PROJECT_COLS = "id, name, created_at, head_model_rev, head_calc_rev"
LEGACY_REV_COLS = "id, project_id, kind, parent_id, seq, label, source_name, sha256, blob, created_at, meta_json"

DETAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS element(
  revision_id INTEGER NOT NULL REFERENCES revision(id), global_id TEXT NOT NULL, express_id INTEGER,
  ifc_type TEXT, cat TEXT, mark TEXT, name TEXT, type_name TEXT, profile TEXT, storey TEXT,
  params_json TEXT NOT NULL, geom_json TEXT, content_hash TEXT NOT NULL,
  PRIMARY KEY(revision_id, global_id));
CREATE TABLE IF NOT EXISTS element_edge(
  revision_id INTEGER NOT NULL REFERENCES revision(id), src TEXT NOT NULL, dst TEXT NOT NULL,
  kind TEXT NOT NULL, rule TEXT, evidence_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(revision_id, src, dst, kind));
CREATE TABLE IF NOT EXISTS page(
  revision_id INTEGER NOT NULL REFERENCES revision(id), n INTEGER NOT NULL, text TEXT NOT NULL,
  words_json TEXT NOT NULL, width REAL, height REAL, scanned INTEGER NOT NULL,
  PRIMARY KEY(revision_id, n));
CREATE TABLE IF NOT EXISTS calc(
  revision_id INTEGER NOT NULL REFERENCES revision(id), calc_key TEXT NOT NULL, ord INTEGER NOT NULL,
  title TEXT, software TEXT, cat TEXT, pages_json TEXT NOT NULL, scanned INTEGER NOT NULL, front INTEGER NOT NULL,
  content_hash TEXT NOT NULL, params_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(revision_id, calc_key));
CREATE TABLE IF NOT EXISTS mapping_run(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, model_rev INTEGER NOT NULL, calc_rev INTEGER NOT NULL,
  engine_version TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS link(
  run_id INTEGER NOT NULL REFERENCES mapping_run(id), global_id TEXT NOT NULL, calc_key TEXT NOT NULL,
  conf REAL NOT NULL, tier TEXT NOT NULL, rule TEXT, page INTEGER, token TEXT, evidence_json TEXT NOT NULL,
  PRIMARY KEY(run_id, global_id, calc_key));
CREATE TABLE IF NOT EXISTS calc_edge(
  run_id INTEGER NOT NULL REFERENCES mapping_run(id), src TEXT NOT NULL, dst TEXT NOT NULL,
  rules_json TEXT NOT NULL, evidence_json TEXT NOT NULL, PRIMARY KEY(run_id, src, dst));
CREATE TABLE IF NOT EXISTS decision(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, global_id TEXT NOT NULL, calc_key TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('confirm','reject','manual','undo')), actor TEXT, note TEXT,
  at TEXT NOT NULL, model_rev INTEGER, calc_rev INTEGER);
CREATE INDEX IF NOT EXISTS ix_decision ON decision(project_id, global_id, calc_key, id);
CREATE INDEX IF NOT EXISTS ix_link_run ON link(run_id);
"""

REVISION_DDL = """
CREATE TABLE {name}(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project(id), kind TEXT NOT NULL,
  parent_id INTEGER REFERENCES revision(id), seq INTEGER NOT NULL, label TEXT, source_name TEXT,
  sha256 TEXT, blob TEXT, created_at TEXT NOT NULL, meta_json TEXT NOT NULL DEFAULT '{{}}',
  created_by TEXT NOT NULL DEFAULT 'ingest', producer_json TEXT NOT NULL DEFAULT '{{}}', facts_at TEXT)"""

SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS document(
  sha256 TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, pages INTEGER, role TEXT NOT NULL DEFAULT '',
  blob TEXT, bytes INTEGER, source_path TEXT, first_seen TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revision_doc(
  revision_id INTEGER NOT NULL REFERENCES revision(id), doc_key TEXT NOT NULL,
  doc_sha TEXT NOT NULL REFERENCES document(sha256), role TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(revision_id, doc_key));
CREATE TABLE IF NOT EXISTS head(
  project_id INTEGER NOT NULL REFERENCES project(id), kind TEXT NOT NULL,
  revision_id INTEGER NOT NULL REFERENCES revision(id), PRIMARY KEY(project_id, kind));
CREATE TABLE IF NOT EXISTS artifact(
  revision_id INTEGER NOT NULL REFERENCES revision(id), name TEXT NOT NULL, sha256 TEXT NOT NULL,
  bytes INTEGER NOT NULL, media_type TEXT NOT NULL, PRIMARY KEY(revision_id, name));
CREATE TABLE IF NOT EXISTS fact(
  scope TEXT NOT NULL CHECK(scope IN ('revision','run')), scope_id INTEGER NOT NULL, coll TEXT NOT NULL,
  id TEXT NOT NULL, body_json TEXT NOT NULL, prov_json TEXT NOT NULL, body_hash TEXT NOT NULL,
  content_hash TEXT NOT NULL, supplied TEXT NOT NULL DEFAULT '', PRIMARY KEY(scope, scope_id, coll, id));
CREATE INDEX IF NOT EXISTS ix_fact_id ON fact(coll, id);
CREATE TABLE IF NOT EXISTS calibration(
  revision_id INTEGER NOT NULL REFERENCES revision(id), key TEXT NOT NULL, body_json TEXT NOT NULL,
  PRIMARY KEY(revision_id, key));
"""

MEDIA = {".json": "application/json", ".ifc": "application/x-step", ".pdf": "application/pdf"}


HEAD = object()   # add_revision(parent=HEAD): the parent is the current head of that kind


def now_et() -> str:
    return datetime.now(ET).isoformat(timespec="seconds")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def content_hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Store:
    def __init__(self, root: str):
        self.root = root
        os.makedirs(os.path.join(root, "blobs"), exist_ok=True)
        path = os.path.join(root, "calcgraph.sqlite")
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        legacy = bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='revision'").fetchone())
        if legacy and version < STORE_VERSION:
            self.db.close()
            bak = path + ".pre-f2.bak"
            if not os.path.exists(bak):
                shutil.copyfile(path, bak)
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self._migrate_v1()
        elif not legacy:
            self.db.executescript(
                "CREATE TABLE project(id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL,"
                " head_model_rev INTEGER, head_calc_rev INTEGER, kind TEXT NOT NULL DEFAULT 'ifc', slug TEXT UNIQUE);"
                + REVISION_DDL.format(name="revision") + ";" + DETAIL_SCHEMA + SHARED_SCHEMA
                + "ALTER TABLE mapping_run ADD COLUMN facts_at TEXT;"
                + "ALTER TABLE mapping_run ADD COLUMN producer_json TEXT NOT NULL DEFAULT '{}';"
                + f"PRAGMA user_version = {STORE_VERSION};")
        self.db.execute("PRAGMA foreign_keys = ON")

    # ---------------- v1 -> v2 migration ----------------
    def _migrate_v1(self) -> None:
        """In place, one transaction. Keeps every v1 row and revision id; nothing is rewritten
        except the revision table's CHECK(kind IN ('model','calcs')), which a drawing-set
        revision would violate (the table is rebuilt with identical rows)."""
        from .segment import title_box
        db = self.db
        db.isolation_level = None  # explicit transaction control (executescript would COMMIT mid-way)
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("BEGIN")
        try:
            n_rev = db.execute("SELECT COUNT(*) FROM revision").fetchone()[0]
            n_dec = db.execute("SELECT COUNT(*) FROM decision").fetchone()[0]
            db.execute("ALTER TABLE project ADD COLUMN kind TEXT NOT NULL DEFAULT 'ifc'")
            db.execute("ALTER TABLE project ADD COLUMN slug TEXT")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_project_slug ON project(slug)")
            db.execute(REVISION_DDL.format(name="revision_v2"))
            db.execute(f"INSERT INTO revision_v2({LEGACY_REV_COLS}) SELECT {LEGACY_REV_COLS} FROM revision")
            db.execute("DROP TABLE revision")
            db.execute("ALTER TABLE revision_v2 RENAME TO revision")
            db.execute("ALTER TABLE mapping_run ADD COLUMN facts_at TEXT")
            db.execute("ALTER TABLE mapping_run ADD COLUMN producer_json TEXT NOT NULL DEFAULT '{}'")
            for stmt in filter(str.strip, SHARED_SCHEMA.split(";")):
                db.execute(stmt)
            # documents: one per distinct sha256, content-addressed blob kept where it is
            for r in db.execute("SELECT * FROM revision ORDER BY id").fetchall():
                blob = os.path.join(self.root, r["blob"])
                db.execute("INSERT OR IGNORE INTO document(sha256, kind, name, pages, role, blob, bytes, source_path,"
                           " first_seen) VALUES (?,?,?,?,?,?,?,?,?)",
                           (r["sha256"], "ifc" if r["kind"] == "model" else "calc", r["source_name"] or r["blob"],
                            json.loads(r["meta_json"]).get("page_count"), "", r["blob"],
                            os.path.getsize(blob) if os.path.exists(blob) else None, None, r["created_at"]))
                db.execute("INSERT INTO revision_doc VALUES (?,?,?,?)", (r["id"], "file", r["sha256"], r["kind"]))
            for p in db.execute("SELECT * FROM project").fetchall():
                for kind, col in (("model", "head_model_rev"), ("calcs", "head_calc_rev")):
                    if p[col]:
                        db.execute("INSERT INTO head VALUES (?,?,?)", (p["id"], kind, p[col]))
            # calc title boxes, recomputed from the stored page words by the producer's own function
            pages = {(r["revision_id"], r["n"]): {"n": r["n"], "text": r["text"], "words": json.loads(r["words_json"]),
                                                  "width": r["width"], "height": r["height"]}
                     for r in db.execute("SELECT * FROM page")}
            for c in db.execute("SELECT revision_id, calc_key, title, pages_json, scanned, front FROM calc").fetchall():
                first = (json.loads(c["pages_json"]) or [None])[0]
                pg = pages.get((c["revision_id"], first))
                if not pg:
                    continue
                tb = title_box(pg, c["title"], bool(c["scanned"]), bool(c["front"]))
                db.execute("UPDATE calc SET params_json=? WHERE revision_id=? AND calc_key=?",
                           (json.dumps({"title_box": tb, "title_box_backfilled": now_et()}), c["revision_id"],
                            c["calc_key"]))
            assert db.execute("SELECT COUNT(*) FROM revision").fetchone()[0] == n_rev
            assert db.execute("SELECT COUNT(*) FROM decision").fetchone()[0] == n_dec
            bad = db.execute("PRAGMA foreign_key_check").fetchall()
            if bad:
                raise RuntimeError(f"foreign key check failed after migration: {[tuple(b) for b in bad[:5]]}")
            db.execute(f"PRAGMA user_version = {STORE_VERSION}")
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        finally:
            db.execute("PRAGMA foreign_keys = ON")
            db.isolation_level = ""

    # ---------------- documents (content-addressed) ----------------
    def put_document(self, path: str, kind: str, name: str, pages: int | None = None, role: str = "",
                     copy: bool = True, sha: str | None = None) -> str:
        sha = sha or sha256_file(path)
        ext = os.path.splitext(name)[1].lower() or os.path.splitext(path)[1].lower()
        blob = os.path.join("blobs", sha + ext) if copy else None
        if blob and not os.path.exists(os.path.join(self.root, blob)):
            shutil.copyfile(path, os.path.join(self.root, blob))
        self.db.execute("INSERT OR IGNORE INTO document(sha256, kind, name, pages, role, blob, bytes, source_path,"
                        " first_seen) VALUES (?,?,?,?,?,?,?,?,?)",
                        (sha, kind, name, pages, role, blob, os.path.getsize(path), os.path.abspath(path), now_et()))
        return sha

    def document(self, sha: str) -> dict | None:
        r = self.db.execute("SELECT * FROM document WHERE sha256=?", (sha,)).fetchone()
        return dict(r) if r else None

    def revision_docs(self, rid: int) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT rd.doc_key, rd.role AS doc_role, d.* FROM revision_doc rd JOIN document d ON d.sha256 = rd.doc_sha"
            " WHERE rd.revision_id=? ORDER BY rd.doc_key", (rid,))]

    # ---------------- projects / revisions ----------------
    def ensure_project(self, name: str = "Default") -> int:
        r = self.db.execute("SELECT id FROM project WHERE kind='ifc' ORDER BY id LIMIT 1").fetchone()
        if r:
            return r["id"]
        cur = self.db.execute("INSERT INTO project(name, created_at) VALUES (?,?)", (name, now_et()))
        self.db.commit()
        return cur.lastrowid

    def ensure_set_project(self, slug: str, name: str) -> int:
        r = self.db.execute("SELECT id, name FROM project WHERE slug=?", (slug,)).fetchone()
        if r:
            if r["name"] != name:
                self.db.execute("UPDATE project SET name=? WHERE id=?", (name, r["id"]))
            return r["id"]
        cur = self.db.execute("INSERT INTO project(name, created_at, kind, slug) VALUES (?,?,?,?)",
                              (name, now_et(), "drawing-set", slug))
        return cur.lastrowid

    def set_project(self, slug: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM project WHERE slug=? AND kind='drawing-set'", (slug,)).fetchone()

    def legacy_projects(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(f"SELECT {LEGACY_PROJECT_COLS} FROM project WHERE kind='ifc' ORDER BY id")]

    def all_projects(self) -> list[dict]:
        return [dict(r) | {"heads": self.heads(r["id"])} for r in self.db.execute("SELECT * FROM project ORDER BY id")]

    def project(self, pid: int) -> sqlite3.Row:
        r = self.db.execute(f"SELECT {LEGACY_PROJECT_COLS} FROM project WHERE id=?", (pid,)).fetchone()
        if not r:
            raise KeyError(pid)
        return r

    def _next(self, pid: int, kind: str) -> tuple[int | None, int]:
        head = self.head(pid, kind)
        seq = self.db.execute("SELECT COALESCE(MAX(seq),0) FROM revision WHERE project_id=? AND kind=?",
                              (pid, kind)).fetchone()[0] + 1
        return head, seq

    def add_revision(self, pid: int, kind: str, src_path: str, source_name: str, label: str | None, meta: dict,
                     producer: dict | None = None, parent: int | None | object = HEAD) -> int:
        """IFC path: one document per revision (the IFC or the calc PDF).

        parent = the revision this one's content was DERIVED FROM. Default HEAD (the current head of
        that kind - right for a sequence of uploads). A producer that computes a revision from some
        other revision (the v2 move API builds every move from the base design) passes that one, or
        None for a new root, so the parent -> revision diff is exactly the change it made."""
        sha = self.put_document(src_path, "ifc" if kind == "model" else "calc", source_name,
                                meta.get("page_count"))
        blob = self.document(sha)["blob"]
        head, seq = self._next(pid, kind)
        if parent is not HEAD:
            if parent is not None:
                pr = self.db.execute("SELECT project_id, kind FROM revision WHERE id=?", (parent,)).fetchone()
                if not pr or pr["project_id"] != pid or pr["kind"] != kind:
                    raise ValueError(f"parent {parent} is not a {kind} revision of project {pid}")
            head = parent
        cur = self.db.execute(
            "INSERT INTO revision(project_id, kind, parent_id, seq, label, source_name, sha256, blob, created_at,"
            " meta_json, producer_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pid, kind, head, seq, label, source_name, sha, blob, now_et(), json.dumps(meta),
             json.dumps(producer or {}, sort_keys=True)))
        self.db.execute("INSERT INTO revision_doc VALUES (?,?,?,?)", (cur.lastrowid, "file", sha, kind))
        return cur.lastrowid

    def add_set_revision(self, pid: int, kind: str, label: str, docs: dict[str, tuple[str, str]], meta: dict,
                         producer: dict | None = None, created_by: str = "ingest") -> int:
        """Drawing-set path: a build that read several documents. docs: doc key -> (sha256, role)."""
        if kind not in SET_KINDS:
            raise ValueError(f"not a drawing-set revision kind: {kind}")
        head, seq = self._next(pid, kind)
        cur = self.db.execute(
            "INSERT INTO revision(project_id, kind, parent_id, seq, label, source_name, created_at, meta_json,"
            " created_by, producer_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, kind, head, seq, label, meta.get("source_name", ""), now_et(), json.dumps(meta, sort_keys=True),
             created_by, json.dumps(producer or {}, sort_keys=True)))
        rid = cur.lastrowid
        self.db.executemany("INSERT INTO revision_doc VALUES (?,?,?,?)",
                            [(rid, k, sha, role) for k, (sha, role) in sorted(docs.items())])
        return rid

    def set_head(self, pid: int, kind: str, rid: int) -> None:
        if kind in IFC_KINDS:
            col = "head_model_rev" if kind == "model" else "head_calc_rev"
            self.db.execute(f"UPDATE project SET {col}=? WHERE id=?", (rid, pid))
        self.db.execute("INSERT INTO head VALUES (?,?,?) ON CONFLICT(project_id, kind) DO UPDATE SET"
                        " revision_id=excluded.revision_id", (pid, kind, rid))

    def head(self, pid: int, kind: str) -> int | None:
        r = self.db.execute("SELECT revision_id FROM head WHERE project_id=? AND kind=?", (pid, kind)).fetchone()
        return r[0] if r else None

    def heads(self, pid: int) -> dict[str, int]:
        return {r["kind"]: r["revision_id"] for r in self.db.execute("SELECT * FROM head WHERE project_id=?", (pid,))}

    def revision(self, rid: int) -> sqlite3.Row:
        r = self.db.execute(f"SELECT {LEGACY_REV_COLS} FROM revision WHERE id=?", (rid,)).fetchone()
        if not r:
            raise KeyError(rid)
        return r

    def revision_full(self, rid: int) -> dict:
        r = self.db.execute("SELECT * FROM revision WHERE id=?", (rid,)).fetchone()
        if not r:
            raise KeyError(rid)
        d = dict(r)
        d["meta"] = json.loads(d.pop("meta_json"))
        d["producer"] = json.loads(d.pop("producer_json"))
        d["documents"] = self.revision_docs(rid)
        d["artifacts"] = [dict(a) for a in self.db.execute("SELECT name, sha256, bytes, media_type FROM artifact"
                                                           " WHERE revision_id=? ORDER BY name", (rid,))]
        d["facts"] = dict(self.db.execute("SELECT coll, COUNT(*) FROM fact WHERE scope='revision' AND scope_id=?"
                                          " GROUP BY coll", (rid,)).fetchall())
        return d

    def revisions(self, pid: int) -> list[dict]:
        """IFC-path revision list exactly as the v1 API returned it."""
        rows = self.db.execute(f"SELECT {LEGACY_REV_COLS} FROM revision WHERE project_id=? AND kind IN ('model','calcs')"
                               " ORDER BY id", (pid,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["meta"] = json.loads(d.pop("meta_json"))
            if r["kind"] == "model":
                d["count"] = self.db.execute("SELECT COUNT(*) FROM element WHERE revision_id=?", (r["id"],)).fetchone()[0]
            else:
                d["count"] = self.db.execute("SELECT COUNT(*) FROM calc WHERE revision_id=?", (r["id"],)).fetchone()[0]
            out.append(d)
        return out

    def all_revisions(self, pid: int) -> list[dict]:
        return [self.revision_full(r["id"]) for r in
                self.db.execute("SELECT id FROM revision WHERE project_id=? ORDER BY id", (pid,))]

    def blob_path(self, rid: int) -> str:
        return os.path.join(self.root, self.revision(rid)["blob"])

    # ---------------- artifacts (content-addressed outputs) ----------------
    def put_artifact(self, rid: int, name: str, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        ext = os.path.splitext(name)[1].lower()
        dst = os.path.join(self.root, "blobs", sha + ext)
        if not os.path.exists(dst):
            tmp = dst + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dst)
        self.db.execute("INSERT INTO artifact VALUES (?,?,?,?,?)", (rid, name, sha, len(data), MEDIA.get(ext, "application/octet-stream")))
        return sha

    def artifact(self, rid: int, name: str) -> dict | None:
        r = self.db.execute("SELECT * FROM artifact WHERE revision_id=? AND name=?", (rid, name)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["path"] = os.path.join(self.root, "blobs", r["sha256"] + os.path.splitext(name)[1].lower())
        return d

    # ---------------- schema facts ----------------
    def put_facts(self, scope: str, scope_id: int, facts: list[tuple[str, object]]) -> int:
        """facts: (collection, pydantic Fact). Provenance is stored with every fact."""
        rows = []
        for coll, f in facts:
            d = f.model_dump(mode="json")
            prov = d.pop("provenance")
            body_hash = content_hash(d)
            rows.append((scope, scope_id, coll, d["id"], json.dumps(d, sort_keys=True), json.dumps(prov, sort_keys=True),
                         body_hash, content_hash([d, {k: v for k, v in prov.items() if k != "at"}]),
                         ",".join(prov.get("adapter_supplied") or [])))
        self.db.executemany("INSERT INTO fact VALUES (?,?,?,?,?,?,?,?,?)", rows)
        tbl = "revision" if scope == "revision" else "mapping_run"
        self.db.execute(f"UPDATE {tbl} SET facts_at=? WHERE id=?", (now_et(), scope_id))
        return len(rows)

    def put_calibrations(self, rid: int, cals: list) -> None:
        self.db.executemany("INSERT INTO calibration VALUES (?,?,?)", [
            (rid, f"{c.sheet.doc_sha}:{c.sheet.page}", c.model_dump_json()) for c in cals])

    def calibrations(self, rid: int) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT body_json FROM calibration WHERE revision_id=? ORDER BY key", (rid,))]

    def facts(self, scope: str, scope_id: int) -> list[dict]:
        out = []
        for r in self.db.execute("SELECT coll, body_json, prov_json FROM fact WHERE scope=? AND scope_id=? ORDER BY coll, id",
                                 (scope, scope_id)):
            d = json.loads(r["body_json"])
            d["provenance"] = json.loads(r["prov_json"])
            out.append((r["coll"], d))
        return out

    def diff_facts(self, scope: str, a: int, b: int) -> dict:
        """Key join of two snapshots' facts on (coll, id): added / removed / changed (body_hash),
        plus facts whose data is unchanged but whose provenance changed."""
        q = "SELECT coll, id, body_hash, content_hash FROM fact WHERE scope=? AND scope_id=?"
        fa = {(r[0], r[1]): (r[2], r[3]) for r in self.db.execute(q, (scope, a))}
        fb = {(r[0], r[1]): (r[2], r[3]) for r in self.db.execute(q, (scope, b))}
        out: dict[str, dict] = {}

        def bucket(coll):
            return out.setdefault(coll, {"added": [], "removed": [], "changed": [], "provenance_changed": [], "same": 0})
        for k in sorted(fa.keys() - fb.keys()):
            bucket(k[0])["removed"].append(k[1])
        for k in sorted(fb.keys() - fa.keys()):
            bucket(k[0])["added"].append(k[1])
        for k in sorted(fa.keys() & fb.keys()):
            if fa[k][0] != fb[k][0]:
                bucket(k[0])["changed"].append(k[1])
            elif fa[k][1] != fb[k][1]:
                bucket(k[0])["provenance_changed"].append(k[1])
            else:
                bucket(k[0])["same"] += 1
        return out

    # ---------------- model snapshots ----------------
    def put_elements(self, rid: int, elements: list[dict], edges: list[dict]) -> None:
        rows = []
        for e in elements:
            g = e.get("geom")
            snap = {k: e[k] for k in ("ifc_type", "mark", "name", "type_name", "profile", "storey", "params")}
            snap["bbox"] = [[round(v, 3) for v in g["min"]], [round(v, 3) for v in g["max"]]] if g else None
            rows.append((rid, e["global_id"], e.get("express_id"), e["ifc_type"], e["cat"], e["mark"], e["name"],
                         e["type_name"], e["profile"], e["storey"], json.dumps(e["params"], sort_keys=True),
                         json.dumps(g) if g else None, content_hash(snap)))
        self.db.executemany("INSERT INTO element VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        self.db.executemany(
            "INSERT INTO element_edge(revision_id, src, dst, kind, rule, evidence_json) VALUES (?,?,?,?,?,?)",
            [(rid, x["src"], x["dst"], x["kind"], x["rule"], json.dumps({"gap_m": x.get("gap_m")})) for x in edges])

    def elements(self, rid: int) -> list[dict]:
        out = []
        for r in self.db.execute("SELECT * FROM element WHERE revision_id=? ORDER BY global_id", (rid,)):
            d = dict(r)
            d["params"] = json.loads(d.pop("params_json"))
            g = d.pop("geom_json")
            d["geom"] = json.loads(g) if g else None
            out.append(d)
        return out

    def element_edges(self, rid: int) -> list[dict]:
        return [{"src": r["src"], "dst": r["dst"], "kind": r["kind"], "rule": r["rule"], **json.loads(r["evidence_json"])}
                for r in self.db.execute("SELECT * FROM element_edge WHERE revision_id=? ORDER BY src, dst", (rid,))]

    # ---------------- calc package snapshots ----------------
    def put_calcs(self, rid: int, pages: list[dict], calcs: list[dict]) -> None:
        self.db.executemany("INSERT INTO page VALUES (?,?,?,?,?,?,?)", [
            (rid, p["n"], p["text"], json.dumps(p["words"]), p["width"], p["height"], int(len(p["text"].strip()) < 25))
            for p in pages])
        self.db.executemany("INSERT INTO calc VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
            (rid, c["key"], i, c["title"], c["software"], c["cat"], json.dumps(c["pages"]), int(c["scanned"]), int(c["front"]),
             content_hash([c["title"], c["text"]]), json.dumps({"title_box": c.get("title_box"), "cats": c.get("cats", [])}))
            for i, c in enumerate(calcs)])

    def pages(self, rid: int) -> list[dict]:
        return [{"n": r["n"], "text": r["text"], "words": json.loads(r["words_json"]), "width": r["width"],
                 "height": r["height"], "scanned": bool(r["scanned"])}
                for r in self.db.execute("SELECT * FROM page WHERE revision_id=? ORDER BY n", (rid,))]

    def calcs(self, rid: int, with_text: bool = False, with_params: bool = False) -> list[dict]:
        pages = {p["n"]: p["text"] for p in self.pages(rid)} if with_text else {}
        out = []
        for r in self.db.execute("SELECT * FROM calc WHERE revision_id=? ORDER BY ord", (rid,)):
            c = {"key": r["calc_key"], "ord": r["ord"], "title": r["title"], "software": r["software"], "cat": r["cat"],
                 "pages": json.loads(r["pages_json"]), "scanned": bool(r["scanned"]), "front": bool(r["front"]),
                 "content_hash": r["content_hash"]}
            # every type the calc designs (segment); a revision stored before segment wrote it has only `cat`
            c["cats"] = json.loads(r["params_json"] or "{}").get("cats") or ([c["cat"]] if c["cat"] else [])
            if with_text:
                c["text"] = "\n".join(pages.get(n, "") for n in c["pages"])
            if with_params:
                c["params"] = json.loads(r["params_json"])
            out.append(c)
        return out

    # ---------------- mapping runs ----------------
    def put_run(self, pid: int, model_rev: int, calc_rev: int, engine: str, links: list[dict], calc_edges: list[dict],
                producer: dict | None = None) -> int:
        cur = self.db.execute("INSERT INTO mapping_run(project_id, model_rev, calc_rev, engine_version, created_at,"
                              " producer_json) VALUES (?,?,?,?,?,?)",
                              (pid, model_rev, calc_rev, engine, now_et(), json.dumps(producer or {}, sort_keys=True)))
        run = cur.lastrowid
        self.db.executemany("INSERT INTO link VALUES (?,?,?,?,?,?,?,?,?)", [
            (run, l["global_id"], l["calc_key"], l["conf"], l["tier"], l["rule"], l["page"], l["token"],
             json.dumps({"span": l["span"], "snippet": l["snippet"], "rects": l["rects"]})) for l in links])
        self.db.executemany("INSERT INTO calc_edge VALUES (?,?,?,?,?)", [
            (run, e["src"], e["dst"], json.dumps(e["rules"]), json.dumps(e["evidence"])) for e in calc_edges])
        return run

    _RUN_COLS = "id, project_id, model_rev, calc_rev, engine_version, created_at"

    def latest_run(self, pid: int, model_rev: int, calc_rev: int) -> sqlite3.Row | None:
        return self.db.execute(f"SELECT {self._RUN_COLS} FROM mapping_run WHERE project_id=? AND model_rev=? AND calc_rev=?"
                               " ORDER BY id DESC LIMIT 1", (pid, model_rev, calc_rev)).fetchone()

    def runs(self, pid: int) -> list[dict]:
        return [dict(r) for r in self.db.execute(f"SELECT {self._RUN_COLS} FROM mapping_run WHERE project_id=? ORDER BY id",
                                                 (pid,))]

    def links(self, run_id: int) -> list[dict]:
        out = []
        for r in self.db.execute("SELECT * FROM link WHERE run_id=?", (run_id,)):
            ev = json.loads(r["evidence_json"])
            out.append({"global_id": r["global_id"], "calc_key": r["calc_key"], "conf": r["conf"], "tier": r["tier"],
                        "rule": r["rule"], "page": r["page"], "token": r["token"], **ev, "status": "auto"})
        return out

    def stored_calc_edges(self, run_id: int) -> list[dict]:
        return [{"src": r["src"], "dst": r["dst"], "rules": json.loads(r["rules_json"]),
                 "evidence": json.loads(r["evidence_json"])}
                for r in self.db.execute("SELECT * FROM calc_edge WHERE run_id=? ORDER BY src, dst", (run_id,))]

    # ---------------- decisions (append-only) ----------------
    def add_decision(self, pid: int, gid: str, calc_key: str, action: str, actor: str | None, note: str | None) -> int:
        p = self.project(pid)
        cur = self.db.execute(
            "INSERT INTO decision(project_id, global_id, calc_key, action, actor, note, at, model_rev, calc_rev)"
            " VALUES (?,?,?,?,?,?,?,?,?)", (pid, gid, calc_key, action, actor, note, now_et(), p["head_model_rev"], p["head_calc_rev"]))
        self.db.commit()
        return cur.lastrowid

    def effective_decisions(self, pid: int) -> dict[tuple[str, str], dict]:
        out: dict[tuple[str, str], dict] = {}
        for r in self.db.execute("SELECT * FROM decision WHERE project_id=? ORDER BY id", (pid,)):
            out[(r["global_id"], r["calc_key"])] = dict(r)
        return {k: v for k, v in out.items() if v["action"] != "undo"}

    def decision_log(self, pid: int) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM decision WHERE project_id=? ORDER BY id DESC", (pid,))]

    # ---------------- diff foundation ----------------
    def compare_models(self, a: int, b: int) -> dict:
        """Element-level diff between two model revisions by GlobalId + content hash.
        Backend only - the redline UI is the next feature."""
        ha = {r["global_id"]: r for r in self.db.execute("SELECT * FROM element WHERE revision_id=?", (a,))}
        hb = {r["global_id"]: r for r in self.db.execute("SELECT * FROM element WHERE revision_id=?", (b,))}
        changed = []
        for g in sorted(ha.keys() & hb.keys()):
            if ha[g]["content_hash"] != hb[g]["content_hash"]:
                pa, pb = json.loads(ha[g]["params_json"]), json.loads(hb[g]["params_json"])
                fields = {k: [pa.get(k), pb.get(k)] for k in sorted(pa.keys() | pb.keys()) if pa.get(k) != pb.get(k)}
                for col in ("mark", "profile", "storey", "type_name"):
                    if ha[g][col] != hb[g][col]:
                        fields[col] = [ha[g][col], hb[g][col]]
                if ha[g]["geom_json"] != hb[g]["geom_json"]:
                    fields["geometry"] = ["", "moved / resized"]
                changed.append({"global_id": g, "mark": hb[g]["mark"], "fields": fields})
        ea = {(r["src"], r["dst"]) for r in self.db.execute("SELECT src, dst FROM element_edge WHERE revision_id=?", (a,))}
        eb = {(r["src"], r["dst"]) for r in self.db.execute("SELECT src, dst FROM element_edge WHERE revision_id=?", (b,))}
        return {
            "a": a, "b": b,
            "removed": [{"global_id": g, "mark": ha[g]["mark"], "cat": ha[g]["cat"]} for g in sorted(ha.keys() - hb.keys())],
            "added": [{"global_id": g, "mark": hb[g]["mark"], "cat": hb[g]["cat"]} for g in sorted(hb.keys() - ha.keys())],
            "changed": changed,
            "edges_removed": sorted(ea - eb), "edges_added": sorted(eb - ea),
        }

    def commit(self) -> None:
        self.db.commit()
