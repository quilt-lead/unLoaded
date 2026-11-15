// Help entries for the v2 move-a-column UI (src/routes/v2, owned by R3). Merged into HELP by
// src/help/registry.ts; scripts/check-help.mjs reads every file in src/help/entries/ as part of the
// registry, so the same rules apply (ids used, entries used, no em dashes, terms link to terms).
// Same format as registry.ts: two-space indented "id": { ... } entries.
import type { HelpEntry } from "../registry";

export const V2_HELP = {
  // ---------------------------------------------------------------- glossary terms
  "term.health-meter": {
    kind: "term",
    title: "Health meter",
    short:
      "How hard it is to move or remove an element, as a band (easy, moderate, hard, do not move) and a 0 to 100 score, with the reasons.",
    what: "The band is the worst reason found. Easy = recalc only. Moderate = a member or typical connection goes up a size, or a footing grows. Hard = a column re-size, a foundation clash, a connection beyond the typical details, a removal, a lateral-system column, or the lateral analysis changes. Do not move = a lateral-system move whose frame members must re-size, or drift already at the limit.",
    read: "Score = 25 per band step, plus up to 15 for the number of calcs to redo and up to 10 for how far the worst estimated UC is above 0.80. Two elements in the same band are ranked by the score.",
    source:
      "The impact engine (backend/calcgraph/move_impact.py) from estimates only, never from a re-design.",
    terms: ["term.unity-check", "term.sfrs", "term.estimate"],
  },
  "term.stale-record": {
    kind: "term",
    title: "Stale calc record",
    short:
      "A calc record that no longer describes the building after a change, so it has to be redone.",
    what: "Found by walking the load path from the moved column: beams that frame into it change span, girders carrying those beams get new point loads, columns and footings get new tributary load, connections get new end reactions, and a lateral-system column makes the whole lateral analysis stale.",
    read: "The reason chain shows each step from the moved column to the record, so you can see why it is on the list.",
    terms: ["term.calc-record", "term.load-path"],
  },
  "term.estimate": {
    kind: "term",
    title: "Estimate (screening)",
    short:
      "A quick new demand and UC for an affected member at its current size, so you can see what is likely to fail before redoing the calc.",
    what: "Beams and girders are re-solved locally (PyNite) on their new span with the loads their own calc prints. Columns scale the H1 interaction with the new axial load. Footings check bearing at the current size. Connections compare the new end reaction with the typical detail's capacity.",
    real: "Estimates are not a re-design. The Re-run button runs the real design code and is the number to trust.",
    terms: ["term.unity-check"],
  },
  "term.sfrs": {
    kind: "term",
    title: "Lateral system (SFRS)",
    short:
      "The seismic force-resisting system: the moment frames and braced frames that carry wind and earthquake load.",
    what: "In the synthetic building: special moment frames on lines A and D, a chevron braced frame on line 3, and collectors. Moving a column that belongs to it changes frame stiffness, drift and force distribution, so the lateral analysis must be re-run.",
  },
  "term.change-order": {
    kind: "term",
    title: "Potential change order",
    short:
      "What a design change would cost on site and in the office: submittals to resubmit, RFIs to reopen, sheets to revise, steel to re-size or replace, and schedule lost.",
    real: "Here every figure is an estimate from stated unit rates on a synthetic project, and the platform records are mock.",
    terms: ["term.construction-stage"],
  },
  "term.construction-stage": {
    kind: "term",
    title: "Construction stage",
    short:
      "How far an element has got: design, submitted, approved, fabricated, delivered, erected. The later the stage, the harder a change.",
    what: "Taken from the (mock) construction platforms: shop-drawing submittals per area and the schedule. An erected column means field rework; an approved submittal means a resubmittal.",
  },
  "term.minimum-change": {
    kind: "term",
    title: "Minimum-change re-design",
    short:
      "Re-design after a move where every surviving member keeps its size unless it fails, and then only goes up to the next size that works.",
    what: "This is how an engineer handles a move. A from-scratch lightest-section design would also downsize members, which nobody does for a move.",
  },
  "term.mock": {
    kind: "term",
    title: "Mock",
    short:
      "Data or an action that imitates a real system (Procore, Autodesk Build, ETABS) without talking to it. Everything mock is labelled on screen.",
    real: "No credentials, no network calls. Mock records are shaped like the real APIs so a real connector can replace them later.",
  },
  "term.e2k": {
    kind: "term",
    title: ".e2k file",
    short:
      "ETABS's text model format. calc-graph writes one from the design (optionally with the move applied) that ETABS could import.",
    real: "Written and read back by calc-graph. ETABS has not opened these files.",
  },

  // ---------------------------------------------------------------- pages
  "page.v2-move": {
    title: "Move a column",
    short:
      "Pick a column, move or remove it, and see every affected element, the calcs to redo, how hard the change is, and the potential change order.",
    read: "Heat view colours every column by how hard it is to move. Move mode lets you drag a column (3D ghost or plan) or type offsets; the impact runs when you drop it.",
    real: "Synthetic building and documents. Construction platforms and ETABS are mock and labelled.",
    terms: ["term.health-meter", "term.stale-record", "term.synthetic"],
  },
  "page.v2-element": {
    title: "Element registry page",
    short:
      "One element and every place it appears: the IFC object, plan tags, schedule rows, detail callouts, spec articles, calc rows, ETABS objects and construction-platform records.",
    read: "Click an occurrence to open its source on the right (PDF page with the spot highlighted, or the 3D model with the element selected). The graph shows how the element relates to others.",
    terms: ["term.element-registry", "term.occurrence"],
  },
  "page.v2-etabs": {
    title: "ETABS link",
    short:
      "The synthetic building as ETABS would hold it, plus the .e2k export. Shows which adapter answered: mock, our PyNite re-run, or real ETABS through the Windows bridge.",
    terms: ["term.mock", "term.e2k"],
  },
  "stat.v2-synthetic": {
    title: "Synthetic building",
    short:
      "A fictional 3-storey steel office generated and designed by calc-graph, with its IFC, drawings, spec book and calc package.",
    source: "data/synthetic_v2, produced by synth/v2/generate.py.",
    terms: ["term.synthetic"],
  },

  // ---------------------------------------------------------------- move workspace
  "panel.move-mode": {
    title: "Heat view / Move mode",
    short:
      "Heat view colours every column by how hard it would be to move. Move mode lets you pick one column and move or remove it.",
    terms: ["term.health-meter"],
  },
  "panel.move-band-basis": {
    title: "Design vs construction status",
    short:
      "Design rates the move on engineering alone. With construction status it also counts what is already approved, fabricated, delivered or erected.",
    real: "Construction status comes from mock Procore / Autodesk Build data. In this synthetic project Level 2 steel is erected, so every column is do not move once it is applied.",
    terms: ["term.construction-stage"],
  },
  "panel.move-offsets": {
    title: "Offsets",
    short:
      "Type the move in feet (dx along the number grids, dy along the letter grids), or tick Remove, then Check impact. Snap sets the drag increment.",
    read: "Positive dx moves toward grid 5, positive dy toward grid D. Drags are limited to 20 ft.",
  },
  "panel.move-undo": {
    title: "Undo / Redo",
    short:
      "Step back or forward through every edit on this page: column picked, dx/dy typed, a drag (one step per drag), snap, Remove, a scenario, Reset, Check impact, Apply as model revision and Re-run calcs.",
    what: "Setup edits swap the whole move setup, so the impact results follow the restored setup. Apply and Re-run wrote revisions, and revisions are never deleted: undoing one writes ANOTHER revision that restores the state before it (for example 'Undid revision R3: restored R2 as R4'), and redo writes one restoring it again.",
    read: "Hover a button to see the step it will undo or redo. Cmd+Z (Ctrl+Z) undoes, Shift+Cmd+Z (Shift+Ctrl+Z) redoes, except while typing in a text or number field, which keeps its own undo. The history lasts for this browser tab, including reloads.",
    source:
      "Setup history in the tab's sessionStorage. Revision undo: POST /api/v2/revisions/model/restore (re-ingests the earlier IFC as a new model revision) and POST /api/v2/revisions/calc/restore (a new calc revision carrying the earlier results).",
    real: "If another tab applied or undid a model revision in between, the model undo is refused rather than guessing; reload to pick up the current history.",
    terms: ["term.revision"],
  },
  "panel.move-scenarios": {
    title: "Scenarios",
    short:
      "Design scenarios (another lateral layout, such as ORIG, the original single-SCBF layout, with what real ETABS found on it) and the test moves the impact engine is scored against. Pick a move to load it, or a design scenario to see its frames and ETABS results.",
    source:
      "GET /api/v2/scenarios, the answer key (design_scenarios + scenarios) built by re-designing the whole building for each move; real ETABS findings from the saved runs in data/fixtures/etabs_runs.",
  },
  "panel.move-side": {
    title: "Impact",
    short:
      "Everything about the current move: how hard it is, which calcs to redo, re-run results, the potential change order, model revisions and ETABS.",
  },
  "tab.move-side": {
    title: "Impact views",
    short:
      "Switch between the views of the current move. Calcs to redo and Change order appear once a move has been checked.",
  },
  "tab.move-health": {
    title: "Health",
    short:
      "How hard the selected column is to move, with the reasons, plus the heat list of every column.",
    terms: ["term.health-meter"],
  },
  "tab.move-calcs": {
    title: "Calcs to redo",
    short:
      "Every calc record the move makes stale, grouped by calc, with the reason chain.",
    terms: ["term.stale-record"],
  },
  "tab.move-rerun": {
    title: "Re-run",
    short:
      "Results of re-running stale calcs with the design code: old vs new values and the regenerated calc pages.",
  },
  "tab.move-co": {
    title: "Change order",
    short:
      "Submittals, RFIs, sheets, spec articles, records, cost and schedule the move would touch.",
    terms: ["term.change-order"],
  },
  "tab.move-revision": {
    title: "Revisions",
    short:
      "Apply the move as a new model revision and compare revisions before / after.",
    terms: ["term.revision"],
  },
  "tab.move-etabs": {
    title: "ETABS",
    short:
      "Send the move to ETABS (mock) and pull results; shows which adapter answered.",
    terms: ["term.mock"],
  },
  "tab.move-views": {
    title: "Model views",
    short:
      "3D model or plan. Both show the same colours and both let you drag the column.",
  },
  "tab.move-3d": {
    title: "3D",
    short:
      "The IFC model. In move mode, drag the blue ghost (or its base disc) to move the selected column.",
  },
  "tab.move-plan": {
    title: "Plan",
    short:
      "A plan of Level 2 with grids and framing. Drag a column square to move it; dashed blue lines are re-framed members.",
  },
  "viewer3d.move-model": {
    title: "3D model",
    short:
      "The synthetic IFC. Click a column to select it. In move mode drag the blue ghost on the ground to move it; elements recolour by estimated UC after the drop.",
    read: "Orbit with left-drag elsewhere, zoom with the wheel, pan with right-drag. Faded grey = not affected.",
    source:
      "GET /api/v2/model.ifc (or a stored revision), read with web-ifc. Ghost and re-framed members are drawn from the impact geometry.",
    terms: ["term.globalid"],
  },
  "viewer3d.move-plan": {
    title: "Plan view",
    short:
      "Grids, the framing of one level and every column. Column squares with a dark outline are in the lateral system. Drag one in move mode to move it.",
    read: "Thick purple lines are lateral-frame members. After a move: members coloured by estimated UC, dashed blue = new member position.",
    terms: ["term.sfrs"],
  },
  "legend.move-heat": {
    title: "How hard to move",
    short:
      "Column colour = health band for a small probe move (2 ft each way, worst case).",
    terms: ["term.health-meter"],
  },
  "legend.band-easy": {
    title: "Easy",
    short: "Recalcs only: nothing goes over capacity at its current size.",
  },
  "legend.band-moderate": {
    title: "Moderate",
    short:
      "A beam, girder or typical connection goes up a size, or a footing grows.",
  },
  "legend.band-hard": {
    title: "Hard",
    short:
      "A column re-size, a foundation clash, a connection beyond the typical details, a removal, a lateral-system column, or the lateral analysis changes.",
  },
  "legend.band-dnm": {
    title: "Do not move",
    short:
      "A lateral-system move whose frame members must re-size, drift already at the limit, no rolled shape works, or (with construction status) steel already erected.",
  },
  "legend.lateral-frame": {
    title: "Braced / moment frame",
    short:
      "The lateral system over the faded gravity framing: chevron braces solid, braced-frame and moment-frame beams lighter. Columns keep their how-hard-to-move colour.",
  },
  "legend.move-uc": {
    title: "Estimated UC",
    short:
      "After a move, affected members are coloured by their estimated new unity check at their current size. While a new approval date is being estimated, the previous date's colours stay, dimmed.",
    terms: ["term.estimate", "term.unity-check"],
  },
  "legend.uc-ok": {
    title: "Up to 0.90",
    short: "Still passes with margin at the current size (estimate).",
  },
  "legend.uc-near": {
    title: "0.90 to 1.00",
    short:
      "Still passes, with little margin (estimate). Worth checking in the re-run.",
  },
  "legend.uc-over": {
    title: "Over 1.00",
    short:
      "Fails at its current size (estimate): expect the next size up or the next typical detail.",
  },
  "legend.uc-stale": {
    title: "Recheck",
    short:
      "Its calc record is stale but the screen made no number for it (for example a pier or base plate, or a lateral record). Redo the calc.",
  },
  "legend.uc-moved": {
    title: "Moved column",
    short: "The column being moved and its ghost at the new position.",
  },
  "stat.move-health-design": {
    title: "Design band",
    short:
      "How hard the move is on engineering grounds alone, from the screen's estimates.",
    source:
      "health.band from POST /api/v2/impact (or GET /api/v2/health for the heat view).",
    terms: ["term.health-meter"],
  },
  "stat.move-health-construction": {
    title: "Band with construction status",
    short:
      "The same move rated again with what has been built or approved: erected steel, approved submittals, open RFIs and schedule float.",
    real: "Construction status is mock platform data.",
    terms: ["term.construction-stage", "term.mock"],
  },
  "panel.move-reasons-design": {
    title: "Design reasons",
    short:
      "Engineering reasons, worst first: lateral role, over-capacity members, connections, foundation, removal, fan-out and worst UC.",
  },
  "panel.move-reasons-construction": {
    title: "Construction status reasons",
    short:
      "Reasons from the construction platforms: stage of the steel, submittals that would need resubmitting.",
    real: "From the construction platforms: synthetic (mock) records unless a platform is set to live and signed in - the badge says which.",
  },
  "panel.move-construction": {
    title: "Construction status",
    short:
      "Stage of the selected column on site, its shop-drawing submittals and open RFIs, and schedule float.",
    source:
      "GET /api/v2/construction-status/{element}, from the mock platform adapters.",
    terms: ["term.construction-stage", "term.mock"],
  },
  "panel.move-heat-list": {
    title: "Every column",
    short:
      "All columns sorted hardest first, with the top reason. Click one to select it.",
  },
  "stat.move-stale": {
    title: "Calcs to redo",
    short:
      "Calc records made stale by the move (load path, connections, foundations and lateral).",
    terms: ["term.stale-record"],
  },
  "stat.move-worst-uc": {
    title: "Worst UC (estimate)",
    short:
      "The highest estimated unity check among affected members at their current sizes.",
    terms: ["term.estimate"],
  },
  "stat.move-sheets": {
    title: "Sheets",
    short:
      "Drawing sheets that show an affected element and will need revising.",
  },
  "stat.move-screened": {
    title: "Demand change over 5%",
    short:
      "Records whose estimated demand changes by more than 5%. The rest are stale by topology only. Click to filter.",
    terms: ["term.estimate"],
  },
  "stat.move-over": {
    title: "Over 1.0 (estimate)",
    short:
      "Affected elements whose estimated UC is over 1.0 at their current size.",
  },
  "panel.move-rerun-all": {
    title: "Re-run all stale",
    short:
      "Re-runs every stale record with the design code in load-path order (beams, girders, columns, footings, connections, then the lateral system as one job). Writes a new calc revision; the Re-run tab shows each stage while it runs.",
    real: "This is calc-graph's own design code (PyNite + AISC 360 / 341 + ACI 318 checks), not ETABS.",
    terms: ["term.minimum-change"],
  },

  // ---------------------------------------------------------------- re-run
  "stat.rerun-records": {
    title: "Records re-run",
    short: "How many calc records were recomputed in this calc revision.",
  },
  "stat.rerun-resized": {
    title: "Re-sized",
    short:
      "Records whose member or detail had to go up a size to pass under the new layout.",
    terms: ["term.minimum-change"],
  },
  "stat.rerun-ng-ok": {
    title: "NG to OK",
    short:
      "Records that fail (NG) at the old size under the new layout and pass (OK) after the re-size.",
  },
  "stat.rerun-still-ng": {
    title: "Still NG",
    short:
      "Records that still fail after the re-run: no size or detail in the tables works. These need an engineer.",
  },
  "panel.rerun-method": {
    title: "Method",
    short:
      "How the new values were made: calc-graph's design code re-run (statics, PyNite frame analysis, AISC / ACI checks), minimum-change re-design, in load-path order.",
    real: "Our re-run, not ETABS and not the original engineer's software.",
  },
  "table.rerun-step": {
    title: "Step",
    short:
      "Order the record was re-run in. Inputs go first, so a girder is re-run after the beams it carries.",
  },
  "table.rerun-job": {
    title: "Job",
    short:
      "Gravity records run one by one in load-path order; lateral records run together as one frame analysis.",
  },
  "table.rerun-uc": {
    title: "UC old to new",
    short:
      "Original UC, then (for re-sized members) the UC at the old size under the new layout, then the UC after the re-run.",
    terms: ["term.unity-check"],
  },
  "panel.rerun-history": {
    title: "Earlier calc revisions",
    short:
      "Every re-run is kept as its own calc revision. Click one to load its results.",
  },
  "panel.rerun-page-style": {
    title: "New page style",
    short:
      "Package style = the revised sheet in the calc package's own layout. Re-run sheet = the same calc as rendered math from the Python that computed it (handcalcs). When a record has no math sheet, the reason is shown beside the button.",
  },
  "evidence.rerun-compare": {
    title: "Old vs new calc page",
    short:
      "Left: the record's row in the original calc package. Right: the same record on the regenerated page of the new calc revision. Both highlighted.",
    real: "The right-hand page is generated by calc-graph from its re-run.",
  },

  // ---------------------------------------------------------------- change order
  "panel.co-mock": {
    title: "Platform data: live or mock",
    short:
      "Submittals, RFIs, sheets, budget lines and schedule come from the construction platforms. The badge says whether each is read live (CALCGRAPH_PLATFORM_<NAME>=live and signed in) or is synthetic mock data; hover it for the reason a platform is on mock.",
    terms: ["term.mock", "term.change-order"],
  },
  "stat.co-cost": {
    title: "Cost estimate",
    short:
      "Sum of the cost lines: steel tonnage changes, replacing fabricated or erected pieces, connection and foundation rework, fireproofing, engineering and resubmittals.",
    source: "Unit rates in Assumptions (synthetic, not a quote).",
    terms: ["term.estimate"],
  },
  "stat.co-range": {
    title: "Cost range",
    short:
      "Rough-order-of-magnitude band: 0.8 to 1.35 times the estimate (assumed accuracy).",
  },
  "stat.co-slip": {
    title: "Forecast slip",
    short:
      "How many working days the forecast project finish moves, from re-running the schedule with the change's work inserted as activities.",
    what: "The work an element needs is cumulative by stage: revise under review (submitted); EOR redesign, re-detail and re-review (approved); plus re-fabricate the replacement (fabricated or delivered); plus a field swap or footing enlargement (erected). It starts the morning after approval and must finish before the element's next open activity. 'Driven by' names the hold that sets the new finish.",
  },
  "stat.co-delay": {
    title: "Past contract",
    short:
      "Working days the new forecast finish goes past the contract completion date. 0 = absorbed by float.",
  },
  "stat.co-float": {
    title: "Float used",
    short: "Project float consumed, in working days.",
  },
  "panel.co-submittals": {
    title: "Submittals",
    short:
      "Shop-drawing submittals that include an affected element. Approved or later ones would have to be resubmitted; the action column says what to do.",
    terms: ["term.construction-stage"],
  },
  "panel.co-rfis": {
    title: "RFIs",
    short:
      "Requests for information about affected elements. Closed ones may need reopening; open ones must be answered with the change in mind.",
  },
  "panel.co-sheets": {
    title: "Sheets",
    short:
      "Drawing sheets showing an affected element. Open sheet shows the page with the affected tags highlighted.",
  },
  "panel.co-specs": {
    title: "Spec articles",
    short:
      "Spec articles governing the touched elements, grouped by the registry link that brings each in (lateral frame, member type, material, detail, affected submittal), collapsed. Open a group to see its articles and how many touched elements the link reaches.",
    read: "An article brought in by several links is listed under each; the badge on the section counts distinct articles.",
    source: "registry_view.governing_specs for every touched element (change order spec_links).",
  },
  "panel.co-records": {
    title: "Calc records",
    short:
      "Stale records whose estimated demand changes by more than 5%; each is priced as engineering redesign in the cost lines.",
  },
  "panel.co-cost": {
    title: "Cost lines",
    short:
      "Every priced item with its basis: quantity, unit rate and any factor applied.",
  },
  "table.co-basis": {
    title: "Basis",
    short:
      "How the figure was worked out, including the assumed unit rate and source of weights (AISC shapes database).",
  },
  "panel.co-schedule": {
    title: "Schedule",
    short:
      "The change's work, inserted into the schedule as its own activities: how long each takes, when it runs, and which existing activity it must finish before (with that activity's finish and float before and after).",
    terms: ["term.estimate"],
  },
  "panel.co-assumptions": {
    title: "Assumptions",
    short:
      "The unit rates and schedule rules used for every estimate. Synthetic, stated so you can challenge them.",
  },
  "panel.platform-record": {
    title: "Platform record",
    short:
      "One platform record: its normalised fields and the platform-shaped API object. The badge says LIVE (read from the platform API) or MOCK (synthetic, no network call).",
    real: "Live or mock, as the badge says.",
    terms: ["term.mock"],
  },

  // ---------------------------------------------------------------- revisions
  "panel.rev-apply": {
    title: "Apply as model revision",
    short:
      "Re-designs the building for this move (minimum change), writes a new IFC, stores it as a new model revision and shows the diff against its parent.",
    read: "Takes several seconds. Nothing is overwritten. Every move is computed from the base design, so the new revision's parent is the base design revision and its diff shows only this move, even when an earlier move is the current head.",
    terms: ["term.revision", "term.minimum-change"],
  },
  "panel.rev-list": {
    title: "Model revisions",
    short:
      "Model revisions of the current design, newest first. Revisions of earlier designs (another base model) are collapsed below. Show loads one into the 3D view (colours still follow the current move).",
    source: "GET /api/v2/revisions: a revision belongs to the design whose base revision its parent chain ends at.",
    read: "'from N' is the revision a revision's content was derived from: the base design for an applied move, the restored revision for an undo or redo.",
  },
  "panel.rev-diff": {
    title: "Before / after diff",
    short:
      "Element-by-element differences between two model revisions, matched by IFC GlobalId.",
    terms: ["term.globalid"],
  },
  "table.rev-field": {
    title: "Field",
    short:
      "Property that changed: section, span, studs, camber, footing size, or geometry (moved / resized).",
  },
  "stat.rev-changed": {
    title: "Changed",
    short:
      "Elements present in both revisions with at least one changed property or geometry.",
  },
  "stat.rev-added": {
    title: "Added",
    short:
      "Elements only in the after revision (for example a new transfer member after a removal).",
  },
  "stat.rev-removed": {
    title: "Removed",
    short:
      "Elements only in the before revision (for example the removed column and its footing).",
  },
  "stat.rev-edges": {
    title: "Load-path edges",
    short:
      "Supports / bears-on links added and removed between the two revisions.",
    terms: ["term.load-path"],
  },

  // ---------------------------------------------------------------- ETABS
  "panel.etabs-real": {
    title: "Real ETABS run",
    short:
      "A saved run of this design in real ETABS (version and date in the label): first modes, story drift by line against the design, and the per-member ETABS vs PyNite agreement.",
    read: "Shown only while this design's e2k is byte-identical to the one ETABS ran (sha1). A run of an earlier version of the design is listed as stale. Agreement: rows within the flag % of PyNite, over the like-for-like comparisons only.",
    source: "data/fixtures/etabs_runs (scripts/build_etabs_run_fixture.py from the compare_etabs_pynite.py report of the run). GET /api/v2/etabs/runs.",
    real: "Real ETABS 23.3.2 results, read through CSI OAPI on the Windows bridge. Everything else on this page is the mock unless the bridge answers.",
  },
  "stat.etabs-mode1": {
    title: "Mode 1",
    short: "Period and shape of the first mode in the real ETABS run: X or Y translation, or torsional (the building twists first, a lateral-layout problem).",
  },
  "stat.etabs-drift-ratio": {
    title: "Worst drift / limit",
    short: "The largest story drift over the allowed drift (0.020 hsx) on any lateral line in the real ETABS run. Over 1.00 = drift NG.",
  },
  "stat.etabs-flagged": {
    title: "Rows over flag %",
    short: "Per-member comparisons where ETABS and our PyNite frames differ by more than the flag % (governing design combo), out of every comparison made.",
  },
  "table.etabs-agreement": {
    title: "ETABS vs PyNite agreement",
    short: "Per line, member kind and quantity (M, V, P): how many like-for-like comparisons fall within the flag %, and the median and largest difference.",
    read: "Rows the comparator reports but does not score (beam axial under the rigid diaphragm, SCBF columns, 2D-frame-only column axial) show as not like-for-like.",
  },
  "panel.design-scenario": {
    title: "Design scenario",
    short:
      "Another lateral layout of the building from the answer key (not a move). Shows its frames, the design's own drift ratios and what real ETABS found on it.",
    read: "The 3D, the plan and the move tools stay on the current design; the ETABS tab shows this scenario's saved runs.",
  },
  "panel.etabs": {
    title: "ETABS model",
    short:
      "The design as ETABS objects: stories, frames, points, sections, load cases, combos, design ratios and drifts.",
    terms: ["term.mock"],
  },
  "stat.etabs-answered": {
    title: "Answered by",
    short:
      "Which adapter produced these values: mock ETABS (our design mapped to ETABS objects), our PyNite re-run, or real ETABS read through the Windows bridge (CSI OAPI or BHoM).",
    real: "The server picks the adapter (CALCGRAPH_ETABS_ADAPTER). Today it is the mock unless the Windows bridge is configured and answering.",
    terms: ["term.mock"],
  },
  "panel.etabs-e2k": {
    title: ".e2k export",
    short:
      "Download the model (or the model with this move) as an ETABS text file.",
    terms: ["term.e2k"],
  },
  "panel.etabs-send": {
    title: "Send / pull",
    short:
      "Send packages the move (.e2k + change list). Pull brings back results as if ETABS had re-analysed it.",
    real: "With the mock adapter, nothing is sent; pulled values are our own PyNite re-run in ETABS result shapes.",
    terms: ["term.mock"],
  },
  "stat.etabs-max-ratio": {
    title: "Max D/C",
    short: "Highest demand / capacity ratio among frame design results.",
    terms: ["term.unity-check"],
  },
  "stat.etabs-over": {
    title: "Frames over 1.0",
    short: "Frame members whose ratio exceeds 1.0 after the change.",
  },
  "stat.etabs-sections": {
    title: "Sections changed",
    short: "Frame objects whose section changed in the re-design.",
  },
  "tab.etabs-objects": {
    title: "Object kinds",
    short: "ETABS object types. Counts are the number of objects of each kind.",
  },
  "tab.etabs-design": {
    title: "Design D/C",
    short:
      "Steel frame design summary: ratio, governing combo and check per frame, sorted highest first.",
  },
  "tab.etabs-drift": {
    title: "Drifts",
    short:
      "Story drift per frame line and load case, with the allowable and the demand / capacity.",
  },
  "tab.etabs-frames": {
    title: "Frames",
    short:
      "Beam, column and brace objects with their section, material and end points.",
  },
  "tab.etabs-points": {
    title: "Points",
    short: "Joint objects (column lines at each story).",
  },
  "tab.etabs-sections": {
    title: "Sections",
    short: "Frame section properties used in the model.",
  },
  "tab.etabs-combos": {
    title: "Combos",
    short: "Load combinations (ASCE 7-16).",
  },
  "tab.etabs-cases": {
    title: "Load cases",
    short: "Load cases (dead, live, roof live, seismic, wind...).",
  },
  "tab.etabs-stories": {
    title: "Stories",
    short: "Story names, elevations and heights.",
  },

  // ---------------------------------------------------------------- registry element page
  "panel.reg-occurrences": {
    title: "Every occurrence",
    short:
      "Every place this element appears, grouped by source. Click one to open it in Source.",
    terms: ["term.occurrence", "term.element-registry"],
  },
  "panel.reg-platforms": {
    title: "Construction platforms",
    short:
      "Every platform record that names this element (submittals, RFIs, budget lines, schedule activities, ...), each with live / mock, and its construction stage.",
    real: "Live or mock per platform, as the badges say.",
    terms: ["term.mock", "term.construction-stage"],
  },
  "panel.reg-designed-by": {
    title: "Designed by",
    short:
      "The calc records that check this element. Click to open the row in the calc package.",
    terms: ["term.calc-record"],
  },
  "panel.reg-source": {
    title: "Source",
    short:
      "The original document page with the occurrence highlighted, the 3D model with the element selected, or the ETABS object.",
  },
  "stat.reg-ifc": {
    title: "IFC model",
    short: "The element's object in the IFC model (by GlobalId).",
    terms: ["term.globalid"],
  },
  "stat.reg-drawings": {
    title: "Drawings",
    short:
      "Plan tags, elevation tags, schedule rows and detail callouts on the drawing set. Each place appears once; a schedule row carries its row header from the drawing (for a column, the storey tier, e.g. L3 - ROOF).",
  },
  "stat.reg-specs": {
    title: "Specs",
    short:
      "Spec articles that govern this element: its own links plus those of its type, the type's material and the frames it belongs to. Each row says which link brought the article in (via).",
  },
  "stat.reg-calcs": {
    title: "Calcs",
    short: "Rows or sheets in the calc package that print this element.",
  },
  "stat.reg-etabs": {
    title: "ETABS",
    short:
      "ETABS objects that represent this element (one per story for a column).",
    real: "Mock ETABS model built from our design.",
  },
  "stat.reg-platforms": {
    title: "Platforms",
    short:
      "Construction-platform records (live or mock) that name this element.",
    terms: ["term.mock"],
  },
  "graph.reg-relations": {
    title: "Relations",
    short:
      "How this element relates to others: what frames into it, what it bears on, its connections, type, grids, spec articles and the calc records that design it.",
    read: "Edge labels are the relation kind. Up to 14 nodes per side; the rest are counted. Click a node to open it.",
    source:
      "GET /api/v2/elements/{id}: relations_in, relations_out and designed_by.",
    terms: ["term.element-registry"],
  },
  "graph.reg-lane-in": {
    title: "Points at this element",
    short:
      "Elements whose relation ends here (for example beams that frame into a column, connections that connect it).",
  },
  "graph.reg-lane-self": {
    title: "This element",
    short: "The element this page is about.",
  },
  "graph.reg-lane-out": {
    title: "This element points at",
    short:
      "Where this element's relations go: its type, grids, what it bears on, its connection and the calc records that design it.",
  },
  "legend.reg-relations": {
    title: "Node colours",
    short: "Colour of a node by what it is.",
  },
  "legend.reg-node-element": {
    title: "Element",
    short:
      "A physical element or organising object (member, connection, footing, grid, frame, level).",
  },
  "legend.reg-node-type": {
    title: "Type / material",
    short: "A section type or material that elements are instances of.",
  },
  "legend.reg-node-spec": {
    title: "Spec article",
    short: "A spec book article. Click to open it highlighted.",
  },
  "legend.reg-node-record": {
    title: "Calc record",
    short: "A calc record that designs this element.",
    terms: ["term.calc-record"],
  },
} as const satisfies Record<string, HelpEntry>;
