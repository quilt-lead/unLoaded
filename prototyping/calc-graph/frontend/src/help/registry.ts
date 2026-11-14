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
    short: "Switch between the views: the synthetic IFC app, the drawing-set view, the v2 move-a-column work, and the old (legacy) pages.",
    real: "The legacy pages are the previous vanilla version, kept until the React port matches them.",
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
    title: "Synthetic IFC app",
    short: "A synthetic steel building (IFC) mapped to a synthetic calc package: 3D model, load-path graph, links with evidence, and impact of a change.",
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
  "home.legacy": {
    title: "Legacy pages",
    short: "The previous (vanilla) version of the two views, kept reachable until the React port reaches parity.",
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
