# Calc Graph - build brief (2026-11-14)

Hackathon project from the hackathon session notes (2026-11-14 11:37 AM ET, see prototyping/notes/).
external (a contractor-tech founder, a Thornton Tomasetti structural engineer, an
architect), so this is NOT part of the Structured monorepo.

## The problem (from the session)
Structural engineers manage hundreds of elements (beams, columns, slabs,
connections, foundations). Each must map to the calc that sized it, and stay
current as the design changes. Today it is hand-annotated PDFs. Calc packages mix
RAM Concept / RAM Structural System reports, MathCAD sheets, hand calcs and
VBA/Excel PDFs. Nothing links an element back to its calc, and when something
changes (a column removed) the downstream calcs that go stale are invisible.

Two graphs: an ELEMENT graph from the BIM model (nodes = beams, columns, slabs,
walls, braces, foundations, and CONNECTIONS as their own typed nodes; edges = load
path slab -> beam -> connection -> column -> foundation) and a CALC graph from the
calc package (nodes = calcs; edges = output of one feeds input of another). The
core task is mapping the two. Deterministic rules preferred over fuzzy inference.
Node parameter sets must be open-ended (bolted vs welded connections add fields
later without a schema change).

## Working mockup (port its behaviour, do not start from zero)
`prototyping/mockups/calc-bim-mapper-2026-11-14.html` - single-file three.js + web-ifc +
pdf.js page. Verified 2026-11-14 on its built-in sample and on a real Revit IFC
(376 elements, marks like `B1B15-1`). Its mapping engine (`segment()`,
`runMapping()`) is the spec for v1 of the matcher: tiers exact mark 0.97, mark
range ("2B1 - 2B9", "C1 thru C12") 0.9, mark ignoring punctuation 0.88, mark
family (B1B15 covers B1B15-1..-n) 0.85, unique partial mark 0.5, section size +
element type (+ level if the line names one) 0.62, element type only 0.3,
cross-reference (a mark of a different element type than the calc designs)
capped 0.45. Front matter / contents pages and scanned pages (no text layer) are
detected and never mapped. Every link keeps page, matched text and the rule.
Also see the earlier 2D concept `prototyping/mockups/calc-graph-prototype-2026-11-14.html`
(load-path propagation, "remove column C2" impact, Git-style history, notes).

## What to build now (v1)
New standalone repo at `prototyping/calc-graph` (git init, local only - do NOT
create a GitHub remote or push; Issy decides where it is shared).

Use open-source / free tools and data wherever possible (Issy's ask):
- IFC: IfcOpenShell (Python) for semantics, psets, storeys and geometry-based
  connectivity; web-ifc or @thatopen/components (MIT) for the browser viewer.
- PDF: PyMuPDF for text + word boxes (highlight boxes for evidence).
- Analysis for synthetic calcs: PyNite (open-source FEA). Mathcad-style worksheets:
  handcalcs-style rendering (matplotlib mathtext is fine if no LaTeX is installed),
  and consider SMath Studio (free) `.sm` XML worksheets as a real, free
  Mathcad-like input format. Real Mathcad Prime `.mcdx` is proprietary - only
  read it if a free sample exists online; never fake its format.
- Data found online: prefer genuinely open structural IFC samples (e.g. the
  buildingSMART Sample-Test-Files repo, IfcOpenShell test models). Record the
  source URL + licence of every downloaded file in `data/SOURCES.md`. Do not use
  any customer file from OneDrive in the repo.

Pieces:
1. `synth/` - deterministic generator: builds a steel-frame IFC with IfcOpenShell
   (marks in Pset, storeys, footings, plates as connections), runs PyNite for
   member forces, and writes a calc package PDF with several realistic styles
   (RAM-style tabular report, Mathcad-style worksheet, Excel/VBA footing table,
   one rasterised "scanned hand calc" page with no text layer, a contents page,
   cross-references between calcs). It ALSO writes the ground-truth mapping JSON
   (element GlobalId -> calc id) and the calc dependency edges. Seeded, so
   re-runs are byte-stable.
2. `backend/` - Python 3.12 + uv + FastAPI. Ingest IFC -> element graph incl.
   load-path edges inferred from geometry (beam end touching column/plate, column
   over footing, slab over beams). Ingest PDF -> calc segments -> mapping (port of
   the mockup's engine). Storage: SQLite (nodes/edges/links with JSON params), or
   an embedded open-source graph DB if it is clearly simpler. Every ingest is a
   REVISION keyed by element GlobalId - Issy will next build a Git-diff feature
   (redlines, markups, effects of a change across the graph), so store revisions
   and parameter snapshots now and keep that door open; do not build the diff UI
   yet.
3. `frontend/` - Vite + TypeScript + three.js viewer, porting the mockup UI:
   upload IFC + PDF, calc list, colour by calc / status / type, inspector with
   evidence snippet + page viewer with highlight, confirm / reject / link by hand,
   export JSON. Add the load-path graph view and impact propagation from the 2D
   concept (select element -> downstream elements + stale calcs).
4. `scripts/evaluate.py` - run the full ingest on the synthetic package and
   score the mapping against ground truth: precision / recall per tier and per
   calc. This is the verification. Report the numbers.

## Constraints on this machine
- No test, type-check or lint runners locally (pytest, vitest, tsc, ruff...) - a
  hook blocks them. Write tests for later CI, but verify by RUNNING the pipeline
  (`scripts/evaluate.py`, the app itself, headless screenshots via
  `~/.claude/bin/stamped-shot [--script steps.mjs] <url> <out.png>`).
- Never claim it works without output you produced. Hyphens, not em dashes, in
  anything Issy reads. Times in US Eastern.
- Commit locally in small steps with clear messages; no remote.

## Report back
What was built, how to run it (exact commands), evaluation numbers, which open
data/tools were used with licences, known gaps, and a short design note on how
revisions are stored so the diff/redline feature can sit on top.
