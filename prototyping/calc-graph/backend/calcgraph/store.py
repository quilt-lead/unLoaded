"""SQLite store. Every ingest is an immutable REVISION; nothing is updated in place.

Tables
  project          head pointers: head_model_rev, head_calc_rev
  revision         one row per ingest (kind 'model' | 'calcs'), parent = previous head of
                   that kind, raw file kept content-addressed in data/store/blobs/<sha256>
  element          full parameter snapshot per model revision, keyed (revision, GlobalId),
                   params_json is open-ended, content_hash = hash of everything but ids
  element_edge     load-path edges of that model revision (rule + measured gap)
  page             calc package pages per calc revision (text + word boxes)
  calc             calcs per calc revision, keyed by a stable calc_key (slug of title),
                   content_hash = hash of title + text
  mapping_run      one per (model rev, calc rev) pair the mapper ran on, engine version
  link             auto links of a run (evidence: page, span, token, snippet, rects, rule)
  decision         APPEND-ONLY human decisions keyed by (GlobalId, calc_key) - not by
                   revision - so they carry forward to every later revision
  calc_edge        calc dependency edges of a run

The diff / redline feature sits on top: compare two revisions of the same kind by
key (GlobalId or calc_key) and content_hash; see compare_models().
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS project(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL,
  head_model_rev INTEGER, head_calc_rev INTEGER);
CREATE TABLE IF NOT EXISTS revision(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project(id),
  kind TEXT NOT NULL CHECK(kind IN ('model','calcs')), parent_id INTEGER REFERENCES revision(id),
  seq INTEGER NOT NULL, label TEXT, source_name TEXT, sha256 TEXT NOT NULL, blob TEXT NOT NULL,
  created_at TEXT NOT NULL, meta_json TEXT NOT NULL DEFAULT '{}');
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
        self.db = sqlite3.connect(os.path.join(root, "calcgraph.sqlite"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    # ---------------- projects / revisions ----------------
    def ensure_project(self, name: str = "Default") -> int:
        r = self.db.execute("SELECT id FROM project ORDER BY id LIMIT 1").fetchone()
        if r:
            return r["id"]
        cur = self.db.execute("INSERT INTO project(name, created_at) VALUES (?,?)", (name, now_et()))
        self.db.commit()
        return cur.lastrowid

    def project(self, pid: int) -> sqlite3.Row:
        r = self.db.execute("SELECT * FROM project WHERE id=?", (pid,)).fetchone()
        if not r:
            raise KeyError(pid)
        return r

    def add_revision(self, pid: int, kind: str, src_path: str, source_name: str, label: str | None, meta: dict) -> int:
        sha = sha256_file(src_path)
        ext = os.path.splitext(source_name)[1].lower() or (".ifc" if kind == "model" else ".pdf")
        blob = os.path.join("blobs", sha + ext)
        dst = os.path.join(self.root, blob)
        if not os.path.exists(dst):
            shutil.copyfile(src_path, dst)
        head = self.project(pid)["head_model_rev" if kind == "model" else "head_calc_rev"]
        seq = (self.db.execute("SELECT COALESCE(MAX(seq),0) FROM revision WHERE project_id=? AND kind=?", (pid, kind))
               .fetchone()[0]) + 1
        cur = self.db.execute(
            "INSERT INTO revision(project_id, kind, parent_id, seq, label, source_name, sha256, blob, created_at, meta_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, kind, head, seq, label, source_name, sha, blob, now_et(), json.dumps(meta)))
        return cur.lastrowid

    def set_head(self, pid: int, kind: str, rid: int) -> None:
        col = "head_model_rev" if kind == "model" else "head_calc_rev"
        self.db.execute(f"UPDATE project SET {col}=? WHERE id=?", (rid, pid))

    def revision(self, rid: int) -> sqlite3.Row:
        r = self.db.execute("SELECT * FROM revision WHERE id=?", (rid,)).fetchone()
        if not r:
            raise KeyError(rid)
        return r

    def revisions(self, pid: int) -> list[dict]:
        rows = self.db.execute("SELECT * FROM revision WHERE project_id=? ORDER BY id", (pid,)).fetchall()
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

    def blob_path(self, rid: int) -> str:
        return os.path.join(self.root, self.revision(rid)["blob"])

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
             content_hash([c["title"], c["text"]]), "{}") for i, c in enumerate(calcs)])

    def pages(self, rid: int) -> list[dict]:
        return [{"n": r["n"], "text": r["text"], "words": json.loads(r["words_json"]), "width": r["width"],
                 "height": r["height"], "scanned": bool(r["scanned"])}
                for r in self.db.execute("SELECT * FROM page WHERE revision_id=? ORDER BY n", (rid,))]

    def calcs(self, rid: int, with_text: bool = False) -> list[dict]:
        pages = {p["n"]: p["text"] for p in self.pages(rid)} if with_text else {}
        out = []
        for r in self.db.execute("SELECT * FROM calc WHERE revision_id=? ORDER BY ord", (rid,)):
            c = {"key": r["calc_key"], "ord": r["ord"], "title": r["title"], "software": r["software"], "cat": r["cat"],
                 "pages": json.loads(r["pages_json"]), "scanned": bool(r["scanned"]), "front": bool(r["front"]),
                 "content_hash": r["content_hash"]}
            if with_text:
                c["text"] = "\n".join(pages.get(n, "") for n in c["pages"])
            out.append(c)
        return out

    # ---------------- mapping runs ----------------
    def put_run(self, pid: int, model_rev: int, calc_rev: int, engine: str, links: list[dict], calc_edges: list[dict]) -> int:
        cur = self.db.execute("INSERT INTO mapping_run(project_id, model_rev, calc_rev, engine_version, created_at)"
                              " VALUES (?,?,?,?,?)", (pid, model_rev, calc_rev, engine, now_et()))
        run = cur.lastrowid
        self.db.executemany("INSERT INTO link VALUES (?,?,?,?,?,?,?,?,?)", [
            (run, l["global_id"], l["calc_key"], l["conf"], l["tier"], l["rule"], l["page"], l["token"],
             json.dumps({"span": l["span"], "snippet": l["snippet"], "rects": l["rects"]})) for l in links])
        self.db.executemany("INSERT INTO calc_edge VALUES (?,?,?,?,?)", [
            (run, e["src"], e["dst"], json.dumps(e["rules"]), json.dumps(e["evidence"])) for e in calc_edges])
        return run

    def latest_run(self, pid: int, model_rev: int, calc_rev: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM mapping_run WHERE project_id=? AND model_rev=? AND calc_rev=? ORDER BY id DESC"
                               " LIMIT 1", (pid, model_rev, calc_rev)).fetchone()

    def runs(self, pid: int) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM mapping_run WHERE project_id=? ORDER BY id", (pid,))]

    def links(self, run_id: int) -> list[dict]:
        out = []
        for r in self.db.execute("SELECT * FROM link WHERE run_id=?", (run_id,)):
            ev = json.loads(r["evidence_json"])
            out.append({"global_id": r["global_id"], "calc_key": r["calc_key"], "conf": r["conf"], "tier": r["tier"],
                        "rule": r["rule"], "page": r["page"], "token": r["token"], **ev, "status": "auto"})
        return out

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
