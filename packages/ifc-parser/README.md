# @unloaded/ifc-parser

Parses IFC (STEP, IFC2X3 / IFC4 / IFC4X3) into the format-neutral `ModelInput`
defined in `@unloaded/element-graph/input`, using [web-ifc](https://github.com/ThatOpen/engine_web-ifc) 0.0.66.
It reports what the file **states**: elements, explicit relations, levels and a
small geometry summary. It never infers connectivity from geometry. That is the
graph's job.

Runs in Node and in the browser. `src/` has no `fs` or `path` usage.

## API

```ts
import { parseIfc, ifcParser, type IfcParseOptions } from "@unloaded/ifc-parser";

const model = await parseIfc(bytes /* Uint8Array */, {
  fileName: "model.ifc",        // -> meta.source.file
  wasmPath: "/wasm/",           // dir containing web-ifc.wasm (browser); optional in Node
  geometry: true,               // bbox / axis / section (default true)
  includeKinds: ["beam", "column", "connection"], // filter after kind resolution
  kindMap: { "IfcMember.STUD": "column", IfcChimney: "other" },
  onProgress: (phase, fraction) => {}, // init | open | index | elements | geometry | relations | done
});

ifcParser.id;            // "ifc"
ifcParser.extensions;    // ["ifc"]
ifcParser.canParse(name, head?); // head given -> ISO-10303-21 sniff; else *.ifc
ifcParser.parse(bytes, opts);
```

Also exported: `KIND_TABLE`, `LINEAR_KINDS`, `CONNECTION_NAME_RE`,
`createKindResolver`, `normaliseProfile`, `profileFromText`, `hasStepHeader`.

`parseIfc` throws only for unrecoverable input (not STEP, schema web-ifc cannot
open). Everything else goes to `warnings`. The model is always closed (`finally`).
One `IfcAPI` per `wasmPath` is initialised lazily and reused.

## Kind mapping (`src/kind-map.ts`)

| IFC entity | kind |
|---|---|
| IfcBeam, IfcBeamStandardCase | beam |
| IfcColumn, IfcColumnStandardCase | column |
| IfcSlab (+StandardCase, ElementedCase), IfcRoof | slab |
| IfcWall, IfcWallStandardCase, IfcWallElementedCase | wall |
| IfcFooting | footing |
| IfcPile | pile |
| IfcMember (+StandardCase) | brace. By PredefinedType: BRACE, STRUT -> brace; CHORD, COLLAR, PURLIN, RAFTER, STRINGER -> beam; POST -> column; STUD, MULLION, PLATE -> other |
| IfcPlate (+StandardCase) | connection (CURTAIN_PANEL -> other) |
| IfcDiscreteAccessory, IfcBearing | connection |
| IfcMechanicalFastener, IfcFastener | fastener |
| IfcElementAssembly | other. ACCESSORY_ASSEMBLY or a connection-like name -> connection |
| IfcBuildingElementProxy | other. Connection-like name -> connection |

"Connection-like name" is `CONNECTION_NAME_RE` (connection, shear tab, base
plate, fin plate, end plate, gusset, cleat, splice, bracket, hanger, beam shoe,
...), tested against Name, ObjectType and the type object's Name.
PredefinedType comes from the instance, or from the type object when the
instance's is NOTDEFINED/USERDEFINED/absent (IFC2X3 style). Elements that are
`RealizingElements` of an IfcRelConnectsWithRealizingElements become
`connection` (unless they are fasteners or a kindMap override applies).

Overrides: `kindMap["IfcType.PREDEFINED"]` > `kindMap["IfcType"]` > table.
Keys are case-insensitive. A kindMap key for an entity not in the table also
makes that entity extracted. Other element types are skipped with a counted
warning, for example `unsupported element type IfcChimney: 1 instance(s) skipped`.
Spatial elements, openings, annotations and grids are ignored silently.

## Element fields

- `id`: GlobalId. If it is missing, `ifc-express-<expressID>` is used with a
  warning. Duplicate GlobalIds keep the first occurrence and log a warning.
- `mark`: first non-placeholder value of the pset properties `Mark`,
  `Piece Mark`, `Reference Mark`, `Reference`, `Type Mark`, case-insensitive,
  instance psets before type psets. The fallback is the `Tag` attribute, unless
  it looks like an authoring-tool id (long digits/dots, or a GUID).
  Placeholders such as `n.a.`, `-`, `none` and `n/a` are ignored.
- `profile`: material profile set ProfileName, then the swept solid's
  ProfileName (Body representation, through mapped items and boolean clips),
  then a regex over Name / ObjectType / type name / profile set name (W12X26,
  HSS6X6X3/8, IPE300, HEA200, 305X165X40UB, 600X300, ...), then a value built
  from the parametric profile in mm (`I190X200`, `400X200`, `D300`, `CHS168`).
  The result is upper-cased, whitespace removed, `x`/`×`/`*` turned into `X`.
- `material`: IfcRelAssociatesMaterial (instance, else type). For layer,
  profile and constituent sets and material lists, the first entry's
  IfcMaterial name is used.
- `levelId`: IfcRelContainedInSpatialStructure. If that is missing or points at
  a non-storey, the parser walks up containment and aggregation, so parts of an
  assembly inherit its storey. Elements under IfcSite/IfcBuilding get no level.
- `source`: `{ format: "ifc", nativeId: expressID, nativeType: "IfcBeam" }`.

## Params (`params`)

| key | origin |
|---|---|
| `Attr.Name`, `Attr.ObjectType`, `Attr.Tag`, `Attr.PredefinedType`, `Attr.TypeName` | entity attributes |
| `<PsetName>.<Prop>` | IfcPropertySingleValue / EnumeratedValue (joined with ", ") / ListValue (single value, or joined) |
| `<PsetName>.<Prop>.Upper` / `.Lower` / `.SetPoint` | IfcPropertyBoundedValue |
| `<PsetName>.<Complex>.<Prop>` | IfcComplexProperty |
| `<QtoName>.<Quantity>` | IfcElementQuantity: length, area, volume, weight, count, time |
| `Geom.Length`, `Geom.InclinationDeg` | linear kinds with geometry: centreline length (m) and angle from horizontal |

Type psets (`IfcTypeObject.HasPropertySets`) are applied first. Instance psets
(IfcRelDefinesByProperties) override them. IFC typed values are unwrapped:
numbers stay numbers, IfcBoolean/IfcLogical become booleans (UNKNOWN becomes
null), enums and labels become strings.

**Units in params:** values typed as length, area, volume or mass measures,
in both properties and quantities, are converted to SI (m, m², m³, kg). The
property's own `Unit` is used when present, otherwise the project
IfcUnitAssignment. All other measures (forces, ratios, counts, ...) stay as in
the file.

## Units and axes

- The project length unit is read from IfcUnitAssignment: IfcSIUnit with any
  prefix, or IfcConversionBasedUnit (FOOT, INCH, ...) through its
  ConversionFactor, with a name table as fallback. If there is no length unit,
  metres are assumed and a warning is logged.
- **web-ifc meshes are already in metres.** web-ifc 0.0.66 folds the project
  length scale into `PlacedGeometry.flatTransformation`. This was checked on
  millimetre files (the sample and the tiny fixture) and on a FOOT
  conversion-based unit (test `handles conversion-based units`). The parser
  does not rescale geometry.
- **web-ifc emits Y-up.** Its world frame is `(X_ifc, Z_ifc, -Y_ifc)`. The
  parser undoes this, `ifc = (x, -z, y)`, so all output is IFC-native Z-up.
  Checked by storey elevation against wall z-ranges, the column axis
  running along +Z, and beam bboxes.
- `COORDINATE_TO_ORIGIN` is **not** set, so coordinates are the IFC
  engineering coordinates. IfcMapConversion (georeferencing) is **not**
  applied, by web-ifc or by this parser.
- Storey `elevation` is the world z of the storey's `ObjectPlacement`
  (evaluated through the IfcLocalPlacement chain), so it is in the same frame as
  the geometry. The `Elevation` attribute is the fallback. A warning is logged
  if the two disagree by more than 1 mm.

## Geometry summary

For each element, web-ifc `StreamMeshes` gives the vertices, which are
transformed to IFC Z-up metres. From them:

- `bbox`: world AABB, rounded to 1 µm for stable output.
- `axis` (beam, column, brace, pile): the principal axis by PCA of the
  vertices. If the axis is within 3° of a world axis it is snapped to that axis
  (vertex PCA is biased on short or coarse meshes). The axis runs through the
  centre of the cross-section extents, end to end. For columns `start` is the
  lower end.
- `section`: `{depth, width}` from the profile def (in metres). If there is no
  profile def, the PCA cross-section extents are used: depth is the more
  vertical extent for beams and the larger one for columns.
- Elements without a body representation get no `geometry`, and the count goes
  into the warnings. For example, an IfcRoof decomposed into beams keeps no
  bbox. The parser deliberately does not take the union of the parts.

## Relations (explicit only)

| IFC | emitted |
|---|---|
| IfcRelConnectsElements, IfcRelConnectsPathElements | `connects` (rule = entity name, connection types in detail) |
| IfcRelConnectsWithRealizingElements | `connects` from relating and related element to each realizing element |
| IfcRelAggregates (parent and child both emitted elements) | `part_of` (a = child, b = parent) |
| IfcRelConnectsStructuralMember + IfcRelAssignsToProduct | `connects` between the physical products of members sharing a structural connection (or member to the connection's physical product). A warning is logged if members cannot be mapped. |

`evidence = { rule, source: "explicit", detail: { ifcRelId, ifcRelGlobalId, ... } }`.
`connects` is undirected and normalised so `a < b`. Duplicates are removed.
A relation is emitted only when both of its ends are emitted elements.

Output ordering is deterministic: elements are sorted by id, relations by
(kind, a, b, rule), and levels by elevation.

## Browser / Vite setup

web-ifc loads `web-ifc.wasm` at runtime. In a Vite app, copy it into the
public dir and pass the directory:

```bash
# e.g. as a postinstall / predev script in the app
cp node_modules/web-ifc/web-ifc.wasm public/wasm/
```

```ts
const model = await parseIfc(new Uint8Array(await file.arrayBuffer()), {
  fileName: file.name,
  wasmPath: "/wasm/", // absolute URL path to the folder (trailing slash optional)
});
```

The parser forces web-ifc's single-threaded build, so no COOP/COEP headers or
`web-ifc-mt.wasm` are needed. You may need `optimizeDeps: { exclude: ["web-ifc"] }`
in `vite.config.ts` if Vite's prebundling interferes. Parsing is synchronous
wasm work after `Init`, so run it in a Web Worker for large files.

In Node, `wasmPath` can be omitted: web-ifc's Node build finds
`web-ifc-node.wasm` next to itself. To pass it explicitly, use the directory of
`require.resolve("web-ifc/web-ifc.wasm")`.

## Scripts and tests

```bash
npx tsc -p packages/ifc-parser/tsconfig.json
npx vitest run --root packages/ifc-parser        # or: npm test -w @unloaded/ifc-parser
node packages/ifc-parser/scripts/dump.ts [file.ifc]  # Node >= 22.18 (type stripping); summary of a file
```

Fixtures live in the repo-level `data/` folder; provenance is in `data/README.md`.
