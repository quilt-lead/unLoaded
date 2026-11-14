# Move a column - synthetic v2, impact engine, health meter, API (2026-11-14)

Brief: `~/Documents/claude-prompts/2026-11-14-calc-graph-move-a-column-brief.md` (+ addenda 1-7).
UI is pending the React migration (addendum 4); everything is exposed through `/api/v2/*`.

## Run it

```sh
uv run python -m synth.v2.generate            # design + IFC + drawings + specs + calc package (+ registry truth) -> data/synthetic_v2/
uv run python -m synth.v2.generate --check    # byte-stable check (regenerates twice)
uv run python -m synth.v2.scenarios --jobs 5  # 25 move scenarios re-designed end to end -> answer_key.json
uv run python scripts/evaluate_move.py        # impact engine vs answer key -> move_eval.json
uv run python scripts/evaluate_all.py --synthetic-only
uv run calc-graph serve                       # API on http://127.0.0.1:8000
```

## The building (synth/v2)

Harbor View Office (fictional): 3 storeys + roof (14 / 27 / 40 ft), grid 1-5 x A-D (4 x 30 ft by
30 / 25 / 30 ft), composite deck, girders along Y on every number line, infill beams at third
points, grid beams along X. SMF (RBS) on lines A and D bays 2-4, chevron SCBF on line 3 bays A-B
and C-D, collectors A/D 1-2 and 4-5 and girder 3 B-C. Spread footings + piers under every column,
grade beams on A, D, 1, 5 (perimeter wall + SMF base moments) and 3 (braced-frame tie). Areas:
office (61 psf D / 65 psf L incl. 15 psf partitions), corridor bay B-C (80 psf L), roof (25 D / 20
Lr), mech RTU zone on the roof bay 3-4 / A-B (90 psf D).

Design (lightest passing, AISC v16 shapes): AISC 360-16 F2/F3 flexure with Lb (deck braces beams,
girders braced at infill points), G2 shear, L/360 live and L/240 total deflection, E3 + H1 columns
with K = 1 and eccentric shear-tab reactions with pattern live, ASCE 7-16 combos carried as D/L/Lr
components to every member. Lateral: ELF (SDS 1.0 / SD1 0.6, SDC D), simplified MWFRS wind, rigid
diaphragm distribution by PyNite stiffness with 5 % accidental torsion, PyNite frames, drift
0.020 hsx with Cd, SMF strength + SCWB + RBS span/depth, SCBF braces (KL/r <= 200, Ry Fy Ag for
gussets), collectors with Omega0. Footings: bearing (qa 4 ksf net), punching and one-way shear,
flexure steel. Typed connections: ST-2..ST-7 shear tabs (capacity computed: bolt group elastic
method, plate yield / rupture, bearing; bolts limited by beam T-distance), MC-1 RBS, DC-1..3 drag,
BG-1..3 gussets, BP-1..4 base plates; each end gets the lightest typical that works.

## Decisions (and why)

- **Layout -> topology.** A move is a different layout; members re-frame: members framing into
  the column follow it (skew), infill beams keep their line and re-span to the support's new line,
  and re-frame onto the collinear member on the other side when the moved support no longer spans
  past them. Removal: the collinear pair with the shortest combined span becomes one transfer
  member; the others frame into it (girders 55 ft beat grid beams 60 ft - same as practice).
- **Answer key = minimum-change re-design** (`design.run(keep=current)`): every surviving element
  keeps its size/detail unless it fails, else the next heavier. A from-scratch lightest-passing
  re-run also DOWNsizes members, which no engineer does for a move (first run showed 29 "resized"
  members on a 2 ft move, half of them downsizes).
- **Seismic weight uses a steel allowance (8 / 8 / 6 psf), not the as-designed tonnage**, so a
  member re-size does not re-trigger the ELF (design-office practice). Before this, a 2 ft gravity
  move re-sized the SMF frames through a 1 % weight change against a 0.988 drift ratio.
- **"Lateral analysis changes"** = ELF / wind / frame analysis / brace records move > 5 %, or an
  SFRS column moves. Frame-member demand changes count as SFRS demand, not as a lateral re-run.
- **Difficulty labels (answer key)** are categories of work, no count thresholds: easy (recalc
  only), moderate (member / typical connection next size, footing grows), hard (column resize,
  foundation clash, connection beyond the typicals, removal, SFRS column, lateral analysis
  changes), do-not-move (an SFRS column move whose frame members must re-size, drift over at the
  current sizes, or no rolled shape works).
- **Health meter** uses the same categories from ESTIMATES only (never the re-run). Two engine
  rules were added after the first evaluation showed misses, each for an engineering reason:
  (1) a typical shear tab only counts as an option if its bolt row fits the beam web (T-distance);
  (2) because the screen does not re-run the frame analysis, an SFRS member within 5 % of capacity
  under an SFRS-column move is treated as having no reserve. The 25/25 band agreement is therefore
  in-sample for those two rules.
- **Design health vs construction-adjusted health.** The mock construction state has Level 2
  steel erected (columns are single 40 ft pieces erected with Level 2), so every column is
  "do-not-move" once construction status is applied. Both bands are returned: `band` (design,
  scored against the answer key) and `band_construction` (with the platform status reasons).
- **Screening is exact-ish on this data by construction**: the engine re-solves each affected
  member in PyNite from the loads its own calc record prints (and the reactions of the members it
  carries), which are the loads the design used. Error appears where topology changes (re-framing,
  removal) or where an estimate is scaled (columns: H1 scaled with axial).
- **Connections are nodes BETWEEN members** in loadpath.py (fixed at the root): member -> support
  edges carry `via` = the plate (kind frames-into / bears-on) plus connected-by edges for the plate.
  The v2 IFC models joints physically (members stop 1" past the support face, plates at the joint,
  columns on base plates on piers, grade beams embedded 6" into footings).
- **Dana Point is not used** by the engine (retired by Issy's decision); the engine is generic over
  the registry shape (elements with geometry + typed relations + records with values).

## API (`backend/calcgraph/move_api.py`, all under `/api/v2`)

| Method | Route | Returns |
|---|---|---|
| GET | `/summary` | building, counts of elements / records / relations by kind, calcs, AISC table verification, which documents exist |
| GET | `/design` | the full design export (design.json): elements, types, relations, records, occurrences, details, spec_articles, sheets, calc_pages |
| GET | `/model.ifc` | the v2 IFC |
| GET | `/elements/{id}` | registry element page: `{element, record, relations_out, relations_in, designed_by: [records], occurrences: [{doc: ifc/drawings/specs/calcs/etabs, page, sheet, bbox, how, text, global_id, label}], occurrence_kinds_reserved}` - any registry id (elements, TYPE:/DETAIL:/MAT:, records, SPEC: articles, DET: details; ids may contain "/"), plus `kind` and `entity`; occurrences also carry the entity's own located box and doc "platforms" rows (platform, record_type, number, status, link, source live/mock) - registry_view.py |
| GET | `/records/{rid}` | calc record `{id, calc, section, kind, elements, values, demand, capacity, uc, check, lc, page, bbox, sheet, inputs, fed_by, feeds}` |
| GET | `/registry`, `/registry/{truth\|ingested\|eval}` | registry truth / rebuilt-from-documents registry / its scorecard (when built) |
| POST | `/impact` body `{column, dx, dy, remove}` | `{stale: [{record, calc, kind, reasons[], chain[], screened}], estimates: {element: {span_old/new, mu_old/new, uc_old/new, governs, size_est, ru_new, capacity, next_typical, special, B_req, method: "estimate - ..."}}, geometry, clashes, lateral[], notes[], health: {band, score, band_construction, score_construction, reasons: [{band, reason, factor}], worst_uc, stale_records, sheets}, occurrences: {element: [...]}, change_order, labels}` |
| GET | `/health?probe=2` | health of every column for a +/- probe move (heat view); stored in data/cache/heat/ keyed by a hash of every input (heat_cache.py), headers X-Heat-Cache hit/computed |
| POST | `/rerun` body `{column, dx, dy, remove, records?}` | redo calcs: `{rev_id, method, order_rule, results: [{step, record, calc, kind, job: gravity/lateral, old, new, size_old, size_new, status, ok_old, ok_new, ng_to_ok, new_page?}], summary, files: {calc_revision_pdf}}` - a NEW calc revision in data/synthetic_v2/revisions/<rev_id>/ |
| GET | `/revisions`, `/revisions/{rev_id}`, `/revisions/{rev_id}/{calc_revision\|rerun_sheets}.pdf`, `/revisions/{rev_id}/{name}/pages/{n}.png?hl=` | calc revisions (re-runs) + model revisions in the store; calc_revision = revised sheets in the package's own style with clouds + "was -> now"; rerun_sheets = handcalcs sheets (math printed from the Python that recomputed it, every value asserted against the re-run). Each result row carries `uc_current_size_new_layout` (old size, new layout) so NG -> OK is meaningful, and `new_page` {page, bbox, sheet, rerun_sheet} |
| POST | `/apply` body `{column, dx, dy, remove, label?}` | applies the move as a NEW model revision in the SQLite revision store (project "Synthetic v2"; IFC ingested through the production pipeline). Every move is computed from the base design, so parent = the BASE revision (found by model.ifc's hash), not the head: `{project, revision, parent, previous_head, label, diff: compare_models(parent, revision)}` = only this move |
| GET | `/compare?a=&b=` | element diff of two model revisions |
| POST | `/revisions/model/restore` body `{target, of, verb: undo/redo, expect_head}` | undo / redo of `/apply` without deleting history: re-ingests model revision `target`'s IFC blob as the NEW head (label "Undo R3: restore R2"), parent = `target` (same rule as /apply: the revision its content came from); 409 if the head is not `expect_head`. Response = `/apply`'s shape with `diff = previous_head -> revision`, + `{restored, of, verb}` |
| POST | `/revisions/calc/restore` body `{target (null = original package), reverts, of, verb}` | undo / redo of `/rerun`: a NEW calc revision carrying `target`'s results and pages, with `restore: {verb, of, restored, parent}` |
| GET | `/docs/{calcs\|drawings\|specs}/file`, `/docs/{doc}/pages/{n}.png?hl=x0,y0,x1,y1;...&w=` | original synthetic documents, page renders with highlight boxes |
| GET | `/platforms`, `/platforms/{procore\|autodesk_build\|forma}/{record_type}?raw=` | construction platforms, live or mock (`source`, `fallback_reason`) |
| GET | `/platforms/{name}/{record_type}/{id}`, `/platform-record?url=` | one platform record (normalized + raw + source) |
| POST | `/platforms/refresh` | rebuild the adapters (re-read env, credentials, re-fetch live) |
| GET | `/construction-status/{element}` | `{stage, submittals, open_rfis, float_days, reasons, move_difficulty}` |
| POST | `/change-order` body as /impact | potential change order: submittals, RFIs, sheets, spec articles, calc records, cost (every figure `{value, unit, estimate: true, basis}`), schedule |
| GET | `/etabs/objects?kind=`, `/etabs/model.e2k?column=&dx=&dy=&remove=` | `{answered_by: {adapter, adapter_name, mock}, items: [...]}`; .e2k written by calc-graph (ETABS did not open it; header X-Answered-By). Adapter = `CALCGRAPH_ETABS_ADAPTER` (etabs = mock, default; bhom_etabs = Windows bridge) |
| POST | `/etabs/send`, `/etabs/pull/{job_id}` | send / pull (+ answered_by); with the mock, results are our PyNite re-run, labelled so |
| GET | `/scenarios`, `/eval` | answer key summary; engine scorecard |

## Numbers (run 2026-11-14, from the scripts above)

- AISC table: 14/14 reference shapes within 1 % (max 0.4 %, W27X84 area 24.7 vs 24.8).
- Answer key: 25 scenarios - easy 1, moderate 10, hard 11, do-not-move 3.
- Engine on the generator registry: stale topological P 0.563 / R 0.992, screened (> 5 %) P 0.830 /
  R 0.922; UC at current size: 99.8 % within 0.05, over/under-1.0 flag 100 %; health band 25/25.
- Engine on the registry REBUILT FROM THE DOCUMENTS (`evaluate_move.py --source ingested`,
  registry_engine.py: ingested relations + IFC geometry + values parsed from printed calc rows):
  stale topological P 0.524 / R 0.935, screened P 0.852 / R 0.871; UC 99.7 % within 0.05; health
  band 23/25 exact, 25/25 within one band.
- Load path, v2 IFC through the production ingest: 100 / 100 (was 26.9 / 33.9); v1 unchanged.

## Not built / not verified here

UI by this agent (the React port builds it on these routes). Live connectors (all platform and
ETABS data is mock unless the Windows bridge adapter is selected). The two health rules noted above
were added after a first evaluation, so the design-path band score is in-sample for them.

## As-of date and the inbound inbox (2026-11-14)

**As-of (approval) date.** `POST /api/v2/impact`, `/change-order` and `GET /construction-status/{id}` take
`as_of` (`today` | `+1w` | `+2w` | `+1m` | `YYYY-MM-DD`; default today = unchanged). One projection:
`platforms.get_adapters(design, as_of=D)` builds the adapters over `synthetic.build_state(design, as_of=D)`,
the construction state at close of business on D read off the same CPM schedule (current forecast assumed
to hold). Health, construction status and the change order all read those adapters; none has date logic.
`GET /api/v2/as-of` = presets (today in US Eastern). `POST /api/v2/impact/timeline` (body = the /impact
body) = cost + forecast slip at the presets, the selected date and every stage boundary / package or
downstream activity finish of the affected elements within 120 days, plus `approve_by_line`. The
every-column heat view stays at today (by design, labelled in the UI). A live platform source has no
schedule logic and is served as it is today.

**Inbox** (`backend/calcgraph/inbox.py`, `/api/v2/inbox`, UI `/v2/inbox`). Lists the selected adapter's
open RFIs, pending change events and pending change order requests (8 synthetic incoming items come from
`platforms/inbox_synth.py`, unlinked to elements). `POST /{key}/read` = the AI step
(`calcgraph.ai.extract`, task `inbound_item_reading`, Pydantic schema, provider anthropic / the step's
default model, content-hash cache, budget cap from `CALCGRAPH_AI_MAX_RUN_USD`). `PUT /{key}/reading` =
the engineer's confirmed reading. `POST /{key}/impact` maps it onto the engine: move / remove a column ->
`move_api.impact_result` at the item's required-by date (or today); a substitution -> change-order
estimator only (structural recheck not run, said so); anything else -> no number, the reason and the
elements' construction status. `POST /{key}/reply` drafts the reply (template, no LLM), `PUT` saves edits,
`POST /{key}/post` is refused unless the adapter is a live sandbox that implements `post_reply` (none does
yet). `GET /history/{element}` feeds the element page's Platforms tab. State: `data/store/inbox/state.json`.
Score the readings against the generator's answer key: `uv run --with anthropic python scripts/read_inbox.py`
(cache first; real calls need `CALCGRAPH_AI_ENABLE_REAL=1`, a key and a run cap).
