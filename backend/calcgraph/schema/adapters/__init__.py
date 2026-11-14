"""Adapters: calc-graph store rows -> the F1 schema. `ifc_store` reads the IFC path's revisions
and mapping runs (model_facts / calc_facts / run_facts); `_common` holds the shared Tally (what was
rejected and why, which provenance fields the adapter had to supply, how many numbers carry a unit).
The hackathon's drawing_set / calc_records / connections / bhom_json / ifc_model adapters were not
ported: nothing in this package produces their inputs."""
