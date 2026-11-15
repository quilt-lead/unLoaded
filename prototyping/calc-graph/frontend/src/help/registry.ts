// THE help registry: every "i" mark in the app reads its text from here, and the glossary page
// (/help) is generated from it. Written for a structural engineer who is new to the tool.
//
// Rules (enforced by scripts/check-help.mjs inside `npm run build`, locally and in CI):
//  - every id used in the UI (InfoTip id="...", info="...", info: "...", helpFamily("x", ...)) exists here;
//  - every entry here is used somewhere (terms are used by the glossary, family entries by helpFamily);
//  - the component categories listed in check-help.mjs (Panel, StatPill, Tabs, Legend, ...) always
//    get an info id - their props also require `info: HelpId`, so omission is a type error in CI;
//  - no em dashes (house style: hyphens).
// Ids are kebab-case with a dotted prefix: nav. page. panel. tab. stat. legend. graph. pdf. viewer3d.
// evidence. home. and term. for glossary terms. Keep `short` to one or two plain sentences.

import { V2_HELP } from "./entries/v2";
import { ASOF_HELP } from "./entries/asof";

export interface HelpEntry {
  /** label shown as the popover heading and the glossary entry name */
  title: string;
  /** one or two sentences, shown on hover / focus */
  short: string;
  /** "Learn more" sections (all optional) */
  what?: string;
  source?: string;
  read?: string;
  /** what is real and what is mocked or synthetic */
  real?: string;
  /** glossary terms this entry relies on (rendered as links to /help#<id>) */
  terms?: readonly `term.${string}`[];
  /** "term" = glossary term (used by /help even if no "i" mark points at it) */
  kind?: "term";
}

export const HELP = {
  // ---------------------------------------------------------------- glossary terms
  "term.calc-package": {
    kind: "term",
    title: "Calc package",
    short: "The structural calculations submitted with a design: a PDF of hand calcs, spreadsheet pages and analysis software output.",
    what: "Usually organised in sections (criteria, gravity, lateral, foundations, connections). The tool splits it into calc pages and calc records.",
  },
  "term.calc-record": {
    kind: "term",
    title: "Calc record",
    short: "One design check for one member or group, for example the row of a beam design table, or a footing sheet.",
    what: "A calc package page often holds many records (a RAM table has one row per beam). A record knows its inputs, its result and the page area it came from, so it can be highlighted.",
    terms: ["term.calc-package", "term.unity-check"],
  },
  "term.load-path": {
    kind: "term",
    title: "Load path",
    short: "How load travels through the structure: deck to beam, beam to girder, girder to column, column to footing.",
    what: "The model's load path is built from geometry (what bears on what). The calc load path is built from the calcs (which calc's output is another calc's input). Comparing the two shows calcs that no longer describe the building.",
  },
  "term.unity-check": {
    kind: "term",
    title: "Unity check (UC)",
    short: "Demand divided by capacity. Below 1.0 passes, above 1.0 fails (NG).",
    what: "Also called the demand / capacity ratio. A UC close to 1.0 leaves little margin when something changes.",
  },
  "term.tier": {
    kind: "term",
    title: "Link tier",
    short: "How an element was matched to a calc, from strongest (exact mark) to weakest (element type only), with a confidence score.",
    what: "Tiers in order: exact mark, mark range, mark ignoring punctuation, mark family, section size + type, unique partial mark, element type only. Cross-references are capped low.",
    read: "High-tier links are usually right; low-tier links need a human to confirm or reject.",
  },
  "term.provenance": {
    kind: "term",
    title: "Provenance",
    short: "Where a fact came from: which document, page and words, which rule or method produced it, and how confident it is.",
    what: "Every element, link and finding keeps its provenance so you can open the source and check it.",
  },
  "term.evidence": {
    kind: "term",
    title: "Evidence",
    short: "The exact words on a page (with their position) that a link or finding is based on.",
    read: "Click any link or finding to open the original page with the evidence highlighted.",
    terms: ["term.provenance"],
  },
  "term.occurrence": {
    kind: "term",
    title: "Occurrence",
    short: "One place an element appears: an IFC object, a plan tag, a schedule row, a detail callout, a spec article or a calc row.",
    terms: ["term.element-registry"],
  },
  "term.element-registry": {
    kind: "term",
    title: "Element registry",
    short: "One record per element with every occurrence across the model, drawings, specs, calcs and construction platforms, plus how elements relate.",
    what: "Relations include supports, bears-on, frames-into, connected-by, instance-of (type), specified-by (spec article) and designed-by (calc record).",
    terms: ["term.occurrence"],
  },
  "term.join": {
    kind: "term",
    title: "Exact / inferred / absent join",
    short: "How two calc records were connected: exact = a shared label, inferred = matched by coordinates, absent = no support could be found.",
    read: "Absent joins are gaps in the calc load path worth checking.",
    terms: ["term.load-path"],
  },
  "term.revision": {
    kind: "term",
    title: "Revision",
    short: "Every upload or edit is stored as a new revision, never overwritten, so any two can be compared.",
  },
  "term.globalid": {
    kind: "term",
    title: "IFC GlobalId",
    short: "The permanent identifier of an object in an IFC model. It stays the same across model revisions, so changes can be tracked.",
  },
  "term.synthetic": {
    kind: "term",
    title: "Synthetic data",
    short: "A made-up building, drawing set, spec book and calc package generated from one designed model, so every answer is known exactly.",
    real: "Firm, engineer and project names in the synthetic documents are fictional. Platform records (Procore, Autodesk Build) and ETABS objects in the v2 data are mocks shaped like the real APIs.",
  },

  // ---------------------------------------------------------------- app shell
  "nav.viewer-switch": {
    title: "Viewer switch",
    short: "Switch between the views of the Harbor View building: the IFC app, the drawing-set view and move a column.",
  },
  "nav.theme": {
    title: "Theme",
    short: "Switch between light and dark. By default the app follows your system setting.",
  },
  "nav.help": {
    title: "Help and glossary",
    short: "Every explanation behind the \"i\" marks, plus definitions of the terms the tool uses, on one page.",
  },

  // ---------------------------------------------------------------- pages
  "page.home": {
    title: "Calc Graph",
    short: "Links a structural model, its drawings and its calc package, keeps the evidence for every link, and shows what goes stale when something changes.",
    terms: ["term.calc-package", "term.evidence"],
  },
  "page.glossary": {
    title: "Glossary",
    short: "All help text in one place. Terms first, then every \"i\" mark grouped by where it appears.",
  },
  "page.dev-components": {
    title: "Component gallery",
    short: "Developer page: each shared component rendered with real API data where the server has it, sample data otherwise (labelled).",
  },
  "home.ifc": {
    title: "IFC app",
    short: "The Harbor View building's IFC model mapped to its calc package: 3D model, load-path graph, links with evidence, and impact of a change.",
    terms: ["term.synthetic", "term.load-path"],
  },
  "home.set": {
    title: "Drawing-set view",
    short: "A drawing set and calc package read as documents: elements off the plans, calc records, connections and findings, each opening the original page.",
    terms: ["term.calc-record", "term.evidence"],
  },
  "home.v2": {
    title: "Move a column (v2)",
    short: "Move or remove a column in the synthetic v2 building and see which calcs to redo, how hard the change is, and the potential change order.",
    real: "Built on synthetic data; construction platform records and ETABS are mocked and labelled as such.",
    terms: ["term.synthetic", "term.element-registry"],
  },

  // ---------------------------------------------------------------- dev gallery: v2 sample panel
  "panel.v2-model": {
    title: "Synthetic v2 model",
    short: "Counts from the synthetic v2 building: elements by type, calc records by kind and relations by kind.",
    source: "GET /api/v2/summary, built from data/synthetic_v2/design.json by the generator.",
    terms: ["term.synthetic", "term.calc-record"],
  },
  "stat.v2-elements": {
    title: "Elements",
    short: "Structural elements and organising objects in the v2 model (columns, beams, girders, braces, connections, footings, levels, grids...).",
  },
  "stat.v2-records": {
    title: "Calc records",
    short: "Design checks in the synthetic calc package, one per member or group.",
    terms: ["term.calc-record"],
  },
  "stat.v2-relations": {
    title: "Relations",
    short: "Typed links between elements, types, spec articles and calc records (supports, bears-on, designed-by, feeds...).",
    terms: ["term.element-registry"],
  },
  "stat.v2-occurrences": {
    title: "Occurrences",
    short: "Places elements appear across the drawings, specs and calcs (the IFC and ETABS occurrences are added per element).",
    terms: ["term.occurrence"],
  },
  "tab.elements": { title: "Elements", short: "Element counts by type." },
  "tab.records": { title: "Calc records", short: "Calc record counts by kind of check.", terms: ["term.calc-record"] },
  "tab.relations": { title: "Relations", short: "Relation counts by kind.", terms: ["term.element-registry"] },

  // ---------------------------------------------------------------- legends
  "legend.edge-styles": {
    title: "Edge styles",
    short: "How confident each edge in the graph is.",
    terms: ["term.join"],
  },
  "legend.edge-exact": {
    title: "Exact",
    short: "Solid line: the two records share a label (for example a beam mark), so the join is certain.",
  },
  "legend.edge-inferred": {
    title: "Inferred",
    short: "Dashed line: joined by position (coordinates), not by a shared label. Usually right, worth a glance.",
  },
  "legend.edge-absent": {
    title: "Absent",
    short: "Red dotted line to a gap node: no support or source could be found for this end. Check it.",
  },
  "legend.link-tiers": {
    title: "Link confidence",
    short: "Colour of an element-to-calc link by its confidence score.",
    terms: ["term.tier"],
  },
  "legend.link-high": { title: "75% and above", short: "Strong link, usually an exact or ranged mark." },
  "legend.link-mid": { title: "55 to 74%", short: "Plausible link (mark family or section size). Worth confirming." },
  "legend.link-low": { title: "Below 55%", short: "Weak link (type only or a cross-reference). Confirm or reject it." },

  "legend.member-types": {
    title: "Member colours",
    short: "3D members coloured by element type.",
    source: "Element types from the synthetic v2 design (GET /api/v2/design), matched to the IFC by GlobalId.",
    terms: ["term.globalid"],
  },
  "legend.type-column": { title: "Columns", short: "Vertical members carrying floor and roof load down to the foundations." },
  "legend.type-girder": { title: "Girders", short: "Primary beams on the grid lines; they carry the infill beams and frame into columns." },
  "legend.type-beam": { title: "Beams", short: "Infill floor and roof beams; they carry the deck and frame into girders." },
  "legend.type-brace": { title: "Braces", short: "Diagonal members of the braced frames (lateral system)." },
  "legend.type-foundation": { title: "Foundations", short: "Piers, footings and grade beams." },

  // ---------------------------------------------------------------- graph
  "graph.calc-dependency": {
    title: "Calc dependency graph",
    short: "Which calc records feed this one and which it feeds. Click a node to select it, click an edge to see why it exists.",
    source: "GET /api/v2/records/{id}: inputs recorded by the generator (fed_by / feeds).",
    terms: ["term.calc-record", "term.load-path"],
  },
  "graph.lane-inputs": { title: "Feeds in", short: "Records whose results are inputs to the selected record (for a column: the beams and girders it carries)." },
  "graph.lane-record": { title: "Selected record", short: "The calc record being looked at." },
  "graph.lane-downstream": { title: "Feeds out", short: "Records that take the selected record's result as an input (for a column: base plate, pier and footing)." },

  // ---------------------------------------------------------------- PDF
  "pdf.page": {
    title: "Original page",
    short: "The source PDF page, drawn in the browser, with the evidence highlighted. Scroll to zoom, drag to pan.",
    read: "Highlight zooms back to the evidence; Page shows the whole page; PDF opens the file at this page.",
    terms: ["term.evidence"],
  },
  "pdf.split": {
    title: "Split view",
    short: "Two pages one above the other, for example a calc row and the plan it refers to. Close returns to one page.",
  },
  "evidence.compare": {
    title: "Evidence side by side",
    short: "The same element on two documents next to each other, each zoomed to where it appears.",
    terms: ["term.occurrence", "term.evidence"],
  },

  // ---------------------------------------------------------------- 3D
  "viewer3d.model": {
    title: "3D model",
    short: "The IFC model drawn in the browser. Drag to orbit, scroll to zoom, right-drag to pan, click a member to select it.",
    source: "The stored IFC file, read with web-ifc.",
    terms: ["term.globalid"],
  },

  // ---------------------------------------------------------------- per-feature entry files (src/help/entries/*.ts)
  ...V2_HELP,
  ...ASOF_HELP,
  // ---------------------------------------------------------------- R2: synthetic IFC app (/ifc)
  "page.ifc": {
    title: "IFC app",
    short: "A BIM model (IFC) and its calc package (PDF) linked element by element, with the evidence for every link and the calcs that go stale when a member changes.",
    what: "Shows the Harbor View building (the synthetic v2 building Move a column works on): its IFC model becomes an element graph with load-path edges, its calc package is split into calcs, and each element is linked to the calcs that cover it. Upload your own IFC or PDF to add a revision.",
    real: "The Harbor View building, firm and calc package are synthetic. The model shown is the project's head revision, so a move applied in Move a column appears here. Uploading your own IFC and PDF runs the same deterministic mapping on them.",
    terms: ["term.synthetic", "term.load-path", "term.tier"],
  },
  "tool.ifc-upload-model": {
    title: "Upload a BIM model",
    short: "Choose an IFC 2x3 or IFC4 file. Each upload is stored as a new model revision and re-mapped against the current calc package.",
    source: "POST /api/projects/{pid}/model (the Harbor View project). The file is kept as-is; elements, marks, sizes and storeys are read from it with IfcOpenShell.",
    terms: ["term.revision", "term.globalid"],
  },
  "tool.ifc-upload-calcs": {
    title: "Upload a calc package",
    short: "Choose the calc package PDF. Each upload is a new calc revision: the PDF is split into calcs and every element is linked again.",
    source: "POST /api/projects/{pid}/calcs (the Harbor View project). Sheet ids, titles and sections come from the set profile; text is read from the PDF's text layer; scanned pages have none and are flagged.",
    terms: ["term.calc-package", "term.revision"],
  },
  "tool.ifc-load-v2": {
    title: "Load Harbor View documents",
    short: "Ingests what the Harbor View project lacks: the base model (only when the project has no model yet) and the calc package (when the head calc revision is not the current file).",
    read: "Moves applied in Move a column are new model revisions of the same project, so the head may be a moved model; the revisions list shows them all.",
    source: "POST /api/projects/v2/documents, reading data/synthetic_v2/model.ifc and calc_package.pdf.",
    terms: ["term.synthetic", "term.revision"],
  },
  "tool.ifc-export": {
    title: "Export mapping JSON",
    short: "Downloads the current mapping (elements, calcs, links with their evidence and status, decisions, load-path and calc edges) as one JSON file.",
    source: "GET /api/projects/{pid}/export (the Harbor View project) for the head model and calc revisions.",
  },
  "stat.ifc-elements": { title: "Model elements", short: "Structural elements read from the IFC model: beams, columns, braces, slabs, footings, connections and walls." },
  "stat.ifc-edges": {
    title: "Load-path edges",
    short: "Bearing relations found from the model's geometry (a beam frames into a column, a column bears on a footing). They form the element graph.",
    terms: ["term.load-path"],
  },
  "stat.ifc-calcs": {
    title: "Calcs",
    short: "Calculations found in the calc package and how many PDF pages it has. A calc is a titled run of pages (for example a beam design or a footing sheet).",
    terms: ["term.calc-package"],
  },
  "stat.ifc-calcs-linked": { title: "Calcs linked", short: "Calcs with at least one model element linked to them. Calcs with none are either front matter, scanned, or name nothing in the model." },
  "stat.ifc-calc-deps": {
    title: "Calc dependencies",
    short: "Places where one calc uses another's result (for example beam reactions carried into the column design). They form the calc graph.",
    terms: ["term.load-path"],
  },
  "stat.ifc-linked": {
    title: "Elements linked",
    short: "Elements with a confident (80% or more) or confirmed link to a calc. Click to show only these in 3D.",
    terms: ["term.tier"],
  },
  "stat.ifc-review": {
    title: "Need review",
    short: "Elements whose best link is below 80% confidence and not yet confirmed. Click to show only these; confirm or reject them in the inspector.",
    terms: ["term.tier"],
  },
  "stat.ifc-unmapped": { title: "No calc found", short: "Elements no calc names by mark, size or type. Click to show only these; link one by hand from the inspector if a calc does cover it." },
  "stat.ifc-revs": { title: "Revisions", short: "The head model revision and the head calc revision the mapping was built from. Every upload is a new revision.", terms: ["term.revision"] },
  "panel.ifc-calcs": {
    title: "Calc package",
    short: "Every calc in the package with its pages, software, how many elements it covers and how many links still need review. Click one to select it.",
    read: "A coloured square is the calc's colour in 3D. 'stale - re-run' appears after an impact check when the calc depends on a changed member.",
    terms: ["term.calc-package"],
  },
  "tabs.ifc-view": { title: "Centre view", short: "Switch the middle of the screen between the 3D model and the load-path graph. Both follow the same selection." },
  "tab.ifc-3d": { title: "3D model", short: "The IFC model drawn in the browser, coloured by calc, by match status or by element type." },
  "tab.ifc-graph": {
    title: "Load-path graph",
    short: "The selected element's load path (or an impact's footprint) beside the calc graph, with the element-to-calc links between them.",
    terms: ["term.load-path"],
  },
  "tool.ifc-colour": { title: "Colour by", short: "By calc: each element in the colour of its best calc. By match status: linked, needs review, no calc. By element type: beam, column, slab..." },
  "tool.ifc-level": { title: "Level", short: "Show one storey only (from the IFC building storeys). The view refits to what is shown." },
  "tool.ifc-xray": { title: "X-ray", short: "Makes every member semi-transparent so members behind others, such as columns inside walls, can be seen and clicked." },
  "tool.ifc-fit": { title: "Fit", short: "Moves the camera so everything visible fits the view." },
  "legend.ifc-colour": { title: "Colours", short: "What the 3D colours mean in the current colour mode. During an impact check the colours show the impact instead." },
  "legend.ifc-calc-item": { title: "Calc colour", short: "Elements whose best live link is to this calc." },
  "legend.ifc-no-calc": { title: "No calc found", short: "Grey: no calc covers this element (or all its links were rejected)." },
  "legend.ifc-status-confirmed": { title: "Linked", short: "The best link is 80% or more, or a reviewer confirmed it or linked it by hand." },
  "legend.ifc-status-review": { title: "Needs review", short: "The best link is below 80% and nobody has confirmed it yet." },
  "legend.ifc-status-unmapped": { title: "No calc found", short: "No live link: no calc names the element's mark, size or type." },
  "legend.ifc-type-item": { title: "Element type", short: "The element's structural category, read from its IFC class (IfcBeam, IfcColumn, IfcSlab, IfcFooting...)." },
  "legend.ifc-removed": { title: "Removed / orphaned", short: "Members that would be removed, or lose their support, if the selected member were changed or removed." },
  "legend.ifc-impacted": { title: "Impacted / stale", short: "Members on the load path below the change, and calcs that use them: those calcs need re-running." },
  "graph.ifc-load-path": {
    title: "Load-path graph",
    short: "Columns of elements by type (slabs to foundations) and the calc graph on the right. Click a node to select it, click an edge to see why it exists.",
    read: "With an element selected: its full path down to the foundations and two levels up. After an impact check: everything the change reaches. Up to 18 elements per column.",
    terms: ["term.load-path", "term.calc-package"],
  },
  "graph.ifc-lane-slabs": { title: "Slabs", short: "Floor and roof slabs and decks: where gravity load starts." },
  "graph.ifc-lane-beams": { title: "Beams and braces", short: "Beams and girders carrying the slabs, and the braces of the lateral system." },
  "graph.ifc-lane-connections": { title: "Connections", short: "Connection objects in the model (shear tabs, moment connections, base plates) that transfer load between members." },
  "graph.ifc-lane-columns": { title: "Columns and walls", short: "Vertical members taking load down to the foundations." },
  "graph.ifc-lane-foundations": { title: "Foundations", short: "Footings and piles: where the load path ends." },
  "graph.ifc-lane-other": { title: "Other", short: "Elements of any other IFC class on the path." },
  "graph.ifc-lane-calcs": { title: "Calc graph", short: "Every calc (front matter excluded); arrows show which calc's result feeds which. A purple fill is a calc, orange means stale after the impact check." },
  "legend.ifc-graph": { title: "Graph key", short: "Edge and node colours of the load-path graph." },
  "legend.ifc-graph-load-path": { title: "Load path", short: "Grey line: this element delivers load to that one (from the model geometry)." },
  "legend.ifc-graph-calc-dep": { title: "Calc dependency", short: "Purple line: one calc's output is another calc's input, found from the text of the package." },
  "legend.ifc-graph-mapping": { title: "Element to calc link", short: "Dashed purple: the element's best link to a calc (one per element, to keep the graph readable)." },
  "legend.ifc-graph-mapping-low": { title: "Link to review", short: "Dashed orange: the best link is below 80% and not confirmed. Check it in the inspector." },
  "panel.ifc-inspector": {
    title: "Inspector",
    short: "Details of what is selected. Nothing selected: the mapping summary. A calc: its pages, inputs, outputs and elements. An element: its links, decisions and load path.",
  },
  "panel.ifc-impact": {
    title: "Impact",
    short: "What changing or removing the selected member reaches: removed or orphaned members, members on the load path below it (by wave), and the calcs that go stale.",
    read: "A wave is one step down the load path from the change. Hand calcs and scanned calcs are flagged for an engineer rather than re-run.",
    source: "GET /api/projects/{pid}/impact (the Harbor View project): a walk of the model's load-path graph from the member, then every calc linked to a reached member and every calc downstream of those.",
    terms: ["term.load-path"],
  },
  "panel.ifc-rerun": { title: "Re-run queue", short: "Calcs that depend on a reached member, each with why. These are the calcs to redo after the change." },
  "insp.ifc-review": { title: "Needs review", short: "Elements whose best link is below 80% and unconfirmed. Click one to see the link and its evidence." },
  "insp.ifc-unmapped": { title: "No calc found", short: "Elements with no live link. Click one to link it to a calc by hand if a calc covers it." },
  "insp.ifc-no-mark": { title: "Elements without a mark", short: "Elements with no Mark property in the IFC. They can only be linked by section size or element type, which is weaker." },
  "insp.ifc-revisions": {
    title: "Revisions",
    short: "Every model and calc upload, newest first; (head) marks the revisions the mapping uses. Times are Eastern.",
    terms: ["term.revision"],
  },
  "insp.ifc-calc-inputs": { title: "Takes input from", short: "Calcs whose results this calc uses, with the rule that found it (for example a reaction value or a label quoted from the other calc)." },
  "insp.ifc-calc-feeds": { title: "Feeds", short: "Calcs that use this calc's results. If this calc changes, these may need re-running too." },
  "insp.ifc-tier-group": { title: "Elements by link tier", short: "Elements linked to this calc, grouped by how they were matched (mark, mark range, size, type...).", terms: ["term.tier"] },
  "insp.ifc-confirm-all": { title: "Confirm all to review", short: "Confirms every link of this calc that is below 80% and not yet decided. Each is stored as a reviewer decision and can be undone." },
  "insp.ifc-impact-buttons": {
    title: "Impact if changed / removed",
    short: "Changed: follows the load path down from this member and lists the calcs that use anything it reaches. Removed: also lists the members that lose their support.",
  },
  "insp.ifc-linked-calcs": {
    title: "Linked calcs",
    short: "Calcs this element is linked to, strongest first, each with the rule, the page and the words that matched. Confirm a right link, reject a wrong one.",
    read: "Open page shows the original calc page with the matched words highlighted. Decisions are stored with your name and time and survive re-uploads of the same model.",
    terms: ["term.tier", "term.evidence"],
  },
  "insp.ifc-manual-link": { title: "Link by hand", short: "Pick a calc that covers this element but was not found automatically. The link is stored as 'linked by hand' at 100%." },
  "insp.ifc-rejected": { title: "Rejected links", short: "Links a reviewer rejected. They no longer colour the model or count as coverage; undo puts the link back." },
  "insp.ifc-load-path": { title: "Load path", short: "Members this element carries load from and delivers load to, from the model geometry. Click one to select it.", terms: ["term.load-path"] },
  "insp.ifc-element": { title: "Element", short: "The element's identity in the IFC: mark, name, type, section size and GlobalId.", terms: ["term.globalid"] },
  "insp.ifc-params": { title: "Parameters", short: "Every property set value on the element, as written in the IFC (the first 40)." },
  "pdf.ifc-calc-page": {
    title: "Calc package page",
    short: "The original calc package page with the words that produced the link highlighted. Scroll to zoom, drag to pan; the arrows step through pages.",
    terms: ["term.evidence"],
  },
  // ---------------------------------------------------------------- R2: drawing-set view (/set)
  "page.set": {
    title: "Drawing-set view",
    short: "A drawing set and its calc package read as documents: elements tagged on the plans, calc pages and calc records, connection details and findings, each opening the original page.",
    what: "Nothing here comes from a model: elements are tags read off the structural sheets, calc records are rows of the calc package tables. Links between them are deterministic rules, and both sides keep the words they came from.",
    read: "Pick something on the left (or in the graph); the inspector lists everything connected to it, and every row opens its evidence on the right.",
    terms: ["term.calc-record", "term.evidence", "term.provenance"],
  },
  "tool.set-overview": { title: "Overview", short: "Clears the selection and goes back to the overview graph of every link, bundled by element group and calc section." },
  "stat.set-elements": {
    title: "Elements",
    short: "Member tags read off the structural sheets (beam, column, footing, brace and detail tags), each with its sheet, grid location and the words on the page.",
  },
  "stat.set-load-path": {
    title: "Load-path edges",
    short: "Bearing relations found on the plans: a beam framing into a column (followed along the drawn line), a column landing on a footing (by grid position).",
    terms: ["term.load-path"],
  },
  "stat.set-calc-pages": { title: "Calc pages", short: "Pages of the calc package, each with its sheet number, title, software and the sizes printed on it.", terms: ["term.calc-package"] },
  "stat.set-calc-feeds": { title: "Calc feed edges", short: "Places one calc page uses another's result: a label defined on one page and used on another, a reaction carried to a foundation, a load area name." },
  "stat.set-linked": { title: "Elements linked", short: "Elements linked to at least one calc page (by size and type, size type and level, the footing schedule, or a drawing reference).", terms: ["term.tier"] },
  "stat.set-no-calc": { title: "No calc found", short: "Elements no calc page covers. Click to list them as findings, each with why no page matched." },
  "stat.set-pages-unlinked": { title: "Calc pages linked to nothing", short: "Calc pages no drawn element links to: definitions, loads, results tables or calcs for things not tagged on the plans. Click to list them." },
  "stat.set-links-by-rule": { title: "Links by rule", short: "How many element-to-page links each matching rule produced, from the strongest (footing schedule, drawing reference) to the weakest (size only).", terms: ["term.tier"] },
  "stat.set-stale": { title: "Stale data", short: "The calc-record or connection layer was built from older inputs than the drawing set. Rebuild it before trusting those tabs." },
  "stat.set-records": { title: "Calc records", short: "Design records read from the calc package tables: one per member, column stack, footing, load or hand calc. Click to open the Calc records tab.", terms: ["term.calc-record"] },
  "stat.set-record-joins": {
    title: "Calc load path joins",
    short: "Edges of the calc load path (floor to member, member to column, column to footing) by how they were joined: exact label, inferred by coordinates, or absent.",
    terms: ["term.join", "term.load-path"],
  },
  "stat.set-connections": { title: "Connections", short: "Connection details on the detail sheets, how many times they are called out on plans and elevations, and how many callouts attach to a drawn member." },
  "stat.set-gaps": { title: "Load-path gaps", short: "Places where the calc load path stops: a load or member that no record carries further down. Click to list them.", terms: ["term.join"] },
  "stat.set-unsupported": { title: "Unsupported member ends", short: "Calc-model members with an end that lands on no column, beam or wall in the calc model. Click to list them." },
  "tabs.set-list": { title: "Lists", short: "Browse what was read from the documents. Each tab groups its items; click a group to open it and an item to select it." },
  "tab.set-elements": { title: "Elements", short: "Tags read off the drawings, grouped by sheet and type, with how many are linked to a calc page." },
  "tab.set-records": { title: "Calc records", short: "The calc package as design records: section, then software run, then table, then record. 'gap' marks a record whose load path stops.", terms: ["term.calc-record"] },
  "tab.set-pages": { title: "Calc pages", short: "The calc package page by page, grouped into runs and sections. Pages are the evidence containers for the records." },
  "tab.set-connections": { title: "Connections", short: "Connection details by detail sheet, and plan symbols that have no detail number, with how many times each is placed." },
  "tab.set-findings": { title: "Findings", short: "Everything the checks found worth a look (no calc found, size mismatch, load-path gaps, grid and storey differences...), grouped by kind." },
  "tool.set-search": { title: "Search", short: "Filters the current tab by size, sheet, grid, calc id or title. Matching groups open automatically." },
  "tabs.set-center": { title: "Centre view", short: "Switch between the graph around the selection and the building's 3D model." },
  "tab.set-graph": { title: "Graph", short: "The selection and what connects to it: load path, calc pages or records, calc load path and connections. Click nodes to select, edges for evidence." },
  "tab.set-3d": { title: "3D model", short: "The building's IFC model with every drawing tag that resolves to a model element coloured by its calc status, connection markers, and a calc model as an optional ghost when the package prints one." },
  "graph.set": {
    title: "Drawing-set graph",
    short: "Columns of related items around the selection. Click a node to select it and open its page; click an edge to see both ends' evidence side by side.",
    read: "Nothing selected: the overview, one bundle per element group and calc section, thicker for more links. An element: its load path, connections, calc records and their calc load path. A record: what feeds it and what carries it.",
    terms: ["term.load-path", "term.join", "term.evidence"],
  },
  "graph.set-lane-el-groups": { title: "Elements by sheet and type", short: "One node per sheet and element type; the count is how many are linked. Click to list them and select the first linked one." },
  "graph.set-lane-calc-sections": { title: "Calc package sections", short: "The calc package's sections (criteria, gravity, lateral, foundations, connections). Click to select the first linked page." },
  "graph.set-lane-elements": { title: "Elements (drawings)", short: "The selected element with what it carries above it and its load path below it, down to the foundation." },
  "graph.set-lane-connections": { title: "Connections", short: "Connection callouts attached to the selected element on the sheets." },
  "graph.set-lane-records": { title: "Calc records", short: "Calc records linked to the element (page links narrowed to the records on the page that print its size); pages with no matching record are shown as pages." },
  "graph.set-lane-calc-load-path": { title: "Calc load path", short: "Where the linked records' loads go next in the calc: the members, columns and footings that carry them." },
  "graph.set-lane-calc-page": { title: "Calc page", short: "The selected calc page." },
  "graph.set-lane-pages-in": { title: "Pages feeding it", short: "Calc pages whose results the selected page uses." },
  "graph.set-lane-pages-out": { title: "Pages it feeds", short: "Calc pages that use the selected page's results." },
  "graph.set-lane-rec-elements": { title: "Elements linked", short: "Drawn elements linked to this record. Click an edge to compare the plan tag and the record row." },
  "graph.set-lane-rec-feeds2": { title: "Feeds (2 hops)", short: "Records that feed the records feeding this one." },
  "graph.set-lane-rec-feeds": { title: "Feeds", short: "Records whose load arrives at this one (for a column: the members framing into it)." },
  "graph.set-lane-rec": { title: "Calc record", short: "The selected record." },
  "graph.set-lane-rec-carried": { title: "Carried by", short: "Where this record's load goes next. A red dashed node means no support was found for that end." },
  "graph.set-lane-rec-then": { title: "Then", short: "The next steps down the calc load path." },
  "graph.set-lane-rec-detail": { title: "Connection detail", short: "A detail that may be the one this connection calc designs. Matched by title only, so it is a candidate, not a link." },
  "graph.set-lane-conn-elements": { title: "Elements", short: "Drawn members the connection callouts attach to (the nearest member within reach of the bubble or leader)." },
  "graph.set-lane-conn-instances": { title: "Instances on the sheets", short: "Every place the detail is called out: section bubbles, plan symbols and text references." },
  "graph.set-lane-conn-detail": { title: "Connection detail", short: "The detail drawing on the detail sheet." },
  "graph.set-lane-conn-calc": { title: "Design calc", short: "The calc that designs this detail, if any. A red node means no calc page in the package designs it." },
  "legend.set-graph": { title: "Graph key", short: "What each edge colour and line style means in the drawing-set graph." },
  "legend.set-load-path": { title: "Load path (drawings)", short: "Solid dark line: one element bears on another on the plans. Click it for both tags on the sheets." },
  "legend.set-calc-feeds": { title: "Calc feeds", short: "Purple line: one calc page uses a value defined on another. Click it for both places on the pages." },
  "legend.set-connection": { title: "Connection", short: "Orange line: a connection callout attached to a member, or an instance of a detail. Dashed orange is a title-only candidate." },
  "panel.set-inspector": {
    title: "Inspector",
    short: "Everything about the selection: what it is, where it is drawn, what it links to and why. Each row opens its evidence; Show opens the item itself.",
  },
  "insp.set-in-3d": { title: "In 3D", short: "Whether the drawing tag resolves to an element of the building model, by which rule, and the model element's storey and profile." },
  "insp.set-load-path": { title: "Load path", short: "What this element bears on and what it carries, with the rule that found each. Click one for both tags on the sheets.", terms: ["term.load-path"] },
  "insp.set-connections": { title: "Connections", short: "Connection callouts attached to this element. Click for the callout and the member on the sheet; Select opens the callout." },
  "insp.set-el-records": { title: "Calc records", short: "Calc records this element is linked to, grouped by calc page. Click a record to compare the plan tag with the record's row.", terms: ["term.calc-record"] },
  "insp.set-el-pages": { title: "Calc pages", short: "Calc pages linked to this element, strongest first, with the rule. Click to compare the plan tag and the page side by side.", terms: ["term.tier"] },
  "insp.set-calc-fed-by": { title: "Fed by", short: "Pages whose values this page uses, with the labels found on both." },
  "insp.set-calc-feeds": { title: "Feeds", short: "Pages that use values from this page." },
  "insp.set-calc-records": { title: "Records on this page", short: "Calc records with a row on this page. Click one to select it." },
  "insp.set-calc-elements": { title: "Elements linked to this page", short: "Drawn elements linked to this page. Click one to compare its tag with the page." },
  "insp.set-rec-notes": { title: "Engineer notes", short: "Handwritten or coloured notes on the calc pages attached to this record, with the rule that attached them." },
  "insp.set-rec-fed-by": { title: "Fed by", short: "Records whose load arrives here, with how the join was made (exact, inferred, absent). Click for both rows.", terms: ["term.join"] },
  "insp.set-rec-carried-by": { title: "Carried by", short: "Where this record's load goes. 'no support found' marks a gap in the calc load path.", terms: ["term.join"] },
  "insp.set-rec-elements": { title: "Elements linked", short: "Drawn elements linked to this record, via which calc page. Click to compare the tag and the row." },
  "insp.set-rec-rows": { title: "Rows on the original pages", short: "Every table row this record was read from, by table. Click to open the row on its page." },
  "insp.set-ctype-calc": { title: "Design calc", short: "The calc that designs this connection detail, if one was found." },
  "insp.set-ctype-instances": { title: "Instances", short: "Where the detail is called out, with the members each callout attaches to. Click one to select it." },
  "insp.set-cinst-detail": { title: "Detail", short: "The connection detail this callout refers to." },
  "insp.set-cinst-attached": { title: "Attached elements", short: "Members this callout attaches to, with their role and distance from the callout in PDF points." },
  "evidence.set-caption": { title: "Evidence caption", short: "What the page on screen is evidence for: the link, edge or finding you clicked, its rule and its confidence." },
  "evidence.set-link-compare": {
    title: "Link evidence",
    short: "The plan tag on the left and the calc page or record row on the right, each zoomed to the words the link was made from.",
    read: "For footings linked through the foundation schedule, the button in the bar swaps the left page to the schedule row.",
    terms: ["term.evidence", "term.tier"],
  },
  "viewer3d.set-model": {
    title: "Building model",
    short: "The building's IFC model. Each drawing tag is tied to its model element by the element registry's resolver (plan and elevation tags, schedule rows). Click a member, calc member or marker to select it.",
    real: "The Harbor View IFC is synthetic. Model elements no drawing tag resolves to are shown uncoloured.",
    terms: ["term.provenance"],
  },
  "stat.set3d-coverage": { title: "3D coverage", short: "How many drawing elements resolve to an element of the building model." },
  "tool.set3d-layers": { title: "Layers", short: "Turn the building model, the connection markers and (when the package prints one) the calc model on or off." },
  "tool.set3d-placement": {
    title: "Calc model placement",
    short: "Beside: the calc model next to the drawn one, no alignment. Overlaid: the two plan extents centred on each other. Neither is a registration.",
  },
  "evidence.set3d-differences": { title: "Differences", short: "Where the calc model and the drawings disagree (grids, frame sizes). Each button opens the calc and drawing pages side by side." },
  "legend.set3d": { title: "3D colours", short: "Colours of the model members by the calc status of the drawing tag tied to them, markers and the calc-model ghost." },
  "legend.set3d-linked": { title: "Tag linked to a calc", short: "The drawing tag on this member is linked to a calc page that prints its size." },
  "legend.set3d-no-calc": { title: "Tag: no calc found", short: "No calc page covers the drawing tag on this member." },
  "legend.set3d-size-mismatch": { title: "Tag: size mismatch", short: "A calc covers the tag but prints a different size than the plans." },
  "legend.set3d-marker": { title: "Connection instance", short: "A connection callout placed at the member it attaches to." },
  "legend.set3d-calc-model": { title: "Calc model (ghost)", short: "Members and columns of the calc model, drawn from the calc record tables in their own coordinates." },
  "legend.set3d-calc-gap": { title: "Calc member, end not supported", short: "A calc-model member with an end that lands on no support in the calc model." },
  "legend.set3d-selected": { title: "Selected", short: "The selection, or the members linked to the selected calc page, record or connection." },
} as const satisfies Record<string, HelpEntry>;

export type HelpId = keyof typeof HELP;

/**
 * Families of ids picked at runtime from data (for example one entry per link tier or finding kind).
 * Declare the prefix here and look ids up with helpFamily("tier", value); the ratchet then treats
 * every entry under the prefix as used. Empty in R1; R2/R3 add families as they need them.
 */
export const HELP_FAMILIES: readonly string[] = [];

export function helpFamily(family: string, key: string): HelpId | undefined {
  const id = `${family}.${key}`;
  return id in HELP ? (id as HelpId) : undefined;
}

export const helpEntry = (id: HelpId): HelpEntry => HELP[id];
