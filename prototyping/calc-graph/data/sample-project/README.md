# Approved engineering sample

This package contains a user-approved engineering IFC and two ETABS spreadsheet exports. The project name has been replaced with `sample`. It is not synthetic data and the name replacement is not comprehensive anonymization. Geometry, engineering values and element identifiers are retained. These are the only project source files approved for this package; runtime stores, original files and old Git history are excluded.

- `architecture.ifc`: 752 elements, unchanged IFC GlobalIds.
- `Bldg_Export.xlsx`: model assignments, connectivity GUIDs and export settings (100 sheets).
- `Design_results.xlsx`: program information and 368 steel design summaries (2 sheets).

The result importer matches 80 beams, 128 columns and 160 braces by GUID. It checks exported unique names, labels, stories and member types. IFC and ETABS storey names differ for 288 matched members and are flagged; identity matching does not prove the two exports describe the same analysis state. The summary includes ratios, governing combinations and warnings, not detailed forces or automatic recalculation.

## Run locally

From `prototyping/calc-graph`, install and build:

```sh
uv sync --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
CALCGRAPH_STORE=data/local-run/team-sample uv run calc-graph serve --host 127.0.0.1 --port 8000
```

In a second terminal in the same directory, with the server running and the store empty:

```sh
uv run python scripts/load_sample_project.py
```

Open `http://127.0.0.1:8000/ifc`. In the right inspector, search **Find ETABS member** for `B1` and select **B1 · ROOF**. Its beam highlights in the model and the imported PMM ratio, load combination, warning and source rows appear beside it. Use **History & beam checks** for new imports, historical previews and separate simplified Python checks. The toolbar's **Load sample** button loads the older synthetic example, not this package.

No Neo4j, Windows, ETABS installation or VIKTOR is needed to view these exported results. A licensed ETABS installation and connector are still required for an actual ETABS rerun.
