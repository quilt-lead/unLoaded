# Calc engine integration: main + hackathon engine + extraction

- **Status:** active (handed over to a new session ~10:30 PM ET; see `~/Documents/claude-prompts/2026-11-14-unloaded-pr4-handover.md`)
- **Branch:** `issy/integrate-calc-graph-engine` (owner: Issy). Draft PR #4 to `prod` (https://github.com/quilt-lead/unLoaded/pull/4), review requested from Carl (`cslotboom`). `prod` has no branch protection, so his review is requested, not enforced. This branch is pushed; `prod` is never pushed to directly.
- **Owned files:** `backend/`, `.github/workflows/ci.yml`, `src/api/`, `src/data/`, `src/components/pdf/`,
  `src/components/three/`, `src/components/RevisionPanel.tsx`, and the merge of these into main's components.
- **Working files (in flight):** `packages/calc-mapper/` (new), `backend/` → `tools/calcgraph-reference/`, `.github/workflows/ci.yml`, `src/engine/`, `src/data/`, `src/loaders/legacyBimJson.ts`, `docs/ARCHITECTURE.md`.


Cut from `prod`.
Started 2026-11-14, 6:10 PM ET. Commits are authored as Isabel Greenslade.
All times US Eastern. This file records each decision, why it was made, and how to check
it, so the work can be reviewed later. Newest entries are appended at the bottom of each section.

## Sources

| Source | Where | State used |
|---|---|---|
| **main** | `origin/prod` | `00d47e0` "reactified" (Noah, 5:49 PM), then merged forward as `prod` moves (see "Upstream merges") |
| **hackathon** | `~/Documents/unLoaded`, branch `issy-prototype` | the **local working copy**, including one unpushed commit (`b70df9a`) and ~1,500 uncommitted lines (MCP server, drawing verify). Chosen by Issy over the pushed `origin/issy-prototype` (`237fae1`) |
| **extraction** | `origin/extraction` | `ae53652` (rh-6, 6:12 PM): the `calc-viewer` prototype. Ideas only, no code or data (D13) |

## Decisions

### D1. Main's UI is the product shell; the hackathon is the engine behind it
**Why:** the two only overlap on the four views (element graph, calc graph, 3D, PDFs). Main has
the better shell for each: radial hierarchy, grouping, dockable panels, look. The hackathon has the
real content each one is missing: matching with evidence, a real calc graph, real PDFs, revisions,
impact, IFC geometry, tests. Both are React 18.3.1 / three 0.170.0, so there is no stack conflict.
The hackathon's own frontend shell and routes are dropped; individual components are moved in.
**Check:** the view-by-view comparison in the session that produced this branch, and that
`src/` contains no route-based app shell from the hackathon.

### D2. IFC parsing moves to the server (IfcOpenShell), and the browser regex parser is deleted
> **Status: reversed by D16 / D17.** IFC is parsed in the browser (web-ifc, Carl's packages); there is no server.
**Why:** main's `src/utils/ifcParser.ts` parsed STEP text with regex. It cannot produce geometry
and won't hold up on real files. The mission needs "user uploads IFC (and calc PDF) → graphs →
links", and the matcher and PDF ingest are Python. This turns main from a static site into a client
plus server app. It is the biggest architectural change on the branch. **Flag for Noah.**
**Check:** `src/utils/ifcParser.ts` is gone; uploads POST to `/api/projects/{pid}/model` and `/calcs`.

### D3. Only the core engine (mapper-v1) is brought over; about 70% of the hackathon stays on its branch
> **Status: partly superseded by D17.** The engine pieces listed are now ported to TypeScript (`packages/calc-mapper`); `ifc_ingest` / `loadpath` replaced by Carl's packages (D16); the store, API and schema are gone. What stays on `issy-prototype` is unchanged; four pieces are being pulled back in a follow-up PR (D18).
**Brought:** `ifc_ingest, loadpath, pdf_ingest, segment, matcher, calcdeps, impact, store, revstore,
pipeline, store_api, cli, schema/`, the original synthetic generator, tests, evaluation, copyright guard.
**Left behind:** the v2 engine (move-a-column, registry, platforms, as-of, inbox), ETABS / Speckle /
Windows bridge, drawing-set ingest, AI steps, MCP server, drawing verify.
**Why:** the v2 engine and everything built on it read the generator's own answer file
(`data/synthetic_v2/design.json`). They have never parsed an uploaded file, so they can't serve the
mission's "user uploads an IFC" path. The rest is outside the mission (analysis-software round trips, RFIs).
**Check:** `backend/calcgraph/` has no `platforms/`, `ai/`, `move_*`, `registry_*`, `set_*`, `mcp_*`;
the backend agent's report lists every import cut at a kept module.

### D4. The MCP server is deferred, not dropped
> **Status: now planned for the follow-up PR (D18 item 4)** as a local stdio CLI over an exported project file.
**Why:** "connect your AI to calc-graph" fits the mission, but `mcp_server.py` imports `move_api` and
`mcp_element_query.py` reads `design.json`. It answers about the synthetic design, not an uploaded
project. Bringing it in would mean bringing the v2 engine (D3). It should be rewired onto the
revision store first.

### D5. API routes keep identical paths and payloads to the hackathon
> **Status: superseded by D17.** No API; the same JSON shapes are produced by `packages/calc-mapper` so the UI's loader barely changed.
**Why:** the backend and frontend were ported in parallel; a fixed contract let both work at once
without waiting. Kept: health, projects, state, model/calcs upload, sample, revisions, compare,
revision file, page PNG, decisions, impact, export, `/api/store/*`. Dropped: `/api/sets/*`, v2,
as-of, inbox, verify, MCP.

### D6. One data contract, entering in one place
> **Status: principle kept, mechanism changed.** One contract, entering in one place, still holds. With D16 there are two adapters (`elementGraphToBim.ts` for topology, `loadProject.ts` for calc data) and one merge (`mergeProject.ts`). With D17 the canonical types live in `packages/calc-mapper/src/types.ts`; the generated `src/types/schema.ts` and its drift check are removed.
**Why (root cause):** main's mock data had each node carry its own invented `documents[]`, and every
view derived things from it separately (calc categories, revisions, load direction). Fixing views
one at a time would leave the next view free to invent again. Instead:
- the Python schema models are the source of truth; `src/types/schema.ts` is generated from them
  (`backend/scripts/gen_ts_types.py`) and **CI fails if it drifts**;
- `src/data/loadProject.ts` is the only code that turns backend payloads into the view model;
  components never read backend shapes directly;
- deleted: `BimNode.documents`, fake revisions (Rev A–D), invented axial load / strength,
  `buildCalculationGraph`'s inference (the calc graph now comes from backend `calc_edges`).
**Check:** grep `src/` for `documents`, `ifcParser`, `bim-database`; only `src/data/` and `src/api/`
import `types/schema`.

### D7. Load direction comes from geometry, plus the IFC file's own connection records
> **Status: superseded by D16.** Carl's graph provides both (geometry inference + authored IfcRelConnects as explicit evidence); the Python `loadpath` and its `ifc_rel_connects` rule are deleted. Side-by-side scores were identical.
**Why:** main guessed load direction from floor number and type rank (`graphEngine.ts`
`getStructuralGravityRank` / `orientLoadLink`). The hackathon's `loadpath` derives it from geometry
contact, which is what actually bears on what. One thing main did better was read authored IFC
connectivity (`IfcRelConnects*`). That is added to `loadpath` as an extra edge source with its own
rule name, so the backend is the only place edges come from.
**Check:** the evaluation's load-path precision/recall is not lower than the baseline.

### D8. The utilisation heatmap is disabled until there is a real source
**Why:** main's utilisation numbers were invented. The hackathon only has unity checks in the v2
engine (D3), computed from the generator's design. Showing invented numbers on a real project is
worse than showing none. The toggle stays, disabled with an explanation, and turns on automatically
when elements carry a utilisation value. 3D colouring instead shows real things: review status,
link confidence, stale-from-impact. A future source: utilisation read from the calc PDFs by the matcher.

### D9. 3D renders real IFC geometry (web-ifc), keeping main's viewer behaviour
**Why:** main drew boxes from invented `pos3d/size3d`. The hackathon's `viewer.ts` renders the real
IFC by GlobalId. Main's selection sync, zoom-to-selection, docking and heatmap toggle are kept.

### D10. Demo data: the hackathon's synthetic steel frame; Noah's sample JSON is removed
> **Status: amended.** The synthetic steel frame is still the demo and the scoring set. The removal of Noah's sample JSON was **withdrawn** after Issy questioned it (see D19); only the duplicated root `data/bim-database.json` and `public/data/bim-database.json` stayed removed (`prod` had already moved its sample to `sample-data/`).
**Why:** it has a real IFC, a real calc PDF and known correct answers, so it exercises and scores
the real pipeline. Noah's "Hudson Point Tower" JSON is mock data with no PDFs behind it, and its
fields (documents, utilisation, axial loads) no longer exist in the contract (D6).
Removed: `data/bim-database.json`, `public/data/bim-database.json`, `sample-data/bim-database.json`.

### D11. Guardrails land with the code: copyright guard, evaluation baseline, CI
> **Status: CI contents updated by D17:** guard; tooling (generator check, build graphs, run the TS pipeline, gated evaluation); frontend (typecheck, test, build). No pytest of a server, no schema-drift job.
**Why:** this repo is **public**. The hackathon worked next to a copyrighted permit set; its guard
blocks PDFs, images and distinctive strings from that set. It now scans the whole repo, including
`src/` and `public/`. Only `data/open/` (an openly licensed IFC) and small fixtures were copied.
The evaluation baseline makes any matcher change show its effect in numbers; CI runs guard, pytest,
generator check, evaluation, schema drift, frontend build.
**Note:** tests and type-checks cannot run on the laptop that built this branch (blocked by a local
hook), so **CI on the pushed branch is the first real test and type-check**. Until it has run green,
treat the branch as unverified.

### D12. Upstream main is merged forward, and its features are rebuilt on the new contract
**Why:** Noah keeps shipping to `prod` (e.g. `c69ef3d`). Merging `prod` into this branch (rather than
rebasing) keeps the history honest and lets the reviewer see each upstream change arrive. When an
upstream commit adds a feature on the old mock data, the feature is kept and rebuilt on the real data,
not dropped. See "Upstream merges".

### D13. From the extraction branch: ideas only, no code, no data
**Brought, as engine/UI changes (third stage):**
1. link **role**: design vs loads-only; an element counts as "designed" only with a design link;
2. confidence as a **sum of weighted evidence**, including negative evidence, plus caveats;
3. **typical groups** (same size + level) as a link target, so a size-only calc links once to a group
   instead of fanning a weak link to every matching element;
4. **size-mismatch findings**: IFC profile ≠ size in the calc;
5. calcs as **spans of page regions** with a stepper, instead of whole pages.

**Not brought:** the plain-JS viewers (superseded by main's UI), `build.py` (hardwired to one
project's sheet list), hand-written summaries, two-sided drawing↔calc evidence (needs drawings as
an input; later), and **all of `calc-viewer/data/`**.
**Why no data:** it was built from the copyrighted permit set ("Building 12"): sheet numbers, text
snippets with box positions, summaries, ~1.4 MB. **It is already pushed to the public repo on
`origin/extraction`**; that is outside this branch and needs rh-6 / Noah to remove it from history.

### D13a. Extraction ideas 1-5: how they were built (implemented ~8:30 PM ET)
- **Link role** design vs loads: a cross-reference is always `loads`; otherwise `design` if any hit is on a line
  without a load cue word. Element status counts design links only.
- **Confidence as weighted evidence:** item 1 is always the existing tier at its existing weight (so tier metrics
  are unchanged), plus storey equal +0.05 / different −0.15 and size equal +0.05 / different on a mark line −0.20;
  clamped, banded (high ≥0.75, medium ≥0.5), with caveats. Hit selection still uses tier confidence alone, which is
  why pages, spans and calc edges didn't move. (`ExportLink` calls the items `reasons`, since `evidence` was taken.)
- **Typical groups** = same kind + storey + size; a size on a line naming no mark links once to the group, members
  get `via_group` links.
- **Size-mismatch findings** when a design line names the element's mark with a different size; one profile
  normaliser (`profile.ts`, port of the parser's, parity-tested) because importing the parser pulls in web-ifc.
- **Spans:** a page is cut at a mid-page heading ≥1.2× median line height and close to the page title's size (a
  looser first rule wrongly split two main-package pages and was tightened); mapping reads only inside regions.
- **Measured:** a 3-page `calc_supplement.pdf` (synthetic, with ground truth) plants a typ. calc, a mid-page span, a
  loads-only line and a size mismatch. All existing baseline values unchanged; elements whose top link is correct
  440 → 455 of 457; main-package role accuracy 767/768; supplement spans 4/4, roles 7/7, group links P/R 1.0/1.0,
  mismatch P/R 1.0/1.0. 8 new gated rates + 7 exact counts added to the baseline.

### D14. The copyright guard stores only hashes of the protected terms
**Why:** the hackathon guard listed the protected set's firm, project and architect names and job /
permit numbers in plain text, in `copyright_guard.json` and the guard script. In a public repo that
publishes the identity the guard protects. The guard now stores salted SHA-256 hashes of normalised
terms and hashes token n-grams at scan time. Terms are added with `--add-term` on stdin, so they never
touch a file or shell history. `--self-test` uses a throwaway term generated at runtime.
**Check:** grep the hackathon term list against this repo: 0 hits (done 2026-11-14 ~7:05 PM ET over
every file in the worktree, nothing excluded, after deleting gitignored `backend/.venv` whose binaries
collide with the 4-letter acronym by chance).
**Limitation, said out loud:** the salt is public, so this keeps the identity out of plaintext, search
and diffs, but short terms (the 4-letter acronym) can be brute-forced from their hashes. It is
mitigation, not secrecy. Real secrecy would need the term list kept out of the public repo entirely
(e.g. a CI secret).
Also removed: `/api/store/sets/{sid}/bundle` (could only return 404) and the now-unused
`store.set_project` / `ensure_set_project` / `add_set_revision`.

### D15. Backend port specifics (from the porting agent's report)
> **Status: mostly superseded by D17.** Kept for the record: the side-by-side scoring and the root-cause analysis of the concurrency bug. The server, store and API it describes are removed.
- One path root: `revstore.ROOT` = `backend/`; `api.py` derives store / synthetic / `dist/` from it.
- Not brought, because nothing kept imports them: `sizes`, `aisc`, `ifc_diff`, `ids/`, `validate_ifc.py` (v2-only).
  `check_store_parity.py` dropped (one-off migration gate needing `data/sets`).
- `revstore` drawing-set path removed. `store.py` still accepts drawing-set rows, so a store written
  by the hackathon opens unchanged.
- `test_schema.py` had loaded `schema_audit.py` (which imports drawing-set adapters); its
  `contract_checks()` moved into the test verbatim, so that coverage is kept.
- Eval stages kept: `synthetic_v1`, `copyright` (baseline numbers unchanged), plus a new
  `synthetic_check` (generator byte-stability). All v2 / AI / drawing-set / ETABS stages deleted.
- D7 implemented: `ifc_ingest.read_ifc` returns `IfcRelConnectsElements` (incl. subtypes) between
  ingested elements; `loadpath` emits them as rule `ifc_rel_connects`; an edge found by geometry too
  keeps geometry's direction and records both rules. The synthetic IFCs contain 0 such relations,
  so the evaluation metric is unchanged by construction; a hand-edited copy with 2 relations
  produced 1 new edge + 1 merged edge as designed.
- Smoke (2026-11-14, ~6:45 PM ET, app run locally, no tests): sample → 459 elements (457 linked),
  800 links all with evidence, 12 calcs, 13 calc edges, 970 load-path edges; rev 2 compare →
  15 removed, 12 changed (matches ground truth). All kept routes returned 200.
- Licensing to note: PyMuPDF is AGPL-3.0 (matters if shipped commercially); the buildingSMART
  sample IFC is CC BY 4.0, attribution in `backend/data/SOURCES.md` must stay with it.
- Pre-commit hook install: `git config core.hooksPath backend/scripts/git-hooks`.

### D16. Carl's TS element graph is the single source of elements and topology; the backend is the calc engine
**Context:** at 6:40 PM ET `prod` merged PR #3 (Carl, `20baa23`): `packages/ifc-parser` (web-ifc → ModelInput) and
`packages/element-graph` (connections as nodes; `supports` / `connects` / `part_of` edges with evidence, incl.
`IfcRelConnects*`), with ~68 tests and one adapter `src/loaders/elementGraphToBim.ts`. That overlapped the Python
IFC ingest + load path already ported here (D2, D7).
**Decided by:** Claude, delegated by Issy ("whatever a structural engineer would find better").
**Why:** two parsers would build two element graphs that can disagree about the same model, so one must go.
Carl's is already merged by the team; it keeps connections as discrete nodes (what the engineers at the
hackathon asked for); it reads authored connectivity; and the model opens instantly in the browser. Matching,
evidence, impact and revisions need the PDF stack, which is Python, so the backend keeps those.
**What changes:** the client parses the IFC and POSTs the IFC file + the serialized graph as a model revision;
the backend stores both and builds its element rows from the graph (`GET /api/revisions/{rid}/graph` returns it).
`ifc_ingest.py` and `loadpath.py` leave the runtime, and D7's `ifc_rel_connects` rule with them (Carl's graph
already records those relations as explicit evidence). **D2 is reversed** (IFC parsing is client-side again,
but with web-ifc rather than the old regex parser) and **D7 is superseded**.
**Guard against getting worse:** Carl's graph had never been scored against known answers. CI now builds his
graph for the synthetic model and scores load path and matching against ground truth. Before the Python path was
deleted, both were scored side by side against `ground_truth.json` through the same pipeline
(2026-11-14 ~7:20 PM ET, `scripts/evaluate.py`, run as a script on data): **identical on every metric**.
Load path rev 1 and rev 2 precision/recall 1.000/1.000 (692/692, 0 extra, 0 missed); mapping
P/R/F1 0.9324/0.9956/0.9630 with the same per-tier counts; xref 312/312; calc edges 0.846/0.917;
segmentation 12/12; rev 1→2 diff 15 removed / 12 changed; C8 removal impact 15 removed / 36 hit.
So Carl's graph misses no element or edge class. Python counted 970 load-path edges vs 692 because it
added extra beam→column edges through each connection that ground truth doesn't count.
Also fixed at the root: concurrent requests shared one unlocked SQLite connection (17/240 failed);
now one connection per thread, WAL, writes serialised (0/480 failed). Anything Carl's graph misses is to be
fixed in `packages/element-graph`, not by keeping a second engine.
**Also:** 3D keeps real IFC meshes rather than Carl's axis-aligned boxes (diagonal members, his open item);
one web-ifc asset pipeline (his `copy-assets.mjs`). `legacyBimJson.ts` and `sample-data/` are removed (D10).
Project rules from `prod`'s CLAUDE.md now apply: vendored UI skills, and these notes live in `docs/agents/`.

### D17. Frontend only: the calc engine moves into the browser; Python becomes offline test tooling
**Decided by:** Issy, 2026-11-14 ~7:25 PM ET, after Claude laid out the trade-offs and recommended it.
**Why:** with D16 the backend's only remaining job was the calc engine (PDF text, segmentation, matcher,
calc graph, impact, revision store). None of it needs a server: pdf.js gives text and word boxes in the
browser, the matching logic is ~500 lines, storage can be IndexedDB. Gains: calc packages and models never
leave the engineer's machine (confidential / copyrighted calcs), no server to host or secure, and it fits the
team's direction (Carl's packages and Noah's diff are client-side). Loss: projects are per-browser until a
sync layer exists; mitigated by exporting / importing a whole project as one file.
**What changes:**
- new workspace package `packages/calc-mapper` (TS port: pdf.js extraction, segment, matcher with identical
  tiers, calc deps, impact, and the single graph diff `diffGraphs`), run in a Web Worker;
- `src/data/projectStore.ts` on IndexedDB: revisions, mapping runs, append-only decision log;
- `backend/` → `tools/calcgraph-reference/`: the synthetic generator and the scorer stay (Python, dev only);
  FastAPI, the SQLite store, the Python schema and the schema-drift CI job are deleted. This **supersedes D2,
  D5 and the store parts of D3/D15**; the concurrency fix goes with the store.
**Guard:** CI runs the TS pipeline on the synthetic model and gates on the same baseline the Python engine set
(mapping P/R/F1 0.9324/0.9956/0.9630, per-tier counts, xref, calc edges, segmentation, diff, impact). A one-off
link-level comparison of Python vs TS output is recorded below once measured. The baseline is not lowered.
**Noah's samples** stay and are ported onto the new view model, routed through the same `diffGraphs`;
their invented documents are shown labelled as demo data, never mixed with real calc links.

### D18. Pull back four pieces of the hackathon that the pivots had dropped (follow-up PR)
> **Scope:** at ~7:45 PM ET Issy put these in a follow-up PR; at ~8:15 PM ET she reversed that: **they go in PR #4** too. The schema item was briefly withdrawn in between; it now follows the extraction ideas in `packages/calc-mapper` so the two don't edit the same types in parallel.
**Decided by:** Issy, 2026-11-14 ~7:35 PM ET, after Claude listed what survived the pivots (the core
matcher, segmentation, calc deps, impact, diff semantics, decision log, evidence UI and the synthetic gate)
and what didn't. Claude had dropped the schema with the backend without flagging it; this corrects that.
1. **Schema contract** in `packages/calc-mapper/src/types.ts`: provenance required on every link, calc,
   edge, impact result and finding (producer module@version, method, evidence); units on every quantity
   (`Quantity`, fixed unit set, `convert()`); branded coordinate frames (sheet / model metres / building
   feet); producer records with input document hashes per mapping run.
2. **Move-a-column impact screening**, rebuilt on uploaded data (the v2 engine read the generator's
   design file). Unity checks only where a calc states them, labelled as estimates; gated on the v2
   synthetic answer key.
3. **Drawing-set ingest** as another parser producing Carl's `ModelInput`, so plans with no IFC flow
   through the same element graph (also enables extraction idea #6, two-sided evidence).
4. **MCP server** as a local stdio CLI over an exported project file, so an engineer can point their own
   AI at a project without the app gaining a server (consistent with D17).

### D19. Teammates' demo data is not deleted by this branch
**Decided by:** Issy, ~7:15 PM ET ("why are you deleting this? are you sure?"). Claude had planned to delete
Noah's sample JSONs (`sample-data/`, `data/harborview-*`) and `legacyBimJson.ts` because they carry invented
calc documents. That was Claude's rule applied to files a teammate is actively using for his diff demo; it
isn't this branch's call. They stay, and are ported onto the new view model: their invented documents are
shown labelled as demo data, never mixed with real calc links, and their A/B diff goes through the same
`diffGraphs` (legacy JSON is converted to an element graph first). Whether they stay in the repo is Noah's call.

### D20. How the work was done (process decisions)
- **Parallel agents with strict file ownership** (backend/engine vs frontend) so two agents never edited
  the same file; agents never ran git; Claude committed at stage boundaries. Upstream conflicts were resolved
  by the agent that wrote the code.
- **Agents were paused, not left running, at each architecture question** (PR #3, frontend-only) so no work
  was built on an assumption under review.
- **No local tests or type-checks** (blocked by a hook on the build machine). Verification so far is local app
  runs, scoring scripts on data, and screenshots. CI on PR #4 is the first real test and type-check.
- **Commits authored as Isabel Greenslade**, branch prefixed `issy/`. Only the feature branch is pushed;
  `prod` is changed only by merging the PR.
- **Intermediate checkpoint commits don't type-check** (said in their messages); review the branch at its head.
- **Mislabelled commit, kept rather than rewritten:** `ffa9c9c` is titled "Decision log: follow-up sequencing..."
  but also contains 48 files the engine agent had staged with `git mv` / `git rm` (the start of moving
  `backend/` → `tools/calcgraph-reference/` and deleting the Python server), because a plain `git commit` takes the
  whole index. It was already pushed to PR #4, so it is recorded here instead of force-pushed. The engine stage
  is completed in the next commit. Since then Claude commits named paths only (`git commit -- <paths>`).

### D21. The D18 work is built in a second worktree and merged into this branch (one PR)
> **Amended ~8:15 PM ET:** Issy: "keep adding it to that one PR". No follow-up PR. `issy/calc-engine-followups` is now only a staging branch for agents that would otherwise collide with this worktree's; each piece is merged into this branch and pushed to PR #4.
**Why:** PR #4 is already large and a reviewer needs a stable base. The D18 items go on
`issy/calc-engine-followups`, branched from this branch, in its own worktree so its agents can't collide
with this branch's (worktree `~/.paradev/worktrees/unLoaded/issy-calc-engine-followups`).
**Sequencing (amended ~7:55 PM ET):** move-impact screening needs only Carl's graph, so it started first.
Drawing-set ingest needs PDF text extraction, which `packages/calc-mapper/src/pdf.ts` provides; starting it
before the port is committed would mean a second PDF extractor, so it waits. The schema contract and the MCP
server also build on calc-mapper's types and wait. The follow-up branch merges this branch forward when the
port lands.

### D22. Move-a-column impact on uploaded data (`packages/move-impact`), and the AISC table stays out
**Built ~8:45 PM ET (D18 item 2).** Input is any element graph plus optional calc facts. Everything the hackathon
read from the generator's `design.json` now comes from graph geometry (spans and supports match the generator for
189/189 members) or from calc facts. Without facts it gives topological + screened impact only, comparing ratios on
a unit area load; utilisation estimates, health bands and stale calc rows appear only where a calc states values,
each labelled `method: "estimate"` with its basis. Left out (no honest source on uploaded data): next heavier size,
transfer-member sizing on removal, and the construction-status band adjustment (it came from mock platform data).
Four screening rules were added beyond the hackathon, each with an engineering reason in the code.
**Measured** on the v2 answer key (25 scenarios), scripts on data: topological P/R 0.540/0.992, screened
**0.867/0.923** (hackathon now 0.81/0.913), band 25/25, UC within 0.05 0.998, flag 0.999. The hackathon's own baseline
was re-measured on today's generated building mid-session (the numbers in the original brief were from an older
build); ours was copied from its current baseline unchanged. Calc facts come from the generator's calc-sheet data
as printed (a stand-in for matcher output until calc-mapper extracts row values).
**AISC shapes table: not committed.** It is AISC data without an open licence and this repo is public. It is
gitignored (`tools/calcgraph-reference/synth/v2/data/aisc_*.csv`), so CI skips the `move_answer_key` gate until
Issy decides. **That is mitigation, not a fix:** the gate only runs locally until then.

### D23. The auditability contract lives in calc-mapper and every other package reuses it
**Built ~9:00 PM ET (D18 item 1).** Required `provenance` (producer `calc-mapper@<version>/<module>`, rule id,
method rule / human / estimate, input sha256s) on links, group links, calc edges, calcs, findings, impact and
decisions, built only through `src/provenance.ts`; a missing or malformed hash throws rather than defaulting.
Producer records per run carry the element-graph format and the sha256 of the graph JSON and of the PDF.
`Quantity` with the 57 canonical units of the hackathon's `units.py` (checked identical), unknown units throw.
Branded `SheetRect` / `ModelPointM` frames (JSON stays plain numbers). `ENGINE_VERSION` → `mapper-v1.1` so cached
runs recompute. Every baseline metric unchanged.
**One contract, not two:** `packages/move-impact` is being moved onto these same helpers (its own `unit: "klf"`
fields and unlabelled estimates replaced) rather than keeping a parallel provenance/units type.
**Deliberately not brought:** BHoM / structural-analysis types from `schema/structural.py` (analysis-software
round trips are out of scope, D3).

### D24. The browser app: worker engine, IndexedDB store, one-file projects
**Built ~9:30 PM ET (D17).** `src/engine/ops.ts` is the only caller of `@unloaded/calc-mapper`, inside a Web Worker.
`src/data/projectStore.ts` (IndexedDB `unloaded-calc-graph` v1): projects, revisions, original files, element graphs
(built once at import, never re-parsed), extractions, runs keyed by engine version, append-only decisions; falls back
to memory with a visible warning. **Project file = one `*.calcgraph.json` with files base64-encoded:** chosen over a
zip because it needs no new dependency and goes through the same importer; costs ~33% size.
Noah's demo JSONs are converted to a `ModelInput` (boxes from his positions/sizes) so they get the same graph build
and diff through `diffGraphs` (one diff path, D19); their invented documents show as "Demo data", and his invented
utilisation / load numbers are dropped.
UI review pass per the project's CLAUDE.md (frontend-ui-engineering, react-best-practices, web-design-guidelines).
**Browser smoke** (headless, stamped screenshots, ~9:30 PM ET): sample 459 elements, 392 mapped / 65 review / 2
unmapped (same as the Python backend); evidence highlight; a confirmed link persists across reload; rev 1→2 diff
0 / 12 / 15 (ground truth); Harborview demo diff +70 / ~29 / −2; size-mismatch finding; provenance on links.
Seen once and not chased: right after rev 2 the calc-graph tab showed 15 calcs for a few seconds, then 12.
**Open:** the two synthetic IFCs could be committed so the demo works straight after a clone (PDFs would still need
generating); not done.

### D25. Drawing-set ingest is a second `ModelInput` parser (`packages/drawing-parser`)
**Built ~10:00 PM ET (D18 item 3).** Plan PDFs → `ModelInput` → Carl's `buildGraph`, so a drawing set with no IFC gets
the same element graph, calc mapping and impact. Ids are content-based and never contain the size (a resize keeps
the id). Every printed appearance is kept in `params["Drawing.Occurrences"]` for two-sided evidence later (extraction
idea #6). Geometry states how it was placed and its precision (infill beams ~0.03 m at 3/16"). Only relations the
drawing states are emitted; connectivity is left to the graph. PDF text comes from calc-mapper (one extractor): an
opt-in `extractPdfWords` adds rotated word boxes; `extractPdf` output unchanged (gate re-run by Claude, exit 0).
**Measured** on the v2 synthetic drawing set (scripts on data): every element class recall/precision 1.000; size,
level, mark 1.000; grid placement within 0.5 ft 1.000; callout attribution 0.833 (3 of 5 misses flagged ambiguous).
Shortfalls found in the element graph, not the parser (for Carl): a brace's upper end gets only `connects`, and there
is no "beam end bears on footing" rule (grade beam → footing 0/28). Expect lower numbers on real sets: vector-only
content, scans, non-orthogonal members and non-north-up plans aren't read.
**v2 generator drift:** after it was copied, the hackathon committed `18b6203` (brace connection relations, 18 more
placed calc rows). Not synced, so the answer key stays the one the gates were measured on; syncing means re-measuring.
**CI coverage:** both v2 gates (move-impact, drawing-parser) need the v2 generator, whose design step needs the AISC
table (D22), so **both run locally only** until that is decided. Their package tests and type-checks do run in CI.

### D26. First green CI, and what it took
CI on PR #4 went green at `5dd128f` (2026-11-14 ~10:15 PM ET): copyright, tooling (gated evaluation), frontend
(typecheck, tests, build). The first two full runs failed only on type errors that couldn't be caught locally (D20):
an open-union narrowing in `elementGraphToBim.ts`, an unreachable line in drawing-parser, and indexed tuple mutation
in move-impact under `noUncheckedIndexedAccess`. All three fixed at the line, no checks loosened.
Also: calc-mapper's `Producer` type now accepts any workspace package (`<pkg>@<version>/<module>`), so move-impact uses
the shared `Provenance` rather than a narrowed copy (D23).

### D27. MCP server: a local stdio CLI over the engineer's project file (`packages/mcp-server`)
**Built ~10:25 PM ET (D18 item 4, D4).** Reads one `*.calcgraph.json`, runs calc-mapper (and move-impact for
`move_column`) in-process — the same engine as the app, never a second implementation — read-only, no hosted server
(consistent with D17). Tools: project summary, element search/get, calc get, impact, revisions + compare, findings,
typical groups, page image crop with highlight, move column. Every result carries the engine's provenance plus the
project file and input hashes. Parity: the real CLI over stdio with the official MCP client matched the packages
called directly, 35/35 checks on each of three files. CI green at `9f93813`.
**Known duplication, to fix next (not a follow-up ticket):** the project-file type is declared in both
`src/data/projectStore.ts` and `packages/mcp-server/src/projectFile.ts`; it belongs in one shared package module that
both import. Also: add the MCP parity script to the CI tooling job.

## Upstream merges

| When (ET) | prod commit | What it brought | How it was integrated |
|---|---|---|---|
| 6:25 PM | `c69ef3d` "added diff compare to the ui" (Noah) | empty workspace on start; namable groups + whole-group selection; client-side A/B database diff mode with Swap A↔B, coloured statuses, removed-member ghosts, before→after cards; CLAUDE.md architecture notes; sample JSON moved to `sample-data/` | Empty start and groups kept as-is. Diff mode UI and colours kept, but fed from the backend's revision diff (`/compare`, key join by GlobalId + content hash); `computeDatabaseDiff()` deleted so there is one diff implementation (D6). A and B are two model revisions; diff fields that don't exist in real data (utilisation, axial load, strength) are dropped, not faked. Sample JSON deleted (D10). |
| 6:40 PM | `20baa23` PR #3 from `cs/dev` (Carl): `7b1b503` TS IFC parser + element graph into the UI, `13e5c54` vendored UI skills, `e5dd2b9` merge of c69ef3d | TS parser + element graph, npm workspaces, `src/loaders/*`, deletion of the regex parser, UI skills, `docs/agents/` convention | See D16. Merged with `git merge origin/prod`; conflicts in 12 frontend files + package files resolved on the new contract. |
| 6:46 PM | `d361b96` "added json samples" (Noah) | two legacy-format demo JSONs, `sample-data/harborview-tower-rev{1-base,2-compare}.json` (~47k lines, 420 invented `documents` entries), for the diff demo | To be merged after the PR #3 merge commit. The files are deleted: they use the legacy BIM JSON format whose loader goes (D16) and carry invented calc documents (D6/D10). **Withdrawn 2026-11-14 ~7:15 PM ET after Issy questioned it:** deleting a teammate's active demo data in a merge isn't this branch's call. The samples and `legacyBimJson.ts` stay; whether demo JSON with invented documents belongs in the repo is for Noah. |
| 6:52 PM | `c3f39fb` "added json samples" (Noah) | the same two harborview JSONs again under root `data/`, plus a 10-line `package-lock.json` trim | Kept (see the `d361b96` row: deletion withdrawn). Note root `data/bim-database.json` was removed in D10 as a duplicate; these are new files. The lockfile is regenerated by `npm install` on this branch, so the trim is absorbed. |
| 7:17 PM | `1ed39a2` "changed font to apercu" (Noah) | font swap in `tailwind.config.js` / `src/index.css`, two lines in `RadialGraphCanvas.tsx`, a `docs/agents` note | Applied by hand in the frontend commit (`143d175`), then merged (`47edc0d`); conflicts were formatting only. Font kept as Noah set it. |

## Open questions for Noah / the team

1. D17: frontend only means projects are per browser until there's a sync layer. Acceptable for now?
2. D8: is reading utilisation from the calc PDFs the right next source?
3. D19: should demo JSON with invented calc documents stay in the repo? (Noah)
4. The public `origin/extraction` data (D13): needs removing from history (rh-6 / Noah).
5. `prod` has no branch protection; requiring a review needs a repo admin.
6. D22: can the AISC shapes subset be committed (licence)? If not, the move gate needs an openly licensed shape source to run in CI.

## How to review this branch

1. Read this file, then `docs/ARCHITECTURE.md`.
2. CI is green from `5dd128f` (D26). The v2 gates (move-impact, drawing-parser) run locally only (D22, D25).
3. Run it: `cd tools/calcgraph-reference && uv sync && uv run python -m synth.generate` (writes the sample IFCs and calc
   PDF, gitignored), then at the repo root `npm install && npm run dev`; press **Load sample**.
4. Spot-check D6 (only `src/data/` + `src/loaders/` touch package shapes), D16/D17 (evaluation numbers in CI
   match the baseline), D11 (`git ls-files | grep -iE '\.pdf$|calc-viewer|data/sets|data/labels'` returns nothing),
   D14 (`check_no_copyrighted.py --range origin/prod..HEAD` is clean).
