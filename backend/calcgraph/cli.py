"""calc-graph command line.

  calc-graph serve [--host 127.0.0.1] [--port 8000]   API + built frontend (<repo>/dist)
  calc-graph ingest model.ifc [calcs.pdf]             ingest into the store and print a summary
  calc-graph migrate-store                            migrate the store (backend/data/store, or CALCGRAPH_STORE)
                                                      to the current store version, backfill schema facts;
                                                      prints counts
"""
from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser(prog="calc-graph")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    i = sub.add_parser("ingest")
    i.add_argument("ifc")
    i.add_argument("pdf", nargs="?")
    sub.add_parser("migrate-store")
    a = ap.parse_args()
    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("calcgraph.api:app", host=a.host, port=a.port)
    elif a.cmd == "migrate-store":
        from . import revstore
        st = revstore.open_store()  # opening migrates a v1 store in place and backfills missing facts
        q = lambda sql: st.db.execute(sql).fetchall()  # noqa: E731
        print(f"store {revstore.store_dir()} (version {q('PRAGMA user_version')[0][0]})")
        for r in q("SELECT p.id, p.kind, COALESCE(p.slug, p.name), COUNT(r.id) FROM project p LEFT JOIN revision r"
                   " ON r.project_id = p.id GROUP BY p.id ORDER BY p.id"):
            print(f"  project {r[0]} {r[1]:12} {r[2]}: {r[3]} revisions")
        print(f"  documents {q('SELECT COUNT(*) FROM document')[0][0]}, decisions {q('SELECT COUNT(*) FROM decision')[0][0]}, "
              f"mapping runs {q('SELECT COUNT(*) FROM mapping_run')[0][0]}")
        for r in q("SELECT scope, coll, COUNT(*), SUM(supplied != '') FROM fact GROUP BY scope, coll"):
            print(f"  facts {r[0]:8} {r[1]:22} {r[2]:6}  ({r[3]} with adapter-supplied provenance)")
    elif a.cmd == "ingest":
        from .api import st
        from . import pipeline
        pid = st.ensure_project()
        pipeline.ingest_model(st, pid, a.ifc)
        if a.pdf:
            pipeline.ingest_calcs(st, pid, a.pdf)
        s = pipeline.state(st, pid)
        print(f"{len(s['elements'])} elements, {len(s['edges'])} load-path edges, {len(s['calcs'])} calcs, "
              f"{len(s['links'])} links, {len(s['calc_edges'])} calc edges; status {s['counts']}")


if __name__ == "__main__":
    main()
