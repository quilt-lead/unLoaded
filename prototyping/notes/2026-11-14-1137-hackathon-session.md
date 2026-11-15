# Hackathon - session notes

2026-11-14, 11:37 AM ET. Exported from Granola (AI summary of the session).

## Attendees and Backgrounds

- Hassan: tracks people, equipment, and construction progress across Middle East, Brazil, and US; recently launched Zepay (contractor payments tied to quality-certified progress); works with Saudi developers on projects of 3,000+ villas
- Ashlyn: structural engineer at Thornton Tomasetti (Miami), full-time master's student; tasked with building an internal app
- Issy: co-founder, AI startup in QA/QC and construction tech (2 years); recently moved into structural engineering space (~9 months)
- Noah: licensed architect, 6-7 years commercial and high-end residential; now working in digital transformation and computational design

## Core Problem Statement

- Structural engineers manage hundreds of elements (beams, columns, slabs, connections, foundations)
- Every element must map to a calculation, and those calculations must stay current as designs change
- Current practice: hand-annotate PDFs, draw squiggles on key plans, label beam groups manually
- No clean system links an element back to the calculation that produced it
- When something changes (e.g. a column is removed), downstream impact on other calcs is invisible
- Calc packages vary widely: RAM Concept outputs, MathCAD sheets, hand calcs, VBA-generated PDFs

## Graph Network Architecture

- Two graphs needed:
  - Element graph: built from BIM model (column sizes, geometry, topology)
  - Calculation graph: built from ingested calc package PDFs
  - Core task: map the two graphs to each other
- Node types: columns, beams, slabs, PT, shear walls, moment frames, foundations, connections
  - Connections should be discrete nodes, not just edge properties
  - Connection types carry their own sub-calculations (e.g. bolt strength reused across many locations)
- Edges encode load paths: slab loads to beams, beams to columns, columns to foundations
- Changing a floor plate or shifting a column propagates changes through the whole chain
- Topology optimization (kick a column, see how the system updates) flagged as the "holy grail" but out of scope for now
- Agents could recursively re-run affected calculations when an input changes, but deterministic equations preferred over fuzzy inference

## MVP Scope and Demo Direction

- Ingest: take a full calc packet (PDF) + BIM model and parse both into the two graphs
- Map element labels in the calc PDF to elements in the building model
- Output: a visual, navigable representation of the graph with element-to-calc linkage
- Starting point: a complete calc packet (not preliminary design stage; too sparse to be useful)
- UI: vibe-coded custom interface preferred over Revit plugin
  - Show element, hover to see linked calculations and history
  - Display diffs (who changed what, when, and why) like a Git diff
  - Commentary layer: e.g. "Calc 1 was RAM output; this is a special case override"
- Split work into two tracks:
  1. Data parsing and graph schema/database structure
  2. Demo UI and visualization

## Key Design Decisions and Open Questions

- Connections as nodes: agreed they need to be discrete nodes with typed classes, not just edge attributes
- Schema flexibility: node parameter sets should expand dynamically (e.g. bolted vs. welded connections add fields later without redesigning schema now)
- Version control: useful but only on top of the mapping layer, not standalone
- Topology optimization: deferred; acknowledged as extremely complex
- "Did we just reinvent BIM?": noted risk; differentiation is the clean, sexy UX and the explicit calc-to-element linkage that BIM doesn't provide
- Ingestion timing: full calc packet only, not preliminary design phase

## Next Steps

- **Mock up a flowchart of the full system design** (Issy) - offered to use the session notes to diagram the discussed architecture.
- **Define graph database schema and data structure** - agree on node types, edge types, and how element and calc graphs map to each other.
- **Begin parallel workstreams: parsing pipeline and demo UI** - one track builds the PDF and BIM ingest and graph construction; the other builds the visual demo.
