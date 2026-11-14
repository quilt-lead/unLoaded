"""The serialized element graph contract (graph_ingest) and the store's thread safety. CI only."""
import json
import threading

import pytest

from calcgraph import graph_ingest, impact
from calcgraph.store import Store


def node(i, kind, **kw):
    return {"id": i, "kind": kind, "params": kw.pop("params", {}), "source": {"format": "ifc", "nativeId": 7,
            "nativeType": kw.pop("native", "IfcBeam")}, "tags": {}, "links": [], **kw}


def graph(**over):
    g = {"format": "unloaded.element-graph", "version": 1, "meta": None,
         "levels": [{"id": "L2", "name": "Level 2", "elevation": 4.2}],
         "nodes": [node("B1", "beam", mark="2B1", name="2B1", profile="W18X35", levelId="L2",
                        params={"Attr.ObjectType": "W18X35", "Pset.Span": 6.1},
                        geometry={"bbox": {"min": [0, 0, 4], "max": [6, 0.2, 4.4]},
                                  "axis": {"start": [0, 0.1, 4.2], "end": [6, 0.1, 4.2]}}),
                   node("K1", "connection", mark="ST-1", native="IfcPlate"),
                   node("C1", "column", mark="C1", native="IfcColumn"),
                   node("F1", "fastener", native="IfcMechanicalFastener"),
                   node("X1", "stair", native="IfcStairFlight")],
         "edges": [{"id": "supports:B1->K1", "kind": "supports", "a": "B1", "b": "K1", "directed": True,
                    "evidence": [{"rule": "connection contact", "source": "inferred", "detail": {"gap_m": 0.004}}]},
                   {"id": "supports:K1->C1", "kind": "supports", "a": "K1", "b": "C1", "directed": True,
                    "evidence": [{"rule": "connection contact", "source": "inferred", "detail": {"gap_m": 0}}]},
                   {"id": "connects:B1|C1", "kind": "connects", "a": "B1", "b": "C1", "directed": False,
                    "evidence": [{"rule": "IfcRelConnectsElements", "source": "explicit", "detail": {"ifcRelId": 9}},
                                 {"rule": "bbox contact", "source": "inferred"}]}]}
    g.update(over)
    return g


def test_element_rows_from_nodes():
    els = {e["global_id"]: e for e in graph_ingest.elements(graph())}
    b = els["B1"]
    assert (b["ifc_type"], b["cat"], b["mark"], b["profile"], b["storey"], b["type_name"]) == \
        ("IfcBeam", "Beam", "2B1", "W18X35", "Level 2", "W18X35")
    assert b["params"]["Pset.Span"] == 6.1 and b["express_id"] == 7
    assert b["geom"] == {"min": [0, 0, 4], "max": [6, 0.2, 4.4], "p1": [0, 0.1, 4.2], "p2": [6, 0.1, 4.2]}
    assert els["K1"]["cat"] == "Connection" and els["F1"]["cat"] == "Connection" and els["X1"]["cat"] == "Other"
    assert els["C1"]["storey"] == "" and els["C1"]["geom"] is None


def test_load_path_is_supports_edges_and_connectivity_is_connects():
    lp = graph_ingest.load_path(graph())
    assert [(e["src"], e["dst"], e["kind"], e["rule"], e["gap_m"]) for e in lp] == [
        ("B1", "K1", "supports", "connection contact", 0.004), ("K1", "C1", "supports", "connection contact", 0)]
    assert graph_ingest.connectivity(graph()) == [
        {"a": "B1", "b": "C1", "rule": "IfcRelConnectsElements", "explicit": True}]


@pytest.mark.parametrize("bad, msg", [
    (b"not json", "not valid JSON"),
    (json.dumps([1]), "JSON object"),
    (json.dumps(graph(format="something-else")), "format must be"),
    (json.dumps(graph(version=2)), "version 2 is not supported"),
    (json.dumps(graph(nodes="x")), "graph.nodes must be a list"),
    (json.dumps(graph(nodes=[node("A", "beam"), node("A", "beam")], edges=[])), "duplicate node id"),
    (json.dumps(graph(edges=[{"id": "e", "kind": "supports", "a": "B1", "b": "ZZ"}])), "not in graph.nodes"),
])
def test_rejects_what_is_not_a_serialized_graph(bad, msg):
    with pytest.raises(graph_ingest.GraphError, match=msg):
        graph_ingest.parse(bad)


def test_impact_waves_pass_through_connections():
    els = {e["global_id"]: e for e in graph_ingest.elements(graph())}
    im = impact.propagate("B1", "change", graph_ingest.load_path(graph()), [], [], els)
    assert im["hit"] == {"B1": 0, "K1": 1, "C1": 1}  # the column shares the connection's wave


def test_concurrent_reads_never_lose_the_project(tmp_path):
    """Regression: one sqlite connection shared by every request thread made concurrent reads of the
    same cached statement return None ('project 1 not found') or raise InterfaceError."""
    st = Store(str(tmp_path))
    pid = st.ensure_project()
    errors = []

    def read():
        try:
            for _ in range(300):
                st.project(pid)
                st.legacy_projects()
                st.revisions(pid)
        except Exception as e:  # noqa: BLE001 - any failure is the bug
            errors.append(repr(e))

    threads = [threading.Thread(target=read) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_concurrent_first_requests_create_one_project(tmp_path):
    st = Store(str(tmp_path))
    ids = []
    threads = [threading.Thread(target=lambda: ids.append(st.ensure_project())) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == 1 and len(st.legacy_projects()) == 1
