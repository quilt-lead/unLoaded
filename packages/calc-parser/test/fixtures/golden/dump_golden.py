"""Dump the Python calc-graph pipeline's intermediate outputs as golden JSON for the TS port."""
import json
import os
import sys

ROOT = sys.argv[1]   # prototyping/calc-graph
DATA = sys.argv[2]   # synth dir
OUT = sys.argv[3]
sys.path.insert(0, os.path.join(ROOT, "backend"))
from calcgraph import calcdeps, ifc_ingest, impact, loadpath, matcher, pdf_ingest, segment  # noqa: E402

os.makedirs(OUT, exist_ok=True)
pdf = pdf_ingest.read_pdf(os.path.join(DATA, "calc_package.pdf"))
pages = pdf["pages"]
calcs = segment.segment(pages)
ifc = ifc_ingest.read_ifc(os.path.join(DATA, "model_rev1.ifc"))
els = [{k: e[k] for k in ("global_id", "ifc_type", "cat", "mark", "name", "profile", "storey")} for e in ifc["elements"]]
edges = loadpath.infer(ifc["elements"])
links = matcher.run_mapping(els, calcs, pages)
cedges = calcdeps.infer(calcs, pages, links)
by = {e["global_id"]: e for e in els}
imp = []
for e in els:
    if e["mark"] in ("C8", "2B1", "G3") or (e["cat"] == "Footing" and not any(i["global_id"] == e["global_id"] for i in imp) and len([x for x in imp if by[x["global_id"]]["cat"] == "Footing"]) < 1):
        for mode in ("change", "remove"):
            imp.append(impact.propagate(e["global_id"], mode, edges, links, cedges, by))


def dump(name, obj):
    with open(os.path.join(OUT, name), "w") as fh:
        json.dump(obj, fh, indent=None, separators=(",", ":"))


dump("pages.json", {"pages": pages, "meta": pdf["meta"]})
dump("elements.json", els)
dump("calcs.json", calcs)
dump("links.json", links)
dump("calc_edges.json", cedges)
dump("load_edges.json", [{"src": e["src"], "dst": e["dst"]} for e in edges])
dump("impact.json", imp)
print(len(pages), "pages", len(calcs), "calcs", len(els), "els", len(links), "links", len(cedges), "cedges", len(imp), "impacts")
