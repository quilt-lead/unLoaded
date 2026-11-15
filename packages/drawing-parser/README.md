# @unloaded/drawing-parser

Parses a structural **drawing set** (plan, elevation, schedule and detail sheets as PDF, no BIM
model) into the format-neutral `ModelInput` defined in `@unloaded/element-graph/input`. It is the
second model parser beside `@unloaded/ifc-parser`: `buildGraph()` consumes its output exactly like
an IFC import, so firms with plan PDFs but no IFC get an element graph.

It reports what the drawings **state**: members from their tags, columns and foundations from
schedules and marks, levels from stated elevations, grids from bubbles, connections from detail
callouts. Geometry is drawing-derived (grid + scale) and says so. Connectivity is left to the
graph's inference, as the ModelInput contract asks; the only relations emitted are the ones the
drawing states (a callout linking a member end to a detail, a schedule row giving a column its
base plate).

Runs in the browser and in Node. `src/` has no `fs` or `path` usage. PDF text comes from
`@unloaded/calc-mapper`'s pdf.js reader (`extractPdfWords`); there is no second PDF extractor.

## API

```ts
import { parseDrawingSet, drawingParser, parseDrawingPages } from "@unloaded/drawing-parser";

const model = await parseDrawingSet(
  [{ name: "S-sheets.pdf", data: bytes }, { name: "S-5xx details.pdf", data: bytes2 }], // one set, any split
  {
    pdfjs,                    // Node: await import("pdfjs-dist/legacy/build/pdf.mjs"); browser default "pdfjs-dist"
    profile: { sheetNumber: /^S\d\.\d{2}$/ }, // override any drawing-set convention (see src/profile.ts)
  },
);

drawingParser.id;            // "drawing"
drawingParser.extensions;    // ["pdf"]
drawingParser.canParse(name, head?); // "%PDF-" sniff / *.pdf - a calc package is a PDF too: the caller picks the parser
drawingParser.parse(bytes, { fileName, pdfjs });

parseDrawingPages(pages);    // pure core: pages of words (DrawingPage[]) -> ModelInput; no PDF library
```

Also exported: `readSheets`, `DEFAULT_PROFILE`, `resolveProfile`, `memberTag`, `nominalSection`,
`feetInches`, `phrases`, `levelName`, `hasPdfHeader`, `SOURCE_FORMAT` (`"drawing"`).

Never throws on drawing content: pages without a title-block sheet number are skipped and every
unreadable thing goes to `warnings`. Output is deterministic (elements sorted by id, relations by
kind/a/b, levels by elevation); the same PDF gives byte-identical JSON.

## How things are read

Conventions are generic US structural-set conventions (`src/profile.ts`, ported from the hackathon's
`profiles/default.yaml`). A set that differs overrides only what differs.

| What | Rule |
|---|---|
| Sheet | Tallest word in the title-block strip (right 11% of the page) matching the sheet-number pattern; title = the words of 12 pt or more within 300 pt above it. No sheet number: not a drawing sheet, skipped. |
| Sheet kind | First title substring that matches: FOUNDATION PLAN, FRAMING PLAN, ELEVATION, SCHEDULE, DETAIL, SECTION, NOTES. |
| Plan level | From the plan's title: "LEVEL 2 FRAMING PLAN" -> Level 2, "ROOF ..." -> Roof, foundation plan -> Foundation. |
| Level elevation | Stated elevations, most frequent wins (conflicts warned): "LEVEL 2" over "EL. 14'-0"" (elevations), "ROOF EL. 40'-0"" (schedule rows), "TOP OF STEEL (T.O.S.) EL. ..." (the level's own plan notes). Foundation = "TOP OF FOOTING EL.". Unstated levels are assumed and warned. |
| Drawing area | Left of the plan notes column (a heading ending in NOTES right of 63% of the width) or of the title block. |
| Grid | On plans: the same bubble label (single word, 12-30 pt) printed twice far apart (> 500 pt) at the same x (an x-line) or the same y (a y-line). |
| Scale | Feet-inch dimension strings between adjacent grid lines (median ft/pt per axis, residual reported); else a `SCALE: 3/16" = 1'-0"` note; else none (no geometry, warned). |
| Building grid | From the plan with the most grid lines: coordinates are the cumulative written dimensions (else measured pt x scale). x right, y up the sheet (plan north up assumed), origin at the left-most x-line and bottom-most y-line. Every sheet maps page -> building piecewise-linearly between its own grid lines. |
| Plan member | A size tag (`*W18X40 (30) c=3/4"`, `HSS6X6X1/4`, `C12X20.7`, `L4X4X1/4`, metric shapes via ifc-parser) labels the line just past its descent edge (0.4 x text size); flat tags run along x, rotated tags along y. The member spans the grid lines either side of the tag. A line within 0.9 x text size of a grid line is on that grid line (role `girder`); otherwise it is an `infill` member at the measured offset. `*` = SFRS, `(n)` = studs, `c=` = camber. |
| Frame marker | `*SMF` / `*SCBF` ... within 40 pt of a member -> `Drawing.FrameSystem`. |
| Foundation plan | Footing marks (`F5.5`) and pier marks (`P2`) belong to the nearest grid intersection (within 120 pt); grade-beam marks (`GB1`) to the nearest grid line, spanning the lines either side. |
| Frame elevation | A row of single grid bubbles with a title "... LINE <grid>" below it is one elevation of that grid line; level markers give the vertical axis. Rotated tags beside a bubble = a column storey; flat tags just above a level line = a beam of that line (merges with the plan's member: same id); other flat tags in a bay = a brace in the half bay holding the tag. |
| Column schedule | Header row `COLUMN LINE` with grid-intersection cells (`1/A`), storey rows (`L1 - L2`), `BASE PLATE`, `PIER`, `FOOTING` rows. Consecutive storeys with the same size are one column; a size change splits it. |
| Mark schedules | A mark (`F5.5`, `P2`, `GB1`, `BP-4`) under a `MARK` / `TYPE` header: the row's text goes to every element with that mark (`Schedule.Text`, plus sizes for the geometry). |
| Detail panels | A bubble with the sheet's own number under the detail number; title to its right; type mark from the title (`MC-1`, `ST-3`, `BP-4`). |
| Detail callout | A detail number over another sheet's number (callouts to SECTIONS sheets are section cuts, ignored). It becomes a connection at the end of the nearest member of a kind the detail fits (from its title: brace/gusset, base plate, or beam connections). |
| Deck | A `FLOOR DECK:` / `ROOF DECK:` note on a framing plan -> one slab at that level; thickness from `... TOTAL` or the first inch value. |

## Ids (content-based, stable across re-imports)

Drawings have no GlobalIds. Ids are built from level, grid and orientation; **the size is never in
the id**, so a resize keeps the id (and so do decisions keyed on it).

| Element | Id | Example |
|---|---|---|
| Member on a grid line | `beam:<level>:<span>:<line>` | `beam:level-2:A..B:1` (on line 1, from A to B) |
| Infill member | `beam:<level>:<span>:<bay>#<n>` (n = 1 nearest the bay's lower line) | `beam:level-2:1..2:A..B#1` |
| Brace | `brace:<bottom level>:<line>:<bay>:<side>` | `brace:level-1:1:A..B:A` |
| Column | `column:<x-line>/<y-line>` (`:<lo>..<hi>` when sizes change by storey) | `column:1/A` |
| Pier | `pier:<intersection>` (kind `column`, role `pier`, as the IFC writes piers) | `pier:1/A` |
| Footing | `footing:<intersection>` | `footing:1/A` |
| Grade beam | `grade-beam:<span>:<line>` (kind `beam`, role `grade_beam`) | `grade-beam:1..2:A` |
| Callout connection | `connection:<member id>@<end>` (end = grid label, or `bottom` / `top` for braces) | `connection:beam:level-2:1..2:A..B#1@1` |
| Base plate | `connection:base:<intersection>` | `connection:base:1/A` |
| Slab | `slab:<level>` | `slab:level-2` |

Levels: `level-1`, `level-2`, `roof`, `foundation` (slug of the name). Spans list the grid labels in
increasing building coordinate. An infill ordinal shifts if an infill member is added to the bay.

## Geometry and precision

Metres, Z up, building frame above. Every element with geometry has
`Drawing.GeometrySource = "drawing-derived"`, `Drawing.GeometryRule` (how it was placed) and the
sheet's `Drawing.ScaleSource` / `Drawing.ScaleFtPerPt` / `Drawing.ScaleResidualIn`.

- **Plan positions.** Grid-line positions are the written dimensions (exact to the drawing). Members
  on grid lines and everything at grid intersections are exact to the grid. Infill members are
  measured from the tag (`Drawing.PlanErrorM`, about 1.5 pt x scale: ~0.03 m at 3/16" = 1'-0").
  On the synthetic set: mean 0.007 m, max 0.016 m.
- **Elevations.** Beams: top of steel at the level's stated elevation (no deck or slope deducted).
  Columns: from the top of pier (foundation note) or the lowest storey to the highest storey.
  Footings: top at the top of footing, L x W x T from the schedule. Piers: top of footing to top of
  pier. Grade beams: top at the top of footing; the **axis** runs grid line to grid line (the
  analytical line the plan states), the **bbox** between the footing faces.
- **Braces** come from elevation text only (the brace lines are vector graphics): the half bay that
  holds the tag, bottom at the outer grid line, top at mid-bay one storey up. A chevron is assumed
  for the axis; the bbox is the same for a V.
- **Sections** are nominal, from the designation alone (W18 = 18 in deep, flange width ~0.45 d;
  HSS / angles from their dimensions; concrete from schedules). Unknown sections are assumed and
  say so in `Drawing.GeometryRule`.
- **Connections** are small nominal boxes at the member end, inside the member's depth and 30 mm or
  more below the top of steel (so a slab bears on the beam, not on the plate). Base plates sit at the
  column base.

## Occurrences: where each element is printed (two-sided evidence)

Every element carries **every** printed appearance that was merged into it, so the UI can open the
sheet at the box (drawing side of extraction idea #6; the calc side is calc-mapper's link rects):

- `Drawing.Occurrences`: JSON array, plan / elevation tags first, then schedule rows, callouts, notes:
  `[{ "file", "sheet", "page", "rect": [x0, y0, x1, y1], "how", "text" }]` - rect in PDF points,
  top-left origin, page 1-based within `file`; `how` is `plan_tag | elevation_tag | schedule_row |
  detail_callout | note` (the synthetic registry truth's vocabulary).
- `Drawing.OccurrenceCount`; the first occurrence again as `Drawing.Sheet`, `Drawing.Page`,
  `Drawing.Rect`, `Drawing.Tag`; and in `source`: `{ format: "drawing", file, nativeId:
  "S-201:p3:[x0,y0,x1,y1]", nativeType: "plan_tag" }`.

Params are primitives by contract, hence the JSON string. The graph keeps params unchanged
through `serialize()`.

## Params

| key | meaning |
|---|---|
| `Drawing.Role` | `girder`, `infill`, `frame_beam` (elevation only), `grade_beam`, `brace`, `column`, `pier`, `footing`, `connection`, `base_plate`, `deck` |
| `Drawing.Grid` | grid reference (`1/A..B`, `A..B/1..2`, `1/A`) |
| `Drawing.SFRS`, `Drawing.Studs`, `Drawing.CamberIn`, `Drawing.FrameSystem` | from the tag / markers |
| `Drawing.Storeys` | columns: `Level 1 - Roof` |
| `Drawing.Member`, `Drawing.End` | connections: the member id and end |
| `Detail.Ref`, `Detail.Refs`, `Detail.Title` | connections: callout(s) and the detail panel's title; `mark` = the type (`ST-3`, `BP-4`) |
| `Drawing.CalloutAttribution`, `Drawing.CalloutDistancePt` | how a callout was attributed (proximity: the leader is not traced) |
| `Drawing.CalloutAmbiguous`, `Drawing.CalloutRunnerUp` | a second member within 1.5 x the distance: the attribution is a guess between the two |
| `Schedule.Text` | the schedule row(s) for the element's mark |
| `Drawing.SizeConflict`, `Drawing.TypeConflict` | two sheets print different sizes / types for one element (first kept, warned) |
| `Drawing.Rule.<how>` | the rule that read each kind of occurrence |
| `Drawing.GeometrySource`, `Drawing.GeometryRule`, `Drawing.PlanErrorM`, `Drawing.Scale*` | geometry provenance and precision |

## Relations (stated only)

| Drawing | emitted |
|---|---|
| detail callout attributed to a member end | `connects` connection - member, rule `drawing detail callout`, detail `{ callouts: "3/S-501@S-201", attribution }` |
| column schedule base plate row | `connects` base plate - column, rule `column schedule base plate` |

`source` is `"explicit"` (stated by the drawing); the callout attribution is by proximity and the
evidence says so. Everything else (beam on girder, column on pier, slab on beams) is inferred by
`buildGraph` from the geometry.

## Not read (text layer only)

The drawing's text is read; its vector graphics are not. So: member lines (positions come from
tags and grids), callout leaders (attribution by proximity, flagged when ambiguous), moment flags /
drag diamonds and other symbols, brace shapes (chevron assumed). Also: scanned sheets (no text
layer), plans not drawn north-up, non-orthogonal members (skipped, warned), columns that are on no
schedule or elevation, more than one building grid per set, sections.

## Scripts and the synthetic gate

```bash
node packages/drawing-parser/scripts/parse.ts --pdf drawings.pdf [--pdf more.pdf] --out model.json [--graph graph.json]
node packages/drawing-parser/scripts/score.ts --model model.json \
  --truth <synthetic_v2>/registry_truth.json --design <synthetic_v2>/design.json \
  [--out score.json] [--baseline packages/drawing-parser/eval/baseline.json --gate] [--misses]
npx tsc -p packages/drawing-parser/tsconfig.json
npx vitest run --root packages/drawing-parser
```

The gate runs on the synthetic v2 generator's fictional drawing set only
(`tools/calcgraph-reference/synth/v2`: `drawings.pdf`, `registry_truth.json`, `design.json`).
Never commit or score a real (copyrighted) set. `eval/baseline.json` holds the numbers; `--gate`
fails when any gets worse. Tests use pages built in code (`test/helpers.ts`), no PDF.
