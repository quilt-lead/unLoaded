# prototyping

Calc graph: map a structural BIM model to the calc package that sized it, so every
element links back to its calculation and the effect of a change is visible.

| Path | What |
|---|---|
| `notes/` | Session notes from the 2026-11-14 hackathon (problem, architecture, MVP scope) |
| `mockups/calc-graph-prototype-2026-11-14.html` | First concept: element graph and calc graph side by side, load-path impact ("remove column C2"), Git-style history, notes |
| `mockups/calc-bim-mapper-2026-11-14.html` | 3D mockup: upload an IFC and a calc package PDF (or load the sample), see every element linked to its calc with evidence and confidence |
| `calc-graph/` | v1 build: synthetic data generator with ground truth, FastAPI + SQLite backend (revision-aware), Vite + three.js frontend, mapping evaluation. See its README for run commands |
| `docs/2026-11-14-build-brief.md` | The brief the v1 build was made from |

The mockups are single HTML files - open them in a browser. Files you load stay in
the browser.

Next: a Git-diff view between model / calc revisions (redlines, markups, and the
effect of a change across the graph), built on the revision store in `calc-graph/`.
