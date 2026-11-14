# Local review workspace

Open `/ifc` after starting `calc-graph serve --host 127.0.0.1 --port 8000`. Use the existing toolbar’s **History & beam checks** button. `/review` redirects to this existing workspace.

The existing IFC workspace links IFC selection, PDF source links, local inferred relationships, immutable imported revisions, PDF attachments, and saved Python beam comparisons. No Neo4j service is required.

1. Import IFC and calculation PDF, or load the explicitly synthetic sample.
2. Choose before and displayed model revisions, and the PDF to inspect. Model comparison matches IFC GlobalIds. Historical browsing does not modify project heads.
3. Select a member in the list, model, or relationship graph. Matching scores and inferred relationships are candidates for engineering review.
4. Attach a PDF with a source note to a model revision or selected member.
5. Select a beam present in both revisions, enter confirmed effective spans and factored uniform load, record the source and confirm assumptions. Save a paired check. Optional service deflection requires service load, E and I.

The Python check uses M=wL²/8, R=wL/2 and optionally δ=5wL⁴/(384EI). It assumes a simply supported, uniformly loaded, non-composite beam and unchanged E/I. Inputs do not modify the IFC. It is neither a steel capacity check nor an ETABS/global-analysis rerun. ETABS steel summary XLSX imports are supported via History & beam checks: supply a building export containing frame assignments and connectivity GUIDs, plus an AISC 360-10 steel design summary export. Results join by GUID and unique name with story, label and member-type checks. They appear in the existing inspector with source rows and downloadable workbooks. IFC/export section and storey differences remain visible. Imports are immutable records associated with the displayed IFC revision; they are not reruns. Geometry editing and a live Windows connector are not implemented in this clean workspace.

Imported files remain in the configured CALCGRAPH_STORE. Additional review records are persisted in its review/review.sqlite and hash-addressed PDF files. Do not commit user imports or local runtime data.

Validation: `uv sync --extra dev`; `.venv/bin/python -m pytest backend/tests/test_review_workspace.py -q`; frontend build with the repository's documented Node environment. Tests use only isolated synthetic fixtures and cover historical head preservation, revision ownership, calculation values, replay, invalid inputs, attachment retrieval and hash integrity.
