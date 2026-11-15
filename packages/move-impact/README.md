# @unloaded/move-impact

"What happens if this column moves (or goes)?" - screened on **uploaded data**: the element graph
the app builds from the IFC (`@unloaded/element-graph`), plus, optionally, the values the calc package
states. Pure TypeScript, runs in the browser and in Node. Its only runtime dependency is
`@unloaded/calc-mapper`, for the shared contracts: `Quantity` + `convert()` (units), `SheetRect`
(rects) and `Provenance` + `inputList()` (provenance) - none of them is redefined here.

```ts
import { impact } from "@unloaded/move-impact";
import { sha256Json } from "@unloaded/calc-mapper";

const r = impact({
  graph,                                           // ElementGraph.serialize()
  graphSha256: await sha256Json(graph),            // provenance input
  move: { column: gid, dx: 1.5, dy: 0 },           // metres; or { column: gid, remove: true }
  facts,                                           // optional CalcFact[] - what calc rows state
  links,                                           // optional calc-mapper Link[] - for stale calcs
  sections,                                        // optional shape table for the profiles the model names
});
r.topological;   // elements on the path, each with its reasons and chain from the column
r.screened;      // those whose governing geometry changes > 5 %, with before / after / ratio
r.estimates;     // only with facts: utilisation estimates, each `method: "estimate"` + `scaledBy`
r.health;        // only with facts: easy / moderate / hard / do-not-move, with reasons
r.stale;         // only with facts or links: calcs on affected elements
```

Every record (topological element, screened element, estimate, stale row, stale calc, health) carries
calc-mapper's provenance shape: producer `move-impact@<version>/<impact|health>`, a stable rule id,
method `rule` or `estimate`, and `inputs` = the sha256 of the graph and of the calc package(s) its
facts came from (`r.inputs` lists them for the whole result). calc-mapper's `Producer` type admits
only its own modules, so the producer field is narrowed in `MoveImpactProvenance`; widening
`Producer` in calc-mapper would let this be its plain `Provenance`. Physical values are `Quantity`;
unit `"1"` marks a relative magnitude (unit area load, deflection with EI = 1) - compare ratios only.

Nothing in the output is a recalculation. Every utilisation is a printed value scaled by a
geometric ratio and says what it was scaled by; nothing calc-dependent is present without calc facts.

## Inputs (`src/types.ts`)

- **Graph**: read for node kind, geometry (bbox, axis), level and `supports` edges through connection
  nodes - never `params` (a test clears every param and asserts the same output).
- **Move**: `{ column, dx, dy }` (metres, plan) or `{ column, remove: true }`. The column's stack (any
  column at the same plan position, e.g. a pier) and its foundation chain move with it.
- **`CalcFact`** - one calc row: `id`, `kind` (beam / column / footing / connection / typical_detail /
  brace / frame / frame_girder / collector / seismic / other), `elements` (GlobalIds), `source`
  (`calcKey` = calc-mapper `Calc.key`, `page`, `rects` as `SheetRect`, `documentSha256` = the calc
  package's sha256), and whatever the row prints, every physical value a `Quantity`:
  `utilisation`, `demand` / `capacity`, `governs`, `checks[]` (per mode: flexure, shear,
  deflection_live, deflection_total, ...), `span`, `lineLoad` {dead, live, roofLive, unit},
  `reactions` {i, j} by component, `axial`, `serviceLoad` / `allowableBearing` / `width` (footing),
  `detailType` / `bolts` (connections, typical details), `combination` (governing load combination),
  `seismic` {cs, r, ie, system} (ELF row), `chevron` (AISC 341 F2.3 values), plus `role`
  (gravity / lateral) and `group` (frame line) as the sheet header names them. Units are converted
  once (`facts.ts`, calc-mapper `convert()`); a value in the wrong dimension or an unknown unit is
  dropped and listed in `assumptions`, never used. Reaction end "i" is the element's axis start.
- **Links**: calc-mapper `Link`s (`global_id`, `calc_key`; rejected links ignored).
- **Sections** (optional): profile -> `{unit, d, tf, bf, A, Ix, Zx, Sx, ry, rts, ho, J}` from a
  published shape table the caller supplies. The package ships no shape table.

## What it does

1. **Model** (`model.ts`): columns at their axis position; beams and braces with *analytical*
   endpoints - the physical axis stops at the support face, so each end is projected onto what the
   graph says supports it (column centreline, or the supporting beam's line). On the v2 model this
   reproduces every design span exactly and 189/189 members' supports match the generator's own.
2. **Topological impact**: what frames into the moved column follows it; what frames into a moved
   member slides to its new line (re-spans) or re-frames onto the collinear member when the support no
   longer spans past it; every beam downstream of a changed one; connections at both ends of every
   re-solved member; columns and their base plate / pier / footing when their load moves > 0.1 %.
   A column's load change is its own members' reaction changes plus everything carried down from the
   column(s) it supports (an upper storey's column bears on the one below it, a column on its pier),
   accumulated once, top-down; the footing takes the change of the column(s) bearing on it - the whole
   stack;
   grade beams tied to the moved footing and footing clashes; with facts, every member of a lateral
   frame the column belongs to and braces under a chevron beam whose gravity changes. Removal: the
   collinear pair with the shortest combined span becomes one transfer member, the rest re-frame onto it.
   Each far support's change is the transfer member's reaction minus the reaction of the half that
   framed into it before, both from the same local statics on the same loads (line load + self weight),
   never a computed reaction minus a stated one.
3. **Screened impact**: the same local simple-span statics before and after (`statics.ts`; exact for a
   pinned beam, no FE solver) on the stated line loads / reactions, or, without beam facts, a unit
   area load on each beam's tributary width. Kept when the governing quantity - moment (beams),
   brace force, end reaction (connections), footing service load, column axial load (column, base
   plate, pier) - changes > 5 %, when there is no number to decide on, or when the element moves with
   the column.
4. **Estimates** (facts only): beams scale each printed check by its ratio (flexure x moment ratio,
   and / phiMn ratio at the new unbraced length when a shape table is supplied; shear x shear ratio;
   deflection computed from the stated loads and Ix when supplied, else scaled; allowable x span
   ratio); columns x axial ratio (stated Pu + reaction deltas factored by the printed combination,
   seismic combinations with SDS >= Cs R / Ie; a column without a calc row inherits the combination
   of the column above); footings by bearing on the plan area (a stated `width` as stated, the
   model's long side for a rectangular plan, else square - said in `scaledBy`) at the stated allowable
   bearing, with the required width at the same aspect ratio; connections x end-reaction ratio and the next
   typical detail whose capacity covers it and whose bolt row fits the web; braced-frame girders by
   the F2.3 chevron check; chevron braces by the share of the beam's gravity change at the work point.
5. **Health** (facts only): the hackathon's bands and rules on the estimates (design health only).
6. **Stale calcs**: calc rows (facts) and calcs (facts or links) on topological elements, each with
   whether the screen keeps it.

Thresholds are the hackathon's: 5 % screen, 0.1 % load touch, 0.95 frame reserve, UC 1.0, footing
minimum 4 ft rounded up to 0.5 ft, combinations 1.4D / 1.2D+1.6L+0.5Lr / 1.2D+0.5L+1.6Lr.

## What changed from the hackathon engine (and why)

The hackathon engine (`calc-graph` prototype, `backend/calcgraph/move_impact.py`) read the
generator's `design.json`: element sizes and roles, its own relations, every calc record's values and
the AISC table. It never ran on an uploaded model. Here:

| Hackathon read | Here | Degradation |
|---|---|---|
| member endpoints, spans, support relations (`frames-into`, `via`) | graph geometry + `supports` edges | none: identical on v2 |
| element type girder / beam, roles (`scbf_beam`, `collector`, `sfrs`) | girder = carries beams; chevron beam = carries a brace; SFRS = has a lateral calc row | lateral roles need calc facts |
| frame membership (`member-of FRAME:`) | calc rows' `role: "lateral"` + `group` | none with facts; no lateral screen without |
| line loads, reactions, Pu, P_service, qa, capacities | calc facts (printed values) | none with facts; without, unit area load and ratios only - no utilisation, no band |
| footing size `B_ft`, grade beam width | footing / grade beam bbox | none |
| AISC table (phiMn at new Lb, Ix for deflection and brace stiffness, T-distance, sizing) | optional `sections` input | without it: capacity held, deflection scaled from the printed value, brace pair taken as rigid (an upper bound on the brace force change), bolt-row limit with tf = 0 (an upper bound on bolts) |
| next heavier W for an over-capacity beam (`size_est`), transfer member `required_size` | not estimated | omitted - needs a full shape catalogue and sizing loop |
| construction-status adjustment of the band (mock platforms) | not ported | design health only |

## Gate

`tools/calcgraph-reference` builds the v2 synthetic building (`synth.v2.generate`), its 25-scenario
answer key (`synth.v2.scenarios`, full re-design per scenario), the element graph of its IFC
(`scripts/build_graph.mjs`), calc facts (`scripts/move_fixture.py`), runs this package
(`scripts/run-scenarios.ts`) and scores it (`scripts/evaluate_move.py`); `evaluate_all.py` stage
`move_answer_key` gates on `eval/baseline.json`.

**The calc facts are a stand-in for matcher output**: the values the v2 calc package prints per row,
read from the generator's calc-sheet data (rounded as printed, with the page and box they are printed
in), not from the PDF text - `packages/calc-mapper` maps calcs to elements but does not extract row
values yet. When it does, the fixture step should be replaced by its output.

```
cd tools/calcgraph-reference
uv run python -m synth.v2.generate && uv run python -m synth.v2.scenarios --jobs 4
node scripts/build_graph.mjs data/synthetic_v2/model.ifc data/synthetic_v2/model.graph.json
uv run python scripts/evaluate_all.py --only move_answer_key
```

## Scripts

```
node packages/move-impact/scripts/run-scenarios.ts --graph g.json --scenarios s.json --out r.json \
  [--facts facts.json] [--links links.json] [--sections sections.json]
npx tsc -p packages/move-impact/tsconfig.json
npx vitest run --root packages/move-impact
```
